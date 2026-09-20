#!/usr/bin/env python3
"""
Genera las predicciones del modelo afinado (adapter LoRA) para un lote de
imagenes y las guarda en un JSON {id: {prediccion, texto_crudo}}.

Pensado para alimentar la app de revision humana ("Ficha de Prenda"): asi
se puede ver, ficha a ficha, lo que predice el modelo junto a la etiqueta
de Kaggle y a la correccion humana, y calcular acuerdo modelo-vs-humano.

La carpeta puede ser de dos formas:
  - con manifest.json (lista de objetos con "id" y "archivo") e imagenes/,
    el mismo formato que usa la app de revision, o
  - una carpeta plana de imagenes (.jpg/.jpeg/.png/.webp): el id de cada
    una es el nombre del fichero sin extension.

Uso:
    python3 predecir_lote.py --carpeta ~/app_revision_prendas --salida predicciones.json
    python3 predecir_lote.py --carpeta ../data/fotos_calle --salida calle.json
"""
import argparse
import json
import re
import time
from pathlib import Path

import torch
from PIL import Image
from peft import PeftModel
from torch.amp import autocast
from transformers import AutoModelForCausalLM, AutoProcessor

BASE_DIR = Path(__file__).parent.parent
MODELO_BASE = "microsoft/Florence-2-base"
TASK_PROMPT = "<ATRIBUTOS_PRENDA>"


def parsear_json_seguro(texto):
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--carpeta", required=True,
                         help="Carpeta con manifest.json e imagenes/ (formato de la app de revision).")
    parser.add_argument("--salida", required=True, help="JSON de salida con las predicciones.")
    parser.add_argument("--adapter", default=str(BASE_DIR / "modelos" / "florence2_base_lora_v1"))
    args = parser.parse_args()

    carpeta = Path(args.carpeta).expanduser()
    if (carpeta / "manifest.json").exists():
        manifest = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
        ruta_de = lambda item: carpeta / "imagenes" / item["archivo"]
    else:
        extensiones = {".jpg", ".jpeg", ".png", ".webp"}
        planas = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in extensiones)
        manifest = [{"id": p.stem, "archivo": p.name} for p in planas]
        ruta_de = lambda item: carpeta / item["archivo"]

    device = "cuda" if torch.cuda.is_available() else "cpu"
    usar_amp = device == "cuda"
    print(f"Cargando modelo base + adapter ({device})...")
    base = AutoModelForCausalLM.from_pretrained(MODELO_BASE, trust_remote_code=True, torch_dtype=torch.float32)
    modelo = PeftModel.from_pretrained(base, args.adapter).to(device)
    modelo.eval()
    processor = AutoProcessor.from_pretrained(MODELO_BASE, trust_remote_code=True)

    resultados = {}
    inicio = time.time()
    for i, item in enumerate(manifest, 1):
        imagen = Image.open(ruta_de(item)).convert("RGB")
        inputs = processor(text=TASK_PROMPT, images=imagen, return_tensors="pt").to(device)
        with torch.no_grad(), autocast(device_type="cuda", dtype=torch.float16, enabled=usar_amp):
            generados = modelo.generate(
                input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"],
                max_new_tokens=96, num_beams=1,
            )
        texto = processor.batch_decode(generados, skip_special_tokens=True)[0].strip()
        resultados[str(item["id"])] = {"prediccion": parsear_json_seguro(texto), "texto_crudo": texto}
        if i % 10 == 0:
            print(f"  {i}/{len(manifest)}  ({(time.time() - inicio) / i:.1f}s/imagen)")

    Path(args.salida).write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Predicciones guardadas en {args.salida}")


if __name__ == "__main__":
    main()
