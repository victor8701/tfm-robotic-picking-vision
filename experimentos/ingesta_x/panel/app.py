#!/usr/bin/env python3
"""Una sola app: galería de fotos por estilo (clasificar, subir, eliminar/restaurar) + panel de
control de la ingesta automática de X. Todo con su propia URL en Render, con el repo de GitHub
como base de datos (Render no tiene disco persistente gratis de verdad) -- mismo patrón que ya
usaba este panel para config.json, extendido a las fotos y sus clasificaciones.

Por qué el repo y no una base de datos de verdad: por la misma razón que todo lo demás de este
proyecto -- sin gastar dinero aparte de lo que ya se paga, usando lo que ya hay. Un efecto
secundario honesto: cada tap genera un commit real en el repo (se explica en el README del panel).

Variables de entorno (se configuran en Render, nunca en el código):
  GITHUB_TOKEN, PANEL_PASSWORD, GITHUB_REPO, GITHUB_BRANCH, FLASK_SECRET_KEY -- igual que antes.
"""
from __future__ import annotations

import base64
import json
import os
import time
from datetime import datetime, timezone
from functools import wraps

import requests
from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "")
REPO = os.environ.get("GITHUB_REPO", "victor8701/tfm-robotic-picking-vision")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
WORKFLOW_FILE = "ingesta_x.yml"
WORKFLOW_BUSQUEDA = "buscar_x.yml"

RUTA_BASE = "experimentos/ingesta_x/panel"
RUTA_CONFIG = "experimentos/ingesta_x/config.json"
RUTA_DATOS = f"{RUTA_BASE}/data/clasificaciones.json"
RUTA_FOTOS = f"{RUTA_BASE}/static/fotos"
RUTA_SOLICITUDES = f"{RUTA_BASE}/data/solicitudes_x.json"


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

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
    "lujo_ostentoso": "logomania luxury streetwear outfit real photos",
    "clasico_tradicional": "cayetana style outfit spain classic preppy",
    "urbano": "moda trap español streetwear outfit real",
    "bohemio": "bohemian boho chic outfit real photos",
    "alternativo_geek": "geek gamer streetwear outfit real photos",
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

API = "https://api.github.com"
CABECERAS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Cache en memoria de data/clasificaciones.json -- 1 solo worker de gunicorn (ver Procfile /
# comando de arranque), si no cada worker tendría su propia copia y se desincronizarían.
_CACHE = {"datos": None, "sha": None}


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
            return redirect(url_for("galeria"), code=303)
        error = "Contraseña incorrecta"
    return render_template_string(PLANTILLA_LOGIN, error=error)


# --- Ayudantes de GitHub (Contents API) ---

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


def escribir_repo(ruta: str, contenido_bytes: bytes, mensaje: str, sha_actual: str | None) -> bool:
    payload = {
        "message": mensaje,
        "content": base64.b64encode(contenido_bytes).decode("ascii"),
        "branch": BRANCH,
    }
    if sha_actual:
        payload["sha"] = sha_actual
    r = requests.put(
        f"{API}/repos/{REPO}/contents/{ruta}",
        headers=CABECERAS, json=payload, timeout=20,
    )
    return r.status_code in (200, 201)


def obtener_sha_actual(ruta: str) -> str | None:
    r = requests.get(
        f"{API}/repos/{REPO}/contents/{ruta}",
        headers=CABECERAS, params={"ref": BRANCH}, timeout=15,
    )
    return r.json().get("sha") if r.status_code == 200 else None


# --- Datos de clasificación (cache + escritura al repo) ---

def cargar_datos() -> dict:
    if _CACHE["datos"] is None:
        resultado = leer_contenido_repo(RUTA_DATOS)
        if resultado:
            contenido, sha = resultado
            _CACHE["datos"] = json.loads(contenido)
            _CACHE["sha"] = sha
        else:
            _CACHE["datos"] = {}
            _CACHE["sha"] = None
    return _CACHE["datos"]


def guardar_datos(mensaje: str) -> bool:
    contenido = json.dumps(_CACHE["datos"], ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    ok = escribir_repo(RUTA_DATOS, contenido, mensaje, _CACHE["sha"])
    if ok:
        _CACHE["sha"] = obtener_sha_actual(RUTA_DATOS)
    return ok


def categoria_actual(item: dict) -> str:
    return item.get("categoria_final") or item.get("categoria_ia")


def ocasion_actual(item: dict) -> str:
    return item.get("ocasion_final") or "ninguna"


# --- Galería: ver, clasificar, ocasión, eliminar, subir ---

@app.route("/")
@requiere_login
def galeria():
    datos = cargar_datos()
    filtro_origen = request.args.get("origen", "todas")
    filtro_revision = request.args.get("revision", "todas")

    def pasa_filtros(item):
        if filtro_origen == "autor" and item["origen"] != "autor":
            return False
        if filtro_origen == "claude" and item["origen"] != "claude":
            return False
        if filtro_revision == "revisadas" and not item.get("revisada"):
            return False
        if filtro_revision == "sin_revisar" and item.get("revisada"):
            return False
        return True

    grupos = {}
    for clave, _ in CATEGORIAS:
        grupos[clave] = [
            {"id": iid, **item} for iid, item in datos.items()
            if not item["eliminada"] and categoria_actual(item) == clave
            and item.get("imagen") and pasa_filtros(item)
        ]
    sin_estilo = [
        {"id": iid, **item} for iid, item in datos.items()
        if not item["eliminada"] and categoria_actual(item) == "ninguna"
        and item.get("imagen") and pasa_filtros(item)
    ]
    eliminadas_vista = [
        {"id": iid, **item} for iid, item in datos.items()
        if item["eliminada"] and item.get("imagen") and pasa_filtros(item)
    ]
    sin_imagen = [
        {"id": iid, **item} for iid, item in datos.items() if not item.get("imagen")
    ]

    total = len(datos)
    revisadas = sum(1 for item in datos.values() if item.get("revisada"))
    return render_template_string(
        PLANTILLA_GALERIA,
        categorias=CATEGORIAS, grupos=grupos, sin_estilo=sin_estilo,
        eliminadas=eliminadas_vista, ocasiones=OCASIONES, nombre_ocasion=NOMBRE_OCASION,
        estilos_chip=ESTILOS_CHIP, nombre_categoria=NOMBRE_CATEGORIA,
        total=total, sin_imagen=sin_imagen, revisadas=revisadas,
        filtro_origen=filtro_origen, filtro_revision=filtro_revision,
    )


@app.route("/clasificar/<iid>", methods=["POST"])
@requiere_login
def clasificar(iid):
    datos = cargar_datos()
    if iid not in datos:
        return jsonify({"ok": False, "error": "no existe"}), 404
    valor = request.json.get("categoria")
    datos[iid]["categoria_final"] = valor
    datos[iid]["revisada"] = True
    ok = guardar_datos(f"panel: clasifica {iid} -> {valor}")
    return jsonify({"ok": ok})


@app.route("/ocasion/<iid>", methods=["POST"])
@requiere_login
def ocasion(iid):
    datos = cargar_datos()
    if iid not in datos:
        return jsonify({"ok": False, "error": "no existe"}), 404
    valor = request.json.get("ocasion")
    datos[iid]["ocasion_final"] = None if valor == "ninguna" else valor
    ok = guardar_datos(f"panel: ocasion {iid} -> {valor}")
    return jsonify({"ok": ok})


@app.route("/eliminar/<iid>", methods=["POST"])
@requiere_login
def eliminar(iid):
    datos = cargar_datos()
    if iid not in datos:
        return jsonify({"ok": False, "error": "no existe"}), 404
    datos[iid]["eliminada"] = not datos[iid]["eliminada"]
    ok = guardar_datos(f"panel: {'elimina' if datos[iid]['eliminada'] else 'restaura'} {iid}")
    return jsonify({"ok": ok, "eliminada": datos[iid]["eliminada"]})


@app.route("/subir", methods=["POST"])
@requiere_login
def subir():
    categoria = request.form.get("categoria")
    archivos = request.files.getlist("fotos")
    datos = cargar_datos()
    subidas = 0
    for f in archivos:
        if not f or not f.filename:
            continue
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else "jpg"
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"
        nuevo_id = f"u_{int(time.time() * 1000)}_{subidas}"
        contenido = f.read()
        nombre_archivo = f"{nuevo_id}.{ext}"
        if not escribir_repo(f"{RUTA_FOTOS}/{nombre_archivo}", contenido, f"panel: sube foto {nuevo_id}", None):
            continue
        datos[nuevo_id] = {
            "categoria_final": categoria, "categoria_ia": categoria, "revisada": True,
            "ocasion_final": None, "eliminada": False, "origen": "autor",
            "fuente": "Añadida por ti", "fuente_url": "", "imagen": nombre_archivo,
        }
        subidas += 1
    if subidas:
        guardar_datos(f"panel: sube {subidas} foto(s) a {categoria}")
    return redirect(url_for("galeria"), code=303)


# --- Buscar en X: encola una solicitud y dispara el workflow "Buscar en X" ---
#
# A diferencia de clasificaciones.json (que solo escribe este panel), solicitudes_x.json lo
# escriben DOS cosas a la vez: este panel (al crear/cancelar una solicitud) y el propio workflow
# de GitHub Actions (al pasar de "buscando" a "completado"/"error", con git commit directo, no
# con esta API). Por eso, a diferencia de cargar_datos()/guardar_datos(), aquí NO se usa una
# caché en memoria entre peticiones -- se lee fresco de GitHub en cada carga de página, para que
# el progreso que va escribiendo la Action se vea según avanza y no una foto vieja cacheada.

def cargar_solicitudes() -> tuple[dict, str | None]:
    resultado = leer_contenido_repo(RUTA_SOLICITUDES)
    if resultado:
        contenido, sha = resultado
        return json.loads(contenido), sha
    return {}, None


@app.route("/buscar-x", methods=["GET"])
@requiere_login
def buscar_x():
    solicitudes, _ = cargar_solicitudes()
    lista = sorted(
        ({"id": sid, **s} for sid, s in solicitudes.items()),
        key=lambda s: s.get("creado_en", ""), reverse=True,
    )
    return render_template_string(
        PLANTILLA_BUSCAR_X, categorias=CATEGORIAS, ocasiones=OCASIONES,
        nombre_categoria=NOMBRE_CATEGORIA, nombre_ocasion=NOMBRE_OCASION,
        texto_predeterminado=TEXTO_PREDETERMINADO_ESTILO, calificador_ocasion=CALIFICADOR_OCASION,
        solicitudes=lista,
    )


@app.route("/buscar-x", methods=["POST"])
@requiere_login
def enviar_busqueda_x():
    estilo = request.form.get("estilo")
    ocasion = request.form.get("ocasion", "ninguna")
    modo = request.form.get("modo", "automatico")
    texto_personalizado = request.form.get("texto_personalizado", "")
    try:
        cantidad = max(3, min(15, int(request.form.get("cantidad", 8))))
    except ValueError:
        cantidad = 8

    texto_busqueda = calcular_texto_busqueda(estilo, ocasion, modo, texto_personalizado)
    if not estilo or estilo not in NOMBRE_CATEGORIA or not texto_busqueda:
        return redirect(url_for("buscar_x"), code=303)

    nuevo_id = f"sol_{int(time.time() * 1000)}"
    solicitudes, sha = cargar_solicitudes()
    solicitudes[nuevo_id] = {
        "estilo": estilo, "ocasion": ocasion, "modo": modo,
        "texto_busqueda": texto_busqueda, "cantidad": cantidad,
        "estado": "pendiente",
        "pasos": [{"ts": ahora_iso(), "texto": "Solicitud creada, esperando a que GitHub Actions la recoja."}],
        "creado_en": ahora_iso(),
    }
    contenido = json.dumps(solicitudes, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    if escribir_repo(RUTA_SOLICITUDES, contenido, f"panel: nueva busqueda X {nuevo_id} ({estilo})", sha):
        requests.post(
            f"{API}/repos/{REPO}/actions/workflows/{WORKFLOW_BUSQUEDA}/dispatches",
            headers=CABECERAS, json={"ref": BRANCH, "inputs": {"solicitud_id": nuevo_id}}, timeout=15,
        )
    return redirect(url_for("buscar_x"), code=303)


@app.route("/cancelar-busqueda-x/<sid>", methods=["POST"])
@requiere_login
def cancelar_busqueda_x(sid):
    solicitudes, sha = cargar_solicitudes()
    if sid not in solicitudes:
        return jsonify({"ok": False, "error": "no existe"}), 404
    solicitudes[sid]["estado"] = "cancelada"
    solicitudes[sid].setdefault("pasos", []).append(
        {"ts": ahora_iso(), "texto": "Cancelada desde el panel."}
    )
    contenido = json.dumps(solicitudes, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    ok = escribir_repo(RUTA_SOLICITUDES, contenido, f"panel: cancela busqueda X {sid}", sha)
    return jsonify({"ok": ok})


# --- Panel de automatización de X (lo que ya había) ---

def contar_pendientes(estilo: str) -> int:
    resultado = leer_contenido_repo(f"experimentos/ingesta_x/cola/{estilo}.txt")
    if not resultado:
        return 0
    contenido, _ = resultado
    return sum(1 for linea in contenido.splitlines() if linea.strip() and not linea.strip().startswith("#"))


@app.route("/automatizacion", methods=["GET", "POST"])
@requiere_login
def panel():
    config = {"activo": True, "hora_local": 3, "zona_horaria": "Europe/Madrid"}
    config_sha = None
    resultado = leer_contenido_repo(RUTA_CONFIG)
    if resultado:
        contenido, config_sha = resultado
        try:
            config.update(json.loads(contenido))
        except ValueError:
            pass

    pendientes = {estilo: contar_pendientes(estilo) for estilo, _ in CATEGORIAS}

    ejecuciones = []
    r = requests.get(
        f"{API}/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/runs",
        headers=CABECERAS, params={"branch": BRANCH, "per_page": 6}, timeout=15,
    )
    if r.status_code == 200:
        for run in r.json().get("workflow_runs", []):
            ejecuciones.append({
                "estado": run["status"], "conclusion": run.get("conclusion"),
                "disparo": run["event"], "creado": run["created_at"], "url": run["html_url"],
            })

    return render_template_string(
        PLANTILLA_PANEL, config=config, config_sha=config_sha,
        pendientes=pendientes, total_pendientes=sum(pendientes.values()),
        ejecuciones=ejecuciones, repo=REPO,
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
    resultado = leer_contenido_repo(RUTA_CONFIG)
    sha_actual = resultado[1] if resultado else None
    nuevo_config = {
        "activo": request.form.get("activo") == "on",
        "hora_local": int(request.form.get("hora_local", 3)),
        "zona_horaria": request.form.get("zona_horaria", "Europe/Madrid").strip(),
    }
    contenido = (json.dumps(nuevo_config, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    escribir_repo(RUTA_CONFIG, contenido, "panel: actualiza config.json", sha_actual)
    return redirect(url_for("panel"), code=303)


PLANTILLA_LOGIN = """
<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Taxonomía de estilos</title>
<style>
  body { font-family: system-ui, sans-serif; background: #f6f3ee; color: #211d18;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
  form { background: #fff; padding: 24px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,.08); width: 90%; max-width: 320px; }
  input { width: 100%; padding: 10px; margin-top: 8px; border-radius: 8px; border: 1px solid #ddd; box-sizing: border-box; }
  button { width: 100%; margin-top: 14px; padding: 11px; border: none; border-radius: 8px; background: #2f4a6b; color: #fff; font-weight: 700; }
  .error { color: #a8433a; font-size: 0.85rem; margin-top: 8px; }
</style></head><body>
<form method="post">
  <strong>Taxonomía de estilos</strong>
  <input type="password" name="clave" placeholder="Contraseña" autofocus>
  <button type="submit">Entrar</button>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
</form>
</body></html>
"""

ESTILO_PAGINA = """
  body { font-family: system-ui, -apple-system, sans-serif; background: #f6f3ee; color: #211d18; margin: 0; }
  .envoltura { max-width: 620px; margin: 0 auto; padding-bottom: 40px; }
  header { padding: 14px 16px; border-bottom: 1px solid #e2dcd0; background: #fff; position: sticky; top: 0; z-index: 5; }
  h1 { font-family: system-ui, sans-serif; font-weight: 800; font-size: 1.1rem; margin: 0 0 8px; }
  nav { display: flex; gap: 6px; margin-top: 10px; }
  nav a { flex: 1; text-align: center; font-size: 0.78rem; font-weight: 700; padding: 8px 6px; border-radius: 9px;
          border: 1px solid #e2dcd0; background: #efeae1; color: #746c60; text-decoration: none; }
  nav a.activa { background: #2f4a6b; border-color: #2f4a6b; color: #fff; }
  .progreso { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
  .progreso-barra { flex: 1; height: 6px; border-radius: 4px; background: #e4ebf1; overflow: hidden; }
  .progreso-relleno { height: 100%; background: #4f7a56; border-radius: 4px; transition: width .3s ease; }
  .progreso span { font-size: 0.68rem; color: #746c60; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .filtros { display: flex; gap: 8px; margin-top: 10px; }
  .filtros select { flex: 1; font-size: 0.72rem; font-weight: 600; padding: 6px 8px; border-radius: 8px; border: 1px solid #e2dcd0; background: #efeae1; }
  main { padding: 16px; }
  .grupo { margin-bottom: 28px; }
  .titulo-grupo { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid #e4ebf1; padding-bottom: 6px; margin-bottom: 10px; }
  .titulo-grupo h2 { font-size: 1rem; margin: 0; font-weight: 800; }
  .titulo-grupo .n { font-size: 0.72rem; color: #746c60; font-variant-numeric: tabular-nums; }
  .rejilla { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
  .tarjeta { position: relative; background: #fff; border: 1px solid #e2dcd0; border-radius: 12px; overflow: hidden;
             box-shadow: 0 1px 2px rgba(33,29,24,.06), 0 8px 24px -12px rgba(33,29,24,.18); display: flex; flex-direction: column; }
  .tarjeta img { width: 100%; aspect-ratio: 3/4; object-fit: cover; display: block; background: #efeae1; }
  .btn-x { position: absolute; top: 6px; right: 6px; width: 28px; height: 28px; border-radius: 50%; border: none;
           background: rgba(20,18,14,.6); color: #fff; font-size: 0.9rem; display: flex; align-items: center; justify-content: center; cursor: pointer; }
  .btn-x[data-activo="true"] { background: #4f7a56; }
  .cuerpo { padding: 8px; display: flex; flex-direction: column; gap: 6px; }
  .fuente { font-size: 0.6rem; color: #746c60; text-decoration: none; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chips { display: flex; flex-wrap: wrap; gap: 4px; }
  .chip { font-size: 0.64rem; font-weight: 600; padding: 4px 7px; border-radius: 20px; border: 1px solid #e2dcd0;
          background: #fff; color: #746c60; cursor: pointer; }
  .chip[data-activo="true"] { background: #2f4a6b; border-color: #2f4a6b; color: #fff; }
  .chip.corregida[data-activo="true"] { background: #4f7a56; border-color: #4f7a56; }
  .chip.ninguna { border-style: dashed; font-style: italic; }
  .chip.ninguna[data-activo="true"] { background: #efeae1; border-color: #746c60; color: #746c60; }
  .eje-ocasion { margin-top: 6px; padding-top: 6px; border-top: 1px dashed #e2dcd0; }
  .eje-ocasion .etq { font-size: 0.56rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #746c60; display: block; margin-bottom: 3px; }
  .chip-ocasion { border-style: dashed; }
  .chip-ocasion[data-activo="true"] { background: #e4ebf1; border-color: #2f4a6b; border-style: solid; color: #2f4a6b; }
  .vacio { font-size: 0.8rem; color: #746c60; padding: 12px; background: #efeae1; border-radius: 10px; text-align: center; grid-column: 1/-1; }
  .anadir { margin-top: 8px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
            border: 1.5px dashed #e2dcd0; border-radius: 12px; padding: 16px 10px; background: #efeae1; cursor: pointer; min-height: 140px; }
  .anadir span { font-size: 0.7rem; color: #746c60; text-align: center; }
  .aviso-nota { font-size: 0.72rem; color: #746c60; text-align: center; margin-top: -8px; margin-bottom: 20px; }
  .aviso { position: fixed; top: 14px; left: 50%; transform: translateX(-50%) translateY(-140%); background: #211d18; color: #f6f3ee;
           font-size: 0.8rem; font-weight: 600; padding: 8px 15px; border-radius: 20px; z-index: 20; transition: transform .25s ease; white-space: nowrap; }
  .aviso.visible { transform: translateX(-50%) translateY(0); }
"""

NAV_COMUN = """
    <nav>
      <a href="{{ url_for('galeria') }}"%(activa_clasificar)s>Clasificar fotos</a>
      <a href="{{ url_for('buscar_x') }}"%(activa_buscar)s>Buscar en X</a>
      <a href="{{ url_for('panel') }}"%(activa_automatizacion)s>Automatización X</a>
    </nav>
"""


def nav(activa: str) -> str:
    return NAV_COMUN % {
        "activa_clasificar": ' class="activa"' if activa == "clasificar" else "",
        "activa_buscar": ' class="activa"' if activa == "buscar" else "",
        "activa_automatizacion": ' class="activa"' if activa == "automatizacion" else "",
    }


PLANTILLA_GALERIA = """
<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Taxonomía de estilos</title>
<style>""" + ESTILO_PAGINA + """</style></head><body>
{% macro tarjeta(item) %}
<article class="tarjeta" data-id="{{ item.id }}" data-categoria-ia="{{ item.categoria_ia }}">
  <img src="{{ url_for('static', filename='fotos/' + item.imagen) }}" loading="lazy" alt="{{ nombre_categoria.get(item.categoria_final or item.categoria_ia, '') }}">
  <button type="button" class="btn-x" data-activo="{{ 'true' if item.eliminada else 'false' }}"
          onclick="alternarEliminar('{{ item.id }}', this)">{{ '↺' if item.eliminada else '✕' }}</button>
  <div class="cuerpo">
    {% if item.fuente_url %}<a class="fuente" href="{{ item.fuente_url }}" target="_blank" rel="noopener">{{ item.fuente }}</a>
    {% else %}<span class="fuente">{{ item.fuente }}</span>{% endif %}
    <div class="chips">
      {% for valor, etiqueta in estilos_chip %}
      <button type="button" class="chip {{ 'ninguna' if valor=='ninguna' }} {{ 'corregida' if valor==(item.categoria_final or item.categoria_ia) and valor != item.categoria_ia and valor != 'ninguna' }}"
              data-activo="{{ 'true' if valor==(item.categoria_final or item.categoria_ia) else 'false' }}"
              onclick="clasificar('{{ item.id }}', '{{ valor }}', this)">{{ etiqueta }}</button>
      {% endfor %}
    </div>
    <div class="eje-ocasion">
      <span class="etq">Ocasión</span>
      <div class="chips">
        {% for valor, etiqueta in ocasiones %}
        <button type="button" class="chip chip-ocasion {{ 'ninguna' if valor=='ninguna' }}"
                data-activo="{{ 'true' if valor==(item.ocasion_final or 'ninguna') else 'false' }}"
                onclick="marcarOcasion('{{ item.id }}', '{{ valor }}', this)">{{ etiqueta }}</button>
        {% endfor %}
      </div>
    </div>
  </div>
</article>
{% endmacro %}

{% macro tarjeta_anadir(clave, etiqueta) %}
<form class="anadir" method="post" action="{{ url_for('subir') }}" enctype="multipart/form-data" onclick="document.getElementById('input-{{ clave }}').click()">
  <span>📷<br>Añadir fotos propias<br>a "{{ etiqueta }}"</span>
  <input type="hidden" name="categoria" value="{{ clave }}">
  <input type="file" name="fotos" id="input-{{ clave }}" accept="image/*" multiple style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);"
         onchange="this.form.submit()">
</form>
{% endmacro %}

<div class="envoltura">
  <header>
    <h1>Taxonomía de estilos</h1>
    <div style="font-size:0.75rem;color:#746c60;">{{ total }} fotos{% if sin_imagen %} · {{ sin_imagen|length }} sin imagen recuperada{% endif %}</div>
    <div class="progreso">
      <div class="progreso-barra"><div class="progreso-relleno" style="width:{{ (100 * revisadas / total)|round(1) if total else 0 }}%;"></div></div>
      <span>{{ revisadas }} revisadas de {{ total }}</span>
    </div>
    <div class="filtros">
      <select id="filtro-origen" onchange="cambiarFiltro()">
        <option value="todas" {{ 'selected' if filtro_origen=='todas' }}>Origen: todas</option>
        <option value="autor" {{ 'selected' if filtro_origen=='autor' }}>Añadidas por mí</option>
        <option value="claude" {{ 'selected' if filtro_origen=='claude' }}>Añadidas por Claude</option>
      </select>
      <select id="filtro-revision" onchange="cambiarFiltro()">
        <option value="todas" {{ 'selected' if filtro_revision=='todas' }}>Revisión: todas</option>
        <option value="revisadas" {{ 'selected' if filtro_revision=='revisadas' }}>Ya las revisé</option>
        <option value="sin_revisar" {{ 'selected' if filtro_revision=='sin_revisar' }}>Sin revisar todavía</option>
      </select>
    </div>
    """ + nav("clasificar") + """
  </header>
  <main>
    {% for clave, etiqueta in categorias %}
    <section class="grupo">
      <div class="titulo-grupo"><h2>{{ etiqueta }}</h2><span class="n">{{ grupos[clave]|length }}</span></div>
      <div class="rejilla">
        {% if grupos[clave]|length == 0 %}<div class="vacio">Sin fotos en esta categoría.</div>{% endif %}
        {% for item in grupos[clave] %}{{ tarjeta(item) }}{% endfor %}
        {{ tarjeta_anadir(clave, etiqueta) }}
      </div>
    </section>
    {% endfor %}

    {% if sin_estilo|length > 0 %}
    <section class="grupo">
      <div class="titulo-grupo"><h2 style="color:#746c60;font-style:italic;">Sin estilo</h2><span class="n">{{ sin_estilo|length }}</span></div>
      <div class="rejilla">{% for item in sin_estilo %}{{ tarjeta(item) }}{% endfor %}</div>
    </section>
    {% endif %}

    {% if eliminadas|length > 0 %}
    <section class="grupo">
      <div class="titulo-grupo"><h2 style="color:#746c60;font-style:italic;">Eliminadas</h2><span class="n">{{ eliminadas|length }}</span></div>
      <div class="rejilla">{% for item in eliminadas %}{{ tarjeta(item) }}{% endfor %}</div>
    </section>
    {% endif %}

    {% if sin_imagen|length > 0 %}
    <section class="grupo">
      <div class="titulo-grupo"><h2 style="color:#a8433a;">Sin imagen recuperada</h2><span class="n">{{ sin_imagen|length }}</span></div>
      <p style="font-size:0.75rem;color:#746c60;margin-top:-4px;">
        Un fallo del artefacto antiguo borró la foto de estas {{ sin_imagen|length }} entradas al corregir su estilo
        (quedó solo el registro, no la imagen). Vuelve a añadir la foto a su categoría, o descarta el registro.
      </p>
      <div class="rejilla">
        {% for item in sin_imagen %}
        <article class="tarjeta" style="aspect-ratio:3/4;">
          <div style="flex:1;display:flex;align-items:center;justify-content:center;background:#efeae1;color:#746c60;font-size:0.7rem;text-align:center;padding:10px;">
            Foto perdida<br><strong>{{ nombre_categoria.get(item.categoria_final or item.categoria_ia, '') }}</strong>
          </div>
          <div class="cuerpo">
            <button type="button" class="chip" style="width:100%;box-sizing:border-box;background:#a8433a;border-color:#a8433a;color:#fff;"
                    onclick="alternarEliminar('{{ item.id }}', this)">Descartar registro</button>
          </div>
        </article>
        {% endfor %}
      </div>
    </section>
    {% endif %}
  </main>
</div>
<div class="aviso" id="aviso">Guardado</div>

<script>
function mostrarAviso(texto) {
  const el = document.getElementById('aviso');
  el.textContent = texto;
  el.classList.add('visible');
  setTimeout(() => el.classList.remove('visible'), 1300);
}
function cambiarFiltro() {
  const origen = document.getElementById('filtro-origen').value;
  const revision = document.getElementById('filtro-revision').value;
  window.location.href = '{{ url_for("galeria") }}?origen=' + origen + '&revision=' + revision;
}
async function clasificar(id, valor, btn) {
  const fila = btn.closest('.chips');
  fila.querySelectorAll('.chip').forEach(c => c.dataset.activo = 'false');
  btn.dataset.activo = 'true';
  const tarjeta = btn.closest('.tarjeta');
  const esIA = valor === tarjeta.dataset.categoriaIa;
  fila.querySelectorAll('.chip').forEach(c => c.classList.remove('corregida'));
  if (!esIA && valor !== 'ninguna') btn.classList.add('corregida');
  try {
    const r = await fetch('/clasificar/' + id, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({categoria: valor}),
    });
    const d = await r.json();
    mostrarAviso(d.ok ? (esIA ? 'Confirmada' : 'Corregida') : 'No se pudo guardar');
    if (d.ok) setTimeout(() => window.location.reload(), 600);
  } catch (e) { mostrarAviso('Error de red'); }
}
async function marcarOcasion(id, valor, btn) {
  const fila = btn.closest('.chips');
  fila.querySelectorAll('.chip-ocasion').forEach(c => c.dataset.activo = 'false');
  btn.dataset.activo = 'true';
  try {
    const r = await fetch('/ocasion/' + id, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ocasion: valor}),
    });
    const d = await r.json();
    mostrarAviso(d.ok ? 'Guardado' : 'No se pudo guardar');
  } catch (e) { mostrarAviso('Error de red'); }
}
async function alternarEliminar(id, btn) {
  try {
    const r = await fetch('/eliminar/' + id, {method: 'POST'});
    const d = await r.json();
    mostrarAviso(d.ok ? (d.eliminada ? 'Eliminada' : 'Restaurada') : 'No se pudo guardar');
    if (d.ok) setTimeout(() => window.location.reload(), 500);
  } catch (e) { mostrarAviso('Error de red'); }
}
</script>
</body></html>
"""

ESTILO_PANEL_EXTRA = """
  .tarjeta2 { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }
  .btn { display: inline-block; width: 100%; box-sizing: border-box; padding: 13px; border: none; border-radius: 9px;
         background: #2f4a6b; color: #fff; font-weight: 700; font-size: 1rem; text-align: center; cursor: pointer; }
  .fila2 { display: flex; justify-content: space-between; padding: 5px 0; font-size: 0.9rem; border-bottom: 1px solid #eee; }
  .fila2:last-child { border-bottom: none; }
  label { display: block; font-size: 0.72rem; text-transform: uppercase; color: #746c60; margin-top: 10px; }
  input[type=number], input[type=text], select.ancho, textarea {
    width: 100%; padding: 8px; border-radius: 8px; border: 1px solid #ddd; box-sizing: border-box; font-family: inherit;
  }
  .toggle-row { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
  .estado2 { font-size: 0.7rem; padding: 2px 8px; border-radius: 20px; background: #efeae1; }
  .estado2.buscando { background: #fdf1d8; color: #8a6116; }
  .estado2.completado { background: #e4f0e6; color: #3f6a45; }
  .estado2.error { background: #fbe3e0; color: #a8433a; }
  .estado2.cancelada, .estado2.pendiente { background: #efeae1; color: #746c60; }
  .pasos-log { list-style: none; margin: 8px 0 0; padding: 0; font-size: 0.72rem; color: #746c60; }
  .pasos-log li { padding: 3px 0; border-top: 1px dashed #eee; }
  .pasos-log li:first-child { border-top: none; }
  .pasos-log time { font-variant-numeric: tabular-nums; color: #a39a8b; margin-right: 6px; }
  .vista-previa-texto { font-size: 0.75rem; color: #746c60; margin-top: 8px; font-style: italic; }
"""

PLANTILLA_PANEL = """
<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Automatización X</title>
<style>""" + ESTILO_PAGINA + ESTILO_PANEL_EXTRA + """
</style></head><body>
<div class="envoltura">
  <header>
    <h1>Automatización de ingesta en X</h1>
    """ + nav("automatizacion") + """
  </header>
  <main>
  <div class="tarjeta2">
    <form method="post" action="{{ url_for('ejecutar') }}">
      <button class="btn" type="submit">▶ Ejecutar ahora</button>
    </form>
    <p style="font-size:0.75rem;color:#746c60;margin-bottom:0;">Se salta la comprobación de hora, corre al momento.</p>
  </div>
  <div class="tarjeta2">
    <strong>Cola pendiente</strong> (<span style="font-weight:700;">{{ total_pendientes }}</span> en total)
    {% for estilo, n in pendientes.items() %}<div class="fila2"><span>{{ estilo }}</span><span>{{ n }}</span></div>{% endfor %}
  </div>
  <div class="tarjeta2">
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
  <div class="tarjeta2">
    <strong>Últimas ejecuciones</strong>
    {% for e in ejecuciones %}
    <div class="fila2">
      <span><a href="{{ e.url }}" target="_blank">{{ e.creado[:16] }}</a> · {{ e.disparo }}</span>
      <span class="estado2">{{ e.conclusion or e.estado }}</span>
    </div>
    {% else %}<p style="font-size:0.85rem;color:#746c60;">Sin ejecuciones todavía.</p>{% endfor %}
  </div>
  <p style="font-size:0.72rem;color:#746c60;text-align:center;">Repo: <a href="https://github.com/{{ repo }}" target="_blank">{{ repo }}</a></p>
  </main>
</div>
</body></html>
"""

PLANTILLA_BUSCAR_X = """
<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Buscar en X</title>
<style>""" + ESTILO_PAGINA + ESTILO_PANEL_EXTRA + """
</style></head><body>
<div class="envoltura">
  <header>
    <h1>Buscar en X</h1>
    """ + nav("buscar") + """
  </header>
  <main>
  <div class="tarjeta2">
    <p style="font-size:0.8rem;color:#746c60;margin-top:0;">
      Esto dispara un workflow de GitHub Actions que usa Claude Code (con tu suscripción, sin
      coste aparte) para buscar publicaciones reales en X y añadirlas a la cola de descarga.
      Tarda unos minutos — el estado de cada búsqueda se actualiza aquí abajo según avanza.
    </p>
    <form method="post" action="{{ url_for('enviar_busqueda_x') }}" id="form-busqueda">
      <label for="estilo">Estilo</label>
      <select class="ancho" name="estilo" id="estilo" onchange="actualizarVistaPrevia()">
        {% for clave, etiqueta in categorias %}<option value="{{ clave }}">{{ etiqueta }}</option>{% endfor %}
      </select>

      <label for="ocasion">Ocasión (opcional — solo afecta al modo "Automático")</label>
      <select class="ancho" name="ocasion" id="ocasion" onchange="actualizarVistaPrevia()">
        {% for clave, etiqueta in ocasiones %}<option value="{{ clave }}">{{ etiqueta }}</option>{% endfor %}
      </select>

      <label for="modo">Texto de búsqueda</label>
      <select class="ancho" name="modo" id="modo" onchange="actualizarVistaPrevia()">
        <option value="automatico">Automático (estilo + ocasión)</option>
        <option value="predeterminado">Predeterminado (solo estilo)</option>
        <option value="personalizado">Escribirlo yo</option>
      </select>

      <div id="fila-texto-personalizado" hidden>
        <label for="texto_personalizado">Texto personalizado</label>
        <input type="text" name="texto_personalizado" id="texto_personalizado" placeholder="p. ej. streetwear madrileño invierno"
               oninput="actualizarVistaPrevia()">
      </div>

      <div class="vista-previa-texto" id="vista-previa">Se buscará: "…"</div>

      <label for="cantidad">Cuántas publicaciones buscar (3–15)</label>
      <input type="number" name="cantidad" id="cantidad" value="8" min="3" max="15">

      <button class="btn" type="submit" style="margin-top:14px;">Buscar en X</button>
    </form>
  </div>

  {% for s in solicitudes %}
  <div class="tarjeta2">
    <div class="fila2" style="border-bottom:none;padding-bottom:0;">
      <span><strong>{{ s.id|replace('sol_', '') }}</strong> · {{ s.texto_busqueda }}</span>
      <span class="estado2 {{ s.estado }}">{{ s.estado }}</span>
    </div>
    <p style="font-size:0.72rem;color:#746c60;margin:4px 0 0;">
      {{ nombre_categoria.get(s.estilo, s.estilo) }}{% if s.ocasion and s.ocasion != 'ninguna' %} · {{ nombre_ocasion.get(s.ocasion, s.ocasion) }}{% endif %}
      {% if s.urls_encontradas is defined %} · {{ s.urls_encontradas }} URL(s) encontradas{% endif %}
    </p>
    <ul class="pasos-log">
      {% for paso in s.pasos or [] %}
      <li><time>{{ paso.ts[11:16] if paso.ts|length > 16 else paso.ts }}</time>{{ paso.texto }}</li>
      {% endfor %}
    </ul>
    {% if s.estado in ('pendiente', 'buscando') %}
    <button type="button" class="chip" style="margin-top:8px;" onclick="cancelarBusqueda('{{ s.id }}', this)">Cancelar</button>
    {% endif %}
  </div>
  {% else %}
  <p style="font-size:0.85rem;color:#746c60;">Todavía no has lanzado ninguna búsqueda.</p>
  {% endfor %}
  </main>
</div>

<script>
const TEXTO_PREDETERMINADO_ESTILO = {{ texto_predeterminado | tojson }};
const CALIFICADOR_OCASION = {{ calificador_ocasion | tojson }};

function calcularTextoBusqueda(estilo, ocasion, modo, textoManual) {
  if (modo === "personalizado") return (textoManual || "").trim();
  const base = TEXTO_PREDETERMINADO_ESTILO[estilo] || "";
  if (modo === "predeterminado") return base;
  const calificador = CALIFICADOR_OCASION[ocasion];
  return calificador ? `${base} ${calificador}` : base;
}

function actualizarVistaPrevia() {
  const estilo = document.getElementById("estilo").value;
  const ocasion = document.getElementById("ocasion").value;
  const modo = document.getElementById("modo").value;
  const textoManual = document.getElementById("texto_personalizado").value;
  document.getElementById("fila-texto-personalizado").hidden = modo !== "personalizado";
  const texto = calcularTextoBusqueda(estilo, ocasion, modo, textoManual);
  document.getElementById("vista-previa").textContent = `Se buscará: "${texto}"`;
}
actualizarVistaPrevia();

async function cancelarBusqueda(id, btn) {
  btn.disabled = true;
  try {
    const r = await fetch('/cancelar-busqueda-x/' + id, {method: 'POST'});
    const d = await r.json();
    if (d.ok) {
      window.location.reload();
    } else {
      btn.disabled = false;
    }
  } catch (e) {
    btn.disabled = false;
  }
}
</script>
</body></html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
