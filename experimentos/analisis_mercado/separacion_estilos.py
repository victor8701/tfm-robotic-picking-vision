#!/usr/bin/env python3
"""
¿Se separan los estilos (geek / urbano) a nivel de prenda con lo que ya mide el modelo? (10 de octubre de 2026, a petición de Víctor: «lo importante es separar por estilo»).

Para cada dimensión (familia, tipo, estampado, tejido, forma) compara el reparto de prendas de un estilo con el del otro:
  · diferencia de cuota por categoría (geek − urbano), con intervalo del 95 % por bootstrap **por foto** (las prendas de una misma foto no son independientes);
  · p de permutación **por foto** (se baraja el estilo de las fotos enteras) y q de Benjamini-Hochberg (varias categorías a la vez: sin esto saldría «significativo» por azar);
  · una prueba global por dimensión (distancia de variación total entre los dos repartos).
Además, cuánto resiste a un acierto del ~70 %: si el modelo se equivoca al azar con probabilidad 1−a, la diferencia observada es ≈ a·(real) − algo muy pequeño, así que el signo se conserva y la magnitud se encoge (columna «real≈»).

Solo usa prendas válidas (`valida`) con valoración del modelo grande. Escribe `tendencia_datos/separacion_estilos.json`.

Uso:  python3 separacion_estilos.py [--min 6] [--rep 3000] [--salida tendencia_datos/separacion_estilos.json]   (también lo recalcula `tendencia_prenda.py informe`)
"""
import argparse
import collections
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TD = AQUI / "tendencia_datos"
DIMS = ("familia", "tipo", "estampado", "tejido", "forma")


def aciertos():
    """Acierto con el que se corrige la columna «real≈» de cada dimensión: lo aceptable en la revisión de Víctor (fiabilidad.json); si no hay, 70 %."""
    f = TD / "fiabilidad.json"
    fiab = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    out = {}
    for d in DIMS:
        rev = (fiab.get(f"vlm_{d}") or {}).get("revision")
        out[d] = (rev["aceptable"] / rev["n"]) if rev else 0.70
    out["familia"] = max(out["familia"], out["tipo"])   # la familia se confunde menos que el tipo
    return out


def filas(tp, solo_biblioteca=False):
    prendas = json.loads((TD / "prendas.json").read_text(encoding="utf-8"))
    fotos = json.loads((TD / "fotos.json").read_text(encoding="utf-8"))
    out = []
    for fid, r in prendas.items():
        f = fotos.get(fid)
        if not f or f.get("descartada") or f["estilo"] not in ("geek", "urbano"):
            continue
        if solo_biblioteca and f["mercado"] != "Biblioteca":
            continue
        for p in r["prendas"]:
            v = p.get("vlm")
            if not v or not tp.valida(p):
                continue
            out.append({"foto": fid, "estilo": f["estilo"], "mercado": f["mercado"], "familia": tp.FAMILIA.get(v["tipo"], "Otros"), "tipo": v["tipo"],
                        "estampado": v["estampado"], "tejido": v["tejido"], "forma": v["forma"]})
    return out


def cuotas(prendas, dim, cats):
    n = len(prendas)
    c = collections.Counter(p[dim] for p in prendas)
    return {k: (c[k] / n if n else 0.0) for k in cats}, n


def bh(ps):
    """q de Benjamini-Hochberg para una lista de p (mismo orden)."""
    m = len(ps)
    orden = sorted(range(m), key=lambda i: ps[i])
    q = [1.0] * m
    previo = 1.0
    for rango in range(m, 0, -1):
        i = orden[rango - 1]
        previo = min(previo, ps[i] * m / rango)
        q[i] = previo
    return q


def analizar(todas, dim, minimo, rep, rnd, acierto):
    por_foto = collections.defaultdict(list)
    estilo_de = {}
    for p in todas:
        por_foto[p["foto"]].append(p)
        estilo_de[p["foto"]] = p["estilo"]
    cuenta = collections.Counter(p[dim] for p in todas)
    cats = sorted([k for k, n in cuenta.items() if n >= minimo], key=lambda k: -cuenta[k])
    if len(cats) < 2:
        return None
    fotos_g = [f for f, s in estilo_de.items() if s == "geek"]
    fotos_u = [f for f, s in estilo_de.items() if s == "urbano"]

    def reparto(lista_fotos):
        pr = [p for f in lista_fotos for p in por_foto[f]]
        return cuotas(pr, dim, cats)[0]

    def diferencias(fg, fu):
        a, b = reparto(fg), reparto(fu)
        return {k: a[k] - b[k] for k in cats}
    obs = diferencias(fotos_g, fotos_u)
    tv_obs = 0.5 * sum(abs(v) for v in obs.values())
    # bootstrap por foto, dentro de cada estilo
    boots = {k: [] for k in cats}
    for _ in range(rep):
        fg = [rnd.choice(fotos_g) for _ in fotos_g]
        fu = [rnd.choice(fotos_u) for _ in fotos_u]
        d = diferencias(fg, fu)
        for k in cats:
            boots[k].append(d[k])
    ic = {}
    for k in cats:
        s = sorted(boots[k])
        ic[k] = [s[int(0.025 * rep)], s[int(0.975 * rep) - 1]]
    # permutación por foto (se baraja el estilo de las fotos)
    todas_fotos = fotos_g + fotos_u
    ng = len(fotos_g)
    extremo = {k: 0 for k in cats}
    tv_ge = 0
    for _ in range(rep):
        rnd.shuffle(todas_fotos)
        d = diferencias(todas_fotos[:ng], todas_fotos[ng:])
        for k in cats:
            extremo[k] += abs(d[k]) >= abs(obs[k]) - 1e-12
        tv_ge += 0.5 * sum(abs(v) for v in d.values()) >= tv_obs - 1e-12
    p = [(extremo[k] + 1) / (rep + 1) for k in cats]
    q = bh(p)
    a = acierto[dim]
    filas_ = []
    rg, ru = reparto(fotos_g), reparto(fotos_u)
    for i, k in enumerate(cats):
        filas_.append({"categoria": k, "n": cuenta[k], "geek": round(rg[k], 3), "urbano": round(ru[k], 3), "dif": round(obs[k], 3), "ic": [round(ic[k][0], 3), round(ic[k][1], 3)],
                       "p": round(p[i], 4), "q": round(q[i], 4), "real_aprox": round(obs[k] / a, 3)})
    return {"dimension": dim, "prendas": len(todas), "fotos_geek": len(fotos_g), "fotos_urbano": len(fotos_u),
            "prendas_geek": sum(len(por_foto[f]) for f in fotos_g), "prendas_urbano": sum(len(por_foto[f]) for f in fotos_u),
            "global": {"tv": round(tv_obs, 3), "p": round((tv_ge + 1) / (rep + 1), 4)}, "categorias": filas_}


def generar(tp, rep=3000, minimo=6, semilla=5, salida=None, imprimir=False):
    """Calcula la comparación geek-urbano con todas las fuentes y solo con la Biblioteca; la escribe en `salida` (por defecto tendencia_datos/separacion_estilos.json) y la devuelve."""
    rnd = random.Random(semilla)
    acierto = aciertos()
    res = {"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "min_prendas_categoria": minimo, "repeticiones": rep,
           "metodo": "diferencia de cuota geek − urbano por categoría; intervalo por bootstrap por foto; p de permutación por foto; q de Benjamini-Hochberg entre las categorías de cada dimensión"}
    for nombre, solo in (("todas_las_fuentes", False), ("solo_biblioteca", True)):
        todas = filas(tp, solo)
        res[nombre] = {"prendas": len(todas), "dimensiones": [r for r in (analizar(todas, d, minimo, rep, rnd, acierto) for d in DIMS) if r]}
        if imprimir:
            g = [r for r in todas if r["estilo"] == "geek"]
            u = [r for r in todas if r["estilo"] == "urbano"]
            print(f"\n######## {nombre}: {len(todas)} prendas (geek {len(g)} en {len({r['foto'] for r in g})} fotos · urbano {len(u)} en {len({r['foto'] for r in u})} fotos)")
            for d in res[nombre]["dimensiones"]:
                print(f"\n== {d['dimension']}  | prueba global: distancia {d['global']['tv']:.2f}, p = {d['global']['p']:.3f}")
                print(f"   {'categoría':<28}{'n':>4}  {'geek':>6} {'urbano':>7}  {'dif (IC 95 %)':>22}  {'p':>6} {'q':>6}  real≈")
                for c in d["categorias"]:
                    marca = "  ◄" if c["q"] < 0.10 else ("  ·" if c["p"] < 0.05 else "")
                    print(f"   {c['categoria']:<28}{c['n']:>4}  {100 * c['geek']:>5.0f}% {100 * c['urbano']:>6.0f}%  {100 * c['dif']:>+6.0f} [{100 * c['ic'][0]:>+4.0f},{100 * c['ic'][1]:>+4.0f}] pts  {c['p']:>6.3f} {c['q']:>6.3f}  {100 * c['real_aprox']:>+4.0f}{marca}")
    destino = Path(salida) if salida else TD / "separacion_estilos.json"
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(destino)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min", type=int, default=6, help="categorías con al menos tantas prendas en total")
    ap.add_argument("--rep", type=int, default=3000)
    ap.add_argument("--semilla", type=int, default=5)
    ap.add_argument("--salida", type=Path, default=TD / "separacion_estilos.json")
    a = ap.parse_args()
    sys.path.insert(0, str(AQUI))
    import tendencia_prenda as tp
    generar(tp, a.rep, a.min, a.semilla, a.salida, imprimir=True)
    print(f"\nEscrito {a.salida}\n(◄ = diferencia que aguanta la corrección por comparar varias categorías, q < 0,10; · = p < 0,05 sin esa corrección)")


if __name__ == "__main__":
    sys.exit(main())
