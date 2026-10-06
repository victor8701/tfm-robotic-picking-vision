#!/usr/bin/env python3
"""
Prueba 2 de «tendencia por prenda» (2026-10-06): ¿se pueden sacar tipo fino, estampado y forma de cada prenda con un CLIP *sin entrenar nada*?

Entrada: el JSON de `analizar_outfit.py` (cajas por prenda de la persona principal) y la carpeta de fotos.
Para cada prenda detectada (sin «torso» geométrico ni cajas < 40 px) recorta, pasa el recorte a un cuadrado gris y guarda su embedding CLIP junto con los
embeddings de texto de los 25 tipos de prenda del ERP, 10 estampados y 4 formas (`--salida/<modelo>/recortes_emb.npz`). La puntuación se hace luego con
`evaluar_recortes.py`, así se puede cambiar de modelo sin repetir nada más. Con `--hojas N` dibuja N hojas de 12 recortes numerados (R01…) para revisarlos a ojo
(la elección de los recortes depende solo de `--semilla`, no del modelo: R01…R36 son siempre los mismos). Las fotos NO se versionan (son de la Biblioteca).

Modelos: por defecto el del clasificador de estilo (ViT-B-32 OpenAI, `cargar_modelo()` del POC). Otros: `--modelo ViT-L-14-quickgelu --pesos openai`,
`--modelo ViT-L-14 --pesos dfn2b`, `--modelo ViT-SO400M-14-SigLIP --pesos webli` (todos de pesos abiertos, vía open_clip).

Uso:
    python3 prueba_recortes_clip.py --prendas prendas.json --fotos fotos_prendas --salida recortes_out [--modelo M --pesos P] [--hojas 3]
"""
import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "clip_trend_matching"))

TIPOS = [("Camiseta manga corta", "a short-sleeved t-shirt"), ("Camiseta de tirantes", "a sleeveless tank top"), ("Camiseta manga larga", "a long-sleeved t-shirt"),
         ("Top", "a crop top"), ("Camisa", "a button-up shirt"), ("Polo", "a polo shirt"), ("Sudadera", "a hoodie sweatshirt"), ("Jersey", "a knitted sweater"),
         ("Chaleco sin mangas", "a sleeveless vest"), ("Chaqueta", "a jacket"), ("Americana", "a blazer"), ("Abrigo", "a long coat"), ("Plumas", "a puffer jacket"),
         ("Pantalón", "a pair of long trousers"), ("Falda", "a skirt"), ("Short", "a pair of shorts"), ("Legging/Malla", "leggings"),
         ("Vestido", "a dress"), ("Mono", "a jumpsuit"),
         ("Zapatillas deportivas", "a pair of sports sneakers"), ("Zapatillas casual/lifestyle", "a pair of casual canvas shoes"),
         ("Zapatos planos de vestir", "a pair of flat dress shoes"), ("Zapatos de tacón", "a pair of high heels"), ("Sandalias", "a pair of sandals"),
         ("Botas", "a pair of boots")]
# tipos posibles según la categoría que da el detector (arriba y abrigo se mezclan: el detector llama «camisa» a casi todo lo de arriba)
GRUPOS = {"ropa_superior": TIPOS[:13], "abrigo": TIPOS[:13], "ropa_inferior": TIPOS[13:17], "cuerpo_entero": TIPOS[17:19], "calzado": TIPOS[19:]}
ESTAMPADOS = [("liso", "a plain solid-colored garment with no print"), ("rayas", "a striped garment"), ("cuadros / tartán", "a plaid checkered garment"),
              ("floral", "a garment with a floral print"), ("animal print", "a garment with leopard animal print"), ("tie-dye", "a tie-dye garment"),
              ("geométrico", "a garment with a geometric pattern"), ("logo / lettering", "a garment with a logo or text printed on it"),
              ("gráfico / personaje", "a garment with a large cartoon graphic print"), ("camuflaje", "a camouflage garment")]
FORMAS = [("oversized / baggy", "an oversized baggy loose-fitting garment"), ("regular", "a regular fit garment"),
          ("slim", "a slim tight fitted garment"), ("cropped", "a short cropped garment")]


def cargar(modelo, pesos):
    if not modelo:
        from clip_matching_poc import cargar_modelo
        return cargar_modelo()
    import open_clip
    m, _, prep = open_clip.create_model_and_transforms(modelo, pretrained=pesos)
    m.eval()
    return m, prep, open_clip.get_tokenizer(modelo)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prendas", required=True, type=Path)
    ap.add_argument("--fotos", required=True, type=Path)
    ap.add_argument("--salida", required=True, type=Path)
    ap.add_argument("--modelo")
    ap.add_argument("--pesos", default="openai")
    ap.add_argument("--semilla", type=int, default=11)
    ap.add_argument("--hojas", type=int, default=0)
    a = ap.parse_args()
    nombre = (a.modelo or "ViT-B-32-poc") + ("_" + a.pesos if a.modelo else "")
    out = a.salida / nombre
    out.mkdir(parents=True, exist_ok=True)
    import torch
    torch.set_grad_enabled(False)
    model, prep, tok = cargar(a.modelo, a.pesos)
    prendas = json.loads(a.prendas.read_text(encoding="utf-8"))

    def texto(ps):
        t = model.encode_text(tok(["a photo of " + p for p in ps]))
        return (t / t.norm(dim=-1, keepdim=True)).numpy()

    def cuadrada(im):
        w, h = im.size
        s = max(w, h)
        lienzo = Image.new("RGB", (s, s), (128, 128, 128))
        lienzo.paste(im, ((s - w) // 2, (s - h) // 2))
        return lienzo

    meta, embs, crops = [], [], []
    for k in sorted(prendas):
        fotos = list(a.fotos.glob(f"{k}.*"))
        if not fotos or not prendas[k]["personas"]:
            continue
        im = Image.open(fotos[0]).convert("RGB")
        w, h = im.size
        for pr in prendas[k]["personas"][0]["prendas"]:
            x1, y1, x2, y2 = pr["caja"]
            bw, bh = x2 - x1, y2 - y1
            if pr["categoria"] not in GRUPOS or pr["deteccion"] == "torso" or min(bw, bh) < 40:
                continue
            c = im.crop((max(0, int(x1 - .06 * bw)), max(0, int(y1 - .06 * bh)), min(w, int(x2 + .06 * bw)), min(h, int(y2 + .06 * bh))))
            v = model.encode_image(prep(cuadrada(c)).unsqueeze(0))
            embs.append((v / v.norm(dim=-1, keepdim=True)).numpy()[0])
            meta.append({"foto": k, "det": pr["deteccion"], "cat": pr["categoria"]})
            crops.append(c)
    idx = list(range(len(meta)))
    random.Random(a.semilla).shuffle(idx)
    muestra = idx[:36]
    np.savez(out / "recortes_emb.npz", emb=np.array(embs), muestra=np.array(muestra), cat=np.array([m["cat"] for m in meta]),
             t_tipo=texto([p for _, p in TIPOS]), t_est=texto([p for _, p in ESTAMPADOS]), t_forma=texto([p for _, p in FORMAS]),
             n_tipo=np.array([n for n, _ in TIPOS]), n_est=np.array([n for n, _ in ESTAMPADOS]), n_forma=np.array([n for n, _ in FORMAS]))
    (out / "recortes_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{nombre}: {len(meta)} recortes evaluables guardados en {out}")
    if a.hojas:
        try:
            fuente = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
        except OSError:
            fuente = ImageFont.load_default()
        W, H = 300, 260
        for hoja in range(a.hojas):
            im = Image.new("RGB", (3 * W, 4 * H), (24, 24, 32))
            dr = ImageDraw.Draw(im)
            for n, ii in enumerate(muestra[hoja * 12:(hoja + 1) * 12]):
                c = crops[ii].copy()
                c.thumbnail((W - 8, H - 8))
                x, y = (n % 3) * W, (n // 3) * H
                im.paste(c, (x + 4 + (W - 8 - c.width) // 2, y + 4))
                dr.rectangle([x, y, x + 44, y + 20], fill=(0, 0, 0))
                dr.text((x + 4, y + 2), f"R{hoja * 12 + n + 1:02d}", fill=(255, 255, 255), font=fuente)
            im.save(out / f"hoja_recortes_{hoja + 1}.jpg", quality=88)


if __name__ == "__main__":
    main()
