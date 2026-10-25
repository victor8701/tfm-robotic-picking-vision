#!/usr/bin/env python3
"""
Trend JSON por estilo × mercado × temporada (Estado_arte.md §6.4) a partir de lo que mide la tubería de «tendencia por prenda» (25 de octubre de 2026).

Entrada:  `informe.json` (cuota de cada prenda por estilo × mercado × temporada, con intervalo y nivel de confianza) y `separacion_estilos.json` (rasgos que distinguen a cada estilo:
          forma, estampado y tejido; receta R1 de `texto_tendencia.py`).
Salida:   `trends/pending/{fecha}_{mercado}_{estilo}.json`, uno por casilla con datos suficientes, en estado «pendiente» (el operario lo aprueba o rechaza en el HMI, §6.5), y
          `trends/indice.json` con TODAS las casillas y, en las que no se generan, por qué (pocos datos).

Qué hace el texto (sin LLM, sin inventar nada: cada palabra tiene una cifra detrás):
  · prendas = las de esa casilla (ese estilo en ese mercado y temporada) con cuota medida y al menos `min_fotos` fotos, de más a menos cuota, como mucho 5; si hay menos de 3, la casilla no se genera.
  · adjetivos = los rasgos del estilo con la receta R1 (valores de forma, estampado y tejido que lo distinguen de los demás estilos), que salen de la muestra de referencia y no de la casilla
    (la casilla tiene pocas fotos para estimarlos).
  · descripcion_clip (inglés, para el codificador de texto de CLIP): «{estilo} style outfit, {adjetivos}: {prenda}, {prenda}, …» (el texto corto con datos que ganó o empató en el Experimento C).
  · descripcion (español, para la persona que aprueba): las mismas prendas con su cuota, número de fotos y confianza.
  · grupo_estilo_detectado: los grupos del ERP del estilo (`GRUPOS_ERP`); intensidad: null (todavía no hay medida de viralidad: la cifra no se inventa).

Uso:  python3 trend_json_mercado.py generar [--datos CARPETA_tendencia_datos] [--salida CARPETA_trends] [--min-fotos 5] [--fecha AAAA-MM-DD]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent.parent
sys.path.insert(0, str(REPO / "experimentos" / "analisis_mercado"))
import texto_tendencia as tt  # noqa: E402

TD = REPO / "experimentos" / "analisis_mercado" / "tendencia_datos"
MERCADO_ES = {"ES": "España", "US": "EEUU"}
MIN_PRENDAS_CASILLA = 3
MAX_PRENDAS = 5
CONFIANZA_ES = {"baja": "baja", "media": "media", "alta": "alta", None: "sin medir"}


def temporada(fecha: datetime) -> str:
    """Primavera-verano = marzo-agosto, otoño-invierno = septiembre-febrero (igual que `tendencia_prenda.temporada`)."""
    if 3 <= fecha.month <= 8:
        return f"PV {fecha.year}"
    return f"OI {fecha.year}/{str(fecha.year + 1)[2:]}" if fecha.month >= 9 else f"OI {fecha.year - 1}/{str(fecha.year)[2:]}"


def casillas(informe: dict, temp: str) -> list[dict]:
    """Las casillas estilo × mercado (ES, US) de la temporada dada; si un estilo no tiene nada en esa temporada en un mercado, no sale (el índice lo cuenta como «sin fotos»)."""
    return [g for g in informe["grupos"] if g["mercado"] in MERCADO_ES and g["temporada"] == temp]


def prendas_de_casilla(casilla: dict, min_fotos: int) -> list[dict]:
    pr = [p for p in casilla["prendas"] if p.get("cuota") is not None and p["fotos"] >= min_fotos and p["tipo"] in tt.TIPO_EN]
    return sorted(pr, key=lambda p: -p["cuota"])[:MAX_PRENDAS]


def texto_clip(estilo: str, prendas: list[dict], mods: list[dict]) -> str:
    adj = ", ".join(tt.TABLA[m["dimension"]][m["valor"]] for m in mods)
    return f"{tt.NOMBRE_EN[estilo]} style outfit" + (f", {adj}" if adj else "") + ": " + ", ".join(tt.TIPO_EN[p["tipo"]] for p in prendas)


def texto_es(estilo: str, mercado: str, temp: str, casilla: dict, prendas: list[dict], mods: list[dict]) -> str:
    pr = "; ".join(f"{tt.TIPO_ES[p['tipo']]} ({100 * p['cuota']:.0f} % de las fotos con prenda, {p['fotos']} fotos, confianza {CONFIANZA_ES.get(p.get('confianza'), p.get('confianza'))})" for p in prendas)
    t = f"{tt.NOMBRE_ES[estilo]} en {MERCADO_ES[mercado]}, {temp}: las prendas más presentes en las fotos de los referentes del estilo son {pr}."
    if mods:
        t += " Rasgos que distinguen al estilo de los demás: " + ", ".join(tt.VALOR_ES[m["valor"]] for m in mods) + " (medidos en la muestra de referencia)."
    return t + f" Base: {casilla['fotos']} fotos ({casilla['fotos_efectivas']:.0f} efectivas) de {len(casilla.get('fuentes') or {})} fuentes."


def trend_de_casilla(casilla: dict, sep_estilo: dict, fecha: str, min_fotos: int = 5) -> tuple[dict | None, str | None]:
    """(Trend JSON, None) o (None, motivo por el que la casilla no se genera)."""
    estilo, mercado, temp = casilla["estilo"], casilla["mercado"], casilla["temporada"]
    prendas = prendas_de_casilla(casilla, min_fotos)
    if len(prendas) < MIN_PRENDAS_CASILLA:
        return None, f"solo {len(prendas)} prendas con al menos {min_fotos} fotos (hacen falta {MIN_PRENDAS_CASILLA}); fotos de la casilla: {casilla['fotos']}"
    _, mods = tt.elegir(tt.evidencia(sep_estilo, estilo))
    return {
        "id": f"{fecha}_{mercado}_{estilo}", "mercado": MERCADO_ES[mercado], "mercado_codigo": mercado, "temporada": temp, "genero_objetivo": "Todo", "tipo_prenda": "Todo",
        "sub_estilo": tt.CLAVE_B[estilo], "nombre": f"{tt.NOMBRE_ES[estilo]} · {MERCADO_ES[mercado]} · {temp}", "fuentes": sorted((casilla.get("fuentes") or {}).keys()), "fecha_analisis": fecha,
        "descripcion": texto_es(estilo, mercado, temp, casilla, prendas, mods), "descripcion_clip": texto_clip(estilo, prendas, mods),
        "grupo_estilo_detectado": tt.GRUPOS_ERP[estilo], "intensidad": None, "intensidad_nota": "sin medida de viralidad todavía: no se inventa una cifra", "estado": "pendiente",
        "evidencia": {"receta": "R1 (rasgos del estilo) + cuota por prenda de la casilla", "fotos": casilla["fotos"], "fotos_efectivas": casilla["fotos_efectivas"],
                      "prendas": [{"tipo": p["tipo"], "cuota": p["cuota"], "ic": p.get("ic"), "fotos": p["fotos"], "confianza": p.get("confianza")} for p in prendas],
                      "modificadores": [{k: m[k] for k in ("dimension", "valor", "estilo", "resto", "dif", "q")} for m in mods]},
    }, None


def generar(informe: dict, sep: dict, fecha: str, min_fotos: int = 5, temp: str | None = None) -> tuple[list[dict], list[dict]]:
    temp = temp or temporada(datetime.fromisoformat(fecha))
    trends, indice = [], []
    hechas = set()
    for c in sorted(casillas(informe, temp), key=lambda g: (g["estilo"], g["mercado"])):
        t, motivo = trend_de_casilla(c, sep, fecha, min_fotos)
        hechas.add((c["estilo"], c["mercado"]))
        indice.append({"estilo": c["estilo"], "mercado": c["mercado"], "temporada": temp, "fotos": c["fotos"], "generada": t is not None, "motivo": motivo, "id": t["id"] if t else None})
        if t:
            trends.append(t)
    for e in tt.CLAVE_B:
        for m in MERCADO_ES:
            if (e, m) not in hechas:
                indice.append({"estilo": e, "mercado": m, "temporada": temp, "fotos": 0, "generada": False, "motivo": "ninguna foto de este estilo y mercado en la temporada", "id": None})
    return trends, sorted(indice, key=lambda x: (x["estilo"], x["mercado"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("generar")
    p.add_argument("--datos", type=Path, default=TD)
    p.add_argument("--salida", type=Path, default=AQUI / "trends")
    p.add_argument("--min-fotos", type=int, default=5)
    p.add_argument("--fecha", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    a = ap.parse_args()
    informe = json.loads((a.datos / "informe.json").read_text(encoding="utf-8"))
    sep = tt.cargar_separacion(a.datos)
    trends, indice = generar(informe, sep, a.fecha, a.min_fotos)
    (a.salida / "pending").mkdir(parents=True, exist_ok=True)
    for t in trends:
        (a.salida / "pending" / f"{t['id']}.json").write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.salida / "indice.json").write_text(json.dumps({"fecha": a.fecha, "temporada": indice[0]["temporada"] if indice else None, "casillas": indice}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(trends)} Trend JSON pendientes en {a.salida / 'pending'}; {sum(not x['generada'] for x in indice)} casillas sin generar (ver indice.json)")
    for x in indice:
        print(f"  {'✔' if x['generada'] else '·'} {x['estilo']:12} {x['mercado']}  fotos {x['fotos']:4}  {x['motivo'] or ''}")


if __name__ == "__main__":
    main()
