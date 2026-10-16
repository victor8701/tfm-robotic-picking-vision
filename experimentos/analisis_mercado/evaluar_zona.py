#!/usr/bin/env python3
"""
Evalúa la prueba de la «zona del detector» (15 de octubre de 2026). Motivo: en la revisión de la ronda 2, Víctor vio que el modelo grande fallaba con los vaqueros (los llamaba «camisa» y su tejido salía «algodón»);
al mirar todos los datos, en 146 de 291 recortes de ropa inferior el modelo nombraba la prenda de arriba que asoma por el borde, y entonces el tejido, el estampado y la forma eran los de esa otra prenda.
`tendencia_prenda.py vlm-prueba` repite esos recortes con dos variantes del primer paso («¿qué prenda es?»):
  semanal_zona   el tipo se elige solo entre los de la zona del cuerpo que marcó el detector (superior, inferior, cuerpo entero, calzado, accesorio), con el recorte
  semanal_pista  caben los 29 tipos, con la foto + caja roja + recorte, y una pista suave («el detector dice que es ropa inferior; di la prenda que ocupa casi toda la caja»)
Aquí se comparan con la configuración actual («actual», lo guardado en prendas.json) contra lo que Víctor sabe: sus etiquetas a ciegas y sus veredictos de la revisión.

Uso:  python3 evaluar_zona.py DIR_CON_pred_qwen3vl8b_*.jsonl
"""
import json
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import tendencia_prenda as tp  # noqa: E402

TD = AQUI / "tendencia_datos"
EQ = {"Hoodie": "Sudadera"}
VARIANTES = ("actual", "semanal_zona", "semanal_pista")
CORTO = {"actual": "actual", "semanal_zona": "zona", "semanal_pista": "pista"}


def igual(a, b):
    return EQ.get(a, a) == EQ.get(b, b)


def main():
    dir_ = Path(sys.argv[1])
    prendas = json.loads((TD / "prendas.json").read_text(encoding="utf-8"))
    etiq = json.loads((TD / "etiquetas_prendas.json").read_text(encoding="utf-8"))
    val = json.loads((TD / "valoraciones.json").read_text(encoding="utf-8"))
    pred = {}
    for v in VARIANTES[1:]:
        pred[v] = {}
        for linea in open(dir_ / f"pred_qwen3vl8b_{v}.jsonl", encoding="utf-8"):
            r = json.loads(linea)
            pred[v][r["id"][2:]] = {"tipo": r.get("tipo29"), "estampado": r.get("estampado"), "tejido": r.get("tejido"), "forma": r.get("forma")}
    claves = sorted(set(pred["semanal_zona"]) & set(pred["semanal_pista"]))
    print(f"{len(claves)} recortes con respuesta de las dos variantes; sin tipo válido: zona {sum(pred['semanal_zona'][k]['tipo'] is None for k in claves)}, pista {sum(pred['semanal_pista'][k]['tipo'] is None for k in claves)}")

    def pr(k):
        f, _, i = k.partition("#")
        return prendas[f]["prendas"][int(i)]

    def lab(k, v):
        return (pr(k).get("vlm") or {}) if v == "actual" else pred[v][k]

    # 1. sus etiquetas a ciegas (tipo de la prenda principal)
    print("\n== 1. Tipo frente a sus etiquetas (prenda principal del recorte)")
    filas = [(k, etiq[k]["prendas"][0]["tipo"]) for k in claves if k in etiq and etiq[k].get("prendas") and etiq[k]["prendas"][0].get("tipo") and pr(k).get("vlm")]
    for nombre, filtro in (("todas", lambda k: True), ("zona inferior", lambda k: tp.ZONAS.get(pr(k).get("cat")) == "inferior"), ("zona superior", lambda k: tp.ZONAS.get(pr(k).get("cat")) == "superior"),
                           ("resto (cuerpo entero, calzado)", lambda k: tp.ZONAS.get(pr(k).get("cat")) not in ("inferior", "superior"))):
        g = [(k, t) for k, t in filas if filtro(k)]
        if not g:
            continue
        txt = " | ".join(f"{CORTO[v]} {sum(igual(lab(k, v).get('tipo'), t) for k, t in g)}/{len(g)} (familia {sum(tp.FAMILIA.get(lab(k, v).get('tipo')) == tp.FAMILIA.get(t) for k, t in g)})" for v in VARIANTES)
        print(f"   {nombre:<32} {txt}")

    # 2. su revisión (OK / más o menos / No) sobre la respuesta actual
    print("\n== 2. Su revisión (sin controles ni «no sirve»): ¿arregla lo que rechazó y mantiene lo que dio por bueno?")
    for c in ("tipo", "tejido"):
        for v in VARIANTES[1:]:
            n_no = fix = n_ok = keep = 0
            cambiados, arreglados = [], []
            for x in val.values():
                k = f"{x['foto']}#{x['idx']}"
                if x["x"] or x["control"] or k not in pred[v] or not x["r"].get(c):
                    continue
                nuevo = pred[v][k][c]
                if x["r"][c] == "no" and x["alt"].get(c):
                    n_no += 1
                    ok = any(igual(nuevo, a) for a in x["alt"][c]) if c == "tipo" else nuevo in x["alt"][c]
                    fix += ok
                    arreglados.append((x["id"], x["real"][c], nuevo, x["alt"][c], ok))
                elif x["r"][c] == "ok":
                    n_ok += 1
                    mismo = igual(nuevo, x["real"][c]) if c == "tipo" else nuevo == x["real"][c]
                    keep += mismo
                    if not mismo:
                        cambiados.append((x["id"], x["real"][c], nuevo))
            print(f"   {c:<7} {CORTO[v]:<6} rechazados con alternativa: {fix}/{n_no} arreglados | dados por buenos: {keep}/{n_ok} se mantienen")
            for t in arreglados:
                print(f"          {'✓' if t[4] else '✗'} {t[0]}: {t[1]} → {t[2]} (él: {t[3]})")
            for t in cambiados:
                print(f"          cambia lo que dio por bueno: {t[0]}: {t[1]} → {t[2]}")

    # 3. todos los recortes de ropa inferior
    print("\n== 3. Recortes de ropa inferior: ¿qué tipo sale?")
    bajos = [k for k in claves if pr(k).get("cat") == "ropa_inferior" and tp.valida(pr(k)) and pr(k).get("vlm")]
    for v in VARIANTES:
        fam = Counter(tp.FAMILIA.get(lab(k, v).get("tipo"), "sin tipo") for k in bajos)
        tipos = Counter(lab(k, v).get("tipo") for k in bajos)
        den = sum(lab(k, v).get("tejido") == "denim (vaquero)" for k in bajos if lab(k, v).get("tipo") == "Pantalón")
        print(f"   {CORTO[v]:<6} n={len(bajos)}  familia: {dict(fam.most_common())}  | Pantalón {tipos.get('Pantalón', 0)} (con tejido denim {den}) · Short {tipos.get('Short', 0)} · Falda {tipos.get('Falda', 0)}")

    # 4. vaqueros que él ha señalado
    print("\n== 4. Vaqueros que él ha señalado (revisión) o etiquetado como denim")
    casos = {}
    for x in val.values():
        if not x["x"] and not x["control"] and (any("denim" in a for a in x["alt"].get("tejido", [])) or "denim" in x["real"]["tejido"]):
            casos[f"{x['foto']}#{x['idx']}"] = f"revisión {x['id']}"
    for k, e in etiq.items():
        if any("denim" in str(p.get("tejido", "")) for p in e.get("prendas", [])):
            casos.setdefault(k, "etiqueta suya")
    for k, origen in sorted(casos.items(), key=lambda kv: kv[1]):
        if k not in pred["semanal_zona"]:
            continue
        print(f"   {origen:<16} " + " | ".join(f"{CORTO[v]}: {lab(k, v).get('tipo')}/{lab(k, v).get('tejido')}" for v in VARIANTES))

    # 5. fuera de la ropa inferior: ¿cambia algo?
    print("\n== 5. Recortes que no son de ropa inferior: ¿cuántos cambian de tipo respecto al actual?")
    otras = [k for k in claves if pr(k).get("cat") != "ropa_inferior" and pr(k).get("vlm")]
    for v in VARIANTES[1:]:
        cambian = [k for k in otras if not igual(lab(k, v).get("tipo"), pr(k)["vlm"]["tipo"])]
        fam = sum(tp.FAMILIA.get(lab(k, v).get("tipo")) != tp.FAMILIA.get(pr(k)["vlm"]["tipo"]) for k in otras)
        print(f"   {CORTO[v]:<6} {len(cambian)}/{len(otras)} cambian de tipo ({fam} de familia)")


if __name__ == "__main__":
    main()
