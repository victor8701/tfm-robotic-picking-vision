#!/usr/bin/env python3
"""
Lectura de Instagram con la app propia de Meta (Business Discovery) — 25 de octubre de 2026. Solo biblioteca estándar.

Alternativa gratuita y sin tope de cuentas al conector de Windsor: con una app de Meta en modo desarrollo (Víctor es su administrador) y un token de la cuenta profesional
`tendencias.moda_`, Business Discovery deja leer las últimas publicaciones de OTRAS cuentas profesionales (Creador/Empresa) por su @. No descubre cuentas ni hashtags.
Documentación: https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/business-discovery

Secretos de GitHub (nunca se imprimen; los mensajes de error no llevan direcciones ni el token):
  META_IG_TOKEN     token de Meta: vale el de PERSONA (largo, ~60 días) o el de PÁGINA (el que sale de `me/accounts`; no caduca mientras no cambie la contraseña o se quite la app)
  META_IG_USER_ID   (opcional) identificador de la cuenta de Instagram profesional; si falta se busca solo

Devuelve las publicaciones con los MISMOS nombres de campo que el conector de Windsor (`account_name`, `media_id`, `media_type`, `media_url`, `media_thumbnail_url`, `media_permalink`,
`media_timestamp`, `media_like_count`, `media_comments_count`, `profile_followers_count`, `media_caption`): el resto de la tubería no distingue de dónde vienen.
"""
import collections
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

VERSION = "v25.0"
BASE = f"https://graph.facebook.com/{VERSION}/"
MEDIA_POR_PAGINA = 50     # publicaciones por petición (con 35 días de ventana casi todas las cuentas caben en una página)
PAGINAS_MAX = 2           # páginas como mucho por cuenta
HIJOS_MAX = 4             # fotos de un carrusel que se leen como filas aparte (como hace Windsor)
CAMPOS_MEDIA = ["id", "media_type", "media_url", "thumbnail_url", "permalink", "timestamp", "caption", "like_count", "comments_count", "children{id,media_type,media_url}"]
CAMPOS_PRESCINDIBLES = {"thumbnail_url", "caption", "like_count", "comments_count", "children{id,media_type,media_url}", "permalink"}   # si Meta dice que uno no existe en Business Discovery, se quita y se sigue
_CAMPOS_VIVOS = list(CAMPOS_MEDIA)   # los que funcionan (se van quitando los que Meta rechace); se arranca de cero en cada ejecución

# códigos de error de la API de Meta que importan aquí
COD_TOKEN = {190, 102, 2500}                 # token caducado, sin sesión o mal copiado
COD_PERMISOS = {10, 200, 299, 3}             # falta algún permiso del token
COD_CUPO = {4, 17, 32, 341, 613, 80002, 80004}   # demasiadas peticiones (o la app está limitada)
COD_NO_DISPONIBLE = {110, 24}                # «Invalid user id»: la cuenta pedida no es profesional, no existe o es privada/con límite de edad


class MetaError(ValueError):
    """Error que se puede enseñar tal cual: nunca lleva el token. `tipo`: token | permisos | cupo | otro."""

    def __init__(self, msg: str, tipo: str = "otro"):
        super().__init__(msg)
        self.tipo = tipo


def _limpiar(txt: str, token: str) -> str:
    return (txt or "").replace(token, "***") if token else (txt or "")


def llamar(ruta: str, params: dict, token: str, abrir=urllib.request.urlopen) -> tuple[int, dict, dict]:
    """GET a la API Graph. Devuelve (HTTP, cuerpo JSON, cabeceras). Si no hay respuesta, MetaError sin la dirección (lleva el token)."""
    q = dict(params)
    q["access_token"] = token
    req = urllib.request.Request(BASE + ruta + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "Mozilla/5.0"})
    try:
        with abrir(req, timeout=60) as r:
            return int(getattr(r, "status", 200) or 200), json.load(r), dict(getattr(r, "headers", {}) or {})
    except urllib.error.HTTPError as e:
        try:
            cuerpo = json.load(e)
        except Exception:  # noqa: BLE001
            cuerpo = {}
        return e.code, cuerpo if isinstance(cuerpo, dict) else {}, dict(getattr(e, "headers", {}) or {})
    except Exception as e:  # noqa: BLE001
        raise MetaError(f"Meta no contestó ({type(e).__name__})") from None


def clasificar(cuerpo: dict, token: str = "") -> tuple[str, int | None, str]:
    """(tipo, código, mensaje corto) de un error de la API: tipo ∈ token | permisos | cupo | no_disponible | otro."""
    e = (cuerpo or {}).get("error") or {}
    cod = e.get("code")
    msg = _limpiar(str(e.get("message") or ""), token)[:200]
    try:
        cod = int(cod)
    except (TypeError, ValueError):
        cod = None
    if cod in COD_TOKEN:
        tipo = "token"
    elif cod in COD_PERMISOS or "permission" in msg.lower():
        tipo = "permisos"
    elif cod in COD_CUPO or "request limit" in msg.lower():
        tipo = "cupo"
    elif cod in COD_NO_DISPONIBLE or "invalid user id" in msg.lower():
        tipo = "no_disponible"
    else:
        tipo = "otro"
    return tipo, cod, msg


def explicar(tipo: str, cod, msg: str) -> str:
    """Frase en español para el registro y la prueba."""
    if tipo == "token":
        return f"El token de Meta no vale: ha caducado, se cambió la contraseña de Facebook o está mal copiado (código {cod}). Hay que generar otro (guía, parte 4) y guardarlo de nuevo como META_IG_TOKEN."
    if tipo == "permisos":
        return f"Al token le falta algún permiso o la app no tiene acceso a la cuenta (código {cod}: {msg}). Revisa que al generarlo marcaste todos los permisos de la guía y que elegiste la página y la cuenta de Instagram."
    if tipo == "cupo":
        return f"Meta ha limitado las peticiones de la app (código {cod}). Se reintenta la semana que viene; si ocurre siempre, hay que reducir cuentas."
    return f"Meta contestó con un error (código {cod}): {msg}"


def preparar(token: str, ig_id_env: str = "", abrir=urllib.request.urlopen) -> tuple[list[str], str, str, str]:
    """Con el token que haya (de persona o de página) averigua la cuenta de Instagram a usar.
    Devuelve (tokens a probar por orden, id de la cuenta de Instagram, 'persona'|'página'|'desconocido', detalle). Lanza MetaError con un mensaje legible.
    Con un token de persona se prueba primero ese (lo que dice la documentación de Business Discovery) y después el de la página que cuelga de él."""
    st, d, _ = llamar("me/accounts", {"fields": "name,access_token,instagram_business_account"}, token, abrir)
    if st == 200 and isinstance(d.get("data"), list):
        con_ig = [p for p in d["data"] if p.get("instagram_business_account")]
        if ig_id_env:
            con_ig = [p for p in con_ig if str(p["instagram_business_account"].get("id")) == ig_id_env] or con_ig
        if not con_ig:
            raise MetaError("El token vale, pero ninguna de tus páginas de Facebook tiene una cuenta de Instagram profesional enlazada (o al generarlo no elegiste la página). "
                            "Repite la parte 3 de la guía eligiendo la página «Tendencias Moda» y su Instagram.", "permisos")
        p = con_ig[0]
        candidatos = [token] + ([p["access_token"]] if p.get("access_token") and p["access_token"] != token else [])
        return candidatos, str(p["instagram_business_account"]["id"]), "persona", f"página «{p.get('name', '?')}»"
    tipo, cod, msg = clasificar(d, token)
    if tipo in ("token", "cupo"):
        raise MetaError(explicar(tipo, cod, msg), tipo)
    # ¿token de página? (me/accounts no existe para una página)
    st2, d2, _ = llamar("me", {"fields": "id,name,instagram_business_account"}, token, abrir)
    if st2 == 200 and isinstance(d2.get("instagram_business_account"), dict):
        return [token], str(d2["instagram_business_account"]["id"]), "página", f"página «{d2.get('name', '?')}»"
    if ig_id_env and st2 == 200:
        return [token], ig_id_env, "desconocido", ""
    tipo2, cod2, msg2 = clasificar(d2, token)
    t = tipo2 if tipo2 != "otro" else tipo
    raise MetaError(explicar(t, cod2 or cod, msg2 or msg), t)


def ficha_token(token: str, abrir=urllib.request.urlopen) -> dict:
    """Datos del token según Meta (`debug_token`; un token se puede mirar con él mismo): tipo, validez, caducidad y permisos. {} si no se pudo leer."""
    st, d, _ = llamar("debug_token", {"input_token": token}, token, abrir)
    info = d.get("data") if st == 200 and isinstance(d.get("data"), dict) else {}
    if not info:
        return {}
    exp = info.get("expires_at") or 0
    dias = None if not exp else (datetime.fromtimestamp(exp, timezone.utc) - datetime.now(timezone.utc)).days
    return {"tipo": str(info.get("type") or ""), "valido": bool(info.get("is_valid")), "expira": exp or None, "dias": dias, "permisos": list(info.get("scopes") or [])}


def _fecha_ok(ts, corte: datetime) -> bool:
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(str(ts), fmt).astimezone(timezone.utc) >= corte
        except ValueError:
            continue
    return True   # fecha rara: se deja pasar, el resto de la tubería la descarta si no la entiende


def filas_de_media(usuario: str, seguidores, medios: list[dict], corte: datetime) -> list[dict]:
    """Publicaciones de Business Discovery → filas con los campos de Windsor (los hijos de un carrusel salen como filas IMAGE aparte)."""
    out = []
    for m in medios or []:
        ts = m.get("timestamp")
        if not m.get("id") or not _fecha_ok(ts, corte):
            continue
        hijos = [h for h in ((m.get("children") or {}).get("data") or []) if h.get("media_url") and str(h.get("media_type") or "IMAGE").upper() == "IMAGE"]
        url = m.get("media_url") or (hijos[0]["media_url"] if hijos else None)
        base = {"account_name": usuario, "media_timestamp": ts, "media_permalink": m.get("permalink"), "media_like_count": m.get("like_count"),
                "media_comments_count": m.get("comments_count"), "profile_followers_count": seguidores, "media_caption": m.get("caption")}
        out.append({**base, "media_id": str(m["id"]), "media_type": m.get("media_type"), "media_url": url, "media_thumbnail_url": m.get("thumbnail_url")})
        if str(m.get("media_type")).upper() == "CAROUSEL_ALBUM":
            for h in hijos[:HIJOS_MAX]:
                if h["media_url"] != url:
                    out.append({**base, "media_id": str(h["id"]), "media_type": "IMAGE", "media_url": h["media_url"], "media_thumbnail_url": None})
    return out


def _campo_inexistente(cuerpo: dict) -> str | None:
    """Si Meta dice «Tried accessing nonexisting field (X)» devuelve el campo X (se quita de la consulta y se repite)."""
    import re
    msg = str(((cuerpo or {}).get("error") or {}).get("message") or "")
    m = re.search(r"nonexisting field \(([^)]+)\)", msg)
    return m.group(1) if m else None


def leer_cuenta(ig_id: str, usuario: str, token: str, corte: datetime, abrir=urllib.request.urlopen) -> tuple[list[dict], dict]:
    """Una cuenta por Business Discovery (hasta PAGINAS_MAX páginas). Devuelve (filas, info) con info = {'seguidores', 'cabeceras'} o lanza MetaError si el fallo es de token/permisos/cupo.
    Si la cuenta no se puede leer (no profesional, privada, inexistente) devuelve ([], {'motivo': ...}). Si Meta rechaza algún campo opcional, se quita y se repite la petición."""
    filas, seguidores, cursor, cab = [], None, None, {}
    for pagina in range(PAGINAS_MAX):
        for _intento in range(len(CAMPOS_PRESCINDIBLES) + 2):
            media = f"media.limit({MEDIA_POR_PAGINA})" + (f".after({cursor})" if cursor else "") + "{" + ",".join(_CAMPOS_VIVOS) + "}"
            campos = f"business_discovery.username({usuario}){{username,followers_count,media_count,{media}}}"
            st, d, cab = llamar(ig_id, {"fields": campos}, token, abrir)
            malo = _campo_inexistente(d) if st != 200 else None
            hijo = next((c for c in _CAMPOS_VIVOS if malo and (c == malo or c.startswith(malo + "{"))), None)
            if hijo and hijo in CAMPOS_PRESCINDIBLES:
                _CAMPOS_VIVOS.remove(hijo)   # p. ej. «thumbnail_url» o «children» no existen en Business Discovery: se sigue sin ellos
                continue
            break
        if st != 200 or "business_discovery" not in d:
            tipo, cod, msg = clasificar(d, token)
            if tipo in ("token", "permisos", "cupo"):
                raise MetaError(explicar(tipo, cod, msg), tipo)
            if tipo == "no_disponible":
                return filas, {"motivo": "no es una cuenta profesional pública (o no existe)", "seguidores": seguidores, "cabeceras": cab}
            if st >= 500 or st == 0:
                time.sleep(3)
                st, d, cab = llamar(ig_id, {"fields": campos}, token, abrir)
                if not (st == 200 and "business_discovery" in d):
                    return filas, {"motivo": f"Meta falló (HTTP {st})", "seguidores": seguidores, "cabeceras": cab}
            else:
                return filas, {"motivo": f"error de Meta {cod}: {msg}"[:160], "seguidores": seguidores, "cabeceras": cab}
        bd = d["business_discovery"]
        seguidores = bd.get("followers_count", seguidores)
        medios = (bd.get("media") or {}).get("data") or []
        filas += filas_de_media(str(bd.get("username") or usuario).lower(), seguidores, medios, corte)
        cursor = (((bd.get("media") or {}).get("paging") or {}).get("cursors") or {}).get("after")
        mas = len(medios) >= MEDIA_POR_PAGINA and cursor and _fecha_ok(medios[-1].get("timestamp"), corte)
        if not mas:
            break
    return filas, {"seguidores": seguidores, "cabeceras": cab}


def meta_filas(handles: list[str], token: str, ig_id_env: str = "", dias: int = 35, abrir=urllib.request.urlopen, pausa: float = 0.4,
               ahora: datetime | None = None) -> tuple[dict[str, list[dict]], dict]:
    """Todas las cuentas por Business Discovery. Devuelve ({usuario en minúsculas: [filas]}, resumen) con resumen =
    {'tipo_token', 'detalle', 'leidas', 'sin_lectura': {usuario: motivo}, 'avisos': [..], 'ig_id', 'dias_restantes'}. Un fallo de token/permisos al principio lanza MetaError;
    si el cupo se agota a mitad, se devuelve lo leído y se avisa. Si el token de persona no vale para Business Discovery pero el de su página sí, se cambia solo."""
    token = (token or "").strip()
    if not token:
        raise MetaError("falta el secreto META_IG_TOKEN", "token")
    ahora = ahora or datetime.now(timezone.utc)
    corte = ahora - timedelta(days=dias)
    _CAMPOS_VIVOS[:] = CAMPOS_MEDIA   # cada ejecución empieza pidiendo todos los campos
    candidatos, ig_id, tipo_tok, detalle = preparar(token, (ig_id_env or "").strip(), abrir)
    ficha = ficha_token(token, abrir)
    por, sin_lectura, avisos = collections.defaultdict(list), {}, []
    usado = 0   # índice del token que funciona

    def leer(h):
        nonlocal usado
        while True:
            try:
                return leer_cuenta(ig_id, h, candidatos[usado], corte, abrir)
            except MetaError as e:
                if e.tipo in ("permisos", "token") and usado + 1 < len(candidatos):
                    usado += 1
                    avisos.append("el token de persona no sirvió para Business Discovery; se usa el de la página")
                    continue
                raise

    for i, h in enumerate(handles):
        try:
            filas, info = leer(h)
        except MetaError as e:
            if i == 0:
                raise
            avisos.append(str(e))
            for resto in handles[i:]:
                sin_lectura.setdefault(resto, "no se llegó a pedir (Meta cortó las peticiones)")
            break
        if filas:
            por[h].extend(filas)
        else:
            sin_lectura[h] = info.get("motivo") or "sin publicaciones en la ventana"
        time.sleep(pausa)
    return dict(por), {"tipo_token": tipo_tok, "detalle": detalle, "leidas": len(por), "sin_lectura": sin_lectura, "avisos": sorted(set(avisos)), "ig_id": ig_id,
                       "dias_restantes": ficha.get("dias"), "ficha": ficha, "token_usado": "persona" if usado == 0 and tipo_tok == "persona" else "página"}
