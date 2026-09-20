#!/usr/bin/env python3
"""
Stage 3 del plan: fine-tuning LoRA de Florence-2-base sobre el esquema
de 5 campos (ver esquema_atributos.md). Pensado para correr en Google
Colab (GPU T4 gratuita) -- ver notebook_colab_entrenamiento.ipynb, que
es un wrapper fino sobre este mismo script. Tambien sirve como "prueba
de humo" en CPU local con --limite-train pequeno, solo para comprobar
que el bucle no rompe antes de gastar horas de Colab en el run real.

Se introduce una tarea nueva para Florence-2, "<ATRIBUTOS_PRENDA>",
como texto literal (no hace falta registrarla como special token --
asi es como el propio Florence-2 aprendio sus tareas nativas como
"<OD>" durante su preentrenamiento, y como lo hacen los fine-tunes de
la comunidad para tareas nuevas). El objetivo es el JSON compacto de
5 campos ya serializado en target_text por preparar_dataset_florence2.py.

Hiperparametros de partida (paper "Fashion Florence", arXiv:2605.09827,
adaptados a Florence-2-base y a un JSON mas corto que el del paper):
LoRA r=16 alpha=32 dropout=0.05, LR 2e-4, weight decay 0.01,
warmup 0.05, batch efectivo 16, 3 epocas -- se guarda el checkpoint de
cada epoca y al final se deja claro cual tuvo mejor accuracy en
validacion (no se asume que la ultima epoca sea la mejor: el dataset
es mas pequeno que el del paper, mas riesgo de sobreajuste).

La salida por defecto es `florence2_base_lora_v4` (2026-09-20): data/*.jsonl se regenero con
las reglas v4 de preparar_dataset_florence2.py (refuerzo de las filas de `color_primario` mas
raras -- fucsia/dorado/naranja/plateado/burdeos, F1 0.00 o muy bajo en v1/v2/v3 -- ademas de
todo lo de v2/v3) y los adapters v1/v2/v3 ya no son consistentes con esas etiquetas -- no los
sobreescribe, para poder comparar los cuatro.

Uso:
    python3 entrenar_lora.py --salida ../modelos/florence2_base_lora_v4
    python3 entrenar_lora.py --limite-train 40 --limite-val 10 --epocas 1  # prueba de humo
"""
import argparse
import json
import re
import time
from pathlib import Path

import torch
from PIL import Image
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoProcessor, get_linear_schedule_with_warmup
from peft import LoraConfig, get_peft_model

BASE_DIR = Path(__file__).parent.parent
MODELO_BASE = "microsoft/Florence-2-base"
TASK_PROMPT = "<ATRIBUTOS_PRENDA>"
CAMPOS = ["categoria", "color_primario", "grupo_estilo", "genero", "temporada"]

# Solo las capas lineales del decoder de lenguaje llevan LoRA (self_attn +
# encoder_attn + fc1/fc2 dentro de language_model.model.decoder.layers.N) --
# el vision_tower (DaViT) y el encoder de texto se quedan congelados, igual
# que en el paper. Nombres verificados en este repo en el Stage 0 via
# model.named_modules() -- si Florence-2 cambia de implementacion, revisar
# aqui antes de nada.
TARGET_MODULES_REGEX = (
    r".*language_model\.model\.decoder\.layers\.\d+\.(self_attn|encoder_attn)"
    r"\.(q_proj|k_proj|v_proj|out_proj)$"
    r"|.*language_model\.model\.decoder\.layers\.\d+\.(fc1|fc2)$"
)


class DatasetAtributos(Dataset):
    def __init__(self, ruta_jsonl, limite=None):
        self.filas = [json.loads(l) for l in open(ruta_jsonl, encoding="utf-8")]
        if limite:
            self.filas = self.filas[:limite]

    def __len__(self):
        return len(self.filas)

    def __getitem__(self, idx):
        fila = self.filas[idx]
        imagen = Image.open(BASE_DIR / "data" / fila["imagen"]).convert("RGB")
        return imagen, fila["target_text"], fila


def hacer_collate(processor, max_target_len):
    def collate(batch):
        imagenes, textos, filas = zip(*batch)
        inputs = processor(
            text=[TASK_PROMPT] * len(imagenes), images=list(imagenes), return_tensors="pt"
        )
        etiquetas = processor.tokenizer(
            list(textos), return_tensors="pt", padding=True,
            truncation=True, max_length=max_target_len,
        ).input_ids
        etiquetas[etiquetas == processor.tokenizer.pad_token_id] = -100
        inputs["labels"] = etiquetas
        return inputs, filas
    return collate


def generar_prediccion(model, processor, imagen, device, usar_amp, max_new_tokens=96):
    inputs = processor(text=TASK_PROMPT, images=imagen, return_tensors="pt").to(device)
    with torch.no_grad(), autocast(device_type="cuda", dtype=torch.float16, enabled=usar_amp):
        generados = model.generate(
            input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"],
            max_new_tokens=max_new_tokens, num_beams=1,
        )
    texto = processor.batch_decode(generados, skip_special_tokens=True)[0].strip()
    return texto


def parsear_json_seguro(texto):
    """Intenta parsear el JSON generado; si no es valido, devuelve None
    en vez de reventar (la tasa de JSON valido es en si misma una metrica)."""
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def evaluar(model, processor, dataset, device, usar_amp):
    model.eval()
    aciertos = {campo: 0 for campo in CAMPOS}
    json_validos = 0
    for imagen, _texto, fila in dataset:
        texto_generado = generar_prediccion(model, processor, imagen, device, usar_amp)
        prediccion = parsear_json_seguro(texto_generado)
        if prediccion is not None and all(c in prediccion for c in CAMPOS):
            json_validos += 1
            for campo in CAMPOS:
                if prediccion.get(campo) == fila[campo]:
                    aciertos[campo] += 1
    n = len(dataset)
    resumen = {campo: aciertos[campo] / n for campo in CAMPOS}
    resumen["_json_valido"] = json_validos / n
    resumen["_accuracy_media"] = sum(aciertos.values()) / (n * len(CAMPOS))
    return resumen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epocas", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch", type=int, default=4,
                         help="Tamano de micro-batch (ajustar a la VRAM/RAM disponible).")
    parser.add_argument("--grad-accum", type=int, default=4,
                         help="Acumulacion de gradiente -- batch efectivo = batch * grad-accum (16 por defecto).")
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.05)
    parser.add_argument("--max-target-len", type=int, default=96)
    parser.add_argument("--limite-train", type=int, default=None,
                         help="Limitar filas de train (para prueba de humo en CPU).")
    parser.add_argument("--limite-val", type=int, default=None,
                         help="Limitar filas de val (para prueba de humo en CPU).")
    parser.add_argument("--salida", default=str(BASE_DIR / "modelos" / "florence2_base_lora_v4"))
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Precision mixta estandar (autocast + GradScaler), no cargar el modelo
    # directamente en bfloat16/float16: en la GPU T4 de Colab (arquitectura
    # Turing) varias convoluciones depthwise del vision_tower de Florence-2
    # no tienen kernel bfloat16 disponible ("RuntimeError: GET was unable to
    # find an engine to execute this computation") -- bug real encontrado en
    # Colab. Los pesos se quedan en fp32 (maestros) y solo el computo interno
    # se hace en fp16 donde es seguro; GradScaler evita el underflow de
    # gradientes propio de fp16 puro. En CPU esto no aplica (autocast
    # deshabilitado, todo corre en fp32 tal cual).
    usar_amp = device == "cuda"
    print(f"Dispositivo: {device}, AMP (fp16 autocast + GradScaler): {usar_amp}")

    print("Cargando Florence-2-base...")
    model = AutoModelForCausalLM.from_pretrained(MODELO_BASE, trust_remote_code=True, torch_dtype=torch.float32)
    processor = AutoProcessor.from_pretrained(MODELO_BASE, trust_remote_code=True)

    lora_config = LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
        target_modules=TARGET_MODULES_REGEX, bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    model.to(device)

    train_ds = DatasetAtributos(BASE_DIR / "data" / "train.jsonl", limite=args.limite_train)
    val_ds = DatasetAtributos(BASE_DIR / "data" / "val.jsonl", limite=args.limite_val)
    print(f"Train: {len(train_ds)} filas -- Val: {len(val_ds)} filas")

    collate = hacer_collate(processor, args.max_target_len)
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, collate_fn=collate)

    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=args.lr, weight_decay=args.weight_decay,
    )
    pasos_totales = (len(train_loader) // args.grad_accum) * args.epocas
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(pasos_totales * args.warmup_ratio),
        num_training_steps=pasos_totales,
    )
    scaler = GradScaler(device="cuda", enabled=usar_amp)

    salida_dir = Path(args.salida)
    salida_dir.mkdir(parents=True, exist_ok=True)
    mejor_accuracy = -1.0
    resultados_por_epoca = []

    for epoca in range(1, args.epocas + 1):
        model.train()
        inicio = time.time()
        perdida_acumulada = 0.0
        optimizer.zero_grad()

        for paso, (inputs, _filas) in enumerate(train_loader, 1):
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with autocast(device_type="cuda", dtype=torch.float16, enabled=usar_amp):
                salida = model(**inputs)
                perdida = salida.loss / args.grad_accum
            scaler.scale(perdida).backward()
            perdida_acumulada += salida.loss.item()

            if paso % args.grad_accum == 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad], 1.0
                )
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                optimizer.zero_grad()

            if paso % 20 == 0:
                transcurrido = time.time() - inicio
                print(f"  epoca {epoca} paso {paso}/{len(train_loader)} "
                      f"perdida={perdida_acumulada / paso:.4f} "
                      f"({transcurrido / paso:.2f}s/paso)")

        print(f"Epoca {epoca} terminada en {(time.time() - inicio) / 60:.1f} min. Evaluando en val...")
        metricas = evaluar(model, processor, val_ds, device, usar_amp)
        resultados_por_epoca.append(metricas)
        print(f"  val: {metricas}")

        if metricas["_accuracy_media"] > mejor_accuracy:
            mejor_accuracy = metricas["_accuracy_media"]
            model.save_pretrained(salida_dir)
            processor.save_pretrained(salida_dir)
            print(f"  -> nuevo mejor checkpoint guardado en {salida_dir} "
                  f"(accuracy media val={mejor_accuracy:.1%})")

    (salida_dir / "resultados_entrenamiento.json").write_text(
        json.dumps(resultados_por_epoca, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nEntrenamiento terminado. Mejor accuracy media en val: {mejor_accuracy:.1%}")
    print(f"Adapter guardado en: {salida_dir}")


if __name__ == "__main__":
    main()
