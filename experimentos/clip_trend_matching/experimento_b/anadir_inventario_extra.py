#!/usr/bin/env python3
"""
Experimento B, v2 -- amplía el inventario de prueba con prendas de la tendencia «alternativo-geek».

Por qué: en la v1 la tendencia «alternativo_geek» tuvo techo ≈ 0 con TODOS los métodos (5 prendas aprobadas de
42 propuestas) porque el catálogo de 1 207 miniaturas muestreaba ~40 prendas por tipo y casi ninguna llevaba
motivos de fandom. Víctor lo confirmó: «faltó contenido de geek» (su referencia de estilo es Orslok).

Qué hace: del mismo dataset de origen (Fashion Product Images Small, Kaggle; ~/.cache/fashion-product-images-small/,
ver poblar_muestras_dataset.py) selecciona por REGLA SOBRE METADATOS --nunca mirando a CLIP ni a los resultados--
las prendas de ropa de adulto cuyo nombre de producto indica un motivo de cómic/película/videojuego
(Batman, Marvel, Angry Birds, Mickey...). Muestrea 60 (todas las no-camiseta + camisetas con semilla fija) y las
guarda en inventario_extra/geek/ con su ATRIBUCIONES.txt. Mismo tamaño (60x80 px) y misma fuente que el resto del
inventario, así que no introduce un cambio de dominio.

«Lujo ostentoso» (referencia: Dani Alves) NO se puede ampliar de forma gratuita y limpia: este dataset es de grandes
superficies (tras descartar relojes, joyería y perfumes quedan ~4 prendas de diseñador reales, y las 65 de «marcas
premium» son sobre todo merchandising Puma-Ferrari) y Wikimedia Commons devuelve sobre todo escaneos, pasarelas y
fotos de personas. Se declara no evaluable con este inventario (hace falta un catálogo real).

    python3 anadir_inventario_extra.py
"""
import io
import random
import re
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "inventario_extra" / "geek"
SHARDS = [Path.home() / ".cache" / "fashion-product-images-small" / f"shard{i}.parquet" for i in (0, 1)]
N_TOTAL = 60
SEMILLA = 0

FANDOM = re.compile(
    r"marvel|avengers|superman|batman|spider-?man|iron ?man|hulk|captain america|\bthor\b|joker|star ?wars|"
    r"harry ?potter|minecraft|pokemon|naruto|anime|gamer|gaming|mario|transformers|angry birds|minion|hello kitty|"
    r"justice league|dc comics|superhero|simpsons|looney|tom and jerry|mickey", re.I)
NO_ADULTO = re.compile(r"kid|boys?\b|girls?\b|baby|infant|junior", re.I)


def main():
    if not all(s.exists() for s in SHARDS):
        raise SystemExit("ERROR: faltan los shards en ~/.cache/fashion-product-images-small/ "
                         "(se descargan con herramientas/poblar_muestras_dataset.py).")
    cols = ["id", "gender", "masterCategory", "articleType", "baseColour", "usage", "productDisplayName", "image"]
    candidatas = []
    for s in SHARDS:
        for r in pq.read_table(s, columns=cols).to_pylist():
            nombre = r["productDisplayName"] or ""
            if (r["masterCategory"] == "Apparel" and r["gender"] in ("Men", "Women", "Unisex")
                    and not NO_ADULTO.search(nombre) and FANDOM.search(nombre)):
                candidatas.append(r)
    print(f"Candidatas (ropa de adulto con motivo de fandom): {len(candidatas)}  {dict(Counter(r['articleType'] for r in candidatas))}")

    rng = random.Random(SEMILLA)
    otras = [r for r in candidatas if r["articleType"] != "Tshirts"]
    camisetas = [r for r in candidatas if r["articleType"] == "Tshirts"]
    rng.shuffle(camisetas)
    elegidas = otras + camisetas[: max(0, N_TOTAL - len(otras))]

    SALIDA.mkdir(parents=True, exist_ok=True)
    lineas = [
        "Dataset: Fashion Product Images (Small), Param Aggarwal (Kaggle)",
        "https://www.kaggle.com/datasets/paramaggarwal/fashion-product-images-small",
        "Aviso: no es una licencia libre explicita (origen e-commerce Myntra via Kaggle) -- uso apropiado para prototipo de "
        "investigacion academica, revisar antes de cualquier otro uso.",
        f"Seleccion: regla sobre metadatos (ropa de adulto con motivo de fandom en el nombre), semilla {SEMILLA}; "
        "no se uso CLIP ni ningun resultado del experimento para elegirlas.",
        "",
    ]
    for r in sorted(elegidas, key=lambda r: (r["articleType"], r["id"])):
        nombre = f"{r['articleType'].lower().replace(' ', '_')}_{r['id']}.jpg"
        Image.open(io.BytesIO(r["image"]["bytes"])).convert("RGB").save(SALIDA / nombre, quality=95)
        lineas.append(f"{nombre}: {r['productDisplayName']} (articleType={r['articleType']}, usage={r['usage']}, "
                      f"gender={r['gender']}, color={r['baseColour']}, id_dataset={r['id']})")
    (SALIDA / "ATRIBUCIONES.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"Guardadas {len(elegidas)} prendas en {SALIDA}  {dict(Counter(r['articleType'] for r in elegidas))}")


if __name__ == "__main__":
    main()
