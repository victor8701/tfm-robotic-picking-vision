#!/usr/bin/env python3
"""Busca en X publicaciones reales que encajen con un estilo (y opcionalmente una ocasión), y
añade sus URLs a la cola de descarga -- para que procesar_cola.py las descargue/clasifique solo
después, sin tocar esto.

Cómo busca: llama al propio CLI de Claude Code en modo no interactivo (`claude -p`) con la
herramienta de búsqueda web permitida. Es el mismo mecanismo que ya usa el otro proyecto de
Víctor (viral_clips) para llamar a Claude desde GitHub Actions sin salirse de su suscripción
mensual: autenticado con CLAUDE_CODE_OAUTH_TOKEN (generado una vez con 'claude setup-token'),
NO con ANTHROPIC_API_KEY (esa sí se cobra aparte, por eso no se usa). Confirmado con una prueba
real antes de construir esto: con --allowedTools WebSearch la búsqueda se ejecuta sola, sin
pedir permiso interactivo (permission_denials vacío en la respuesta).

Se ejecuta dentro de un job de GitHub Actions ya con el repo cloneado (mismo patrón que
procesar_cola.py), pero a diferencia de ese script, este SÍ commitea y pushea él mismo en dos
puntos (al empezar a buscar, y al terminar) -- así la solicitud pasa por "pendiente" ->
"buscando" -> "completado"/"error" de verdad mientras el job corre, en vez de que el panel se
quede sin saber nada hasta que el job entero termine.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[3]
RAIZ_INGESTA = Path(__file__).resolve().parents[1]
RUTA_COLA = RAIZ_INGESTA / "cola"
RUTA_SOLICITUDES = RAIZ_INGESTA / "panel" / "data" / "solicitudes_x.json"

CLAUDE_TIMEOUT_SECONDS = 600
MAX_INTENTOS = 3

SISTEMA_PROMPT = (
    "Eres un investigador que busca fotos o vídeos REALES publicados en X (Twitter) para un "
    "proyecto universitario de clasificación de estilo de ropa (TFM de robótica). Usa la "
    "herramienta de búsqueda web para encontrar publicaciones de X que muestren a gente vestida "
    "con el estilo pedido -- fotos o vídeos de cuerpo entero o medio cuerpo, con la ropa "
    "claramente visible, contenido real (nunca dibujos, arte generado por IA, ni capturas de "
    "otra red social). Evita contenido con personajes con copyright (cosplay, merchandising de "
    "franquicias), contenido sensible o fuera de tema aunque la ropa encaje, y publicaciones que "
    "sean solo un enlace, un meme de texto, o un vídeo sin ropa visible. Cada URL debe apuntar a "
    "una publicación CONCRETA (x.com/usuario/status/NUMERO o twitter.com/usuario/status/NUMERO), "
    "nunca a un perfil, un hashtag ni una búsqueda. No inventes ninguna URL: si no la has visto "
    "de verdad en un resultado de búsqueda, no la incluyas.\n\n"
    "FORMATO DE RESPUESTA OBLIGATORIO -- un programa parsea esto automáticamente, ningún humano "
    "lo lee. Responde ÚNICAMENTE con el objeto JSON con esta estructura exacta, nada de texto "
    "antes ni después, nada de bloques de código markdown:\n"
    '{"encontradas": [{"url": "https://x.com/usuario/status/1234567890123456789", '
    '"nota": "breve razón de por qué encaja"}]}\n'
    "Si no encuentras suficientes que encajen de verdad, devuelve solo las que sí encuentres -- "
    "es preferible devolver menos que inventar o forzar encaje."
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


def guardar_y_commitear(solicitudes: dict, mensaje: str) -> None:
    RUTA_SOLICITUDES.parent.mkdir(parents=True, exist_ok=True)
    RUTA_SOLICITUDES.write_text(
        json.dumps(solicitudes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git("config", "user.name", "github-actions[bot]")
    _git("config", "user.email", "github-actions[bot]@users.noreply.github.com")
    _git("add", str(RUTA_SOLICITUDES), str(RUTA_COLA))
    if _hay_cambios_staged():
        _git("commit", "-m", mensaje)
        _git("push")


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


def ejecutar_claude(prompt_usuario: str) -> dict:
    ejecutable = shutil.which("claude")
    if ejecutable is None:
        raise ErrorBusqueda(
            "No se encontró el CLI 'claude' en el PATH (¿falta 'npm install -g "
            "@anthropic-ai/claude-code' en el workflow?)"
        )
    sistema_una_linea = " ".join(SISTEMA_PROMPT.split())
    args = [
        ejecutable, "-p", "--output-format", "json", "--model", "sonnet",
        "--allowedTools", "WebSearch",
        "--permission-mode", "acceptEdits",
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
        guardar_y_commitear(solicitudes, f"buscar_x: {args.solicitud_id} cancelada antes de empezar")
        return 0

    solicitud["estado"] = "buscando"
    añadir_paso(solicitud, "Buscando en X con Claude...")
    guardar_y_commitear(solicitudes, f"buscar_x: {args.solicitud_id} empieza a buscar")

    try:
        cantidad = int(solicitud.get("cantidad", 8))
        prompt_usuario = (
            f"Busca {cantidad} publicaciones de X que encajen con: "
            f"{solicitud['texto_busqueda']!r}."
        )
        respuesta = ejecutar_claude(prompt_usuario)
        candidatas = respuesta.get("encontradas") or []

        ya_en_cola = urls_ya_en_cola(solicitud["estilo"])
        validas: list[str] = []
        descartadas = 0
        for item in candidatas:
            url = (item.get("url") or "").strip()
            if not RE_URL_TWEET.match(url):
                descartadas += 1
                continue
            if url in ya_en_cola or url in validas:
                descartadas += 1
                continue
            validas.append(url)

        if validas:
            añadir_a_cola(solicitud["estilo"], validas)

        solicitud["estado"] = "completado"
        solicitud["urls_encontradas"] = len(validas)
        resumen = f"Encontradas {len(validas)} URL(s) nuevas, añadidas a la cola de '{solicitud['estilo']}'."
        if descartadas:
            resumen += f" Descartadas {descartadas} (repetidas o no eran una publicación válida)."
        if len(candidatas) - len(validas) - descartadas > 0:
            resumen += " Aviso: alguna candidata no tenía URL."
        añadir_paso(solicitud, resumen)
        guardar_y_commitear(solicitudes, f"buscar_x: {args.solicitud_id} completado ({len(validas)} URLs)")
        print(resumen)
        return 0

    except Exception as exc:  # noqa: BLE001 -- se registra cualquier fallo, nunca se queda callado
        solicitudes = cargar_solicitudes()  # recargar por si acaso, aunque no debería haber cambiado
        solicitud = solicitudes.get(args.solicitud_id, solicitud)
        solicitud["estado"] = "error"
        añadir_paso(solicitud, f"Error: {exc}")
        solicitudes[args.solicitud_id] = solicitud
        guardar_y_commitear(solicitudes, f"buscar_x: {args.solicitud_id} fallo")
        print(f"Error en la solicitud {args.solicitud_id}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
