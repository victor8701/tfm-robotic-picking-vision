#!/usr/bin/env python3
"""
Prepara la carpeta que se sube a Kaggle como dataset PRIVADO para la prueba del «profesor» (un modelo abierto grande de lenguaje y visión). Hay dos paquetes
independientes, para poder subirlos, usarlos y borrarlos por separado:

  --origen fashionpedia  una muestra equilibrada de prendas de Fashionpedia val (público; con su estampado y forma derivados de los atributos del conjunto)
  --origen victor        las fotos de los recortes que Víctor etiquetó (caja y tipo de la prenda, pero SIN estampado, tejido ni forma: eso se queda en local para medir)

Salida (en --salida): `fotos.zip` (todas las fotos, ya reducidas), `manifiesto.json` y `dataset-metadata.json`.
Uso:  python3 preparar_dataset.py --origen fashionpedia --salida /ruta/dataset [--fashionpedia ~/datos_tfm/fashionpedia] [--por-estampado 30 --por-forma 40]
"""
import argparse
import collections
import json
import random
import sys
import zipfile
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import evaluar_etiquetas_prendas as ev  # noqa: E402
import entrenar_atributos_fashionpedia as fp  # noqa: E402

LADO_MAX = 1280
TIPO_EN = dict(ev.TIPOS)
TIPO_EN.update({"Zapatos de vestir": "a pair of dress shoes", "Zapatos planos de vestir": "a pair of dress shoes"})
CAT_EN = {"shirt, blouse": "a shirt or blouse", "top, t-shirt, sweatshirt": "a t-shirt, top or sweatshirt", "sweater": "a sweater", "cardigan": "a cardigan", "jacket": "a jacket",
          "vest": "a vest", "pants": "a pair of pants", "shorts": "a pair of shorts", "skirt": "a skirt", "coat": "a coat", "dress": "a dress", "jumpsuit": "a jumpsuit", "cape": "a cape"}
PAQUETES = {"fashionpedia": ("tfm-prendas-fashionpedia-vlm", "TFM prendas Fashionpedia VLM"), "victor": ("tfm-prendas-victor-vlm", "TFM prendas Victor VLM (privado)")}


def guardar_reducida(origen: Path, destino: Path, caja):
    """Guarda la foto con el lado largo <= LADO_MAX y devuelve la caja en las coordenadas de la foto guardada."""
    im = Image.open(origen).convert("RGB")
    W, H = im.size
    s = min(1.0, LADO_MAX / max(W, H))
    if s < 1:
        im = im.resize((round(W * s), round(H * s)), Image.LANCZOS)
    im.save(destino, quality=90)
    return [round(c * s, 1) for c in caja]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", choices=sorted(PAQUETES), required=True)
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--etiquetas", type=Path, default=ev.BASE / "etiquetas_prendas.json")
    ap.add_argument("--fotos", type=Path, default=ev.BASE / "cache" / "img")
    ap.add_argument("--fashionpedia", type=Path, default=Path.home() / "datos_tfm" / "fashionpedia")
    ap.add_argument("--por-estampado", type=int, default=30)
    ap.add_argument("--por-forma", type=int, default=40)
    a = ap.parse_args()
    a.salida.mkdir(parents=True, exist_ok=True)
    tmp = a.salida / "_fotos"
    tmp.mkdir(exist_ok=True)
    manifiesto = []

    # ---- recortes etiquetados por Víctor: solo foto, caja y tipo (lo demás se mide en local)
    etiq = {k: v for k, v in json.loads(a.etiquetas.read_text(encoding="utf-8")).items() if v.get("prendas")} if a.origen == "victor" else {}
    for k in sorted(etiq):
        nombre = f"{k.split('#')[0]}.jpg"
        destino = f"v_{nombre}"
        caja = guardar_reducida(a.fotos / nombre, tmp / destino, etiq[k]["caja"])
        tipo = etiq[k]["prendas"][0].get("tipo") or etiq[k]["tipo_modelo"]
        manifiesto.append({"id": f"v:{k}", "origen": "victor", "foto": destino, "caja": caja, "tipo": tipo, "tipo_en": TIPO_EN.get(tipo, tipo)})
    if a.origen == "victor":
        print(f"Víctor: {len(manifiesto)} recortes de {len({m['foto'] for m in manifiesto})} fotos")

    # ---- muestra equilibrada de Fashionpedia val
    if a.origen == "fashionpedia":
        va = fp.items_de(a.fashionpedia, "val", min_lado=120)
        rnd = random.Random(11)
        elegidos = {}
        for campo, n in (("estampado", a.por_estampado), ("forma", a.por_forma)):
            por = collections.defaultdict(list)
            for it in va:
                if it[campo]:
                    por[it[campo]].append(it)
            for clase, lista in sorted(por.items()):
                rnd.shuffle(lista)
                for it in lista[:n]:
                    elegidos[it["id"]] = it
        for it in sorted(elegidos.values(), key=lambda x: x["id"]):
            destino = f"f_{it['grupo']}.jpg"
            caja = guardar_reducida(it["imagen"], tmp / destino, it["caja"]) if not (tmp / destino).exists() else None
            if caja is None:   # la foto ya se guardó para otra prenda: se recalcula la escala
                W, H = Image.open(it["imagen"]).size
                s = min(1.0, LADO_MAX / max(W, H))
                caja = [round(c * s, 1) for c in it["caja"]]
            manifiesto.append({"id": f"f:{it['id']}", "origen": "fashionpedia", "foto": destino, "caja": caja, "tipo": it["categoria"], "tipo_en": CAT_EN.get(it["categoria"], it["categoria"]),
                               "estampado": it["estampado"], "forma": it["forma"]})
        for campo in ("estampado", "forma"):
            c = collections.Counter(m[campo] for m in manifiesto if m["origen"] == "fashionpedia" and m.get(campo))
            print(f"Fashionpedia {campo}: {dict(c.most_common())}")
        print(f"Fashionpedia: {sum(m['origen'] == 'fashionpedia' for m in manifiesto)} prendas de {len({m['foto'] for m in manifiesto if m['origen'] == 'fashionpedia'})} fotos")

    # ---- paquete
    with zipfile.ZipFile(a.salida / "fotos.zip", "w", zipfile.ZIP_STORED) as z:
        for f in sorted(tmp.glob("*.jpg")):
            z.write(f, f.name)
    (a.salida / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False), encoding="utf-8")
    slug, titulo = PAQUETES[a.origen]
    (a.salida / "dataset-metadata.json").write_text(json.dumps({"title": titulo, "id": f"victor871/{slug}", "licenses": [{"name": "other"}],
                                                                 "description": "Privado. Fotos de prueba del TFM (UC3M) para medir un modelo de lenguaje y visión; se borra al terminar."}, ensure_ascii=False, indent=1), encoding="utf-8")
    for f in tmp.glob("*.jpg"):
        f.unlink()
    tmp.rmdir()
    mb = (a.salida / "fotos.zip").stat().st_size / 1e6
    print(f"Listo en {a.salida}: {len(manifiesto)} prendas, fotos.zip {mb:.1f} MB")


if __name__ == "__main__":
    main()
