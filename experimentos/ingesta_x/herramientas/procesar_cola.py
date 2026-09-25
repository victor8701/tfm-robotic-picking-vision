#!/usr/bin/env python3
"""Procesa la cola de URLs de X pendientes, una carpeta por estilo, sin necesitar ninguna
sesión de Claude activa -- pensado para correr desde GitHub Actions (o a mano igual de bien).

Estructura que espera/mantiene, relativa a este archivo (../):
  cola/<estilo>.txt     -- URLs pendientes de ese estilo, una por línea (# o vacía = ignorada)
  cola/procesadas.txt   -- log de "estilo | url | resultado", se va añadiendo, nunca se borra
  data/<estilo>/         -- fotos + metadata descargadas, mismo formato que descargar_x.py

No busca URLs nuevas por sí solo (eso seguía necesitando una IA con acceso a búsqueda web real,
que no es gratis fuera de una sesión de Claude) -- solo procesa lo que ya haya en cola/. Alguien
(Claude en una sesión activa, o el autor a mano) añade líneas a esos ficheros; esta pieza se
limita a descargar y comitear, y esa parte sí corre sola, en un horario o cuando se dispare a
mano desde GitHub -- no depende de que haya nadie mirando.

Uso:
    python procesar_cola.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from descargar_x import procesar_url  # noqa: E402

RAIZ = Path(__file__).parent.parent
DIR_COLA = RAIZ / "cola"
DIR_DATA = RAIZ / "data"
LOG_PROCESADAS = DIR_COLA / "procesadas.txt"

ESTILOS = [
    "old_money", "lujo_ostentoso", "clasico_tradicional", "urbano",
    "bohemio", "alternativo_geek", "convencional",
]


def leer_pendientes(ruta: Path) -> list[str]:
    if not ruta.exists():
        return []
    urls = []
    for linea in ruta.read_text().splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#"):
            urls.append(linea)
    return urls


def reescribir_pendientes(ruta: Path, restantes: list[str]) -> None:
    cabecera = (
        "# Una URL de X (x.com/usuario/status/ID) por linea.\n"
        "# Las lineas vacias o que empiezan por # se ignoran.\n"
        "# La Action mueve cada URL procesada a procesadas.txt automaticamente.\n"
    )
    ruta.write_text(cabecera + "\n".join(restantes) + ("\n" if restantes else ""))


def registrar_procesada(estilo: str, url: str, resultado: str) -> None:
    with LOG_PROCESADAS.open("a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} | {estilo} | {url} | {resultado}\n")


def main() -> None:
    tmp_dir = DIR_DATA / "_tmp_video"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    total_ok = 0
    total_fallo = 0

    for estilo in ESTILOS:
        ruta_cola = DIR_COLA / f"{estilo}.txt"
        pendientes = leer_pendientes(ruta_cola)
        if not pendientes:
            continue

        out_dir = DIR_DATA / estilo
        restantes = []
        for url in pendientes:
            try:
                meta = procesar_url(url, out_dir, tmp_dir, intervalo_seg=3.0)
                print(f"OK    [{estilo}] {url} -> {meta['n_imagenes']} {meta['tipo_contenido']}(s)")
                registrar_procesada(estilo, url, f"ok:{meta['n_imagenes']}_{meta['tipo_contenido']}")
                total_ok += 1
            except RuntimeError as e:
                # Fallo permanente (post sin media nativa, o inaccesible) -- reintentar no
                # arregla nada, así que sale de la cola pero queda registrado en el log.
                print(f"FALLO [{estilo}] {url}: {e} (permanente, sale de la cola)", file=sys.stderr)
                registrar_procesada(estilo, url, f"fallo_permanente:{e}")
                total_fallo += 1
            except Exception as e:
                # Fallo posiblemente transitorio (red, rate-limit...) -- se queda en cola para
                # reintentarlo en la próxima ejecución.
                print(f"FALLO [{estilo}] {url}: {e} (se reintenta la próxima vez)", file=sys.stderr)
                registrar_procesada(estilo, url, f"fallo_temporal:{e}")
                total_fallo += 1
                restantes.append(url)

        reescribir_pendientes(ruta_cola, restantes)

    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\nResumen: {total_ok} descargadas, {total_fallo} fallidas (quedan en cola)")


if __name__ == "__main__":
    main()
