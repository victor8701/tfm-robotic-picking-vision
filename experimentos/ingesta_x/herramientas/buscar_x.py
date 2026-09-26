#!/usr/bin/env python3
"""Busca en X publicaciones reales que encajen con un estilo (y opcionalmente una ocasión), y
añade sus URLs a la cola de descarga -- para que procesar_cola.py las descargue/clasifique solo
después, sin tocar esto.

Cómo busca, en dos pasos (v2 -- ver por qué en el commit que introdujo este cambio):
1. **Tavily** (`https://tavily.com`, capa gratuita: 1000 créditos/mes, sin tarjeta) hace la
   búsqueda real en la web, acotada a x.com/twitter.com. Esto es lo que de verdad encuentra
   URLs -- cero coste, no pasa por Claude en absoluto.
2. **Claude Code en modo no interactivo** (`claude -p`, autenticado con CLAUDE_CODE_OAUTH_TOKEN,
   mismo mecanismo que ya usa viral_clips) recibe esos resultados YA encontrados por Tavily
   (título + URL + fragmento de texto de cada uno) y elige/filtra cuáles encajan de verdad --
   sin ninguna herramienta activada, tarea de puro texto, igual que el patrón que ya usa
   viral_clips en producción sin coste, dentro de la suscripción mensual.

Por qué no lo hace todo Claude con su propia búsqueda web (como en la v1 de este script):
probado en real, y la búsqueda web de Claude Code gasta saldo de crédito de pago de verdad
("Credit balance is too low" fue el error real que dio en producción) -- no está cubierta por
la suscripción como sí lo está una llamada de puro texto sin herramientas. Separar "buscar" de
"juzgar" en dos herramientas distintas mantiene todo esto en 0€ aparte de lo que ya se paga.

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
import shutil
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
# Pedimos de más para que Claude tenga margen real donde elegir/descartar -- Tavily permite
# hasta 20 por llamada.
FACTOR_CANDIDATAS = 3
MAX_CANDIDATAS_TAVILY = 20

CLAUDE_TIMEOUT_SECONDS = 300
MAX_INTENTOS = 3

SISTEMA_PROMPT = (
    "Eres un curador que revisa resultados de búsqueda YA ENCONTRADOS (título, URL y fragmento "
    "de texto de cada uno) para un proyecto universitario de clasificación de estilo de ropa "
    "(TFM de robótica), y elige cuáles apuntan de verdad a una foto o vídeo REAL de una persona "
    "vestida con el estilo pedido -- ropa claramente visible, contenido real (nunca dibujos, "
    "arte generado por IA, ni capturas de otra red social). Descarta contenido con personajes "
    "con copyright (cosplay, merchandising de franquicias), contenido sensible o fuera de tema "
    "aunque el texto mencione el estilo, y cualquier resultado que por el título/fragmento "
    "parezca ser solo un enlace, un meme de texto, una noticia, o un perfil/hashtag en vez de "
    "una publicación concreta. NO TIENES herramientas ni acceso a la web: solo puedes elegir "
    "entre las URLs que te paso en la lista, nunca inventar ni completar una URL que no esté "
    "ahí literal.\n\n"
    "FORMATO DE RESPUESTA OBLIGATORIO -- un programa parsea esto automáticamente, ningún humano "
    "lo lee. Responde ÚNICAMENTE con el objeto JSON con esta estructura exacta, nada de texto "
    "antes ni después, nada de bloques de código markdown:\n"
    '{"encontradas": [{"url": "(copiada tal cual de la lista)", '
    '"nota": "breve razón de por qué encaja"}]}\n'
    "Si ninguna de la lista encaja de verdad, devuelve la lista vacía -- es preferible devolver "
    "menos que forzar encaje."
)

RE_URL_TWEET = re.compile(
    r"^https?://(www\.)?(x\.com|twitter\.com)/[A-Za-z0-9_]+/status/(\d+)"
)


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


def _extraer_json(texto: str) -> str | None:
    texto = texto.strip()
    if texto.startswith("{"):
        return texto
    coincidencia = re.search(r"```(?:json)?\s*(\{.*\})\s*```", texto, re.DOTALL)
    if coincidencia:
        return coincidencia.group(1)
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        return texto[inicio : fin + 1]
    return None


def consultar_tavily(consulta: str, cantidad: int) -> list[dict]:
    """Busca de verdad en la web, acotado a x.com/twitter.com. Sin esto no hay forma de saber
    qué URLs existen realmente -- Claude, sin herramientas, no puede saberlo por sí solo."""
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


def ejecutar_claude(prompt_usuario: str) -> dict:
    ejecutable = shutil.which("claude")
    if ejecutable is None:
        raise ErrorBusqueda(
            "No se encontró el CLI 'claude' en el PATH (¿falta 'npm install -g "
            "@anthropic-ai/claude-code' en el workflow?)"
        )
    sistema_una_linea = " ".join(SISTEMA_PROMPT.split())
    # Sin --allowedTools: esta tarea es de puro texto (elegir entre candidatas ya dadas), no
    # necesita ninguna herramienta -- así se queda dentro de la suscripción, sin tocar saldo de
    # crédito de pago (confirmado en real: con la búsqueda web activada sí lo tocaba).
    args = [
        ejecutable, "-p", "--output-format", "json", "--model", "sonnet",
        "--setting-sources", "",
        "--no-session-persistence",
        "--system-prompt", sistema_una_linea,
    ]

    errores_intentos: list[str] = []
    for intento in range(MAX_INTENTOS):
        prompt_actual = prompt_usuario
        if intento > 0:
            prompt_actual += (
                "\n\nRECORDATORIO: tu respuesta anterior no fue JSON válido. Esta vez responde "
                "ÚNICAMENTE con el objeto JSON pedido, sin ningún otro texto."
            )
        try:
            resultado = subprocess.run(
                args, input=prompt_actual, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=CLAUDE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ErrorBusqueda(
                f"'claude -p' no respondió en {CLAUDE_TIMEOUT_SECONDS}s"
            ) from exc

        if resultado.returncode != 0:
            errores_intentos.append(
                f"intento {intento + 1}: código {resultado.returncode}: "
                f"{(resultado.stderr or resultado.stdout)[:400]}"
            )
            continue

        try:
            sobre = json.loads(resultado.stdout)
        except json.JSONDecodeError:
            errores_intentos.append(f"intento {intento + 1}: stdout no es JSON: {resultado.stdout[:400]}")
            continue

        if not isinstance(sobre, dict):
            errores_intentos.append(f"intento {intento + 1}: 'claude -p' no devolvió un objeto")
            continue

        if sobre.get("is_error"):
            errores_intentos.append(f"intento {intento + 1}: {str(sobre.get('result', ''))[:400]}")
            continue

        texto_resultado = sobre.get("result") or ""
        candidato = _extraer_json(texto_resultado)
        if candidato is None:
            errores_intentos.append(
                f"intento {intento + 1}: sin JSON en la respuesta: {texto_resultado[:400]}"
            )
            continue

        try:
            return json.loads(candidato)
        except json.JSONDecodeError:
            errores_intentos.append(f"intento {intento + 1}: JSON extraído inválido")
            continue

    raise ErrorBusqueda("No se pudo obtener una respuesta válida:\n" + "\n".join(errores_intentos))


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

        añadir_paso(solicitud, f"Tavily encontró {len(resultados_tavily)} resultado(s), pidiendo a Claude que filtre...")
        guardar_con_reintentos(
            lambda: _guardar_solo_solicitud(args.solicitud_id, solicitud),
            f"buscar_x: {args.solicitud_id} filtrando con Claude",
        )

        lista_candidatas = "\n\n".join(
            f"{i + 1}. URL: {r.get('url', '')}\n   Título: {r.get('title', '')}\n   Fragmento: {r.get('content', '')[:300]}"
            for i, r in enumerate(resultados_tavily)
        )
        prompt_usuario = (
            f"Busco publicaciones que encajen con: {solicitud['texto_busqueda']!r}. "
            f"Elige hasta {cantidad} de estos {len(resultados_tavily)} resultados ya encontrados "
            f"(los que de verdad encajen, no fuerces si no hay tantos):\n\n{lista_candidatas}"
        )
        respuesta = ejecutar_claude(prompt_usuario)
        candidatas = respuesta.get("encontradas") or []

        validas: list[str] = []
        descartadas = 0
        for item in candidatas:
            url = (item.get("url") or "").strip()
            if not RE_URL_TWEET.match(url):
                descartadas += 1
                continue
            if url in validas:
                descartadas += 1
                continue
            validas.append(url)

        solicitud["estado"] = "completado"
        resumen_base = f"Descartadas {descartadas} (repetidas o no eran una publicación válida)." if descartadas else ""

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
