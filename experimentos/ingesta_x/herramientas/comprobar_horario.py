#!/usr/bin/env python3
"""Comprueba si toca ejecutar la ingesta ahora mismo, según config.json (activo + hora_local +
zona_horaria). Pensado como paso de GitHub Actions: imprime el resultado y, si existe la
variable de entorno GITHUB_OUTPUT, deja ahí "toca=true"/"toca=false" para que el resto de pasos
del workflow decidan si ejecutarse.

El workflow se dispara cada hora (ver el cron); este script decide si ESTA hora es la
configurada -- así el horario se controla editando config.json, no tocando el cron del YAML.
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
    hora_local = int(config.get("hora_local", 3))
    zona = config.get("zona_horaria", "Europe/Madrid")

    ahora = datetime.now(ZoneInfo(zona))
    toca = activo and ahora.hour == hora_local

    print(
        f"activo={activo} hora_local={hora_local} zona={zona} -> "
        f"ahora son las {ahora.hour}:00 en {zona} -> toca={toca}"
    )

    salida_github = os.environ.get("GITHUB_OUTPUT")
    if salida_github:
        with open(salida_github, "a") as f:
            f.write(f"toca={'true' if toca else 'false'}\n")


if __name__ == "__main__":
    main()
