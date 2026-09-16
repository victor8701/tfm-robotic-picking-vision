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

Sobre el mapeo de clases: el dataset tiene 135 valores de articleType.
Se han revisado los 135 y se descartan a proposito tres bloques enteros
porque no aportan senal util para "estilo/tendencia de una prenda":
  - Ropa etnica india (Kurtas, Sarees, Salwar, Churidar, Dupatta...):
    no tiene equivalente en la taxonomia Inditex-style de Estado_arte.md.
  - Ropa interior/de estar por casa (Bra, Briefs, Nightdress, Boxers...):
    no es "outfit" visible para trend matching.
  - Articulos no textiles (relojes, perfume, maquillaje, joyeria...):
    no son prendas.
El resto se reparte entre los 6 Grupos de estilo de S3.4.1, afinando
con el campo `usage` o `season` del dataset cuando ayuda a distinguir
(p.ej. "Track Pants" con usage=Sports va a deportivo/, con usage=Casual
va a streetwear/).

Aviso de licencia: el dataset original viene de un sitio de e-commerce
(Myntra) via Kaggle. Es uno de los datasets de moda mas usados en
investigacion y docencia de ML, pero su termino de uso en Kaggle no es
una licencia libre explicita como la de Wikimedia Commons -- adecuado
para este prototipo de investigacion, pero revisalo tu mismo antes de
usar estas imagenes concretas fuera de un contexto academico.

Requiere: pip install pyarrow
Descarga (~136 MB cada uno) los dos shards del dataset la primera vez
y los cachea en ~/.cache/fashion-product-images-small/ (fuera del
repo, no se sube a git).

Uso:
    python3 poblar_muestras_dataset.py [--por-filtro N] [--max-por-categoria N]
"""
import argparse
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = Path.home() / ".cache" / "fashion-product-images-small"
SHARD_URLS = [
    "https://huggingface.co/api/datasets/ashraq/fashion-product-images-small"
    "/parquet/default/train/0.parquet",
    "https://huggingface.co/api/datasets/ashraq/fashion-product-images-small"
    "/parquet/default/train/1.parquet",
]
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
# eleccion de articleType/usage/season por categoria es un mapeo manual
# (el dataset no tiene estos 6 Grupos de estilo como campo propio).
CATEGORIAS = {
    "casual": [
        {"articleType": "Tshirts"},
        {"articleType": "Jeans"},
        {"articleType": "Shirts", "usage": "Casual"},
        {"articleType": "Tops", "usage": "Casual"},
        {"articleType": "Sweaters"},
        {"articleType": "Casual Shoes"},
        {"articleType": "Capris"},
        {"articleType": "Flats"},
    ],
    "streetwear": [
        {"articleType": "Sweatshirts"},
        {"articleType": "Caps"},
        {"articleType": "Jackets"},
        {"articleType": "Backpacks"},
        {"articleType": "Track Pants", "usage": "Casual"},
    ],
    "de_vestir": [
        {"articleType": "Formal Shoes"},
        {"articleType": "Trousers"},
        {"articleType": "Ties"},
        {"articleType": "Shirts", "usage": "Formal"},
        {"articleType": "Waistcoat"},
    ],
    "fiesta_noche": [
        {"articleType": "Dresses"},
        {"articleType": "Heels"},
        {"articleType": "Clutches"},
        {"articleType": "Jumpsuit"},
    ],
    "deportivo": [
        {"articleType": "Track Pants", "usage": "Sports"},
        {"articleType": "Shorts", "usage": "Sports"},
        {"articleType": "Sports Shoes", "usage": "Sports"},
        {"articleType": "Leggings"},
        {"articleType": "Tracksuits"},
        {"articleType": "Sports Sandals"},
    ],
    "playa_resort": [
        {"articleType": "Flip Flops"},
        {"articleType": "Sandals"},
        {"articleType": "Shorts", "usage": "Casual", "season": "Summer"},
        {"articleType": "Swimwear"},
        {"articleType": "Skirts", "season": "Summer"},
        {"articleType": "Sunglasses"},
    ],
}


def descargar_shards():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    rutas = []
    for i, url in enumerate(SHARD_URLS):
        destino = CACHE_DIR / f"shard{i}.parquet"
        if destino.exists():
            print(f"Usando shard ya descargado en cache: {destino}")
        else:
            print(f"Descargando shard {i} del dataset (~136 MB) a {destino} ...")
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=180) as resp, open(destino, "wb") as f:
                f.write(resp.read())
        rutas.append(destino)
    return rutas


def cumple_filtro(fila, filtro):
    return all(fila.get(col) == val for col, val in filtro.items())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--por-filtro", type=int, default=40,
        help="Maximo de imagenes a coger de cada filtro individual (por defecto 40).",
    )
    parser.add_argument(
        "--max-por-categoria", type=int, default=250,
        help="Tope total de imagenes por carpeta/grupo_estilo (por defecto 250).",
    )
    args = parser.parse_args()

    rutas_parquet = descargar_shards()
    print("Cargando tabla del dataset (los dos shards)...")
    columnas = [
        "id", "articleType", "usage", "season", "gender",
        "baseColour", "productDisplayName", "image",
    ]
    tabla = []
    for ruta in rutas_parquet:
        tabla.extend(pq.read_table(ruta, columns=columnas).to_pylist())
    print(f"{len(tabla)} filas cargadas en total.")

    usadas = set()  # indices de fila ya usados, para no repetir la misma prenda en dos categorias

    for categoria, filtros in CATEGORIAS.items():
        carpeta = BASE_DIR / categoria
        carpeta.mkdir(exist_ok=True)
        atribuciones = []
        print(f"\n=== {categoria} ===")

        for filtro in filtros:
            if len(atribuciones) >= args.max_por_categoria:
                print(f"  (tope de {args.max_por_categoria} alcanzado, se omiten filtros restantes)")
                break

            candidatos = [
                i for i, fila in enumerate(tabla)
                if i not in usadas and cumple_filtro(fila, filtro)
            ]
            hueco = args.max_por_categoria - len(atribuciones)
            elegidos = candidatos[: min(args.por_filtro, hueco)]
            if not elegidos:
                print(f"  (aviso) sin candidatos para el filtro {filtro}")
                continue

            etiqueta = filtro["articleType"].lower().replace(" ", "_")
            existentes = len(list(carpeta.glob(f"{etiqueta}_*.jpg")))
            for n, idx in enumerate(elegidos, existentes + 1):
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
            print(f"  + {len(elegidos)} imagenes de '{filtro}'")

        (carpeta / "ATRIBUCIONES.txt").write_text(
            CABECERA_ATRIBUCION + "\n" + "\n".join(atribuciones), encoding="utf-8"
        )
        print(f"  Total en {categoria}: {len(atribuciones)} imagenes")


if __name__ == "__main__":
    main()
