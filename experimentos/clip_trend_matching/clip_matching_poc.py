#!/usr/bin/env python3
"""
POC de matching semantico prenda <-> tendencia (Estado_arte.md, seccion 7).

Implementa literalmente la formula de 7.2:

    score(SKU, tendencia) = score_semantico + beta * boost_estilo

donde score_semantico es la similitud coseno CLIP entre la imagen de la
prenda y el texto de la tendencia, y boost_estilo vale 1.0 si el
grupo_estilo de la prenda coincide con el grupo_estilo_detectado de la
tendencia (mismo vocabulario cerrado de 6 valores, seccion 3.4.1).

No usa fotos nuevas de ropa: las 5 imagenes de muestras/ son las que ya
se capturaron para el proyecto de Vision por Computador (rama
proyecto_VC de este mismo repo), reutilizadas aqui como stand-in de
fotos de catalogo mientras no hay acceso a los robots ni al setup real.
"""
import json
from pathlib import Path

import open_clip
import torch
from PIL import Image

BASE_DIR = Path(__file__).parent
MUESTRAS_DIR = BASE_DIR / "muestras"
METADATA_PATH = BASE_DIR / "muestras_metadata.json"
TENDENCIAS_PATH = BASE_DIR / "tendencias_ejemplo.json"

BETA_BOOST_ESTILO = 0.1  # mismo valor que Estado_arte.md, seccion 7.2


def cargar_modelo():
    print("Cargando CLIP (ViT-B-32, pesos openai)... (primera vez tarda por la descarga)")
    # "-quickgelu": los pesos originales de OpenAI se entrenaron con QuickGELU;
    # cargarlos con la variante GELU estandar (el default de open_clip) da un
    # mismatch de activacion silencioso que degrada la calidad del embedding.
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32-quickgelu", pretrained="openai"
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32-quickgelu")
    model.eval()
    return model, preprocess, tokenizer


def encodear_imagenes(model, preprocess, muestras):
    tensores = [preprocess(Image.open(m["ruta"]).convert("RGB")) for m in muestras]
    lote = torch.stack(tensores)
    with torch.no_grad():
        v = model.encode_image(lote)
        v = v / v.norm(dim=-1, keepdim=True)
    return v


def encodear_texto(model, tokenizer, texto):
    tokens = tokenizer([texto])
    with torch.no_grad():
        v = model.encode_text(tokens)
        v = v / v.norm(dim=-1, keepdim=True)
    return v[0]


def calcular_score(v_prenda, v_tendencia, grupo_prenda, grupos_tendencia):
    score_semantico = float((v_prenda @ v_tendencia).item())
    boost = BETA_BOOST_ESTILO if grupo_prenda in grupos_tendencia else 0.0
    return score_semantico, boost, score_semantico + boost


def main():
    muestras = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    tendencias = json.loads(TENDENCIAS_PATH.read_text(encoding="utf-8"))

    for m in muestras:
        m["ruta"] = MUESTRAS_DIR / m["archivo"]

    model, preprocess, tokenizer = cargar_modelo()
    v_prendas = encodear_imagenes(model, preprocess, muestras)

    for tendencia in tendencias:
        print(f"\n{'=' * 78}")
        print(f"TENDENCIA: {tendencia['descripcion'][:90]}...")
        print(f"grupo_estilo_detectado: {tendencia['grupo_estilo_detectado']}  "
              f"(intensidad={tendencia['intensidad']})")
        print("=" * 78)

        v_tendencia = encodear_texto(model, tokenizer, tendencia["descripcion"])

        resultados = []
        for muestra, v_prenda in zip(muestras, v_prendas):
            s_sem, boost, s_total = calcular_score(
                v_prenda, v_tendencia, muestra["grupo_estilo"],
                tendencia["grupo_estilo_detectado"],
            )
            resultados.append((muestra, s_sem, boost, s_total))

        resultados.sort(key=lambda r: r[3], reverse=True)

        for rank, (muestra, s_sem, boost, s_total) in enumerate(resultados, 1):
            marca = "*" if boost > 0 else " "
            print(
                f"{rank}. {marca} {muestra['nombre']:<38} "
                f"(grupo={muestra['grupo_estilo']:<13}) "
                f"score_semantico={s_sem:+.4f}  boost={boost:.2f}  total={s_total:+.4f}"
            )


if __name__ == "__main__":
    main()
