#!/usr/bin/env python3
"""Taxonomía de estilos/ocasiones y textos de búsqueda predeterminados -- fuente única, para que
el panel de Render (app.py) y los scripts que corren en GitHub Actions (buscar_x.py,
lanzar_busquedas_automaticas.py) usen siempre exactamente los mismos textos, ya afinados con
datos reales (ver los comentarios de cada estilo). Sin Flask ni nada más que stdlib, para poder
importarse desde cualquiera de los dos sitios sin arrastrar dependencias que no hacen falta ahí.
"""
from __future__ import annotations

CATEGORIAS = [
    ("old_money", "Old Money"), ("lujo_ostentoso", "Lujo ostentoso"),
    ("clasico_tradicional", "Clásico-tradicional"), ("urbano", "Urbano"),
    ("bohemio", "Bohemio"), ("alternativo_geek", "Alternativo-geek"),
    ("convencional", "Convencional"),
]
NOMBRE_CATEGORIA = dict(CATEGORIAS) | {"ninguna": "Ninguna"}
ESTILOS_CHIP = [("ninguna", "Ninguna")] + CATEGORIAS

OCASIONES = [
    ("ninguna", "Ninguna"), ("fiesta_noche", "Fiesta/Noche"), ("deportivo", "Deportivo"),
    ("playa_resort", "Playa/Resort"), ("arreglado", "Arreglado"),
]
NOMBRE_OCASION = dict(OCASIONES)

# Mismos textos que usaba el artefacto retirado, para que "predeterminado" y "automático"
# sigan dando resultados consistentes con las fotos ya clasificadas.
TEXTO_PREDETERMINADO_ESTILO = {
    "old_money": "old money aesthetic outfit quiet luxury real photos",
    # "luxury streetwear" compartía las palabras "luxury" (con old_money, que busca "quiet
    # luxury" -- lo opuesto) y "streetwear" (con urbano y alternativo_geek) -- de las 2 fotos
    # reales que trajo, una era un artículo genérico de tendencias streetwear (sin nada de
    # ostentoso), Víctor la corrigió a "urbano" (revisión real, 2026-09-27). Menos solape:
    # "logomania"/"flashy"/"designer brands" describen justo lo ostentoso, sin la palabra
    # "streetwear" que ya usan otros dos estilos.
    "lujo_ostentoso": "logomania flashy designer brands outfit real photos",
    "clasico_tradicional": "cayetana style outfit spain classic preppy",
    "urbano": "moda trap español streetwear outfit real",
    "bohemio": "bohemian boho chic outfit real photos",
    # Dos intentos previos, los dos descartados con datos reales (Víctor revisó a mano,
    # 2026-09-27):
    # v1 "geek gamer streetwear": traía cuentas de equipos de esports (TeamLiquid, G2esports),
    #   merchandising de marca de equipo, no una estética geek/tech propia (6 de 6 corregidas).
    # v2 "techwear cyberpunk...": "cyberpunk" resultó ser un imán todavía peor -- de 48 fotos
    #   eliminadas por Víctor, la inmensa mayoría eran arte digital/3D de personajes ficticios
    #   (fan art, a veces con desnudez parcial; modelos 3D descargables de Genshin; hojas de
    #   personaje de OCs/furries), porque "cyberpunk" lo usa muchísimo más la comunidad de
    #   dibujantes/3D en X que la de moda real. "techwear" en sí SÍ es una subcultura real con
    #   fotos de calle de verdad -- se queda, pero sin "cyberpunk" ni "tech accessories" (ese
    #   "tech" genérico también atraía renders). "gorpcore"/"utilitarian" son términos de moda
    #   real equivalentes que no arrastran esa comunidad.
    "alternativo_geek": "techwear utilitarian gorpcore streetwear outfit real photos",
    "convencional": "normcore basic outfit real photos",
}
CALIFICADOR_OCASION = {
    "fiesta_noche": "night out party look",
    "deportivo": "athletic sporty look",
    "playa_resort": "beach resort vacation look",
    "arreglado": "dressed up smart casual look",
}


def calcular_texto_busqueda(estilo: str, ocasion: str, modo: str, texto_manual: str) -> str:
    if modo == "personalizado":
        return (texto_manual or "").strip()
    base = TEXTO_PREDETERMINADO_ESTILO.get(estilo, "")
    if modo == "predeterminado":
        return base
    # "automatico": añade un calificador de ocasión mecánicamente, si se ha elegido una.
    calificador = CALIFICADOR_OCASION.get(ocasion)
    return f"{base} {calificador}" if calificador else base
