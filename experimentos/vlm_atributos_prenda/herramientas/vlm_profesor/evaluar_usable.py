#!/usr/bin/env python3
"""
Mide el filtro de recortes inservibles del modelo grande (configuraciones `usable_a` y `usable_b` de kernel_profesor.py) contra lo que Víctor marcó en «Etiquetar prendas»:
inservible (`inservible: true`) frente a utilizable (tiene prendas etiquetadas). Sus marcas no se subieron a Kaggle.

Para un filtro importa sobre todo: de los recortes que descarta, cuántos eran de verdad inservibles (precisión) y cuántos de los buenos se pierde (utilizables descartados).

Uso:  python3 evaluar_usable.py --pred DIR_CON_pred_*_usable_*.jsonl [--lote-ciego] [--salida resultados/….json]
"""
import argparse
import collections
import json
import math
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BASE = AQUI.parents[2] / "analisis_mercado" / "tendencia_datos"


def wilson(k, n, z=1.96):
    if not n:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h)), round(100 * (c + h)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pred", type=Path, required=True)
    ap.add_argument("--etiquetas", type=Path, default=BASE / "etiquetas_prendas.json")
    ap.add_argument("--lote-ciego", action="store_true", help="medir solo con los recortes del lote ciego (los demás se eligieron por variedad)")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args()
    etiq = json.loads(a.etiquetas.read_text(encoding="utf-8"))
    ciego = set(json.loads((BASE / "lote_ciego.json").read_text(encoding="utf-8")))
    verdad = {}
    for k, v in etiq.items():
        if a.lote_ciego and k not in ciego:
            continue
        if v.get("inservible"):
            verdad[k] = "inservible"
        elif v.get("prendas"):
            verdad[k] = "utilizable"
    print(f"verdad de Víctor: {collections.Counter(verdad.values())}" + (" (solo lote ciego)" if a.lote_ciego else ""))
    res = {}
    for f in sorted(a.pred.glob("pred_*usable*.jsonl")):
        filas = [json.loads(linea) for linea in open(f, encoding="utf-8")]
        cfg = filas[0]["config"]
        pred = {r["id"][2:]: r for r in filas}
        tp = fp = fn = tn = sin = 0
        motivos = collections.Counter()
        for k, v in verdad.items():
            r = pred.get(k)
            if r is None or r.get("usable") is None:
                sin += 1
                continue
            descarta = r["usable"] == "no"
            if descarta:
                motivos[(v, r.get("motivo"))] += 1
            if v == "inservible":
                tp += descarta
                fn += not descarta
            else:
                fp += descarta
                tn += not descarta
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        res[cfg] = {"descarta_inservibles": [tp, tp + fn], "descarta_utilizables": [fp, fp + tn], "precision_al_descartar": [tp, tp + fp], "sin_respuesta": sin,
                    "motivos_de_descarte": {f"{v} → {m}": n for (v, m), n in motivos.most_common()}}
        print(f"\n== {cfg}: descarta {tp} de {tp + fn} inservibles (recall {100 * rec:.0f} %, IC {wilson(tp, tp + fn)}) y {fp} de {fp + tn} utilizables ({100 * fp / (fp + tn) if fp + tn else 0:.0f} %, IC {wilson(fp, fp + tn)}); "
              f"cuando descarta acierta {tp} de {tp + fp} ({100 * prec:.0f} %); sin respuesta válida: {sin}")
        print("   motivos:", dict(motivos.most_common(8)))
    if a.salida:
        a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
