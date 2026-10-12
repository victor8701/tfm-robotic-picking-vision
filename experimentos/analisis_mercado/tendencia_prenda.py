#!/usr/bin/env python3
"""
Tendencia por prenda (geek y urbano) — v0, 2026-10-06.

Qué mide: dentro de un estilo (geek, urbano) y un mercado (España, EEUU), qué prendas aparecen en las fotos de los *referentes* del estilo
(el estilo lo da la persona, no la foto) y cuánto pesan, por temporada (6 meses). Decisiones de Víctor: ver memoria/TFM_tendencias_de_prenda.md.

Flujo (todo en `tendencia_datos/`, aparte de los datos de la app «Analizar mercado»; las fotos no van a git):
  cosechar   fuentes de `tendencia_fuentes.json` (X vía FxTwitter, prensa por nombre vía Bing Noticias, comunidades de Reddit) -> fotos + `fotos.json`
  biblioteca incorpora como muestra de referencia las fotos que Víctor aprobó como urbano / geek en la app
  analizar   detector de prendas (analizar_outfit.py: DeepFashion2 + Florence) + tipo fino con CLIP sobre el recorte -> `prendas.json`
  vlm        un modelo abierto grande de lenguaje y visión (Qwen3-VL-8B, en una GPU de Kaggle) etiqueta cada prenda nueva: tipo entre los 29 de Víctor, estampado, tejido y forma.
             Los recortes de las fotos nuevas se suben a un dataset PRIVADO de Kaggle que se BORRA al terminar (decisión de Víctor, 2026-10-09) -> `prendas.json` (campo `vlm`)
  informe    cuota de fotos por prenda, por estilo × mercado × temporada (mínimo de fotos por cifra) -> `informe.json`
  todo       las cinco seguidas (es lo que corre cada semana; `--sin-vlm` salta el paso de Kaggle)

Límites conocidos (medidos el 2026-10-06): con las fuentes legibles salen pocas fotos por referente (decenas por temporada); el estampado y la forma NO se
estiman todavía (CLIP sin entrenar: 32 % y no mejora a «siempre oversized»); la visibilidad de la prenda es una heurística de caja pegada al borde.

Uso:  python3 tendencia_prenda.py todo [--sin-vlm] | cosechar [--solo NOMBRE] | biblioteca | analizar [--max N] | vlm [--max-vlm N] [--simular] | informe
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
import tarfile
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
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
VLMP = DET / "vlm_profesor"
LADO_VLM = 1024           # las fotos se reducen a este lado largo antes de subirlas a Kaggle
MAX_POR_KERNEL = 700      # prendas por kernel (~2,5 s cada una): con más se reparten en varios kernels en paralelo
MIN_FOTOS = 5            # decisión de Víctor: por debajo de 5 fotos no se enseña una cifra
VIDA_MEDIA = 10.0        # días, como el informe de estilos
VENTANA_DIAS = 180       # temporada
UMBRAL_DUP = 0.97        # coseno CLIP a partir del cual dos fotos son la misma
SEP_MKT = {"ES": "es-ES", "US": "en-US"}
CONTEXTO = {"musica": ["cantante", "rapero", "rapera", "artista", "cancion", "disco", "concierto", "musica", "trap", "gira", "festival", "album", "single", "videoclip"],
            "streamer": ["streamer", "twitch", "youtuber", "directo", "videojuego", "juego"],
            "music_en": ["rapper", "singer", "artist", "song", "album", "concert", "tour", "festival", "fashion", "style", "outfit", "met gala", "collection"]}
norm = lambda s: unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()
FAMILIA = {"Camiseta manga corta": "Arriba", "Camiseta de tirantes": "Arriba", "Camiseta manga larga": "Arriba", "Top": "Arriba", "Camisa": "Arriba", "Polo": "Arriba",
           "Sudadera": "Arriba", "Hoodie": "Arriba", "Jersey": "Arriba", "Chaleco sin mangas": "Arriba", "Chaqueta": "Abrigo", "Americana": "Abrigo", "Abrigo": "Abrigo", "Plumas": "Abrigo",
           "Pantalón": "Abajo", "Falda": "Abajo", "Short": "Abajo", "Legging/Malla": "Abajo", "Vestido": "Cuerpo entero", "Mono": "Cuerpo entero",
           "Zapatillas deportivas": "Calzado", "Zapatillas casual/lifestyle": "Calzado", "Zapatos planos de vestir": "Calzado", "Zapatos de vestir": "Calzado", "Zapatos de tacón": "Calzado",
           "Sandalias": "Calzado", "Botas": "Calzado", "Bolso": "Accesorio", "Riñonera": "Accesorio", "Gorra/Gorro/Sombrero": "Accesorio"}
# los siete estilos de la app (id en la app → clave en el flujo por prenda). Víctor decidió el 6 de octubre empezar por geek y urbano (con referentes y fuentes de mercado); el 11 de octubre pidió los demás:
# de esos cinco solo hay, por ahora, la muestra de referencia de su Biblioteca (fotos aprobadas, sin fecha ni mercado).
ESTILOS_FLUJO = {"urbano": "urbano", "alternativo_geek": "geek", "clasico_tradicional": "clasico", "old_money": "old_money", "lujo_ostentoso": "lujo", "bohemio": "bohemio", "convencional": "convencional"}
NOMBRE_ESTILO = {"urbano": "Urbano", "geek": "Geek", "clasico": "Clásico", "old_money": "Old money", "lujo": "Lujo ostentoso", "bohemio": "Bohemio", "convencional": "Convencional"}
NIVELES = ["baja", "media", "alta"]
ATRIBUTOS = ("estampado", "forma", "tejido")
ALUMNO = TD / "alumno.npz"           # capas sobre CLIP B/32 entrenadas con el profesor (vlm_profesor/entrenar_alumno.py --guardar); si no existe, se usa CLIP sin entrenar
PESO_FUERA_DE_CATEGORIA = 0.2        # el detector solo orienta: los tipos que no son de su categoría pesan esto (0 = restricción dura)
FIABILIDAD = TD / "fiabilidad.json"   # aciertos medidos de cada atributo (`fiabilidad_prenda.py`): ponen el techo de confianza de sus cifras


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
    ultimo = None
    for intento in range(3):   # desde los servidores de GitHub Bing contesta a ratos con algo que no es XML: se reintenta con pausa
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": m.UA, "Accept": "application/rss+xml,text/xml"}), timeout=25) as r:
                raiz = ET.fromstring(r.read(3_000_000))
            break
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(3 + 5 * intento)
    else:
        raise ultimo
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


FOTOS_KAGGLE = TD / "fotos_kaggle.txt"   # nombre de un dataset PRIVADO de Kaggle con fotos que solo están en el portátil de Víctor (su Biblioteca): la tarea de la nube las baja, las analiza y lo borra al terminar bien
EMB_IDS = TD / "embeddings.npz"   # embedding CLIP de cada foto aceptada, por identificador: sirve para detectar repetidas aunque la caché de imágenes esté vacía (la tarea en la nube empieza sin ella)


def cargar_emb() -> dict:
    if not EMB_IDS.exists():
        return {}
    try:
        z = np.load(EMB_IDS, allow_pickle=False)
        return dict(zip(z["ids"].tolist(), z["v"].astype(np.float32)))
    except Exception:  # noqa: BLE001 -- fichero a medio escribir: se recalcula
        return {}


def guardar_emb(d: dict) -> None:
    tmp = EMB_IDS.with_name(EMB_IDS.stem + ".tmp.npz")
    np.savez_compressed(tmp, ids=np.array(list(d.keys())), v=np.array(list(d.values()), dtype=np.float16))
    tmp.replace(EMB_IDS)


def asegurar_imagen(k: str, fotos: dict) -> bool:
    """La foto en la caché; si falta y se conoce su dirección, se vuelve a bajar (en la nube la caché empieza vacía cada semana). False si no se pudo."""
    ruta = m.IMG / f"{k}.jpg"
    if ruta.exists():
        return True
    url = (fotos.get(k) or {}).get("url")
    if not url:
        return False
    try:
        return bool(m.descargar_imagen(url, ruta))
    except Exception:  # noqa: BLE001 -- la foto pudo desaparecer: esa prenda se queda sin etiquetar esta semana
        return False


def filtrar_nuevas(fotos: dict, nuevas: dict) -> tuple[int, int, int]:
    """Puerta «persona con ropa» y repetidas (coseno CLIP). Lo descartado se apunta para no volver a bajarlo. Devuelve (buenas, no persona, repetidas)."""
    ids = list(nuevas)
    if not ids:
        return 0, 0, 0
    X = m.embeber_imagenes([m.IMG / f"{c}.jpg" for c in ids], "tendencia")
    g = m.puntuacion_foto_real(X)
    embs = cargar_emb()
    previas = [k for k, v in fotos.items() if not v.get("descartada") and k not in nuevas]
    falta = [k for k in previas if k not in embs and (m.IMG / f"{k}.jpg").exists()]   # sin embedding guardado: se calcula si la foto está
    if falta:
        for k, v in zip(falta, m.embeber_imagenes([m.IMG / f"{k}.jpg" for k in falta], "tendencia")):
            embs[k] = v
    P = np.array([embs[k] for k in previas if k in embs]) if any(k in embs for k in previas) else np.zeros((0, X.shape[1]))
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
            embs[cid] = X[i]
        fotos[cid] = v
    guardar_emb(embs)
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


def _kaggle_ops():
    sys.path.insert(0, str(VLMP))
    import kaggle_ops as ko
    return ko


def cmd_fotos_kaggle(args):
    """`fotos-kaggle subir`: sube a un dataset privado de Kaggle las fotos de la Biblioteca que aún no tienen todas sus prendas etiquetadas por el modelo grande y apunta su nombre en `fotos_kaggle.txt`
    (se sincroniza con la rama de datos; la tarea semanal de la nube las baja, las analiza y borra el dataset cuando todo ha ido bien). Así el portátil no hace el trabajo pesado."""
    fotos, prendas = cargar(FOTOS), cargar(PRENDAS)
    ids = []
    for k, v in sorted(fotos.items()):
        if v.get("fuente") != "biblioteca" or v.get("descartada") or not (m.IMG / f"{k}.jpg").exists():
            continue
        pr = prendas.get(k)
        if pr is None or any(valida(p) and "vlm" not in p for p in pr["prendas"]):
            ids.append(k)
    if args.max:
        ids = ids[:args.max]
    if not ids:
        raise SystemExit("No hay fotos de la Biblioteca pendientes.")
    slug = args.slug
    carpeta = Path(tempfile.mkdtemp(prefix="fotos_kaggle_"))
    with tarfile.open(carpeta / "fotos.bin", "w") as z:   # un tar con extensión .bin: Kaggle abre los .zip y los .tar y reparte su contenido en cientos de ficheros (y el dataset entero da 404 y uno a uno 429); un .bin lo deja como UN fichero
        for k in ids:
            z.add(m.IMG / f"{k}.jpg", f"{k}.jpg")
    (carpeta / "dataset-metadata.json").write_text(json.dumps({"title": f"TFM fotos pendientes {slug[-12:]}", "id": f"victor871/{slug}", "licenses": [{"name": "other"}],
                                                               "description": "Privado. Fotos de referencia del TFM (UC3M); la tarea semanal las usa y lo borra."}, ensure_ascii=False), encoding="utf-8")
    print(f"{len(ids)} fotos ({(carpeta / 'fotos.bin').stat().st_size / 1e6:.1f} MB) → dataset PRIVADO de Kaggle «{slug}»", flush=True)
    ko = _kaggle_ops()
    ko.dataset_crear(carpeta, quiet=True)
    ko.esperar_dataset(slug)
    FOTOS_KAGGLE.write_text(slug, encoding="utf-8")
    shutil.rmtree(carpeta, ignore_errors=True)
    print(f"Listo. Marca escrita en {FOTOS_KAGGLE}: la nube las bajará en su próxima ejecución.")


def traer_fotos_kaggle() -> str | None:
    """Si hay una marca `fotos_kaggle.txt`, baja ese dataset (un solo `fotos.bin`, que es un tar) y deja sus fotos en la caché (la nube no las tiene). Devuelve el nombre del dataset para borrarlo al final."""
    if not FOTOS_KAGGLE.exists() or not FOTOS_KAGGLE.read_text(encoding="utf-8").strip():
        return None
    slug = FOTOS_KAGGLE.read_text(encoding="utf-8").strip()
    tmp = Path(tempfile.mkdtemp(prefix="fotos_kaggle_"))
    try:
        tar = _kaggle_ops().dataset_bajar_fichero(slug, "fotos.bin", tmp)
        m.IMG.mkdir(parents=True, exist_ok=True)
        n = 0
        with tarfile.open(tar) as z:
            for mi in z.getmembers():
                nombre = Path(mi.name).name
                if mi.isfile() and nombre.endswith(".jpg") and not (m.IMG / nombre).exists():
                    with z.extractfile(mi) as fi, open(m.IMG / nombre, "wb") as fo:
                        shutil.copyfileobj(fi, fo)
                    n += 1
    except Exception as e:  # noqa: BLE001
        print(f"⚠ No pude bajar el dataset {slug} de Kaggle ({type(e).__name__}: {str(e)[:160]}); sigo sin esas fotos.", flush=True)
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Fotos de la Biblioteca bajadas de Kaggle ({slug}): {n}", flush=True)
    return slug


def borrar_fotos_kaggle(slug: str) -> None:
    try:
        _kaggle_ops().dataset_borrar(slug)
        FOTOS_KAGGLE.unlink(missing_ok=True)   # al subir los datos, la marca desaparece de la rama de datos
        print(f"Dataset {slug} borrado de Kaggle.", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"⚠ No pude borrar el dataset {slug} ({type(e).__name__}: {str(e)[:120]}): se reintenta la próxima vez.", flush=True)


def cmd_embeddings(args):
    """Calcula y guarda el embedding de cada foto aceptada que tenga imagen en la caché (para la detección de repetidas desde la nube)."""
    fotos, embs = cargar(FOTOS), cargar_emb()
    falta = [k for k, v in fotos.items() if not v.get("descartada") and k not in embs and (m.IMG / f"{k}.jpg").exists()]
    if falta:
        for k, v in zip(falta, m.embeber_imagenes([m.IMG / f"{k}.jpg" for k in falta], "tendencia")):
            embs[k] = v
        guardar_emb(embs)
    print(f"Embeddings guardados: {len(embs)} ({len(falta)} nuevos) → {EMB_IDS}")


def cmd_biblioteca(args):
    """Incorpora como muestra de referencia las fotos que Víctor aprobó en la app como urbano / geek (ya sin repetidas)."""
    TD.mkdir(parents=True, exist_ok=True)
    m.IMG.mkdir(parents=True, exist_ok=True)
    rutas, y, origen = _datos_app(m.AQUI)
    fotos = cargar(FOTOS)
    n = 0
    for r, est, org in zip(rutas, y, origen):
        if est not in ESTILOS_FLUJO:
            continue
        cid = "bib_" + hashlib.sha1(str(r).encode()).hexdigest()[:10]
        if cid in fotos:
            continue
        shutil.copy(r, m.IMG / f"{cid}.jpg")
        fotos[cid] = {"id": cid, "fuente": "biblioteca", "referente": None, "estilo": ESTILOS_FLUJO[est], "mercado": "Biblioteca", "fecha": None,
                      "url": None, "enlace": None, "titulo": f"origen: {org}", "capturada": ahora_iso(), "gate": 1.0}
        n += 1
    guardar(FOTOS, fotos)
    por_estilo = collections.Counter(v["estilo"] for v in fotos.values() if v["fuente"] == "biblioteca")
    print(f"Muestra de referencia: {n} fotos nuevas de la Biblioteca ({sum(por_estilo.values())} en total: " + ", ".join(f"{NOMBRE_ESTILO[k]} {v}" for k, v in por_estilo.most_common()) + ")")


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
def cargar_alumno():
    """Capas del alumno {campo: (clases, W, b)} si hay `alumno.npz` hecho con CLIP B/32 (el que usa este flujo); si no, None."""
    if not ALUMNO.exists():
        return None
    z = np.load(ALUMNO, allow_pickle=False)
    if str(z["_modelo"]) != "b32":
        return None
    return {c.split("__")[0]: (z[c], z[c.replace("__clases", "__W")], z[c.replace("__clases", "__b")]) for c in z.files if c.endswith("__clases")}


def tipo_del_alumno(alumno, v, categoria, pc):
    """Tipo de prenda con la capa del alumno: probabilidad por tipo × peso según la categoría del detector. Devuelve (tipo, probabilidad)."""
    clases, W, b = alumno["tipo29"]
    z = W @ v + b
    p = np.exp(z - z.max())
    p /= p.sum()
    permitidos = {t[0] for t in pc.GRUPOS[categoria]} | ({"Hoodie"} if categoria in ("ropa_superior", "abrigo") else set()) | ({"Zapatos de vestir"} if categoria == "calzado" else set())
    q = p * np.array([1.0 if c in permitidos else PESO_FUERA_DE_CATEGORIA for c in clases])
    q /= q.sum()
    j = int(q.argmax())
    return str(clases[j]), float(q[j])


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
    alumno = cargar_alumno()
    if alumno and "tipo29" in alumno:
        print("tipo de prenda: capa entrenada con el profesor (alumno.npz)", flush=True)
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
                if pr["categoria"] not in pc.GRUPOS or pr["deteccion"].startswith("torso") or min(x2 - x1, y2 - y1) < 40:
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
                tipo, p_tipo = pc.TIPOS[cand[j]][0], float(p[j])
                extra = {}
                if alumno and "tipo29" in alumno:   # el tipo de CLIP sin entrenar queda guardado aparte, para poder compararlos
                    extra["tipo_clip"] = tipo
                    tipo, p_tipo = tipo_del_alumno(alumno, v, pr["categoria"], pc)
                out.append({"tipo": tipo, "p_tipo": round(p_tipo, 3), "cat": pr["categoria"], "deteccion": pr["deteccion"], **extra,
                            "color": (pr.get("atributos") or {}).get("color_primario"), "visible": visible(pr["caja"], pr["categoria"], W, H), "caja": [round(v_, 1) for v_ in pr["caja"]]})
            prendas[k] = {"n_personas": r["n_personas"], "prendas": out}
        guardar(PRENDAS, prendas)
        print(f"  lote {i // 20 + 1}/{math.ceil(len(pend) / 20)}: {len(lote)} fotos en {time.time() - t0:.0f} s", flush=True)
    shutil.rmtree(TD / "lote", ignore_errors=True)


# ---------------------------------------------------------------- etiquetado con el modelo grande (Kaggle)
def paquete_vlm(pend, destino: Path, slug: str) -> list[dict]:
    """Carpeta para subir a Kaggle: `fotos.zip` (fotos reducidas), `manifiesto.json` (una entrada por prenda: foto y caja) y los metadatos del dataset PRIVADO."""
    tmp = destino / "_fotos"
    tmp.mkdir(parents=True, exist_ok=True)
    manifiesto, escala = [], {}
    for k, i, p in pend:
        nombre = f"w_{k}.jpg"
        if k not in escala:
            im = Image.open(m.IMG / f"{k}.jpg").convert("RGB")
            escala[k] = min(1.0, LADO_VLM / max(im.size))
            if escala[k] < 1:
                im = im.resize((round(im.width * escala[k]), round(im.height * escala[k])), Image.LANCZOS)
            im.save(tmp / nombre, quality=90)
        manifiesto.append({"id": f"w:{k}#{i}", "origen": "semanal", "foto": nombre, "caja": [round(c * escala[k], 1) for c in p["caja"]], "tipo": p["tipo"], "tipo_en": "a garment"})
    with zipfile.ZipFile(destino / "fotos.zip", "w", zipfile.ZIP_STORED) as z:
        for f in sorted(tmp.glob("*.jpg")):
            z.write(f, f.name)
    shutil.rmtree(tmp)
    (destino / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False), encoding="utf-8")
    (destino / "dataset-metadata.json").write_text(json.dumps({"title": f"TFM semanal prendas {slug[-13:]}", "id": f"victor871/{slug}", "licenses": [{"name": "other"}],
                                                               "description": "Privado. Fotos de prueba del TFM (UC3M); se borra al terminar."}, ensure_ascii=False), encoding="utf-8")
    return manifiesto


def texto_kernel(parte=None) -> str:
    """El código de `kernel_profesor.py` con las constantes de la tanda semanal: solo la configuración «semanal», solo Qwen3-VL-8B y, si hace falta, una parte (k, n)."""
    s = (VLMP / "kernel_profesor.py").read_text(encoding="utf-8")
    s, n1 = re.subn(r"(?m)^SOLO = None ", 'SOLO = ["semanal"] ', s, count=1)
    s, n2 = re.subn(r"(?m)^MODELOS_SOLO = None ", 'MODELOS_SOLO = ["qwen3vl8b"] ', s, count=1)
    if parte:
        s, n3 = re.subn(r"(?m)^PARTE = None ", f"PARTE = {tuple(parte)} ", s, count=1)
        assert n3 == 1
    assert n1 == n2 == 1, "no encuentro las constantes SOLO / MODELOS_SOLO en kernel_profesor.py"
    return s


def cmd_vlm(args):
    prendas = cargar(PRENDAS)
    fotos_d, hay = cargar(FOTOS), {}
    pend = [(k, i, p) for k, v in sorted(prendas.items()) for i, p in enumerate(v["prendas"])
            if valida(p) and "vlm" not in p and hay.setdefault(k, asegurar_imagen(k, fotos_d))]
    if args.max_vlm:
        pend = pend[:args.max_vlm]
    fotos_pend = len({k for k, _, _ in pend})
    print(f"{len(pend)} prendas visibles de {fotos_pend} fotos sin etiquetar con el modelo grande", flush=True)
    if not pend or args.simular:
        return
    sys.path.insert(0, str(VLMP))
    import kaggle_ops as ko   # lee el token de ~/.config/kaggle/api_token
    for ref, _, _ in ko.datasets():   # restos de una pasada anterior que falló: las fotos de personas no se quedan en Kaggle
        if ref.split("/")[-1].startswith("tfm-semanal-prendas-"):
            try:
                ko.dataset_borrar(ref.split("/")[-1])
                print(f"Borrado un dataset que quedó de una pasada anterior: {ref}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"⚠ No pude borrar {ref} ({type(e).__name__}): bórralo a mano en kaggle.com/datasets", flush=True)
    slug = "tfm-semanal-prendas-" + datetime.now().strftime("%Y%m%d-%H%M")
    n_partes = max(1, math.ceil(len(pend) / MAX_POR_KERNEL))
    resultados = []
    with tempfile.TemporaryDirectory(prefix="vlm_") as tmp:
        carpeta = Path(tmp) / "paquete"
        paquete_vlm(pend, carpeta, slug)
        mb = (carpeta / "fotos.zip").stat().st_size / 1e6
        print(f"Paquete de {mb:.0f} MB: se sube a un dataset PRIVADO de Kaggle ({slug}) y se borra al terminar. Kernels: {n_partes}.", flush=True)
        creado = False
        try:
            ko.dataset_crear(carpeta, quiet=True)
            creado = True
            ko.esperar_dataset(slug)
            slugs = [ko.kernel_push(texto_kernel((j, n_partes) if n_partes > 1 else None), f"TFM semanal VLM prendas {j + 1}", [slug]) for j in range(n_partes)]
            print(f"Lanzado en Kaggle: {', '.join(slugs)} (unos {math.ceil(len(pend) / n_partes * 2.5 / 60) + 4} minutos)", flush=True)
            for sl in slugs:
                est = ko.esperar_kernel(sl, avisar=lambda t: print("  " + t, flush=True))
                if est != "COMPLETE":
                    raise RuntimeError(f"el kernel {sl} terminó en {est}: {ko.kernel_log(sl)[-400:]}")
                salida = Path(tmp) / f"salida_{sl}"
                ko.kernel_bajar(salida, sl)
                f = salida / "pred_qwen3vl8b_semanal.jsonl"
                if not f.exists():
                    raise RuntimeError(f"el kernel {sl} no devolvió resultados: {ko.kernel_log(sl)[-400:]}")
                resultados += [json.loads(linea) for linea in open(f, encoding="utf-8")]
        finally:
            if creado:
                try:
                    ko.dataset_borrar(slug)
                    print("Dataset borrado de Kaggle.", flush=True)
                except Exception as e:  # noqa: BLE001
                    print(f"⚠ NO se pudo borrar el dataset {slug} de Kaggle ({type(e).__name__}: {e}): bórralo a mano en kaggle.com/datasets", flush=True)
    ahora = ahora_iso()
    n_ok = 0
    for r in resultados:
        k, _, i = r["id"][2:].partition("#")
        p = prendas[k]["prendas"][int(i)]
        if not r.get("tipo29"):
            continue   # sin respuesta válida: queda pendiente para la próxima pasada
        p.setdefault("tipo_clip", p["tipo"])   # el tipo de CLIP sin entrenar queda aparte, para compararlos
        p["tipo"] = r["tipo29"]
        p["vlm"] = {"tipo": r["tipo29"], "estampado": r.get("estampado"), "tejido": r.get("tejido"), "forma": r.get("forma"), "modelo": "qwen3vl8b", "config": "semanal", "fecha": ahora}
        n_ok += 1
    guardar(PRENDAS, prendas)
    print(f"Etiquetadas con el modelo grande: {n_ok} de {len(pend)} prendas.", flush=True)


# ---------------------------------------------------------------- informe
def peso(v: dict, ahora_dt) -> float:
    if not v.get("fecha"):
        return 1.0   # muestra de referencia sin fecha: todas pesan igual
    c = {"fecha": v["fecha"], "likes": v.get("likes"), "reposts": v.get("reposts"), "seguidores_autor": v.get("seguidores_autor"), "rank": v.get("rank")}
    return m.peso_foto(c, ahora_dt, VIDA_MEDIA)


def wilson(p: float, n: float, z: float = 1.96) -> list[float]:
    """Intervalo de Wilson al 95 % de una proporción p con n fotos efectivas."""
    if n <= 0:
        return [0.0, 1.0]
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def techo_de(medida: dict | None) -> str:
    """Techo de confianza de un atributo según lo bien que acierta medido con las etiquetas de Víctor (o a ojo): ≥ 85 % alta, ≥ 65 % media, menos baja."""
    if not medida or not medida.get("n"):
        return "baja"
    acc = medida["acierto"] / medida["n"]
    t = "alta" if acc >= 0.85 and medida["n"] >= 30 else "media" if acc >= 0.65 else "baja"
    return medida.get("techo") or t


def nivel(n_fotos: int, techo: str) -> str:
    """Confianza de una cifra: por cuántas fotos la sostienen (≥ 30 alta, ≥ 15 media, el resto baja), sin pasar del techo del atributo."""
    base = "alta" if n_fotos >= 30 else "media" if n_fotos >= 15 else "baja"
    return NIVELES[min(NIVELES.index(base), NIVELES.index(techo))]


def valida(p: dict) -> bool:
    """Una prenda entra en el informe si se ve y no sale del «torso geométrico» (red de seguridad del detector: en el lote ciego, 4 de 4 eran inservibles)."""
    return bool(p["visible"]) and not p.get("deteccion", "").startswith("torso")


def cmd_informe(args):
    fotos, prendas, fiab = cargar(FOTOS), cargar(PRENDAS), cargar(FIABILIDAD)
    t_tipo, t_fam, t_col = techo_de(fiab.get("tipo_fino")), techo_de(fiab.get("familia")), techo_de(fiab.get("color"))
    t_vlm = {c: techo_de(fiab.get(f"vlm_{c}")) for c in ("tipo", "familia", "estampado", "tejido", "forma")}
    dudosos = {t: d for t, d in ((fiab.get("vlm_tipo") or {}).get("por_tipo") or {}).items() if d["n"] >= 6 and d["aceptado"] / d["n"] < 0.65}   # tipos que el modelo dice y que Víctor no da por buenos (revisión)
    ahora_dt = datetime.now(timezone.utc)
    grupos = collections.defaultdict(list)
    for k, v in fotos.items():
        if v.get("descartada") or k not in prendas:
            continue
        grupos[(v["estilo"], v["mercado"], temporada(v.get("fecha")) if v.get("fecha") else "muestra")].append(k)
    informe = {"generado": ahora_iso(), "min_fotos": MIN_FOTOS, "vida_media_dias": VIDA_MEDIA, "fiabilidad": fiab, "techos": {"tipo": t_tipo, "familia": t_fam, "color": t_col, "vlm": t_vlm}, "grupos": []}
    for (estilo, mercado, temp), ids in sorted(grupos.items()):
        con_prendas = [k for k in ids if any(valida(p) for p in prendas[k]["prendas"])]
        pesos = {k: peso(fotos[k], ahora_dt) for k in con_prendas}
        total = sum(pesos.values()) or 1.0
        s1, s2 = sum(pesos.values()), sum(w * w for w in pesos.values())
        n_ef = (s1 * s1 / s2) if s2 else 0.0   # fotos «efectivas»: con pesos desiguales cuentan menos que las fotos reales
        por_tipo = collections.defaultdict(lambda: {"n": 0, "w": 0.0, "ej": [], "atr": {c: collections.Counter() for c in ATRIBUTOS}})
        por_fam = collections.defaultdict(lambda: {"n": 0, "w": 0.0, "ej": [], "atr": {c: collections.Counter() for c in ATRIBUTOS}})
        atr_grupo = {c: collections.Counter() for c in ATRIBUTOS}
        todas_vlm = all("vlm" in p for k in con_prendas for p in prendas[k]["prendas"] if valida(p))
        for k in con_prendas:
            vistos_t, vistos_f = set(), set()
            for i, p in enumerate(prendas[k]["prendas"]):
                if not valida(p):
                    continue
                for c in ATRIBUTOS:   # estampado, tejido y forma del modelo grande (cuentan prendas, no fotos)
                    v = (p.get("vlm") or {}).get(c)
                    if v:
                        atr_grupo[c][v] += 1
                        por_tipo[p["tipo"]]["atr"][c][v] += 1
                        por_fam[FAMILIA.get(p["tipo"], "Otros")]["atr"][c][v] += 1
                fam = FAMILIA.get(p["tipo"], "Otros")
                for clave, vistos, tabla in ((p["tipo"], vistos_t, por_tipo), (fam, vistos_f, por_fam)):   # una foto cuenta una vez por tipo y una vez por familia
                    if clave not in vistos:
                        vistos.add(clave)
                        tabla[clave]["n"] += 1
                        tabla[clave]["w"] += pesos[k]
                    tabla[clave]["ej"].append((pesos[k] * p["p_tipo"], k, i))

        def fila(clave, d, techo, extra=None):
            ok = d["n"] >= MIN_FOTOS
            cuota = d["w"] / total
            ej = [[k, i] for _, k, i in sorted(d["ej"], reverse=True)[:3]]
            # estampado, tejido y forma de las prendas de esta fila: solo si hay al menos MIN_FOTOS prendas etiquetadas con ese atributo
            atr = {c: {"n": sum(cnt.values()), "reparto": dict(cnt.most_common()), "confianza": nivel(sum(cnt.values()), t_vlm[c])}
                   for c, cnt in d["atr"].items() if sum(cnt.values()) >= MIN_FOTOS}
            return {**(extra or {}), "fotos": d["n"], "cuota": round(cuota, 3) if ok else None, "ic": wilson(min(cuota, 1.0), n_ef) if ok else None,
                    "confianza": nivel(d["n"], techo) if ok else None, "pocos_datos": not ok, "ejemplos": ej, "atributos": atr if ok else {}}
        def techo_tipo(t):
            return "baja" if todas_vlm and t in dudosos else (t_vlm["tipo"] if todas_vlm else t_tipo)

        def extra_tipo(t):
            e = {"tipo": t, "familia": FAMILIA.get(t, "Otros")}
            if todas_vlm and t in dudosos:
                e["aviso"] = f"En tu revisión diste por buena la etiqueta «{t}» del modelo {dudosos[t]['aceptado']} de {dudosos[t]['n']} veces: se confunde con otras prendas, así que esta cifra es más dudosa que las demás."
            return e
        filas = [fila(t, d, techo_tipo(t), extra_tipo(t)) for t, d in sorted(por_tipo.items(), key=lambda kv: -kv[1]["w"])]
        familias = [fila(f, d, t_vlm["familia"] if todas_vlm else t_fam, {"familia": f}) for f, d in sorted(por_fam.items(), key=lambda kv: -kv[1]["w"])]
        atributos = {c: {"n": sum(cnt.values()), "reparto": dict(cnt.most_common()), "confianza": nivel(sum(cnt.values()), t_vlm[c])} for c, cnt in atr_grupo.items() if sum(cnt.values()) >= MIN_FOTOS}
        colores = collections.Counter(p["color"] for k in con_prendas for p in prendas[k]["prendas"] if valida(p) and p.get("color"))
        fuentes = collections.Counter((fotos[k].get("referente") or "Biblioteca") for k in ids)
        informe["grupos"].append({"estilo": estilo, "mercado": mercado, "temporada": temp, "fotos": len(ids), "fotos_con_prenda": len(con_prendas), "fotos_efectivas": round(n_ef, 1),
                                  "prendas": filas, "familias": familias, "atributos": atributos, "etiquetadas_con_modelo_grande": todas_vlm,
                                  "colores": dict(colores.most_common(8)), "confianza_color": t_col, "fuentes": dict(fuentes.most_common())})
    guardar(INFORME, informe)
    try:   # comparación geek-urbano (`separacion_estilos.py`): son unos segundos y la enseña la pestaña «Prendas»
        import separacion_estilos
        separacion_estilos.generar(sys.modules[__name__], rep=2000)
    except Exception as e:  # noqa: BLE001 -- sin ella el informe sale igual
        print(f"⚠ No se pudo calcular la comparación entre estilos ({type(e).__name__}: {e}).", flush=True)
    for g in informe["grupos"]:
        print(f"\n{g['estilo']} · {g['mercado']} · {g['temporada']}: {g['fotos']} fotos ({g['fotos_con_prenda']} con prenda visible)  fuentes: {g['fuentes']}")
        for f in g["prendas"][:12]:
            print(f"   {f['tipo']:<28} {f['fotos']:>3} fotos  " + (f"{f['cuota']:.0%} (entre {f['ic'][0]:.0%} y {f['ic'][1]:.0%}) confianza {f['confianza']}" if f["cuota"] is not None else "pocos datos"))
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
    p = sub.add_parser("vlm")
    p.add_argument("--max-vlm", type=int, dest="max_vlm", help="como mucho N prendas (para probar)")
    p.add_argument("--simular", action="store_true", help="solo cuenta lo pendiente, sin subir nada")
    sub.add_parser("informe")
    sub.add_parser("embeddings")
    p = sub.add_parser("fotos-kaggle")
    p.add_argument("accion", choices=["subir"])
    p.add_argument("--slug", default="tfm-biblioteca-pendiente")
    p.add_argument("--max", type=int)
    p = sub.add_parser("todo")
    p.add_argument("--solo")
    p.add_argument("--sin-biblioteca", action="store_true", dest="sin_biblioteca", help="no importar las fotos aprobadas en la app (en la nube no están)")
    p.add_argument("--max", type=int)
    p.add_argument("--max-dias", type=int, default=400)
    p.add_argument("--sin-vlm", action="store_true", help="no usar el modelo grande de Kaggle (nada sale del ordenador)")
    p.add_argument("--max-vlm", type=int, dest="max_vlm")
    a = ap.parse_args()
    if a.cmd in ("cosechar", "todo"):
        cmd_cosechar(a)
    if a.cmd == "biblioteca" or (a.cmd == "todo" and not getattr(a, "solo", None) and not getattr(a, "sin_biblioteca", False)):
        cmd_biblioteca(a)
    if a.cmd == "embeddings":
        cmd_embeddings(a)
    if a.cmd == "fotos-kaggle":
        cmd_fotos_kaggle(a)
    slug_fotos = traer_fotos_kaggle() if a.cmd == "todo" else None   # fotos de la Biblioteca que solo estaban en el portátil
    if a.cmd in ("analizar", "todo"):
        cmd_analizar(a)
    vlm_ok = False
    if a.cmd == "vlm":
        a.simular = getattr(a, "simular", False)
        cmd_vlm(a)
    elif a.cmd == "todo" and not a.sin_vlm and not os.environ.get("TENDENCIA_SIN_VLM"):
        a.simular = False
        try:
            cmd_vlm(a)
            vlm_ok = True
        except Exception as e:  # noqa: BLE001 -- sin Kaggle el informe sale igual, con el tipo de CLIP; las prendas siguen pendientes para la próxima semana
            print(f"\n⚠ El modelo grande de Kaggle falló ({type(e).__name__}: {e}). Sigo sin él; se reintenta la próxima vez.", flush=True)
    if a.cmd in ("informe", "todo"):
        cmd_informe(a)
    if slug_fotos and vlm_ok:   # solo si el análisis y el modelo grande han ido bien: si no, el dataset se queda para reintentarlo
        borrar_fotos_kaggle(slug_fotos)


if __name__ == "__main__":
    main()
