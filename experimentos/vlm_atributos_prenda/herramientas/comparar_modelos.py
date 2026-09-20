#!/usr/bin/env python3
"""
Compara N adapters sobre las MISMAS fichas revisadas a mano (no el test set completo, que
cambia de contenido entre versiones del dataset -- ver memoria S11.2/S11.5). Es una comparacion
pareada: las 100 fichas son identicas para todos los modelos, asi que aqui se puede saber si
una caida es ruido de una foto dificil o un cambio real, mirando que fichas cambian de acierto
a fallo (y al reves) de una version a la siguiente -- no solo el numero agregado.

Uso:
    python3 comparar_modelos.py --revisiones ../data/revision_humana/revisiones_app_n100_2026-09-20.json
        # por defecto compara v1, v2 y v3 (los ficheros de data/revision_humana/predicciones_app_120*.json)
    python3 comparar_modelos.py --revisiones ... --modelo v2=../data/revision_humana/predicciones_app_120_v2.json \
        --modelo v3=../data/revision_humana/predicciones_app_120_v3.json   # subconjunto / otros ficheros
"""
import argparse
import collections
import json
from pathlib import Path

CAMPOS = ["categoria", "color_primario", "genero", "temporada", "grupo_estilo"]
DATOS = Path(__file__).parent.parent / "data" / "revision_humana"
DEFAULT_MODELOS = [
    ("v1", DATOS / "predicciones_app_120.json"),
    ("v2", DATOS / "predicciones_app_120_v2.json"),
    ("v3", DATOS / "predicciones_app_120_v3.json"),
    ("v4", DATOS / "predicciones_app_120_v4.json"),
]


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


def parse_modelo(s):
    nombre, ruta = s.split("=", 1)
    return nombre, Path(ruta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revisiones", required=True)
    ap.add_argument("--manifest", default=str(DATOS / "manifest_app_120.json"))
    ap.add_argument("--modelo", action="append", type=parse_modelo, metavar="NOMBRE=RUTA",
                    help="Repetible. Por defecto compara v1/v2/v3 con los ficheros ya conocidos, en ese orden.")
    args = ap.parse_args()
    modelos_spec = args.modelo or [(n, r) for n, r in DEFAULT_MODELOS if r.exists()]
    if len(modelos_spec) < 2:
        raise SystemExit("Hacen falta al menos 2 --modelo (o al menos 2 de los ficheros v1/v2/v3 por defecto).")

    manifest = {str(m["id"]): m for m in json.load(open(Path(args.manifest).expanduser(), encoding="utf-8"))}
    modelos = {nombre: cargar_predicciones(ruta) for nombre, ruta in modelos_spec}
    nombres = [n for n, _ in modelos_spec]
    revs = cargar_revisiones(args.revisiones)
    ids = sorted((i for i in revs if all(modelos[n].get(i) for n in nombres)), key=int)
    print(f"Modelos: {' -> '.join(nombres)}   Fichas comparables: {len(ids)}\n")

    cab = "".join(f"{n + ' vs Kaggle':>14}" for n in nombres) + "  " + "".join(f"{n + ' vs humano':>14}" for n in nombres)
    print(f"{'campo':<16} {cab}")
    tot_k = {n: 0 for n in nombres}
    tot_h = {n: 0 for n in nombres}
    for c in CAMPOS:
        fila_k, fila_h = [], []
        for n in nombres:
            k = sum(1 for i in ids if modelos[n][i].get(c) == manifest[i][c])
            h = sum(1 for i in ids if modelos[n][i].get(c) in S(revs[i][c]))
            tot_k[n] += k
            tot_h[n] += h
            fila_k.append(f"{k / len(ids):>14.0%}")
            fila_h.append(f"{h / len(ids):>14.0%}")
        print(f"{c:<16} {''.join(fila_k)}  {''.join(fila_h)}")
    n5 = 5 * len(ids)
    print(f"{'MEDIA':<16} " + "".join(f"{tot_k[n] / n5:>14.0%}" for n in nombres) + "  " +
          "".join(f"{tot_h[n] / n5:>14.0%}" for n in nombres))

    for a, b in zip(nombres, nombres[1:]):
        print(f"\nCambios pareados frente al humano ({a} -> {b}, misma ficha)")
        for c in CAMPOS:
            gana = pierde = 0
            cambios_pierde = []
            for i in ids:
                ok_a = modelos[a][i].get(c) in S(revs[i][c])
                ok_b = modelos[b][i].get(c) in S(revs[i][c])
                if ok_a and not ok_b:
                    pierde += 1
                    cambios_pierde.append((i, modelos[a][i].get(c), modelos[b][i].get(c)))
                elif ok_b and not ok_a:
                    gana += 1
            print(f"  {c:<16} pasan de acierto a fallo: {pierde:<3}  pasan de fallo a acierto: {gana}")
            if c == "color_primario" and cambios_pierde:
                print("    fichas que color_primario pierde (id, antes->despues, nombre, tu selección):")
                for i, x, y in cambios_pierde:
                    m = manifest[i]
                    print(f"      {i:<6} {x}->{y:<10} {m['productDisplayName'][:40]:<42} tu={sorted(S(revs[i]['color_primario']))}")


if __name__ == "__main__":
    main()
