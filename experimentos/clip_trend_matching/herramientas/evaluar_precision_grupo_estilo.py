#!/usr/bin/env python3
"""
Evalua con numeros si la deteccion automatica de grupo_estilo (CLIP
zero-shot, la misma logica que usa clip_matching_poc.py) funciona sobre
un volumen grande de imagenes reales -- no solo "parece que funciona" a
ojo con un puñado.

Usa como terreno de prueba las 6 carpetas de muestras (casual/,
streetwear/, de_vestir/, fiesta_noche/, deportivo/, playa_resort/): el
nombre de la carpeta de origen de cada imagen se usa como "etiqueta
esperada". Ojo: esa etiqueta viene del filtro articleType/usage con el
que se descargo cada imagen (ver poblar_muestras_dataset.py), NO es una
anotacion humana verificada foto a foto -- es la mejor aproximacion
barata que hay sin revisar 1000+ imagenes a mano, y puede tener algo de
ruido propio (ver el aviso del README sobre articleType inconsistente
con productDisplayName).

Para cada imagen se compara esa etiqueta esperada contra el grupo_estilo
que CLIP asigna por zero-shot, y se calcula:
  - accuracy por categoria (cuantas de esa carpeta CLIP acierta)
  - accuracy global
  - matriz de confusion completa (a que otro grupo se van los fallos)

Uso:
    python3 evaluar_precision_grupo_estilo.py [--muestras-por-categoria N]
"""
import argparse
import collections
import json
from pathlib import Path

import open_clip
import torch
from PIL import Image

BASE_DIR = Path(__file__).parent.parent
EXTENSIONES_VALIDAS = {".jpg", ".jpeg", ".png", ".webp"}
TAMANO_LOTE = 32

GRUPOS_ESTILO = {
    "casual": "ropa casual de diario",
    "streetwear": "ropa de estilo urbano, streetwear",
    "de_vestir": "ropa elegante y formal, de vestir",
    "fiesta_noche": "ropa de fiesta o para salir de noche",
    "deportivo": "ropa deportiva",
    "playa_resort": "ropa veraniega de playa o resort",
}

NOMBRE_MOSTRAR = {
    "casual": "Casual", "streetwear": "Streetwear", "de_vestir": "De vestir",
    "fiesta_noche": "Fiesta/Noche", "deportivo": "Deportivo", "playa_resort": "Playa/Resort",
}


def cargar_modelo():
    print("Cargando CLIP (ViT-B-32, pesos openai)...")
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32-quickgelu", pretrained="openai"
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32-quickgelu")
    model.eval()
    return model, preprocess, tokenizer


def encodear_carpeta(carpeta, model, preprocess, limite):
    """Encodea todas las imagenes validas de una carpeta, en lotes.
    Devuelve (rutas_ok, tensor de embeddings normalizados)."""
    rutas = sorted(
        p for p in carpeta.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONES_VALIDAS
    )
    if limite:
        rutas = rutas[:limite]

    rutas_ok = []
    embeddings = []
    for inicio in range(0, len(rutas), TAMANO_LOTE):
        lote_rutas = rutas[inicio: inicio + TAMANO_LOTE]
        tensores = []
        for r in lote_rutas:
            try:
                tensores.append(preprocess(Image.open(r).convert("RGB")))
                rutas_ok.append(r)
            except Exception as e:
                print(f"  (aviso) no se pudo leer '{r.name}': {e}")

        if not tensores:
            continue

        with torch.no_grad():
            v_imgs = model.encode_image(torch.stack(tensores))
            v_imgs = v_imgs / v_imgs.norm(dim=-1, keepdim=True)
            embeddings.append(v_imgs)

    if not embeddings:
        return [], torch.empty(0)
    return rutas_ok, torch.cat(embeddings, dim=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--muestras-por-categoria", type=int, default=None,
        help="Limitar cuantas imagenes evaluar por carpeta (por defecto: todas).",
    )
    args = parser.parse_args()

    model, preprocess, tokenizer = cargar_modelo()

    etiquetas = list(GRUPOS_ESTILO.keys())
    tokens_grupos = tokenizer(list(GRUPOS_ESTILO.values()))
    with torch.no_grad():
        v_grupos = model.encode_text(tokens_grupos)
        v_grupos = v_grupos / v_grupos.norm(dim=-1, keepdim=True)

    confusion = collections.Counter()  # (esperado, predicho) -> cuenta
    total_por_categoria = collections.Counter()
    aciertos_por_categoria = collections.Counter()
    embeddings_por_categoria = {}  # categoria -> tensor de embeddings (para el analisis 2)

    print("Encodeando imagenes y clasificando por zero-shot...")
    for categoria in etiquetas:
        carpeta = BASE_DIR / categoria
        if not carpeta.is_dir():
            continue

        rutas_ok, v_imgs = encodear_carpeta(carpeta, model, preprocess, args.muestras_por_categoria)
        if not rutas_ok:
            continue
        embeddings_por_categoria[categoria] = v_imgs

        similitudes = v_imgs @ v_grupos.T
        predicciones = [etiquetas[i] for i in similitudes.argmax(dim=1).tolist()]

        print(f"  {categoria}/: {len(predicciones)} imagenes evaluadas")
        for predicho in predicciones:
            confusion[(categoria, predicho)] += 1
            total_por_categoria[categoria] += 1
            if predicho == categoria:
                aciertos_por_categoria[categoria] += 1

    print(f"\n{'=' * 78}")
    print("ANALISIS 1: accuracy zero-shot de grupo_estilo por categoria")
    print("(clasificacion 1-de-6 con las frases de GRUPOS_ESTILO -- la comodidad")
    print(" automatica que usa clip_matching_poc.py, NO el mecanismo real del ERP)")
    print("=" * 78)
    total_global = sum(total_por_categoria.values())
    aciertos_global = sum(aciertos_por_categoria.values())
    for categoria in etiquetas:
        n = total_por_categoria[categoria]
        if n == 0:
            continue
        aciertos = aciertos_por_categoria[categoria]
        print(f"  {NOMBRE_MOSTRAR[categoria]:<14} {aciertos:>4}/{n:<4} = {aciertos / n:.1%}")
    if total_global:
        print(f"  {'TOTAL':<14} {aciertos_global:>4}/{total_global:<4} = {aciertos_global / total_global:.1%}")

    print(f"\n{'=' * 78}")
    print("MATRIZ DE CONFUSION (filas = carpeta de origen, columnas = prediccion CLIP)")
    print("=" * 78)
    cabecera = " " * 16 + "".join(f"{NOMBRE_MOSTRAR[e][:10]:>12}" for e in etiquetas)
    print(cabecera)
    for esperado in etiquetas:
        if total_por_categoria[esperado] == 0:
            continue
        fila = f"{NOMBRE_MOSTRAR[esperado]:<16}"
        for predicho in etiquetas:
            fila += f"{confusion[(esperado, predicho)]:>12}"
        print(fila)

    # ---- Analisis 2: el mecanismo real de S7.2, sin pasar por la ----
    # ---- clasificacion 1-de-6 (que el analisis 1 acaba de mostrar ----
    # ---- que es fragil). Aqui NO se le pide a CLIP que elija una  ----
    # ---- categoria; se mide directamente score_semantico(imagen,  ----
    # ---- texto_tendencia) y se compara el promedio por carpeta.   ----
    tendencias_path = BASE_DIR / "tendencias_ejemplo.json"
    if not tendencias_path.exists() or not embeddings_por_categoria:
        return
    tendencias = json.loads(tendencias_path.read_text(encoding="utf-8"))

    print(f"\n{'=' * 78}")
    print("ANALISIS 2: score_semantico medio por carpeta (sin clasificacion 1-de-6)")
    print("Es el mecanismo real de S7.2 -- CLIP no elige categoria, solo se mide")
    print("cuanto se parece cada imagen al TEXTO de la tendencia, directamente.")
    print("=" * 78)

    for tendencia in tendencias:
        v_tendencia = None
        with torch.no_grad():
            tokens = tokenizer([tendencia["descripcion"]])
            v_tendencia = model.encode_text(tokens)
            v_tendencia = (v_tendencia / v_tendencia.norm(dim=-1, keepdim=True))[0]

        print(f"\nTENDENCIA: {tendencia['descripcion'][:80]}...")
        print(f"grupo_estilo_detectado: {tendencia['grupo_estilo_detectado']}")

        medias = []
        for categoria, v_imgs in embeddings_por_categoria.items():
            media = float((v_imgs @ v_tendencia).mean().item())
            medias.append((categoria, media))

        medias.sort(key=lambda x: x[1], reverse=True)
        grupos_esperados = set(tendencia["grupo_estilo_detectado"])
        # el "esperado" en este script usa claves en minuscula_con_guion,
        # los del JSON de tendencias usan el nombre bonito -- se comparan
        # via NOMBRE_MOSTRAR
        for rank, (categoria, media) in enumerate(medias, 1):
            marca = "*" if NOMBRE_MOSTRAR[categoria] in grupos_esperados else " "
            print(f"  {rank}. {marca} {NOMBRE_MOSTRAR[categoria]:<14} media_score_semantico={media:+.4f}")


if __name__ == "__main__":
    main()
