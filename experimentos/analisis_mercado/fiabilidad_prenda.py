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
- revisión «OK / más o menos / No» (`revisar_valoraciones.py`, 10 de octubre de 2026): se añade a cada `vlm_*` como `revision` y puede subir su techo a «media» (ver `aplicar_revision`).

Uso:  python3 fiabilidad_prenda.py [--etiquetas RUTA] [--salida RUTA]
"""
import argparse
import collections
import json
import math
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
    frecuente = {c: collections.Counter() for c in ("estampado", "tejido", "forma")}      # lo que daría decir siempre lo más frecuente de sus etiquetas
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
                frecuente[c][pri[c]] += 1
                cuenta[c][0] += v.get(c) == pri[c]
                cuenta[c][2] += any(v.get(c) == q.get(c) for q in todas)
    if cuenta["tipo"][1] < 20:
        return {}
    return {f"vlm_{c}": {"acierto": a, "n": n, "cualquiera": q, "fuente": "lote ciego de Víctor (etiquetado después de que el modelo etiquetara esos recortes)",
                         **({"mas_frecuente": [frecuente[c].most_common(1)[0][0], frecuente[c].most_common(1)[0][1], n]} if c in frecuente and frecuente[c] else {})}
            for c, (a, n, q) in cuenta.items() if n}


def wilson(k: int, n: int, z: float = 1.96) -> list[int]:
    if not n:
        return [0, 0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h)), round(100 * (c + h))]


def revision_de_valoraciones() -> dict:
    """Lo que Víctor dio por bueno en «Revisar valoraciones» (`revisar_valoraciones.py importar`): por atributo, OK / «más o menos» / No sobre los recortes reales (sin los de control ni los
    marcados «no sirve»). «Aceptable» = OK + «más o menos». Es otra vara de medir que el lote ciego: allí contestaba sin ver la respuesta del modelo; aquí la ve (más generosa, con posible sesgo
    de anclaje), y las cosas dudosas pueden valer. {} si aún no hay revisión."""
    f = TD / "valoraciones.json"
    if not f.exists():
        return {}
    resp = json.loads(f.read_text(encoding="utf-8"))
    reales = [v for v in resp.values() if not v.get("x") and not v.get("control")]
    out = {}
    for c in ("tipo", "estampado", "tejido", "forma"):
        r = [v["r"][c] for v in reales if v["r"].get(c)]
        rb = [v["r"][c] for v in reales if v["r"].get(c) and v["parte"] == "B"]
        if len(r) < 20:
            continue
        ok, mm = r.count("ok"), r.count("mm")
        out[c] = {"ok": ok, "mas_o_menos": mm, "no": r.count("no"), "n": len(r), "aceptable": ok + mm, "ic_aceptable": wilson(ok + mm, len(r)), "ic_estricto": wilson(ok, len(r)),
                  "parte_b_nuevos": {"n": len(rb), "ok": rb.count("ok"), "aceptable": rb.count("ok") + rb.count("mm")},
                  "recortes": len(reales), "fuente": "revisión de Víctor (OK / más o menos / No) viendo la valoración del modelo, 10 de octubre de 2026"}
    return out


def revision_por_tipo() -> dict:
    """Por tipo que dijo el modelo grande: cuántas veces lo diste por bueno (OK o «más o menos») en la revisión. El informe baja la confianza de los tipos con 6 o más revisados y menos del 65 %."""
    f = TD / "valoraciones.json"
    if not f.exists():
        return {}
    cuenta = {}
    for v in json.loads(f.read_text(encoding="utf-8")).values():
        if v.get("x") or v.get("control") or not v["r"].get("tipo"):
            continue
        a = cuenta.setdefault(v["real"]["tipo"], [0, 0])
        a[1] += 1
        a[0] += v["r"]["tipo"] in ("ok", "mm")
    return {t: {"aceptado": a, "n": n} for t, (a, n) in sorted(cuenta.items(), key=lambda kv: -kv[1][1])}


def aplicar_revision(fiab: dict) -> None:
    """Añade la revisión a cada `vlm_*` y sube el techo de confianza a «media» cuando el límite inferior del intervalo de «aceptable» pasa del 65 % (mismo umbral que a ciegas).
    «Alta» solo se alcanza a ciegas: la revisión ve la respuesta del modelo. Sus controles (valoración de otro recorte, de otra familia de prenda) no fueron concluyentes en la ronda 1 (6, cuatro «no sirve») y sí en la
    ronda 2 (6 de 6 rechazados, cinco con «no sirve» y uno con No), así que sus OK no son automáticos; aun así el techo por la revisión se queda en «media». Las cifras de la ciega son del método anterior del modelo
    grande (config «semanal»); desde el 16 de octubre la tarea semanal usa «semanal_pista» (ver `evaluar_zona.py`)."""
    sys.path.insert(0, str(AQUI))
    import tendencia_prenda as tp
    orden = ["baja", "media", "alta"]
    for c, rev in revision_de_valoraciones().items():
        m = fiab.setdefault(f"vlm_{c}", {})
        ciego = tp.techo_de(m) if m.get("n") else "baja"
        por_revision = "media" if rev["ic_aceptable"][0] >= 65 else "baja"
        m["revision"] = rev
        m["techo"] = max(ciego, por_revision, key=orden.index)
        m["techo_regla"] = (f"a ciegas: {ciego}; por la revisión (límite inferior de «aceptable» {rev['ic_aceptable'][0]} % ≥ 65 % → media): {por_revision}; manda el más alto, y «alta» solo se alcanza a ciegas")
    por_tipo = revision_por_tipo()
    if por_tipo and "vlm_tipo" in fiab:
        fiab["vlm_tipo"]["por_tipo"] = por_tipo


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
    aplicar_revision(fiab)
    for c in ("tipo", "estampado", "tejido", "forma"):
        m = fiab.get(f"vlm_{c}", {})
        if m.get("revision"):
            r = m["revision"]
            print(f"revisión {c}: aceptable {r['aceptable']}/{r['n']} (IC {r['ic_aceptable']}), solo OK {r['ok']}/{r['n']} · a ciegas {m.get('acierto')}/{m.get('n')} → techo {m['techo']}")
    a.salida.write_text(json.dumps(fiab, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"tipo fino {fino}/{n} ({fino / n:.0%}; cualquiera {fino_cual}/{n}) · familia {fam}/{n} ({fam / n:.0%}; cualquiera {fam_cual}/{n}) · color 21/30 a ojo → {a.salida}")


if __name__ == "__main__":
    main()
