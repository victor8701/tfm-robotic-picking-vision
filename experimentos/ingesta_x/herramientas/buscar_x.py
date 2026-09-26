#!/usr/bin/env python3
"""Busca en X publicaciones reales que encajen con un estilo (y opcionalmente una ocasión), y
añade sus URLs a la cola de descarga -- para que procesar_cola.py las descargue/clasifique solo
después, sin tocar esto.

Cómo busca (v3): **solo Tavily** (`https://tavily.com`, capa gratuita: 1000 créditos/mes, sin
tarjeta) -- acotado a x.com/twitter.com, ordenado por su propia relevancia, con un filtro
mecánico de palabras a evitar (ver PALABRAS_PROHIBIDAS) como red de seguridad básica.

Por qué no pasa por Claude (v1 y v2 sí lo hacían): probado en real, DOS veces, con enfoques
distintos -- ni la búsqueda web de Claude Code ni siquiera una llamada de puro texto sin
ninguna herramienta consiguieron evitar "Credit balance is too low". Confirmado con el dueño de
la cuenta: solo tiene el plan Pro mensual, sin saldo de crédito de la API cargado -- es decir,
el modo no interactivo de Claude Code (`claude -p`) necesita saldo de pago real en esta cuenta
para CUALQUIER llamada, esté o no usando herramientas. No se puede evitar sin que se gaste
dinero de verdad, así que se quitó del todo: el filtro de calidad ahora es solo mecánico
(PALABRAS_PROHIBIDAS + orden por relevancia de Tavily), más flojo que el de un LLM pero
gratis de verdad. Lo que cuele de más se descarta a mano en la galería con el botón ✕.

Se ejecuta dentro de un job de GitHub Actions ya con el repo cloneado (mismo patrón que
procesar_cola.py), pero a diferencia de ese script, este SÍ commitea y pushea él mismo en varios
puntos -- así la solicitud pasa por "pendiente" -> "buscando" -> "completado"/"error" de verdad
mientras el job corre, en vez de que el panel se quede sin saber nada hasta que el job termine.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Callable
from pathlib import Path

import requests

RAIZ_REPO = Path(__file__).resolve().parents[3]
RAIZ_INGESTA = Path(__file__).resolve().parents[1]
RUTA_COLA = RAIZ_INGESTA / "cola"
RUTA_SOLICITUDES = RAIZ_INGESTA / "panel" / "data" / "solicitudes_x.json"

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_URL = "https://api.tavily.com/search"
TAVILY_TIMEOUT_SECONDS = 30
# Pedimos de más de lo que hace falta para poder descartar por PALABRAS_PROHIBIDAS y aun así
# llegar a `cantidad` -- Tavily permite hasta 20 por llamada.
FACTOR_CANDIDATAS = 3
MAX_CANDIDATAS_TAVILY = 20

RE_URL_TWEET = re.compile(
    r"^https?://(www\.)?(x\.com|twitter\.com)/[A-Za-z0-9_]+/status/(\d+)"
)

# Red de seguridad mecánica, no tan fina como un juicio humano/LLM -- pensada para descartar los
# tipos de ruido que más se han visto colarse en este proyecto (cosplay/personajes con copyright,
# noticias/deporte fuera de tema) a partir del título+fragmento que devuelve Tavily. Case-
# insensitive, coincidencia de subcadena simple.
PALABRAS_PROHIBIDAS = [
    "cosplay", "anime", "manga", "fanart", "fan art", "personaje de",
    "gol", "partido de fútbol", "resultado del partido", "liga de fútbol", "champions league",
    "elecciones", "atentado", "presidente de", "noticia de última hora",
]


class ErrorBusqueda(RuntimeError):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=RAIZ_REPO, check=True)


def _hay_cambios_staged() -> bool:
    resultado = subprocess.run(
        ["git", "diff", "--staged", "--quiet"], cwd=RAIZ_REPO
    )
    return resultado.returncode != 0


def cargar_solicitudes() -> dict:
    if not RUTA_SOLICITUDES.exists():
        return {}
    return json.loads(RUTA_SOLICITUDES.read_text(encoding="utf-8"))


MAX_INTENTOS_PUSH = 5


def guardar_con_reintentos(preparar: Callable[[], None], mensaje: str) -> None:
    """Llama a `preparar` (que debe escribir en disco lo que haga falta -- actualizar
    solicitudes_x.json y, si toca, añadir URLs a la cola) y lo commitea/pushea. Si el push
    falla, reintenta desde cero: reset duro al último estado remoto y se vuelve a llamar a
    `preparar` sobre esa versión fresca, antes de reintentar.

    Por qué hace falta: visto en real -- si se lanzan dos búsquedas casi a la vez, sus dos
    ejecuciones de GitHub Actions pueden intentar avanzar la rama al mismo tiempo; la segunda
    en llegar se quedaba con el push rechazado y, como el propio manejo de errores también
    intentaba pushear, se quedaba sin poder guardar ni su propio mensaje de error -- la
    solicitud se veía atascada en "pendiente" para siempre, sin ninguna pista. Reintentar sobre
    el estado fresco evita que una ejecución pise el progreso de la otra."""
    _git("config", "user.name", "github-actions[bot]")
    _git("config", "user.email", "github-actions[bot]@users.noreply.github.com")

    for intento in range(MAX_INTENTOS_PUSH):
        preparar()
        # RUTA_COLA puede no existir todavía en un checkout nuevo -- 'git add' de una ruta
        # inexistente falla y tira abajo todo el script, así que solo se añade si está.
        rutas = [str(RUTA_SOLICITUDES)]
        if RUTA_COLA.exists():
            rutas.append(str(RUTA_COLA))
        _git("add", *rutas)
        if not _hay_cambios_staged():
            return
        _git("commit", "-m", mensaje)

        resultado_push = subprocess.run(["git", "push"], cwd=RAIZ_REPO)
        if resultado_push.returncode == 0:
            return
        if intento == MAX_INTENTOS_PUSH - 1:
            raise ErrorBusqueda(
                f"No se pudo hacer push tras {MAX_INTENTOS_PUSH} intentos (probablemente otra "
                "búsqueda se lanzó casi a la vez y ganó la carrera cada vez)"
            )
        _git("fetch", "origin")
        _git("reset", "--hard", "@{u}")


def añadir_paso(solicitud: dict, texto: str) -> None:
    solicitud.setdefault("pasos", []).append({"ts": _ahora(), "texto": texto})


def consultar_tavily(consulta: str, cantidad: int) -> list[dict]:
    """Busca de verdad en la web, acotado a x.com/twitter.com y ordenado por la relevancia que
    calcula la propia Tavily (campo "score" de cada resultado)."""
    if not TAVILY_API_KEY:
        raise ErrorBusqueda(
            "Falta el secreto TAVILY_API_KEY en este repo (Settings -> Secrets -> Actions). "
            "Se genera gratis, sin tarjeta, en tavily.com."
        )
    max_resultados = min(MAX_CANDIDATAS_TAVILY, max(cantidad * FACTOR_CANDIDATAS, cantidad))
    try:
        r = requests.post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {TAVILY_API_KEY}"},
            json={
                "query": consulta,
                "include_domains": ["x.com", "twitter.com"],
                "max_results": max_resultados,
                "search_depth": "basic",
            },
            timeout=TAVILY_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise ErrorBusqueda(f"Error de red hacia Tavily: {exc}") from exc

    if r.status_code != 200:
        raise ErrorBusqueda(f"Tavily respondió {r.status_code}: {r.text[:300]}")

    return r.json().get("results") or []


def parece_indeseable(resultado: dict) -> bool:
    texto = f"{resultado.get('title', '')} {resultado.get('content', '')}".lower()
    return any(palabra in texto for palabra in PALABRAS_PROHIBIDAS)


def urls_ya_en_cola(estilo: str) -> set[str]:
    ruta = RUTA_COLA / f"{estilo}.txt"
    if not ruta.exists():
        return set()
    return {
        linea.strip() for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    }


def añadir_a_cola(estilo: str, urls_nuevas: list[str]) -> None:
    ruta = RUTA_COLA / f"{estilo}.txt"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    contenido_previo = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    separador = "" if (not contenido_previo or contenido_previo.endswith("\n")) else "\n"
    with ruta.open("a", encoding="utf-8") as f:
        if separador:
            f.write(separador)
        for url in urls_nuevas:
            f.write(url + "\n")


def _escribir_solicitudes_json(datos: dict) -> None:
    RUTA_SOLICITUDES.parent.mkdir(parents=True, exist_ok=True)
    RUTA_SOLICITUDES.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _guardar_solo_solicitud(id_solicitud: str, solicitud: dict) -> None:
    """Se llama de nuevo en cada reintento -- por eso vuelve a leer el fichero fresco cada vez
    en vez de reusar un `solicitudes` cargado una sola vez al principio."""
    datos = cargar_solicitudes()
    datos[id_solicitud] = solicitud
    _escribir_solicitudes_json(datos)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solicitud-id", required=True)
    args = parser.parse_args()

    solicitudes = cargar_solicitudes()
    solicitud = solicitudes.get(args.solicitud_id)
    if solicitud is None:
        print(f"No existe la solicitud {args.solicitud_id!r} en {RUTA_SOLICITUDES}", file=sys.stderr)
        return 1

    if solicitud.get("estado") == "cancelada":
        añadir_paso(solicitud, "Cancelada antes de empezar a buscar, no se hace nada.")
        guardar_con_reintentos(
            lambda: _guardar_solo_solicitud(args.solicitud_id, solicitud),
            f"buscar_x: {args.solicitud_id} cancelada antes de empezar",
        )
        return 0

    try:
        solicitud["estado"] = "buscando"
        añadir_paso(solicitud, "Buscando en la web con Tavily...")
        guardar_con_reintentos(
            lambda: _guardar_solo_solicitud(args.solicitud_id, solicitud),
            f"buscar_x: {args.solicitud_id} empieza a buscar",
        )

        cantidad = int(solicitud.get("cantidad", 8))
        resultados_tavily = consultar_tavily(solicitud["texto_busqueda"], cantidad)

        if not resultados_tavily:
            solicitud["estado"] = "completado"
            solicitud["urls_encontradas"] = 0
            añadir_paso(solicitud, "Tavily no encontró ningún resultado en x.com/twitter.com para este texto.")
            guardar_con_reintentos(
                lambda: _guardar_solo_solicitud(args.solicitud_id, solicitud),
                f"buscar_x: {args.solicitud_id} completado (0 resultados)",
            )
            print("Sin resultados de Tavily.")
            return 0

        añadir_paso(solicitud, f"Tavily encontró {len(resultados_tavily)} resultado(s), aplicando filtro...")
        guardar_con_reintentos(
            lambda: _guardar_solo_solicitud(args.solicitud_id, solicitud),
            f"buscar_x: {args.solicitud_id} filtrando",
        )

        # Sin Claude (ver docstring del módulo): filtro puramente mecánico -- URL con forma de
        # publicación real, sin palabras de la lista negra, ordenado por la relevancia que ya
        # calcula Tavily, y nos quedamos con las primeras `cantidad`.
        ordenados = sorted(resultados_tavily, key=lambda r: r.get("score", 0), reverse=True)
        validas: list[str] = []
        descartadas = 0
        for r in ordenados:
            if len(validas) >= cantidad:
                break
            url = (r.get("url") or "").strip()
            if not RE_URL_TWEET.match(url) or url in validas or parece_indeseable(r):
                descartadas += 1
                continue
            validas.append(url)

        solicitud["estado"] = "completado"
        resumen_base = f"Descartadas {descartadas} (repetidas, no válidas, o coincidían con la lista de palabras a evitar)." if descartadas else ""

        def _guardar_final() -> None:
            # Se recalcula qué es "ya en cola" en cada intento -- puede haber cambiado si otra
            # ejecución concurrente (misma estilo) escribió primero en este reintento.
            ya_en_cola = urls_ya_en_cola(solicitud["estilo"])
            nuevas = [u for u in validas if u not in ya_en_cola]
            if nuevas:
                añadir_a_cola(solicitud["estilo"], nuevas)
            solicitud["urls_encontradas"] = len(nuevas)
            resumen = f"Encontradas {len(nuevas)} URL(s) nuevas, añadidas a la cola de '{solicitud['estilo']}'. {resumen_base}".strip()
            # Si esta es la segunda vez que se llama (reintento tras un push rechazado),
            # sustituye el resumen ya añadido en vez de duplicarlo.
            if solicitud["pasos"] and solicitud["pasos"][-1]["texto"].startswith("Encontradas "):
                solicitud["pasos"][-1] = {"ts": _ahora(), "texto": resumen}
            else:
                añadir_paso(solicitud, resumen)
            _guardar_solo_solicitud(args.solicitud_id, solicitud)

        guardar_con_reintentos(_guardar_final, f"buscar_x: {args.solicitud_id} completado")
        print(f"Completado: {len(validas)} URL(s) válidas encontradas.")
        return 0

    except Exception as exc:  # noqa: BLE001 -- se registra cualquier fallo, nunca se queda callado
        solicitud["estado"] = "error"
        añadir_paso(solicitud, f"Error: {exc}")
        guardar_con_reintentos(
            lambda: _guardar_solo_solicitud(args.solicitud_id, solicitud),
            f"buscar_x: {args.solicitud_id} fallo",
        )
        print(f"Error en la solicitud {args.solicitud_id}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
