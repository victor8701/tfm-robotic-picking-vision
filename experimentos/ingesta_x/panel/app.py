#!/usr/bin/env python3
"""Panel web mínimo para controlar la ingesta de X sin pasar por GitHub a mano: ver la cola
pendiente, disparar la Action ya mismo, y cambiar activo/hora/zona de config.json.

Pensado para desplegarse en Render (u otro hosting con Python) -- el hosting en sí solo sirve
para tener una URL con la que interactuar; la ejecución programada (el cron diario/horario) ya
corre sola dentro de GitHub Actions sin que este panel tenga que estar despierto. Este panel es
comodidad de interfaz, no la pieza que hace que la ingesta sea autónoma -- esa ya lo era antes.

Variables de entorno necesarias (se configuran en Render, nunca en el código):
  GITHUB_TOKEN     -- token de acceso personal con permiso "repo" + "workflow"
  PANEL_PASSWORD   -- contraseña para entrar al panel (es una URL pública, sin esto la vería
                      cualquiera que la encontrara, y el token de arriba puede escribir en tu repo)
  GITHUB_REPO      -- "usuario/repo", por defecto victor8701/tfm-robotic-picking-vision
  GITHUB_BRANCH    -- por defecto ingesta-viral-clips
"""
from __future__ import annotations

import base64
import os
from functools import wraps

import requests
from flask import Flask, redirect, render_template_string, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "")
REPO = os.environ.get("GITHUB_REPO", "victor8701/tfm-robotic-picking-vision")
BRANCH = os.environ.get("GITHUB_BRANCH", "ingesta-viral-clips")
WORKFLOW_FILE = "ingesta_x.yml"
RUTA_CONFIG = "experimentos/ingesta_x/config.json"
ESTILOS = [
    "old_money", "lujo_ostentoso", "clasico_tradicional", "urbano",
    "bohemio", "alternativo_geek", "convencional",
]

API = "https://api.github.com"
CABECERAS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def requiere_login(f):
    @wraps(f)
    def envoltura(*args, **kwargs):
        if PANEL_PASSWORD and not session.get("autenticado"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return envoltura


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("clave") == PANEL_PASSWORD:
            session["autenticado"] = True
            return redirect(url_for("panel"), code=303)
        error = "Contraseña incorrecta"
    return render_template_string(PLANTILLA_LOGIN, error=error)


def leer_contenido_repo(ruta: str) -> tuple[str, str] | None:
    """Devuelve (contenido_texto, sha) de un fichero del repo, o None si falla."""
    r = requests.get(
        f"{API}/repos/{REPO}/contents/{ruta}",
        headers=CABECERAS, params={"ref": BRANCH}, timeout=15,
    )
    if r.status_code != 200:
        return None
    data = r.json()
    contenido = base64.b64decode(data["content"]).decode("utf-8")
    return contenido, data["sha"]


def contar_pendientes(estilo: str) -> int:
    resultado = leer_contenido_repo(f"experimentos/ingesta_x/cola/{estilo}.txt")
    if not resultado:
        return 0
    contenido, _ = resultado
    return sum(1 for linea in contenido.splitlines() if linea.strip() and not linea.strip().startswith("#"))


@app.route("/", methods=["GET", "POST"])
@requiere_login
def panel():
    import json

    config = {"activo": True, "hora_local": 3, "zona_horaria": "Europe/Madrid"}
    config_sha = None
    resultado = leer_contenido_repo(RUTA_CONFIG)
    if resultado:
        contenido, config_sha = resultado
        try:
            config.update(json.loads(contenido))
        except ValueError:
            pass

    pendientes = {estilo: contar_pendientes(estilo) for estilo in ESTILOS}

    ejecuciones = []
    r = requests.get(
        f"{API}/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/runs",
        headers=CABECERAS, params={"branch": BRANCH, "per_page": 6}, timeout=15,
    )
    if r.status_code == 200:
        for run in r.json().get("workflow_runs", []):
            ejecuciones.append({
                "estado": run["status"],
                "conclusion": run.get("conclusion"),
                "disparo": run["event"],
                "creado": run["created_at"],
                "url": run["html_url"],
            })

    return render_template_string(
        PLANTILLA_PANEL,
        config=config,
        config_sha=config_sha,
        pendientes=pendientes,
        total_pendientes=sum(pendientes.values()),
        ejecuciones=ejecuciones,
        repo=REPO,
    )


@app.route("/ejecutar", methods=["POST"])
@requiere_login
def ejecutar():
    requests.post(
        f"{API}/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches",
        headers=CABECERAS, json={"ref": BRANCH}, timeout=15,
    )
    return redirect(url_for("panel"), code=303)


@app.route("/guardar-config", methods=["POST"])
@requiere_login
def guardar_config():
    import json

    resultado = leer_contenido_repo(RUTA_CONFIG)
    sha_actual = resultado[1] if resultado else None

    nuevo_config = {
        "activo": request.form.get("activo") == "on",
        "hora_local": int(request.form.get("hora_local", 3)),
        "zona_horaria": request.form.get("zona_horaria", "Europe/Madrid").strip(),
    }
    contenido_b64 = base64.b64encode(
        (json.dumps(nuevo_config, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    ).decode("ascii")

    payload = {
        "message": "panel: actualiza config.json",
        "content": contenido_b64,
        "branch": BRANCH,
    }
    if sha_actual:
        payload["sha"] = sha_actual

    requests.put(
        f"{API}/repos/{REPO}/contents/{RUTA_CONFIG}",
        headers=CABECERAS, json=payload, timeout=15,
    )
    return redirect(url_for("panel"), code=303)


PLANTILLA_LOGIN = """
<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ingesta X</title>
<style>
  body { font-family: system-ui, sans-serif; background: #f6f3ee; color: #211d18;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
  form { background: #fff; padding: 24px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,.08); width: 90%; max-width: 320px; }
  input { width: 100%; padding: 10px; margin-top: 8px; border-radius: 8px; border: 1px solid #ddd; box-sizing: border-box; }
  button { width: 100%; margin-top: 14px; padding: 11px; border: none; border-radius: 8px; background: #2f4a6b; color: #fff; font-weight: 700; }
  .error { color: #a8433a; font-size: 0.85rem; margin-top: 8px; }
</style></head><body>
<form method="post">
  <strong>Panel de ingesta X</strong>
  <input type="password" name="clave" placeholder="Contraseña" autofocus>
  <button type="submit">Entrar</button>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
</form>
</body></html>
"""

PLANTILLA_PANEL = """
<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ingesta X</title>
<style>
  body { font-family: system-ui, sans-serif; background: #f6f3ee; color: #211d18; margin: 0; padding: 16px; padding-bottom: 48px; }
  .envoltura { max-width: 480px; margin: 0 auto; }
  h1 { font-size: 1.2rem; }
  .tarjeta { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
  .btn { display: inline-block; width: 100%; box-sizing: border-box; padding: 13px; border: none; border-radius: 9px;
         background: #2f4a6b; color: #fff; font-weight: 700; font-size: 1rem; text-align: center; cursor: pointer; }
  .fila { display: flex; justify-content: space-between; padding: 5px 0; font-size: 0.9rem; border-bottom: 1px solid #eee; }
  .fila:last-child { border-bottom: none; }
  label { display: block; font-size: 0.72rem; text-transform: uppercase; color: #746c60; margin-top: 10px; }
  input[type=number], input[type=text] { width: 100%; padding: 8px; border-radius: 8px; border: 1px solid #ddd; box-sizing: border-box; }
  .toggle-row { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
  .estado { font-size: 0.7rem; padding: 2px 8px; border-radius: 20px; background: #efeae1; }
  .total { font-weight: 700; }
  a { color: #2f4a6b; }
</style></head><body>
<div class="envoltura">
  <h1>🧵 Ingesta X por estilo</h1>

  <div class="tarjeta">
    <form method="post" action="{{ url_for('ejecutar') }}">
      <button class="btn" type="submit">▶ Ejecutar ahora</button>
    </form>
    <p style="font-size:0.75rem;color:#746c60;margin-bottom:0;">
      Se salta la comprobación de hora, corre al momento.
    </p>
  </div>

  <div class="tarjeta">
    <strong>Cola pendiente</strong> (<span class="total">{{ total_pendientes }}</span> en total)
    {% for estilo, n in pendientes.items() %}
    <div class="fila"><span>{{ estilo }}</span><span>{{ n }}</span></div>
    {% endfor %}
  </div>

  <div class="tarjeta">
    <strong>Horario automático</strong>
    <form method="post" action="{{ url_for('guardar_config') }}">
      <div class="toggle-row">
        <input type="checkbox" name="activo" id="activo" {{ 'checked' if config.activo }}>
        <label for="activo" style="margin:0;text-transform:none;font-size:0.9rem;">Activo</label>
      </div>
      <label for="hora_local">Hora local</label>
      <input type="number" min="0" max="23" name="hora_local" id="hora_local" value="{{ config.hora_local }}">
      <label for="zona_horaria">Zona horaria</label>
      <input type="text" name="zona_horaria" id="zona_horaria" value="{{ config.zona_horaria }}">
      <button class="btn" type="submit" style="margin-top:14px;background:#4f7a56;">Guardar</button>
    </form>
  </div>

  <div class="tarjeta">
    <strong>Últimas ejecuciones</strong>
    {% for e in ejecuciones %}
    <div class="fila">
      <span><a href="{{ e.url }}" target="_blank">{{ e.creado[:16] }}</a> · {{ e.disparo }}</span>
      <span class="estado">{{ e.conclusion or e.estado }}</span>
    </div>
    {% else %}
    <p style="font-size:0.85rem;color:#746c60;">Sin ejecuciones todavía.</p>
    {% endfor %}
  </div>

  <p style="font-size:0.72rem;color:#746c60;text-align:center;">
    Repo: <a href="https://github.com/{{ repo }}" target="_blank">{{ repo }}</a>
  </p>
</div>
</body></html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
