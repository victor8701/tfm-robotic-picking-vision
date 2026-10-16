#!/usr/bin/env python3
"""
Revisión de valoraciones (9 de octubre de 2026, a petición de Víctor): en vez de etiquetar desde cero, ve lo que ha valorado el modelo grande de cada recorte (tipo, estampado, tejido y forma)
y contesta por cada fila OK, «más o menos» (marcando qué más podría ser) o No (marcando qué es). Así se recoge lo que no es blanco o negro.

  crear      elige los recortes (parte A: los del lote ciego en los que no coincidíamos; parte B: recortes nuevos con valoración del modelo) y unos pocos de CONTROL con la valoración de OTRO recorte
             (para medir si el OK se da con demasiada facilidad: sin eso, aceptar lo que se ve inflaría el acierto). Los controles no se marcan en la página.
  html       genera la página «Revisar valoraciones» (Artifact) con los recortes incrustados.
  importar   pasa las respuestas de la base de la página (exportadas con ArtifactData) a `tendencia_datos/valoraciones.json`.
  medir      OK, «más o menos» y No por atributo (estricto = solo OK; aceptable = OK + más o menos), la parte A por separado, los controles y las alternativas que marca.

Uso:  python3 revisar_valoraciones.py crear [--estilos a,b] [--nuevos 30] [--controles 6] [--prefijo r1-] | html --salida X.html [--prefijo r2-] [--titulo T] | importar --dir DIR | medir [--prefijo r2-]
  Cada ronda tiene su prefijo (r1-, r2-…) y `crear` NO borra las rondas anteriores del fichero de estado; `html` toma por defecto la ronda más reciente.
  Con `--estilos` solo entran recortes de esos estilos, repartidos por turnos, y sin parte A (el lote ciego es de geek y urbano). Necesita las fotos en `cache/img`: las de la Biblioteca solo están en el portátil de Víctor.
"""
import argparse
import base64
import html as html_lib
import io
import itertools
import json
import math
import random
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import hojas_prendas as hp  # noqa: E402

TD = hp.TD
CAMPOS = ("tipo", "estampado", "tejido", "forma")
EQ = {"Hoodie": "Sudadera"}
ESTADO = TD / "revision_estado.json"
RESP = TD / "valoraciones.json"
RESUMEN = TD / "valoraciones_resumen.json"


def familia(t):
    import tendencia_prenda as tp   # importa mercado.py: solo para leer FAMILIA
    return tp.FAMILIA.get(t, "Otros")


def wilson(k, n, z=1.96):
    if not n:
        return [0, 0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h)), round(100 * (c + h))]


def igual(campo, a, b):
    return (EQ.get(a, a) == EQ.get(b, b)) if campo == "tipo" else a == b


def cmd_crear(a):
    prendas = json.loads((TD / "prendas.json").read_text(encoding="utf-8"))
    etiq = json.loads(hp.ETIQ.read_text(encoding="utf-8"))
    ciego = json.loads((TD / "lote_ciego.json").read_text(encoding="utf-8")) if (TD / "lote_ciego.json").exists() else []
    previas = json.loads(RESP.read_text(encoding="utf-8")) if RESP.exists() else {}
    fotos = json.loads((TD / "fotos.json").read_text(encoding="utf-8"))
    estilos = {e.strip() for e in a.estilos.split(",") if e.strip()} if a.estilos else None   # claves del flujo: geek, urbano, clasico, old_money, lujo, bohemio, convencional
    if estilos and not estilos <= {f.get("estilo") for f in fotos.values()}:
        sys.exit(f"estilos desconocidos: {sorted(estilos - {f.get('estilo') for f in fotos.values()})}")

    def pr(k):
        f, _, i = k.partition("#")
        return prendas[f]["prendas"][int(i)]

    def de_estilo(f):
        return not estilos or (fotos.get(f) or {}).get("estilo") in estilos
    elegidos = []   # (clave, parte)
    # parte A: los recortes del lote ciego donde el modelo y Víctor no coincidían en alguna fila
    if a.desacuerdos:
        for k in ciego:
            e = etiq.get(k)
            if not e or not e.get("prendas") or k in previas or not de_estilo(k.split("#")[0]):
                continue
            p0, v = e["prendas"][0], pr(k).get("vlm")
            if v and any(p0.get(c) and p0.get(c) != "no aplica" and not igual(c, v.get(c), p0.get(c)) for c in CAMPOS):
                elegidos.append((k, "A"))
    # parte B: recortes nuevos (con valoración del modelo, válidos, sin etiqueta ni revisión previa), uno por foto
    usadas = {k.split("#")[0] for k, _ in elegidos}
    nuevos = []
    for f, r in prendas.items():
        ficha = fotos.get(f)
        if not ficha or ficha.get("descartada") or not de_estilo(f) or not (hp.CACHE / "img" / f"{f}.jpg").exists():
            continue
        for i, p in enumerate(r["prendas"]):
            x1, y1, x2, y2 = p["caja"]
            k = f"{f}#{i}"
            if "vlm" not in p or not p["visible"] or p.get("deteccion", "").startswith("torso") or min(x2 - x1, y2 - y1) < 110 or not 0.4 <= (x2 - x1) / (y2 - y1) <= 2.5 or k in etiq or k in previas:
                continue
            nuevos.append(k)
    rnd = random.Random(a.semilla)
    rnd.shuffle(nuevos)
    if estilos:   # con varios estilos, por turnos (uno de cada, otra vez uno de cada…) para que ninguno domine la muestra; un recorte por foto
        por_estilo, en_lista = {e: [] for e in sorted(estilos)}, set()
        for k in nuevos:
            f = k.split("#")[0]
            if f not in en_lista and f not in usadas:
                en_lista.add(f)
                por_estilo[fotos[f]["estilo"]].append(k)
        orden = sorted(estilos)
        rnd.shuffle(orden)   # el estilo que recibe el recorte sobrante sale del azar, no del abecedario
        nuevos = [k for tanda in itertools.zip_longest(*(por_estilo[e] for e in orden)) for k in tanda if k]
    vistas = set(usadas)
    for k in nuevos:
        if len([1 for _, parte in elegidos if parte == "B"]) >= a.nuevos:
            break
        if k.split("#")[0] not in vistas:
            vistas.add(k.split("#")[0])
            elegidos.append((k, "B"))
    # controles: de la parte B, con la valoración de otro recorte de OTRA familia
    bs = [k for k, parte in elegidos if parte == "B"]
    controles = set(rnd.sample(bs, min(a.controles, len(bs))))
    estado = {}
    rnd.shuffle(elegidos)
    for n, (k, parte) in enumerate(elegidos, 1):
        p = pr(k)
        real = {c: p["vlm"].get(c) for c in CAMPOS}
        mostrar = dict(real)
        if k in controles:
            donantes = [d for d, _ in elegidos if d != k and familia(pr(d)["vlm"]["tipo"]) != familia(real["tipo"])]
            d = rnd.choice(donantes)
            mostrar = {c: pr(d)["vlm"].get(c) for c in CAMPOS}
        foto, _, i = k.partition("#")
        estado[f"{a.prefijo}{n}"] = {"foto": foto, "idx": int(i), "caja": p["caja"], "parte": parte, "control": k in controles, "mostrar": mostrar, "real": real,
                                     "previo": ({c: etiq[k]["prendas"][0].get(c) for c in CAMPOS} if parte == "A" else None), "estilo": fotos[foto]["estilo"], "mercado": fotos[foto]["mercado"]}
    # las rondas anteriores se conservan (`importar` necesita sus ids); solo se rehace la de este prefijo
    anterior = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}
    ESTADO.write_text(json.dumps({**{k: v for k, v in anterior.items() if not k.startswith(a.prefijo)}, **estado}, ensure_ascii=False, indent=1), encoding="utf-8")
    import collections
    print(f"{len(estado)} recortes ({a.prefijo}): parte A (desacuerdos del lote ciego) {sum(e['parte'] == 'A' for e in estado.values())}, parte B (nuevos) {sum(e['parte'] == 'B' for e in estado.values())}, "
          f"controles {sum(e['control'] for e in estado.values())} → {ESTADO}\nestilos: {dict(collections.Counter(e['estilo'] for e in estado.values()))}")


def ultima_ronda(estado):
    """Prefijo de la ronda más reciente (la de número mayor: r1-, r2-…); vacío si los ids no siguen ese formato."""
    n = [int(m.group(1)) for m in (re.match(r"r(\d+)-", k) for k in estado) if m]
    return f"r{max(n)}-" if n else ""


def cmd_html(a):
    estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    prefijo = a.prefijo if a.prefijo is not None else ultima_ronda(estado)
    estado = {k: v for k, v in estado.items() if k.startswith(prefijo)}
    if not estado:
        sys.exit(f"no hay recortes con el prefijo «{prefijo}» en {ESTADO}")
    crops = []
    for pid in sorted(estado, key=lambda k: (len(k), k)):
        e = estado[pid]
        im = hp.recorte({"foto": e["foto"], "caja": e["caja"]})
        im.thumbnail((480, 480))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=72)
        crops.append({"id": pid, "src": "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode(), "mostrar": e["mostrar"]})
    pagina = Path(a.plantilla).read_text(encoding="utf-8").replace("__CROPS__", json.dumps(crops, ensure_ascii=False))
    if a.titulo:   # otra ronda = otro Artifact: con nombre distinto para no confundirlo con el anterior
        t = html_lib.escape(a.titulo)
        pagina = pagina.replace("<title>Revisar valoraciones</title>", f"<title>{t}</title>").replace("<h1>Revisar valoraciones</h1>", f"<h1>{t}</h1>")
    Path(a.salida).write_text(pagina, encoding="utf-8")
    print(f"{len(crops)} recortes ({prefijo}) incrustados en {a.salida} ({Path(a.salida).stat().st_size // 1024} KB)")


def cmd_importar(a):
    estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    resp = json.loads(RESP.read_text(encoding="utf-8")) if RESP.exists() else {}
    n = 0
    for f in sorted(Path(a.dir).rglob("v*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d = d.get("data", d)
        e = estado.get(f.stem[1:])
        if not e or not (d.get("x") or d.get("r")):
            continue
        resp[f"{e['foto']}#{e['idx']}"] = {**e, "id": f.stem[1:], "x": bool(d.get("x")), "r": d.get("r") or {}, "alt": d.get("alt") or {}, "t": d.get("t")}
        n += 1
    RESP.write_text(json.dumps(resp, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Importadas {n} revisiones ({len(resp)} en total)")


def ronda_de(v):
    m = re.match(r"(r\d+-)", v.get("id", ""))
    return m.group(1) if m else "?"


def acepta(grupo, c):
    """OK / «más o menos» / No de un grupo de revisiones en un atributo (estricto = solo OK; aceptable = OK + más o menos), con intervalo de Wilson. None si nadie contestó."""
    r = [v["r"].get(c) for v in grupo if v["r"].get(c)]
    n, ok, mm = len(r), r.count("ok"), r.count("mm")
    if not n:
        return None
    return {"n": n, "ok": ok, "mas_o_menos": mm, "no": r.count("no"), "estricto": [ok, n, wilson(ok, n)], "aceptable": [ok + mm, n, wilson(ok + mm, n)]}


def tabla(titulo, grupos):
    """Una fila por grupo (ronda, estilo…) con lo aceptable por atributo; se imprime y se devuelve para el resumen."""
    print(f"\n== {titulo} (aceptable = OK + más o menos; n pequeña por grupo: orientativo)")
    out = {}
    for nombre, g in grupos:
        fila = {c: acepta(g, c) for c in CAMPOS}
        out[nombre] = {"recortes": len(g), **{c: f for c, f in fila.items() if f}}
        print(f"   {nombre:<13} {len(g):>3} recortes | " + " | ".join(f"{c} {f['aceptable'][0]}/{f['n']}" for c, f in fila.items() if f))
    return out


def cmd_medir(a):
    resp = json.loads(RESP.read_text(encoding="utf-8"))
    if a.prefijo:
        resp = {k: v for k, v in resp.items() if v.get("id", "").startswith(a.prefijo)}
    sal = {"recortes": len(resp), "inservibles": sum(v["x"] for v in resp.values())}
    utiles = {k: v for k, v in resp.items() if not v["x"]}
    sin_control = sum(v["x"] and not v["control"] for v in resp.values())
    print(f"{len(resp)} revisados; {sal['inservibles']} marcados «no sirve» ({sin_control} fuera de los controles); {len(utiles)} con respuestas")
    for etiqueta, filtro in (("recortes reales (partes A y B)", lambda v: not v["control"]), ("parte A: donde no coincidíamos con tu etiqueta", lambda v: not v["control"] and v["parte"] == "A"),
                             ("parte B: recortes nuevos", lambda v: not v["control"] and v["parte"] == "B")):
        grupo = {k: v for k, v in utiles.items() if filtro(v)}
        sal[etiqueta] = {}
        print(f"\n== {etiqueta}: {len(grupo)} recortes")
        for c in CAMPOS:
            f = acepta(grupo.values(), c)
            if not f:
                continue
            sal[etiqueta][c] = f
            n, ok, mm = f["n"], f["ok"], f["mas_o_menos"]
            print(f"   {c:<10} OK {ok:>2} · más o menos {mm:>2} · No {f['no']:>2}  (n = {n})  | estricto {100 * ok / n:.0f} % {f['estricto'][2]} | aceptable {100 * (ok + mm) / n:.0f} % {f['aceptable'][2]}")
    # controles: valoración de OTRO recorte; el modelo no debería salir bien parado. Un «no sirve» en un control cuenta como rechazo (así lo usó Víctor en la ronda 2: la valoración no era de lo que veía)
    todos_ctl = [v for v in resp.values() if v["control"]]
    if todos_ctl:
        con_resp = [v for v in todos_ctl if not v["x"]]
        sal["controles_resumen"] = {"n": len(todos_ctl), "no_sirve": sum(v["x"] for v in todos_ctl), "tipo_no": sum(v["r"].get("tipo") == "no" for v in con_resp),
                                    "tipo_aceptado_estando_mal": sum(v["r"].get("tipo") in ("ok", "mm") and not igual("tipo", v["mostrar"]["tipo"], v["real"]["tipo"]) for v in con_resp)}
        c = sal["controles_resumen"]
        print(f"\n== controles (valoración de otro recorte, de otra familia de prenda): {c['n']}; «no sirve» {c['no_sirve']}; tipo rechazado con No {c['tipo_no']}; tipo dado por bueno estando mal {c['tipo_aceptado_estando_mal']}")
        sal["controles"] = {}
        for campo in CAMPOS:
            filas = [v["r"].get(campo) for v in con_resp if v["r"].get(campo) and not igual(campo, v["mostrar"][campo], v["real"][campo])]
            if filas:
                sal["controles"][campo] = {"n": len(filas), "no": filas.count("no"), "mas_o_menos": filas.count("mm"), "ok": filas.count("ok")}
                print(f"   {campo:<10} valoración distinta de la real en {len(filas)}: la rechazas (No) {filas.count('no')}, más o menos {filas.count('mm')}, la das por OK {filas.count('ok')}")
    # por ronda y por estilo (solo recortes reales con respuestas)
    reales = [v for v in utiles.values() if not v["control"]]
    sal["por_ronda"] = tabla("por ronda", [(r, [v for v in reales if ronda_de(v) == r]) for r in sorted({ronda_de(v) for v in reales})])
    sal["por_estilo"] = tabla("por estilo", [(e, [v for v in reales if v["estilo"] == e]) for e in sorted({v["estilo"] for v in reales})])
    # lo que marcas como alternativa
    alt = {}
    for v in utiles.values():
        if v["control"]:
            continue
        for c in CAMPOS:
            for x in v["alt"].get(c, []):
                alt.setdefault(c, {}).setdefault(x, 0)
                alt[c][x] += 1
    sal["alternativas_marcadas"] = alt
    # coherencia con tu etiqueta anterior (parte A): si dices «No» y marcas la misma que pusiste antes
    coh = [0, 0]
    for v in utiles.values():
        if v["parte"] == "A" and not v["control"] and v["previo"]:
            for c in CAMPOS:
                if v["r"].get(c) in ("no", "mm") and v["previo"].get(c) and v["alt"].get(c):
                    coh[1] += 1
                    coh[0] += any(igual(c, x, v["previo"][c]) for x in v["alt"][c])
    sal["coherencia_con_etiqueta_anterior"] = coh
    if coh[1]:
        print(f"\ncoherencia: en la parte A, cuando marcas alternativas, incluyen tu etiqueta anterior {coh[0]} de {coh[1]} veces")
    if not a.prefijo:   # con filtro de ronda no se pisa el resumen de todas
        RESUMEN.write_text(json.dumps(sal, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("crear")
    p.add_argument("--estilos", default=None, help="solo recortes de estos estilos (claves del flujo, separadas por comas); con varios, se reparten a partes iguales")
    p.add_argument("--nuevos", type=int, default=30)
    p.add_argument("--controles", type=int, default=6)
    p.add_argument("--desacuerdos", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--prefijo", default="r1-")
    p.add_argument("--semilla", type=int, default=13)
    p = sub.add_parser("html")
    p.add_argument("--plantilla", default=str(AQUI / "tendencias_prenda" / "revisar_valoraciones.html"))
    p.add_argument("--salida", required=True)
    p.add_argument("--prefijo", default=None, help="ronda a generar (por defecto, la más reciente)")
    p.add_argument("--titulo", default=None, help="título de la página (por defecto, «Revisar valoraciones»)")
    p = sub.add_parser("importar")
    p.add_argument("--dir", required=True)
    p = sub.add_parser("medir")
    p.add_argument("--prefijo", default=None, help="solo esta ronda (por ejemplo r2-); sin filtro se miden todas y se guarda el resumen")
    a = ap.parse_args()
    {"crear": cmd_crear, "html": cmd_html, "importar": cmd_importar, "medir": cmd_medir}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
