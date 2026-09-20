#!/usr/bin/env python3
"""
Compara el adapter v1 y el v2 sobre las MISMAS fichas revisadas a mano (no sobre el test set
completo, que cambio de contenido entre versiones -- ver memoria S11.2). Es una comparacion
pareada: las 100 fichas son identicas para los dos modelos, asi que aqui se puede saber si una
caida es ruido de una foto dificil o un cambio real, mirando que fichas cambian de acierto a
fallo (y al reves) al pasar de v1 a v2 -- no solo el numero agregado.

Uso:
    python3 comparar_modelos_v1_v2.py \
        --revisiones ../data/revision_humana/revisiones_app_n100_2026-09-20.json \
        --predicciones-v1 ../data/revision_humana/predicciones_app_120.json \
        --predicciones-v2 ../data/revision_humana/predicciones_app_120_v2.json
"""
import argparse
import collections
import json
from pathlib import Path

CAMPOS = ["categoria", "color_primario", "genero", "temporada", "grupo_estilo"]


def S(v):
    return set(v) if isinstance(v, list) else {v}


def cargar_revisiones(ruta):
    return {str(i): d.get("data", d) for i, d in json.load(open(Path(ruta).expanduser(), encoding="utf-8")).items()}


def cargar_predicciones(ruta):
    """predicciones_app_120.json esta "aplanado" (los 5 campos sueltos); la salida cruda de
    predecir_lote.py envuelve la prediccion en {"prediccion": {...}, "texto_crudo": ...} --
    se admiten los dos formatos aqui."""
    datos = json.load(open(Path(ruta).expanduser(), encoding="utf-8"))
    return {str(i): (v.get("prediccion") or {}) if "prediccion" in v else v for i, v in datos.items()}


def main():
    ap = argparse.ArgumentParser()
    datos = Path(__file__).parent.parent / "data" / "revision_humana"
    ap.add_argument("--revisiones", required=True)
    ap.add_argument("--manifest", default=str(datos / "manifest_app_120.json"))
    ap.add_argument("--predicciones-v1", default=str(datos / "predicciones_app_120.json"))
    ap.add_argument("--predicciones-v2", default=str(datos / "predicciones_app_120_v2.json"))
    args = ap.parse_args()

    manifest = {str(m["id"]): m for m in json.load(open(Path(args.manifest).expanduser(), encoding="utf-8"))}
    v1 = cargar_predicciones(args.predicciones_v1)
    v2 = cargar_predicciones(args.predicciones_v2)
    revs = cargar_revisiones(args.revisiones)
    ids = sorted((i for i in revs if v1.get(i) and v2.get(i)), key=int)
    print(f"Fichas comparables (revisadas y con prediccion valida en v1 y v2): {len(ids)}\n")

    print(f"{'campo':<16} {'v1 vs Kaggle':>13} {'v2 vs Kaggle':>13}   {'v1 vs humano':>13} {'v2 vs humano':>13}")
    tot_k1 = tot_k2 = tot_h1 = tot_h2 = 0
    for c in CAMPOS:
        k1 = sum(1 for i in ids if v1[i].get(c) == manifest[i][c])
        k2 = sum(1 for i in ids if v2[i].get(c) == manifest[i][c])
        h1 = sum(1 for i in ids if v1[i].get(c) in S(revs[i][c]))
        h2 = sum(1 for i in ids if v2[i].get(c) in S(revs[i][c]))
        tot_k1, tot_k2, tot_h1, tot_h2 = tot_k1 + k1, tot_k2 + k2, tot_h1 + h1, tot_h2 + h2
        print(f"{c:<16} {k1 / len(ids):>13.0%} {k2 / len(ids):>13.0%}   {h1 / len(ids):>13.0%} {h2 / len(ids):>13.0%}")
    n5 = 5 * len(ids)
    print(f"{'MEDIA':<16} {tot_k1 / n5:>13.0%} {tot_k2 / n5:>13.0%}   {tot_h1 / n5:>13.0%} {tot_h2 / n5:>13.0%}")

    print("\nCambios pareados frente al humano (v1 -> v2, misma ficha)")
    for c in CAMPOS:
        gana = pierde = 0
        cambios_pierde = []
        for i in ids:
            ok1 = v1[i].get(c) in S(revs[i][c])
            ok2 = v2[i].get(c) in S(revs[i][c])
            if ok1 and not ok2:
                pierde += 1
                cambios_pierde.append((i, v1[i].get(c), v2[i].get(c)))
            elif ok2 and not ok1:
                gana += 1
        print(f"  {c:<16} pasan de acierto a fallo: {pierde:<3}  pasan de fallo a acierto: {gana}")
        if c == "color_primario" and cambios_pierde:
            print("    fichas que color_primario pierde (id, v1->v2, nombre, tu seleccion):")
            for i, a, b in cambios_pierde:
                m = manifest[i]
                print(f"      {i:<6} {a}->{b:<10} {m['productDisplayName'][:40]:<42} tu={sorted(S(revs[i]['color_primario']))}")


if __name__ == "__main__":
    main()
