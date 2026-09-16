#!/usr/bin/env python3
"""
Puebla las carpetas de muestras del POC de CLIP con fotos de producto
reales (una prenda por imagen, fondo limpio) sacadas del dataset
publico "Fashion Product Images (Small)" (Param Aggarwal, Kaggle),
mirror en Hugging Face: ashraq/fashion-product-images-small.

Por que un dataset y no buscar imagenes sueltas en internet: cada fila
es una unica prenda de verdad fotografiada sobre fondo blanco/limpio --
la condicion de "foto de catalogo" que describe Estado_arte.md S5.6 --
con metadatos consistentes (tipo de prenda, uso, color...). Es mucho
mas fiable que una busqueda de texto en Wikimedia Commons, que devuelve
una mezcla de fotos de museo, gente llevando la prenda puesta, etc.
(ver herramientas/descargar_muestras_wikimedia.py, que se deja como
referencia pero ya no se usa para poblar las carpetas de muestras).

Aviso de licencia: el dataset original viene de un sitio de e-commerce
(Myntra) via Kaggle. Es uno de los datasets de moda mas usados en
investigacion y docencia de ML, pero su termino de uso en Kaggle no es
una licencia libre explicita como la de Wikimedia Commons -- adecuado
para este prototipo de investigacion, pero revisalo tu mismo antes de
usar estas imagenes concretas fuera de un contexto academico.

Requiere: pip install pyarrow
Descarga (~136 MB) el primer shard del dataset la primera vez y lo
cachea en ~/.cache/fashion-product-images-small/ (fuera del repo, no
se sube a git).

Uso:
    python3 poblar_muestras_dataset.py [--por-filtro N]
"""
import argparse
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = Path.home() / ".cache" / "fashion-product-images-small"
SHARD_URL = (
    "https://huggingface.co/api/datasets/ashraq/fashion-product-images-small"
    "/parquet/default/train/0.parquet"
)
USER_AGENT = "TFM-RoboticPickingVision-CLIP-POC/1.0 (educational research prototype)"

CABECERA_ATRIBUCION = (
    "Dataset: Fashion Product Images (Small), Param Aggarwal (Kaggle)\n"
    "https://www.kaggle.com/datasets/paramaggarwal/fashion-product-images-small\n"
    "Mirror en Hugging Face: "
    "https://huggingface.co/datasets/ashraq/fashion-product-images-small\n"
    "Aviso: no es una licencia libre explicita (origen e-commerce Myntra via "
    "Kaggle) -- uso apropiado para prototipo de investigacion academica, "
    "revisar antes de cualquier otro uso.\n"
)

# grupo_estilo -> lista de filtros; cada filtro es un dict columna->valor
# que deben cumplir TODAS las filas seleccionadas para ese filtro. La
# eleccion de articleType/usage por categoria es un mapeo manual (el
# dataset no tiene "Streetwear" ni "Playa/Resort" como campo propio).
CATEGORIAS = {
    "casual": [
        {"articleType": "Tshirts"},
        {"articleType": "Jeans"},
        {"articleType": "Shirts", "usage": "Casual"},
    ],
    "streetwear": [
        {"articleType": "Sweatshirts"},
        {"articleType": "Caps"},
        {"articleType": "Sports Shoes"},
        {"articleType": "Jackets"},
    ],
    "de_vestir": [
        {"articleType": "Formal Shoes"},
        {"articleType": "Trousers", "usage": "Formal"},
        {"articleType": "Ties"},
        {"articleType": "Shirts", "usage": "Formal"},
    ],
    "fiesta_noche": [
        {"articleType": "Dresses"},
        {"articleType": "Heels"},
        {"articleType": "Clutches"},
    ],
    "deportivo": [
        {"articleType": "Track Pants"},
        {"articleType": "Shorts", "usage": "Sports"},
        {"articleType": "Sports Shoes", "usage": "Sports"},
    ],
    "playa_resort": [
        {"articleType": "Flip Flops"},
        {"articleType": "Sandals"},
        {"articleType": "Sunglasses"},
    ],
}


def descargar_shard():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    destino = CACHE_DIR / "shard0.parquet"
    if destino.exists():
        print(f"Usando shard ya descargado en cache: {destino}")
        return destino
    print(f"Descargando shard del dataset (~136 MB) a {destino} ...")
    req = urllib.request.Request(SHARD_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp, open(destino, "wb") as f:
        f.write(resp.read())
    return destino


def cumple_filtro(fila, filtro):
    return all(fila.get(col) == val for col, val in filtro.items())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--por-filtro", type=int, default=2,
        help="Cuantas imagenes descargar por cada filtro de articleType (por defecto 2).",
    )
    args = parser.parse_args()

    ruta_parquet = descargar_shard()
    print("Cargando tabla del dataset...")
    columnas = ["id", "articleType", "usage", "gender", "baseColour", "productDisplayName", "image"]
    tabla = pq.read_table(ruta_parquet, columns=columnas).to_pylist()
    print(f"{len(tabla)} filas cargadas.")

    usadas = set()  # indices de fila ya usados, para no repetir la misma prenda en dos categorias

    for categoria, filtros in CATEGORIAS.items():
        carpeta = BASE_DIR / categoria
        carpeta.mkdir(exist_ok=True)
        atribuciones = []
        print(f"\n=== {categoria} ===")

        for filtro in filtros:
            candidatos = [
                i for i, fila in enumerate(tabla)
                if i not in usadas and cumple_filtro(fila, filtro)
            ]
            elegidos = candidatos[: args.por_filtro]
            if not elegidos:
                print(f"  (aviso) sin candidatos para el filtro {filtro}")
                continue

            etiqueta = filtro["articleType"].lower().replace(" ", "_")
            for n, idx in enumerate(elegidos, 1):
                fila = tabla[idx]
                nombre = f"{etiqueta}_{n}.jpg"
                (carpeta / nombre).write_bytes(fila["image"]["bytes"])
                usadas.add(idx)
                atribuciones.append(
                    f"{nombre}: {fila['productDisplayName']} "
                    f"(articleType={fila['articleType']}, usage={fila['usage']}, "
                    f"gender={fila['gender']}, color={fila['baseColour']}, "
                    f"id_dataset={fila['id']})"
                )
                print(f"  + {nombre}  <-  {fila['productDisplayName']}")

        (carpeta / "ATRIBUCIONES.txt").write_text(
            CABECERA_ATRIBUCION + "\n" + "\n".join(atribuciones), encoding="utf-8"
        )
        print(f"  Total en {categoria}: {len(atribuciones)} imagenes")


if __name__ == "__main__":
    main()
