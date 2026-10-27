#!/usr/bin/env python3
"""
Prueba de las claves de Instagram, en un minuto y sin esperar a la revista del lunes (25 de octubre de 2026).

Se lanza a mano desde GitHub: pestaña Actions → «Prueba de Instagram» → Run workflow. Solo usa la biblioteca estándar y NUNCA imprime una clave
(ni la dirección con la clave: Windsor, cuando rechaza una clave, la repite en su mensaje de error, así que los mensajes de error no se imprimen).
El resultado sale en español en el resumen de la ejecución (y en el registro).

Comprueba, con las mismas funciones que usa la tarea semanal:
  · Meta (app propia): que llega el secreto META_IG_TOKEN, qué tipo de token es y cuándo caduca, qué permisos tiene, qué cuenta de Instagram usa y que Business Discovery
    devuelve publicaciones y fotos que se pueden bajar de unas cuentas de muestra (con la opción «todas», de las cuentas de tendencia_fuentes.json).
  · Windsor: que existe el secreto WINDSOR_API_KEY, que Windsor lo acepta y cuántas publicaciones devuelve con la MISMA petición que hace la tarea semanal.
"""
import collections
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import instagram_meta as im  # noqa: E402

WINDSOR_URL = "https://connectors.windsor.ai/instagram_public"
PERMISOS_NECESARIOS = ("instagram_basic", "pages_read_engagement", "instagram_manage_insights")
FORMAS_COSTE = (("50 publicaciones con carruseles", 50, True), ("30 con carruseles", 30, True), ("30 sin carruseles", 30, False), ("12 sin carruseles", 12, False))
CUENTAS_COSTE = ("zara", "stussy", "gucci")   # una que publica mucho, una normal y una grande
LINEAS: list[str] = []
CORTE_POR_CUOTA = False   # la prueba terminó porque Meta limitó la app, no por el token


def dice(txt: str = "") -> None:
    print(txt, flush=True)
    LINEAS.append(txt)


def texto_caducidad(expira: int | None, dias: int | None, ahora: float | None = None) -> tuple[str, bool]:
    """(frase, es_corto): «no caduca», «caduca el 26-12-2026 (dentro de 60 días)» o, si le quedan menos de 24 h (token corto del Explorador), la hora y las horas que quedan."""
    if not expira:
        return "no caduca", False
    horas = (expira - (time.time() if ahora is None else ahora)) / 3600
    fecha = datetime.fromtimestamp(expira, timezone.utc)
    if horas < 0:
        return f"caducó el {fecha:%d-%m-%Y a las %H:%M} UTC", False
    if horas < 24:
        return f"caduca el {fecha:%d-%m-%Y a las %H:%M} UTC (dentro de {horas:.1f} horas)".replace(".", ","), True
    return f"caduca el {fecha:%d-%m-%Y} (dentro de {dias} días)", False


def anotacion_resumen(lineas: list[str]) -> str:
    """El resumen entero como anotación de GitHub (`::notice`): la API pública la deja leer sin iniciar sesión. Nunca lleva claves: ninguna línea las imprime."""
    texto = "\n".join(lineas).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return f"::notice title=Resumen de la prueba de Instagram::{texto}"


def fallo_meta(e: Exception) -> None:
    """Cuenta un error de Meta; si es de cuota lo dice claro, porque no es culpa del token."""
    global CORTE_POR_CUOTA
    if getattr(e, "tipo", "") == "cupo":
        CORTE_POR_CUOTA = True
        dice("✘ Meta ha limitado las peticiones de la app (código 4). El límite es de TIEMPO de proceso por hora y cada cuenta gasta unos pocos puntos: no es un fallo del token. "
             "Espera una hora sin usar el Explorador de Meta ni lanzar más pruebas, y repite.")
    else:
        dice(f"✘ {e}")


def prueba_coste(ig_id: str, token: str, corte: datetime, abrir=urllib.request.urlopen) -> None:
    """Mide cuánta cuota de la app gasta cada forma de pedir las publicaciones. La cabecera de Meta acumula (ventana de 1 h) y solo da enteros: se resta lo anterior y se promedian 3 cuentas."""
    dice("Coste de cada forma de pedir las publicaciones (puntos de cuota de la app por cuenta; Meta corta al llegar a 100 dentro de una hora):")

    def uso_ahora() -> dict | None:
        try:
            return im.uso_detalle(im.llamar(ig_id, {"fields": "id"}, token, abrir)[2])   # petición casi gratis, solo para leer la cabecera
        except im.MetaError:
            return None

    for nombre, n, hijos in FORMAS_COSTE:
        antes = uso_ahora()
        if antes is None:
            dice("   (Meta no dice cuánta cuota queda: no se puede medir.)")
            return
        t0, filas_n, ultimo = time.time(), 0, antes
        for c in CUENTAS_COSTE:
            try:
                filas, inf = im.leer_cuenta(ig_id, c, token, corte, abrir, limite=n, paginas=1, con_hijos=hijos)
            except im.MetaError as e:
                fallo_meta(e)
                return
            filas_n += len(filas)
            ultimo = im.uso_detalle(inf.get("cabeceras")) or ultimo
        k = len(CUENTAS_COSTE)
        d_tiempo, d_pet = (ultimo["total_time"] - antes["total_time"]) / k, (ultimo["call_count"] - antes["call_count"]) / k
        por_hora = f"≈ {75 / d_tiempo:.0f} cuentas por hora al 75 % de la cuota" if d_tiempo > 0 else "gasta menos de lo que se puede medir"
        dice(f"   · {nombre}: +{d_tiempo:.1f} de tiempo y +{d_pet:.1f} de peticiones por cuenta ({(time.time() - t0) / k:.1f} s, {filas_n / k:.0f} filas de media) → {por_hora}")
        time.sleep(0.4)


def cuentas_de_instagram() -> list[str]:
    cfg = json.loads((AQUI / "tendencia_fuentes.json").read_text(encoding="utf-8"))["fuentes"]
    return sorted({x["valor"].lstrip("@").lower() for x in cfg if x.get("tipo") == "instagram"})


def muestra(cuentas: list[str], n: int = 6) -> list[str]:
    """Cuentas de muestra repartidas por estilo y mercado (las primeras de cada casilla), para no gastar peticiones."""
    cfg = json.loads((AQUI / "tendencia_fuentes.json").read_text(encoding="utf-8"))["fuentes"]
    vistas, out = set(), []
    for x in cfg:
        if x.get("tipo") == "instagram" and (x["estilo"], x["mercado"]) not in vistas:
            vistas.add((x["estilo"], x["mercado"]))
            out.append(x["valor"].lstrip("@").lower())
    return (out + [c for c in cuentas if c not in out])[:n]


def foto_bajable(url: str) -> str:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=0-1023", "User-Agent": "Mozilla/5.0"}), timeout=30) as r:
            return "sí" if str(r.headers.get("Content-Type", "")).startswith("image") else f"no ({r.headers.get('Content-Type', '?')})"
    except Exception as e:  # noqa: BLE001
        return f"no ({type(e).__name__})"


def prueba_meta() -> bool | None:
    dice("## Meta (app propia: Business Discovery)")
    token = im.limpiar_token(os.environ.get("META_IG_TOKEN", ""))
    if not token:
        dice("— Todavía no hay secreto META_IG_TOKEN (es normal si aún no has hecho la guía de la app de Meta). No se prueba.")
        return None
    if len(token) < 40 or " " in token or token.startswith(("'", '"')):
        dice(f"✘ El token guardado tiene un aspecto raro (longitud {len(token)}, con espacios o comillas). Un token de Meta mide ~200 caracteres y empieza por «EAA»: vuelve a copiarlo entero, sin comillas ni espacios.")
        return False
    dice(f"Token guardado: {len(token)} caracteres; empieza por «EAA»: {'sí' if token.startswith('EAA') else 'no'}.")   # sin enseñar el token: solo su forma
    # 1) qué token es (Meta deja mirar un token con él mismo)
    ficha = im.ficha_token(token)
    if ficha:
        tipo = {"USER": "de persona", "PAGE": "de página"}.get(ficha["tipo"], ficha["tipo"] or "de tipo desconocido")
        caduca, corto = texto_caducidad(ficha["expira"], ficha["dias"])
        dice(f"Token {tipo}; {'válido' if ficha['valido'] else 'NO válido'}; {caduca}.")
        if not ficha["valido"]:
            dice("✘ Meta dice que el token ya no es válido: genera otro (guía, parte 4).")
            return False
        dice("Permisos del token: " + (", ".join(ficha["permisos"]) or "(no se pudieron leer)"))
        faltan = [p for p in PERMISOS_NECESARIOS if p not in ficha["permisos"]]
        if faltan and ficha["permisos"]:
            dice(f"⚠ Faltan permisos: {', '.join(faltan)}. Al generar el token (guía, parte 3) hay que marcarlos todos; si no te dejaba, dímelo.")
        if corto:
            dice("⚠ Es un token CORTO (dura 1-2 horas): vale para probar hoy, pero la tarea semanal necesita el LARGO. En el depurador de tokens pulsa «Ampliar token de acceso», copia el token NUEVO que sale abajo (no el del campo del Explorador) y guárdalo como META_IG_TOKEN (guía, parte 4).")
        elif ficha["dias"] is not None and ficha["dias"] < 15:
            dice(f"⚠ Al token le quedan {ficha['dias']} días: renuévalo pronto (guía, parte 4).")
    else:
        dice("(No se pudo leer la ficha del token; se sigue probando.)")
    # 2) qué cuenta de Instagram usa
    try:
        candidatos, ig_id, tipo_tok, detalle = im.preparar(token, os.environ.get("META_IG_USER_ID", "").strip())
    except im.MetaError as e:
        fallo_meta(e)
        return False
    dice(f"✔ Cuenta de Instagram encontrada: {ig_id} ({detalle}; el token es {'de página' if tipo_tok == 'página' else 'de persona: la tarea prueba primero ese y, si no vale, el de su página'}).")
    corte = datetime.now(timezone.utc) - timedelta(days=35)
    cuentas = cuentas_de_instagram()
    tok = None
    for k, cand in enumerate(candidatos):
        nombre = "el token tal cual" if k == 0 else "el token de la página que cuelga de él"
        try:
            filas, _ = im.leer_cuenta(ig_id, "zara", cand, corte, limite=3, paginas=1, con_hijos=False)   # sonda barata: la cuota es de tiempo de proceso
            dice(f"✔ Business Discovery funciona con {nombre} (prueba con @zara: {len(filas)} publicaciones).")
            tok = tok or cand
        except im.MetaError as e:
            dice(f"✘ Con {nombre} no funciona:") if getattr(e, "tipo", "") != "cupo" else None
            fallo_meta(e)
    if tok is None:
        dice("✘ Ningún token vale para Business Discovery. Si el mensaje habla de permisos, repite la parte 3 marcando todos; si habla de «app review» o similar, dímelo.")
        return False
    if os.environ.get("PRUEBA_COSTE") == "1":
        prueba_coste(ig_id, tok, corte)
        dice("Campos que acepta Business Discovery: " + ", ".join(im._CAMPOS_VIVOS))   # los que Meta no rechazó
        return not CORTE_POR_CUOTA
    # 3) Business Discovery con cuentas de muestra
    pruebas = cuentas if os.environ.get("PRUEBA_TODAS") == "1" else muestra(cuentas)
    dice(f"Business Discovery con {len(pruebas)} cuentas ({'todas las de las fuentes' if len(pruebas) == len(cuentas) else 'de muestra, una por casilla estilo/mercado'}):")
    leidas, sin, bajables, probadas, cab = 0, {}, 0, 0, {}
    for i, c in enumerate(pruebas):
        try:
            filas, inf = im.leer_cuenta(ig_id, c, tok, corte)
        except im.MetaError as e:
            dice(f"(Antes del corte se habían leído {leidas} de {len(pruebas)} cuentas.)")
            fallo_meta(e)
            return False
        cab = inf.get("cabeceras") or cab
        if not filas:
            sin[c] = inf.get("motivo") or "sin publicaciones en 35 días"
            continue
        leidas += 1
        fotos = [f for f in filas if f.get("media_url") and f.get("media_type") != "VIDEO"]
        if len(pruebas) <= 12:
            u = im.uso_detalle(cab)
            dice(f"   · {c}: {len(filas)} filas ({len(fotos)} con foto), {inf.get('seguidores')} seguidores" + (f"; cuota de la app: tiempo {u['total_time']:.0f} %" if u else ""))
        if fotos and probadas < 4:
            probadas += 1
            r = foto_bajable(fotos[0]["media_url"])
            bajables += r == "sí"
            dice(f"     foto de {c} se puede bajar: {r}")
        time.sleep(0.4)
    uso = cab.get("x-app-usage") or cab.get("X-App-Usage")
    if uso:
        dice(f"Uso de la cuota de peticiones de la app (cabecera de Meta): {uso}")
    dice(f"Resultado: {leidas} de {len(pruebas)} cuentas devuelven publicaciones; fotos que se pueden bajar: {bajables} de {probadas} probadas.")
    if sin:
        dice(f"Sin lectura ({len(sin)}): " + "; ".join(f"{c} ({m})" for c, m in list(sin.items())[:12]) + ("…" if len(sin) > 12 else ""))
    if leidas == 0:
        dice("✘ Meta no devolvió publicaciones de ninguna cuenta. Mira arriba si es de permisos; si todo parece bien, la app puede necesitar la revisión de Meta para leer cuentas ajenas: dímelo.")
        return False
    dice("✔ Meta FUNCIONA: la tarea semanal puede leer Instagram con la app propia.")
    return True


def prueba_windsor() -> bool | None:
    dice("## Windsor (lectura de Instagram por el conector oficial)")
    clave = os.environ.get("WINDSOR_API_KEY", "").strip()
    if not clave:
        dice("— No llega el secreto WINDSOR_API_KEY (si ya no usas Windsor, es normal).")
        return None
    if len(clave) < 20 or " " in clave or clave.startswith(("'", '"')):
        dice(f"✘ La clave guardada tiene un aspecto raro (longitud {len(clave)}, con espacios o comillas): vuelve a copiarla en Windsor → Data preview → API key, sin comillas ni espacios.")
        return False
    cuentas = cuentas_de_instagram()
    hoy = datetime.now(timezone.utc).date()
    q = {"api_key": clave, "fields": "account_name,media_id,media_type,media_timestamp,media_url,profile_followers_count",
         "date_from": (hoy - timedelta(days=14)).isoformat(), "date_to": hoy.isoformat(), "select_accounts": ",".join(cuentas), "_renderer": "json"}

    def pedir(consulta: dict):
        try:
            with urllib.request.urlopen(urllib.request.Request(WINDSOR_URL + "?" + urllib.parse.urlencode(consulta), headers={"User-Agent": "Mozilla/5.0"}), timeout=180) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode("utf-8", "replace")
            return e.code, ("clave" if "API key" in cuerpo else "otro")
        except Exception as e:  # noqa: BLE001
            return 0, type(e).__name__

    estado, datos = pedir(q)
    dice(f"Petición con las {len(cuentas)} cuentas de las fuentes (igual que la de la revista): respuesta HTTP {estado}.")
    if estado == 400 and datos == "clave":
        dice("✘ Windsor RECHAZA la clave: no es válida (o la prueba gratuita ya terminó). Cópiala de nuevo en Windsor (onboard.windsor.ai → Data preview → API key), sin comillas ni espacios, y guárdala otra vez como secreto WINDSOR_API_KEY.")
        return False
    if estado != 200:
        if estado in (400, 404, 422):
            dice("La petición con la lista completa de cuentas da error: la tarea semanal repite la petición SIN lista y se queda con las cuentas de las fuentes. Pruebo así:")
            q.pop("select_accounts")
            estado, datos = pedir(q)
            dice(f"Petición sin lista de cuentas: respuesta HTTP {estado}.")
        if estado != 200:
            dice(f"✘ Windsor no contesta bien ({estado}, {datos if isinstance(datos, str) else 'respuesta rara'}). Reintenta en unos minutos; si sigue igual, el fallo es de Windsor.")
            return False
    filas = datos.get("data", []) if isinstance(datos, dict) else datos
    por = collections.Counter(str(f.get("account_name") or "").lower() for f in filas or [])
    pedidas = set(cuentas)
    leidas = sorted(c for c in por if c in pedidas)
    dice(f"✔ La clave de Windsor FUNCIONA: {sum(por[c] for c in leidas)} publicaciones de {len(leidas)} cuentas en los últimos 14 días.")
    for c in leidas:
        dice(f"   · {c}: {por[c]}")
    ajenas = sorted(c for c in por if c not in pedidas)
    if ajenas:
        dice(f"(Windsor devuelve además {len(ajenas)} cuentas que no son fuentes: {', '.join(ajenas)}; la tarea las descarta.)")
    dice(f"Cuentas de las fuentes que Windsor NO lee ahora ({len(pedidas) - len(leidas)}): hay 14 dadas de alta durante la prueba gratuita; el resto se lee con la app de Meta o con otro plan.")
    return True


def main() -> int:
    meta = prueba_meta()
    dice()
    windsor = prueba_windsor()
    dice()
    principal = meta if meta is not None else windsor
    if meta is True:
        dice("RESULTADO: la lectura de Instagram con la app de Meta funciona." + (" Windsor sirve de respaldo." if windsor else " (Windsor ya no hace falta.)"))
    elif meta is False and CORTE_POR_CUOTA:
        dice("RESULTADO: Meta limitó la app durante la prueba (cuota de tiempo por hora). El token no es el problema: repite pasada una hora." + (" Windsor sirve de respaldo." if windsor else ""))
    elif meta is False:
        dice("RESULTADO: hay algo que arreglar con el token de Meta (mira el ✘ de arriba)." + (" Mientras, la tarea semanal sigue leyendo con Windsor." if windsor else ""))
    elif windsor:
        dice("RESULTADO: todo bien con Windsor (la app de Meta aún no está montada).")
    else:
        dice("RESULTADO: hay algo que arreglar con Windsor (mira el ✘ de arriba).")
    print(anotacion_resumen(LINEAS), flush=True)
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as f:
            f.write("### Prueba de Instagram\n\n```\n" + "\n".join(LINEAS) + "\n```\n")
    return 0 if principal else 1


if __name__ == "__main__":
    sys.exit(main())
