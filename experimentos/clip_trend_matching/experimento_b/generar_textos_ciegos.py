#!/usr/bin/env python3
"""
Experimento B -- línea base de TEXTO honesta.

Un LLM que NO conoce la taxonomía interna (solo recibe el nombre de la tendencia, sin definiciones
ni rasgos) redacta la `descripcion` que pondría el Trend Intelligence Agent (Estado_arte.md S6.4),
primero en español (como la produce el pipeline) y luego traducida al inglés (CLIP ViT-B/32 de OpenAI
se entrenó con texto en inglés: comparar los dos idiomas aísla ese efecto, que si no contaminaría la
comparación texto-vs-imagen). Se añade además un tercer brazo "oráculo": prompts escritos a mano por
Claude CONOCIENDO la taxonomía -- NO es ciego, sirve solo de cota superior optimista del texto.

Usa la API gratuita de Google AI Studio (sin tarjeta; clave en ~/.config/gemini/api_key), temperatura 0.
Escribe textos_tendencia_b.json (se versiona: el experimento debe poder reproducirse con los mismos textos).

    python3 generar_textos_ciegos.py            # v1: regenera TODOS los textos (cambiaría el experimento ya puntuado)
    python3 generar_textos_ciegos.py --solo-v2  # v2: solo AÑADE el prompt corto ciego y el oráculo corregido
"""
import json
import time
from datetime import date
from pathlib import Path

from google import genai
from google.genai import types

SALIDA = Path(__file__).parent / "textos_tendencia_b.json"
MODELO = "gemini-3.5-flash-lite"

# Solo el NOMBRE, tal como lo diría una cuenta de moda. Nada de definiciones.
NOMBRES = {
    "old_money": "Old Money",
    "lujo_ostentoso": "Lujo ostentoso",
    "clasico_tradicional": "Clásico tradicional",
    "urbano": "Urbano",
    "bohemio": "Bohemio",
    "alternativo_geek": "Alternativo geek",
    "convencional": "Convencional",
}

# Brazo oráculo (NO ciego): los prompts en inglés usados en las mediciones previas de este proyecto.
ORACULO_EN = {
    "old_money": "an old money quiet luxury outfit, tailored classic preppy clothes in neutral colors",
    "lujo_ostentoso": "a flashy ostentatious luxury outfit with designer logos and bling",
    "clasico_tradicional": "a classic traditional conservative elegant formal outfit",
    "urbano": "an urban streetwear outfit with hoodie and sneakers",
    "bohemio": "a bohemian boho outfit with flowy fabrics and earthy tones",
    "alternativo_geek": "an alternative geek outfit, techwear, goth or punk style",
    "convencional": "a plain everyday casual conventional outfit",
}

PROMPT_ES = (
    "Eres el Trend Intelligence Agent de un sistema de gestión de moda. Te doy el nombre de una "
    "tendencia de moda tal y como aparece en redes sociales. Redacta el campo `descripcion` de tu "
    "informe: 2 o 3 frases, en español, que describan las prendas, colores, siluetas, materiales y el "
    "contexto de uso típicos de esa tendencia. No repitas el nombre de la tendencia ni uses listas. "
    "Responde SOLO con la descripción.\n\nTendencia: {nombre}"
)
# --- v2 (añadido el 2026-10-03, DESPUÉS de ver los resultados de la v1; ver README) ---
# Brazo nuevo "prompt corto ciego": mismo LLM ciego (solo el nombre), pero pidiéndole un prompt corto y concreto.
# Separa el efecto del FORMATO del texto del efecto del CONOCIMIENTO de la taxonomía (el oráculo mezclaba ambos).
PROMPT_CORTO = (
    "Eres un experto en moda. Te doy el nombre de una tendencia de moda. Escribe un prompt CORTO en inglés "
    "(máximo 15 palabras) que describa un look típico de esa tendencia, nombrando prendas concretas, colores o "
    "siluetas, pensado para buscar prendas por similitud imagen-texto en un catálogo. No repitas el nombre de la "
    "tendencia. Responde SOLO con el prompt.\n\nTendencia: {nombre}"
)
# Corrección del oráculo para «alternativo_geek»: el de la v1 decía "techwear, goth or punk" y la taxonomía de
# Víctor (Estado_arte.md S3.4.2; su referencia es Orslok) define fandom: gaming, anime, cómic. Se redacta a partir de
# esa definición escrita, no de suposiciones sobre el vestuario de ninguna persona concreta.
ORACULO_EN_V2 = {
    "alternativo_geek": "a geek fandom outfit, graphic t-shirt or hoodie with anime, video game or comic print",
}

PROMPT_EN = (
    "Traduce al inglés el siguiente texto de moda manteniendo todo su contenido, con un tono "
    "descriptivo apto para un modelo imagen-texto. Responde SOLO con la traducción.\n\n{texto}"
)


def llamar(cliente, prompt):
    for intento in range(6):
        try:
            r = cliente.models.generate_content(
                model=MODELO, contents=prompt, config=types.GenerateContentConfig(temperature=0)
            )
            return r.text.strip()
        except Exception as e:  # 429/503 del nivel gratuito: reintento con espera creciente
            espera = 10 * (intento + 1)
            print(f"  (aviso) {type(e).__name__}: reintento en {espera}s")
            time.sleep(espera)
    raise SystemExit("ERROR: la API no respondió tras 6 intentos.")


def anadir_v2():
    """Añade a textos_tendencia_b.json (SIN regenerar nada de lo existente) el prompt corto ciego y el oráculo corregido."""
    cliente = genai.Client(api_key=(Path.home() / ".config" / "gemini" / "api_key").read_text().strip())
    datos = json.loads(SALIDA.read_text(encoding="utf-8"))
    for estilo, t in datos["tendencias"].items():
        if "prompt_corto_en" not in t:
            t["prompt_corto_en"] = llamar(cliente, PROMPT_CORTO.format(nombre=t["nombre"])).strip().strip('"')
        if estilo in ORACULO_EN_V2:
            t["oraculo_en_v2"] = ORACULO_EN_V2[estilo]
        print(f"- {estilo}: {t['prompt_corto_en']}")
    datos["prompt_corto"] = PROMPT_CORTO
    datos["aviso_v2"] = ("prompt_corto_en: ciego (solo el nombre), añadido tras ver la v1. oraculo_en_v2: corrección del oráculo "
                         "de alternativo_geek según la definición de la taxonomía.")
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nActualizado {SALIDA}")


def main():
    import sys
    if "--solo-v2" in sys.argv:
        return anadir_v2()
    clave = (Path.home() / ".config" / "gemini" / "api_key").read_text().strip()
    cliente = genai.Client(api_key=clave)
    tendencias = {}
    for estilo, nombre in NOMBRES.items():
        es = llamar(cliente, PROMPT_ES.format(nombre=nombre))
        en = llamar(cliente, PROMPT_EN.format(texto=es))
        tendencias[estilo] = {"nombre": nombre, "descripcion_es": es, "descripcion_en": en,
                              "oraculo_en": ORACULO_EN[estilo]}
        print(f"- {estilo}\n    ES: {es}\n    EN: {en}")
    SALIDA.write_text(json.dumps({
        "modelo": MODELO, "fecha": date.today().isoformat(), "temperatura": 0,
        "prompt_es": PROMPT_ES, "prompt_en": PROMPT_EN,
        "aviso": "descripcion_es/en son ciegas (solo el nombre); oraculo_en NO es ciego (cota superior optimista).",
        "tendencias": tendencias,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nEscrito {SALIDA}")


if __name__ == "__main__":
    main()
