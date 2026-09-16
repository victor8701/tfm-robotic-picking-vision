#!/usr/bin/env python3
"""
Stage 2 del plan: numero "antes" documentado para Florence-2-base SIN
afinar, sobre el mismo test set que luego usara el modelo afinado
(Stage 4) -- mismo espiritu que ya se hizo con CLIP en
clip_trend_matching/herramientas/evaluar_precision_grupo_estilo.py
(32.8% de accuracy zero-shot).

Florence-2 sin afinar no conoce nuestro esquema JSON de 5 campos, asi
que se le pide una tarea nativa (<MORE_DETAILED_CAPTION>, texto libre
en ingles) y el texto se parsea con palabras clave contra el
vocabulario cerrado de cada campo -- analogo a como el POC de CLIP
compara contra un vocabulario cerrado via embeddings, aqui es
regex/substring sobre texto libre en vez de similitud coseno.

Uso:
    python3 baseline_zero_shot.py [--limite N] [--beams 1] [--max-tokens 100]
"""
import argparse
import collections
import json
import re
import time
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

BASE_DIR = Path(__file__).parent.parent

# palabra clave (ingles, la caption de Florence-2 sin afinar sale en ingles)
# -> valor de nuestro esquema. Se busca en orden y se queda con la primera
# que aparezca en el texto.
CATEGORIA_KEYWORDS = [
    (r"\b(dress|jumpsuit|romper)\b", "cuerpo_entero"),
    (r"\b(jacket|blazer|coat|parka)\b", "abrigo"),
    (r"\b(sandal|flip-flop|shoe|sneaker|boot|heel|footwear)\b", "calzado"),
    (r"\b(bag|backpack|belt|cap\b|scarf|tie\b|clutch)\b", "accesorio"),
    (r"\b(trouser|pant|jean|short|skirt|legging|capri)\b", "ropa_inferior"),
    (r"\b(shirt|t-shirt|tshirt|top\b|sweater|sweatshirt|blouse|tank)\b", "ropa_superior"),
]

COLOR_KEYWORDS = [
    (r"\bblack\b", "negro"), (r"\bwhite\b", "blanco"),
    (r"\bnavy\b", "navy"), (r"\bblue\b", "azul"),
    (r"\b(grey|gray)\b", "gris"), (r"\bred\b", "rojo"),
    (r"\bgreen\b", "verde"), (r"\bpink\b", "rosa"),
    (r"\b(purple|lavender)\b", "lavanda"), (r"\bsilver\b", "plateado"),
    (r"\b(yellow|mustard)\b", "amarillo"),
    (r"\b(beige|cream|tan|khaki)\b", "beige"),
    (r"\bbrown\b", "camel"),
    (r"\bgold\b", "dorado"), (r"\b(maroon|burgundy)\b", "burdeos"),
    (r"\borange\b", "naranja"), (r"\b(magenta|fuchsia)\b", "fucsia"),
]

GRUPO_ESTILO_KEYWORDS = [
    (r"\b(sneaker|hoodie|cap\b|cargo|bomber|streetwear|oversized)\b", "streetwear"),
    (r"\b(sandal|flip-flop|shorts|summer|beach)\b", "playa_resort"),
    (r"\b(suit|blazer|formal|tie\b|dress shirt)\b", "de_vestir"),
    (r"\b(sport|athletic|track|running|gym)\b", "deportivo"),
    (r"\b(sequin|party|evening|gown|glitter)\b", "fiesta_noche"),
]

GENERO_KEYWORDS = [
    (r"\b(man|men|male)\b", "masculino"),
    (r"\b(woman|women|female)\b", "femenino"),
]

TEMPORADA_KEYWORDS = [
    (r"\b(sandal|flip-flop|shorts|tank top|summer)\b", "primavera_verano"),
    (r"\b(sweater|jacket|boots|coat|sweatshirt)\b", "otono_invierno"),
]


def primera_coincidencia(texto, tabla, valor_por_defecto):
    texto = texto.lower()
    for patron, valor in tabla:
        if re.search(patron, texto):
            return valor
    return valor_por_defecto


def parsear_caption(caption):
    return {
        "categoria": primera_coincidencia(caption, CATEGORIA_KEYWORDS, "ropa_superior"),
        "color_primario": primera_coincidencia(caption, COLOR_KEYWORDS, "negro"),
        "grupo_estilo": primera_coincidencia(caption, GRUPO_ESTILO_KEYWORDS, "casual"),
        "genero": primera_coincidencia(caption, GENERO_KEYWORDS, "neutro"),
        "temporada": primera_coincidencia(caption, TEMPORADA_KEYWORDS, "primavera_verano"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=None,
                         help="Evaluar solo las primeras N filas de test.jsonl (por defecto: todas).")
    parser.add_argument("--beams", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=100)
    parser.add_argument("--split", default="test", choices=["val", "test"])
    args = parser.parse_args()

    print("Cargando Florence-2-base (sin LoRA, tal cual)...")
    model = AutoModelForCausalLM.from_pretrained(
        "microsoft/Florence-2-base", trust_remote_code=True, torch_dtype=torch.float32
    )
    processor = AutoProcessor.from_pretrained("microsoft/Florence-2-base", trust_remote_code=True)
    model.eval()

    filas = [json.loads(l) for l in open(BASE_DIR / "data" / f"{args.split}.jsonl", encoding="utf-8")]
    if args.limite:
        filas = filas[: args.limite]
    print(f"Evaluando {len(filas)} imagenes de {args.split}.jsonl...")

    campos = ["categoria", "color_primario", "grupo_estilo", "genero", "temporada"]
    aciertos = collections.Counter()
    confusion_grupo = collections.Counter()
    inicio = time.time()

    for i, fila in enumerate(filas, 1):
        img_path = BASE_DIR / "data" / fila["imagen"]
        imagen = Image.open(img_path).convert("RGB")

        prompt = "<MORE_DETAILED_CAPTION>"
        inputs = processor(text=prompt, images=imagen, return_tensors="pt")
        with torch.no_grad():
            generados = model.generate(
                input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"],
                max_new_tokens=args.max_tokens, num_beams=args.beams,
            )
        texto = processor.batch_decode(generados, skip_special_tokens=False)[0]
        parsed = processor.post_process_generation(texto, task=prompt, image_size=(imagen.width, imagen.height))
        caption = parsed[prompt]

        prediccion = parsear_caption(caption)
        for campo in campos:
            if prediccion[campo] == fila[campo]:
                aciertos[campo] += 1
        confusion_grupo[(fila["grupo_estilo"], prediccion["grupo_estilo"])] += 1

        if i % 25 == 0:
            transcurrido = time.time() - inicio
            print(f"  {i}/{len(filas)}  ({transcurrido / i:.1f}s/imagen, "
                  f"ETA {(len(filas) - i) * transcurrido / i / 60:.1f} min)")

    n = len(filas)
    print(f"\n{'=' * 78}")
    print(f"BASELINE ZERO-SHOT Florence-2-base -- {n} imagenes de {args.split}.jsonl")
    print("=" * 78)
    for campo in campos:
        print(f"  {campo:<16} {aciertos[campo]:>4}/{n} = {aciertos[campo] / n:.1%}")

    etiquetas = ["casual", "streetwear", "de_vestir", "fiesta_noche", "deportivo", "playa_resort"]
    print(f"\nMatriz de confusion grupo_estilo (filas=esperado, columnas=predicho):")
    cabecera = " " * 16 + "".join(f"{e[:11]:>12}" for e in etiquetas)
    print(cabecera)
    for esperado in etiquetas:
        fila_txt = f"{esperado:<16}"
        for predicho in etiquetas:
            fila_txt += f"{confusion_grupo[(esperado, predicho)]:>12}"
        print(fila_txt)


if __name__ == "__main__":
    main()
