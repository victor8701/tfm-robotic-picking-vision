#!/usr/bin/env python3
"""
Revisión de valoraciones (9 de octubre de 2026, a petición de Víctor): en vez de etiquetar desde cero, ve lo que ha valorado el modelo grande de cada recorte (tipo, estampado, tejido y forma)
y contesta por cada fila OK, «más o menos» (marcando qué más podría ser) o No (marcando qué es). Así se recoge lo que no es blanco o negro.

  crear      elige los recortes (parte A: los del lote ciego en los que no coincidíamos; parte B: recortes nuevos con valoración del modelo) y unos pocos de CONTROL con la valoración de OTRO recorte
             (para medir si el OK se da con demasiada facilidad: sin eso, aceptar lo que se ve inflaría el acierto). Los controles no se marcan en la página.
             `--estilos old_money,clasico,lujo,bohemio,convencional` (14 de octubre): solo recortes de esos estilos, repartidos por igual, y sin parte A (el lote ciego es de geek y urbano).
             Necesita las fotos en `cache/img` (las de la Biblioteca solo están en el portátil de Víctor): hay que ejecutarlo allí; `crear` sobrescribe `revision_estado.json` (las respuestas de r1- ya están en `valoraciones.json`).
  html       genera la página «Revisar valoraciones» (Artifact) con los recortes incrustados.
  importar   pasa las respuestas de la base de la página (exportadas con ArtifactData) a `tendencia_datos/valoraciones.json`.
  medir      OK, «más o menos» y No por atributo (estricto = solo OK; aceptable = OK + más o menos), la parte A por separado, los controles y las alternativas que marca.

Uso:  python3 revisar_valoraciones.py crear [--nuevos 30] [--controles 6] [--prefijo r1-] [--estilos a,b,c] | html --salida X.html | importar --dir DIR | medir
"""
import argparse
import base64
import io
import json
import math
import random
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
    if a.estilos:
        a.desacuerdos = False   # la parte A es del lote ciego (solo geek y urbano)

    def pr(k):
        f, _, i = k.partition("#")
        return prendas[f]["prendas"][int(i)]
    elegidos = []   # (clave, parte)
    # parte A: los recortes del lote ciego donde el modelo y Víctor no coincidían en alguna fila
    if a.desacuerdos:
        for k in ciego:
            e = etiq.get(k)
            if not e or not e.get("prendas") or k in previas:
                continue
            p0, v = e["prendas"][0], pr(k).get("vlm")
            if v and any(p0.get(c) and p0.get(c) != "no aplica" and not igual(c, v.get(c), p0.get(c)) for c in CAMPOS):
                elegidos.append((k, "A"))
    # parte B: recortes nuevos (con valoración del modelo, válidos, sin etiqueta ni revisión previa), uno por foto
    usadas = {k.split("#")[0] for k, _ in elegidos}
    nuevos = []
    for f, r in prendas.items():
        ficha = fotos.get(f)
        if not ficha or ficha.get("descartada") or not (hp.CACHE / "img" / f"{f}.jpg").exists() or (a.estilos and ficha["estilo"] not in a.estilos):
            continue
        for i, p in enumerate(r["prendas"]):
            x1, y1, x2, y2 = p["caja"]
            k = f"{f}#{i}"
            if "vlm" not in p or not p["visible"] or p.get("deteccion", "").startswith("torso") or min(x2 - x1, y2 - y1) < 110 or not 0.4 <= (x2 - x1) / (y2 - y1) <= 2.5 or k in etiq or k in previas:
                continue
            nuevos.append(k)
    rnd = random.Random(a.semilla)
    rnd.shuffle(nuevos)
    if a.estilos:   # por turnos entre estilos, para que cada uno tenga los mismos recortes (±1)
        colas = {e: [k for k in nuevos if fotos[k.split("#")[0]]["estilo"] == e] for e in a.estilos}
        nuevos = []
        while any(colas.values()):
            for e in a.estilos:
                if colas[e]:
                    nuevos.append(colas[e].pop(0))
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
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    import collections
    print(f"{len(estado)} recortes: parte A (desacuerdos del lote ciego) {sum(e['parte'] == 'A' for e in estado.values())}, parte B (nuevos) {sum(e['parte'] == 'B' for e in estado.values())}, "
          f"controles {sum(e['control'] for e in estado.values())} → {ESTADO}\nestilos: {dict(collections.Counter(e['estilo'] for e in estado.values()))}")


def cmd_html(a):
    estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    crops = []
    for pid in sorted(estado, key=lambda k: (len(k), k)):
        e = estado[pid]
        im = hp.recorte({"foto": e["foto"], "caja": e["caja"]})
        im.thumbnail((480, 480))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=72)
        crops.append({"id": pid, "src": "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode(), "mostrar": e["mostrar"]})
    plantilla = Path(a.plantilla).read_text(encoding="utf-8")
    Path(a.salida).write_text(plantilla.replace("__CROPS__", json.dumps(crops, ensure_ascii=False)), encoding="utf-8")
    print(f"{len(crops)} recortes incrustados en {a.salida} ({Path(a.salida).stat().st_size // 1024} KB)")


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


def cmd_medir(a):
    resp = json.loads(RESP.read_text(encoding="utf-8"))
    sal = {"recortes": len(resp), "inservibles": sum(v["x"] for v in resp.values())}
    utiles = {k: v for k, v in resp.items() if not v["x"]}
    print(f"{len(resp)} revisados; {sal['inservibles']} marcados «no sirve»; {len(utiles)} con respuestas")
    for etiqueta, filtro in (("recortes reales (partes A y B)", lambda v: not v["control"]), ("parte A: donde no coincidíamos con tu etiqueta", lambda v: not v["control"] and v["parte"] == "A"),
                             ("parte B: recortes nuevos", lambda v: not v["control"] and v["parte"] == "B")):
        grupo = {k: v for k, v in utiles.items() if filtro(v)}
        sal[etiqueta] = {}
        print(f"\n== {etiqueta}: {len(grupo)} recortes")
        for c in CAMPOS:
            r = [v["r"].get(c) for v in grupo.values() if v["r"].get(c)]
            n, ok, mm, no = len(r), r.count("ok"), r.count("mm"), r.count("no")
            if not n:
                continue
            sal[etiqueta][c] = {"n": n, "ok": ok, "mas_o_menos": mm, "no": no, "estricto": [ok, n, wilson(ok, n)], "aceptable": [ok + mm, n, wilson(ok + mm, n)]}
            print(f"   {c:<10} OK {ok:>2} · más o menos {mm:>2} · No {no:>2}  (n = {n})  | estricto {100 * ok / n:.0f} % {wilson(ok, n)} | aceptable {100 * (ok + mm) / n:.0f} % {wilson(ok + mm, n)}")
    # controles: valoraciones de OTRO recorte; deberían salir «No» en el tipo
    ctl = [v for v in utiles.values() if v["control"]]
    if ctl:
        print(f"\n== controles (valoración de otro recorte, de otra familia de prenda): {len(ctl)}")
        sal["controles"] = {}
        for c in CAMPOS:
            filas = [v["r"].get(c) for v in ctl if v["r"].get(c) and not igual(c, v["mostrar"][c], v["real"][c])]
            if filas:
                sal["controles"][c] = {"n": len(filas), "no": filas.count("no"), "mas_o_menos": filas.count("mm"), "ok": filas.count("ok")}
                print(f"   {c:<10} valoración distinta de la real en {len(filas)}: la rechazas (No) {filas.count('no')}, más o menos {filas.count('mm')}, la das por OK {filas.count('ok')}")
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
    RESUMEN.write_text(json.dumps(sal, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("crear")
    p.add_argument("--nuevos", type=int, default=30)
    p.add_argument("--controles", type=int, default=6)
    p.add_argument("--desacuerdos", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--prefijo", default="r1-")
    p.add_argument("--estilos", type=lambda s: [x for x in s.split(",") if x], help="solo estos estilos (old_money,clasico,lujo,bohemio,convencional,urbano,geek), repartidos por igual; sin parte A")
    p.add_argument("--semilla", type=int, default=13)
    p = sub.add_parser("html")
    p.add_argument("--plantilla", default=str(AQUI / "tendencias_prenda" / "revisar_valoraciones.html"))
    p.add_argument("--salida", required=True)
    p = sub.add_parser("importar")
    p.add_argument("--dir", required=True)
    sub.add_parser("medir")
    a = ap.parse_args()
    {"crear": cmd_crear, "html": cmd_html, "importar": cmd_importar, "medir": cmd_medir}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
