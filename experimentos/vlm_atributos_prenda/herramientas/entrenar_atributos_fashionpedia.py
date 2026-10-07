#!/usr/bin/env python3
"""
Estampado y forma de una prenda con una capa pequeña sobre CLIP ViT-B/32, entrenada con Fashionpedia (anotaciones CC BY 4.0) y probada con las etiquetas
de Víctor, que NO se usan para entrenar. Se entrena con fracciones crecientes de los datos (curva de aprendizaje) para ver cuántas fotos hacen falta.

Atributos de Fashionpedia que se aprovechan:
  - «textile pattern» -> estampado (liso, rayas, cuadros, gráfico / dibujo, texto / logo, camuflaje, otro)
  - «silhouette», «length» y los «nickname» crop -> forma (oversized / baggy, regular, ajustada, corta / cropped)
No hay atributo de tejido (algodón, punto…) en Fashionpedia: solo cuero y pieles, así que el tejido no se entrena aquí.

Datos (descarga directa, sin registro):
  https://s3.amazonaws.com/ifashionist-dataset/annotations/instances_attributes_{val,train}2020.json     (14 MB / 542 MB)
  https://s3.amazonaws.com/ifashionist-dataset/images/val_test2020.zip (236 MB, fotos en test/)  y  train2020.zip (3,3 GB, fotos en train/)
Se descomprimen en <datos>/imagenes_val y <datos>/imagenes_train.

Uso:  python3 entrenar_atributos_fashionpedia.py --datos ~/datos_tfm/fashionpedia [--max-por-clase 2500] [--salida ../resultados/…json]
"""
import argparse
import collections
import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import evaluar_etiquetas_prendas as ev  # noqa: E402

GARMENTS = 13   # las 13 primeras categorías de Fashionpedia son prendas (camisa … capa); a partir de ahí, complementos y partes
CROP_NICK = ("crop (top)", "crop (jacket)", "crop (pants)")
CAMPOS = ("estampado", "forma")


def estampado_de(attrs):
    if "camouflage" in attrs:
        return "camuflaje"
    if "letters, numbers" in attrs:
        return "texto / logo"
    if attrs & {"cartoon", "abstract", "plant", "toile de jouy"}:
        return "gráfico / dibujo"
    if "stripe" in attrs:
        return "rayas"
    if attrs & {"check", "houndstooth (pattern)"}:
        return "cuadros"
    if "plain (pattern)" in attrs:
        return "liso"
    if attrs & {"dot", "fair isle", "floral", "geometric", "paisley", "herringbone (pattern)", "chevron", "argyle", "leopard", "snakeskin (pattern)", "cheetah", "peacock", "zebra", "giraffe"}:
        return "otro"
    return None


def forma_de(attrs, cat):
    superior = cat in ("shirt, blouse", "top, t-shirt, sweatshirt", "sweater", "cardigan", "jacket", "vest")
    if attrs & set(CROP_NICK) or (superior and attrs & {"above-the-hip (length)", "micro (length)"}):
        return "corta / cropped"
    if attrs & {"oversized", "baggy", "loose (fit)", "wide leg"}:
        return "oversized / baggy"
    if "tight (fit)" in attrs:
        return "ajustada"
    if attrs & {"regular (fit)", "straight"}:
        return "regular"
    return None


def cargar_anotaciones(ruta: Path):
    """Lee el JSON tirando la segmentación (es lo que más pesa) en cuanto se construye cada anotación."""
    def sin_segmentacion(d):
        d.pop("segmentation", None)
        return d
    with open(ruta, encoding="utf-8") as f:
        return json.load(f, object_hook=sin_segmentacion)


def items_de(datos: Path, split: str, min_lado: int = 60):
    d = cargar_anotaciones(datos / f"instances_attributes_{split}2020.json")
    cats = {c["id"]: c["name"] for c in d["categories"]}
    prendas = {c["id"] for c in d["categories"][:GARMENTS]}
    atr = {a["id"]: a["name"] for a in d["attributes"]}
    carpeta = datos / f"imagenes_{split}"
    ficheros = {p.name: p for p in carpeta.rglob("*.jpg")}
    nombre = {i["id"]: i["file_name"] for i in d["images"]}
    items = []
    for a in d["annotations"]:
        if a["category_id"] not in prendas:
            continue
        x, y, w, h = a["bbox"]
        if min(w, h) < min_lado or nombre[a["image_id"]] not in ficheros:
            continue
        nombres = {atr[i] for i in a.get("attribute_ids", []) if i in atr}
        items.append({"id": f"{split}{a['id']}", "imagen": ficheros[nombre[a["image_id"]]], "caja": [x, y, x + w, y + h], "grupo": a["image_id"],
                      "estampado": estampado_de(nombres), "forma": forma_de(nombres, cats[a["category_id"]])})
    return items


def muestrear(items, max_por_clase: int, semilla: int = 7):
    """Como mucho `max_por_clase` prendas por clase y atributo (liso tiene decenas de miles): la unión de las dos muestras."""
    rnd = np.random.default_rng(semilla)
    elegidos = set()
    for campo in CAMPOS:
        por = collections.defaultdict(list)
        for i, it in enumerate(items):
            if it[campo]:
                por[it[campo]].append(i)
        for clase, idx in por.items():
            rnd.shuffle(idx)
            elegidos.update(idx[:max_por_clase])
    return [items[i] for i in sorted(elegidos)]


def embeber(items, cache: Path):
    """Embeddings CLIP de cada recorte, con caché por id (se puede interrumpir y reanudar)."""
    previo = {}
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        previo = dict(zip(z["ids"].tolist(), z["E"]))
    faltan = [it for it in items if it["id"] not in previo]
    if faltan:
        import torch
        torch.set_grad_enabled(False)
        torch.set_num_threads(6)
        model, prep, _ = ev.pc.cargar(None, None)
        t0 = time.time()
        for i in range(0, len(faltan), 64):
            lote = faltan[i:i + 64]
            v = model.encode_image(torch.stack([prep(ev.recorte(it["imagen"], it["caja"])) for it in lote]))
            v = (v / v.norm(dim=-1, keepdim=True)).numpy()
            for it, e in zip(lote, v):
                previo[it["id"]] = e
            if (i // 64) % 20 == 0:
                print(f"  {min(i + 64, len(faltan))}/{len(faltan)} recortes ({(i + 64) / (time.time() - t0):.0f}/s)", flush=True)
                np.savez(cache, ids=np.array(list(previo)), E=np.array(list(previo.values())))
        np.savez(cache, ids=np.array(list(previo)), E=np.array(list(previo.values())))
    return np.array([previo[it["id"]] for it in items])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", type=Path, required=True)
    ap.add_argument("--max-por-clase", type=int, default=2500)
    ap.add_argument("--etiquetas", type=Path, default=ev.BASE / "etiquetas_prendas.json")
    ap.add_argument("--fotos", type=Path, default=ev.BASE / "cache" / "img")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args()
    tr = muestrear(items_de(a.datos, "train"), a.max_por_clase)
    va = items_de(a.datos, "val")
    print(f"entrenamiento: {len(tr)} prendas de Fashionpedia train | validación: {len(va)} de val", flush=True)
    Etr = embeber(tr, a.datos / "emb_train_b32.npz")
    Eva = embeber(va, a.datos / "emb_val_b32.npz")
    # ---- etiquetas de Víctor (solo para probar)
    etiq = {k: v for k, v in json.loads(a.etiquetas.read_text(encoding="utf-8")).items() if v.get("prendas")}
    claves = sorted(etiq)
    import torch
    torch.set_grad_enabled(False)
    model, prep, _ = ev.pc.cargar(None, None)
    EV = []
    for k in claves:
        v = model.encode_image(prep(ev.recorte(a.fotos / f"{k.split('#')[0]}.jpg", etiq[k]["caja"])).unsqueeze(0))
        EV.append((v / v.norm(dim=-1, keepdim=True)).numpy()[0])
    EV = np.array(EV)
    res = {"entrenamiento": len(tr), "validacion": len(va), "max_por_clase": a.max_por_clase, "curvas": {}}
    rnd = np.random.default_rng(3)
    for campo in CAMPOS:
        idx = [i for i, it in enumerate(tr) if it[campo]]
        vidx = [i for i, it in enumerate(va) if it[campo]]
        y, yv = np.array([tr[i][campo] for i in idx]), np.array([va[i][campo] for i in vidx])
        prin = [(i, etiq[k]["prendas"][0].get(campo)) for i, k in enumerate(claves) if etiq[k]["prendas"][0].get(campo) in set(y)]
        cualq = [(i, {q.get(campo) for q in etiq[k]["prendas"]} & set(y)) for i, k in enumerate(claves)]
        cualq = [(i, s) for i, s in cualq if s]
        frecs = collections.Counter(v for _, v in prin)
        print(f"\n== {campo}: entrenamiento {dict(collections.Counter(y.tolist()).most_common())} | etiquetas de Víctor (principal) {dict(frecs.most_common())}", flush=True)
        orden = rnd.permutation(len(idx))
        filas = []
        for frac in (0.1, 0.25, 0.5, 1.0):
            sub = orden[: max(20, int(frac * len(idx)))]
            for balanceado in (True, False):
                m = LogisticRegression(C=2.0, max_iter=3000, class_weight="balanced" if balanceado else None).fit(Etr[np.array(idx)[sub]], y[sub])
                acc_val = float((m.predict(Eva[vidx]) == yv).mean())
                p = m.predict(EV)
                ok_prin = sum(p[i] == v for i, v in prin)
                ok_cual = sum(p[i] in s for i, s in cualq)
                filas.append({"fraccion": frac, "n": int(len(sub)), "balanceado": balanceado, "val_fashionpedia": round(acc_val, 3), "victor_principal": [ok_prin, len(prin)], "victor_cualquiera": [ok_cual, len(cualq)]})
                print(f"  {int(frac * 100):>3} % ({len(sub):>5}) {'balanceado' if balanceado else 'sin pesos '}: validación Fashionpedia {acc_val:.0%} | Víctor principal {ok_prin}/{len(prin)} | cualquier prenda {ok_cual}/{len(cualq)}", flush=True)
        base_val = collections.Counter(yv.tolist()).most_common(1)[0]
        res["curvas"][campo] = {"filas": filas, "siempre_la_mas_frecuente_val": [base_val[0], round(base_val[1] / len(yv), 3)],
                                "siempre_la_mas_frecuente_victor": [frecs.most_common(1)[0][0], frecs.most_common(1)[0][1], len(prin)] if frecs else None}
    if a.salida:
        a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
