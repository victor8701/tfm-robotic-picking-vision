#!/usr/bin/env python3
"""
Convierte el dataset "Fashion Product Images (Small)" en ejemplos de
entrenamiento para el fine-tuning de Florence-2: pares (imagen, JSON de
atributos). Si el parquet no esta cacheado (p.ej. maquina nueva, sesion
de Colab), se descarga solo -- mismos shards que usa
experimentos/clip_trend_matching/herramientas/poblar_muestras_dataset.py,
asi que si ya lo corriste antes en esta maquina no vuelve a bajar nada.

El esquema de salida y las tablas de mapeo completas estan documentadas
en ../esquema_atributos.md -- este script es la implementacion de esas
tablas, no la fuente de verdad (si cambia una tabla, cambia primero el
.md y luego este script).

Solo se queda una fila si los 5 campos (categoria, color_primario,
grupo_estilo, genero, temporada) se pueden mapear -- si falta alguno,
la fila se descarta entera (no hay supervision parcial en este v1).

Reglas v2 (2026-09-20, decisiones del autor sobre memoria/TFM_clasificador_visual_atributos.md
S11.1, a partir de la revision humana de 100 fichas):
  - Filtro de ropa infantil por NOMBRE, no solo por `gender`: ~3.3% del dataset tiene
    gender=Boys/Girls (ya se descartaba), pero 713 filas mas (p.ej. "Doodle Kids Girl...",
    "Gini and Jony Girl's...") llevan gender=Women/Men y se colaban -- 108 de las 464 Dresses.
  - `temporada` gana un tercer valor, `todo_el_ano`: por ahora solo para Jackets (decision
    explicita: "vamos a suponerlas de todas las estaciones, independientemente de lo que
    pusiese yo [en la revision]"). El resto sigue con el mapeo de 2 valores por `season` de
    Kaggle -- pendiente extender la tabla a mas tipos de prenda.
  - `grupo_estilo` de Dresses ya no es fiesta_noche fijo (regla vieja, mal: usage=Party solo
    18/464 filas, y la revision humana la corrige en 11 de 16 vestidos a casual). Nueva regla,
    validada contra la revision humana (13/14 vestidos no infantiles, descartando los 2
    contraejemplos por defecto de fabrica): estampado/multicolor -> casual, liso -> fiesta_noche
    (el criterio dado fue "de noche suelen ser de un unico color, mas planos y quizas
    brillantes" -- no hay vestidos con lentejuelas/brillo en este catalogo de 60x80px para
    afinar esa parte). Heels/Clutches/Jumpsuit se quedan igual: la revision humana los confirma
    (Heels 2/3, Clutches 4/4) salvo Jumpsuit (el unico caso revisado no encajaba, pero es 1 dato).
  - Paleta de color SIN cambios (decision explicita: no tocar el vocabulario de Estado_arte.md
    tan a fondo) -- `lavanda` sigue absorbiendo `Purple`, `fucsia`/`plateado` siguen con pocos
    ejemplos.

Reglas v3 (2026-09-20, mismo dia): `temporada` amplia TIPOS_TODO_EL_ANO al resto de tipos de
prenda, decidido tipo a tipo por el autor en el artifact "Reglas de temporada" (propuesta por
tipo calculada de sus 100 revisiones -- mayoria clara -> esa regla, sin patron -> se deja el
mapeo por `season` de Kaggle; el autor solo corrigio una, Caps, de la propuesta "estacional" a
"todo_el_ano"). Nada mas cambia respecto a v2 -- ver TIPOS_TODO_EL_ANO abajo para el detalle.

Uso:
    python3 preparar_dataset_florence2.py [--train N] [--val N] [--test N]
"""
import argparse
import json
import random
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq

BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = Path.home() / ".cache" / "fashion-product-images-small"
SEMILLA = 42

SHARD_URLS = [
    "https://huggingface.co/api/datasets/ashraq/fashion-product-images-small"
    "/parquet/default/train/0.parquet",
    "https://huggingface.co/api/datasets/ashraq/fashion-product-images-small"
    "/parquet/default/train/1.parquet",
]
USER_AGENT = "TFM-RoboticPickingVision-CLIP-POC/1.0 (educational research prototype)"

# ---------------------------------------------------------------------------
# Mapeos -- ver esquema_atributos.md para la tabla completa y el porque
# ---------------------------------------------------------------------------

CATEGORIA_POR_ARTICLETYPE = {
    "Tshirts": "ropa_superior", "Shirts": "ropa_superior", "Tops": "ropa_superior",
    "Sweatshirts": "ropa_superior", "Sweaters": "ropa_superior", "Waistcoat": "ropa_superior",
    "Jeans": "ropa_inferior", "Shorts": "ropa_inferior", "Trousers": "ropa_inferior",
    "Track Pants": "ropa_inferior", "Leggings": "ropa_inferior", "Capris": "ropa_inferior",
    "Skirts": "ropa_inferior",
    "Dresses": "cuerpo_entero", "Jumpsuit": "cuerpo_entero",
    "Jackets": "abrigo", "Blazers": "abrigo", "Rain Jacket": "abrigo", "Nehru Jackets": "abrigo",
    "Casual Shoes": "calzado", "Sports Shoes": "calzado", "Heels": "calzado",
    "Formal Shoes": "calzado", "Flats": "calzado", "Sandals": "calzado",
    "Flip Flops": "calzado", "Sports Sandals": "calzado",
    "Handbags": "accesorio", "Backpacks": "accesorio", "Belts": "accesorio", "Caps": "accesorio",
    "Scarves": "accesorio", "Stoles": "accesorio", "Mufflers": "accesorio", "Ties": "accesorio",
    "Clutches": "accesorio",
}

COLOR_POR_BASECOLOUR = {
    "Black": "negro",
    "White": "blanco", "Off White": "blanco",
    "Blue": "azul", "Turquoise Blue": "azul", "Teal": "azul",
    "Navy Blue": "navy",
    "Grey": "gris", "Grey Melange": "gris", "Charcoal": "gris",
    "Red": "rojo",
    "Green": "verde", "Olive": "verde", "Sea Green": "verde", "Lime Green": "verde",
    "Fluorescent Green": "verde",
    "Pink": "rosa", "Rose": "rosa", "Mauve": "rosa",
    "Purple": "lavanda", "Lavender": "lavanda",
    "Silver": "plateado", "Steel": "plateado", "Metallic": "plateado",
    "Yellow": "amarillo", "Mustard": "amarillo",
    "Beige": "beige", "Cream": "beige", "Skin": "beige", "Nude": "beige", "Taupe": "beige",
    "Brown": "camel", "Khaki": "camel", "Tan": "camel", "Coffee Brown": "camel",
    "Mushroom Brown": "camel",
    "Gold": "dorado", "Bronze": "dorado", "Copper": "dorado",
    "Maroon": "burdeos", "Burgundy": "burdeos",
    "Orange": "naranja", "Peach": "naranja", "Rust": "naranja",
    "Magenta": "fucsia",
    # "Multi" deliberadamente fuera: no es un color primario, ver esquema_atributos.md
}

GENERO_POR_GENDER = {"Men": "masculino", "Women": "femenino", "Unisex": "neutro"}

TEMPORADA_POR_SEASON = {
    "Summer": "primavera_verano", "Spring": "primavera_verano",
    "Fall": "otono_invierno", "Winter": "otono_invierno",
}
# Tipos de prenda que se dan por "todo el año" pase lo que ponga `season` -- ver aviso v2
# arriba. v2 solo tenia Jackets; v3 (2026-09-20) amplia al resto de tipos segun las decisiones
# del autor en el artifact "Reglas de temporada" (propuesta calculada de sus 100 revisiones,
# confirmada o corregida por el a mano -- solo corrigio Caps, de "estacional" a "todo_el_ano";
# el resto de propuestas se quedaron como estaban). Lo que no esta aqui sigue con el mapeo de
# 2 valores por `season` de Kaggle (incluye Dresses, que se quedo sin patron claro en la
# revision -- ver esquema_atributos.md).
TIPOS_TODO_EL_ANO = {
    "Jackets", "Caps", "Backpacks", "Casual Shoes", "Clutches", "Formal Shoes", "Heels",
    "Jeans", "Shirts", "Sports Shoes", "Sweaters", "Track Pants", "Trousers",
}

# Ropa infantil que se cuela con gender=Women/Men (marcas y palabras habituales del dataset;
# ver aviso v2 arriba). `gender` ya filtra Boys/Girls, esto filtra lo que ese campo no coge.
PATRON_INFANTIL = re.compile(
    r"\b(kids?|girl'?s?|boy'?s?|infants?|baby|toddler|juniors?|kidz)\b|gini and jony|doodle",
    re.IGNORECASE,
)

# Vestidos: estampado/multicolor -> casual, liso -> fiesta_noche (ver aviso v2 arriba).
PATRON_ESTAMPADO_VESTIDO = re.compile(
    r"printed?|striped?|floral|polka|dot|checked?|multi|colou?r|animal|a-line|tiered|ruffle",
    re.IGNORECASE,
)

# grupo_estilo -> filtros (mismo formato y mismas listas que
# clip_trend_matching/herramientas/poblar_muestras_dataset.py, reutilizadas
# tal cual para que las dos piezas del TFM usen el mismo criterio).
FILTROS_GRUPO_ESTILO = [
    ("casual", {"articleType": "Tshirts"}),
    ("casual", {"articleType": "Jeans"}),
    ("casual", {"articleType": "Shirts", "usage": "Casual"}),
    ("casual", {"articleType": "Tops", "usage": "Casual"}),
    ("casual", {"articleType": "Sweaters"}),
    ("casual", {"articleType": "Casual Shoes"}),
    ("casual", {"articleType": "Capris"}),
    ("casual", {"articleType": "Flats"}),
    ("streetwear", {"articleType": "Sweatshirts"}),
    ("streetwear", {"articleType": "Caps"}),
    ("streetwear", {"articleType": "Jackets"}),
    ("streetwear", {"articleType": "Backpacks"}),
    ("streetwear", {"articleType": "Track Pants", "usage": "Casual"}),
    ("de_vestir", {"articleType": "Formal Shoes"}),
    ("de_vestir", {"articleType": "Trousers"}),
    ("de_vestir", {"articleType": "Ties"}),
    ("de_vestir", {"articleType": "Shirts", "usage": "Formal"}),
    ("de_vestir", {"articleType": "Waistcoat"}),
    # Dresses NO esta aqui: tiene regla propia en mapear_grupo_estilo (ver aviso v2 arriba).
    ("fiesta_noche", {"articleType": "Heels"}),
    ("fiesta_noche", {"articleType": "Clutches"}),
    ("fiesta_noche", {"articleType": "Jumpsuit"}),
    ("deportivo", {"articleType": "Track Pants", "usage": "Sports"}),
    ("deportivo", {"articleType": "Shorts", "usage": "Sports"}),
    ("deportivo", {"articleType": "Sports Shoes", "usage": "Sports"}),
    ("deportivo", {"articleType": "Leggings"}),
    ("deportivo", {"articleType": "Tracksuits"}),
    ("deportivo", {"articleType": "Sports Sandals"}),
    ("playa_resort", {"articleType": "Flip Flops"}),
    ("playa_resort", {"articleType": "Sandals"}),
    ("playa_resort", {"articleType": "Shorts", "usage": "Casual", "season": "Summer"}),
    ("playa_resort", {"articleType": "Swimwear"}),
    ("playa_resort", {"articleType": "Skirts", "season": "Summer"}),
]


def mapear_grupo_estilo(fila):
    if fila.get("articleType") == "Dresses":
        nombre = fila.get("productDisplayName", "")
        return "casual" if PATRON_ESTAMPADO_VESTIDO.search(nombre) else "fiesta_noche"
    for grupo, filtro in FILTROS_GRUPO_ESTILO:
        if all(fila.get(col) == val for col, val in filtro.items()):
            return grupo
    return None


def mapear_temporada(fila):
    if fila.get("articleType") in TIPOS_TODO_EL_ANO:
        return "todo_el_ano"
    return TEMPORADA_POR_SEASON.get(fila["season"])


def mapear_fila(fila):
    """Devuelve el dict de 5 campos, o None si falta alguno o es ropa infantil colada
    (gender=Women/Men/Unisex pero el nombre delata que es de niño/a; ver aviso v2 arriba)."""
    if PATRON_INFANTIL.search(fila.get("productDisplayName", "")):
        return None

    categoria = CATEGORIA_POR_ARTICLETYPE.get(fila["articleType"])
    color = COLOR_POR_BASECOLOUR.get(fila["baseColour"])
    grupo_estilo = mapear_grupo_estilo(fila)
    genero = GENERO_POR_GENDER.get(fila["gender"])
    temporada = mapear_temporada(fila)

    if None in (categoria, color, grupo_estilo, genero, temporada):
        return None

    return {
        "categoria": categoria,
        "color_primario": color,
        "grupo_estilo": grupo_estilo,
        "genero": genero,
        "temporada": temporada,
    }


def descargar_shard_si_falta(nombre, url):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    destino = CACHE_DIR / nombre
    if destino.exists():
        return destino
    print(f"No esta cacheado {destino}, descargando (~136 MB)...")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp, open(destino, "wb") as f:
        f.write(resp.read())
    return destino


def cargar_filas():
    columnas = [
        "id", "gender", "articleType", "baseColour", "season",
        "usage", "productDisplayName", "image",
    ]
    filas = []
    for i, url in enumerate(SHARD_URLS):
        ruta = descargar_shard_si_falta(f"shard{i}.parquet", url)
        filas.extend(pq.read_table(ruta, columns=columnas).to_pylist())
    return filas


def muestreo_estratificado(filas_mapeadas, n_objetivo, rng):
    """Reparte n_objetivo filas balanceando por categoria. Categorias con
    pocas filas (p.ej. abrigo, cuerpo_entero) no pueden llenar su cupo
    inicial -- ese hueco se redistribuye en pasadas sucesivas entre las
    categorias que aun tengan filas disponibles, para no quedarnos cortos
    del total pedido solo porque una categoria escasea (bug real: sin este
    reparto, val/test podian salir vacios aunque sobrasen filas en total)."""
    por_categoria = defaultdict(list)
    for f in filas_mapeadas:
        por_categoria[f["_atributos"]["categoria"]].append(f)
    for lista in por_categoria.values():
        rng.shuffle(lista)

    disponibles = {c: len(v) for c, v in por_categoria.items()}
    tomado = {c: 0 for c in por_categoria}
    activas = [c for c in por_categoria if disponibles[c] > 0]

    objetivo_restante = min(n_objetivo, sum(disponibles.values()))
    while objetivo_restante > 0 and activas:
        cupo = max(1, objetivo_restante // len(activas))
        for c in list(activas):
            hueco = disponibles[c] - tomado[c]
            coger = min(cupo, hueco, objetivo_restante)
            tomado[c] += coger
            objetivo_restante -= coger
            if tomado[c] >= disponibles[c]:
                activas.remove(c)
            if objetivo_restante <= 0:
                break

    elegidas = []
    for c, lista in por_categoria.items():
        elegidas.extend(lista[: tomado[c]])
    return elegidas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=int, default=4000)
    parser.add_argument("--val", type=int, default=500)
    parser.add_argument("--test", type=int, default=500)
    args = parser.parse_args()

    rng = random.Random(SEMILLA)

    print("Cargando parquet (dos shards)...")
    filas = cargar_filas()
    print(f"{len(filas)} filas totales en el dataset.")

    mapeadas = []
    for f in filas:
        atributos = mapear_fila(f)
        if atributos is not None:
            f["_atributos"] = atributos
            mapeadas.append(f)
    print(f"{len(mapeadas)} filas con los 5 campos mapeables "
          f"({len(mapeadas) / len(filas):.1%} del total).")

    print("\nDistribucion por categoria (de las mapeables):")
    for cat, n in Counter(f["_atributos"]["categoria"] for f in mapeadas).most_common():
        print(f"  {cat:<16} {n}")
    print("\nDistribucion por grupo_estilo (de las mapeables):")
    for g, n in Counter(f["_atributos"]["grupo_estilo"] for f in mapeadas).most_common():
        print(f"  {g:<16} {n}")

    rng.shuffle(mapeadas)
    total_pedido = args.train + args.val + args.test
    if total_pedido > len(mapeadas):
        print(f"\n(aviso) se pidieron {total_pedido} filas pero solo hay "
              f"{len(mapeadas)} mapeables -- se ajustan los splits proporcionalmente.")
        factor = len(mapeadas) / total_pedido
        args.train, args.val, args.test = (
            int(args.train * factor), int(args.val * factor), int(args.test * factor)
        )

    seleccion = muestreo_estratificado(mapeadas, args.train + args.val + args.test, rng)
    rng.shuffle(seleccion)

    splits = {
        "train": seleccion[: args.train],
        "val": seleccion[args.train: args.train + args.val],
        "test": seleccion[args.train + args.val: args.train + args.val + args.test],
    }

    data_dir = BASE_DIR / "data"
    imagenes_dir = data_dir / "imagenes_cache"
    imagenes_dir.mkdir(parents=True, exist_ok=True)

    for nombre_split, filas_split in splits.items():
        registros = []
        for f in filas_split:
            img_path = imagenes_dir / f"{f['id']}.jpg"
            if not img_path.exists():
                img_path.write_bytes(f["image"]["bytes"])

            target_text = json.dumps(f["_atributos"], ensure_ascii=False, separators=(",", ":"))
            registros.append({
                "id": f["id"],
                **f["_atributos"],
                "target_text": target_text,
                "articleType": f["articleType"],
                "productDisplayName": f["productDisplayName"],
                "imagen": f"imagenes_cache/{f['id']}.jpg",
            })

        ruta_jsonl = data_dir / f"{nombre_split}.jsonl"
        with open(ruta_jsonl, "w", encoding="utf-8") as fh:
            for r in registros:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\n{nombre_split}: {len(registros)} ejemplos -> {ruta_jsonl}")


if __name__ == "__main__":
    main()
