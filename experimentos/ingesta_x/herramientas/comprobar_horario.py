#!/usr/bin/env python3
"""Comprueba si toca ejecutar la ingesta ahora mismo, según config.json (activo + horas_locales +
zona_horaria). Pensado como paso de GitHub Actions: imprime el resultado y, si existe la
variable de entorno GITHUB_OUTPUT, deja ahí "toca=true"/"toca=false" para que el resto de pasos
del workflow decidan si ejecutarse.

El workflow se dispara cada hora (ver el cron); este script decide si ESTA hora está en la lista
configurada -- así el horario (incluida la frecuencia: una vez al día, varias...) se controla
editando config.json, no tocando el cron del YAML. `horas_locales` es una lista (p. ej. [8, 20]
para dos veces al día) en vez de una sola hora -- 2026-09-27: se pasó de 1 a 2 veces al día para
acelerar la recolección hacia la meta de [[project-ingesta-viral-clips]] sin gastar más cuota de
Tavily (el techo de resultados por búsqueda ya estaba en el máximo de la API, ver
lanzar_busquedas_automaticas.py) y sin que nadie tenga que disparar nada a mano.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUTA_CONFIG = Path(__file__).parent.parent / "config.json"


def main() -> None:
    config = json.loads(RUTA_CONFIG.read_text())
    activo = bool(config.get("activo", True))
    horas_locales = config.get("horas_locales") or [3]
    zona = config.get("zona_horaria", "Europe/Madrid")

    ahora = datetime.now(ZoneInfo(zona))
    toca = activo and ahora.hour in horas_locales

    print(
        f"activo={activo} horas_locales={horas_locales} zona={zona} -> "
        f"ahora son las {ahora.hour}:00 en {zona} -> toca={toca}"
    )

    salida_github = os.environ.get("GITHUB_OUTPUT")
    if salida_github:
        with open(salida_github, "a") as f:
            f.write(f"toca={'true' if toca else 'false'}\n")


if __name__ == "__main__":
    main()
