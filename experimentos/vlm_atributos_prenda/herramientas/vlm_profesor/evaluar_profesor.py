#!/usr/bin/env python3
"""
Mide lo que devolvió el kernel del «profesor» (`kernel_profesor.py`, bajado con `kaggle_ops.py bajar`) en dos exámenes:

  1. Fashionpedia (público, muestra equilibrada por clase): acierto y recall por clase de estampado y forma, junto a la capa pequeña sobre CLIP B/32
     entrenada con Fashionpedia (`entrenar_atributos_fashionpedia.py`) sobre las MISMAS prendas, y a «decir siempre la clase más frecuente de la muestra».
  1b. El tipo de prenda (configuraciones `tipo_*`): acierto del modelo grande frente a CLIP B/32 sin entrenar sobre las mismas prendas y las mismas 13 categorías.
  2. Las etiquetas de Víctor (si se subieron sus fotos): acierto en la prenda principal y en cualquiera de sus prendas, contra «decir siempre lo más frecuente»
     de sus etiquetas. Con tan pocas etiquetas (22 o 23 por atributo) el error típico es de ±10 puntos.

Uso:  python3 evaluar_profesor.py --pred DIR_SALIDA --manifiesto DIR_DATASET_FASHIONPEDIA/manifiesto.json [--salida resultados/profesor_….json] [--sin-cabeza]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import evaluar_etiquetas_prendas as ev  # noqa: E402
import entrenar_atributos_fashionpedia as fp  # noqa: E402
import kernel_profesor as kp  # noqa: E402  (solo sus vocabularios)

DATOS_FP = Path.home() / "datos_tfm" / "fashionpedia"


def leer_predicciones(carpeta: Path):
    preds = {}
    for f in sorted(carpeta.glob("pred_*.jsonl")):
        for linea in open(f, encoding="utf-8"):
            r = json.loads(linea)
            preds.setdefault((r["modelo"], r["config"]), {})[r["id"]] = r
    return preds


def predicciones_cabeza(ids_val):
    """Capa pequeña (regresión logística) sobre CLIP B/32 entrenada con Fashionpedia train, aplicada a las prendas de val dadas. Devuelve {campo: {id: clase}}."""
    from sklearn.linear_model import LogisticRegression
    cache_et = DATOS_FP / "etiquetas_train_b32.json"
    z = np.load(DATOS_FP / "emb_train_b32.npz", allow_pickle=False)
    emb_tr = dict(zip(z["ids"].tolist(), z["E"]))
    if cache_et.exists():
        etiquetas = json.loads(cache_et.read_text(encoding="utf-8"))
    else:
        print("leyendo anotaciones de train (una vez, ~2 min)…", flush=True)
        etiquetas = {it["id"]: {c: it[c] for c in fp.CAMPOS} for it in fp.items_de(DATOS_FP, "train") if it["id"] in emb_tr}
        cache_et.write_text(json.dumps(etiquetas, ensure_ascii=False), encoding="utf-8")
    zv = np.load(DATOS_FP / "emb_val_b32.npz", allow_pickle=False)
    emb_va = dict(zip(zv["ids"].tolist(), zv["E"]))
    salida = {}
    for campo in fp.CAMPOS:
        idx = [i for i in emb_tr if etiquetas.get(i, {}).get(campo)]
        m = LogisticRegression(C=2.0, max_iter=3000, class_weight="balanced").fit(np.array([emb_tr[i] for i in idx]), [etiquetas[i][campo] for i in idx])
        pedidos = [i for i in ids_val if i in emb_va]
        salida[campo] = dict(zip(pedidos, m.predict(np.array([emb_va[i] for i in pedidos])).tolist()))
    return salida


def metrica(pares):
    """pares: [(verdad, predicción)] -> acierto, recall medio por clase y recall por clase."""
    por = collections.defaultdict(lambda: [0, 0])
    for v, p in pares:
        por[v][1] += 1
        por[v][0] += (v == p)
    n = sum(b for _, b in por.values())
    ok = sum(a for a, _ in por.values())
    return {"acierto": [ok, n], "recall_medio": round(float(np.mean([a / b for a, b in por.values()])), 3) if por else None, "por_clase": {k: v for k, v in sorted(por.items())}}


def medir_fashionpedia(preds, manifiesto, cabeza):
    items = {m["id"]: m for m in manifiesto if m["origen"] == "fashionpedia"}
    filas = []
    for (modelo, cfg), pr in sorted(preds.items()):
        if cfg.startswith("tipo_"):
            continue
        for campo in fp.CAMPOS:
            ids = [i for i in pr if i in items and items[i].get(campo)]
            if not ids:
                continue
            fila = {"modelo": modelo, "config": cfg, "campo": campo, "vlm": metrica([(items[i][campo], pr[i].get(campo)) for i in ids])}
            fila["sin_respuesta_valida"] = sum(pr[i].get(campo) is None for i in ids)
            if cabeza:
                fila["cabeza_clip"] = metrica([(items[i][campo], cabeza[campo].get(i)) for i in ids])
            frec = collections.Counter(items[i][campo] for i in ids).most_common(1)[0]
            fila["siempre_la_mas_frecuente"] = [frec[0], frec[1], len(ids)]
            filas.append(fila)
    return filas


def clip_cero_disparos_fp(ids_val):
    """CLIP B/32 sin entrenar elige entre las 13 categorías de Fashionpedia (mismos recortes que el modelo grande: los embeddings guardados de val)."""
    import torch
    torch.set_grad_enabled(False)
    model, _, tok = ev.pc.cargar(None, None)
    t = model.encode_text(tok(["a photo of " + en for _, en in kp.TIPOS_FP]))
    T = (t / t.norm(dim=-1, keepdim=True)).numpy()
    zv = np.load(DATOS_FP / "emb_val_b32.npz", allow_pickle=False)
    emb = dict(zip(zv["ids"].tolist(), zv["E"]))
    return {i: kp.TIPOS_FP[int(np.argmax(emb[i] @ T.T))][0] for i in ids_val if i in emb}


def medir_tipo_fashionpedia(preds, manifiesto):
    items = {m["id"]: m for m in manifiesto if m["origen"] == "fashionpedia"}
    ids_val = [i[2:] for i in items]
    clip = {"f:" + i: v for i, v in clip_cero_disparos_fp(ids_val).items()}
    filas = []
    for (modelo, cfg), pr in sorted(preds.items()):
        if not cfg.startswith("tipo_"):
            continue
        ids = [i for i in pr if i in items]
        ok = sum(pr[i].get("tipo") == items[i]["tipo"] for i in ids)
        ok_clip = sum(clip.get(i) == items[i]["tipo"] for i in ids)
        frec = collections.Counter(items[i]["tipo"] for i in ids).most_common(1)[0]
        filas.append({"modelo": modelo, "config": cfg, "vlm": [ok, len(ids)], "clip_b32": [ok_clip, len(ids)], "siempre_la_mas_frecuente": [frec[0], frec[1], len(ids)],
                      "sin_respuesta_valida": sum(pr[i].get("tipo") is None for i in ids)})
    return filas


def medir_tipo_victor(preds, etiq):
    filas = []
    for (modelo, cfg), pr in sorted(preds.items()):
        if not (cfg.startswith("tipo_") or cfg.startswith("profesor")):
            continue
        clave_tipo = "tipo29" if cfg.startswith("profesor") else "tipo"
        claves = [i[2:] for i in pr if i.startswith("v:") and i[2:] in etiq and etiq[i[2:]]["prendas"][0].get("tipo")]
        eq = lambda t: {"Hoodie": "Sudadera"}.get(t, t)   # noqa: E731
        princ = sum(eq(pr["v:" + k].get(clave_tipo)) == eq(etiq[k]["prendas"][0]["tipo"]) for k in claves)
        cual = sum(eq(pr["v:" + k].get(clave_tipo)) in {eq(q["tipo"]) for q in etiq[k]["prendas"] if q.get("tipo")} for k in claves)
        fam = sum(kp_familia(pr["v:" + k].get(clave_tipo)) == kp_familia(etiq[k]["prendas"][0]["tipo"]) for k in claves)
        filas.append({"modelo": modelo, "config": cfg, "principal": [princ, len(claves)], "cualquiera": [cual, len(claves)], "familia_principal": [fam, len(claves)]})
    return filas


def kp_familia(tipo):
    sys.path.insert(0, str(AQUI.parents[2] / "analisis_mercado"))
    import tendencia_prenda as tp   # noqa: PLC0415 (importa mercado.py)
    return tp.FAMILIA.get(tipo, "Otros")


def medir_victor(preds, etiq):
    filas = []
    for (modelo, cfg), pr in sorted(preds.items()):
        if cfg.startswith("tipo_"):
            continue
        for campo in ("estampado", "tejido", "forma"):
            claves = [i[2:] for i in pr if i.startswith("v:") and i[2:] in etiq]
            principal = [(k, etiq[k]["prendas"][0].get(campo)) for k in claves if etiq[k]["prendas"][0].get(campo) and etiq[k]["prendas"][0].get(campo) != "no aplica"]
            cualquiera = [(k, {q.get(campo) for q in etiq[k]["prendas"]} - {None, "no aplica"}) for k in claves]
            cualquiera = [(k, s) for k, s in cualquiera if s]
            if not principal:
                continue
            frec = collections.Counter(v for _, v in principal).most_common(1)[0]
            frec_any = collections.Counter(v for _, s in cualquiera for v in s).most_common(1)[0][0]
            filas.append({"modelo": modelo, "config": cfg, "campo": campo,
                          "principal": [sum(pr["v:" + k].get(campo) == v for k, v in principal), len(principal)],
                          "cualquiera": [sum(pr["v:" + k].get(campo) in s for k, s in cualquiera), len(cualquiera)],
                          "siempre_la_mas_frecuente": [frec[0], frec[1], len(principal)],
                          "siempre_la_mas_frecuente_cualquiera": [frec_any, sum(frec_any in s for _, s in cualquiera), len(cualquiera)],
                          "no_mayoritarias_acertadas": [sum(pr["v:" + k].get(campo) == v for k, v in principal if v != frec[0]), sum(v != frec[0] for _, v in principal)]})
    return filas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pred", type=Path, required=True, help="carpeta con pred_*.jsonl bajada del kernel")
    ap.add_argument("--manifiesto", type=Path, help="manifiesto.json del paquete de Fashionpedia (lleva sus etiquetas)")
    ap.add_argument("--etiquetas", type=Path, default=ev.BASE / "etiquetas_prendas.json")
    ap.add_argument("--sin-cabeza", action="store_true", help="no calcular la capa sobre CLIP en las mismas prendas")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args()
    preds = leer_predicciones(a.pred)
    print("configuraciones:", {f"{m}/{c}": len(p) for (m, c), p in preds.items()})
    res = {}
    if a.manifiesto:
        man = json.loads(a.manifiesto.read_text(encoding="utf-8"))
        ids = [m["id"] for m in man if m["origen"] == "fashionpedia"]
        cabeza = None if a.sin_cabeza else predicciones_cabeza([i[2:] for i in ids])
        if cabeza:
            cabeza = {c: {"f:" + i: v for i, v in d.items()} for c, d in cabeza.items()}
        res["fashionpedia"] = medir_fashionpedia(preds, man, cabeza)
        print("\n== Fashionpedia (muestra equilibrada por clase) ==")
        for f in res["fashionpedia"]:
            v = f["vlm"]
            extra = f" | capa CLIP {f['cabeza_clip']['acierto'][0]}/{f['cabeza_clip']['acierto'][1]} (recall medio {f['cabeza_clip']['recall_medio']})" if "cabeza_clip" in f else ""
            print(f"{f['modelo']:>10}/{f['config']:<11} {f['campo']:<9} acierto {v['acierto'][0]}/{v['acierto'][1]} ({v['acierto'][0] / v['acierto'][1]:.0%}) recall medio {v['recall_medio']}"
                  f"{extra} | más frecuente {f['siempre_la_mas_frecuente'][0]} {f['siempre_la_mas_frecuente'][1]}/{f['siempre_la_mas_frecuente'][2]} | sin respuesta válida {f['sin_respuesta_valida']}")
    if a.manifiesto and any(c.startswith("tipo_") for _, c in preds):
        res["tipo_fashionpedia"] = medir_tipo_fashionpedia(preds, man)
        print("\n== Tipo de prenda en Fashionpedia (13 categorías; el modelo no sabe cuál es la prenda) ==")
        for f in res["tipo_fashionpedia"]:
            print(f"{f['modelo']:>10}/{f['config']:<13} modelo grande {f['vlm'][0]}/{f['vlm'][1]} ({f['vlm'][0] / f['vlm'][1]:.0%}) | CLIP B/32 {f['clip_b32'][0]}/{f['clip_b32'][1]} ({f['clip_b32'][0] / f['clip_b32'][1]:.0%})"
                  f" | más frecuente {f['siempre_la_mas_frecuente'][0]} {f['siempre_la_mas_frecuente'][1]}/{f['siempre_la_mas_frecuente'][2]} | sin respuesta válida {f['sin_respuesta_valida']}")
    if any(i.startswith("v:") for p in preds.values() for i in p):
        etiq = {k: v for k, v in json.loads(a.etiquetas.read_text(encoding="utf-8")).items() if v.get("prendas")}
        if any(c.startswith("tipo_") or c.startswith("profesor") for _, c in preds):
            res["tipo_victor"] = medir_tipo_victor(preds, etiq)
            print("\n== Tipo de prenda: etiquetas de Víctor (el flujo semanal: 19 de 38 principal, 24 de 38 cualquiera, 29 de 38 familia) ==")
            for f in res["tipo_victor"]:
                print(f"{f['modelo']:>10}/{f['config']:<13} principal {f['principal'][0]}/{f['principal'][1]} | cualquiera {f['cualquiera'][0]}/{f['cualquiera'][1]} | familia {f['familia_principal'][0]}/{f['familia_principal'][1]}")
        res["victor"] = medir_victor(preds, etiq)
        print("\n== Etiquetas de Víctor (estampado, tejido y forma) ==")
        for f in res["victor"]:
            print(f"{f['modelo']:>10}/{f['config']:<11} {f['campo']:<9} principal {f['principal'][0]}/{f['principal'][1]} | cualquiera {f['cualquiera'][0]}/{f['cualquiera'][1]} | "
                  f"más frecuente «{f['siempre_la_mas_frecuente'][0]}» {f['siempre_la_mas_frecuente'][1]}/{f['siempre_la_mas_frecuente'][2]} | no mayoritarias acertadas {f['no_mayoritarias_acertadas'][0]}/{f['no_mayoritarias_acertadas'][1]}")
    if a.salida:
        a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
