#!/usr/bin/env python3
"""
Tendencia por prenda (geek y urbano) — v0, 2026-10-06.

Qué mide: dentro de un estilo (geek, urbano) y un mercado (España, EEUU), qué prendas aparecen en las fotos de los *referentes* del estilo
(el estilo lo da la persona, no la foto) y cuánto pesan, por temporada (6 meses). Decisiones de Víctor: ver memoria/TFM_tendencias_de_prenda.md.

Flujo (todo en `tendencia_datos/`, aparte de los datos de la app «Analizar mercado»; las fotos no van a git):
  cosechar   fuentes de `tendencia_fuentes.json` (X vía FxTwitter, prensa por nombre vía Bing Noticias, comunidades de Reddit) -> fotos + `fotos.json`
  biblioteca incorpora como muestra de referencia las fotos que Víctor aprobó como urbano / geek en la app
  analizar   detector de prendas (analizar_outfit.py: DeepFashion2 + Florence) + tipo fino con CLIP sobre el recorte -> `prendas.json`
  informe    cuota de fotos por prenda, por estilo × mercado × temporada (mínimo de fotos por cifra) -> `informe.json`
  todo       las cuatro seguidas (es lo que correría cada semana)

Límites conocidos (medidos el 2026-10-06): con las fuentes legibles salen pocas fotos por referente (decenas por temporada); el estampado y la forma NO se
estiman todavía (CLIP sin entrenar: 32 % y no mejora a «siempre oversized»); la visibilidad de la prenda es una heurística de caja pegada al borde.

Uso:  python3 tendencia_prenda.py todo | cosechar [--solo NOMBRE] | biblioteca | analizar [--max N] | informe
"""
import argparse
import collections
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import numpy as np
from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import mercado as m  # noqa: E402  (helpers de red, descarga, CLIP y pesos de la app)

TD = Path(os.environ.get("TENDENCIA_DATOS") or AQUI / "tendencia_datos")
m.CACHE, m.IMG = TD / "cache", TD / "cache" / "img"   # las funciones de cosecha de mercado.py escriben aquí, no en los datos de la app
FUENTES, FOTOS, PRENDAS, INFORME = AQUI / "tendencia_fuentes.json", TD / "fotos.json", TD / "prendas.json", TD / "informe.json"
DET = AQUI.parent / "vlm_atributos_prenda" / "herramientas"
MIN_FOTOS = 5            # decisión de Víctor: por debajo de 5 fotos no se enseña una cifra
VIDA_MEDIA = 10.0        # días, como el informe de estilos
VENTANA_DIAS = 180       # temporada
UMBRAL_DUP = 0.97        # coseno CLIP a partir del cual dos fotos son la misma
SEP_MKT = {"ES": "es-ES", "US": "en-US"}
CONTEXTO = {"musica": ["cantante", "rapero", "rapera", "artista", "cancion", "disco", "concierto", "musica", "trap", "gira", "festival", "album", "single", "videoclip"],
            "streamer": ["streamer", "twitch", "youtuber", "directo", "videojuego", "juego"],
            "music_en": ["rapper", "singer", "artist", "song", "album", "concert", "tour", "festival", "fashion", "style", "outfit", "met gala", "collection"]}
norm = lambda s: unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cargar(ruta: Path) -> dict:
    return m.leer_json(ruta) if ruta.exists() else {}


def guardar(ruta: Path, obj) -> None:
    TD.mkdir(parents=True, exist_ok=True)
    m.guardar_json(ruta, obj)


def temporada(fecha_iso: str | None) -> str | None:
    """Primavera-verano = marzo-agosto, otoño-invierno = septiembre-febrero (6 meses cada una)."""
    try:
        d = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None
    if 3 <= d.month <= 8:
        return f"PV {d.year}"
    return f"OI {d.year}/{str(d.year + 1)[2:]}" if d.month >= 9 else f"OI {d.year - 1}/{str(d.year)[2:]}"


# ---------------------------------------------------------------- cosecha
def registro(cid, s, fecha, url, enlace, titulo, **extra) -> dict:
    if s.get("archivo"):   # persona fallecida o cuenta de archivo: la foto es antigua aunque se publique hoy -> sin fecha (muestra de referencia)
        fecha, extra["archivo"] = None, True
    return {"id": cid, "fuente": s["tipo"], "referente": s["referente"], "estilo": s["estilo"], "mercado": s["mercado"], "fecha": fecha, "url": url, "enlace": enlace,
            "titulo": (titulo or "")[:140], "capturada": ahora_iso(), **{k: v for k, v in extra.items() if v is not None}}


def cosechar_x(s, existentes):
    nuevas, al_dia, info = m.cosechar_cuenta_x(s["valor"], None, None, existentes, None)
    out = {}
    for cid, c in nuevas.items():
        out[cid] = registro(cid, s, c.get("fecha"), c.get("imagen_url"), c.get("permalink"), c.get("titulo"), likes=c.get("likes"), reposts=c.get("reposts"),
                            seguidores_autor=c.get("seguidores_autor"), idioma=c.get("idioma"))
    for cid, meta in al_dia.items():   # fotos ya conocidas: se actualiza su popularidad
        if cid in existentes:
            existentes[cid].update({k: v for k, v in meta.items() if k in ("likes", "reposts", "seguidores_autor") and v is not None})
    return out, info


def cosechar_reddit(s, existentes):
    r = m.cosechar_feed_reddit(f"https://www.reddit.com/r/{s['valor']}/top/.rss?t=month&limit=100", f"r/{s['valor']}", "month", True, None, None, existentes)
    if r is None:
        raise ValueError("Reddit no devolvió datos (límite de peticiones, privada o inexistente)")
    nuevas, con_imagen, reset = r
    time.sleep(max(reset, 15.0) + 3)
    return {cid: registro(cid, s, c.get("fecha"), c.get("imagen_url"), c.get("permalink"), c.get("titulo"), rank=c.get("rank")) for cid, c in nuevas.items()}, {"con_imagen": con_imagen}


def noticias_rss(consulta: str, mkt: str) -> list[dict]:
    url = "https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": consulta, "format": "rss", "mkt": mkt})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": m.UA, "Accept": "application/rss+xml,text/xml"}), timeout=25) as r:
        raiz = ET.fromstring(r.read(3_000_000))
    out = []
    for it in (e for e in raiz.iter() if e.tag.rsplit("}", 1)[-1] == "item"):
        h = {e.tag.rsplit("}", 1)[-1]: (e.text or "") for e in it}
        link = h.get("link", "")
        real = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url", [link])[0]
        try:
            fecha = parsedate_to_datetime(h.get("pubDate", ""))
        except Exception:  # noqa: BLE001
            fecha = None
        out.append({"titulo": html.unescape(h.get("title", "")), "desc": html.unescape(re.sub(r"<[^>]+>", " ", h.get("description", ""))), "url": real, "fecha": fecha})
    return out


def cosechar_noticias(s, existentes):
    """Noticias de los últimos VENTANA_DIAS que nombran a la persona (y traen alguna palabra de contexto): bajan las imágenes de cada artículo.
    La atribución es solo por texto: puede colarse otra persona con el mismo nombre."""
    ctx = CONTEXTO.get(s.get("contexto"), []) + [norm(c) for c in s.get("contexto_extra", [])]
    rx, excl = s["nombre"], [norm(x) for x in s.get("excluir", [])]
    vistos = {v.get("enlace") for v in existentes.values() if v.get("fuente") == "noticias"}
    items = {}
    for q in s.get("consultas") or [s["valor"]]:
        try:
            for it in noticias_rss(q, SEP_MKT.get(s["mercado"], "es-ES")):
                items.setdefault(it["url"], it)
        except Exception as e:  # noqa: BLE001
            print(f"   consulta fallida {q!r}: {type(e).__name__}", flush=True)
        time.sleep(2)
    limite = datetime.now(timezone.utc) - timedelta(days=VENTANA_DIAS)
    out, leidas = {}, 0
    for it in items.values():
        if not it["fecha"] or it["fecha"] < limite or it["url"] in vistos:
            continue
        t = norm(it["titulo"] + " " + it["desc"])
        if not (re.search(rx, t) and any(c in t for c in ctx) and not any(x in t for x in excl)):
            continue
        leidas += 1
        try:
            final, texto = m.pedir_html(it["url"])
            _, grupos = m.imagenes_de_pagina(final, texto)
        except Exception as e:  # noqa: BLE001
            print(f"   ✖ {urllib.parse.urlparse(it['url']).netloc}: {type(e).__name__}", flush=True)
            time.sleep(1)
            continue
        for g in grupos[:25]:
            cid = "pr_" + hashlib.sha1(g[-1].encode()).hexdigest()[:10]
            if cid in existentes or cid in out:
                continue
            for u in g:
                try:
                    if m.descargar_imagen(u, m.IMG / f"{cid}.jpg", min_lado=400, referer=final, proporcion=(0.4, 2.5)):
                        out[cid] = registro(cid, s, it["fecha"].isoformat(), u, final, it["titulo"])
                        break
                except Exception:  # noqa: BLE001
                    continue
        time.sleep(1.5)
    return out, {"articulos": leidas}


COSECHA = {"x": cosechar_x, "reddit": cosechar_reddit, "noticias": cosechar_noticias}


def filtrar_nuevas(fotos: dict, nuevas: dict) -> tuple[int, int, int]:
    """Puerta «persona con ropa» y repetidas (coseno CLIP). Lo descartado se apunta para no volver a bajarlo. Devuelve (buenas, no persona, repetidas)."""
    ids = list(nuevas)
    if not ids:
        return 0, 0, 0
    X = m.embeber_imagenes([m.IMG / f"{c}.jpg" for c in ids], "tendencia")
    g = m.puntuacion_foto_real(X)
    previas = [k for k, v in fotos.items() if not v.get("descartada") and (m.IMG / f"{k}.jpg").exists()]
    P = m.embeber_imagenes([m.IMG / f"{k}.jpg" for k in previas], "tendencia") if previas else np.zeros((0, X.shape[1]))
    buenas = sinp = dup = 0
    aceptadas = []
    for i, cid in enumerate(ids):
        v = nuevas[cid]
        v["gate"] = round(float(g[i]), 3)
        motivo = None
        if g[i] < m.UMBRAL_PUERTA:
            motivo = "no_persona"
        elif (len(P) and float((P @ X[i]).max()) >= UMBRAL_DUP) or any(float(X[i] @ X[j]) >= UMBRAL_DUP for j in aceptadas):
            motivo = "repetida"
        if motivo:
            v["descartada"] = motivo
            (m.IMG / f"{cid}.jpg").unlink(missing_ok=True)
            sinp += motivo == "no_persona"
            dup += motivo == "repetida"
        else:
            aceptadas.append(i)
            buenas += 1
        fotos[cid] = v
    return buenas, sinp, dup


def cmd_cosechar(args):
    TD.mkdir(parents=True, exist_ok=True)
    m.IMG.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(FUENTES.read_text(encoding="utf-8"))["fuentes"]
    fotos, estado = cargar(FOTOS), cargar(TD / "estado.json")
    for k, s in enumerate(cfg, 1):
        if args.solo and norm(args.solo) not in norm(s["referente"] + " " + s["valor"]):
            continue
        sid = hashlib.sha1(f"{s['tipo']}|{s['valor']}|{s['referente']}".encode()).hexdigest()[:8]
        print(f"[{k}/{len(cfg)}] {s['referente']} · {s['tipo']} {s['valor']} → {s['estilo']} {s['mercado']}", flush=True)
        try:
            nuevas, info = COSECHA[s["tipo"]](s, fotos)
            b, sp, du = filtrar_nuevas(fotos, nuevas)
            estado[sid] = {"referente": s["referente"], "tipo": s["tipo"], "ultima": ahora_iso(), "nuevas": len(nuevas), "buenas": b, **info}
            print(f"   {len(nuevas)} fotos bajadas → {b} nuevas con persona y ropa ({sp} sin persona, {du} repetidas)", flush=True)
        except Exception as e:  # noqa: BLE001
            estado[sid] = {"referente": s["referente"], "tipo": s["tipo"], "ultima": ahora_iso(), "error": f"{type(e).__name__}: {e}"[:160]}
            print(f"   ✖ {estado[sid]['error']}", flush=True)
        guardar(FOTOS, fotos)
        guardar(TD / "estado.json", estado)
        time.sleep(1.5)
    n = sum(1 for v in fotos.values() if not v.get("descartada"))
    print(f"\nFotos útiles acumuladas: {n} ({len(fotos)} vistas en total)")


def cmd_biblioteca(args):
    """Incorpora como muestra de referencia las fotos que Víctor aprobó en la app como urbano / geek (ya sin repetidas)."""
    TD.mkdir(parents=True, exist_ok=True)
    m.IMG.mkdir(parents=True, exist_ok=True)
    rutas, y, origen = _datos_app(m.AQUI)
    fotos = cargar(FOTOS)
    n = 0
    for r, est, org in zip(rutas, y, origen):
        if est not in ("urbano", "alternativo_geek"):
            continue
        cid = "bib_" + hashlib.sha1(str(r).encode()).hexdigest()[:10]
        if cid in fotos:
            continue
        shutil.copy(r, m.IMG / f"{cid}.jpg")
        fotos[cid] = {"id": cid, "fuente": "biblioteca", "referente": None, "estilo": "geek" if est == "alternativo_geek" else "urbano", "mercado": "Biblioteca", "fecha": None,
                      "url": None, "enlace": None, "titulo": f"origen: {org}", "capturada": ahora_iso(), "gate": 1.0}
        n += 1
    guardar(FOTOS, fotos)
    print(f"Muestra de referencia: {n} fotos nuevas de la Biblioteca ({sum(1 for v in fotos.values() if v['fuente'] == 'biblioteca')} en total)")


def _datos_app(ruta_app: Path):
    """Fotos aprobadas en la app (sus datos, no los de `tendencia_datos`): se leen con mercado.py apuntando a la carpeta de la app."""
    codigo = ("import sys, json; sys.path.insert(0, %r); import mercado as m; r, y, o = m.datos_entrenamiento(); "
              "print(json.dumps([[str(a), str(b), str(c)] for a, b, c in zip(r, y.tolist(), o)]))" % str(ruta_app))
    env = {k: v for k, v in os.environ.items() if k != "MERCADO_DATOS"}
    sal = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=ruta_app, env=env)
    lineas = [l for l in sal.stdout.splitlines() if l.startswith("[[")]
    if not lineas:
        raise SystemExit("No pude leer las fotos de la app: " + sal.stderr[-300:])
    datos = json.loads(lineas[-1])
    return [Path(a) for a, _, _ in datos], [b for _, b, _ in datos], [c for _, _, c in datos]


# ---------------------------------------------------------------- análisis de prendas
def cargar_tipos():
    sys.path.insert(0, str(DET))
    import prueba_recortes_clip as pc
    model, prep, tok = m.clip()
    t = model.encode_text(tok(["a photo of " + p for _, p in pc.TIPOS]))
    return pc, model, prep, (t / t.norm(dim=-1, keepdim=True)).numpy()


def visible(caja, cat, W, H) -> bool:
    """Heurística de «se ve más de la mitad»: la caja no está pegada al borde inferior con muy poca altura (prenda cortada por el borde)."""
    x1, y1, x2, y2 = caja
    alto = (y2 - y1) / H
    if y2 >= H - 3 and (alto < 0.2 or cat == "calzado"):
        return False
    if (x1 <= 2 and x2 >= W - 3) and alto < 0.25:
        return False
    return True


def cmd_analizar(args):
    import torch
    torch.set_grad_enabled(False)
    fotos, prendas = cargar(FOTOS), cargar(PRENDAS)
    pend = [k for k, v in sorted(fotos.items()) if not v.get("descartada") and k not in prendas and (m.IMG / f"{k}.jpg").exists()]
    limite = datetime.now(timezone.utc) - timedelta(days=args.max_dias)   # las fotos más viejas se quedan sin analizar (cuestan ~20 s cada una)
    antes = len(pend)
    pend = [k for k in pend if not fotos[k].get("fecha") or datetime.fromisoformat(fotos[k]["fecha"].replace("Z", "+00:00")) >= limite]
    if antes != len(pend):
        print(f"{antes - len(pend)} fotos de hace más de {args.max_dias} días se dejan sin analizar", flush=True)
    if args.max:
        pend = pend[:args.max]
    print(f"{len(pend)} fotos por analizar")
    if not pend:
        return
    pc, model, prep, T = cargar_tipos()
    for i in range(0, len(pend), 20):
        lote = pend[i:i + 20]
        carpeta = TD / "lote"
        shutil.rmtree(carpeta, ignore_errors=True)
        carpeta.mkdir(parents=True)
        for k in lote:
            shutil.copy(m.IMG / f"{k}.jpg", carpeta / f"{k}.jpg")
        salida = TD / "lote.json"
        t0 = time.time()
        subprocess.run([sys.executable, "-u", "analizar_outfit.py", "--carpeta", str(carpeta), "--salida-json", str(salida), "--cache", str(TD / "cache" / "od_cache.json")],
                       cwd=DET, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        res = json.loads(salida.read_text(encoding="utf-8"))
        for k in lote:
            r = res.get(k)
            if r is None:
                continue
            im = Image.open(m.IMG / f"{k}.jpg").convert("RGB")
            W, H = im.size
            out = []
            for pr in (r["personas"][0]["prendas"] if r["personas"] else []):
                x1, y1, x2, y2 = pr["caja"]
                if pr["categoria"] not in pc.GRUPOS or pr["deteccion"] == "torso" or min(x2 - x1, y2 - y1) < 40:
                    continue
                c = im.crop((max(0, int(x1 - .06 * (x2 - x1))), max(0, int(y1 - .06 * (y2 - y1))), min(W, int(x2 + .06 * (x2 - x1))), min(H, int(y2 + .06 * (y2 - y1)))))
                lado = max(c.size)
                lienzo = Image.new("RGB", (lado, lado), (128, 128, 128))
                lienzo.paste(c, ((lado - c.width) // 2, (lado - c.height) // 2))
                v = model.encode_image(prep(lienzo).unsqueeze(0))
                v = (v / v.norm(dim=-1, keepdim=True)).numpy()[0]
                cand = [pc.TIPOS.index(t) for t in pc.GRUPOS[pr["categoria"]]]
                s = 100.0 * T[cand] @ v
                s -= s.max()
                p = np.exp(s)
                p /= p.sum()
                j = int(p.argmax())
                out.append({"tipo": pc.TIPOS[cand[j]][0], "p_tipo": round(float(p[j]), 3), "cat": pr["categoria"], "deteccion": pr["deteccion"],
                            "color": (pr.get("atributos") or {}).get("color_primario"), "visible": visible(pr["caja"], pr["categoria"], W, H), "caja": [round(v_, 1) for v_ in pr["caja"]]})
            prendas[k] = {"n_personas": r["n_personas"], "prendas": out}
        guardar(PRENDAS, prendas)
        print(f"  lote {i // 20 + 1}/{math.ceil(len(pend) / 20)}: {len(lote)} fotos en {time.time() - t0:.0f} s", flush=True)
    shutil.rmtree(TD / "lote", ignore_errors=True)


# ---------------------------------------------------------------- informe
def peso(v: dict, ahora_dt) -> float:
    if not v.get("fecha"):
        return 1.0   # muestra de referencia sin fecha: todas pesan igual
    c = {"fecha": v["fecha"], "likes": v.get("likes"), "reposts": v.get("reposts"), "seguidores_autor": v.get("seguidores_autor"), "rank": v.get("rank")}
    return m.peso_foto(c, ahora_dt, VIDA_MEDIA)


def cmd_informe(args):
    fotos, prendas = cargar(FOTOS), cargar(PRENDAS)
    ahora_dt = datetime.now(timezone.utc)
    grupos = collections.defaultdict(list)
    for k, v in fotos.items():
        if v.get("descartada") or k not in prendas:
            continue
        grupos[(v["estilo"], v["mercado"], temporada(v.get("fecha")) if v.get("fecha") else "muestra")].append(k)
    informe = {"generado": ahora_iso(), "min_fotos": MIN_FOTOS, "vida_media_dias": VIDA_MEDIA, "grupos": []}
    for (estilo, mercado, temp), ids in sorted(grupos.items()):
        con_prendas = [k for k in ids if any(p["visible"] for p in prendas[k]["prendas"])]
        pesos = {k: peso(fotos[k], ahora_dt) for k in con_prendas}
        total = sum(pesos.values()) or 1.0
        por_tipo = collections.defaultdict(lambda: {"n": 0, "w": 0.0})
        for k in con_prendas:
            for t in {p["tipo"] for p in prendas[k]["prendas"] if p["visible"]}:   # una foto cuenta una vez por tipo
                por_tipo[t]["n"] += 1
                por_tipo[t]["w"] += pesos[k]
        colores = collections.Counter(p["color"] for k in con_prendas for p in prendas[k]["prendas"] if p["visible"] and p.get("color"))
        filas = [{"tipo": t, "fotos": d["n"], "cuota": round(d["w"] / total, 3) if d["n"] >= MIN_FOTOS else None, "pocos_datos": d["n"] < MIN_FOTOS}
                 for t, d in sorted(por_tipo.items(), key=lambda kv: -kv[1]["w"])]
        fuentes = collections.Counter((fotos[k].get("referente") or "Biblioteca") for k in ids)
        informe["grupos"].append({"estilo": estilo, "mercado": mercado, "temporada": temp, "fotos": len(ids), "fotos_con_prenda": len(con_prendas), "prendas": filas,
                                  "colores": dict(colores.most_common(8)), "fuentes": dict(fuentes.most_common())})
    guardar(INFORME, informe)
    for g in informe["grupos"]:
        print(f"\n{g['estilo']} · {g['mercado']} · {g['temporada']}: {g['fotos']} fotos ({g['fotos_con_prenda']} con prenda visible)  fuentes: {g['fuentes']}")
        for f in g["prendas"][:12]:
            print(f"   {f['tipo']:<28} {f['fotos']:>3} fotos  " + (f"{f['cuota']:.0%}" if f["cuota"] is not None else "pocos datos"))
    print(f"\nGuardado en {INFORME}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("cosechar")
    p.add_argument("--solo")
    sub.add_parser("biblioteca")
    p = sub.add_parser("analizar")
    p.add_argument("--max", type=int)
    p.add_argument("--max-dias", type=int, default=400)
    sub.add_parser("informe")
    p = sub.add_parser("todo")
    p.add_argument("--solo")
    p.add_argument("--max", type=int)
    p.add_argument("--max-dias", type=int, default=400)
    a = ap.parse_args()
    if a.cmd in ("cosechar", "todo"):
        cmd_cosechar(a)
    if a.cmd == "biblioteca" or (a.cmd == "todo" and not getattr(a, "solo", None)):
        cmd_biblioteca(a)
    if a.cmd in ("analizar", "todo"):
        cmd_analizar(a)
    if a.cmd in ("informe", "todo"):
        cmd_informe(a)


if __name__ == "__main__":
    main()
