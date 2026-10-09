#!/usr/bin/env python3
"""
Mide lo que acierta cada atributo del flujo de tendencia por prenda y lo guarda en `tendencia_datos/fiabilidad.json`. El informe (`tendencia_prenda.py informe`) lo lee
para poner un techo de confianza a cada cifra: un atributo que acierta la mitad no puede dar una cifra de confianza «alta» por muchas fotos que tenga.

- tipo fino y familia: el tipo que da el flujo semanal frente a la prenda PRINCIPAL que Víctor etiquetó (y, aparte, frente a cualquiera de las prendas de ese recorte).
  Hoodie y Sudadera cuentan como lo mismo (el flujo aún no distingue la capucha). Se recalcula con sus etiquetas (`tendencia_datos/etiquetas_prendas.json`).
- color: no hay etiquetas de Víctor; se guarda la revisión a ojo hecha por el asistente (una sola persona, 30 prendas al azar). Se actualiza a mano al repetirla.
- modelo grande (Qwen3-VL-8B en Kaggle, `tendencia_prenda.py vlm`): tipo, familia, estampado, tejido y forma. Mientras no haya un lote ciego, salen de la prueba con las 40 fotos de Víctor
  (`vlm_atributos_prenda/resultados/profesor_victor_2026-10-09/`, configuraciones «tipo_recorte» y «profesor», con las instrucciones v1: lo más parecido a lo que corre cada semana);
  cuando exista `tendencia_datos/lote_ciego.json` (claves foto#índice de los recortes que Víctor etiquetó DESPUÉS de que el modelo los etiquetara) y tenga al menos 20 prendas, manda el lote ciego.

Uso:  python3 fiabilidad_prenda.py [--etiquetas RUTA] [--salida RUTA]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TD = AQUI / "tendencia_datos"
PRUEBA_VLM = AQUI.parent / "vlm_atributos_prenda" / "resultados" / "profesor_victor_2026-10-09" / "evaluacion.json"
EQ = {"Hoodie": "Sudadera"}


def familia_de(tipo: str) -> str:
    sys.path.insert(0, str(AQUI))
    import tendencia_prenda as tp   # importa mercado.py: solo para leer FAMILIA
    return tp.FAMILIA.get(tipo, "Otros")


def vlm_de_la_prueba() -> dict:
    """Aciertos del modelo grande con las 40 fotos de Víctor (prenda principal): tipo con «tipo_recorte»; estampado, tejido y forma con «profesor» (usa el tipo que elige él, como la tanda semanal)."""
    d = json.loads(PRUEBA_VLM.read_text(encoding="utf-8"))
    tipo = next(f for f in d["tipo_victor"] if f["config"] == "tipo_recorte")
    out = {"vlm_tipo": {"acierto": tipo["principal"][0], "n": tipo["principal"][1], "cualquiera": tipo["cualquiera"][0]},
           "vlm_familia": {"acierto": tipo["familia_principal"][0], "n": tipo["familia_principal"][1]}}
    for f in d["victor"]:
        if f["config"] == "profesor":
            out[f"vlm_{f['campo']}"] = {"acierto": f["principal"][0], "n": f["principal"][1], "cualquiera": f["cualquiera"][0], "mas_frecuente": f["siempre_la_mas_frecuente"]}
    for v in out.values():
        v["fuente"] = "prueba con las 40 fotos de Víctor (9 de octubre de 2026), instrucciones v1; sustituir por el lote ciego"
    return out


def vlm_del_lote_ciego(prendas: dict, etiq: dict) -> dict:
    """Aciertos del modelo grande en los recortes del lote ciego (etiquetados por Víctor después de que el modelo los etiquetara). {} si aún no hay 20."""
    f = TD / "lote_ciego.json"
    if not f.exists():
        return {}
    claves = [k for k in json.loads(f.read_text(encoding="utf-8")) if k in etiq and etiq[k].get("prendas")]
    cuenta = {c: [0, 0, 0] for c in ("tipo", "familia", "estampado", "tejido", "forma")}   # aciertos, n, «cualquiera»
    for k in claves:
        foto, _, i = k.partition("#")
        try:
            v = prendas[foto]["prendas"][int(i)].get("vlm")
        except (KeyError, IndexError, ValueError):
            continue
        if not v:
            continue
        pri, todas = etiq[k]["prendas"][0], etiq[k]["prendas"]
        if pri.get("tipo"):
            cuenta["tipo"][1] += 1
            cuenta["tipo"][0] += EQ.get(v["tipo"], v["tipo"]) == EQ.get(pri["tipo"], pri["tipo"])
            cuenta["tipo"][2] += any(EQ.get(v["tipo"], v["tipo"]) == EQ.get(q["tipo"], q["tipo"]) for q in todas if q.get("tipo"))
            cuenta["familia"][1] += 1
            cuenta["familia"][0] += familia_de(v["tipo"]) == familia_de(pri["tipo"])
        for c in ("estampado", "tejido", "forma"):
            if pri.get(c) and pri[c] != "no aplica":
                cuenta[c][1] += 1
                cuenta[c][0] += v.get(c) == pri[c]
                cuenta[c][2] += any(v.get(c) == q.get(c) for q in todas)
    if cuenta["tipo"][1] < 20:
        return {}
    return {f"vlm_{c}": {"acierto": a, "n": n, "cualquiera": q, "fuente": "lote ciego de Víctor (etiquetado después de que el modelo etiquetara esos recortes)"} for c, (a, n, q) in cuenta.items() if n}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--etiquetas", type=Path, default=TD / "etiquetas_prendas.json")
    ap.add_argument("--salida", type=Path, default=TD / "fiabilidad.json")
    a = ap.parse_args()
    todas = json.loads(a.etiquetas.read_text(encoding="utf-8"))
    ciego = set(json.loads((TD / "lote_ciego.json").read_text(encoding="utf-8"))) if (TD / "lote_ciego.json").exists() else set()
    # el tipo de CLIP se mide con los lotes 1 y 2: en el lote ciego el `tipo_modelo` guardado ya es el del modelo grande (se mide aparte, abajo)
    etiq = {k: v for k, v in todas.items() if v.get("prendas") and v["prendas"][0].get("tipo") and k not in ciego}
    n = fino = fino_cual = fam = fam_cual = 0
    for v in etiq.values():
        modelo = v["tipo_modelo"]
        principal = v["prendas"][0]["tipo"]
        todos = {q["tipo"] for q in v["prendas"] if q.get("tipo")}
        n += 1
        fino += EQ.get(modelo, modelo) == EQ.get(principal, principal)
        fino_cual += any(EQ.get(modelo, modelo) == EQ.get(t, t) for t in todos)
        fam += familia_de(modelo) == familia_de(principal)
        fam_cual += any(familia_de(modelo) == familia_de(t) for t in todos)
    fiab = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tipo_fino": {"acierto": fino, "n": n, "cualquiera": fino_cual, "fuente": "etiquetas de Víctor (lotes 1 y 2)",
                      "metodo": "tipo del flujo semanal (CLIP ViT-B/32 dentro de la lista de la categoría del detector) frente a la prenda principal etiquetada; Hoodie = Sudadera",
                      "nota": "con «cualquiera de las prendas del recorte» sube; CLIP ViT-L/14 y una capa entrenada con sus etiquetas no mejoran"},
        "familia": {"acierto": fam, "n": n, "cualquiera": fam_cual, "fuente": "etiquetas de Víctor (lotes 1 y 2)",
                    "metodo": "arriba · abrigo · abajo · cuerpo entero · calzado · accesorio, con el mismo tipo del flujo semanal"},
        "color": {"acierto": 21, "n": 30, "fuente": "revisión a ojo del asistente, 30 prendas al azar (no de Víctor)", "techo": "baja",
                  "metodo": "color_primario del adaptador Florence-2 v3 sobre el recorte",
                  "nota": "5 claramente mal y 4 dudosas; sesgo hacia «negro»: prendas rojas, moradas, doradas o de camuflaje salen negras o grises"},
        "estampado": {"estado": "no se estima", "mejor_medido": "12 a 13 de 22, igual que decir siempre «liso» (11 de 22)", "fuente": "memoria/TFM_tendencias_de_prenda.md §6"},
        "tejido": {"estado": "no se estima", "mejor_medido": "6 de 17 con CLIP; decir siempre «algodón» da 10 de 17", "fuente": "memoria/TFM_tendencias_de_prenda.md §6"},
        "forma": {"estado": "no se estima", "mejor_medido": "4 a 9 de 23; decir siempre «oversized» da 11 de 23", "fuente": "memoria/TFM_tendencias_de_prenda.md §6"},
    }
    fiab.update(vlm_de_la_prueba())
    prendas_f = TD / "prendas.json"
    if prendas_f.exists():
        ciego = vlm_del_lote_ciego(json.loads(prendas_f.read_text(encoding="utf-8")), {k: v for k, v in json.loads(a.etiquetas.read_text(encoding="utf-8")).items()})
        if ciego:
            fiab.update(ciego)
            print("modelo grande: manda el lote ciego", {k: f"{v['acierto']}/{v['n']}" for k, v in ciego.items()})
    a.salida.write_text(json.dumps(fiab, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"tipo fino {fino}/{n} ({fino / n:.0%}; cualquiera {fino_cual}/{n}) · familia {fam}/{n} ({fam / n:.0%}; cualquiera {fam_cual}/{n}) · color 21/30 a ojo → {a.salida}")


if __name__ == "__main__":
    main()
