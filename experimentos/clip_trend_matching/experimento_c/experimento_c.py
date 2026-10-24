#!/usr/bin/env python3
"""
Experimento C — ¿un texto de tendencia hecho con datos medidos supera al de un LLM que solo conoce el nombre? Diseño fijado en README.md (16 de octubre de 2026, antes de puntuar).

Reutiliza el Experimento B tal cual (inventario de 1 267 prendas de la v2, CLIP ViT-B/32, evidencia visual con la misma semilla, estadística y puntuaciones de `../experimento_b/ratings_b.json`)
y añade UN brazo: `T_datos_en` (los textos congelados de `textos_datos_c.json`). Las tendencias que se evalúan son las 6 de la v2 de B (sin lujo ostentoso).

  python3 experimento_c.py preparar    codifica los textos, recupera el top-10 de cada brazo y deja en `pool_c.json` solo las prendas aún sin puntuar (barajadas, tramo 1 primero)
  python3 experimento_c.py analizar    P@5, NDCG@5 (y @10 si hay puntuaciones suficientes) por brazo y las comparaciones emparejadas (la primaria: T_datos_en − T_corto_ciego_en)
  python3 experimento_c.py retest-preparar   pool de la REPETICIÓN de la puntuación (README §10): las 67 prendas del top-5 de T_datos_en, T_corto_ciego_en y T_oraculo_en, barajadas
  python3 experimento_c.py retest-analizar   acuerdo con la primera puntuación (kappa) y la comparación primaria recalculada con la segunda puntuación sola, la conservadora y la indulgente
"""
import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "experimento_b"))
sys.path.insert(0, str(AQUI.parents[1] / "analisis_mercado"))
import experimento_b as B  # noqa: E402
import texto_tendencia as tt  # noqa: E402

TEXTOS_C = AQUI / "textos_datos_c.json"
POOL_C, CLAVE_C = AQUI / "pool_c.json", AQUI / "pool_c_clave.json"
POOL_C2, RETEST = AQUI / "pool_c2.json", AQUI / "ratings_c_retest.json"
ARMS_RETEST = ["T_datos_en", "T_corto_ciego_en", "T_oraculo_en"]
METODOS_C = B.METODOS_V2 + ["T_datos_en"]
FLUJO_DE_B = {v: k for k, v in tt.CLAVE_B.items()}   # clave de B (alternativo_geek) → clave del flujo (geek)
COMP_C = (("T_datos_en", "T_corto_ciego_en", "[C primaria] ¿el texto hecho con datos medidos supera al texto corto de un LLM que solo conoce el nombre?"),
          ("T_datos_en", "T_oraculo_en", "¿se acerca al oráculo (escrito conociendo la taxonomía; cota optimista)?"),
          ("T_datos_en", "T_ciego_en", "¿y al texto largo ciego, el del pipeline actual?"),
          ("T_datos_en", "V", "¿texto con datos frente a solo imagen?"))


def cmd_preparar(args):
    texto = json.loads(B.TEXTOS.read_text(encoding="utf-8"))["tendencias"]
    datos = json.loads(TEXTOS_C.read_text(encoding="utf-8"))["estilos"]
    model, preprocess, tokenizer = B.cargar_modelo()
    enc = lambda s: B.encodear_textos(model, tokenizer, [s])[0].numpy()  # noqa: E731
    tok = lambda s: len(tokenizer([s])[0].nonzero())  # noqa: E731  (con SOT y EOT; tope de CLIP = 77)
    T = {"ciego_en": {e: enc(texto[e]["descripcion_en"]) for e in B.ESTILOS},
         "ciego_es": {e: enc(texto[e]["descripcion_es"]) for e in B.ESTILOS},
         "oraculo_en": {e: enc(texto[e]["oraculo_en_v2"] if "oraculo_en_v2" in texto[e] else texto[e]["oraculo_en"]) for e in B.ESTILOS},
         "corto_ciego_en": {e: enc(texto[e]["prompt_corto_en"]) for e in B.ESTILOS}}
    t_datos = {e: datos[FLUJO_DE_B[e]]["descripcion_clip"] for e in B.ESTILOS}
    print("Tokens de T_datos_en (tope de CLIP: 77):", {e: tok(t_datos[e]) for e in B.ESTILOS})
    T_datos = {e: enc(t_datos[e]) for e in B.ESTILOS}

    rutas_cat, _ = B.cargar_catalogo(con_extra=True)
    V_cat = B.con_cache("catalogo_v2", rutas_cat, model, preprocess)
    rutas_real, est_real = B.cargar_reales()
    V_real = B.con_cache("reales", rutas_real, model, preprocess)
    print(f"Inventario: {len(rutas_cat)} prendas. Fotos de evidencia: {len(rutas_real)}.")

    rng = random.Random(0)   # la MISMA secuencia de sorteo que B (v1 y v2): la evidencia de cada tendencia no cambia
    elementos, clave = {}, {}
    for e in B.ESTILOS:
        idx = np.where(est_real == e)[0]
        ev = V_real[rng.sample(list(idx), min(B.N_EVIDENCIA, len(idx)))]
        if e not in B.ESTILOS_V2:
            continue
        vec = B.vectores_tendencia(e, T, ev)
        vec["T_datos_en"] = T_datos[e]
        for m, v in vec.items():
            for rank, j in enumerate(np.argsort(-(V_cat @ v))[:B.K_POOL], 1):
                k = f"{e}|{rutas_cat[j].relative_to(B.POC)}"
                elementos.setdefault(k, {"tendencia": e, "imagen": str(rutas_cat[j].relative_to(B.POC))})
                clave.setdefault(k, {})[m] = rank
    CLAVE_C.write_text(json.dumps(clave, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    ratings = json.loads(B.RATINGS.read_text(encoding="utf-8")) if B.RATINGS.exists() else {}
    sin_b = [k for k, v in clave.items() if k not in ratings and any(m != "T_datos_en" for m in v)]
    if sin_b:
        print(f"AVISO: {len(sin_b)} prendas de los brazos de B no tienen puntuación (deberían estar todas): {sin_b[:3]}")
    nuevas = [k for k in clave if k not in ratings]
    tramo = {k: 1 if min(clave[k].values()) <= B.K_TRAMO1 else 2 for k in nuevas}
    barajador = random.Random(3)
    orden = []
    for t in (1, 2):
        grupo = sorted(k for k in nuevas if tramo[k] == t)
        barajador.shuffle(grupo)
        orden += grupo
    POOL_C.write_text(json.dumps([{"clave": k, "tramo": tramo[k], "nombre": B.NOMBRE[elementos[k]["tendencia"]], "rasgos": B.RASGOS[elementos[k]["tendencia"]], "imagen": elementos[k]["imagen"]}
                                  for k in orden], ensure_ascii=False, indent=1), encoding="utf-8")
    n1 = sum(1 for k in orden if tramo[k] == 1)
    top = {e: [k.split("|", 1)[1] for k, v in sorted(clave.items(), key=lambda kv: kv[1].get("T_datos_en", 99)) if k.startswith(e + "|") and "T_datos_en" in v][:5] for e in B.ESTILOS_V2}
    print(f"\nPrendas distintas en el análisis: {len(clave)}; ya puntuadas: {len(clave) - len(nuevas)}; NUEVAS por puntuar: {len(orden)} (tramo 1 = {n1}, tramo 2 = {len(orden) - n1}).")
    print("Siguiente paso: la página de puntuación (puntuar_c.py) y, con las puntuaciones en ../experimento_b/ratings_b.json:  python3 experimento_c.py analizar")


def cmd_analizar(args):
    B.analizar_generico(CLAVE_C, METODOS_C, B.ESTILOS_V2, Path(args.ratings) if args.ratings else B.RATINGS, COMP_C,
                        "ANÁLISIS C (inventario de 1 267 prendas, 6 tendencias sin lujo ostentoso; brazo nuevo T_datos_en; primaria declarada en README.md)")


def cmd_retest_preparar(args):
    """Pool de la repetición: todas las prendas del top-5 de los tres brazos de la comparación primaria y la del oráculo (README §10). Semilla de barajado fijada (24)."""
    clave = json.loads(CLAVE_C.read_text(encoding="utf-8"))
    items = sorted(k for k, v in clave.items() if k.split("|")[0] in B.ESTILOS_V2 and any(v.get(m, 99) <= B.K_TRAMO1 for m in ARMS_RETEST))
    random.Random(24).shuffle(items)
    POOL_C2.write_text(json.dumps([{"clave": k, "tramo": 1, "nombre": B.NOMBRE[k.split("|")[0]], "rasgos": B.RASGOS[k.split("|")[0]], "imagen": k.split("|", 1)[1]} for k in items],
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} prendas en {POOL_C2.name}")


def kappa(a, b):
    """Kappa de Cohen entre dos listas de categorías."""
    cats = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def cmd_retest_analizar(args):
    clave = json.loads(CLAVE_C.read_text(encoding="utf-8"))
    r1 = json.loads(B.RATINGS.read_text(encoding="utf-8"))
    r2 = json.loads(RETEST.read_text(encoding="utf-8")) if RETEST.exists() else {}
    pool = [p["clave"] for p in json.loads(POOL_C2.read_text(encoding="utf-8"))]
    falta = [k for k in pool if k not in r2]
    print(f"Repetición: {len(pool) - len(falta)} de {len(pool)} prendas puntuadas de nuevo.")
    if falta:
        print("Faltan prendas por puntuar; no se analiza.")
        return
    a, b = [r1[k] for k in pool], [r2[k] for k in pool]
    acuerdo = sum(x == y for x, y in zip(a, b)) / len(pool)
    rel1, rel2 = [x == 2 for x in a], [x == 2 for x in b]
    print(f"\nAcuerdo con la primera puntuación (misma persona): {100 * acuerdo:.0f} % de {len(pool)} prendas; kappa de Cohen {kappa(a, b):.2f} (3 categorías), {kappa(rel1, rel2):.2f} (encaja / no encaja)")
    print(f"   «encaja»: primera vez {sum(rel1)}, segunda {sum(rel2)}; cambian de «encaja» a otra cosa {sum(x and not y for x, y in zip(rel1, rel2))} y al revés {sum(y and not x for x, y in zip(rel1, rel2))}")

    def p5(m, rel, estilo):
        top = [k for k, v in clave.items() if k.startswith(estilo + "|") and v.get(m, 99) <= B.K_TRAMO1]
        return np.mean([rel(k) for k in top])

    variantes = (("SOLO LA SEGUNDA puntuación (el análisis primario repetido)", lambda k: r2[k] == 2),
                 ("CONSERVADORA: encaja solo si lo fue las dos veces", lambda k: r1[k] == 2 and r2[k] == 2),
                 ("INDULGENTE: encaja si lo fue alguna de las dos veces", lambda k: r1[k] == 2 or r2[k] == 2),
                 ("(referencia) la primera puntuación sola", lambda k: r1[k] == 2))
    for nombre, rel in variantes:
        res = {m: [p5(m, rel, e) for e in B.ESTILOS_V2] for m in ARMS_RETEST}
        print(f"\n== {nombre}\n   P@5 estricto medio: " + " · ".join(f"{m} {100 * np.mean(v):.0f} %" for m, v in res.items()))
        for x, y, que in (("T_datos_en", "T_corto_ciego_en", "primaria"), ("T_datos_en", "T_oraculo_en", "frente al oráculo")):
            d = np.array(res[x]) - np.array(res[y])
            media, lo, hi, pv = B.estadistica_emparejada(d)
            veredicto = "MEJORA" if lo > 0 and media >= 0.05 else ("EMPEORA" if hi < 0 and media <= -0.05 else "neutro/no concluyente")
            print(f"   {x} − {y}: {100 * media:+.0f} pp IC95% [{100 * lo:+.0f}, {100 * hi:+.0f}] p={pv:.3f} gana {int((d > 0).sum())}/empata {int((d == 0).sum())}/pierde {int((d < 0).sum())} -> {veredicto} ({que})")
    print("\nRegla fijada antes de puntuar (README §10): la conclusión es ROBUSTA si la comparación primaria con la SEGUNDA puntuación sola sigue siendo MEJORA (≥ +5 pp e IC95 % sin el 0).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preparar").set_defaults(f=cmd_preparar)
    pa = sub.add_parser("analizar")
    pa.add_argument("--ratings", default=None, help="fichero de puntuaciones (por defecto ../experimento_b/ratings_b.json)")
    pa.set_defaults(f=cmd_analizar)
    sub.add_parser("retest-preparar").set_defaults(f=cmd_retest_preparar)
    sub.add_parser("retest-analizar").set_defaults(f=cmd_retest_analizar)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
