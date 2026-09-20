#!/usr/bin/env python3
"""
Analiza las revisiones humanas de la app "Ficha de Prenda" frente a (a) las
etiquetas de Kaggle con las que se entreno y (b) las predicciones del modelo.

Entrada: los documentos de la coleccion `revisiones` de la app exportados a JSON
(un unico fichero {id: documento}, como data/revision_humana/revisiones_app_n*.json,
o una carpeta con un JSON por ficha, que es lo que da ArtifactData `list` + `out_dir`),
el manifest de la app (etiquetas originales de Kaggle) y las predicciones del modelo.

Convencion de acierto con etiquetas multiseleccion: la prediccion del modelo
(que da UN valor por campo) cuenta como correcta si cae dentro del conjunto
que marco el revisor.

Uso:
    python3 analizar_revision_humana.py \
        --revisiones ../data/revision_humana/revisiones_app_n100_2026-09-20.json \
        [--json-salida resumen.json]
"""
import argparse
import collections
import glob
import json
from pathlib import Path

CAMPOS = ["categoria", "color_primario", "genero", "temporada", "grupo_estilo"]
MULTI = ["color_primario", "genero", "temporada", "grupo_estilo"]


def S(v):
    return set(v) if isinstance(v, list) else {v}


def cargar_revisiones(ruta):
    ruta = Path(ruta).expanduser()
    if ruta.is_file():
        return {str(i): d.get("data", d) for i, d in json.load(open(ruta, encoding="utf-8")).items()}
    revs = {}
    for p in glob.glob(str(ruta / "*.json")):
        d = json.load(open(p, encoding="utf-8"))
        revs[Path(p).stem] = d.get("data", d)
    return revs


def main():
    ap = argparse.ArgumentParser()
    datos = Path(__file__).parent.parent / "data" / "revision_humana"
    ap.add_argument("--revisiones", required=True, help="Fichero {id: doc} o carpeta con un JSON por ficha.")
    ap.add_argument("--manifest", default=str(datos / "manifest_app_120.json"))
    ap.add_argument("--predicciones", default=str(datos / "predicciones_app_120.json"))
    ap.add_argument("--json-salida")
    args = ap.parse_args()

    manifest = {str(m["id"]): m for m in json.load(open(Path(args.manifest).expanduser(), encoding="utf-8"))}
    pred = json.load(open(args.predicciones, encoding="utf-8"))
    revs = cargar_revisiones(args.revisiones)
    ids = sorted(revs, key=int)
    n = len(ids)
    resumen = {"n_revisadas": n, "n_muestra": len(manifest)}

    exactas = sum(1 for i in ids if revs[i]["coincide_original"])
    resumen["coincide_exacto_kaggle"] = exactas
    print(f"Fichas revisadas: {n}/{len(manifest)}")
    print(f"Coinciden exactamente con Kaggle en los 5 campos: {exactas}/{n} = {exactas / n:.0%}\n")

    # 1) humano vs Kaggle por campo
    print("1) Humano vs Kaggle, por campo")
    print(f"   {'campo':<16} {'igual':>6} {'anade':>7} {'cambia':>7}   acuerdo(orig en tu seleccion)")
    resumen["humano_vs_kaggle"] = {}
    for c in CAMPOS:
        igual = anade = cambia = 0
        for i in ids:
            orig, hum = manifest[i][c], S(revs[i][c])
            if hum == {orig}:
                igual += 1
            elif orig in hum:
                anade += 1
            else:
                cambia += 1
        resumen["humano_vs_kaggle"][c] = {"igual": igual, "anade": anade, "cambia": cambia}
        print(f"   {c:<16} {igual:>6} {anade:>7} {cambia:>7}   {(igual + anade) / n:.0%}")

    # 2) uso de multiseleccion
    print("\n2) Cuanto usas la multiseleccion (fichas con >1 valor)")
    resumen["multiseleccion"] = {}
    for c in MULTI:
        k = sum(1 for i in ids if len(S(revs[i][c])) > 1)
        resumen["multiseleccion"][c] = k
        print(f"   {c:<16} {k}/{n} = {k / n:.0%}")

    # 3) modelo vs Kaggle y vs humano
    print("\n3) Acierto del modelo (n = fichas revisadas con prediccion valida)")
    print(f"   {'campo':<16} {'vs Kaggle':>10} {'vs humano':>10}")
    resumen["modelo"] = {}
    validas = [i for i in ids if pred.get(i)]
    for c in CAMPOS:
        ok_k = sum(1 for i in validas if pred[i].get(c) == manifest[i][c])
        ok_h = sum(1 for i in validas if pred[i].get(c) in S(revs[i][c]))
        resumen["modelo"][c] = {"vs_kaggle": ok_k, "vs_humano": ok_h, "n": len(validas)}
        print(f"   {c:<16} {ok_k / len(validas):>10.0%} {ok_h / len(validas):>10.0%}")
    media_k = sum(resumen["modelo"][c]["vs_kaggle"] for c in CAMPOS) / (5 * len(validas))
    media_h = sum(resumen["modelo"][c]["vs_humano"] for c in CAMPOS) / (5 * len(validas))
    resumen["modelo"]["media"] = {"vs_kaggle": media_k, "vs_humano": media_h}
    print(f"   {'MEDIA':<16} {media_k:>10.0%} {media_h:>10.0%}")

    # 4) temporada: lo que Kaggle dice vs lo que marcas
    print("\n4) temporada: Kaggle -> humano")
    cnt = collections.Counter()
    for i in ids:
        cnt[(manifest[i]["temporada"], "+".join(sorted(S(revs[i]["temporada"]))))] += 1
    for (o, h), k in cnt.most_common():
        print(f"   {o:<17} -> {h:<28} x{k}")
    todo = sum(1 for i in ids if "todo_el_ano" in S(revs[i]["temporada"]))
    resumen["temporada_todo_el_ano"] = todo
    print(f"   Fichas con 'todo el año' entre tus valores: {todo}/{n} = {todo / n:.0%}")

    # 5) por tipo de prenda: como etiquetas cada uno
    print("\n5) Por tipo de prenda (articleType): tu criterio")
    por_tipo = collections.defaultdict(list)
    for i in ids:
        por_tipo[manifest[i]["articleType"]].append(i)
    ABR = {"primavera_verano": "PV", "otono_invierno": "OI", "todo_el_ano": "TODO"}
    for t in sorted(por_tipo, key=lambda x: -len(por_tipo[x])):
        lst = por_tipo[t]
        temp = collections.Counter("+".join(ABR[x] for x in sorted(S(revs[i]["temporada"]))) for i in lst)
        est = collections.Counter("+".join(sorted(S(revs[i]["grupo_estilo"]))) for i in lst)
        print(f"   {t:<14} n={len(lst):<2} temporada={dict(temp)}  estilo={dict(est)}")

    # 6) estilos que eliges a la vez
    print("\n6) Combinaciones de grupo_estilo que marcas juntas")
    comb = collections.Counter("+".join(sorted(S(revs[i]["grupo_estilo"]))) for i in ids if len(S(revs[i]["grupo_estilo"])) > 1)
    for k, v in comb.most_common():
        print(f"   {k}: {v}")

    # 7) casos donde el modelo no coincide contigo (para revisar a mano)
    print("\n7) El modelo NO cae dentro de tu seleccion (excluyendo temporada)")
    mis = []
    for i in validas:
        for c in CAMPOS:
            if c == "temporada":
                continue
            if pred[i].get(c) not in S(revs[i][c]):
                mis.append((i, c))
                m = manifest[i]
                print(f"   {i:<6} {m['productDisplayName'][:36]:<38} {c:<14} modelo={pred[i].get(c)!s:<14} tu={sorted(S(revs[i][c]))} kaggle={m[c]}")
    resumen["desacuerdos_no_temporada"] = [{"id": i, "campo": c} for i, c in mis]

    if args.json_salida:
        Path(args.json_salida).write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nResumen guardado en {args.json_salida}")


if __name__ == "__main__":
    main()
