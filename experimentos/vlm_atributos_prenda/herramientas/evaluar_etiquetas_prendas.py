#!/usr/bin/env python3
"""
Mide lo que acierta CLIP (ViT-B/32, sin entrenar) contra las etiquetas que Víctor puso a los recortes de prendas en la página «Etiquetar prendas»
(`analisis_mercado/tendencia_datos/etiquetas_prendas.json`, lote 1, 2026-10-06). Las predicciones del modelo no se le enseñaron al etiquetar, así que es una
medida real. Cada recorte puede traer varias prendas y algunas a medias; se mide de forma indulgente (acierta si la predicción es alguna de las etiquetas puestas
a ese recorte) y se compara con «decir siempre la etiqueta más frecuente». Además prueba corregir el modelo con la frecuencia de tus etiquetas (prior), eligiendo el
peso con validación cruzada dejando un recorte fuera: con tan pocas etiquetas es una estimación optimista.

Uso:  python3 evaluar_etiquetas_prendas.py [--etiquetas RUTA] [--fotos CARPETA] [--salida RESULTADOS.json]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import prueba_recortes_clip as pc  # noqa: E402

BASE = AQUI.parents[1] / "analisis_mercado" / "tendencia_datos"
TIPOS = dict(pc.TIPOS)
TIPOS.update({"Sudadera": "a crewneck sweatshirt without a hood", "Hoodie": "a hoodie with a hood", "Gorra/Gorro/Sombrero": "a cap or a hat", "Bolso": "a handbag",
              "Riñonera": "a fanny pack"})
ESTAMPADOS = {"liso": "a plain solid-colored garment with no print", "rayas": "a striped garment", "cuadros": "a plaid checkered garment",
              "gráfico / dibujo": "a garment with a large graphic illustration print", "texto / logo": "a garment with a logo or text printed on it",
              "camuflaje": "a camouflage garment", "otro": "a garment with a floral or geometric pattern"}
TEJIDOS = {"denim (vaquero)": "a denim garment", "cuero / vinilo": "a leather garment", "algodón": "a plain cotton garment", "punto": "a knitted garment",
           "felpa / polar": "a fleece or french terry sweatshirt garment", "técnico / impermeable": "a technical waterproof nylon garment", "pana": "a corduroy garment",
           "terciopelo": "a velvet garment", "seda / satén": "a satin silk garment", "tul / encaje": "a lace or tulle garment", "lino": "a linen garment"}
FORMAS = {"oversized / baggy": "an oversized baggy loose-fitting garment", "regular": "a regular fit garment", "ajustada": "a slim tight fitted garment",
          "corta / cropped": "a short cropped garment"}
EQUIV = {"Hoodie": {"Hoodie", "Sudadera"}, "Sudadera": {"Sudadera", "Hoodie"}}   # el modelo del flujo aún no distingue hoodie de sudadera


def recorte(foto: Path, caja) -> Image.Image:
    im = Image.open(foto).convert("RGB")
    W, H = im.size
    x1, y1, x2, y2 = caja
    bw, bh = x2 - x1, y2 - y1
    c = im.crop((max(0, int(x1 - .06 * bw)), max(0, int(y1 - .06 * bh)), min(W, int(x2 + .06 * bw)), min(H, int(y2 + .06 * bh))))
    s = max(c.size)
    lienzo = Image.new("RGB", (s, s), (128, 128, 128))
    lienzo.paste(c, ((s - c.width) // 2, (s - c.height) // 2))
    return lienzo


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--etiquetas", type=Path, default=BASE / "etiquetas_prendas.json")
    ap.add_argument("--fotos", type=Path, default=BASE / "cache" / "img")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args()
    import torch
    torch.set_grad_enabled(False)
    model, prep, tok = pc.cargar(None, None)
    etiq = {k: v for k, v in json.loads(a.etiquetas.read_text(encoding="utf-8")).items() if v.get("prendas")}

    def texto(d):
        t = model.encode_text(tok(["a photo of " + p for p in d.values()]))
        return (t / t.norm(dim=-1, keepdim=True)).numpy()
    T = {"tipo": texto(TIPOS), "estampado": texto(ESTAMPADOS), "tejido": texto(TEJIDOS), "forma": texto(FORMAS)}
    N = {"tipo": list(TIPOS), "estampado": list(ESTAMPADOS), "tejido": list(TEJIDOS), "forma": list(FORMAS)}
    claves = sorted(etiq)
    E = []
    for k in claves:
        v = model.encode_image(prep(recorte(a.fotos / f"{k.split('#')[0]}.jpg", etiq[k]["caja"])).unsqueeze(0))
        E.append((v / v.norm(dim=-1, keepdim=True)).numpy()[0])
    E = np.array(E)
    res = {"recortes": len(claves), "prendas": sum(len(etiq[k]["prendas"]) for k in claves)}

    # ---- tipo: lo que dice el flujo (listas por categoría) y CLIP sin restringir (top-1 / top-3)
    def mis_tipos(k): return {q["tipo"] for q in etiq[k]["prendas"] if q.get("tipo")}
    con_tipo = [k for k in claves if mis_tipos(k)]
    flujo = sum(1 for k in con_tipo if EQUIV.get(etiq[k]["tipo_modelo"], {etiq[k]["tipo_modelo"]}) & (mis_tipos(k) | {t2 for t in mis_tipos(k) for t2 in EQUIV.get(t, ())}))
    L = 100.0 * E @ T["tipo"].T
    top1 = top3 = 0
    for i, k in enumerate(claves):
        if k not in con_tipo:
            continue
        orden = [N["tipo"][j] for j in np.argsort(-L[i])]
        validas = mis_tipos(k) | {t2 for t in mis_tipos(k) for t2 in EQUIV.get(t, ())}
        top1 += orden[0] in validas
        top3 += bool(set(orden[:3]) & validas)
    res["tipo"] = {"recortes": len(con_tipo), "flujo_acierta": flujo, "clip_top1": top1, "clip_top3": top3,
                   "varias_prendas_en_el_recorte": sum(1 for k in con_tipo if len(mis_tipos(k)) > 1)}

    # ---- estampado, tejido y forma
    for campo, vocab in (("estampado", ESTAMPADOS), ("tejido", TEJIDOS), ("forma", FORMAS)):
        valores = {k: {q[campo] for q in etiq[k]["prendas"] if q.get(campo) in vocab} for k in claves}
        idx = [i for i, k in enumerate(claves) if valores[k]]
        L = 100.0 * E @ T[campo].T
        pred = [N[campo][int(L[i].argmax())] for i in idx]
        acierta = sum(p in valores[claves[i]] for p, i in zip(pred, idx))
        todas = collections.Counter(v for k in claves for q in etiq[k]["prendas"] if (v := q.get(campo)) in vocab)
        mayoria = todas.most_common(1)[0][0]
        base = sum(mayoria in valores[claves[i]] for i in idx)
        # prior de tus etiquetas con validación cruzada dejando un recorte fuera
        cls = N[campo]
        mejor_w, mejor_ok = 0.0, -1
        for w in (0.0, 3.0, 6.0, 10.0, 15.0, 25.0):
            ok = 0
            for t in idx:
                cnt = collections.Counter(v for k in claves if k != claves[t] for v in valores[k])
                prior = np.log(np.array([cnt[c] + 0.5 for c in cls]) / (sum(cnt.values()) + 0.5 * len(cls)))
                ok += cls[int((L[t] + w * prior).argmax())] in valores[claves[t]]
            if ok > mejor_ok:
                mejor_w, mejor_ok = w, ok
        res[campo] = {"recortes": len(idx), "clip_acierta": acierta, "siempre_la_mas_frecuente": base, "mas_frecuente": mayoria, "con_prior_cv": mejor_ok, "peso_prior": mejor_w,
                      "frecuencias": dict(todas.most_common())}
    for c in ("tipo", "estampado", "tejido", "forma"):
        print(c, res[c])
    if a.salida:
        a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
