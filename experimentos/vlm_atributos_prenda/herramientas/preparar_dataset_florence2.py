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

Reglas v4 (2026-09-20, mas tarde): refuerzo de las filas de `color_primario` mas raras
(fucsia/dorado/naranja/plateado/burdeos -- F1 0.00 o muy bajo en v1/v2/v3, no por culpa del
muestreo sino porque el dataset entero tiene pocas: fucsia solo 50 filas mapeables de 24215).
Se reservan aparte (ver COLORES_A_REFORZAR/separar_refuerzo abajo) antes del muestreo por
categoria, que no mira el color y las dejaba a la suerte. Nada mas cambia respecto a v3.

Reglas v5 (2026-09-21): mismo mecanismo de refuerzo de v4, generalizado (separar_refuerzo ya
no es especifico de color) y aplicado tambien a `articleType` -- ver TIPOS_A_REFORZAR abajo
para que tipos y por que (cola larga real: S6.3 de la memoria mide que el acierto de estilo
cae al 3% en tipos con <10 ejemplos en train y al 59% con 10-49). Ademas, arregla un bug real:
`Tracksuits` y `Swimwear` aparecian en FILTROS_GRUPO_ESTILO pero no en
CATEGORIA_POR_ARTICLETYPE, asi que mapear_fila los descartaba siempre (categoria=None) --
0 filas de esos dos tipos en todas las versiones v1-v4, pase lo que pasara con el muestreo.
Nada mas cambia respecto a v4.

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
    # Tracksuits y Swimwear: bug real encontrado al sobremuestrear tipos de prenda (v5, ver
    # aviso mas abajo) -- FILTROS_GRUPO_ESTILO ya los resuelve a "deportivo"/"playa_resort",
    # pero al faltar aqui mapear_fila devolvia categoria=None y la fila se descartaba SIEMPRE,
    # nunca llegaban a "mapeadas" pasara lo que pasara con el color o el muestreo. Mismo
    # criterio que Jumpsuit/Dresses (prenda de una pieza que cubre torso+piernas).
    "Tracksuits": "cuerpo_entero", "Swimwear": "cuerpo_entero",
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



# Colores con F1 0.00 (fucsia, dorado, naranja, plateado) o muy bajo (burdeos) en las tres
# versiones del adapter (v1/v2/v3 -- ver memoria S11.2/S11.5): muy pocos ejemplos en el pool
# ENTERO, no solo en la muestra de 4550 -- fucsia solo tiene 50 filas mapeables en las 44072
# del dataset. El muestreo por categoria de mas abajo no mira el color, asi que estas filas se
# reparten aparte primero (todas las que haya de fucsia, hasta 200 del resto) para asegurar que
# caen en train/val/test en vez de dejarlo a la suerte de que sean tan pocas en general.
COLORES_A_REFORZAR = {"fucsia": 200, "dorado": 200, "naranja": 200, "plateado": 200, "burdeos": 200}


# Tipos de prenda de la cola larga (v5, 2026-09-21). El estilo cae al 3% de acierto en tipos
# con <10 ejemplos en train y al 59% con 10-49, medido de verdad en imagenes no vistas
# (evaluar_solape_1207.py / memoria S6.3) -- el muestreo estratificado de mas abajo solo mira
# `categoria` (6 valores), no `articleType` (30), asi que dentro de una categoria grande
# (ropa_superior: 11222 filas en 6 tipos; calzado: 7847 en 8 tipos) un tipo raro se queda casi
# sin cupo por pura proporcion aunque el pool tenga de sobra. Elegidos calculando cuantas filas
# de cada tipo caian realmente en train+val+test con el muestreo de v4 (ver commit): los que
# quedaban claramente por debajo de 50 en train (bucket "10-49" o peor de la tabla de S6.3) --
# Waistcoat (0 seleccionadas de 12 en el pool), Sports Sandals (5 de 65), Sweatshirts (23 de
# 278), Skirts (26 de 57), Sweaters (38 de 277), Capris (42 de 114). Tope 150 (deja a los que sí
# tienen pool para ello en el rango "50-199" de S6.3, donde el acierto ya sube a 76%); los que
# tienen menos de 150 en TODO el pool (Waistcoat/Sports Sandals/Skirts/Capris) cogen el 100%
# igual que fucsia con los colores. Tracksuits/Swimwear NO estan aqui a proposito: su problema
# no era de muestreo sino que faltaban en CATEGORIA_POR_ARTICLETYPE (ver el aviso ahi arriba);
# una vez mapeables se corrigen solas porque su categoria (cuerpo_entero) es pequena y el
# muestreo ya coge el 100% de lo que hay (comprobado, ver commit).
TIPOS_A_REFORZAR = {
    "Waistcoat": 150, "Sports Sandals": 150, "Sweatshirts": 150,
    "Skirts": 150, "Sweaters": 150, "Capris": 150,
}


def separar_refuerzo(mapeadas, clave_fn, objetivo, rng):
    """Generaliza el refuerzo de v4 (que era solo de color) a cualquier campo: aparta hasta
    objetivo[clave] filas de cada valor de clave_fn(fila) (todas las que haya si hay menos) y
    las devuelve en un solo grupo -- se combinan luego con el resto y todo junto se reparte en
    train/val/test con el mismo shuffle+slice de siempre (main()), asi que caen repartidas
    proporcionalmente sin necesidad de fijar un cupo por split a mano."""
    por_clave = defaultdict(list)
    resto = []
    for f in mapeadas:
        clave = clave_fn(f)
        (por_clave[clave] if clave in objetivo else resto).append(f)
    refuerzo = []
    for clave, filas in por_clave.items():
        rng.shuffle(filas)
        tope = objetivo[clave]
        refuerzo.extend(filas[:tope])
        resto.extend(filas[tope:])  # lo que sobra de cada clave vuelve al pool general
    return refuerzo, resto


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

    refuerzo_color, resto = separar_refuerzo(
        mapeadas, lambda f: f["_atributos"]["color_primario"], COLORES_A_REFORZAR, rng)
    print(f"\nRefuerzo de colores raros ({sum(COLORES_A_REFORZAR.values())} tope, {len(refuerzo_color)} conseguidas):")
    for color, tope in COLORES_A_REFORZAR.items():
        n = sum(1 for f in refuerzo_color if f["_atributos"]["color_primario"] == color)
        print(f"  {color:<10} {n}/{tope}" + ("  (todo lo que hay)" if n < tope else ""))

    refuerzo_tipo, resto = separar_refuerzo(resto, lambda f: f["articleType"], TIPOS_A_REFORZAR, rng)
    print(f"\nRefuerzo de tipos de prenda raros ({sum(TIPOS_A_REFORZAR.values())} tope, {len(refuerzo_tipo)} conseguidas):")
    for tipo, tope in TIPOS_A_REFORZAR.items():
        n = sum(1 for f in refuerzo_tipo if f["articleType"] == tipo)
        print(f"  {tipo:<16} {n}/{tope}" + ("  (todo lo que hay)" if n < tope else ""))

    refuerzo = refuerzo_color + refuerzo_tipo
    seleccion_categoria = muestreo_estratificado(resto, args.train + args.val + args.test - len(refuerzo), rng)
    seleccion = refuerzo + seleccion_categoria
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
