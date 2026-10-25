#!/usr/bin/env python3
"""
Puntuación de SKUs contra un Trend JSON (Estado_arte.md §7.2), con los embeddings del inventario del Experimento B ya calculados (sin volver a abrir las imágenes):

    score_semantico = coseno(v_prenda, v_tendencia)           v_tendencia = codificador de TEXTO de CLIP sobre `descripcion_clip` del Trend JSON
    boost_estilo    = β  si el grupo de estilo del SKU está en `grupo_estilo_detectado`, 0 si no       (β = 0,1)
    score           = score_semantico + boost_estilo
    alineado        = score_semantico ≥ θ                                                              (θ = 0,20)

El inventario son 1 267 miniaturas de 60×80 px de una tienda en línea (1 207 con grupo del ERP por la carpeta donde están; 60 «extra» sin grupo, boost 0). Es la misma base del Experimento B/C: un banco de
pruebas, no el catálogo real de SKUs. Nota: §6.5 dice que el codificador procesa el campo `descripcion`; aquí se codifica `descripcion_clip` (texto corto en inglés), que es lo que mostraron los Experimentos B y C.

Uso:  python3 puntuar_skus.py puntuar [--pendientes trends/pending] [--salida trends/scored] [--k 10]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
POC = AQUI.parent
REPO = POC.parent.parent
CATALOGO = POC / "experimento_b" / "cache" / "catalogo_v2.npz"
BETA, THETA = 0.1, 0.20
GRUPO_ERP = {"casual": "Casual", "streetwear": "Streetwear", "de_vestir": "De vestir", "fiesta_noche": "Fiesta/Noche", "deportivo": "Deportivo", "playa_resort": "Playa/Resort"}


def cargar_catalogo(ruta: Path = CATALOGO):
    """(rutas relativas al repositorio, grupo ERP o None, matriz de embeddings unitarios)."""
    z = np.load(ruta, allow_pickle=False)
    rutas = [str(c) for c in z["claves"]]
    grupos = [GRUPO_ERP.get(Path(r).parent.name) for r in rutas]
    return rutas, grupos, z["v"].astype(np.float32)


def puntuar(v_tendencia: np.ndarray, V: np.ndarray, grupos_sku: list, grupos_tendencia: list, beta: float = BETA, theta: float = THETA, k: int = 10) -> list[dict]:
    v = v_tendencia / np.linalg.norm(v_tendencia)
    sem = V @ v
    boost = np.array([beta if (g is not None and g in grupos_tendencia) else 0.0 for g in grupos_sku], dtype=np.float32)
    score = sem + boost
    orden = np.argsort(-score, kind="stable")[:k]
    return [{"i": int(i), "semantico": round(float(sem[i]), 4), "boost": round(float(boost[i]), 3), "score": round(float(score[i]), 4), "alineado": bool(sem[i] >= theta)} for i in orden]


def cmd_puntuar(a):
    sys.path.insert(0, str(POC))
    from clip_matching_poc import cargar_modelo, encodear_textos  # noqa: E402
    rutas, grupos, V = cargar_catalogo()
    model, _, tok = cargar_modelo()
    a.salida.mkdir(parents=True, exist_ok=True)
    for f in sorted(a.pendientes.glob("*.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        v = encodear_textos(model, tok, [t["descripcion_clip"]])[0].numpy()
        top = puntuar(v, V, grupos, t["grupo_estilo_detectado"], k=a.k)
        for r in top:
            r["ruta"], r["grupo"] = rutas[r["i"]], grupos[r["i"]]
        sem = V @ (v / np.linalg.norm(v))
        n_alineados = int((sem >= THETA).sum())
        dist = {"p50": round(float(np.percentile(sem, 50)), 3), "p90": round(float(np.percentile(sem, 90)), 3), "max": round(float(sem.max()), 3)}
        (a.salida / f.name).write_text(json.dumps({"id": t["id"], "beta": BETA, "theta": THETA, "n_sku": len(rutas), "n_alineados": n_alineados, "distribucion_semantica": dist, "top": top}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{t['id']:28} alineados {n_alineados:4}/{len(rutas)} (mediana {dist['p50']}, p90 {dist['p90']}, máx {dist['max']})  top-3: " + ", ".join(f"{Path(r['ruta']).parent.name}/{Path(r['ruta']).stem[:14]} {r['score']:.3f}" for r in top[:3]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("puntuar")
    p.add_argument("--pendientes", type=Path, default=AQUI / "trends" / "pending")
    p.add_argument("--salida", type=Path, default=AQUI / "trends" / "scored")
    p.add_argument("--k", type=int, default=10)
    a = ap.parse_args()
    cmd_puntuar(a)


if __name__ == "__main__":
    main()
