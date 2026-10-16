#!/usr/bin/env python3
"""
Texto de tendencia en lenguaje natural HECHO CON LOS DATOS MEDIDOS (16 de octubre de 2026, a petición de Víctor: «lo del lenguaje natural»).

El diseño de `Estado_arte.md` §6–7 convierte una descripción de la tendencia en un vector con el codificador de texto de CLIP y puntúa cada SKU por coseno. En el Experimento B, lo que
decidió el acierto fue el texto: uno largo escrito por un LLM que solo conocía el NOMBRE de la tendencia dio P@5 de 23 a 34 %; uno corto y bien especificado, 51 %; la evidencia visual no
aportó. Aquí el texto se escribe con plantillas a partir de lo que mide el análisis (qué prendas, formas, estampados y tejidos tiene cada estilo), sin LLM y sin inventar nada:
la misma entrada da siempre el mismo texto y cada palabra tiene detrás una cifra.

Receta R1 (CONGELADA el 16 de octubre de 2026 antes de puntuar nada en el Experimento C; no se ajusta mirando resultados):
  · evidencia: `separacion_estilos.json`, bloque «solo_biblioteca» (la muestra de referencia aprobada por Víctor), `por_estilo`: cada estilo frente a los demás, con cuota, diferencia y q de BH.
  · prendas: lo que DISTINGUE al estilo (cuota ≥ 5 % y al menos +3 puntos por encima del resto de estilos), de más a menos diferencia, como mucho 5; si salen menos de 3, se completan con las
    más frecuentes del estilo hasta 3 (p. ej. «convencional», que por definición no tiene rasgo propio). Un texto con las prendas más frecuentes de todos los estilos (el pantalón, en casi todos)
    describiría lo mismo en cada tendencia; quien puntúa juzga si la prenda encaja con ESE estilo.
  · modificadores: valores de forma, estampado y tejido que distinguen al estilo (q < 0,10 y diferencia ≥ +8 puntos), de más a menos diferencia, como mucho 3. No se usan los valores por
    defecto (regular, algodón, no aplica, no se distingue); «liso» solo si la diferencia es ≥ +15 puntos.
  · plantilla (inglés, para CLIP; el texto en español es para que lo apruebe una persona): «{nombre del estilo} style outfit, {modificadores}: {prenda}, {prenda}, …».
  · el nombre del estilo es el mismo dato que reciben los textos ciegos del Experimento B; lo único nuevo es la evidencia medida.

Uso:
  python3 texto_tendencia.py generar [--bloque solo_biblioteca] [--salida textos_datos.json]       escribe los textos y la evidencia de cada estilo
  python3 texto_tendencia.py ver                                                                    los imprime
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TD = AQUI / "tendencia_datos"
VERSION_RECETA = "R1"

# claves del flujo (tendencia_prenda.py) → claves del Experimento B (Estado_arte §3.4.2)
CLAVE_B = {"urbano": "urbano", "geek": "alternativo_geek", "clasico": "clasico_tradicional", "old_money": "old_money", "lujo": "lujo_ostentoso", "bohemio": "bohemio", "convencional": "convencional"}
NOMBRE_ES = {"urbano": "Urbano", "geek": "Alternativo-geek", "clasico": "Clásico-tradicional", "old_money": "Old money", "lujo": "Lujo ostentoso", "bohemio": "Bohemio", "convencional": "Convencional"}
NOMBRE_EN = {"urbano": "urban", "geek": "alternative geek", "clasico": "classic traditional", "old_money": "old money", "lujo": "ostentatious luxury", "bohemio": "bohemian", "convencional": "conventional"}
# Estado_arte §3.4.2: «Grupo de estilo más cercano» (el primero es el principal; los demás, los cruces que el documento menciona)
GRUPOS_ERP = {"old_money": ["De vestir", "Casual"], "lujo": ["De vestir", "Fiesta/Noche"], "clasico": ["Casual", "De vestir"], "urbano": ["Streetwear"],
              "bohemio": ["Casual", "Playa/Resort"], "geek": ["Casual"], "convencional": ["Casual"]}
TIPO_EN = {"Camiseta manga corta": "t-shirt", "Camiseta de tirantes": "tank top", "Camiseta manga larga": "long-sleeve t-shirt", "Top": "crop top", "Camisa": "button-up shirt", "Polo": "polo shirt",
           "Sudadera": "sweatshirt", "Hoodie": "hoodie", "Jersey": "knit sweater", "Chaleco sin mangas": "sleeveless vest", "Chaqueta": "jacket", "Americana": "blazer", "Abrigo": "long coat",
           "Plumas": "puffer jacket", "Pantalón": "trousers", "Falda": "skirt", "Short": "shorts", "Legging/Malla": "leggings", "Vestido": "dress", "Mono": "jumpsuit",
           "Zapatillas deportivas": "sneakers", "Zapatillas casual/lifestyle": "casual sneakers", "Zapatos de vestir": "dress shoes", "Zapatos de tacón": "high heels", "Sandalias": "sandals",
           "Botas": "boots", "Bolso": "handbag", "Riñonera": "fanny pack", "Gorra/Gorro/Sombrero": "cap"}
FORMA_EN = {"oversized / baggy": "oversized baggy", "ajustada": "slim-fit", "corta / cropped": "cropped"}
ESTAMPADO_EN = {"gráfico / dibujo": "graphic print", "texto / logo": "logo print", "rayas": "striped", "cuadros": "checked", "camuflaje": "camouflage", "otro": "patterned", "liso": "plain solid-color"}
TEJIDO_EN = {"denim (vaquero)": "denim", "cuero / vinilo": "leather", "punto": "knit", "felpa / polar": "fleece", "técnico / impermeable": "technical", "pana": "corduroy",
             "terciopelo": "velvet", "seda / satén": "satin", "tul / encaje": "lace", "lino": "linen"}
# mismo vocabulario en español para el texto que lee una persona
TIPO_ES = {k: k.lower() for k in TIPO_EN}
VALOR_ES = {"oversized / baggy": "oversized", "ajustada": "ajustada", "corta / cropped": "corta", "gráfico / dibujo": "con gráfico", "texto / logo": "con texto o logo", "rayas": "de rayas",
            "cuadros": "de cuadros", "camuflaje": "de camuflaje", "otro": "con estampado", "liso": "lisa", "denim (vaquero)": "de vaquero", "cuero / vinilo": "de cuero", "punto": "de punto",
            "felpa / polar": "de felpa", "técnico / impermeable": "técnica", "pana": "de pana", "terciopelo": "de terciopelo", "seda / satén": "de satén", "tul / encaje": "de encaje", "lino": "de lino"}
TABLA = {"forma": FORMA_EN, "estampado": ESTAMPADO_EN, "tejido": TEJIDO_EN}
CUOTA_MIN, DIF_TIPO_MIN, DIF_MOD_MIN, DIF_LISO_MIN, Q_MAX, MAX_PRENDAS, MIN_PRENDAS, MAX_MODS = 0.05, 0.03, 0.08, 0.15, 0.10, 5, 3, 3


def cargar_separacion(td: Path = TD, bloque: str = "solo_biblioteca") -> dict:
    return json.loads((td / "separacion_estilos.json").read_text(encoding="utf-8"))[bloque]["por_estilo"]


def evidencia(sep: dict, estilo: str) -> dict:
    """Lo medido de un estilo, por dimensión: lista de {valor, estilo, resto, dif, q} y los recuentos."""
    out = {"prendas": None, "fotos": None}
    for d in sep["dimensiones"]:
        e = d["estilos"].get(estilo)
        if not e:
            continue
        out["prendas"], out["fotos"] = e["prendas"], e["fotos"]
        out[d["dimension"]] = [{"valor": c["categoria"], "estilo": c["estilo"], "resto": c["resto"], "dif": c["dif"], "q": c["q"], "n": c["n"]} for c in e["categorias"]]
    return out


def elegir(ev: dict) -> tuple[list[dict], list[dict]]:
    """Aplica la receta R1: (prendas, modificadores) con la cifra que respalda cada uno. Las prendas se muestran con su cuota en el estilo y su diferencia con el resto."""
    tipos = [c for c in ev.get("tipo", []) if c["valor"] in TIPO_EN]
    prendas = sorted([c for c in tipos if c["estilo"] >= CUOTA_MIN and c["dif"] >= DIF_TIPO_MIN], key=lambda c: -c["dif"])[:MAX_PRENDAS]
    if len(prendas) < MIN_PRENDAS:   # estilo sin rasgo propio en prendas: se completan con las más frecuentes
        resto = sorted([c for c in tipos if c not in prendas], key=lambda c: -c["estilo"])
        prendas += resto[:MIN_PRENDAS - len(prendas)]
    mods = []
    for dim, tabla in TABLA.items():
        for c in ev.get(dim, []):
            minimo = DIF_LISO_MIN if c["valor"] == "liso" else DIF_MOD_MIN
            if c["valor"] in tabla and c["q"] < Q_MAX and c["dif"] >= minimo:
                mods.append({**c, "dimension": dim})
    mods = sorted(mods, key=lambda c: -c["dif"])[:MAX_MODS]
    return prendas, mods


def texto_en(estilo: str, prendas: list[dict], mods: list[dict]) -> str:
    adj = ", ".join(TABLA[m["dimension"]][m["valor"]] for m in mods)
    cab = f"{NOMBRE_EN[estilo]} style outfit" + (f", {adj}" if adj else "")
    return cab + ": " + ", ".join(TIPO_EN[p["valor"]] for p in prendas)


def texto_es(estilo: str, prendas: list[dict], mods: list[dict], n_fotos: int | None = None) -> str:
    mods_es = ", ".join(VALOR_ES[m["valor"]] + f" ({100 * m['estilo']:.0f} % frente a {100 * m['resto']:.0f} %)" for m in mods)
    pr = ", ".join(f"{TIPO_ES[p['valor']]} ({100 * p['estilo']:.0f} %)" for p in prendas)
    base = f"{NOMBRE_ES[estilo]}: prendas que lo caracterizan (cuota en el estilo): {pr}."
    if mods_es:
        base += f" Lo que lo distingue de los demás estilos: {mods_es}."
    return base + (f" Muestra de referencia: {n_fotos} fotos." if n_fotos else "")


def trend_json(estilo: str, sep: dict, fecha: str | None = None, mercado: str = "Europa (muestra de referencia)") -> dict:
    """Trend JSON de Estado_arte §6.4 + los campos de evidencia. `intensidad` es None para la muestra de referencia (no hay viralidad que medir)."""
    ev = evidencia(sep, estilo)
    prendas, mods = elegir(ev)
    return {"mercado": mercado, "sub_estilo": CLAVE_B[estilo], "nombre": NOMBRE_ES[estilo], "genero_objetivo": "Todo", "tipo_prenda": "Todo", "fuentes": ["muestra de referencia aprobada por Víctor"],
            "fecha_analisis": fecha or datetime.now(timezone.utc).strftime("%Y-%m-%d"), "descripcion": texto_es(estilo, prendas, mods, ev["fotos"]), "descripcion_clip": texto_en(estilo, prendas, mods),
            "grupo_estilo_detectado": GRUPOS_ERP[estilo], "intensidad": None, "estado": "pendiente",
            "evidencia": {"receta": VERSION_RECETA, "prendas_medidas": ev["prendas"], "fotos": ev["fotos"], "prendas": prendas, "modificadores": mods}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("generar", "ver"):
        p = sub.add_parser(n)
        p.add_argument("--bloque", default="solo_biblioteca")
        p.add_argument("--datos", type=Path, default=TD)
        if n == "generar":
            p.add_argument("--salida", type=Path, required=True)
    a = ap.parse_args()
    sep = cargar_separacion(a.datos, a.bloque)
    estilos = [e for e in CLAVE_B if any(e in d["estilos"] for d in sep["dimensiones"])]
    textos = {e: trend_json(e, sep) for e in estilos}
    if a.cmd == "ver":
        for e, t in textos.items():
            print(f"[{e}] {t['descripcion_clip']}\n     {t['descripcion']}\n     grupos ERP: {t['grupo_estilo_detectado']}")
        return
    a.salida.write_text(json.dumps({"receta": VERSION_RECETA, "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bloque": a.bloque, "estilos": textos}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(textos)} textos en {a.salida}")


if __name__ == "__main__":
    sys.exit(main())
