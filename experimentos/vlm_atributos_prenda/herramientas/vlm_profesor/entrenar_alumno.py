#!/usr/bin/env python3
"""
El «alumno»: una capa pequeña (regresión logística) sobre los embeddings de CLIP, entrenada con lo que etiquetó el profesor (`kernel_profesor.py`, configuración «profesor») sobre prendas
públicas de Fashionpedia train, y medida con las etiquetas de Víctor, que NO se suben a ningún sitio ni se usan para entrenar: sus fotos y etiquetas se quedan en este ordenador.

Qué mide, frente a lo que había:
  tipo (29 tipos de Víctor)   el flujo semanal acierta 19 de 38 con la prenda principal (24 de 38 con «cualquiera», 29 de 38 por familia)
  estampado, tejido, forma    «decir siempre lo más frecuente» y la capa entrenada con las etiquetas propias de Fashionpedia (12-13 de 22, 6 de 17, 4-9 de 23)

Uso:  python3 entrenar_alumno.py --profesor DIR/pred_qwen3vl8b_profesor.jsonl [--modelo ViT-L-14 --pesos ~/datos_tfm/modelos/ViT-L-14.pt --etiqueta l14] [--salida ../../resultados/alumno_….json]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI.parents[2] / "analisis_mercado"))
import evaluar_etiquetas_prendas as ev  # noqa: E402
import entrenar_atributos_fashionpedia as fp  # noqa: E402

DATOS_FP = Path.home() / "datos_tfm" / "fashionpedia"
EQ = {"Hoodie": "Sudadera"}
CAMPOS = ("tipo29", "estampado", "tejido", "forma")


def embeddings_victor(claves, etiq, modelo, pesos, etiqueta):
    """Embeddings CLIP de los recortes de Víctor (solo se guardan los números, en ~/datos_tfm; las fotos no salen de cache/)."""
    cache = Path.home() / "datos_tfm" / f"victor_emb_{etiqueta}.npz"
    previo = {}
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        previo = dict(zip(z["ids"].tolist(), z["E"]))
    faltan = [k for k in claves if k not in previo]
    if faltan:
        import torch
        torch.set_grad_enabled(False)
        model, prep, _ = ev.pc.cargar(modelo, pesos)
        for k in faltan:
            v = model.encode_image(prep(ev.recorte(ev.BASE / "cache" / "img" / f"{k.split('#')[0]}.jpg", etiq[k]["caja"])).unsqueeze(0))
            previo[k] = (v / v.norm(dim=-1, keepdim=True)).numpy()[0]
        np.savez(cache, ids=np.array(list(previo)), E=np.array(list(previo.values())))
    return np.array([previo[k] for k in claves])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profesor", type=Path, required=True, help="pred_<modelo>_profesor.jsonl con tipo29, estampado, tejido y forma")
    ap.add_argument("--modelo")
    ap.add_argument("--pesos")
    ap.add_argument("--etiqueta", default="b32")
    ap.add_argument("--etiquetas", type=Path, default=ev.BASE / "etiquetas_prendas.json")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args()
    fp.MODELO.update(modelo=a.modelo, pesos=a.pesos)

    filas = [json.loads(linea) for linea in open(a.profesor, encoding="utf-8")]
    ids = [r["id"][2:] for r in filas]   # «f:train123» -> «train123»
    print(f"{len(filas)} prendas etiquetadas por el profesor", flush=True)
    # ---- imágenes y cajas originales de esas prendas (el paquete subido iba reducido) y sus embeddings
    ropa = [c["name"] for c in json.loads((DATOS_FP / "instances_attributes_val2020.json").read_text(encoding="utf-8"))["categories"][:13]]
    todos = {it["id"]: it for it in fp.items_de(DATOS_FP, "train", min_lado=100, categorias=ropa + ["hat", "shoe", "bag, wallet"])}
    items = [todos[i] for i in ids if i in todos]
    X = fp.embeber(items, DATOS_FP / f"emb_alumno_{a.etiqueta}.npz")
    por_id = dict(zip([it["id"] for it in items], range(len(items))))
    # ---- etiquetas de Víctor (solo para medir)
    etiq = {k: v for k, v in json.loads(a.etiquetas.read_text(encoding="utf-8")).items() if v.get("prendas")}
    claves = sorted(etiq)
    EV = embeddings_victor(claves, etiq, a.modelo, a.pesos, a.etiqueta)
    res = {"prendas_del_profesor": len(filas), "campos": {}}

    for campo in CAMPOS:
        pares = [(por_id[r["id"][2:]], r.get(campo)) for r in filas if r["id"][2:] in por_id and r.get(campo)]
        # el tipo del profesor solo se usa si encaja con la categoría de Fashionpedia (descarta contradicciones evidentes)
        if campo == "tipo29":
            ok = {"pants": {"Pantalón", "Legging/Malla"}, "shorts": {"Short"}, "skirt": {"Falda"}, "dress": {"Vestido", "Mono"}, "jumpsuit": {"Mono", "Vestido"}, "hat": {"Gorra/Gorro/Sombrero"},
                  "shoe": {"Zapatillas deportivas", "Zapatillas casual/lifestyle", "Zapatos de vestir", "Zapatos de tacón", "Sandalias", "Botas"}, "bag, wallet": {"Bolso", "Riñonera"}}
            antes = len(pares)
            pares = [(i, t) for i, t in pares if items[i]["categoria"] not in ok or t in ok[items[i]["categoria"]]]
            print(f"tipo: {antes - len(pares)} prendas descartadas por contradecir la categoría de Fashionpedia", flush=True)
        if not pares:
            continue
        idx, y = zip(*pares)
        y = np.array([EQ.get(v, v) if campo == "tipo29" else v for v in y])
        dist = collections.Counter(y.tolist())
        m = LogisticRegression(C=2.0, max_iter=4000, class_weight="balanced").fit(X[list(idx)], y)
        pred = m.predict(EV)
        # verdad de Víctor
        if campo == "tipo29":
            prin = [(i, EQ.get(etiq[k]["prendas"][0]["tipo"], etiq[k]["prendas"][0]["tipo"])) for i, k in enumerate(claves) if etiq[k]["prendas"][0].get("tipo")]
            cual = [(i, {EQ.get(q["tipo"], q["tipo"]) for q in etiq[k]["prendas"] if q.get("tipo")}) for i, k in enumerate(claves)]
        else:
            prin = [(i, etiq[k]["prendas"][0].get(campo)) for i, k in enumerate(claves) if etiq[k]["prendas"][0].get(campo) and etiq[k]["prendas"][0].get(campo) != "no aplica"]
            cual = [(i, {q.get(campo) for q in etiq[k]["prendas"]} - {None, "no aplica"}) for i, k in enumerate(claves)]
        cual = [(i, s) for i, s in cual if s]
        frec = collections.Counter(v for _, v in prin).most_common(1)[0]
        r = {"entrenamiento": len(y), "clases": dict(dist.most_common()),
             "principal": [int(sum(pred[i] == v for i, v in prin)), len(prin)], "cualquiera": [int(sum(pred[i] in s for i, s in cual)), len(cual)],
             "siempre_la_mas_frecuente": [frec[0], frec[1], len(prin)],
             "no_mayoritarias_acertadas": [int(sum(pred[i] == v for i, v in prin if v != frec[0])), sum(v != frec[0] for _, v in prin)]}
        if campo == "tipo29":
            fam = lambda t: kp_familia(t)   # noqa: E731
            r["familia_principal"] = [int(sum(fam(pred[i]) == fam(v) for i, v in prin)), len(prin)]
        res["campos"][campo] = r
        extra = f" | familia {r['familia_principal'][0]}/{r['familia_principal'][1]}" if "familia_principal" in r else ""
        print(f"{campo:<10} entrenado con {len(y)} prendas | principal {r['principal'][0]}/{r['principal'][1]} | cualquiera {r['cualquiera'][0]}/{r['cualquiera'][1]}{extra} | "
              f"más frecuente «{frec[0]}» {frec[1]}/{len(prin)} | no mayoritarias {r['no_mayoritarias_acertadas'][0]}/{r['no_mayoritarias_acertadas'][1]}", flush=True)
    if a.salida:
        a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


def kp_familia(tipo):
    import tendencia_prenda as tp   # noqa: PLC0415 (importa mercado.py: solo para leer FAMILIA)
    return tp.FAMILIA.get(tipo, "Otros")


if __name__ == "__main__":
    main()
