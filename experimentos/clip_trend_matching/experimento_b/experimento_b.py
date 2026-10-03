#!/usr/bin/env python3
"""
Experimento B -- ¿mejora la evidencia VISUAL (fotos reales de una tendencia) al vector de tendencia
de TEXTO a la hora de recomendar prendas de un inventario?  (Estado_arte.md S6-S7, S11.2)

Reutiliza el CLIP del POC (clip_matching_poc.py: mismo modelo, mismo tokenizador, mismo coseno).

Dos subcomandos:

  preparar   Calcula embeddings (con caché), construye los vectores de tendencia, imprime una SEÑAL
             AUTOMÁTICA GRUESA y genera el "pool" para el juicio humano a ciegas
             (pool_b.json = lo que ve quien puntúa; pool_b_clave.json = qué método puso cada prenda).
  analizar   Lee ratings_b.json (los 0/1/2 de Víctor, ver evaluar_b.py) y calcula P@5 y NDCG@5 por
             método, diferencias emparejadas con intervalo bootstrap y victorias/empates/derrotas.

Brazos (métodos) comparados -- todos recuperan sobre el MISMO inventario con el mismo coseno:
  T_ciego_en    descripción redactada por un LLM que solo conoce el NOMBRE de la tendencia, en inglés
  T_ciego_es    la misma en español (como la produce hoy el pipeline; CLIP-OpenAI es de inglés)
  T_oraculo_en  prompt escrito por Claude conociendo la taxonomía (cota superior optimista del texto)
  V             centroide RECORTADO de N fotos reales confirmadas de esa tendencia
  F_ciego       fusión alpha*T_ciego_en + (1-alpha)*V          (alpha = 0.5, fijado de antemano)
  F_oraculo     fusión alpha*T_oraculo_en + (1-alpha)*V

LIMITACIONES (también en el README): el inventario de prueba son 1.207 miniaturas de 60x80 px de
Kaggle (no el catálogo real de SKUs); la "señal automática" usa un mapeo orientativo
sub-estilo -> grupo del ERP que es muy grueso (4 de los 7 sub-estilos caen en "Casual"); solo hay 7
tendencias, así que cualquier diferencia pequeña es ruido: ver los intervalos y los
victorias/empates/derrotas, no solo la media.
"""
import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

AQUI = Path(__file__).resolve().parent
POC = AQUI.parent
sys.path.insert(0, str(POC))
from clip_matching_poc import cargar_modelo, encodear_textos  # noqa: E402  (reutiliza el POC)

REPO = POC.parent.parent
CLASIF = REPO / "experimentos/ingesta_x/panel/data/clasificaciones.json"
FOTOS = REPO / "experimentos/ingesta_x/panel/static/fotos"
CACHE = AQUI / "cache"
TEXTOS = AQUI / "textos_tendencia_b.json"
POOL, CLAVE, RATINGS = AQUI / "pool_b.json", AQUI / "pool_b_clave.json", AQUI / "ratings_b.json"

CARPETAS_CATALOGO = ["casual", "streetwear", "de_vestir", "fiesta_noche", "deportivo", "playa_resort"]
EXT = {".jpg", ".jpeg", ".png", ".webp"}
ESTILOS = ["old_money", "lujo_ostentoso", "clasico_tradicional", "urbano", "bohemio",
           "alternativo_geek", "convencional"]

ALPHA = 0.5          # fijado de antemano (no se ajusta mirando resultados)
N_EVIDENCIA = 10     # fotos reales por tendencia
RECORTE = 0.2        # media recortada: se descarta el 20% más alejado del centroide inicial
K_TRAMO1, K_POOL = 5, 10   # tramo 1 = top-5 (lo mínimo, es la métrica del plan); tramo 2 = puestos 6-10 (más precisión)

# Mapeo orientativo sub-estilo -> grupos del ERP (Estado_arte.md S3.4.2). SOLO para la señal automática.
GRUPOS_RELEVANTES = {
    "old_money": {"de_vestir"}, "lujo_ostentoso": {"de_vestir", "fiesta_noche"},
    "clasico_tradicional": {"de_vestir", "casual"}, "urbano": {"streetwear"},
    "bohemio": {"casual", "playa_resort"}, "alternativo_geek": {"casual"}, "convencional": {"casual"},
}
# Lo que ve quien puntúa: el nombre y los rasgos de la taxonomía de Víctor (Estado_arte.md S3.4.2),
# NUNCA los textos generados por los métodos.
NOMBRE = {"old_money": "Old Money", "lujo_ostentoso": "Lujo ostentoso", "clasico_tradicional": "Clásico-tradicional",
          "urbano": "Urbano", "bohemio": "Bohemio", "alternativo_geek": "Alternativo-geek", "convencional": "Convencional"}
RASGOS = {
    "old_money": "Elegancia clásica y discreta: americana/chaleco, camisa de corte náutico, punto fino, sin logos visibles (\"lujo silencioso\").",
    "lujo_ostentoso": "Marca de lujo muy visible y reconocible, colores y estampados llamativos; el contraste deliberado de Old Money.",
    "clasico_tradicional": "Silueta clásica, tonos tierra/neutros, prenda atemporal.",
    "urbano": "Estética urbana trap/rap español, desde la más cruda hasta la más pulida: marca deportiva o lifestyle de gama alta, ropa de gimnasio, estética de reality.",
    "bohemio": "Telas fluidas, tonos tierra, capas, accesorios artesanales.",
    "alternativo_geek": "Ropa ligada a fandom (gaming, anime, cómic); el motivo o estampado pesa más que la silueta.",
    "convencional": "Sigue la tendencia dominante del momento, sin rasgo diferenciador propio.",
}
METODOS = ["T_ciego_en", "T_ciego_es", "T_oraculo_en", "V", "F_ciego", "F_oraculo"]

# --- v2 (añadida tras ver la v1; ver README) ---
# Inventario ampliado con prendas «geek» (anadir_inventario_extra.py), brazo nuevo "T_corto_ciego_en" (prompt corto
# redactado por el LLM ciego) y oráculo corregido de alternativo_geek. «lujo_ostentoso» queda fuera del análisis v2:
# el inventario gratuito no contiene prendas de ese tipo (techo ≈ 0 también con juicio humano en la v1).
METODOS_V2 = METODOS + ["T_corto_ciego_en", "F_corto"]
ESTILOS_V2 = [e for e in ESTILOS if e != "lujo_ostentoso"]
POOL_V2, CLAVE_V2 = AQUI / "pool_b_v2.json", AQUI / "pool_b_clave_v2.json"


# ---------- embeddings ----------

def embeber(model, preprocess, rutas, lote=64):
    salida = []
    with torch.no_grad():
        for i in range(0, len(rutas), lote):
            t = torch.stack([preprocess(Image.open(r).convert("RGB")) for r in rutas[i:i + lote]])
            v = model.encode_image(t)
            salida.append((v / v.norm(dim=-1, keepdim=True)).numpy())
    return np.concatenate(salida)


def con_cache(nombre, rutas, model, preprocess):
    """Embeddings con caché: se recalculan solo si cambia la lista de ficheros."""
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"{nombre}.npz"
    claves = np.array([str(r.relative_to(REPO)) for r in rutas])
    if f.exists():
        z = np.load(f, allow_pickle=False)
        if len(z["claves"]) == len(claves) and (z["claves"] == claves).all():
            return z["v"]
    print(f"  calculando embeddings de {len(rutas)} imágenes ({nombre})...", flush=True)
    v = embeber(model, preprocess, rutas)
    np.savez(f, claves=claves, v=v)
    return v


def cargar_catalogo(con_extra=False):
    rutas, grupos = [], []
    for g in CARPETAS_CATALOGO:
        for p in sorted((POC / g).iterdir()):
            if p.suffix.lower() in EXT:
                rutas.append(p)
                grupos.append(g)
    if con_extra:  # prendas añadidas en la v2: sin grupo del ERP asignado
        for p in sorted((AQUI / "inventario_extra").rglob("*")):
            if p.suffix.lower() in EXT:
                rutas.append(p)
                grupos.append("extra_" + p.parent.name)
    return rutas, np.array(grupos)


def cargar_reales():
    """Fotos reales CONFIRMADAS por Víctor (no eliminadas, revisadas, con fichero), por sub-estilo."""
    d = json.loads(CLASIF.read_text(encoding="utf-8"))
    por_estilo = {e: [] for e in ESTILOS}
    for it in d.values():
        est = it.get("categoria_final") or it.get("categoria_ia")
        if it["eliminada"] or not it.get("revisada") or not it.get("imagen") or est not in por_estilo:
            continue
        p = FOTOS / it["imagen"]
        if p.exists():
            por_estilo[est].append(p)
    rutas = [p for e in ESTILOS for p in sorted(por_estilo[e])]
    estilos = np.array([e for e in ESTILOS for _ in por_estilo[e]])
    return rutas, estilos


# ---------- vectores ----------

def unit(v):
    return v / np.linalg.norm(v)


def centroide_recortado(V, recorte=RECORTE):
    c = unit(V.mean(0))
    k = max(1, int(round(len(V) * (1 - recorte))))
    return unit(V[np.argsort(-(V @ c))[:k]].mean(0))


def fusion(t, v, alpha=ALPHA):
    return unit(alpha * t + (1 - alpha) * v)


def vectores_tendencia(estilo, T, V_ev):
    """Los 6 vectores de una tendencia. T = dict de vectores de texto; V_ev = embeddings de la evidencia."""
    v = centroide_recortado(V_ev)
    vec = {"T_ciego_en": T["ciego_en"][estilo], "T_ciego_es": T["ciego_es"][estilo],
           "T_oraculo_en": T["oraculo_en"][estilo], "V": v,
           "F_ciego": fusion(T["ciego_en"][estilo], v), "F_oraculo": fusion(T["oraculo_en"][estilo], v)}
    if "corto_ciego_en" in T:
        vec["T_corto_ciego_en"] = T["corto_ciego_en"][estilo]
        vec["F_corto"] = fusion(T["corto_ciego_en"][estilo], v)
    return vec


# ---------- métricas ----------

def dcg(g):
    return sum((2 ** x - 1) / np.log2(i + 2) for i, x in enumerate(g))


def ndcg(ganancias_ordenadas, todas, k):
    ideal = dcg(sorted(todas, reverse=True)[:k])
    return dcg(ganancias_ordenadas[:k]) / ideal if ideal > 0 else 0.0


# ---------- preparar ----------

def cmd_preparar(args):
    texto = json.loads(TEXTOS.read_text(encoding="utf-8"))["tendencias"]
    model, preprocess, tokenizer = cargar_modelo()
    tok = lambda s: len(tokenizer([s])[0].nonzero())  # noqa: E731  (tokens incl. SOT/EOT; 77 = tope de CLIP)
    print("\nTokens de cada texto (CLIP recorta a 77):")
    for e in ESTILOS:
        print(f"  {e:20s} ES {tok(texto[e]['descripcion_es']):3d}   EN {tok(texto[e]['descripcion_en']):3d}   oráculo {tok(texto[e]['oraculo_en']):3d}")

    T = {k: {e: encodear_textos(model, tokenizer, [texto[e][campo]])[0].numpy() for e in ESTILOS}
         for k, campo in (("ciego_en", "descripcion_en"), ("ciego_es", "descripcion_es"), ("oraculo_en", "oraculo_en"))}

    rutas_cat, grupos_cat = cargar_catalogo()
    V_cat = con_cache("catalogo", rutas_cat, model, preprocess)
    rutas_real, est_real = cargar_reales()
    V_real = con_cache("reales", rutas_real, model, preprocess)
    print(f"\nInventario de prueba: {len(rutas_cat)} prendas (60x80 px). Fotos reales confirmadas: {len(rutas_real)} "
          f"({', '.join(f'{e[:6]}={int((est_real == e).sum())}' for e in ESTILOS)})")

    # --- señal automática gruesa: P@5, P@10, nDCG@10 contra el mapeo orientativo a grupos del ERP ---
    rng = random.Random(args.seed)
    acum = {m: {"P5": [], "P10": [], "N10": []} for m in METODOS}
    azar = []
    for e in ESTILOS:
        idx = np.where(est_real == e)[0]
        rel = np.isin(grupos_cat, list(GRUPOS_RELEVANTES[e]))
        azar.append(rel.mean())
        n = min(args.n, len(idx))
        for _ in range(args.sorteos):
            ev = V_real[rng.sample(list(idx), n)]
            for m, vec in vectores_tendencia(e, T, ev).items():
                orden = np.argsort(-(V_cat @ vec))
                r = rel[orden]
                acum[m]["P5"].append(r[:5].mean()); acum[m]["P10"].append(r[:10].mean())
                acum[m]["N10"].append(ndcg(r[:10].astype(float), rel.astype(float), 10))
    print(f"\n=== SEÑAL AUTOMÁTICA GRUESA (relevante = la prenda pertenece a un grupo del ERP mapeado a la tendencia) ===")
    print(f"    {args.sorteos} sorteos de {args.n} fotos por tendencia; azar P@K ≈ {100*np.mean(azar):.0f}%. "
          f"OJO: etiquetas muy gruesas, NO sustituye al juicio humano.")
    print(f"    {'método':14s}   P@5     P@10    nDCG@10")
    for m in METODOS:
        print(f"    {m:14s}  {100*np.mean(acum[m]['P5']):4.0f}%   {100*np.mean(acum[m]['P10']):4.0f}%   {np.mean(acum[m]['N10']):.2f}")

    # --- pool para el juicio humano a ciegas (un sorteo fijo de evidencia) ---
    rng = random.Random(0)
    elementos, clave = {}, {}
    for e in ESTILOS:
        idx = np.where(est_real == e)[0]
        ev = V_real[rng.sample(list(idx), min(N_EVIDENCIA, len(idx)))]
        for m, vec in vectores_tendencia(e, T, ev).items():
            for rank, j in enumerate(np.argsort(-(V_cat @ vec))[:K_POOL], 1):
                k = f"{e}|{rutas_cat[j].relative_to(POC)}"
                elementos.setdefault(k, {"tendencia": e, "imagen": str(rutas_cat[j].relative_to(POC))})
                clave.setdefault(k, {})[m] = rank
    # Tramo 1 = prendas que algún método pone en su top-5; tramo 2 = el resto (puestos 6-10). Se puntúa
    # primero todo el tramo 1 (barajado): si paras ahí ya tienes el top-5 completo de TODOS los métodos.
    tramo = {k: 1 if min(v.values()) <= K_TRAMO1 else 2 for k, v in clave.items()}
    barajador = random.Random(1)
    orden = []
    for t in (1, 2):
        grupo = sorted(k for k in clave if tramo[k] == t)
        barajador.shuffle(grupo)
        orden += grupo
    POOL.write_text(json.dumps([{"clave": k, "tramo": tramo[k], "nombre": NOMBRE[elementos[k]["tendencia"]],
                                 "rasgos": RASGOS[elementos[k]["tendencia"]], "imagen": elementos[k]["imagen"]}
                                for k in orden], ensure_ascii=False, indent=1), encoding="utf-8")
    CLAVE.write_text(json.dumps(clave, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    n1 = sum(1 for k in orden if tramo[k] == 1)
    print(f"\nPool para puntuar: {len(orden)} prendas distintas: tramo 1 (top-5) = {n1}, tramo 2 (puestos 6-10) = {len(orden) - n1}.")
    print("Siguiente paso:  python3 evaluar_b.py   y puntúa en el navegador;  luego:  python3 experimento_b.py analizar")


# ---------- analizar ----------

T_CRIT_95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262,
             10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131}


def estadistica_emparejada(d):
    """d = diferencias por tendencia. Devuelve media, IC95% t (gl = n-1) y p exacto por permutación de signos.
    Se usa esto y NO el bootstrap percentil: con n = 7 el bootstrap da ~13% de falsos positivos (medido por
    simulación con puntuaciones aleatorias; t ~6%, permutación ~1%)."""
    import itertools
    d = np.asarray(d, dtype=float)
    n = len(d)
    media = d.mean()
    se = d.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    tc = T_CRIT_95.get(n - 1, 1.96)
    obs = abs(media)
    cuenta = sum(1 for s in itertools.product([1, -1], repeat=n) if abs((np.array(s) * d).mean()) >= obs - 1e-12)
    return media, media - tc * se, media + tc * se, cuenta / 2 ** n


def analizar_generico(ruta_clave, metodos, estilos, ruta_ratings, comparaciones, titulo):
    clave = json.loads(Path(ruta_clave).read_text(encoding="utf-8"))
    ratings = json.loads(Path(ruta_ratings).read_text(encoding="utf-8")) if Path(ruta_ratings).exists() else {}
    clave = {k: v for k, v in clave.items() if k.split("|")[0] in estilos}
    print(f"{titulo}\nPuntuadas {sum(1 for k in clave if k in ratings)} de {len(clave)} prendas de este análisis.")

    def lista(e, m, k):
        return [kk for _, kk in sorted((v[m], kk) for kk, v in clave.items() if kk.startswith(e + "|") and m in v and v[m] <= k)]

    for K in (K_TRAMO1, K_POOL):
        falta = [kk for e in estilos for m in metodos for kk in lista(e, m, K) if kk not in ratings]
        if falta:
            print(f"\n[K={K}] omitido: faltan {len(set(falta))} prendas por puntuar para tener el top-{K} completo de todos los métodos.")
            continue
        res = {m: {"P_estricto": [], "P_laxo": [], "NDCG": []} for m in metodos}
        for e in estilos:
            todas = [float(ratings[kk]) for kk in clave if kk.startswith(e + "|") and kk in ratings]
            for m in metodos:
                g = [ratings[kk] for kk in lista(e, m, K)]
                res[m]["P_estricto"].append(np.mean([x == 2 for x in g]))
                res[m]["P_laxo"].append(np.mean([x >= 1 for x in g]))
                res[m]["NDCG"].append(ndcg([float(x) for x in g], todas, K))
        print(f"\n===== K = {K} (media sobre {len(estilos)} tendencias) =====")
        print(f"{'método':16s} {'P@%d estricto(=2)' % K:>17s} {'P@%d laxo(>=1)' % K:>14s} {'NDCG@%d' % K:>8s}")
        for m in metodos:
            r = res[m]
            print(f"{m:16s} {100*np.mean(r['P_estricto']):16.0f}% {100*np.mean(r['P_laxo']):13.0f}% {np.mean(r['NDCG']):8.2f}")
        print(f"\nComparaciones emparejadas por tendencia, P@{K} estricto (pp). IC95% t con {len(estilos)-1} gl; p = permutación exacta de signos:")
        semianchuras = []
        for a, b, que in comparaciones:
            if a not in res or b not in res:
                continue
            d = np.array(res[a]["P_estricto"]) - np.array(res[b]["P_estricto"])
            media, lo, hi, p = estadistica_emparejada(d)
            semianchuras.append((hi - lo) / 2)
            if lo > 0 and media >= 0.05:
                veredicto = "MEJORA"
            elif hi < 0 and media <= -0.05:
                veredicto = "EMPEORA"
            else:
                veredicto = "neutro/no concluyente"
            print(f"  {a:16s} − {b:16s} {100*media:+5.0f} pp  IC95% [{100*lo:+4.0f}, {100*hi:+4.0f}]  p={p:.3f}  "
                  f"gana {int((d > 0).sum())}/empata {int((d == 0).sum())}/pierde {int((d < 0).sum())}  -> {veredicto}   ({que})")
        print(f"\nPotencia: con {len(estilos)} tendencias el IC tiene una semianchura típica de ±{100*np.mean(semianchuras):.0f} pp, así que solo se puede "
              f"AFIRMAR una diferencia si es grande; 'neutro' significa 'no se detecta un efecto grande', no 'no hay efecto'.")
    print("\nRegla fijada antes de puntuar (ver README): MEJORA = media >= +5 pp y el IC95% excluye 0; en otro caso, resultado neutro.")


COMP_V1 = (("F_ciego", "T_ciego_en", "¿la fusión mejora al texto realista (ciego)?"),
           ("F_oraculo", "T_oraculo_en", "¿la fusión mejora al texto optimista (oráculo)?"),
           ("V", "T_oraculo_en", "¿solo imagen vs texto optimista?"),
           ("T_ciego_es", "T_ciego_en", "efecto del idioma (español vs inglés)"))
COMP_V2 = (("F_corto", "T_corto_ciego_en", "[v2 primaria] ¿la imagen mejora a un texto corto SIN conocimiento de la taxonomía?"),
           ("T_corto_ciego_en", "T_ciego_en", "[v2 primaria] efecto del FORMATO (corto vs largo), mismo LLM ciego"),
           ("T_corto_ciego_en", "T_oraculo_en", "¿el corto ciego alcanza al oráculo?"),
           ("V", "T_corto_ciego_en", "¿solo imagen vs texto corto ciego?")) + COMP_V1


def cmd_analizar(args):
    analizar_generico(CLAVE, METODOS, ESTILOS, Path(args.ratings) if args.ratings else RATINGS, COMP_V1,
                      "ANÁLISIS v1 (inventario de 1 207 prendas, 7 tendencias; el fijado de antemano)")


def cmd_analizar_v2(args):
    analizar_generico(CLAVE_V2, METODOS_V2, ESTILOS_V2, Path(args.ratings) if args.ratings else RATINGS, COMP_V2,
                      "ANÁLISIS v2 (inventario + 60 prendas geek, 6 tendencias sin lujo_ostentoso, 2 brazos nuevos; EXPLORATORIO salvo lo marcado)")


def cmd_preparar_v2(args):
    """Genera el pool de la v2 como DELTA: solo las prendas (tendencia, imagen) que aún no tienen puntuación."""
    texto = json.loads(TEXTOS.read_text(encoding="utf-8"))["tendencias"]
    if "prompt_corto_en" not in texto[ESTILOS[0]]:
        raise SystemExit("ERROR: faltan los textos v2. Ejecuta:  python3 generar_textos_ciegos.py --solo-v2")
    model, preprocess, tokenizer = cargar_modelo()
    enc = lambda campo, e: encodear_textos(model, tokenizer, [texto[e][campo]])[0].numpy()  # noqa: E731
    T = {"ciego_en": {e: enc("descripcion_en", e) for e in ESTILOS},
         "ciego_es": {e: enc("descripcion_es", e) for e in ESTILOS},
         "oraculo_en": {e: enc("oraculo_en_v2" if "oraculo_en_v2" in texto[e] else "oraculo_en", e) for e in ESTILOS},
         "corto_ciego_en": {e: enc("prompt_corto_en", e) for e in ESTILOS}}
    print("Oráculo v2 distinto del v1 en:", [e for e in ESTILOS if "oraculo_en_v2" in texto[e]])

    rutas_cat, _ = cargar_catalogo(con_extra=True)
    V_cat = con_cache("catalogo_v2", rutas_cat, model, preprocess)
    rutas_real, est_real = cargar_reales()
    V_real = con_cache("reales", rutas_real, model, preprocess)
    print(f"Inventario v2: {len(rutas_cat)} prendas ({len(rutas_cat) - 1207} añadidas). Fotos de evidencia: {len(rutas_real)}.")

    rng = random.Random(0)   # MISMA secuencia de sorteo que la v1: la evidencia de cada tendencia no cambia
    elementos, clave = {}, {}
    for e in ESTILOS:
        idx = np.where(est_real == e)[0]
        ev = V_real[rng.sample(list(idx), min(N_EVIDENCIA, len(idx)))]
        if e not in ESTILOS_V2:
            continue
        for m, vec in vectores_tendencia(e, T, ev).items():
            for rank, j in enumerate(np.argsort(-(V_cat @ vec))[:K_POOL], 1):
                k = f"{e}|{rutas_cat[j].relative_to(POC)}"
                elementos.setdefault(k, {"tendencia": e, "imagen": str(rutas_cat[j].relative_to(POC))})
                clave.setdefault(k, {})[m] = rank
    CLAVE_V2.write_text(json.dumps(clave, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    ratings = json.loads(RATINGS.read_text(encoding="utf-8")) if RATINGS.exists() else {}
    nuevas = [k for k in clave if k not in ratings]
    tramo = {k: 1 if min(clave[k].values()) <= K_TRAMO1 else 2 for k in nuevas}
    barajador = random.Random(2)
    orden = []
    for t in (1, 2):
        grupo = sorted(k for k in nuevas if tramo[k] == t)
        barajador.shuffle(grupo)
        orden += grupo
    POOL_V2.write_text(json.dumps([{"clave": k, "tramo": tramo[k], "nombre": NOMBRE[elementos[k]["tendencia"]],
                                    "rasgos": RASGOS[elementos[k]["tendencia"]], "imagen": elementos[k]["imagen"]}
                                   for k in orden], ensure_ascii=False, indent=1), encoding="utf-8")
    n1 = sum(1 for k in orden if tramo[k] == 1)
    print(f"\nPrendas distintas en el análisis v2: {len(clave)}; ya puntuadas en la v1: {len(clave) - len(nuevas)}; "
          f"NUEVAS por puntuar: {len(orden)} (tramo 1 = {n1}, tramo 2 = {len(orden) - n1}).")
    print("Siguiente paso:  python3 evaluar_b.py --pool pool_b_v2.json   y puntúa;  luego:  python3 experimento_b.py analizar-v2")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("preparar")
    pp.add_argument("--n", type=int, default=N_EVIDENCIA, help="fotos reales de evidencia por tendencia")
    pp.add_argument("--sorteos", type=int, default=30, help="sorteos de la evidencia para la señal automática")
    pp.add_argument("--seed", type=int, default=0)
    pp.set_defaults(f=cmd_preparar)
    pa = sub.add_parser("analizar")
    pa.add_argument("--ratings", default=None, help="fichero de puntuaciones (por defecto ratings_b.json)")
    pa.set_defaults(f=cmd_analizar)
    sub.add_parser("preparar-v2").set_defaults(f=cmd_preparar_v2)
    pa2 = sub.add_parser("analizar-v2")
    pa2.add_argument("--ratings", default=None)
    pa2.set_defaults(f=cmd_analizar_v2)
    args = p.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
