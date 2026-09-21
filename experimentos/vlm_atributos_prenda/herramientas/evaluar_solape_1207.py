#!/usr/bin/env python3
"""
Comparacion CLIP vs Florence-2 afinado sobre las 1207 imagenes de
clip_trend_matching/, SIN contaminacion de entrenamiento.

Las 1207 imagenes salen del mismo dataset (Kaggle Fashion Product Images Small) del
que se muestrearon train/val/test del afinado, y la etiqueta de cada carpeta sale de
la misma regla articleType -> grupo_estilo. Asi que parte de ellas son imagenes que
el modelo afinado YA VIO en train (o esta en val/test). Este script:

  1. detecta que imagenes de las 6 carpetas son la misma imagen que una de
     data/imagenes_cache/ (diferencia media de pixeles < 3 sobre 60x80) y en que split cae;
  2. corre CLIP zero-shot (misma frase por grupo que clip_matching_poc.py) en todas;
  3. corre Florence-2 + LoRA en el subconjunto elegido (por defecto, solo las NO vistas);
  4. imprime accuracy de grupo_estilo por carpeta para todas / no vistas / vistas.

Requiere data/imagenes_cache/ (regenerable con preparar_dataset_florence2.py) y open_clip.

AVISO DE VERSION (importante, no solo cosmetico): el solape se calcula contra
data/{train,val,test}.jsonl TAL COMO ESTAN EN DISCO ahora mismo -- que a fecha de escribir esto
son v5 (memoria S11.7), no v1 (esto ya paso de v4 a v5 una vez, ver commit -- cada regeneracion
del dataset lo vuelve a mover). El --adapter por defecto de mas abajo sigue siendo v1 (para
reproducir la memoria S6.3 tal cual), pero si alguien regenera el dataset a una version nueva y
luego corre este script sin mas, compara el adapter v1 contra el solape de la particion nueva --
inconsistente. Para repetir S6.3 de verdad hay que reconstruir train/val/test.jsonl de v1 desde
el historial de git primero. Para una comparacion de otra version, pasar --adapter y regenerar
antes con la version de preparar_dataset_florence2.py correspondiente.

Uso:
    python3 evaluar_solape_1207.py                       # Florence solo en las no vistas
    python3 evaluar_solape_1207.py --florence vistas     # contraste: las que si vio
    python3 evaluar_solape_1207.py --florence ninguna    # solo solape + CLIP (segundos)
Guarda data/eval_1207_solape.json (por imagen) y reanuda lo ya calculado.
"""
import argparse
import collections
import json
import random
import re
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

BASE_DIR = Path(__file__).parent.parent
CLIP_DIR = BASE_DIR.parent / "clip_trend_matching"
CARPETAS = ["casual", "streetwear", "de_vestir", "fiesta_noche", "deportivo", "playa_resort"]
EXT = {".jpg", ".jpeg", ".png", ".webp"}
UMBRAL_MAD = 3.0
GRUPOS_ESTILO = {  # las mismas frases que clip_matching_poc.py / evaluar_precision_grupo_estilo.py
    "casual": "ropa casual de diario",
    "streetwear": "ropa de estilo urbano, streetwear",
    "de_vestir": "ropa elegante y formal, de vestir",
    "fiesta_noche": "ropa de fiesta o para salir de noche",
    "deportivo": "ropa deportiva",
    "playa_resort": "ropa veraniega de playa o resort",
}
MODELO_BASE = "microsoft/Florence-2-base"


def pixeles(ruta):
    return np.asarray(Image.open(ruta).convert("RGB").resize((60, 80)), dtype=np.float32).ravel()


def detectar_solapes(rutas):
    """ruta -> split ('train'/'val'/'test') si la imagen esta en el afinado, si no None."""
    split_de = {}
    for s in ["train", "val", "test"]:
        for linea in open(BASE_DIR / "data" / f"{s}.jsonl", encoding="utf-8"):
            split_de[str(json.loads(linea)["id"])] = s
    ids = [i for i in split_de if (BASE_DIR / "data" / "imagenes_cache" / f"{i}.jpg").exists()]
    if len(ids) < len(split_de):
        raise SystemExit(f"Faltan imagenes en data/imagenes_cache/ ({len(ids)}/{len(split_de)}): "
                         "regeneralas con preparar_dataset_florence2.py")
    A = np.stack([pixeles(BASE_DIR / "data" / "imagenes_cache" / f"{i}.jpg") for i in ids])
    salida = {}
    for r in rutas:
        mad = np.abs(A - pixeles(r)).mean(1)
        j = int(mad.argmin())
        salida[str(r)] = split_de[ids[j]] if mad[j] < UMBRAL_MAD else None
    return salida


def clip_zero_shot(rutas):
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32-quickgelu", pretrained="openai")
    tokenizer = open_clip.get_tokenizer("ViT-B-32-quickgelu")
    model.eval()
    claves = list(GRUPOS_ESTILO)
    with torch.no_grad():
        t = model.encode_text(tokenizer([GRUPOS_ESTILO[c] for c in claves]))
        t = t / t.norm(dim=-1, keepdim=True)
    pred = {}
    for i in range(0, len(rutas), 32):
        lote = rutas[i:i + 32]
        x = torch.stack([preprocess(Image.open(r).convert("RGB")) for r in lote])
        with torch.no_grad():
            v = model.encode_image(x)
            v = v / v.norm(dim=-1, keepdim=True)
        for r, k in zip(lote, (v @ t.T).argmax(1).tolist()):
            pred[str(r)] = claves[k]
    return pred


def florence_lote(claves, adapter, guardar, resultados, batch):
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoProcessor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    base = AutoModelForCausalLM.from_pretrained(MODELO_BASE, trust_remote_code=True, torch_dtype=torch.float32)
    modelo = PeftModel.from_pretrained(base, adapter).to(device).eval()
    proc = AutoProcessor.from_pretrained(MODELO_BASE, trust_remote_code=True)
    t0, hechas = time.time(), 0
    for i in range(0, len(claves), batch):
        lote = claves[i:i + batch]
        inp = proc(text=["<ATRIBUTOS_PRENDA>"] * len(lote), images=[Image.open(CLIP_DIR / k).convert("RGB") for k in lote],
                   return_tensors="pt").to(device)
        with torch.no_grad(), torch.autocast(device_type="cuda", dtype=torch.float16, enabled=device == "cuda"):
            gen = modelo.generate(input_ids=inp["input_ids"], pixel_values=inp["pixel_values"], max_new_tokens=96, num_beams=1)
        for k, texto in zip(lote, proc.batch_decode(gen, skip_special_tokens=True)):
            m = re.search(r"\{.*\}", texto, re.DOTALL)
            try:
                resultados[k]["florence"] = json.loads(m.group(0)) if m else None
            except json.JSONDecodeError:
                resultados[k]["florence"] = None
        hechas += len(lote)
        guardar()
        print(f"  Florence {hechas}/{len(claves)}  ({(time.time() - t0) / hechas:.1f}s/imagen)", flush=True)


def tabla(resultados, filtro, titulo, clave):
    print(f"\n{titulo}")
    tot = ok = 0
    for c in CARPETAS:
        sub = [r for r in resultados.values() if r["carpeta"] == c and filtro(r) and clave(r) is not None]
        k = sum(1 for r in sub if clave(r) == c)
        tot, ok = tot + len(sub), ok + k
        print(f"  {c:<13} {k:>4}/{len(sub):<4} = {k / len(sub):.1%}" if sub else f"  {c:<13}    -")
    print(f"  {'TOTAL':<13} {ok:>4}/{tot:<4} = {ok / tot:.1%}" if tot else "  TOTAL -")


def tabla_frecuencia(resultados):
    """Acierto en imagenes no vistas segun cuantos ejemplos de ese articleType hubo en train
    (el articleType es el prefijo del nombre de archivo de las carpetas: capris_10.jpg)."""
    train = collections.Counter(json.loads(l)["articleType"].lower().replace(" ", "_")
                                for l in open(BASE_DIR / "data" / "train.jsonl", encoding="utf-8"))
    tipo = lambda k: re.sub(r"_\d+\.\w+$", "", k.split("/")[1]).lower()
    sub = {k: r for k, r in resultados.items() if r["visto_en"] is None and r.get("florence")}
    if not sub:
        return
    print("\nNO vistas, segun los ejemplos de ese tipo de prenda en train (Florence / CLIP)")
    for etiqueta, lo, hi in [("0-9", 0, 9), ("10-49", 10, 49), ("50-199", 50, 199), (">=200", 200, 10 ** 9)]:
        s = [r for k, r in sub.items() if lo <= train.get(tipo(k), 0) <= hi]
        if s:
            f = sum(1 for r in s if r["florence"].get("grupo_estilo") == r["carpeta"])
            c = sum(1 for r in s if r["clip"] == r["carpeta"])
            print(f"  {etiqueta:>7} ejemplos: n={len(s):>3}  Florence {f:>3}/{len(s):<3} = {f / len(s):.0%}   CLIP {c:>3}/{len(s):<3} = {c / len(s):.0%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--florence", choices=["no_vistas", "vistas", "todas", "ninguna"], default="no_vistas")
    ap.add_argument("--max-por-carpeta", type=int, default=None, help="Tope aleatorio (semilla 42) de imagenes de Florence por carpeta.")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--adapter", default=str(BASE_DIR / "modelos" / "florence2_base_lora_v1"))
    ap.add_argument("--salida", default=str(BASE_DIR / "data" / "eval_1207_solape.json"))
    args = ap.parse_args()

    salida = Path(args.salida)
    resultados = json.loads(salida.read_text(encoding="utf-8")) if salida.exists() else {}
    guardar = lambda: salida.write_text(json.dumps(resultados, ensure_ascii=False, indent=0), encoding="utf-8")

    rutas = sorted(p for c in CARPETAS for p in (CLIP_DIR / c).iterdir() if p.suffix.lower() in EXT)
    nuevas = [r for r in rutas if str(r.relative_to(CLIP_DIR)) not in resultados]
    if nuevas:
        print(f"Detectando solapes con train/val/test ({len(nuevas)} imagenes)...")
        solape = detectar_solapes(nuevas)
        print("CLIP zero-shot...")
        clip = clip_zero_shot(nuevas)
        for r in nuevas:
            k = str(r.relative_to(CLIP_DIR))
            resultados[k] = {"carpeta": r.parent.name, "visto_en": solape[str(r)], "clip": clip[str(r)]}
        guardar()

    n_vistas = collections.Counter(r["visto_en"] for r in resultados.values())
    total = len(resultados)
    print(f"\nImagenes: {total}. Ya vistas por el afinado (misma imagen en train/val/test): "
          f"{total - n_vistas[None]} ({(total - n_vistas[None]) / total:.0%})  -> {dict(n_vistas)}")
    print("Por carpeta (vistas/total): " + ", ".join(
        f"{c} {sum(1 for r in resultados.values() if r['carpeta'] == c and r['visto_en'])}/"
        f"{sum(1 for r in resultados.values() if r['carpeta'] == c)}" for c in CARPETAS))

    if args.florence != "ninguna":
        elegir = {"no_vistas": lambda r: r["visto_en"] is None, "vistas": lambda r: r["visto_en"] is not None,
                  "todas": lambda r: True}[args.florence]
        cand = [k for k, r in resultados.items() if elegir(r) and "florence" not in r]
        if args.max_por_carpeta:
            random.seed(42)
            keep = []
            for c in CARPETAS:
                keep += random.sample([k for k in cand if resultados[k]["carpeta"] == c],
                                      min(args.max_por_carpeta, sum(1 for k in cand if resultados[k]["carpeta"] == c)))
            cand = keep
        if cand:
            print(f"\nFlorence-2 + LoRA sobre {len(cand)} imagenes (batch {args.batch})...")
            florence_lote(cand, args.adapter, guardar, resultados, args.batch)

    ver = lambda r: r["florence"].get("grupo_estilo") if r.get("florence") else None
    tabla(resultados, lambda r: True, "CLIP zero-shot, TODAS", lambda r: r["clip"])
    tabla(resultados, lambda r: r["visto_en"] is None, "CLIP zero-shot, solo NO vistas", lambda r: r["clip"])
    tabla(resultados, lambda r: r["visto_en"] is not None, "CLIP zero-shot, solo vistas", lambda r: r["clip"])
    for nombre, f in [("NO vistas", lambda r: r["visto_en"] is None and "florence" in r),
                      ("vistas en train/val/test", lambda r: r["visto_en"] is not None and "florence" in r)]:
        if any(f(r) for r in resultados.values()):
            tabla(resultados, f, f"Florence-2 afinado, {nombre} (las calculadas)", ver)
            tabla(resultados, f, f"CLIP zero-shot, mismas imagenes ({nombre})", lambda r: r["clip"])
    tabla_frecuencia(resultados)


if __name__ == "__main__":
    main()
