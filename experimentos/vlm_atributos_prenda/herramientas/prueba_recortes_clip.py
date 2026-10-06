#!/usr/bin/env python3
"""
Prueba 2 de «tendencia por prenda» (2026-10-06): ¿se pueden sacar tipo fino, estampado y forma
de cada prenda con CLIP *sin entrenar nada*?

Entrada: el JSON de `analizar_outfit.py` (cajas por prenda de la persona principal) y la carpeta de fotos.
Para cada prenda detectada (sin «torso» geométrico ni cajas < 40 px) recorta, pasa el recorte a un
cuadrado gris y elige con CLIP ViT-B/32 (el mismo del clasificador de estilo, pesos de OpenAI):
  - tipo fino, entre los tipos del ERP de la categoría detectada (Estado_arte §3.3);
  - estampado, entre 10 opciones;
  - forma, entre 4 opciones.
Guarda los logits (`--salida/recortes_scores.npz`) y 3 hojas de 12 recortes con la predicción escrita
debajo (`hoja_recortes_1..3.jpg`) para revisarlas a ojo. Las fotos NO se versionan (son de la Biblioteca).

Uso:
    python3 prueba_recortes_clip.py --prendas prendas.json --fotos fotos_prendas --salida recortes_out
Resultado de la revisión a ojo de la primera pasada: ../resultados/prueba_recortes_clip_2026-10-06.json
"""
import argparse
import collections
import json
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "clip_trend_matching"))
from clip_matching_poc import cargar_modelo  # noqa: E402  (mismo CLIP y tokenizador que el POC y analisis_mercado)

TIPOS = {
    "ropa_superior": [("Camiseta manga corta", "a short-sleeved t-shirt"), ("Camiseta de tirantes", "a sleeveless tank top"),
                      ("Camiseta manga larga", "a long-sleeved t-shirt"), ("Top", "a crop top"), ("Camisa", "a button-up shirt"),
                      ("Polo", "a polo shirt"), ("Sudadera", "a hoodie sweatshirt"), ("Jersey", "a knitted sweater"),
                      ("Chaleco sin mangas", "a sleeveless vest")],
    "abrigo": [("Chaqueta", "a jacket"), ("Americana", "a blazer"), ("Abrigo", "a long coat"), ("Plumas", "a puffer jacket"),
               ("Sudadera", "a zip-up hoodie")],
    "ropa_inferior": [("Pantalón", "a pair of long trousers"), ("Falda", "a skirt"), ("Short", "a pair of shorts"),
                      ("Legging/Malla", "leggings")],
    "cuerpo_entero": [("Vestido", "a dress"), ("Mono", "a jumpsuit")],
    "calzado": [("Zapatillas deportivas", "a pair of sports sneakers"), ("Zapatillas casual/lifestyle", "a pair of casual canvas shoes"),
                ("Zapatos planos de vestir", "a pair of flat dress shoes"), ("Zapatos de tacón", "a pair of high heels"),
                ("Sandalias", "a pair of sandals"), ("Botas", "a pair of boots")],
}
ESTAMPADOS = [("liso", "a plain solid-colored garment with no print"), ("rayas", "a striped garment"),
              ("cuadros / tartán", "a plaid checkered garment"), ("floral", "a garment with a floral print"),
              ("animal print", "a garment with leopard animal print"), ("tie-dye", "a tie-dye garment"),
              ("geométrico", "a garment with a geometric pattern"), ("logo / lettering", "a garment with a logo or text printed on it"),
              ("gráfico / personaje", "a garment with a large cartoon graphic print"), ("camuflaje", "a camouflage garment")]
FORMAS = [("oversized / baggy", "an oversized baggy loose-fitting garment"), ("regular", "a regular fit garment"),
          ("slim", "a slim tight fitted garment"), ("cropped", "a short cropped garment")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prendas", required=True, type=Path)
    ap.add_argument("--fotos", required=True, type=Path)
    ap.add_argument("--salida", required=True, type=Path)
    ap.add_argument("--semilla", type=int, default=11)
    ap.add_argument("--n-hojas", type=int, default=3)
    a = ap.parse_args()
    a.salida.mkdir(parents=True, exist_ok=True)
    import torch
    torch.set_grad_enabled(False)
    model, prep, tok = cargar_modelo()
    prendas = json.loads(a.prendas.read_text(encoding="utf-8"))

    def texto(ps):
        t = model.encode_text(tok(["a photo of " + p for p in ps]))
        return (t / t.norm(dim=-1, keepdim=True)).numpy()

    t_tipo = {k: texto([p for _, p in v]) for k, v in TIPOS.items()}
    t_est, t_forma = texto([p for _, p in ESTAMPADOS]), texto([p for _, p in FORMAS])

    def cuadrada(im):
        w, h = im.size
        s = max(w, h)
        lienzo = Image.new("RGB", (s, s), (128, 128, 128))
        lienzo.paste(im, ((s - w) // 2, (s - h) // 2))
        return lienzo

    def top(v, t, etq):
        s = 100.0 * (t @ v)
        s -= s.max()
        p = np.exp(s)
        p /= p.sum()
        i = int(p.argmax())
        return etq[i], float(p[i])

    filas = []
    for k in sorted(prendas):
        fotos = list(a.fotos.glob(f"{k}.*"))
        if not fotos or not prendas[k]["personas"]:
            continue
        im = Image.open(fotos[0]).convert("RGB")
        w, h = im.size
        for pr in prendas[k]["personas"][0]["prendas"]:
            cat = pr["categoria"]
            x1, y1, x2, y2 = pr["caja"]
            bw, bh = x2 - x1, y2 - y1
            if cat not in TIPOS or pr["deteccion"] == "torso" or min(bw, bh) < 40:
                continue
            c = im.crop((max(0, int(x1 - .06 * bw)), max(0, int(y1 - .06 * bh)), min(w, int(x2 + .06 * bw)), min(h, int(y2 + .06 * bh))))
            v = model.encode_image(prep(cuadrada(c)).unsqueeze(0))
            v = (v / v.norm(dim=-1, keepdim=True)).numpy()[0]
            tipo, pt = top(v, t_tipo[cat], [n for n, _ in TIPOS[cat]])
            est, pe = top(v, t_est, [n for n, _ in ESTAMPADOS])
            forma, pf = top(v, t_forma, [n for n, _ in FORMAS])
            filas.append(dict(v=v, foto=k, det=pr["deteccion"], cat=cat, tipo=tipo, p_tipo=pt, est=est, p_est=pe, forma=forma, p_forma=pf, crop=c))
    print("recortes evaluables:", len(filas), {c: sum(1 for f in filas if f["cat"] == c) for c in TIPOS})

    idx = list(range(len(filas)))
    random.Random(a.semilla).shuffle(idx)
    muestra = idx[:12 * a.n_hojas]
    try:
        fuente = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    except OSError:
        fuente = ImageFont.load_default()
    W, H, TH = 300, 330, 82
    meta = []
    for hoja in range(a.n_hojas):
        im = Image.new("RGB", (3 * W, 4 * H), (24, 24, 32))
        dr = ImageDraw.Draw(im)
        for n, ii in enumerate(muestra[hoja * 12:(hoja + 1) * 12]):
            f = filas[ii]
            c = f["crop"].copy()
            c.thumbnail((W - 8, H - TH - 8))
            x, y = (n % 3) * W, (n // 3) * H
            im.paste(c, (x + 4 + (W - 8 - c.width) // 2, y + 4))
            id_ = f"R{hoja * 12 + n + 1:02d}"
            dr.rectangle([x, y, x + 44, y + 20], fill=(0, 0, 0))
            dr.text((x + 4, y + 2), id_, fill=(255, 255, 255), font=fuente)
            ty = y + H - TH
            dr.text((x + 6, ty + 2), f"T: {f['tipo']} {f['p_tipo']:.0%}", fill=(150, 220, 255), font=fuente)
            dr.text((x + 6, ty + 28), f"E: {f['est']} {f['p_est']:.0%}", fill=(255, 220, 140), font=fuente)
            dr.text((x + 6, ty + 54), f"F: {f['forma']} {f['p_forma']:.0%}", fill=(190, 255, 170), font=fuente)
            meta.append(dict(id=id_, foto=f["foto"], det=f["det"], cat=f["cat"], tipo=f["tipo"], est=f["est"], forma=f["forma"]))
        im.save(a.salida / f"hoja_recortes_{hoja + 1}.jpg", quality=88)
    (a.salida / "recortes_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    np.savez(a.salida / "recortes_scores.npz", est=np.array([100.0 * (t_est @ f["v"]) for f in filas]),
             forma=np.array([100.0 * (t_forma @ f["v"]) for f in filas]), muestra=np.array(muestra))
    (a.salida / "recortes_etiquetas.json").write_text(
        json.dumps({"est": [n for n, _ in ESTAMPADOS], "forma": [n for n, _ in FORMAS]}, ensure_ascii=False), encoding="utf-8")
    for campo in ("tipo", "est", "forma"):
        print(campo, dict(collections.Counter(f[campo] for f in filas).most_common()))


if __name__ == "__main__":
    main()
