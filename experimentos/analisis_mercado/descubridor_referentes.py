#!/usr/bin/env python3
"""
Descubridor de referentes (2026-10-13): ¿de dónde sacar fotos de mercado para los estilos que aún no tienen referentes (clásico, old money, lujo, bohemio, convencional)?

Por cada estilo × mercado (ES / US) propone fuentes candidatas SIN claves de API y mide lo que rendiría cada una:
  reddit    comunidades: búsqueda de comunidades y de publicaciones por RSS (de ahí salen nombres nuevos) + «top» del mes de cada una (semillas, descubiertas y las de la Biblioteca)
  noticias  prensa: Bing Noticias y Google Noticias por RSS, por estilo («"old money" moda») y por referente (persona o marca, por nombre)
  x         cuentas de X que ya se conocen (tendencia_fuentes.json, cuentas_confiables.json, biblioteca.json) vía FxTwitter
Por candidato: publicaciones con imagen en los últimos 30 días y, en una muestra de ≤ 8 fotos, cuántas tienen persona con ropa visible (`--validar`):
  puerta   la puerta CLIP «persona con ropa» de tendencia_prenda.py (ligera; es la que filtra cada semana las fotos nuevas)
  prendas  además, el detector de prendas de tendencia_prenda.py (analizar_outfit.py + `visible`/`valida`): «persona con ropa visible» de verdad (≈ 10-20 s por foto en CPU: va a GitHub Actions)
  nada     solo cuenta publicaciones
Salida: tendencia_datos/candidatos_referentes.json (estilo, mercado, tipo, valor, evidencia, 3 URLs de ejemplo, y `fuente` = la entrada lista para pegar en tendencia_fuentes.json si Víctor dice ✓)
y tendencia_datos/candidatos_referentes_resumen.md (corto, para contestar ✓/✕ desde el móvil).

Si un servicio contesta 403/429 (o no hay red hacia él) se anota en `red` y se sigue con el resto; no se rodea. Las fotos de la muestra se bajan a una carpeta temporal y se BORRAN al terminar:
no salen a ningún servicio ni se guardan en el repositorio (solo direcciones públicas de las publicaciones).
Lo que NO mide: si la comunidad o la prensa encaja de verdad con el estilo (solo que tiene fotos de personas con ropa); eso lo juzga Víctor con los ejemplos.

Uso:  python3 descubridor_referentes.py [medir] [--estilos old_money,lujo] [--mercados ES,US] [--fuentes reddit,noticias,x] [--validar puerta|prendas|nada] [--muestra 8]
      python3 descubridor_referentes.py resumen        # vuelve a imprimir el resumen del último resultado
Pruebas sin red: test_descubridor_referentes.py
"""
import argparse
import base64
import collections
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import numpy as np
from PIL import Image

AQUI = Path(__file__).resolve().parent
SALIDA_DIR = Path(os.environ.get("TENDENCIA_DATOS") or AQUI / "tendencia_datos")
ESC = Path(os.environ.get("DESCUBRIDOR_TMP") or Path(tempfile.gettempdir()) / f"descubridor_{os.getpid()}")   # fotos y cachés de esta pasada: se borran al terminar
os.environ["TENDENCIA_DATOS"] = str(ESC)   # tendencia_prenda y mercado escriben su caché aquí, nunca en los datos de la semana
sys.path.insert(0, str(AQUI))
import mercado as m  # noqa: E402
import tendencia_prenda as tp  # noqa: E402  (la validación «persona con ropa visible» es la suya)

SEMILLAS, FUENTES = AQUI / "descubridor_semillas.json", AQUI / "tendencia_fuentes.json"
CUENTAS_CONFIABLES = Path(os.environ.get("MERCADO_CUENTAS_X") or m.CUENTAS_X)
VENTANA = 30              # días
MUESTRA = 8               # fotos por candidato
MERCADOS = ("ES", "US")
UMBRAL_REPETIDA = tp.UMBRAL_DUP
PAUSA_REDDIT, PAUSA_WEB, PAUSA_FOTO = 3.0, 1.5, 0.4   # segundos entre peticiones al mismo servicio (los tests las ponen a 0)
BASE = {"reddit": "https://www.reddit.com", "bing": "https://www.bing.com/news/search", "google": "https://news.google.com/rss/search"}   # los tests apuntan a un servidor local
MKT_BING = {"ES": "es-ES", "US": "en-US"}
GOOGLE = {"ES": ("es", "ES", "ES:es"), "US": ("en-US", "US", "US:en")}
CTX_MODA = ["moda", "look", "estilo", "outfit", "tendencia", "fashion", "style", "trend", "vestido", "traje", "prenda", "ropa", "collection", "coleccion", "alfombra roja", "red carpet", "estilismo"]
GENERICAS = {"all", "popular", "pics", "funny", "memes", "askreddit", "aww", "videos", "gaming", "worldnews", "todayilearned", "mildlyinteresting", "interestingasfuck", "movies", "music"}
ORIGEN_PRIORIDAD = {"en_uso": 0, "biblioteca": 1, "cuentas_confiables": 2, "propuesta": 3, "descubierto": 4}
SERVICIO = {"reddit": "reddit", "x": "fxtwitter", "noticias": "bing"}
AHORA = datetime.now(timezone.utc)
norm = tp.norm


# ---------------------------------------------------------------- red: pausas, contadores y servicios bloqueados
class Red:
    """Qué contesta cada servicio: «ok», códigos HTTP («403», «429»…) o «red». Con 3 fallos seguidos y ningún acierto (o 6 seguidos), el servicio se da por bloqueado y no se le vuelve a pedir nada."""

    def __init__(self):
        self.cuenta = collections.defaultdict(collections.Counter)
        self.seguidos = collections.Counter()
        self.bloqueado = {}

    def cerrado(self, srv: str) -> bool:
        return srv in self.bloqueado

    def acierto(self, srv: str) -> None:
        self.cuenta[srv]["ok"] += 1
        self.seguidos[srv] = 0

    def fallo(self, srv: str, codigo: int) -> None:
        self.cuenta[srv][str(codigo) if codigo else "red"] += 1
        if codigo == 404:   # el servicio funciona: es esa dirección la que no existe
            self.seguidos[srv] = 0
            return
        self.seguidos[srv] += 1
        if srv not in self.bloqueado and ((self.seguidos[srv] >= 3 and not self.cuenta[srv]["ok"]) or self.seguidos[srv] >= 6):
            self.bloqueado[srv] = f"{self.seguidos[srv]} peticiones seguidas sin respuesta útil (último: {codigo or 'sin conexión'})"
            print(f"  ⚠ {srv}: {self.bloqueado[srv]}; lo anoto y sigo sin él", flush=True)

    def informe(self) -> dict:
        return {s: {"respuestas": dict(c), "bloqueado": self.bloqueado.get(s)} for s, c in sorted(self.cuenta.items())}


RED = Red()


def pedir(srv: str, url: str, pausa: float | None = None, aceptar: str = "*/*"):
    """GET educado con pausa. Devuelve (código, texto): (200, texto) si va bien; (código, None) si el servicio contesta mal (0 = sin conexión); (None, None) si ya estaba bloqueado.
    Ante un 429 espera lo que pida el servicio (máx. 90 s) y reintenta una vez."""
    if RED.cerrado(srv):
        return None, None
    codigo, retry = 0, None
    for intento in (0, 1):
        time.sleep(PAUSA_WEB if pausa is None else pausa)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": m.UA, "Accept": aceptar}), timeout=30) as r:
                texto = r.read(6_000_000).decode("utf-8", "ignore")
                quedan, reset = r.headers.get("x-ratelimit-remaining"), r.headers.get("x-ratelimit-reset")
            RED.acierto(srv)
            try:
                if quedan is not None and float(quedan) < 2:
                    time.sleep(min(120.0, float(reset or 30)) + 2)   # Reddit avisa de que se agotan las peticiones de esta ventana
            except ValueError:
                pass
            return 200, texto
        except urllib.error.HTTPError as e:
            codigo, retry = e.code, e.headers.get("retry-after")
        except Exception as e:  # noqa: BLE001 -- el 403 del proxy de salida llega como URLError «Tunnel connection failed: 403»
            hallado = re.search(r"\b([45]\d\d)\b", str(e))
            codigo, retry = (int(hallado.group(1)) if hallado else 0), None
        if codigo == 429 and intento == 0:
            RED.cuenta[srv]["429"] += 1
            try:
                espera = min(90.0, float(retry or 30))
            except ValueError:
                espera = 30.0
            print(f"  {srv}: 429, espero {espera:.0f} s", flush=True)
            time.sleep(espera)
            continue
        break
    RED.fallo(srv, codigo)
    return codigo, None


def fecha_iso(s: str | None):
    try:
        d = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def en_ventana(fecha) -> bool:
    return fecha is None or fecha >= AHORA - timedelta(days=VENTANA)


def repartida(lista: list, n: int) -> list:
    """n elementos repartidos por toda la lista (no solo los primeros, que serían los más votados o los más recientes)."""
    if len(lista) <= n:
        return list(lista)
    return [lista[round(i * (len(lista) - 1) / (n - 1))] for i in range(n)] if n > 1 else lista[:1]


def _loc(etiqueta: str) -> str:
    return etiqueta.rsplit("}", 1)[-1]


# ---------------------------------------------------------------- Reddit
RE_IMG_REDDIT = re.compile(r"https://i\.redd\.it/[A-Za-z0-9_\-]+\.(?:jpe?g|png|webp)", re.I)
RE_SUB_ENLACE = re.compile(r"reddit\.com/r/([A-Za-z0-9_]{2,21})(?:[/?#]|$)", re.I)


def parsear_atom(xml: str) -> list[dict]:
    """Entradas de un feed Atom de Reddit: título, enlace, fecha, comunidad e imagen directa (solo i.redd.it, como la cosecha semanal; galerías y vídeos no cuentan)."""
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    for en in (e for e in raiz.iter() if _loc(e.tag) == "entry"):
        d = {"titulo": "", "enlace": "", "fecha": None, "sub": None, "imagen": None}
        contenido, cat = "", None
        for h in en:
            t = _loc(h.tag)
            if t == "title":
                d["titulo"] = html.unescape((h.text or "").strip())
            elif t == "link" and not d["enlace"]:
                d["enlace"] = h.attrib.get("href", "")
            elif t in ("published", "updated") and (t == "published" or d["fecha"] is None):
                d["fecha"] = fecha_iso(h.text)
            elif t == "category":
                cat = h.attrib.get("term")
            elif t == "content":
                contenido = h.text or ""
        hallado = RE_SUB_ENLACE.search(d["enlace"])
        d["sub"] = hallado.group(1) if hallado else cat
        img = RE_IMG_REDDIT.search(contenido) or RE_IMG_REDDIT.search(html.unescape(contenido))
        d["imagen"] = img.group(0) if img else None
        out.append(d)
    return out


def sub_valida(nombre: str | None) -> bool:
    return bool(nombre) and re.fullmatch(r"[A-Za-z0-9_]{2,21}", nombre) is not None and not nombre.lower().startswith("u_") and nombre.lower() not in GENERICAS


def descubrir_subs(consultas: list[str]) -> collections.Counter:
    """Puntos por comunidad: +3 si sale entre las 5 primeras de la búsqueda de comunidades, +1 por cada publicación con imagen que sale en la búsqueda de publicaciones del mes."""
    puntos = collections.Counter()
    for q in consultas:
        _, xml = pedir("reddit", f"{BASE['reddit']}/subreddits/search.rss?" + urllib.parse.urlencode({"q": q, "limit": 15}), PAUSA_REDDIT, "application/atom+xml")
        for e in (parsear_atom(xml) if xml else [])[:5]:
            if sub_valida(e["sub"]):
                puntos[e["sub"]] += 3
        _, xml = pedir("reddit", f"{BASE['reddit']}/search.rss?" + urllib.parse.urlencode({"q": q, "sort": "top", "t": "month", "limit": 100}), PAUSA_REDDIT, "application/atom+xml")
        for e in (parsear_atom(xml) if xml else []):
            if e["imagen"] and sub_valida(e["sub"]):
                puntos[e["sub"]] += 1
    return puntos


# ---------------------------------------------------------------- medidas: una por comunidad / cuenta / consulta de prensa (varios candidatos pueden compartirla)
MEDIDAS: dict[str, dict] = {}


def nueva_medida(tipo: str, valor: str, **extra) -> dict:
    return {"tipo": tipo, "valor": valor, "estado": "sin_datos", "http": None, "datos": {}, "fotos": [], "enlaces": [], **extra}


def estado_por_http(codigo, texto) -> str:
    if texto is not None:
        return "medido"
    return "bloqueado" if codigo in (None, 0) else "no_disponible"   # 404 o 403 de una dirección concreta; el bloqueo de todo el servicio se decide al final


def bajar_muestra(med: dict, candidatas: list[dict], n: int) -> None:
    """Descarga hasta n fotos (repartidas) de las candidatas [{url, enlace}] a la carpeta temporal. Las que fallan se cuentan y se sustituyen por otras."""
    (ESC / "fotos").mkdir(parents=True, exist_ok=True)
    fallidas = 0
    for cand in repartida(candidatas, min(len(candidatas), n + 4)):
        if len(med["fotos"]) >= n:
            break
        cid = "d_" + hashlib.sha1(cand["url"].encode()).hexdigest()[:10]
        ruta = ESC / "fotos" / f"{cid}.jpg"
        try:
            if ruta.exists() or m.descargar_imagen(cand["url"], ruta, min_lado=cand.get("min_lado", 300), referer=cand.get("referer"), proporcion=cand.get("proporcion")):
                med["fotos"].append({"id": cid, "ruta": ruta, "enlace": cand["enlace"]})
                time.sleep(PAUSA_FOTO)
                continue
        except Exception:  # noqa: BLE001 -- la foto pudo desaparecer o el sitio bloquea la descarga
            pass
        fallidas += 1
    med["datos"]["descargas_fallidas"] = med["datos"].get("descargas_fallidas", 0) + fallidas


def medir_reddit(sub: str, n: int) -> str:
    clave = f"reddit:{sub.lower()}"
    if clave in MEDIDAS:
        return clave
    med = MEDIDAS[clave] = nueva_medida("reddit", sub)
    cod, xml = pedir("reddit", f"{BASE['reddit']}/r/{sub}/top/.rss?" + urllib.parse.urlencode({"t": "month", "limit": 100}), PAUSA_REDDIT, "application/atom+xml")
    med["http"], med["estado"] = cod, estado_por_http(cod, xml)
    if xml is None:
        return clave
    entradas = parsear_atom(xml)
    dentro = [e for e in entradas if en_ventana(e["fecha"])]
    con_img = [e for e in dentro if e["imagen"]]
    idiomas = collections.Counter(m.detectar_idioma(e["titulo"]) for e in dentro)
    es, en = idiomas["es"], idiomas["en"]
    mercado = "ES" if es > 0 and es >= 0.6 * (es + en) else ("US" if en > 0 and en >= 0.6 * (es + en) else None)
    med["estado"] = "medido" if entradas else "sin_datos"
    med["datos"] = {"publicaciones_30d": len(dentro), "con_imagen_30d": len(con_img), "tope_100": len(entradas) >= 100, "titulos_es": es, "titulos_en": en, "mercado_medido": mercado}
    med["enlaces"] = [e["enlace"] for e in repartida(con_img, 3)]
    if con_img:
        bajar_muestra(med, [{"url": e["imagen"], "enlace": e["enlace"]} for e in con_img], n)
    return clave


# ---------------------------------------------------------------- prensa (Bing y Google Noticias por RSS)
def decodificar_google(link: str) -> str | None:
    """Dirección real de un artículo de Google Noticias: en los identificadores antiguos va dentro (base64); los nuevos hay que pedirlos a Google y aquí no se hace (None)."""
    hallado = re.search(r"/articles/([A-Za-z0-9_\-]+)", link)
    if not hallado:
        return link or None
    try:
        crudo = base64.urlsafe_b64decode(hallado.group(1) + "=" * (-len(hallado.group(1)) % 4))
    except Exception:  # noqa: BLE001
        return None
    url = re.search(rb"https?://[^\s\x00-\x1f\"<>\x80-\xff]+", crudo)
    return url.group(0).decode() if url else None


def clave_titular(titulo: str, medio: str = "") -> str:
    t = re.sub(r"\s+-\s+" + re.escape(medio) + r"\s*$", "", titulo) if medio else titulo
    return norm(re.sub(r"\W+", " ", t)).strip()[:70]


def parsear_noticias(xml: str, motor: str) -> list[dict] | None:
    """Noticias de un RSS de Bing o de Google: titular, resumen, enlace real si se conoce, fecha, medio y si el RSS trae imagen (solo Bing). None si no es un RSS."""
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError:
        return None
    out = []
    for it in (e for e in raiz.iter() if _loc(e.tag) == "item"):
        h, atr = {}, {}
        for e in it:
            h[_loc(e.tag).lower()] = e.text or ""
            atr[_loc(e.tag).lower()] = e.attrib
        link = h.get("link", "")
        medio = html.unescape(h.get("source", "")).strip()
        titulo = html.unescape(h.get("title", "")).strip()
        try:
            fecha = parsedate_to_datetime(h.get("pubdate", ""))
            fecha = fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)
        except Exception:  # noqa: BLE001
            fecha = None
        if motor == "bing":
            url, imagen = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url", [link])[0], bool(h.get("image", "").strip())
        else:
            url, imagen = decodificar_google(link), None   # el RSS de Google no trae imagen
            medio = medio or atr.get("source", {}).get("url", "")
        out.append({"titulo": titulo, "desc": html.unescape(re.sub(r"<[^>]+>", " ", h.get("description", ""))), "url": url, "fecha": fecha, "medio": medio,
                    "imagen_rss": imagen, "clave": clave_titular(titulo, medio), "motores": {motor}})
    return out


def consulta_noticias(motor: str, q: str, mercado: str):
    """(noticias, código HTTP). Bing contesta a ratos con algo que no es XML (sobre todo desde GitHub): una segunda vez con más pausa."""
    if motor == "bing":
        url = f"{BASE['bing']}?" + urllib.parse.urlencode({"q": q, "format": "rss", "mkt": MKT_BING[mercado]})
    else:
        hl, gl, ceid = GOOGLE[mercado]
        url = f"{BASE['google']}?" + urllib.parse.urlencode({"q": q + f" when:{VENTANA}d", "hl": hl, "gl": gl, "ceid": ceid})
    cod = None
    for intento in (0, 1):
        cod, xml = pedir(motor, url, PAUSA_WEB + 3 * intento, "application/rss+xml,text/xml")
        if xml is None:
            return [], cod
        items = parsear_noticias(xml, motor)
        if items is not None:
            return items, 200
    return [], 200


def medir_noticias(d: dict, n: int) -> str:
    """d: {mercado, consultas, rx (nombre/frase sin tildes, o None), contexto (palabras), excluir}. Cuenta las noticias de 30 días que cumplen y baja una foto de cada artículo de la muestra."""
    clave = "noticias:" + hashlib.sha1(json.dumps([d["mercado"], d["consultas"], d["rx"], d["contexto"], d["excluir"]], sort_keys=True).encode()).hexdigest()[:12]
    if clave in MEDIDAS:
        return clave
    med = MEDIDAS[clave] = nueva_medida("noticias", d["consultas"][0])
    unidas, codigos, ok = {}, {}, set()
    for motor in ("bing", "google"):
        for q in d["consultas"]:
            items, cod = consulta_noticias(motor, q, d["mercado"])
            if cod == 200:
                ok.add(motor)
            if motor not in ok:
                codigos[motor] = cod
            for it in items:
                t = norm(it["titulo"] + " " + it["desc"])
                if it["fecha"] is None or not en_ventana(it["fecha"]):   # como la cosecha semanal: sin fecha no vale
                    continue
                if (d["rx"] and not re.search(d["rx"], t)) or not any(c in t for c in d["contexto"]) or any(x in t for x in d["excluir"]):
                    continue
                previo = unidas.get(it["clave"])
                if previo:   # la misma noticia en los dos motores: se queda con el enlace real y la marca de imagen de Bing
                    previo["motores"] |= it["motores"]
                    previo["url"] = previo["url"] or it["url"]
                    previo["imagen_rss"] = bool(previo["imagen_rss"] or it["imagen_rss"])
                else:
                    unidas[it["clave"]] = it
    med["http"] = {mo: (200 if mo in ok else c) for mo, c in codigos.items()} | {mo: 200 for mo in ok}
    med["estado"] = ("medido" if unidas else "sin_datos") if ok else ("bloqueado" if all(c in (None, 0, 403, 429) for c in codigos.values()) else "no_disponible")
    if not ok:
        return clave
    noticias = sorted(unidas.values(), key=lambda it: it["fecha"] or AHORA, reverse=True)
    medios = {norm(it["medio"]) for it in noticias if it["medio"]}
    con_url = [it for it in noticias if it["url"]]
    med["datos"] = {"publicaciones_30d": len(noticias), "con_imagen_rss": sum(bool(it["imagen_rss"]) for it in noticias), "medios_distintos": len(medios),
                    "solo_bing": sum(it["motores"] == {"bing"} for it in noticias), "solo_google": sum(it["motores"] == {"google"} for it in noticias),
                    "sin_enlace_real": len(noticias) - len(con_url), "motores_ok": sorted(ok)}
    med["enlaces"] = [it["url"] for it in repartida(con_url, 3)]
    articulos = repartida(con_url, min(len(con_url), 2 * n))
    probados = 0
    for it in articulos:
        if len(med["fotos"]) >= n:
            break
        probados += 1
        try:
            final, texto = m.pedir_html(it["url"])
            _, grupos = m.imagenes_de_pagina(final, texto)
        except Exception:  # noqa: BLE001 -- muro de pago, bloqueo o página rota
            time.sleep(1)
            continue
        for g in grupos[:8]:   # una foto por artículo: la primera grande (≥ 400 px, proporción de foto) como en la cosecha semanal
            antes = len(med["fotos"])
            for u in g:
                bajar_muestra(med, [{"url": u, "enlace": it["url"], "referer": final, "min_lado": 400, "proporcion": (0.4, 2.5)}], antes + 1)
                if len(med["fotos"]) > antes:
                    break
            if len(med["fotos"]) > antes:
                break
        time.sleep(PAUSA_WEB)
    con_foto = len(med["fotos"])
    med["datos"].update({"articulos_probados": probados, "articulos_con_foto": con_foto})
    if probados:   # estimación: el RSS no dice cuántos artículos traen una foto utilizable; se extrapola de los que se probaron
        med["datos"]["con_imagen_30d"] = round(len(noticias) * con_foto / probados)
        med["datos"]["con_imagen_30d_estimada"] = True
    else:
        med["datos"]["con_imagen_30d"] = 0
    return clave


# ---------------------------------------------------------------- cuentas de X (FxTwitter)
def medir_x(handle: str, n: int) -> str:
    clave = f"x:{handle.lower()}"
    if clave in MEDIDAS:
        return clave
    med = MEDIDAS[clave] = nueva_medida("x", handle)
    cod, texto = None, None
    for espera in (0, 4, 8):   # FxTwitter contesta 404 a veces la primera vez que se pide una cuenta que sí existe
        cod, texto = pedir("fxtwitter", f"{m.FXTWITTER}/2/profile/{handle}/statuses", max(espera, PAUSA_WEB), "application/json")
        if cod != 404:
            break
    med["http"], med["estado"] = cod, estado_por_http(cod, texto)
    if texto is None:
        return clave
    try:
        posts = [p for p in (json.loads(texto).get("results") or []) if not p.get("reposted_by")]
    except ValueError:
        med["estado"] = "error"
        return clave
    ahora_s = time.time()
    edad = lambda p: (ahora_s - p["created_timestamp"]) / 86400 if p.get("created_timestamp") else None   # noqa: E731
    recientes = [p for p in posts if edad(p) is not None and edad(p) <= VENTANA]
    con_foto = [p for p in recientes if (p.get("media") or {}).get("photos")]
    todas_con_foto = [edad(p) for p in posts if (p.get("media") or {}).get("photos") and edad(p) is not None]
    idiomas = collections.Counter(p.get("lang") for p in recientes or posts)
    es, en = idiomas["es"], idiomas["en"]
    mercado = "ES" if es > 0 and es >= 0.6 * (es + en) else ("US" if en > 0 and en >= 0.6 * (es + en) else None)
    med["estado"] = "medido" if posts else "sin_datos"
    med["datos"] = {"publicaciones_30d": len(recientes), "con_imagen_30d": len(con_foto), "fotos_30d": sum(len(p["media"]["photos"]) for p in con_foto),
                    "posts_en_el_lote": len(posts), "tope_lote": bool(posts) and max((edad(p) or 0) for p in posts) < VENTANA,   # el lote (~20 posts) no llega a 30 días atrás: la cifra es un mínimo
                    "ultima_foto_hace_dias": round(min(todas_con_foto)) if todas_con_foto else None, "seguidores": ((posts[0].get("author") or {}).get("followers") if posts else None),
                    "titulos_es": es, "titulos_en": en, "mercado_medido": mercado}
    med["enlaces"] = [p.get("url") or f"https://x.com/{handle}/status/{p.get('id')}" for p in repartida(con_foto, 3)]
    fotos = [{"url": ft["url"], "enlace": p.get("url") or f"https://x.com/{handle}/status/{p.get('id')}"} for p in con_foto for ft in p["media"]["photos"] if ft.get("url")]
    if fotos:
        bajar_muestra(med, fotos, n)
    return clave


# ---------------------------------------------------------------- validación: persona con ropa visible (la de tendencia_prenda.py)
def puntuar_puerta(rutas: list[Path]):
    """Puerta CLIP «persona con ropa» (la misma de tendencia_prenda.filtrar_nuevas): puntuación y embedding de cada foto."""
    X = m.embeber_imagenes(rutas, "descubridor")
    return m.puntuacion_foto_real(X), X


def detectar_ropa(rutas: list[Path], lote: int = 40) -> dict:
    """{ruta: True/False/None} con el detector de prendas de tendencia_prenda.py: True si alguna prenda se ve y no es el «torso geométrico» (`tp.valida`). None si el lote falló."""
    sys.path.insert(0, str(tp.DET))
    import prueba_recortes_clip as pc  # noqa: E402
    res_final = {}
    for i in range(0, len(rutas), lote):
        trozo = rutas[i:i + lote]
        carpeta, salida = ESC / "lote", ESC / "lote.json"
        shutil.rmtree(carpeta, ignore_errors=True)
        carpeta.mkdir(parents=True)
        for r in trozo:
            shutil.copy(r, carpeta / r.name)
        t0 = time.time()
        try:
            subprocess.run([sys.executable, "-u", "analizar_outfit.py", "--carpeta", str(carpeta), "--salida-json", str(salida), "--cache", str(ESC / "od_cache.json")],
                           cwd=tp.DET, check=True, capture_output=True, text=True)
            res = json.loads(salida.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  ✖ detector de prendas, lote {i // lote + 1}: {type(e).__name__}: {(getattr(e, 'stderr', '') or str(e))[-300:]}", flush=True)
            res_final.update({r: None for r in trozo})
            continue
        for r in trozo:
            rr = res.get(r.stem) or res.get(r.name)
            if rr is None:
                res_final[r] = None
                continue
            W, H = Image.open(r).convert("RGB").size
            ok = False
            for pr in (rr["personas"][0]["prendas"] if rr["personas"] else []):
                x1, y1, x2, y2 = pr["caja"]
                if pr["categoria"] not in pc.GRUPOS or pr["deteccion"].startswith("torso") or min(x2 - x1, y2 - y1) < 40:   # el mismo filtro que tendencia_prenda.cmd_analizar
                    continue
                if tp.valida({"visible": tp.visible(pr["caja"], pr["categoria"], W, H), "deteccion": pr["deteccion"]}):
                    ok = True
                    break
            res_final[r] = ok
        print(f"  detector: lote {i // lote + 1}/{-(-len(rutas) // lote)}, {len(trozo)} fotos en {time.time() - t0:.0f} s", flush=True)
    shutil.rmtree(ESC / "lote", ignore_errors=True)
    return res_final


def validar(modo: str, max_detector: int) -> str:
    """Rellena `gate` (puerta CLIP), `repetida` y, con modo «prendas», `ropa` en cada foto de la muestra. Devuelve el modo realmente aplicado."""
    todas = [f for med in MEDIDAS.values() for f in med["fotos"]]
    if modo == "nada" or not todas:
        return "nada"
    try:
        g, X = puntuar_puerta([f["ruta"] for f in todas])
    except Exception as e:  # noqa: BLE001 -- sin torch / sin los pesos de CLIP
        print(f"✖ No pude cargar la puerta CLIP ({type(e).__name__}: {str(e)[:160]}): solo cuento publicaciones.", flush=True)
        return "no_disponible"
    for f, gi, xi in zip(todas, g, X):
        f["gate"], f["_x"] = float(gi), xi
    for med in MEDIDAS.values():
        vistos = []
        for f in med["fotos"]:
            f["repetida"] = any(float(f["_x"] @ v) >= UMBRAL_REPETIDA for v in vistos)
            if not f["repetida"]:
                vistos.append(f["_x"])
    print(f"Puerta CLIP: {sum(f['gate'] >= m.UMBRAL_PUERTA for f in todas)} de {len(todas)} fotos con persona y ropa", flush=True)
    if modo != "prendas":
        return "puerta"
    pasan = [f for f in todas if f["gate"] >= m.UMBRAL_PUERTA and not f["repetida"]]
    print(f"Detector de prendas sobre {min(len(pasan), max_detector)} de {len(pasan)} fotos que pasan la puerta", flush=True)
    try:
        res = detectar_ropa([f["ruta"] for f in pasan[:max_detector]])
    except Exception as e:  # noqa: BLE001
        print(f"✖ detector de prendas no disponible ({type(e).__name__}: {str(e)[:160]}): me quedo con la puerta.", flush=True)
        return "puerta"
    for f in pasan[:max_detector]:
        f["ropa"] = res.get(f["ruta"])
    return "prendas"


# ---------------------------------------------------------------- candidatos
def cargar_semillas() -> dict:
    return json.loads(SEMILLAS.read_text(encoding="utf-8"))["estilos"]


def candidatos_de_ficheros(estilos: list[str]) -> list[dict]:
    """Lo que Víctor (o el asistente, marcado) ya tiene en el repositorio: fuentes en uso (control), cuentas de X confiables, y las cuentas y comunidades de la Biblioteca."""
    c = []
    for s in json.loads(FUENTES.read_text(encoding="utf-8"))["fuentes"]:   # en uso: sirven de control para comparar con lo nuevo
        c.append({"estilo": s["estilo"], "mercado": s["mercado"], "tipo": s["tipo"], "valor": s["referente"] if s["tipo"] == "noticias" else s["valor"],
                  "ambito": "referente" if s["tipo"] == "noticias" else ("comunidad" if s["tipo"] == "reddit" else "cuenta"), "origen": "en_uso", "fuente": s,
                  "medida_def": medida_def_de_fuente(s) if s["tipo"] == "noticias" else None})
    flujo = tp.ESTILOS_FLUJO
    if CUENTAS_CONFIABLES.exists():
        for est_app, cuentas in json.loads(CUENTAS_CONFIABLES.read_text(encoding="utf-8")).items():
            if est_app in flujo and isinstance(cuentas, list):
                for h in cuentas:
                    c.append({"estilo": flujo[est_app], "mercado": "auto", "tipo": "x", "valor": h, "ambito": "cuenta", "origen": "cuentas_confiables", "fuente": None})
    for s in json.loads((AQUI / "biblioteca.json").read_text(encoding="utf-8")).get("fuentes", []):
        if s.get("estilo") in flujo and s.get("tipo") in ("x", "reddit_sub"):
            tipo = "x" if s["tipo"] == "x" else "reddit"
            c.append({"estilo": flujo[s["estilo"]], "mercado": s.get("mercado") or "auto", "tipo": tipo, "valor": s["valor"], "ambito": "cuenta" if tipo == "x" else "comunidad",
                      "origen": "biblioteca" + (" (asistente)" if s.get("origen") == "asistente" else ""), "fuente": None})
    return [x for x in c if x["estilo"] in estilos]


def definicion_prensa(mercado: str, consultas: list[str], rx: str | None, extra_ctx=(), excluir=()) -> dict:
    return {"mercado": mercado, "consultas": consultas, "rx": rx, "contexto": CTX_MODA + [norm(x) for x in extra_ctx], "excluir": [norm(x) for x in excluir]}


def candidatos_de_semillas(sem: dict, estilos: list[str], mercados: list[str]) -> list[dict]:
    c = []
    for estilo in estilos:
        for mercado in mercados:
            celda = sem.get(estilo, {}).get(mercado, {})
            for sub in celda.get("reddit_subs", []):
                c.append({"estilo": estilo, "mercado": mercado, "tipo": "reddit", "valor": sub, "ambito": "comunidad", "origen": "propuesta", "fuente": None})
            for q in celda.get("prensa", []):
                frases = [norm(f) for f in re.findall(r'"([^"]+)"', q)]
                rx = "|".join(re.escape(f) for f in frases) or None
                fuente = {"referente": f"prensa: {q}", "estilo": estilo, "mercado": mercado, "tipo": "noticias", "valor": q, "consultas": [q], "nombre": rx or ".", "contexto_extra": CTX_MODA}
                c.append({"estilo": estilo, "mercado": mercado, "tipo": "noticias", "valor": q, "ambito": "estilo", "origen": "propuesta", "fuente": fuente, "medida_def": definicion_prensa(mercado, [q], rx)})
            for r in celda.get("referentes", []):
                fuente = {"referente": r["nombre"], "estilo": estilo, "mercado": mercado, "tipo": "noticias", "valor": r["consultas"][0], "consultas": r["consultas"], "nombre": r["rx"], "contexto_extra": CTX_MODA,
                          **({"excluir": r["excluir"]} if r.get("excluir") else {}), **({"archivo": True} if r.get("archivo") else {})}
                c.append({"estilo": estilo, "mercado": mercado, "tipo": "noticias", "valor": r["nombre"], "ambito": "referente", "origen": "propuesta", "fuente": fuente,
                          "medida_def": definicion_prensa(mercado, r["consultas"], r["rx"], excluir=r.get("excluir", []))})
    return c


def medida_def_de_fuente(s: dict) -> dict:
    """Una fuente de prensa de tendencia_fuentes.json → definición de medida (misma lógica que tendencia_prenda.cosechar_noticias)."""
    return {"mercado": s["mercado"], "consultas": s.get("consultas") or [s["valor"]], "rx": s["nombre"],
            "contexto": tp.CONTEXTO.get(s.get("contexto"), []) + [norm(c) for c in s.get("contexto_extra", [])], "excluir": [norm(x) for x in s.get("excluir", [])]}


def unir(candidatos: list[dict]) -> list[dict]:
    """Un candidato por (estilo, tipo, valor, mercado): si viene de varios sitios gana el origen más fiable (en uso > Biblioteca > confiables > propuesta > descubierto)."""
    por_clave = {}
    for c in sorted(candidatos, key=lambda c: ORIGEN_PRIORIDAD.get(c["origen"].split(" ")[0], 9)):
        por_clave.setdefault((c["estilo"], c["tipo"], str(c["valor"]).lower(), c["mercado"] if c["tipo"] == "noticias" else "-"), c)
    return list(por_clave.values())


def evidencia_de(med: dict, modo: str) -> dict:
    """Números de un candidato: lo medido por tipo + lo de la validación de la muestra + una estimación de fotos útiles al mes."""
    d = dict(med["datos"])
    fotos = med["fotos"]
    d["muestra"] = len(fotos)
    if modo in ("puerta", "prendas") and fotos and "gate" in fotos[0]:
        distintas = [f for f in fotos if not f["repetida"]]
        d["repetidas"] = len(fotos) - len(distintas)
        d["con_persona"] = sum(f["gate"] >= m.UMBRAL_PUERTA for f in distintas)
        d["validacion"] = "puerta"
        buenas = d["con_persona"]
        pasan = [f for f in distintas if f["gate"] >= m.UMBRAL_PUERTA]
        if modo == "prendas" and (not pasan or any(f.get("ropa") is not None for f in pasan)):   # si el detector falló en todas, no se enseña un 0 engañoso
            d["validacion"] = "prendas"
            d["con_ropa_visible"] = sum(f.get("ropa") is True for f in distintas)
            d["sin_detectar"] = sum(f.get("ropa") is None for f in pasan)
            buenas = d["con_ropa_visible"]
        d["tasa_util"] = round(buenas / len(fotos), 2)
        d["fotos_utiles_est"] = round(d.get("con_imagen_30d", 0) * d["tasa_util"], 1)
    else:
        d["validacion"] = "ninguna" if modo != "no_disponible" else "no_disponible"
    return d


def ejemplos_de(med: dict) -> list[str]:
    """3 direcciones públicas de publicaciones: primero las de fotos que pasaron la validación; si no se bajó ninguna foto, las de las publicaciones medidas."""
    def valor(f):
        return (f.get("ropa") is True, f.get("gate", 0) >= m.UMBRAL_PUERTA if "gate" in f else False, not f.get("repetida", False))
    out = []
    for f in sorted(med["fotos"], key=valor, reverse=True):
        if f["enlace"] and f["enlace"] not in out:
            out.append(f["enlace"])
    for e in med["enlaces"]:
        if e and e not in out:
            out.append(e)
    return out[:3]


def texto_evidencia(ev: dict, estado: str) -> str:
    if estado != "medido":
        return {"bloqueado": "sin medir: el servicio no contesta desde aquí", "no_disponible": "no disponible (404/403: no existe o es privada)", "sin_datos": "sin publicaciones en 30 días", "error": "error al leer"}.get(estado, estado)
    est = "~" if ev.get("con_imagen_30d_estimada") else ""
    t = f"{est}{ev.get('con_imagen_30d', 0)} pub. con imagen/30 d"
    if "con_ropa_visible" in ev:
        t += f" · {ev['con_ropa_visible']}/{ev['muestra']} con ropa visible"
    elif "con_persona" in ev:
        t += f" · {ev['con_persona']}/{ev['muestra']} con persona"
    elif ev.get("muestra") == 0 and ev.get("con_imagen_30d"):
        t += " · sin fotos bajadas"
    if ev.get("tope_100") or ev.get("tope_lote"):
        t += " (mínimo)"
    return t


# ---------------------------------------------------------------- orquestación
def montar_candidatos(args, sem) -> list[dict]:
    estilos = args.estilos or list(sem)
    cands = candidatos_de_ficheros(estilos) + candidatos_de_semillas(sem, estilos, args.mercados)
    return [c for c in unir(cands) if c["tipo"] in args.fuentes and c["mercado"] in (*args.mercados, "auto")]


def fase_reddit(cands: list[dict], sem: dict, args) -> None:
    """Descubre comunidades nuevas por búsqueda (por estilo × mercado) y mide el «top» del mes de todas las comunidades candidatas."""
    for estilo in args.estilos:
        for mercado in args.mercados:
            qs = sem.get(estilo, {}).get(mercado, {}).get("reddit_busquedas", [])
            if not qs or RED.cerrado("reddit"):
                continue
            puntos = descubrir_subs(qs)
            ya = {c["valor"].lower() for c in cands if c["tipo"] == "reddit" and c["estilo"] == estilo}
            elegidas = [(s, p) for s, p in puntos.most_common() if p >= 2 and s.lower() not in ya][:args.max_subs]
            print(f"  Reddit · {estilo} {mercado}: {len(puntos)} comunidades vistas, {len(elegidas)} candidatas nuevas", flush=True)
            cands += [{"estilo": estilo, "mercado": mercado, "tipo": "reddit", "valor": s, "ambito": "comunidad", "origen": "descubierto", "fuente": None, "puntos_busqueda": p} for s, p in elegidas]
    todas = sorted({c["valor"] for c in cands if c["tipo"] == "reddit"}, key=str.lower)
    for k, sub in enumerate(todas, 1):
        clave = medir_reddit(sub, args.muestra)
        for c in cands:
            if c["tipo"] == "reddit" and c["valor"].lower() == sub.lower():
                c["medida"] = clave
        med = MEDIDAS[clave]
        print(f"  [{k}/{len(todas)}] r/{sub}: {med['estado']} · {med['datos'].get('con_imagen_30d', '-')} con imagen · {len(med['fotos'])} fotos bajadas", flush=True)


def fase_noticias(cands: list[dict], args) -> None:
    pend = [c for c in cands if c["tipo"] == "noticias"]
    for k, c in enumerate(pend, 1):
        c["medida"] = medir_noticias(c["medida_def"], args.muestra)
        med = MEDIDAS[c["medida"]]
        print(f"  [{k}/{len(pend)}] prensa {c['estilo']} {c['mercado']} · {c['valor'][:40]}: {med['estado']} · {med['datos'].get('publicaciones_30d', '-')} noticias · {len(med['fotos'])} fotos bajadas", flush=True)


def fase_x(cands: list[dict], args) -> None:
    pend = [c for c in cands if c["tipo"] == "x"]
    for k, c in enumerate(pend, 1):
        c["medida"] = medir_x(c["valor"], args.muestra)
        med = MEDIDAS[c["medida"]]
        print(f"  [{k}/{len(pend)}] @{c['valor']}: {med['estado']} · {med['datos'].get('con_imagen_30d', '-')} posts con foto en 30 d · {len(med['fotos'])} fotos bajadas", flush=True)


def cerrar_candidato(c: dict, modo: str) -> dict:
    med = MEDIDAS[c["medida"]]
    estado = med["estado"]
    if estado in ("no_disponible", "error", "bloqueado") and RED.cerrado(SERVICIO[c["tipo"]]) and med["http"] in (None, 0, 403, 429):
        estado = "bloqueado"
    ev = evidencia_de(med, modo) if estado == "medido" else {}
    mercado = c["mercado"]
    if mercado == "auto" or c["tipo"] in ("reddit", "x") and c["origen"] != "en_uso":
        mercado = ev.get("mercado_medido") or (mercado if mercado != "auto" else "?")   # el mercado de una comunidad o cuenta es el de su idioma, no el de la búsqueda que la encontró
    fuente = dict(c["fuente"]) if c.get("fuente") else {"referente": ("r/" + c["valor"]) if c["tipo"] == "reddit" else c["valor"], "estilo": c["estilo"], "mercado": mercado, "tipo": c["tipo"], "valor": c["valor"]}
    fuente["mercado"] = mercado
    return {"id": hashlib.sha1(f"{c['estilo']}|{mercado}|{c['tipo']}|{c['valor']}".encode()).hexdigest()[:8], "estilo": c["estilo"], "mercado": mercado, "tipo": c["tipo"], "valor": c["valor"], "ambito": c["ambito"],
            "origen": c["origen"], "en_uso": c["origen"] == "en_uso", "estado": estado, "evidencia": ev, "evidencia_texto": texto_evidencia(ev, estado), "ejemplos": ejemplos_de(med) if estado == "medido" else [], "fuente": fuente}


def clave_orden(c: dict):
    ev = c["evidencia"]
    return (c["estado"] != "medido", -(ev.get("fotos_utiles_est") if ev.get("fotos_utiles_est") is not None else ev.get("con_imagen_30d", 0) / 10), c["valor"].lower())


def resumen_texto(datos: dict, por_celda: int = 3) -> str:
    """Corto, para leer en el móvil y contestar «1✓ 2✕»."""
    cands = datos["candidatos"]
    red = datos["red"]
    caidos = [f"{s} ✕" for s, r in red.items() if r["bloqueado"]]
    sanos = [f"{s} ✓" for s, r in red.items() if not r["bloqueado"]]
    lineas = [f"Candidatos a referente · {VENTANA} días · {datos['generado'][:10]}", "Red: " + (" · ".join(sanos + caidos) or "sin peticiones"),
              {"prendas": "Muestra: persona con ropa VISIBLE (detector de prendas)", "puerta": "Muestra: persona con ropa (puerta CLIP; sin detector)", "nada": "Sin validar fotos", "no_disponible": "Sin validar fotos (no cargó CLIP)"}.get(datos["validacion"], ""), ""]
    nombres = {"old_money": "Old money", "clasico": "Clásico", "lujo": "Lujo ostentoso", "bohemio": "Bohemio", "convencional": "Convencional", "urbano": "Urbano (control)", "geek": "Geek (control)"}
    n = 0
    for estilo in nombres:
        for mercado in ("ES", "US"):
            celda = sorted([c for c in cands if c["estilo"] == estilo and c["mercado"] == mercado], key=clave_orden)
            if not celda:
                continue
            lineas.append(f"▸ {nombres[estilo]} · {mercado}")
            medidos = [c for c in celda if c["estado"] == "medido"]
            for c in medidos[:por_celda]:
                n += 1
                c["numero"] = n
                nombre = {"reddit": f"r/{c['valor']}", "x": f"@{c['valor']}", "noticias": ("«" + c["valor"] + "»") if c["ambito"] == "referente" else c["valor"]}[c["tipo"]]
                lineas.append(f" {n} {'prensa ' if c['tipo'] == 'noticias' else ''}{nombre}{' (ya en uso)' if c['en_uso'] else ''} — {c['evidencia_texto']}")
            resto = len(celda) - min(len(medidos), por_celda)
            if resto:
                lineas.append(f"   (+{resto} sin datos suficientes o sin medir)")
    lineas += ["", "Contesta p. ej.: 1✓ 2✕ 5✓ (lo ✓ pasa a tendencia_fuentes.json)."]
    return "\n".join(lineas)


def cmd_medir(args) -> int:
    ESC.mkdir(parents=True, exist_ok=True)
    sem = cargar_semillas()
    estilos = args.estilos or list(sem)
    if set(estilos) - set(sem):
        raise SystemExit(f"Estilo desconocido: {sorted(set(estilos) - set(sem))}. Disponibles: {', '.join(sem)}")
    args.estilos = estilos
    cands = montar_candidatos(args, sem)
    por_tipo = collections.Counter(c["tipo"] for c in cands)
    print(f"{len(cands)} candidatos de partida (reddit {por_tipo['reddit']}, noticias {por_tipo['noticias']}, x {por_tipo['x']}); muestra ≤ {args.muestra}, validación «{args.validar}»", flush=True)
    try:
        if "reddit" in args.fuentes:
            print("Reddit:", flush=True)
            fase_reddit(cands, sem, args)
        if "noticias" in args.fuentes:
            print("Prensa (Bing y Google Noticias):", flush=True)
            fase_noticias(cands, args)
        if "x" in args.fuentes:
            print("Cuentas de X (FxTwitter):", flush=True)
            fase_x(cands, args)
        modo = validar(args.validar, args.max_detector)
        cerrados = [cerrar_candidato(c, modo) for c in cands]
        cerrados = [c for c in cerrados if c["mercado"] in args.mercados or c["mercado"] == "?"]
        cerrados.sort(key=lambda c: (c["estilo"], c["mercado"], *clave_orden(c)))
        datos = {"version": 1, "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ventana_dias": VENTANA, "muestra_max": args.muestra, "validacion": modo,
                 "red": RED.informe(), "nota": "La muestra se baja a una carpeta temporal y se borra: no se guardan fotos, solo direcciones públicas. `fuente` es la entrada para tendencia_fuentes.json si se acepta.",
                 "candidatos": cerrados}
        resumen = resumen_texto(datos)
        SALIDA = Path(args.salida)
        SALIDA.parent.mkdir(parents=True, exist_ok=True)
        m.guardar_json(SALIDA, datos)   # ya con el número que el resumen puso a cada candidato
        SALIDA.with_name(SALIDA.stem + "_resumen.md").write_text(resumen + "\n", encoding="utf-8")
    finally:
        if not os.environ.get("DESCUBRIDOR_CONSERVAR"):
            shutil.rmtree(ESC, ignore_errors=True)   # las fotos de la muestra no se quedan en ningún sitio
    print("\n" + resumen)
    return 0


def cmd_resumen(args) -> int:
    ruta = Path(args.salida)
    if not ruta.exists():
        print(f"No hay {ruta}: ejecuta primero `medir`.")
        return 1
    print(resumen_texto(json.loads(ruta.read_text(encoding="utf-8"))))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", nargs="?", default="medir", choices=["medir", "resumen"])
    ap.add_argument("--estilos", type=lambda s: [x for x in s.split(",") if x], help="old_money,clasico,lujo,bohemio,convencional,urbano,geek (por defecto, todos)")
    ap.add_argument("--mercados", type=lambda s: [x for x in s.split(",") if x], default=list(MERCADOS))
    ap.add_argument("--fuentes", type=lambda s: [x for x in s.split(",") if x], default=["reddit", "noticias", "x"], help="reddit,noticias,x")
    ap.add_argument("--validar", choices=["puerta", "prendas", "nada"], default="puerta")
    ap.add_argument("--muestra", type=int, default=MUESTRA)
    ap.add_argument("--max-subs", type=int, default=4, help="comunidades nuevas que se miden por estilo × mercado")
    ap.add_argument("--max-detector", type=int, default=400, help="tope de fotos para el detector de prendas (≈ 10-20 s cada una en CPU)")
    ap.add_argument("--salida", default=str(SALIDA_DIR / "candidatos_referentes.json"))
    args = ap.parse_args(argv)
    return cmd_resumen(args) if args.accion == "resumen" else cmd_medir(args)


if __name__ == "__main__":
    sys.exit(main())
