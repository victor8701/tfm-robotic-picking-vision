#!/usr/bin/env python3
"""
Estadisticas del prototipo de looks completos (salida de analizar_outfit.py)
frente a la lectura "foto entera" del clasificador de prenda unica
(predecir_lote.py sobre las mismas fotos), con o sin auditoria manual.

Bloque automatico (no necesita etiquetas):
  - cuantas personas / prendas se detectan, con que origen de caja;
  - acuerdo categoria del detector vs categoria del clasificador (mide si los
    recortes "se parecen" a lo que el clasificador vio al entrenar);
  - distribucion de categoria / temporada / color / estilo, recortes vs foto entera.

Bloque de auditoria (--auditoria, JSON hecho a mano mirando las fotos anotadas;
ver data/revision_humana/auditoria_outfit_calle.json):
  - precision de las cajas ("ok"/"parcial"/"mal"), acierto de color en cajas ok,
  - prendas basicas visibles que no se detectaron (recall),
  - estilo del outfit dentro del conjunto de estilos aceptables, vs foto entera.

Uso:
    python3 resumen_outfit.py --outfits outfits.json --foto-entera ../data/revision_humana/predicciones_fotos_calle.json \
        [--auditoria ../data/revision_humana/auditoria_outfit_calle.json] [--json-salida resumen.json]
"""
import argparse
import collections
import json
from pathlib import Path

BASICAS = ["ropa_superior", "ropa_inferior", "cuerpo_entero", "abrigo", "calzado"]


def pct(a, b):
    return f"{a}/{b} = {a / b:.0%}" if b else "0/0"


def distribucion(valores, titulo):
    c = collections.Counter(valores)
    total = sum(c.values())
    print(f"   {titulo}: " + ", ".join(f"{k} {v} ({v / total:.0%})" for k, v in c.most_common()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outfits", required=True)
    ap.add_argument("--foto-entera", required=True)
    ap.add_argument("--auditoria")
    ap.add_argument("--json-salida")
    args = ap.parse_args()

    outfits = json.load(open(args.outfits, encoding="utf-8"))
    entera = json.load(open(args.foto_entera, encoding="utf-8"))
    # acepta {foto: {campos}} (predicciones_fotos_calle.json) y {foto: {"prediccion": {campos}}} (predecir_lote.py)
    entera = {f: (v.get("prediccion") if "prediccion" in v else v) for f, v in entera.items()}
    aud = json.load(open(args.auditoria, encoding="utf-8")) if args.auditoria else None
    fotos = sorted(outfits)
    resumen = {"n_fotos": len(fotos)}

    personas = [(f, k, p) for f in fotos for k, p in enumerate(outfits[f]["personas"])]
    prendas = [(f, k, pr) for f, k, p in personas for pr in p["prendas"]]
    con_attr = [(f, k, pr) for f, k, pr in prendas if pr.get("atributos")]
    print(f"Fotos: {len(fotos)}   personas detectadas: {len(personas)}   prendas: {len(prendas)} "
          f"({len(prendas) / len(personas):.1f} por persona)   con atributos: {len(con_attr)}")
    resumen.update(n_personas=len(personas), n_prendas=len(prendas))

    print("\n1) Detector")
    porcat = collections.Counter(pr["categoria"] for _, _, pr in prendas)
    print("   prendas por categoria:", dict(porcat.most_common()))
    origen = collections.Counter(pr["origen"] for _, _, pr in prendas)
    print("   origen de la caja:", dict(origen.most_common()))
    resumen.update(prendas_por_categoria=dict(porcat), origen_caja=dict(origen))
    for cat in ["ropa_superior", "ropa_inferior", "cuerpo_entero", "abrigo", "calzado"]:
        k = sum(1 for _, _, p in personas if any(pr["categoria"] == cat for pr in p["prendas"]))
        print(f"   personas con {cat}: {pct(k, len(personas))}")

    print("\n2) Acuerdo categoria del detector vs clasificador (mide si el recorte 'se parece' a una prenda suelta)")
    ok = sum(1 for _, _, pr in con_attr if pr["coincide_categoria"])
    print(f"   global: {pct(ok, len(con_attr))}")
    resumen["acuerdo_categoria_global"] = {"coincide": ok, "n": len(con_attr)}
    for cat in BASICAS + ["accesorio"]:
        sub = [pr for _, _, pr in con_attr if pr["categoria"] == cat]
        if sub:
            k = sum(1 for pr in sub if pr["coincide_categoria"])
            desv = collections.Counter(pr["atributos"].get("categoria") for pr in sub if not pr["coincide_categoria"])
            print(f"   {cat:<14} {pct(k, len(sub)):<12} desvios: {dict(desv) if desv else '-'}")

    print("\n3) Atributos que predice el clasificador: foto entera vs recortes por prenda")
    ent = [v for v in entera.values() if v]
    rec = [pr["atributos"] for _, _, pr in con_attr]
    for campo in ["categoria", "temporada", "color_primario", "grupo_estilo", "genero"]:
        print(f" {campo}")
        distribucion([e.get(campo) for e in ent], "foto entera (n=%d)" % len(ent))
        distribucion([r.get(campo) for r in rec], "recortes   (n=%d)" % len(rec))

    print("\n4) Estilo del outfit (voto ponderado por area) por persona")
    distribucion([next(iter(p["outfit"]["estilo_outfit"]), None) for _, _, p in personas], "estilo dominante")
    distribucion([p["outfit"]["temporada"] for _, _, p in personas], "temporada dominante")

    if aud:
        print("\n5) Auditoria manual (mi lectura de las fotos anotadas; pendiente de validar por el autor)")
        cajas = collections.Counter()
        col_ok = col_n = 0
        visibles = faltan = 0
        por_origen = collections.defaultdict(collections.Counter)
        pers_aud = personas_reales = 0
        hit_p0 = hit_base = n_p0 = hit_todas = n_todas = 0
        for f in fotos:
            a = aud.get(f)
            if not a:
                continue
            personas_reales += a["personas_visibles"]
            pers_aud += len(outfits[f]["personas"])
            for k, p in enumerate(outfits[f]["personas"]):
                ap_ = a[f"P{k}"]
                veredictos = []
                for pr in p["prendas"]:
                    v = ap_["prendas"][pr["categoria"]]
                    veredictos.append((pr, v))
                    cajas[v["caja"]] += 1
                    por_origen[pr["origen"]][v["caja"]] += 1
                    if v["caja"] == "ok" and v.get("color") in ("ok", "mal"):
                        col_n += 1
                        col_ok += v["color"] == "ok"
                detectadas = {pr["categoria"] for pr, v in veredictos if v["caja"] != "mal"}
                visibles += len(detectadas & set(BASICAS)) + len(ap_["faltan"])
                faltan += len(ap_["faltan"])
                dom = next(iter(p["outfit"]["estilo_outfit"]), None)
                hit_todas += dom in ap_["estilos_aceptables"]
                n_todas += 1
                if k == 0:  # persona principal: la unica comparable con la lectura de la foto entera
                    base = (entera.get(f) or {}).get("grupo_estilo")
                    hit_p0 += dom in ap_["estilos_aceptables"]
                    hit_base += base in ap_["estilos_aceptables"]
                    n_p0 += 1
        print(f"   personas visibles {personas_reales}; detectadas {pers_aud}")
        tot = sum(cajas.values())
        print(f"   cajas: ok {pct(cajas['ok'], tot)}, parcial {pct(cajas['parcial'], tot)}, mal {pct(cajas['mal'], tot)}")
        for o, c in por_origen.items():
            n = sum(c.values())
            print(f"     origen {o:<10} n={n}: ok {c['ok']}, parcial {c['parcial']}, mal {c['mal']}")
        print(f"   color correcto en cajas ok: {pct(col_ok, col_n)}")
        print(f"   prendas basicas visibles no cubiertas por ninguna caja: {faltan} de {visibles} -> recall {1 - faltan / visibles:.0%}")
        print(f"   estilo dentro de lo aceptable, persona principal: pipeline {pct(hit_p0, n_p0)}  vs  foto entera {pct(hit_base, n_p0)}")
        print(f"   estilo dentro de lo aceptable, todas las personas (pipeline): {pct(hit_todas, n_todas)}")
        resumen["auditoria"] = {
            "cajas": dict(cajas), "color_ok": col_ok, "color_n": col_n, "basicas_visibles": visibles, "basicas_faltan": faltan,
            "estilo_pipeline_p0": hit_p0, "estilo_foto_entera_p0": hit_base, "n_p0": n_p0,
            "estilo_pipeline_todas": hit_todas, "n_todas": n_todas,
            "personas_visibles": personas_reales, "personas_detectadas": pers_aud,
            "cajas_por_origen": {o: dict(c) for o, c in por_origen.items()},
        }

    if args.json_salida:
        Path(args.json_salida).write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nResumen guardado en {args.json_salida}")


if __name__ == "__main__":
    main()
