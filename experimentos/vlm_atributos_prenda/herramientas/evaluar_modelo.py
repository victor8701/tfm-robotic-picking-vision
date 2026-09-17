#!/usr/bin/env python3
"""
Stage 4 del plan: compara Florence-2-base zero-shot (Stage 2) contra el
adapter LoRA afinado (Stage 3, entrenado en Colab y descargado a
../modelos/florence2_base_lora_v1/) sobre data/test.jsonl -- accuracy
por campo, F1 por clase en color_primario y grupo_estilo, tasa de JSON
valido, latencia.

Ademas re-evalua grupo_estilo sobre las 1207 imagenes de
experimentos/clip_trend_matching/{casual,streetwear,...}/ para poder
comparar el modelo afinado directamente contra el 32.8% de CLIP
zero-shot ya documentado en evaluar_precision_grupo_estilo.py -- mismas
imagenes, comparacion limpia.

Uso:
    python3 evaluar_modelo.py [--limite N] [--sin-1207]
    python3 evaluar_modelo.py --adapter ../modelos/otro_experimento
"""
import argparse
import collections
import json
import time
from pathlib import Path

import torch
from PIL import Image
from peft import PeftModel
from torch.amp import autocast
from transformers import AutoModelForCausalLM, AutoProcessor

BASE_DIR = Path(__file__).parent.parent
CLIP_POC_DIR = BASE_DIR.parent / "clip_trend_matching"
MODELO_BASE = "microsoft/Florence-2-base"
TASK_PROMPT = "<ATRIBUTOS_PRENDA>"
CAMPOS = ["categoria", "color_primario", "grupo_estilo", "genero", "temporada"]
EXTENSIONES_VALIDAS = {".jpg", ".jpeg", ".png", ".webp"}

GRUPOS_ESTILO_1207 = ["casual", "streetwear", "de_vestir", "fiesta_noche", "deportivo", "playa_resort"]


def parsear_json_seguro(texto):
    import re
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def generar(model, processor, imagen, device, usar_amp, max_new_tokens=96):
    inputs = processor(text=TASK_PROMPT, images=imagen, return_tensors="pt").to(device)
    # Precision mixta estandar (autocast), no cargar el modelo directamente en
    # bfloat16/fp16: en la GPU T4 de Colab, varias convoluciones depthwise del
    # vision_tower de Florence-2 no tienen kernel bfloat16 disponible (bug real
    # encontrado al entrenar, ver entrenar_lora.py). Los pesos se quedan en
    # fp32 y autocast castea el computo internamente donde es seguro.
    with torch.no_grad(), autocast(device_type="cuda", dtype=torch.float16, enabled=usar_amp):
        generados = model.generate(
            input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"],
            max_new_tokens=max_new_tokens, num_beams=1,
        )
    return processor.batch_decode(generados, skip_special_tokens=True)[0].strip()


def evaluar_test_set(model, processor, device, usar_amp, filas, etiqueta_modelo):
    aciertos = collections.Counter()
    confusion_grupo = collections.Counter()
    confusion_color = collections.Counter()
    json_validos = 0
    latencias = []

    for i, fila in enumerate(filas, 1):
        imagen = Image.open(BASE_DIR / "data" / fila["imagen"]).convert("RGB")
        t0 = time.time()
        texto = generar(model, processor, imagen, device, usar_amp)
        latencias.append(time.time() - t0)

        prediccion = parsear_json_seguro(texto)
        if prediccion is not None and all(c in prediccion for c in CAMPOS):
            json_validos += 1
            for campo in CAMPOS:
                if prediccion.get(campo) == fila[campo]:
                    aciertos[campo] += 1
            confusion_grupo[(fila["grupo_estilo"], prediccion.get("grupo_estilo"))] += 1
            confusion_color[(fila["color_primario"], prediccion.get("color_primario"))] += 1
        else:
            confusion_grupo[(fila["grupo_estilo"], "_json_invalido")] += 1

        if i % 50 == 0:
            print(f"  [{etiqueta_modelo}] {i}/{len(filas)}")

    n = len(filas)
    print(f"\n{'=' * 78}\n{etiqueta_modelo} -- {n} imagenes\n{'=' * 78}")
    for campo in CAMPOS:
        print(f"  {campo:<16} {aciertos[campo]:>4}/{n} = {aciertos[campo] / n:.1%}")
    print(f"  {'JSON valido':<16} {json_validos:>4}/{n} = {json_validos / n:.1%}")
    print(f"  {'latencia media':<16} {sum(latencias) / len(latencias):.2f}s/imagen (CPU)")

    return {"aciertos": aciertos, "n": n, "json_validos": json_validos,
            "confusion_grupo": confusion_grupo, "confusion_color": confusion_color}


def f1_por_clase(confusion, clases, etiqueta_campo):
    print(f"\nF1 por clase -- {etiqueta_campo}:")
    for clase in clases:
        vp = confusion[(clase, clase)]
        fn = sum(v for (esp, pred), v in confusion.items() if esp == clase and pred != clase)
        fp = sum(v for (esp, pred), v in confusion.items() if pred == clase and esp != clase)
        precision = vp / (vp + fp) if (vp + fp) > 0 else 0.0
        recall = vp / (vp + fn) if (vp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        print(f"  {clase:<14} precision={precision:.2f}  recall={recall:.2f}  F1={f1:.2f}")


def evaluar_1207_imagenes(model, processor, device, usar_amp, etiqueta_modelo, limite_por_carpeta):
    if not CLIP_POC_DIR.is_dir():
        print(f"\n(aviso) no se encuentra {CLIP_POC_DIR}, se omite la comparacion con CLIP.")
        return

    print(f"\n{'=' * 78}\n{etiqueta_modelo} sobre las 1207 imagenes de clip_trend_matching/ "
          f"(comparacion directa con el 32.8% de CLIP)\n{'=' * 78}")

    aciertos = 0
    total = 0
    for carpeta_nombre in GRUPOS_ESTILO_1207:
        carpeta = CLIP_POC_DIR / carpeta_nombre
        if not carpeta.is_dir():
            continue
        rutas = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in EXTENSIONES_VALIDAS)
        if limite_por_carpeta:
            rutas = rutas[:limite_por_carpeta]

        aciertos_carpeta = 0
        for ruta in rutas:
            imagen = Image.open(ruta).convert("RGB")
            texto = generar(model, processor, imagen, device, usar_amp)
            prediccion = parsear_json_seguro(texto)
            grupo_predicho = prediccion.get("grupo_estilo") if prediccion else None
            if grupo_predicho == carpeta_nombre:
                aciertos_carpeta += 1
        aciertos += aciertos_carpeta
        total += len(rutas)
        print(f"  {carpeta_nombre:<14} {aciertos_carpeta:>4}/{len(rutas)} = "
              f"{aciertos_carpeta / len(rutas) if rutas else 0:.1%}")

    print(f"  {'TOTAL':<14} {aciertos:>4}/{total} = {aciertos / total:.1%}"
          f"  (referencia: CLIP zero-shot = 32.8%)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=None,
                         help="Limitar filas de test.jsonl a evaluar (por defecto: todas, 500).")
    parser.add_argument("--adapter", default=str(BASE_DIR / "modelos" / "florence2_base_lora_v1"))
    parser.add_argument("--sin-1207", action="store_true",
                         help="Saltar la comparacion sobre las 1207 imagenes de clip_trend_matching/.")
    parser.add_argument("--limite-1207", type=int, default=None,
                         help="Limitar imagenes por carpeta en la comparacion de las 1207 (por defecto: todas).")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    usar_amp = device == "cuda"
    filas_test = [json.loads(l) for l in open(BASE_DIR / "data" / "test.jsonl", encoding="utf-8")]
    if args.limite:
        filas_test = filas_test[: args.limite]

    print("Cargando Florence-2-base (zero-shot)...")
    base_zeroshot = AutoModelForCausalLM.from_pretrained(MODELO_BASE, trust_remote_code=True, torch_dtype=torch.float32).to(device)
    processor = AutoProcessor.from_pretrained(MODELO_BASE, trust_remote_code=True)
    resultado_zeroshot = evaluar_test_set(base_zeroshot, processor, device, usar_amp, filas_test, "ZERO-SHOT (sin afinar)")
    f1_por_clase(resultado_zeroshot["confusion_color"],
                 sorted({f["color_primario"] for f in filas_test}), "color_primario (zero-shot)")
    f1_por_clase(resultado_zeroshot["confusion_grupo"], GRUPOS_ESTILO_1207, "grupo_estilo (zero-shot)")
    del base_zeroshot

    adapter_path = Path(args.adapter)
    if not adapter_path.exists():
        print(f"\n(aviso) no existe {adapter_path} -- todavia no se ha bajado el adapter "
              f"entrenado en Colab (Stage 3). Solo se ha evaluado el baseline zero-shot.")
        return

    print(f"\nCargando adapter afinado desde {adapter_path}...")
    base_afinado = AutoModelForCausalLM.from_pretrained(MODELO_BASE, trust_remote_code=True, torch_dtype=torch.float32)
    modelo_afinado = PeftModel.from_pretrained(base_afinado, adapter_path).to(device)
    resultado_afinado = evaluar_test_set(modelo_afinado, processor, device, usar_amp, filas_test, "AFINADO (LoRA)")
    f1_por_clase(resultado_afinado["confusion_color"],
                 sorted({f["color_primario"] for f in filas_test}), "color_primario (afinado)")
    f1_por_clase(resultado_afinado["confusion_grupo"], GRUPOS_ESTILO_1207, "grupo_estilo (afinado)")

    print(f"\n{'=' * 78}\nRESUMEN zero-shot vs afinado\n{'=' * 78}")
    for campo in CAMPOS:
        antes = resultado_zeroshot["aciertos"][campo] / resultado_zeroshot["n"]
        despues = resultado_afinado["aciertos"][campo] / resultado_afinado["n"]
        print(f"  {campo:<16} {antes:.1%} -> {despues:.1%}  ({'+' if despues >= antes else ''}{(despues - antes) * 100:.1f} pp)")

    if not args.sin_1207:
        evaluar_1207_imagenes(modelo_afinado, processor, device, usar_amp, "AFINADO (LoRA)", args.limite_1207)


if __name__ == "__main__":
    main()
