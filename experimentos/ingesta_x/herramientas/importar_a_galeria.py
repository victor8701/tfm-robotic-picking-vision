#!/usr/bin/env python3
"""Importa a la galería (panel/data/clasificaciones.json + panel/static/fotos/) las fotos que
procesar_cola.py ya descargó en data/<estilo>/ -- ese script se escribió antes de que existiera
la galería unificada y nunca llegó a conectarse con ella: descargaba bien, pero las fotos se
quedaban ahí, invisibles en la app. Este script es el puente que faltaba.

Idempotente: a cada foto le da un id derivado del tweet (x_<tweet_id>_<indice>), así que
ejecutarlo varias veces no duplica nada -- solo importa lo que todavía no esté.

Uso: python importar_a_galeria.py (se ejecuta después de procesar_cola.py, mismo directorio
de trabajo que el resto de herramientas de este proyecto).
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).parent.parent
DIR_DATA = RAIZ / "data"
RUTA_CLASIFICACIONES = RAIZ / "panel" / "data" / "clasificaciones.json"
DIR_FOTOS = RAIZ / "panel" / "static" / "fotos"

# Mismas 7 categorías que ya usa la galería (app.py: CATEGORIAS) -- cualquier otra carpeta en
# data/ (p. ej. "prueba_lote", de cuando se probó el descargador) se ignora a propósito: meterla
# rompería el agrupado por estilo de la galería, que solo conoce estas 7.
ESTILOS_VALIDOS = {
    "old_money", "lujo_ostentoso", "clasico_tradicional", "urbano",
    "bohemio", "alternativo_geek", "convencional",
}

TAMAÑO_MAX = 1200


def cargar_clasificaciones() -> dict:
    if not RUTA_CLASIFICACIONES.exists():
        return {}
    return json.loads(RUTA_CLASIFICACIONES.read_text(encoding="utf-8"))


def comprimir_y_guardar(origen: Path, destino: Path) -> None:
    with Image.open(origen) as img:
        img = img.convert("RGB")
        img.thumbnail((TAMAÑO_MAX, TAMAÑO_MAX), Image.LANCZOS)
        img.save(destino, "JPEG", quality=85, optimize=True)


def main() -> None:
    if not DIR_DATA.exists():
        print("No existe data/, nada que importar.")
        return

    clasificaciones = cargar_clasificaciones()
    ids_existentes = set(clasificaciones.keys())
    nuevas = 0
    ignoradas_carpeta = set()

    for carpeta_estilo in sorted(DIR_DATA.iterdir()):
        if not carpeta_estilo.is_dir():
            continue
        estilo = carpeta_estilo.name
        if estilo not in ESTILOS_VALIDOS:
            ignoradas_carpeta.add(estilo)
            continue

        for ruta_meta in sorted(carpeta_estilo.glob("*_metadata.json")):
            meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
            tweet_id = meta.get("tweet_id", ruta_meta.stem)
            for indice, nombre_archivo in enumerate(meta.get("imagenes", []), start=1):
                nuevo_id = f"x_{tweet_id}_{indice}"
                if nuevo_id in ids_existentes:
                    continue
                origen = carpeta_estilo / nombre_archivo
                if not origen.exists():
                    print(f"Aviso: falta el fichero {origen}, se salta")
                    continue

                nombre_destino = f"{nuevo_id}.jpg"
                DIR_FOTOS.mkdir(parents=True, exist_ok=True)
                comprimir_y_guardar(origen, DIR_FOTOS / nombre_destino)

                clasificaciones[nuevo_id] = {
                    "categoria_final": estilo,
                    "categoria_ia": estilo,
                    "revisada": False,
                    "ocasion_final": None,
                    "eliminada": False,
                    "origen": "claude",
                    "fuente": f"@{meta.get('cuenta', '?')} (X)",
                    "fuente_url": meta.get("url_original", ""),
                    "imagen": nombre_destino,
                }
                ids_existentes.add(nuevo_id)
                nuevas += 1

    if ignoradas_carpeta:
        print(f"Carpetas ignoradas (no son una categoría válida): {', '.join(sorted(ignoradas_carpeta))}")

    if nuevas:
        RUTA_CLASIFICACIONES.write_text(
            json.dumps(clasificaciones, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(f"Importadas {nuevas} foto(s) nueva(s) a la galería (sin revisar).")


if __name__ == "__main__":
    main()
