#!/usr/bin/env python3
"""
Puntúa uno o varios modelos de `prueba_recortes_clip.py` contra la verdad a ojo de los recortes R01-R36
(`../resultados/recortes_verdad_a_ojo_2026-10-06.json`). Protocolo «v2»: el tipo se elige entre los de la categoría que da el detector, con arriba y
abrigo mezclados. Referencias: «siempre la clase más frecuente» para estampado y forma. Para el estampado se prueba también un sesgo hacia «liso»
elegido con validación cruzada dejando una prenda fuera. Uso: python3 evaluar_recortes.py recortes_out/<modelo> [recortes_out/<otro> ...]
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np

VERDAD = Path(__file__).resolve().parents[1] / "resultados" / "recortes_verdad_a_ojo_2026-10-06.json"
GRUPOS = {"ropa_superior": range(0, 13), "abrigo": range(0, 13), "ropa_inferior": range(13, 17), "cuerpo_entero": range(17, 19), "calzado": range(19, 25)}


def evaluar(carpeta: Path, v: dict) -> dict:
    z = np.load(carpeta / "recortes_emb.npz", allow_pickle=False)
    emb, muestra, cat = z["emb"], z["muestra"].tolist(), z["cat"].tolist()
    nt, ne, nf = z["n_tipo"].tolist(), z["n_est"].tolist(), z["n_forma"].tolist()
    idx = lambda r: muestra[int(r[1:]) - 1]
    res = {}
    # tipo
    ok, n, arriba = 0, 0, [0, 0]
    for r, aceptables in v["tipo"].items():
        i = idx(r)
        cand = list(GRUPOS[cat[i]])
        s = 100.0 * z["t_tipo"][cand] @ emb[i]
        pred = nt[cand[int(s.argmax())]]
        acierto = pred in aceptables
        ok += acierto; n += 1
        if cat[i] in ("ropa_superior", "abrigo"):
            arriba[0] += acierto; arriba[1] += 1
    res["tipo"] = (ok, n, arriba)
    # estampado
    ids = list(v["estampado"]); X = np.array([100.0 * z["t_est"] @ emb[idx(r)] for r in ids]); y = np.array([ne.index(v["estampado"][r]) for r in ids])
    L = ne.index("liso")
    pred = lambda X, b: (X + b * np.eye(len(ne))[L]).argmax(1)
    grid = np.arange(0, 40.1, 0.5)
    loo = []
    for i in range(len(ids)):
        m = np.arange(len(ids)) != i
        mejor = max(grid, key=lambda b: ((pred(X[m], b) == y[m]).mean(), -abs(b - 10)))
        loo.append(pred(X[i:i + 1], mejor)[0] == y[i])
    res["estampado"] = (int((pred(X, 0) == y).sum()), len(ids), int(np.sum(loo)), float((y == L).mean()))
    # forma
    ids = list(v["forma"]); X = np.array([100.0 * z["t_forma"] @ emb[idx(r)] for r in ids]); y = np.array([nf.index(v["forma"][r]) for r in ids])
    res["forma"] = (int((X.argmax(1) == y).sum()), len(ids), float(max(collections.Counter(y.tolist()).values()) / len(ids)))
    return res


if __name__ == "__main__":
    v = json.loads(VERDAD.read_text(encoding="utf-8"))
    for c in sys.argv[1:]:
        r = evaluar(Path(c), v)
        t, e, f = r["tipo"], r["estampado"], r["forma"]
        print(f"{Path(c).name}\n  tipo: {t[0]}/{t[1]} ({t[0]/t[1]:.0%}), arriba {t[2][0]}/{t[2][1]}"
              f"\n  estampado: {e[0]}/{e[1]} ({e[0]/e[1]:.0%}); con sesgo a «liso» (validación cruzada) {e[2]}/{e[1]} ({e[2]/e[1]:.0%}); siempre «liso» {e[3]:.0%}"
              f"\n  forma: {f[0]}/{f[1]} ({f[0]/f[1]:.0%}); siempre la más frecuente {f[2]:.0%}")
