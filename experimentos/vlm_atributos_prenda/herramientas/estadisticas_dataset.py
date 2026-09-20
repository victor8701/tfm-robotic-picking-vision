#!/usr/bin/env python3
"""
Distribucion de clases de cada campo en train/val/test (data/*.jsonl), en tablas
Markdown listas para pegar en la memoria. Sin dependencias fuera de la libreria
estandar.

Uso:
    python3 estadisticas_dataset.py
"""
import collections
import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
CAMPOS = ["categoria", "color_primario", "grupo_estilo", "genero", "temporada"]
SPLITS = ["train", "val", "test"]


def main():
    filas = {s: [json.loads(l) for l in open(DATA / f"{s}.jsonl", encoding="utf-8")] for s in SPLITS}
    print("| Split | Imagenes |\n|---|---|")
    for s in SPLITS:
        print(f"| {s} | {len(filas[s])} |")
    for campo in CAMPOS:
        cnt = {s: collections.Counter(r[campo] for r in filas[s]) for s in SPLITS}
        valores = sorted(cnt["train"], key=lambda v: -cnt["train"][v])
        valores += sorted(v for s in SPLITS for v in cnt[s] if v not in valores)
        print(f"\n### `{campo}`\n\n| valor | train | val | test |\n|---|---|---|---|")
        for v in dict.fromkeys(valores):
            celdas = " | ".join(f"{cnt[s][v]} ({cnt[s][v] / len(filas[s]):.1%})" for s in SPLITS)
            print(f"| {v} | {celdas} |")


if __name__ == "__main__":
    main()
