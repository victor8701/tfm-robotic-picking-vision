#!/usr/bin/env python3
"""
Analizar mercado (prototipo) -- «¿qué está de moda ahora mismo?» a partir de fotos reales.

FORMA NORMAL DE USO (sin terminal): doble clic en «Analizar mercado» (el .bat del escritorio de Windows, copia de
Iniciar_Mercado.bat). Arranca esta app y abre el navegador en http://localhost:8766, con pestañas y botones:
Inicio («Analizar mercado»), Clasificar, Informe, Biblioteca (lo que TÚ le enseñas: descripción de cada estilo, fotos,
cuentas y enlaces) y Ajustes (reentrenar).

BIBLIOTECA (Víctor, 2026-10-03): un sitio donde metes descripciones, fotos, cuentas y enlaces por estilo, y sirve a las dos partes:
  · al CLASIFICADOR: tus fotos son ejemplos de entrenamiento y tus frases (en inglés) forman un prototipo de texto CLIP que se
    mezcla con el de las fotos (el peso λ se elige por validación cruzada y se informa);
  · al BUSCADOR: las comunidades/usuarios de Reddit se descargan; los enlaces (tuits, páginas web, imágenes) se convierten en
    candidatas «propuestas» con tu estilo para confirmarlas con Enter; las cuentas de X se copian a ingesta_x/cuentas_confiables.json
    (las usa la búsqueda híbrida de X); Instagram/TikTok se guardan (no se pueden leer solos: abres el perfil y pegas enlaces).

OBJETIVO FINAL (Víctor, 2026-10-03): que el operario pulse un botón «Analizar mercado» y vea qué está de moda ahora
mismo (Estado_arte.md §6, HMI de tendencias). Esto es el primer tramo de ese botón:
    cosechar (fuentes) → clasificar (modelo de 7 estilos) → informe,
y las etiquetas que das al clasificar reentrenan el modelo.

Los mismos pasos existen por línea de comandos (para automatizar / depurar):
    python3 mercado.py app | entrenar | cosechar --reddit a,b | cosechar --urls f.txt | informe | reentrenar
    python3 mercado.py analizar --cosechar --reddit streetwear,fashion      # el «botón» entero

Fuentes: cada una es un adaptador que devuelve candidatas con los mismos campos (id, fuente, comunidad, titulo,
imagen_url, permalink, fecha, rank). Hoy: Reddit (RSS, sin login) y enlaces pegados. El botón final necesitará
fuentes fiables y legales (API oficial de Reddit, YouTube vía viral_clips…); X no lo es (bloqueos).

PRIVACIDAD: las fotos son de personas reales. Se guardan SOLO en cache/ (fuera de git); al repositorio solo van
código, el modelo (7×512 números) y las etiquetas (id, estilo, enlace). No publiques las imágenes.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import math
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin, urlparse

import numpy as np
from PIL import Image, ImageOps

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[1]
POC = REPO / "experimentos" / "clip_trend_matching"
HERR_X = REPO / "experimentos" / "ingesta_x" / "herramientas"
CLASIF = REPO / "experimentos/ingesta_x/panel/data/clasificaciones.json"
FOTOS = REPO / "experimentos/ingesta_x/panel/static/fotos"
DATOS = Path(os.environ.get("MERCADO_DATOS") or AQUI)   # carpeta de datos; solo se cambia en las pruebas
CACHE = DATOS / "cache"
IMG = CACHE / "img"
BIB_IMG = CACHE / "biblioteca"   # fotos que subes a la Biblioteca, una carpeta por estilo (fuera de git: son personas reales)
HUELLAS = CACHE / "huellas.json"  # huella de cada foto de entrenamiento, para avisarte de las repetidas al subirlas
HISTORIAL = DATOS / "informes_historial.json"   # cuota de cada estilo en cada informe (para decir «sube / baja»)
CANDIDATOS = DATOS / "candidatos.json"
ETIQUETAS = DATOS / "etiquetas_mercado.json"
BIBLIOTECA = DATOS / "biblioteca.json"   # descripciones, frases, cuentas y enlaces (texto: va a git)
MODELO = DATOS / "modelo_estilos.npz"
INFORME_JSON, INFORME_HTML = DATOS / "informe_mercado.json", DATOS / "informe_mercado.html"
CUENTAS_X = Path(os.environ.get("MERCADO_CUENTAS_X") or REPO / "experimentos/ingesta_x/cuentas_confiables.json")
UA = "tfm-uc3m-research/0.1 (academic prototype)"   # sin datos personales de nadie
CANDADO = threading.Lock()

# ---------------------------------------------------------------- taxonomía (Estado_arte.md §3.4.2)
ESTILOS = ["old_money", "lujo_ostentoso", "clasico_tradicional", "urbano", "bohemio", "alternativo_geek", "convencional"]
NOMBRE = {"old_money": "Old Money", "lujo_ostentoso": "Lujo ostentoso", "clasico_tradicional": "Clásico-tradicional",
          "urbano": "Urbano", "bohemio": "Bohemio", "alternativo_geek": "Alternativo-geek", "convencional": "Convencional"}
RASGOS = {
    "old_money": "Elegancia clásica y discreta, sin logos visibles",
    "lujo_ostentoso": "Marca de lujo muy visible, estética «futbolista»",
    "clasico_tradicional": "Silueta clásica, tonos tierra, prenda atemporal",
    "urbano": "Trap/rap español, de lo crudo a lo pulido",
    "bohemio": "Telas fluidas, tonos tierra, capas",
    "alternativo_geek": "Fandom: gaming, anime, cómic",
    "convencional": "Tendencia dominante sin rasgo propio",
}
# Mapeo orientativo a los 6 Grupos de estilo del ERP (para el Trend JSON de §6.4)
GRUPOS_ERP = {"old_money": ["De vestir"], "lujo_ostentoso": ["De vestir", "Fiesta/Noche"],
              "clasico_tradicional": ["Casual", "De vestir"], "urbano": ["Streetwear"],
              "bohemio": ["Casual", "Playa/Resort"], "alternativo_geek": ["Casual"], "convencional": ["Casual"]}
# Solo las que dieron imágenes directas en la cosecha real (femalefashionadvice, techwearclothing y OldMoney dieron 0 y cada una cuesta ~25 s de espera)
SUBS_POR_DEFECTO = "streetwear,malefashionadvice,Mensfashion,WomensStreetwear,fashion"

# Puerta «es una foto real de una persona con ropa» (CLIP zero-shot; medida contra las decisiones de Víctor:
# umbral 0,5 conserva el 94 % de las útiles y descarta el 63 % de la basura en la búsqueda por texto de X).
POS = ["a photo of a person wearing a stylish outfit", "a street style fashion photograph of a person",
       "a fashion editorial photo of a model wearing clothes", "a photo of clothing worn by a real person"]
NEG = ["an anime or manga illustration", "a cartoon drawing or comic panel", "a digital art character design",
       "a 3D render or video game screenshot", "a screenshot of a TV show or news broadcast",
       "a poster, flyer or infographic with lots of text", "a meme with text", "a chart, map or diagram",
       "a landscape or nature photo", "a photo of an object or gadget with no person",
       "a product advertisement collage", "a close-up portrait headshot with no visible clothes"]
UMBRAL_PUERTA = 0.35   # por debajo, el informe ignora la foto (no es un outfit)


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _escribir_json(ruta: Path, obj) -> None:
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)


def guardar_json(ruta: Path, obj) -> None:
    with CANDADO:
        _escribir_json(ruta, obj)


def leer_json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def modificar_json(ruta: Path, cambio):
    """Lee, aplica `cambio(obj)` y escribe, todo seguido. La app y una tarea aparte escriben a veces los mismos ficheros:
    releer justo antes de escribir evita pisar lo que acaba de añadir el otro (la ventana de carrera queda en milisegundos)."""
    with CANDADO:
        obj = leer_json(ruta)
        res = cambio(obj)
        _escribir_json(ruta, obj)
        return res


# ---------------------------------------------------------------- CLIP y embeddings (reutiliza el POC)
_CLIP: dict = {}
_TXT: dict = {}


def clip():
    if not _CLIP:
        import torch
        torch.set_grad_enabled(False)
        torch.set_num_threads(os.cpu_count() or 4)
        sys.path.insert(0, str(POC))
        from clip_matching_poc import cargar_modelo  # mismo CLIP, mismo tokenizador que el POC y el Experimento B
        _CLIP["m"], _CLIP["p"], _CLIP["t"] = cargar_modelo()
    return _CLIP["m"], _CLIP["p"], _CLIP["t"]


def embeber_imagenes(rutas: list[Path], nombre_cache: str) -> np.ndarray:
    """Embeddings CLIP normalizados (n, 512), con caché por (ruta, tamaño de fichero)."""
    import torch
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"emb_{nombre_cache}.npz"
    claves = [f"{r}|{r.stat().st_size}" for r in rutas]
    previo = {}
    if f.exists():
        try:
            z = np.load(f, allow_pickle=False)
            previo = dict(zip(z["claves"].tolist(), z["v"]))
        except Exception:  # noqa: BLE001 -- caché a medio escribir por otro proceso: se recalcula
            previo = {}
    faltan = [i for i, k in enumerate(claves) if k not in previo]
    if faltan:
        model, prep, _ = clip()
        print(f"  calculando embeddings de {len(faltan)} imágenes ({nombre_cache})...", flush=True)
        for i in range(0, len(faltan), 32):
            lote = faltan[i:i + 32]
            t = torch.stack([prep(Image.open(rutas[j]).convert("RGB")) for j in lote])
            v = model.encode_image(t)
            v = (v / v.norm(dim=-1, keepdim=True)).numpy()
            for j, vec in zip(lote, v):
                previo[claves[j]] = vec
        tmp = f.with_name(f.stem + ".tmp.npz")   # escritura atómica: la app y una tarea aparte pueden usar la misma caché
        np.savez(tmp, claves=np.array(list(previo.keys())), v=np.array(list(previo.values())))
        tmp.replace(f)
    return np.array([previo[k] for k in claves])


def puntuacion_foto_real(X: np.ndarray) -> np.ndarray:
    """Probabilidad de que la imagen sea «una foto real de una persona con ropa» (CLIP zero-shot)."""
    if "T" not in _TXT:
        m, _, tok = clip()
        t = m.encode_text(tok(POS + NEG))
        _TXT["T"] = (t / t.norm(dim=-1, keepdim=True)).numpy()
    s = 100.0 * X @ _TXT["T"].T
    s -= s.max(1, keepdims=True)
    p = np.exp(s)
    p /= p.sum(1, keepdims=True)
    return p[:, :len(POS)].sum(1)


# ---------------------------------------------------------------- Biblioteca (lo que TÚ le enseñas)
# Textos de partida: quedan en biblioteca.json, desde la app los editas tú y el código solo rellena lo que falte.
# `frases` van en inglés porque CLIP (OpenAI) entiende mucho mejor el inglés; se promedian en un «prototipo» de texto por estilo.
DESCRIPCION_DEFECTO = {
    "old_money": "Lujo discreto y clásico: americana o chaleco, camisa de corte náutico, punto fino, tonos sobrios y ningún logo ni detalle vistoso (Anexo A de la memoria).",
    "lujo_ostentoso": "El contraste de Old Money («New Money»): marca de lujo muy visible (Gucci, Philipp Plein…), logos grandes, joyas, colores y estampados llamativos. "
                      "Referencia de Víctor: estética «futbolista» (Dani Alves).",
    "clasico_tradicional": "El pijo/cayetano español que viste un poco «paleto» (definición de Víctor, 2026-10-03): chalecos, náuticos, calcetines feos y vistosos con "
                           "pantalones tobilleros, etc. Prendas icónicas citadas en prensa: chaqueta Barbour y manoletinas. Es un estilo muy de España.",
    "urbano": "Escena trap/rap española, de lo más crudo a lo más pulido (bronceado, gimnasio, marca deportiva o lifestyle de gama alta, estética de reality y redes).",
    "bohemio": "Telas fluidas, tonos tierra, capas y accesorios artesanales.",
    "alternativo_geek": "Ropa ligada al fandom y la cultura pop (gaming, anime, cómic): manda el motivo o estampado, no la silueta.",
    "convencional": "Sigue la tendencia dominante del momento sin rasgo diferenciador propio.",
}
FRASES_DEFECTO = {
    "old_money": ["a quiet luxury outfit with a tailored navy blazer, a fine knit sweater and no visible logos",
                  "old money style: a cashmere sweater over a white collared shirt, beige chinos and leather loafers",
                  "an elegant understated classic look in neutral colors made of high quality fabrics",
                  "a refined outfit with a camel coat, tailored trousers and a silk scarf"],
    "lujo_ostentoso": ["a person wearing flashy designer clothes with big visible luxury brand logos",
                       "footballer style outfit with a Gucci or Louis Vuitton monogram, a gold chain and a designer belt",
                       "ostentatious luxury fashion with bold prints, an expensive watch, jewelry and designer sneakers",
                       "new money look: Philipp Plein, Versace baroque print, Balenciaga or Dolce & Gabbana"],
    "clasico_tradicional": ["a man wearing a quilted vest over a polo shirt, ankle-length chino trousers, bright colorful socks and boat shoes",
                            "a spanish preppy conservative look: a navy blazer with gold buttons, pink or red trousers and loafers with colorful socks",
                            "a waxed Barbour jacket with a quilted gilet, corduroy trousers and earth tone colors",
                            "cropped trousers that show loud patterned socks with nautical boat shoes",
                            "a traditional upper class outfit with a polo shirt, a sweater tied over the shoulders and boat shoes",
                            "a classic women's look with a Barbour jacket, ballet flats, a headband and pearl earrings"],
    "urbano": ["spanish trap and rap street style: an oversized hoodie or tracksuit, chunky sneakers, a gold chain and a cap",
               "urban streetwear with premium sportswear brands, a puffer jacket and a cross-body bag",
               "a young man with a fade haircut and a tan wearing a branded tracksuit and white sneakers"],
    "bohemio": ["a bohemian outfit with flowy fabrics, earth tones and layered handmade jewelry",
                "hippie style with a crochet top, fringe, an embroidered blouse and sandals",
                "a boho layered look with a long cardigan, a scarf, a floppy hat and a leather bag"],
    "alternativo_geek": ["a geek outfit with a graphic t-shirt of an anime, video game or comic character",
                         "fandom clothing with printed characters, a gaming hoodie and a backpack",
                         "nerd fashion with glasses and pop culture merchandise t-shirts"],
    "convencional": ["an everyday normcore outfit with a plain t-shirt, jeans and white sneakers",
                     "a basic casual look that follows mainstream trends with no distinctive style",
                     "simple jeans and a sweatshirt in neutral colors"],
}
REFERENTES_DEFECTO = {"urbano": "Cruz Cafuné · Hoke · Israel B · Shoda Monkas · bycalitos · La Isla de las Tentaciones",
                      "alternativo_geek": "orslok", "lujo_ostentoso": "Dani Alves (estética «futbolista»)"}
USAR_TEXTO_DEFECTO = {"clasico_tradicional", "lujo_ostentoso"}   # los dos estilos con pocas fotos y mal recall (2026-10-03); el resto, solo fotos
MAX_FRASES, MAX_LARGO_FRASE = 12, 300

FXTWITTER = "https://api.fxtwitter.com"   # servicio público de terceros (FixTweet/FxEmbed): X no deja listar cuentas, ellos sí; sin clave ni coste
# tipo de fuente → (nombre que ve el usuario, ¿la app la descarga sola?)
TIPOS = {"reddit_sub": ("Comunidad de Reddit", True), "reddit_user": ("Usuario de Reddit", True),
         "tuit": ("Tuit con fotos", True), "pagina": ("Página web", True), "imagen": ("Imagen suelta", True),
         "x": ("Cuenta de X", True), "instagram": ("Instagram", False), "tiktok": ("TikTok", False),
         "red": ("Publicación de red social", False), "rss": ("Feed RSS de un medio", True)}
ESTILO_MERCADO = "mercado"   # «estilo» de las fuentes que no entrenan: alimentan el informe «qué está de moda» de un mercado
MERCADOS = {"ES": "España", "US": "EEUU", "UK": "Reino Unido", "FR": "Francia", "IT": "Italia", "LATAM": "Latinoamérica", "OTRO": "Otro"}
MERCADO_REDDIT = "US"        # las comunidades de Reddit que se descargan por defecto son de habla inglesa
DIAS_MAX_MERCADO = 60        # de una fuente de mercado no se bajan fotos de posts más viejos (el informe no las usa)
# Idiomas que cuentan para cada mercado: una cuenta de «España» que publica en inglés (p. ej. una marca global) no es contenido del mercado español
MERCADO_IDIOMAS = {"ES": {"es"}, "US": {"en"}, "UK": {"en"}, "FR": {"fr"}, "IT": {"it"}, "LATAM": {"es"}}
_PALABRAS = {"es": set("el la los las de del y en que un una para con por su sus se al más lo como es este esta así tu tus muy ya sin sobre entre desde también".split()),
             "en": set("the of and to in for with is on your you that this are new at by from our it its be as".split())}
RE_REDDIT = re.compile(r"(?:https?://(?:[a-z]+\.)?reddit\.com)?/?(r|u|user)/([A-Za-z0-9_\-]{2,30})(?:/(?:top|new|hot|submitted)?/?)?(?:[?#].*)?", re.I)
RE_X_TUIT = re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/status/(\d+)", re.I)
RE_X_PERFIL = re.compile(r"https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/?(?:[?#].*)?", re.I)
RESERVADAS_X = {"home", "search", "explore", "i", "hashtag", "intent", "share", "messages", "notifications", "settings", "compose", "login"}
RE_IG_PERFIL = re.compile(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]{1,30})/?(?:[?#].*)?", re.I)
RESERVADAS_IG = {"p", "reel", "reels", "explore", "stories", "accounts", "tv", "direct"}
RE_TT_PERFIL = re.compile(r"https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]{2,24})/?(?:[?#].*)?", re.I)
RE_IMAGEN = re.compile(r"\.(jpe?g|png|webp)(\?.*)?$", re.I)
RE_FEED = re.compile(r"(/(feed|rss|atom)(/|\.xml|\.rss)?$)|(\.(xml|rss)$)|(/(feed|rss)/)", re.I)


def leer_biblioteca() -> dict:
    """biblioteca.json completado con los textos de partida (por si falta el fichero o alguna clave)."""
    b = leer_json(BIBLIOTECA) or {}
    salida = {"version": 1, "estilos": {}, "fuentes": [{**s, "estado": s.get("estado") or {}} for s in b.get("fuentes", [])
                                                        if s.get("tipo") in TIPOS and (s.get("estilo") in ESTILOS or s.get("estilo") == ESTILO_MERCADO)
                                                        and s.get("id") and s.get("valor")]}
    for e in ESTILOS:
        d = (b.get("estilos") or {}).get(e, {})
        salida["estilos"][e] = {"descripcion": d.get("descripcion", DESCRIPCION_DEFECTO[e]),
                                "frases": list(d.get("frases", FRASES_DEFECTO[e])),
                                "referentes": d.get("referentes", REFERENTES_DEFECTO.get(e, "")),
                                "usar_texto": bool(d.get("usar_texto", e in USAR_TEXTO_DEFECTO))}
    return salida


def modificar_biblioteca(cambio):
    with CANDADO:
        b = leer_biblioteca()
        res = cambio(b)
        _escribir_json(BIBLIOTECA, b)
        return res


def guardar_textos(estilo: str, descripcion, frases, referentes, usar_texto=None) -> int:
    """Guarda lo que escribes de un estilo. `frases`: lista o texto con una por línea. Devuelve cuántas frases quedan."""
    if estilo not in ESTILOS:
        raise ValueError("estilo no válido")
    if isinstance(frases, str):
        frases = frases.splitlines()
    lim = [re.sub(r"\s+", " ", str(f)).strip()[:MAX_LARGO_FRASE] for f in frases]
    lim = [f for f in lim if f][:MAX_FRASES]

    def cambio(b):
        b["estilos"][estilo] = {"descripcion": str(descripcion or "").strip()[:1200], "frases": lim, "referentes": str(referentes or "").strip()[:300],
                                "usar_texto": b["estilos"][estilo]["usar_texto"] if usar_texto is None else bool(usar_texto)}
    modificar_biblioteca(cambio)
    return len(lim)


def fotos_biblioteca(estilo: str | None = None) -> list[Path]:
    carpetas = [BIB_IMG / estilo] if estilo else [BIB_IMG / e for e in ESTILOS]
    return sorted(p for c in carpetas if c.is_dir() for p in c.glob("*.jpg"))


UMBRAL_HUELLA = 16   # de 256 bits: por debajo, es la misma foto (recomprimida, reescalada o con un recorte mínimo)


def huella(im: Image.Image) -> int:
    """dHash de 256 bits: casi idéntico para la misma foto aunque cambie de tamaño o de compresión."""
    px = np.asarray(im.convert("L").resize((17, 16), Image.LANCZOS), dtype=np.int16)
    return int("".join("1" if b else "0" for b in (px[:, 1:] > px[:, :-1]).ravel()), 2)


def huella_de(ruta: Path, cache: dict) -> int:
    """Huella de un fichero de imagen, guardada en `cache` por (ruta, tamaño)."""
    k = f"{ruta}|{ruta.stat().st_size}"
    if k not in cache:
        with Image.open(ruta) as im:
            cache[k] = format(huella(ImageOps.exif_transpose(im)), "x")
    return int(cache[k], 16)


def huellas_entrenamiento() -> list:
    """[(huella, origen, estilo)] de las fotos de entrenamiento (galería, clasificadas en la app, Biblioteca); las huellas se guardan en caché."""
    rutas, y, origen = datos_entrenamiento()
    previo = leer_json(HUELLAS)
    nuevo, salida = dict(previo), []
    for r, e, o in zip(rutas, y.tolist(), origen.tolist()):
        try:
            salida.append((huella_de(r, nuevo), o, e))
        except Exception:  # noqa: BLE001 -- una imagen rota no impide comprobar las demás
            continue
    if nuevo != previo:
        CACHE.mkdir(exist_ok=True)
        guardar_json(HUELLAS, nuevo)
    return salida


def quitar_repetidas(nuevas: dict, existentes: dict) -> int:
    """De las candidatas recién descargadas quita las que ya tienes: repetidas entre sí (una página suele repetir la misma foto con dos direcciones),
    ya entre tus fotos de entrenamiento o ya descargadas antes. Borra el fichero y la entrada; devuelve cuántas quitó."""
    if not nuevas:
        return 0
    vistas = [h for h, _, _ in huellas_entrenamiento()]
    cache = leer_json(HUELLAS)
    for cid in existentes:
        p = IMG / f"{cid}.jpg"
        if cid not in nuevas and p.exists():
            try:
                vistas.append(huella_de(p, cache))
            except Exception:  # noqa: BLE001
                pass
    quitadas = 0
    for cid in list(nuevas):
        p = IMG / f"{cid}.jpg"
        try:
            h = huella_de(p, cache)
        except Exception:  # noqa: BLE001
            continue
        if any(bin(h ^ v).count("1") <= UMBRAL_HUELLA for v in vistas):
            p.unlink(missing_ok=True)
            del nuevas[cid]
            quitadas += 1
        else:
            vistas.append(h)
    CACHE.mkdir(exist_ok=True)
    guardar_json(HUELLAS, cache)
    return quitadas


def guardar_foto_biblioteca(estilo: str, datos: bytes) -> dict:
    """Guarda una foto subida (reducida a ≤1024 px, JPEG). Si YA estaba entre las de entrenamiento con ese mismo estilo no se guarda otra vez
    (`guardada` False); si estaba con OTRO estilo se guarda igualmente (tu elección manda) y se avisa en `estilo_previo`."""
    if estilo not in ESTILOS:
        raise ValueError("estilo no válido")
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(datos))).convert("RGB")
    except Exception:  # noqa: BLE001
        raise ValueError("no se puede leer esa imagen (usa JPG, PNG o WebP)") from None
    if min(im.size) < 200:
        raise ValueError("imagen demasiado pequeña (al menos 200 px de lado)")
    im.thumbnail((1024, 1024))
    fid = hashlib.sha1(im.tobytes()).hexdigest()[:12]
    h, previa = huella(im), None
    for hh, o, e in huellas_entrenamiento():
        if bin(h ^ hh).count("1") <= UMBRAL_HUELLA:
            if e == estilo:
                return {"id": fid, "guardada": False, "ya_estaba": o, "estilo_previo": e}
            previa = (o, e)
    destino = BIB_IMG / estilo / f"{fid}.jpg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    im.save(destino, quality=90)
    return {"id": fid, "guardada": True, "ya_estaba": previa[0] if previa else None, "estilo_previo": previa[1] if previa else None}


def borrar_foto_biblioteca(estilo: str, fid: str) -> bool:
    if estilo not in ESTILOS or not re.fullmatch(r"[0-9a-f]{12}", fid):
        raise ValueError("foto no válida")
    p = BIB_IMG / estilo / f"{fid}.jpg"
    if p.exists():
        p.unlink()
        return True
    return False


def hash_biblioteca() -> str:
    """Huella de lo que influye en el modelo (frases + fotos de la Biblioteca). Si cambia desde el último entrenamiento, hay que reentrenar."""
    b = leer_biblioteca()
    frases = {e: [f for f in b["estilos"][e]["frases"] if f.strip()] for e in ESTILOS}
    usan = sorted(e for e in ESTILOS if b["estilos"][e]["usar_texto"])
    fotos = sorted(f"{p.parent.name}/{p.name}" for p in fotos_biblioteca())
    return hashlib.sha1(json.dumps([frases, usan, fotos], sort_keys=True).encode()).hexdigest()[:16]


def interpretar_token(t: str, plataforma: str) -> dict:
    """Una cuenta o enlace pegado → {'tipo', 'valor'}. ValueError si no se entiende."""
    u = t.strip().strip("<>()[]\"'")
    if re.fullmatch(r"@[A-Za-z0-9_.]{1,30}", u):   # cuenta suelta: la plataforma la eliges tú en la lista desplegable
        h = u[1:]
        if plataforma == "x" and re.fullmatch(r"[A-Za-z0-9_]{1,15}", h):
            return {"tipo": "x", "valor": h}
        if plataforma == "instagram":
            return {"tipo": "instagram", "valor": h}
        if plataforma == "tiktok" and 2 <= len(h) <= 24:
            return {"tipo": "tiktok", "valor": h}
        raise ValueError(f"{u} no es un nombre válido en esa plataforma")
    m = RE_REDDIT.fullmatch(u)
    if m:
        return {"tipo": "reddit_sub" if m.group(1).lower() == "r" else "reddit_user", "valor": m.group(2)}
    if re.match(r"https?://", u, re.I):
        m = RE_X_TUIT.search(u)
        if m:
            return {"tipo": "tuit", "valor": f"https://x.com/{m.group(1)}/status/{m.group(2)}"}
        m = RE_X_PERFIL.fullmatch(u)
        if m:
            if m.group(1).lower() in RESERVADAS_X:
                raise ValueError("eso no es una cuenta")
            return {"tipo": "x", "valor": m.group(1)}
        m = RE_IG_PERFIL.fullmatch(u)
        if m and m.group(1).lower() not in RESERVADAS_IG:
            return {"tipo": "instagram", "valor": m.group(1)}
        m = RE_TT_PERFIL.fullmatch(u)
        if m:
            return {"tipo": "tiktok", "valor": m.group(1)}
        host = urlparse(u).netloc.lower()
        if any(h in host for h in ("instagram.com", "tiktok.com", "youtube.com", "youtu.be", "facebook.com", "pinterest.", "x.com", "twitter.com", "reddit.com")):
            return {"tipo": "red", "valor": u}
        if RE_IMAGEN.search(u):
            return {"tipo": "imagen", "valor": u}
        if RE_FEED.search(urlparse(u).path):
            return {"tipo": "rss", "valor": u}
        return {"tipo": "pagina", "valor": u}
    raise ValueError("no lo entiendo")


def url_fuente(s: dict) -> str:
    v = s["valor"]
    return {"reddit_sub": f"https://www.reddit.com/r/{v}/", "reddit_user": f"https://www.reddit.com/user/{v}/",
            "x": f"https://x.com/{v}", "instagram": f"https://www.instagram.com/{v}/", "tiktok": f"https://www.tiktok.com/@{v}"}.get(s["tipo"], v)


def texto_fuente(s: dict) -> str:
    v = s["valor"]
    if s["tipo"] == "rss":
        p = urlparse(v)
        return (p.netloc.removeprefix("www.") + p.path)[:60]
    return {"reddit_sub": f"r/{v}", "reddit_user": f"u/{v}", "x": f"@{v}", "instagram": f"@{v}", "tiktok": f"@{v}"}.get(s["tipo"], v)


def anadir_fuentes(estilo: str, texto: str, plataforma: str = "x", origen: str = "usuario", mercado: str | None = None) -> dict:
    """Cuentas y enlaces pegados (separados por espacios, comas o líneas) → Biblioteca. Las cuentas de X se copian a la búsqueda de X.
    Con estilo «mercado» no entrenan: sus fotos alimentan el informe del `mercado` indicado (España, EEUU…)."""
    if estilo not in ESTILOS and estilo != ESTILO_MERCADO:
        raise ValueError("estilo no válido")
    if estilo == ESTILO_MERCADO:
        mercado = mercado or "ES"
        if mercado not in MERCADOS:
            raise ValueError("mercado no válido")
    if plataforma not in ("x", "instagram", "tiktok"):
        raise ValueError("plataforma no válida")
    tokens = [t for t in re.split(r"[\s,;]+", texto or "") if t and not t.startswith("#")][:300]
    if not tokens:
        raise ValueError("no has pegado nada")
    res = {"nuevas": 0, "repetidas": 0, "no_entendidas": [], "no_existen": [], "por_descargar": 0, "hay_x": False}
    pares = []
    for t in tokens:
        try:
            pares.append(interpretar_token(t, plataforma))
        except ValueError:
            res["no_entendidas"].append(t[:70])
    reales = {}   # fuera del candado (es una petición de red): ¿existe cada cuenta de X? Sin red no se bloquea: se añade sin comprobar
    for r in pares:
        if r["tipo"] == "x" and r["valor"].lower() not in reales:
            try:
                reales[r["valor"].lower()] = cuenta_x(r["valor"])
            except Exception:  # noqa: BLE001
                reales[r["valor"].lower()] = {}

    def cambio(b):
        ids = {s["id"] for s in b["fuentes"]}
        for r in pares:
            info = reales.get(r["valor"].lower()) if r["tipo"] == "x" else {}
            if info is None:
                res["no_existen"].append("@" + r["valor"])
                continue
            sid = hashlib.sha1(f"{r['tipo']}|{r['valor'].lower()}|{estilo}".encode()).hexdigest()[:10]
            if sid in ids:
                res["repetidas"] += 1
                continue
            ids.add(sid)
            b["fuentes"].append({"id": sid, "tipo": r["tipo"], "valor": r["valor"], "estilo": estilo, "anadida": ahora(), "estado": {},
                                 **({"nombre": info["name"]} if info and info.get("name") else {}), **({"origen": origen} if origen != "usuario" else {}),
                                 **({"mercado": mercado} if estilo == ESTILO_MERCADO else {})})
            res["nuevas"] += 1
            res["por_descargar"] += int(r["tipo"] in ("tuit", "pagina", "imagen"))
            res["hay_x"] |= r["tipo"] == "x" and estilo != ESTILO_MERCADO
    modificar_biblioteca(cambio)
    if res["hay_x"] and origen == "usuario":
        sincronizar_cuentas_x()
    return res


def borrar_fuente(sid: str) -> bool:
    quitada = {"x": False}

    def cambio(b):
        antes = len(b["fuentes"])
        quitada["x"] = any(s["id"] == sid and s["tipo"] == "x" for s in b["fuentes"])
        b["fuentes"] = [s for s in b["fuentes"] if s["id"] != sid]
        return len(b["fuentes"]) < antes
    ok = modificar_biblioteca(cambio)
    if quitada["x"]:
        sincronizar_cuentas_x()
    return ok


def sincronizar_cuentas_x() -> None:
    """Copia las cuentas de X de la Biblioteca a ingesta_x/cuentas_confiables.json (las lee la búsqueda híbrida de X) y quita las que
    la Biblioteca ya no tiene. Las que estaban ahí de antes (verificadas en la galería) no se tocan: `_desde_biblioteca` apunta cuáles son nuestras."""
    datos = leer_json(CUENTAS_X)
    if not datos:
        return
    b = leer_biblioteca()
    nuestras = datos.setdefault("_desde_biblioteca", {})
    for e in ESTILOS:
        actuales = [s["valor"] for s in b["fuentes"] if s["tipo"] == "x" and s["estilo"] == e and s.get("origen", "usuario") == "usuario"]
        previas = set(nuestras.get(e, []))
        lista = [c for c in datos.get(e, []) if isinstance(c, str) and (c not in previas or c in actuales)]
        for c in actuales:
            if c.lower() not in {x.lower() for x in lista}:
                lista.append(c)
        datos[e] = lista
        nuestras[e] = actuales
    guardar_json(CUENTAS_X, datos)


# ---------------------------------------------------------------- modelo de estilos
def datos_entrenamiento():
    """Fotos con estilo confirmado: las de la galería + las que clasificas en la app + las que subes a la Biblioteca.
    Devuelve (rutas, estilos, origen) con origen ∈ {galeria, clasificadas, biblioteca}."""
    rutas, y, origen = [], [], []
    for it in leer_json(CLASIF).values():
        est = it.get("categoria_final") or it.get("categoria_ia")
        if it["eliminada"] or not it.get("revisada") or not it.get("imagen") or est not in ESTILOS:
            continue
        p = FOTOS / it["imagen"]
        if p.exists():
            rutas.append(p)
            y.append(est)
            origen.append("galeria")
    for cid, e in leer_json(ETIQUETAS).items():
        p = IMG / f"{cid}.jpg"
        if e.get("decision") == "ok" and e.get("estilo") in ESTILOS and p.exists():
            rutas.append(p)
            y.append(e["estilo"])
            origen.append("clasificadas")
    for est in ESTILOS:
        for p in fotos_biblioteca(est):
            rutas.append(p)
            y.append(est)
            origen.append("biblioteca")
    return rutas, np.array(y), np.array(origen)


@dataclass
class Modelo:
    """Clasificador de 7 estilos: regresión logística sobre CLIP (fotos) + prototipo de texto CLIP por estilo (frases de la Biblioteca)."""
    W: np.ndarray
    b: np.ndarray
    clases: list
    cv_acc: float
    fecha: str
    n: int = 0
    T: np.ndarray | None = None      # (k, 512) prototipos de texto, en el orden de `clases`
    usa: np.ndarray | None = None    # (k,) True si ese estilo tiene frases
    lam: float = 0.0                 # peso del texto frente a las fotos (0 = solo fotos)
    cv_acc_fotos: float = 0.0        # validación cruzada con λ = 0
    recall: dict | None = None       # estilo → recall en validación cruzada con el λ elegido
    recall_fotos: dict | None = None  # ídem con λ = 0
    n_clase: dict | None = None
    bib: str = ""                    # huella de la Biblioteca con la que se entrenó


LAMBDAS = [0.0, 0.25, 0.5, 1.0, 2.0]   # pesos del texto que se prueban en validación cruzada
UMBRAL_REPETIDA = 0.97                 # coseno CLIP a partir del cual dos fotos se consideran la misma
C_REGULARIZACION = 5.0                 # la misma C de la regresión logística de siempre (menos = más suave)


def prototipos_texto(clases: list):
    """Un vector de texto por estilo: media (normalizada) de sus frases. `usa[i]` es True si ese estilo tiene frases Y marcaste «usar la descripción»."""
    b = leer_biblioteca()
    m, _, tok = clip()
    T = np.zeros((len(clases), 512), np.float32)
    usa = np.zeros(len(clases), bool)
    for i, c in enumerate(clases):
        frases = [f for f in b["estilos"][c]["frases"] if f.strip()]
        if frases:
            t = m.encode_text(tok(frases))
            t = t / t.norm(dim=-1, keepdim=True)
            v = t.mean(0).numpy()
            T[i], usa[i] = v / np.linalg.norm(v), b["estilos"][c]["usar_texto"]
    return T, usa


def logits_texto(X: np.ndarray, T: np.ndarray, usa: np.ndarray) -> np.ndarray:
    """Puntos que la descripción da a cada estilo marcado: parecido (coseno × 100) de la foto con su texto menos la media de todos los estilos, y solo
    la parte positiva. El texto suma cuando la foto se parece a la descripción pero nunca resta: una cayetana no debe perder puntos por no ser el
    cayetano de la frase."""
    Z = 100.0 * X @ T.T
    tiene = np.abs(T).sum(1) > 0
    if tiene.any():
        Z = Z - Z[:, tiene].mean(1, keepdims=True)
    Z = np.maximum(Z, 0.0)
    Z[:, ~usa] = 0.0
    return Z


def ajustar_regresion(X: np.ndarray, yi: np.ndarray, k: int, base: np.ndarray | None = None):
    """Regresión logística multinomial con pesos de clase «balanced» y L2 (equivale a LogisticRegression(C=5, class_weight='balanced') de scikit-learn), con
    una puntuación de partida `base` (n, k) que se suma a los logits sin entrenarse: el texto. El modelo solo aprende la CORRECCIÓN que hacen falta las
    fotos, así que con pocas fotos manda el texto y con muchas mandan las fotos."""
    from scipy.optimize import minimize
    from scipy.special import logsumexp
    n, d = X.shape
    cuenta = np.bincount(yi, minlength=k)
    w = (n / (k * np.maximum(cuenta, 1)))[yi]
    Y = np.eye(k)[yi]
    base = np.zeros((n, k)) if base is None else base

    def f(theta):
        W, b = theta[:k * d].reshape(k, d), theta[k * d:]
        Z = X @ W.T + b + base
        L = logsumexp(Z, axis=1)
        P = np.exp(Z - L[:, None])
        G = w[:, None] * (P - Y)
        return (w * (L - (Z * Y).sum(1))).sum() + (W ** 2).sum() / (2 * C_REGULARIZACION), np.concatenate([(G.T @ X + W / C_REGULARIZACION).ravel(), G.sum(0)])
    r = minimize(f, np.zeros(k * d + k), jac=True, method="L-BFGS-B", options={"maxiter": 500})
    return r.x[:k * d].reshape(k, d), r.x[k * d:]


def quitar_casi_repetidas(X: np.ndarray, y: np.ndarray, origen: np.ndarray):
    """Si subes dos veces la misma foto (o una recortada) la validación cruzada la vería en entrenamiento y en prueba y saldría inflada:
    de cada grupo de fotos casi idénticas se queda una sola. Si las copias tienen estilos distintos manda lo último que decides tú:
    Biblioteca > clasificadas en la app > galería."""
    prioridad = {"biblioteca": 0, "clasificadas": 1, "galeria": 2}
    orden = np.argsort([prioridad[o] for o in origen], kind="stable")
    X, y, origen = X[orden], y[orden], origen[orden]
    S = X @ X.T
    quedan, conflictos = [], 0
    for i in range(len(X)):
        if quedan:
            s = S[i, quedan]
            k = int(s.argmax())
            if s[k] >= UMBRAL_REPETIDA:
                conflictos += int(y[i] != y[quedan[k]])
                continue
        quedan.append(i)
    quedan = np.array(quedan)
    return X[quedan], y[quedan], origen[quedan], len(X) - len(quedan), conflictos


def cmd_entrenar(_):
    from sklearn.model_selection import StratifiedKFold
    from threadpoolctl import threadpool_limits
    rutas, y, origen = datos_entrenamiento()
    cuenta = {o: int((origen == o).sum()) for o in ("galeria", "clasificadas", "biblioteca")}
    print(f"Fotos de entrenamiento: {len(y)} ({cuenta['galeria']} de la galería, {cuenta['clasificadas']} clasificadas en la app, "
          f"{cuenta['biblioteca']} de la Biblioteca)")
    X = embeber_imagenes(rutas, "entrenamiento")
    X, y, origen, repetidas, conflictos = quitar_casi_repetidas(X, y, origen)
    if repetidas:
        print(f"  {repetidas} fotos casi idénticas a otra se usan una sola vez" +
              (f" ({conflictos} de ellas con un estilo distinto en cada copia: se queda el de la Biblioteca, o el último que decidiste)" if conflictos else ""))
    clases = sorted(set(y.tolist()))
    por_clase = {c: int((y == c).sum()) for c in clases}
    if min(por_clase.values()) < 2:
        raise SystemExit("ERROR: hace falta al menos 2 fotos de cada estilo para entrenar. Faltan: " +
                         ", ".join(NOMBRE[c] for c, n in por_clase.items() if n < 2))
    k, ca = len(clases), np.array(clases)
    yi = np.array([clases.index(v) for v in y])
    T, usa = prototipos_texto(clases)
    Zt = logits_texto(X, T, usa)
    lambdas = LAMBDAS if usa.any() else [0.0]
    pliegues = [list(StratifiedKFold(min(5, min(por_clase.values())), shuffle=True, random_state=s).split(X, y)) for s in (0, 1)]

    def medir(lam):
        """Validación cruzada (2 repeticiones): ninguna foto se predice con un modelo que la haya visto."""
        accs, recs, pred_ult = [], [], None
        with threadpool_limits(1):   # matrices pequeñas: con un solo hilo va mucho más rápido
            for rep in pliegues:
                pred = np.empty(len(y), int)
                for tr, te in rep:
                    W, b = ajustar_regresion(X[tr], yi[tr], k, lam * Zt[tr])
                    pred[te] = (X[te] @ W.T + b + lam * Zt[te]).argmax(1)
                accs.append(float((pred == yi).mean()))
                recs.append([float((pred[yi == c] == c).mean()) for c in range(k)])
                pred_ult = pred
        rec = np.mean(recs, axis=0)
        return float(np.mean(accs)), rec, pred_ult

    if usa.any():
        print("\nEstilos que usan su descripción: " + ", ".join(NOMBRE[c] for c, u in zip(clases, usa) if u))
        print("Peso de la descripción (λ) · acierto global · recall medio por estilo   (λ = 0: solo fotos)")
    tabla = {lam: medir(lam) for lam in lambdas}
    for lam, (acc, rec, _) in tabla.items():
        if usa.any():
            print(f"   λ = {lam:<4}  {100 * acc:3.0f} %   {100 * rec.mean():3.0f} %")
    acc0, rec0, _ = tabla[0.0]
    mejor = max(lambdas, key=lambda l: (round(float(tabla[l][1].mean()), 3), -l))
    # solo se usa el texto si mejora ≥ 1 punto el recall medio y no cuesta más de 2 puntos de acierto global (si no, es ruido o robar a otros estilos)
    lam = mejor if (tabla[mejor][1].mean() - rec0.mean() >= 0.01 and tabla[mejor][0] >= acc0 - 0.02) else 0.0
    acc, rec, pred = tabla[lam]
    if usa.any():
        print(f"\n→ Se usa λ = {lam}" + ("" if lam else "  (la descripción no mejora lo bastante en validación cruzada: el modelo usa solo las fotos)"))
    print(f"Acierto con validación cruzada: {100 * acc:.0f} %  (solo fotos: {100 * acc0:.0f} %; azar ≈ {100 / k:.0f} %, clase mayoritaria {100 * max(por_clase.values()) / len(y):.0f} %)")
    print("Por estilo (recall = de las fotos de ese estilo, cuántas acierta):")
    for i, c in enumerate(clases):
        m = yi == i
        conf = {ca[j]: int(((pred == j) & m).sum()) for j in range(k) if j != i and ((pred == j) & m).sum()}
        peor = max(conf, key=conf.get) if conf else "-"
        marca = "  ← con descripción" if usa[i] and lam else ""
        print(f"   {NOMBRE[c]:20s} {por_clase[c]:3d} fotos · recall {100 * rec[i]:3.0f} %  (solo fotos {100 * rec0[i]:3.0f} %)   se confunde sobre todo con: {NOMBRE.get(peor, peor)}{marca}")
    if usa.any():
        print("Aviso: con 15-20 fotos en un estilo, estas cifras tienen un margen de ±10 puntos; la medida de verdad es «coincide contigo» al clasificar fotos nuevas.")
    W, b = ajustar_regresion(X, yi, k, lam * Zt)
    np.savez(MODELO, W=W.astype(np.float32), b=b.astype(np.float32), clases=ca, cv_acc=acc, cv_acc_fotos=acc0, n=len(y), fecha=ahora(), T=T, usa=usa, lam=lam,
             recall=rec, recall_fotos=rec0, n_clase=np.array([por_clase[c] for c in clases]), bib=hash_biblioteca())
    print(f"\nModelo guardado en {MODELO.name}. Aviso: la validación cruzada mezcla fuentes; el acierto REAL en una fuente nueva "
          f"(p. ej. Reddit) lo ves al clasificar en la pestaña «Clasificar».")


def cargar_modelo_estilos() -> Modelo:
    if not MODELO.exists():
        raise SystemExit("ERROR: falta modelo_estilos.npz. Ejecuta primero:  python3 mercado.py entrenar")
    z = np.load(MODELO, allow_pickle=True)
    clases, ficheros = [str(c) for c in z["clases"]], z.files

    def por_clase(k):
        return {c: float(v) for c, v in zip(clases, z[k])} if k in ficheros else None
    return Modelo(W=z["W"], b=z["b"], clases=clases, cv_acc=float(z["cv_acc"]), fecha=str(z["fecha"]), n=int(z["n"]),
                  T=z["T"] if "T" in ficheros else None, usa=z["usa"] if "usa" in ficheros else None,
                  lam=float(z["lam"]) if "lam" in ficheros else 0.0, cv_acc_fotos=float(z["cv_acc_fotos"]) if "cv_acc_fotos" in ficheros else float(z["cv_acc"]),
                  recall=por_clase("recall"), recall_fotos=por_clase("recall_fotos"),
                  n_clase={c: int(v) for c, v in zip(clases, z["n_clase"])} if "n_clase" in ficheros else None,
                  bib=str(z["bib"]) if "bib" in ficheros else "")


def predecir(X: np.ndarray, modelo: Modelo):
    z = X @ modelo.W.T + modelo.b
    if modelo.lam and modelo.T is not None:
        z = z + modelo.lam * logits_texto(X, modelo.T, modelo.usa)
    z -= z.max(1, keepdims=True)
    p = np.exp(z)
    p /= p.sum(1, keepdims=True)
    return p, modelo.clases


def completar_predicciones(cands: dict) -> None:
    """Calcula estilo sugerido (top-3) y puntuación de foto real para las candidatas con imagen; se rehace si cambia el modelo."""
    modelo = cargar_modelo_estilos()
    pend = [c for c in cands.values() if (IMG / f"{c['id']}.jpg").exists() and c.get("modelo") != modelo.fecha]
    if not pend:
        return
    X = embeber_imagenes([IMG / f"{c['id']}.jpg" for c in pend], "candidatos")
    P, clases = predecir(X, modelo)
    gate = puntuacion_foto_real(X)
    nuevos = {}
    for c, p, g in zip(pend, P, gate):
        orden = np.argsort(-p)[:3]
        nuevos[c["id"]] = {"pred": [[clases[i], round(float(p[i]), 3)] for i in orden], "gate": round(float(g), 3), "modelo": modelo.fecha}

    def aplicar(actual):   # sobre el fichero recién leído: no pisa candidatas que una tarea haya añadido mientras tanto
        for cid, v in nuevos.items():
            if cid in actual:
                actual[cid].update(v)
    modificar_json(CANDIDATOS, aplicar)


# ---------------------------------------------------------------- cosechar
def peticion_con_ritmo(url: str, reintentos: int = 6):
    """GET educado: respeta Retry-After / x-ratelimit-reset de Reddit y reintenta con espera creciente ante 429."""
    for intento in range(reintentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                reset = float(r.headers.get("x-ratelimit-reset", "20") or 20)
                return r.read().decode("utf-8", "ignore"), reset
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                espera = min(240.0, max(float(e.headers.get("retry-after", 0) or 0), 30.0 * (intento + 1)))
                print(f"  límite de Reddit ({e.code}): espero {espera:.0f}s", flush=True)
                time.sleep(espera)
                continue
            if e.code in (403, 404):
                return None, 0.0
            raise
    return None, 0.0


def parsear_rss(xml: str, comunidad: str, periodo: str, con_rank: bool = True) -> list[dict]:
    salida = []
    for rank, e in enumerate(re.findall(r"<entry>(.*?)</entry>", xml, re.S), 1):
        cont = html.unescape(re.search(r"<content[^>]*>(.*?)</content>", e, re.S).group(1)) if "<content" in e else ""
        m = re.search(r"https://i\.redd\.it/[A-Za-z0-9_\-]+\.(?:jpe?g|png|webp)", cont, re.I)
        pid = re.search(r"<id>t3_(\w+)</id>", e)
        if not m or not pid:
            continue   # texto, enlace externo, galería o vídeo: solo se toman imágenes directas
        salida.append({
            "post": pid.group(1), "fuente": "reddit", "comunidad": comunidad, "periodo": periodo, "rank": rank if con_rank else None,
            "titulo": html.unescape(re.search(r"<title>(.*?)</title>", e, re.S).group(1)).strip(),
            "imagen_url": m.group(0),
            "permalink": (re.search(r'<link href="([^"]+)"', e) or [None, ""])[1],
            "fecha": (re.search(r"<updated>(.*?)</updated>", e) or [None, ahora()])[1],
        })
    return salida


MAX_BYTES_IMAGEN = 15_000_000


def descargar_imagen(url: str, destino: Path, max_lado: int = 1024, min_lado: int = 300, referer: str | None = None,
                     proporcion: tuple | None = None) -> bool:
    """Descarga una imagen y la guarda como JPEG ≤ max_lado. False si es pequeña (< min_lado) o con proporción rara (banners)."""
    if url.startswith("data:image/"):   # imagen incrustada en la propia página (webs pequeñas)
        datos = base64.b64decode(url.split(",", 1)[1])
    else:
        cabeceras = {"User-Agent": UA, **({"Referer": referer} if referer else {})}
        with urllib.request.urlopen(urllib.request.Request(url, headers=cabeceras), timeout=30) as r:
            datos = r.read(MAX_BYTES_IMAGEN + 1)
    if len(datos) > MAX_BYTES_IMAGEN:
        return False
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(datos))).convert("RGB")
    if min(im.size) < min_lado:
        return False
    if proporcion and not (proporcion[0] <= im.width / im.height <= proporcion[1]):
        return False
    im.thumbnail((max_lado, max_lado))
    destino.parent.mkdir(parents=True, exist_ok=True)
    im.save(destino, quality=88)
    return True


def nueva_candidata(cid, fuente, comunidad, titulo, imagen_url, permalink, fecha=None, rank=None, estilo=None, fuente_id=None, solo_entrenamiento=False,
                    mercado=None, extra=None) -> dict:
    """`estilo` = el que indicaste en la Biblioteca. Lo que viene de ahí solo cuenta como «moda de ahora» en el informe cuando lo confirmas tú."""
    c = {"id": cid, "fuente": fuente, "comunidad": comunidad, "titulo": titulo, "imagen_url": imagen_url, "permalink": permalink,
         "fecha": fecha or ahora(), "rank": rank, "capturado": ahora()}
    if estilo:
        c["estilo_propuesto"] = estilo        # lo que TÚ indicaste en la Biblioteca: se te propone al clasificar, tú confirmas
        c["solo_si_confirmada"] = True
    if fuente_id:
        c["fuente_biblioteca"] = fuente_id
    if solo_entrenamiento:
        c["solo_entrenamiento"] = True       # páginas e imágenes sueltas: sirven para entrenar, no cuentan como «moda de ahora» en el informe
    if mercado:
        c["mercado"], c["solo_mercado"] = mercado, True   # de una fuente de mercado: cuenta en el informe y no sale en «Clasificar»
    c.update({k: v for k, v in (extra or {}).items() if v is not None})
    return c


def anadir_candidatos(nuevas: dict) -> None:
    """Añade candidatas al fichero releyéndolo antes (la app y una tarea escriben a la vez); nunca pisa las que ya estaban."""
    def cambio(actual):
        for k, v in nuevas.items():
            actual.setdefault(k, v)
    if nuevas:
        modificar_json(CANDIDATOS, cambio)


# ---- páginas web: sacar las fotos de un artículo/blog
RE_BASURA = re.compile(r"logo|icon|sprite|avatar|favicon|pixel|tracking|placeholder|spacer|emoji|gravatar|1x1|blank|advert|/ads?[/_-]", re.I)
RE_MINIATURA = re.compile(r"[-_]\d{2,4}x\d{2,4}(?=\.\w+$)")   # WordPress: foto-300x200.jpg es la miniatura de foto.jpg
MAX_FOTOS_PAGINA, MAX_INTENTOS_PAGINA = 12, 40


class ExtractorImagenes(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []
        self.titulo, self._en_titulo = "", False

    def _a(self, u):
        if u and (not u.strip().startswith("data:") or re.match(r"data:image/(jpeg|jpg|png|webp);base64,", u.strip())):
            self.urls.append(u.strip())

    @staticmethod
    def mejor_srcset(s):
        mejor, ancho = None, -1
        for parte in (s or "").split(","):
            p = parte.strip().split()
            if not p:
                continue
            w = 0
            if len(p) > 1 and p[1][:-1].replace(".", "", 1).isdigit():
                w = int(float(p[1][:-1]) * (1000 if p[1].endswith("x") else 1))
            if w >= ancho:
                mejor, ancho = p[0], w
        return mejor

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            if (a.get("property") or a.get("name") or "").lower() in ("og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src"):
                self._a(a.get("content"))
        elif tag == "img":
            for k in ("src", "data-src", "data-lazy-src", "data-original"):
                self._a(a.get(k))
            for k in ("srcset", "data-srcset"):
                self._a(self.mejor_srcset(a.get(k)))
        elif tag == "source":
            self._a(self.mejor_srcset(a.get("srcset") or a.get("data-srcset")))
        elif tag == "title":
            self._en_titulo = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._en_titulo = False

    def handle_data(self, data):
        if self._en_titulo:
            self.titulo += data


def imagenes_de_pagina(base: str, texto: str) -> tuple[str, list[list[str]]]:
    """(título, grupos de direcciones). Cada grupo es una foto con alternativas: primero la original (sin el «-300x200» de las miniaturas
    de WordPress) y luego la que aparece en la página. Se descartan logos, iconos, SVG/GIF y repetidas."""
    ex = ExtractorImagenes()
    ex.feed(texto)
    vistos, grupos = set(), []
    for u in ex.urls:
        if u.startswith("data:"):
            clave = ("data", hashlib.sha1(u.encode()).hexdigest())
            if clave not in vistos:
                vistos.add(clave)
                grupos.append([u])
            continue
        u = urljoin(base, u)
        p = urlparse(u)
        if p.scheme not in ("http", "https"):
            continue
        ruta = p.path.lower()
        if ruta.endswith((".svg", ".gif", ".ico", ".avif")) or RE_BASURA.search(ruta):
            continue
        clave = (p.netloc, RE_MINIATURA.sub("", ruta))
        if clave in vistos:
            continue
        vistos.add(clave)
        original = urljoin(u, RE_MINIATURA.sub("", p.path)) if RE_MINIATURA.search(p.path) else None
        grupos.append([original, u] if original else [u])
    return re.sub(r"\s+", " ", ex.titulo).strip()[:140], grupos


def pedir_html(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "es-ES,es;q=0.9,en;q=0.5"})
    with urllib.request.urlopen(req, timeout=25) as r:
        tipo = r.headers.get("Content-Type", "")
        if tipo and "html" not in tipo and "xml" not in tipo:
            raise ValueError(f"no es una página web ({tipo.split(';')[0]})")
        datos, codificacion = r.read(4_000_000), r.headers.get_content_charset() or "utf-8"
        return r.geturl(), datos.decode(codificacion, "replace")


def cosechar_pagina(url: str, estilo: str | None, fuente_id: str | None, existentes: dict) -> dict:
    """Fotos de un artículo o blog: las descarga (≥400 px, proporción de foto, no banner) y se queda con las que CLIP reconoce como
    «persona con ropa» (descarta logos, publicidad y fotos de producto sueltas), un máximo de MAX_FOTOS_PAGINA."""
    final, texto = pedir_html(url)
    titulo, grupos = imagenes_de_pagina(final, texto)
    host = urlparse(final).netloc.removeprefix("www.")
    nuevas, intentos = {}, 0
    for grupo in grupos:
        if intentos >= MAX_INTENTOS_PAGINA:
            break
        cid = "pg_" + hashlib.sha1(grupo[-1].encode()).hexdigest()[:10]
        if cid in existentes:
            continue
        intentos += 1
        for u in grupo:
            try:
                if descargar_imagen(u, IMG / f"{cid}.jpg", min_lado=400, referer=final, proporcion=(0.4, 2.5)):
                    nuevas[cid] = nueva_candidata(cid, "pagina", host, titulo, final + "#imagen-incrustada" if u.startswith("data:") else u, final,
                                                  estilo=estilo, fuente_id=fuente_id, solo_entrenamiento=True)
                    break
            except Exception:  # noqa: BLE001 -- una imagen rota no impide probar las demás
                continue
    if nuevas:
        g = puntuacion_foto_real(embeber_imagenes([IMG / f"{cid}.jpg" for cid in nuevas], "candidatos"))
        buenas = sorted(((float(gi), cid) for gi, cid in zip(g, nuevas) if gi >= UMBRAL_PUERTA), reverse=True)[:MAX_FOTOS_PAGINA]
        quedan = {cid for _, cid in buenas}
        for cid in list(nuevas):
            if cid not in quedan:
                (IMG / f"{cid}.jpg").unlink(missing_ok=True)
                del nuevas[cid]
        print(f"  {intentos} imágenes probadas → {len(nuevas)} parecen una persona con ropa", flush=True)
    return nuevas


def cosechar_tuit(url: str, estilo: str | None, fuente_id: str | None, existentes: dict) -> dict:
    """Fotos de un tuit (endpoint público de sindicación, el mismo de la ingesta de X)."""
    sys.path.insert(0, str(HERR_X))
    import descargar_x as dx
    m = RE_X_TUIT.search(url)
    sind = dx.consultar_sindicacion(m.group(2)) or {}
    fotos = sind.get("photos") or []
    if not fotos:
        raise ValueError("el tuit no tiene fotos (o X no dejó leerlo)")
    nuevas = {}
    for n, f in enumerate(fotos, 1):
        cid = f"tw_{m.group(2)}_{n}"
        url_img = f.get("url") or f.get("media_url_https")
        if cid in existentes or not url_img:
            continue
        if descargar_imagen(url_img + ("&" if "?" in url_img else "?") + "format=jpg&name=orig", IMG / f"{cid}.jpg"):
            nuevas[cid] = nueva_candidata(cid, "x", "@" + m.group(1), (sind.get("text") or "")[:120], url_img, url,
                                          fecha=sind.get("created_at"), estilo=estilo, fuente_id=fuente_id)
    return nuevas


def pedir_json(url: str, espera: int = 25):
    """GET de una API pública. None si responde 404; las demás faltas se propagan."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=espera) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def cuenta_x(handle: str):
    """Datos públicos de una cuenta de X (nombre, seguidores) o None si no existe. FxTwitter contesta «User not found» a veces la primera vez que
    se pide una cuenta que sí existe (y 200 unos segundos después): solo se da por inexistente tras 3 intentos seguidos."""
    for espera in (0, 3, 6):
        time.sleep(espera)
        user = (pedir_json(f"{FXTWITTER}/{handle}", espera=12) or {}).get("user")
        if user:
            return user
    return None


def actualizar_candidatas(cambios: dict) -> None:
    """Pone al día (likes, vistas…) candidatas ya descargadas; no toca nada más."""
    def cambio(actual):
        for cid, meta in cambios.items():
            if cid in actual:
                actual[cid].update({k: v for k, v in meta.items() if v is not None})
    if cambios:
        modificar_json(CANDIDATOS, cambio)


def cosechar_cuenta_x(handle: str, estilo: str | None, fuente_id: str | None, existentes: dict, mercado: str | None = None):
    """Fotos de los últimos ~20 posts propios (sin reposts) de una cuenta de X, a través del servicio público FxTwitter. Cada foto guarda de dónde es
    (autor, idioma del post, ubicación declarada del autor) y su popularidad (likes, reposts, vistas, seguidores del autor).
    Devuelve (candidatas nuevas, datos puestos al día de las que ya estaban, {"ultima_foto_hace_dias": …} para avisar de cuentas inactivas)."""
    d = None
    for espera in (0, 4, 8, 12):   # FxTwitter responde 404 a veces la primera vez que se pide una cuenta y 200 unos segundos después
        time.sleep(espera)
        d = pedir_json(f"{FXTWITTER}/2/profile/{handle}/statuses")
        if d is not None:
            break
    if d is None:
        if cuenta_x(handle) is None:
            raise ValueError("la cuenta no existe en X (o es privada): ¿está bien escrita?")
        raise ValueError("el servicio FxTwitter no devolvió los posts de esta cuenta (a veces falla): inténtalo de nuevo en unos minutos")
    posts = [p for p in d.get("results") or [] if not p.get("reposted_by")]
    nuevas, puestas_al_dia, con_foto, edades = {}, {}, 0, []
    for p in posts:
        fotos = (p.get("media") or {}).get("photos") or []
        con_foto += bool(fotos)
        edad = (time.time() - p["created_timestamp"]) / 86400 if p.get("created_timestamp") else None
        if fotos and edad is not None:
            edades.append(edad)
        if mercado and edad is not None and edad > DIAS_MAX_MERCADO:
            continue
        a = p.get("author") or {}
        meta = {"autor": "@" + handle, "idioma": p.get("lang"), "ubicacion_autor": a.get("location") or None, "seguidores_autor": a.get("followers"),
                "likes": p.get("likes"), "reposts": p.get("reposts"), "vistas": p.get("views"), "respuestas": p.get("replies")}
        for n, ft in enumerate(fotos, 1):
            cid = f"tw_{p['id']}_{n}"
            if cid in existentes:
                puestas_al_dia[cid] = meta
                continue
            if cid in nuevas or not ft.get("url"):
                continue
            try:
                if descargar_imagen(ft["url"], IMG / f"{cid}.jpg"):
                    ts = p.get("created_timestamp")
                    nuevas[cid] = nueva_candidata(cid, "x", "@" + handle, (p.get("text") or "")[:120], ft["url"], p.get("url") or f"https://x.com/{handle}/status/{p['id']}",
                                                  fecha=datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds") if ts else None,
                                                  estilo=estilo, fuente_id=fuente_id, mercado=mercado, extra=meta)
            except Exception as e:  # noqa: BLE001
                print(f"  foto no descargada ({ft['url'][-30:]}): {e}")
    print(f"  {len(posts)} posts propios, {con_foto} con foto" + (f"; la última foto es de hace {min(edades):.0f} días" if edades else ""), flush=True)
    return nuevas, puestas_al_dia, {"ultima_foto_hace_dias": round(min(edades)) if edades else None}


def _local(etiqueta: str) -> str:
    return etiqueta.rsplit("}", 1)[-1].lower()


def imagenes_de_item(item) -> list[str]:
    """Direcciones de imagen de una entrada de feed (media:content / media:thumbnail / enclosure / <img> del contenido), las más grandes primero."""
    encontradas = []
    for e in item.iter():
        t = _local(e.tag)
        tipo, medio = (e.get("type") or "").lower(), (e.get("medium") or "").lower()
        if t in ("content", "thumbnail") and e.get("url") and medio != "video" and not tipo.startswith("video"):
            encontradas.append((int(re.sub(r"\D", "", e.get("width") or "0") or 0), e.get("url")))
        elif t == "enclosure" and tipo.startswith("image") and e.get("url"):
            encontradas.append((0, e.get("url")))
        elif t in ("encoded", "description", "summary") and e.text:
            for m in re.finditer(r"<img[^>]+src=[\"']([^\"']+)", html.unescape(e.text)):
                encontradas.append((0, m.group(1)))
    vistas, salida = set(), []
    for _, u in sorted(encontradas, key=lambda x: -x[0]):
        u = html.unescape(u).strip()
        if u.startswith("http") and u not in vistas and not RE_BASURA.search(urlparse(u).path):
            vistas.add(u)
            salida.append(u)
    return salida


def cosechar_rss(url: str, estilo: str | None, fuente_id: str | None, existentes: dict, mercado: str | None = None):
    """Un feed RSS/Atom de un medio: una foto por entrada (la mayor), con su título, enlace y fecha. Para fuentes de mercado solo las de los últimos DIAS_MAX_MERCADO días.
    Devuelve (candidatas nuevas, {}, {"ultima_foto_hace_dias": …}) como `cosechar_cuenta_x`."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=30) as r:
        datos = r.read(5_000_000)
    raiz = ET.fromstring(datos)
    host = urlparse(url).netloc.removeprefix("www.")
    entradas = [e for e in raiz.iter() if _local(e.tag) in ("item", "entry")]
    nuevas, edades = {}, []
    for it in entradas:
        hijos = {_local(e.tag): e for e in it}
        titulo = html.unescape((hijos["title"].text or "") if "title" in hijos else "").strip()
        enlace = (hijos["link"].text or hijos["link"].get("href") or "").strip() if "link" in hijos else ""
        crudo = next((hijos[k].text for k in ("pubdate", "published", "updated", "date") if k in hijos and hijos[k].text), None)
        fecha = None
        if crudo:
            try:
                fecha = parsedate_to_datetime(crudo)
            except Exception:  # noqa: BLE001
                try:
                    fecha = datetime.fromisoformat(crudo.strip().replace("Z", "+00:00"))
                except Exception:  # noqa: BLE001
                    fecha = None
        if fecha is not None and fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        edad = (datetime.now(timezone.utc) - fecha).total_seconds() / 86400 if fecha else None
        if edad is not None:
            edades.append(edad)
        if mercado and edad is not None and edad > DIAS_MAX_MERCADO:
            continue
        for img in imagenes_de_item(it)[:2]:
            cid = "rs_" + hashlib.sha1(img.encode()).hexdigest()[:10]
            if cid in existentes or cid in nuevas:
                break
            try:
                if descargar_imagen(img, IMG / f"{cid}.jpg", min_lado=400, referer=enlace or url, proporcion=(0.4, 2.5)):
                    nuevas[cid] = nueva_candidata(cid, "rss", host, titulo[:140], img, enlace or url, fecha=fecha.isoformat(timespec="seconds") if fecha else None,
                                                  estilo=estilo, fuente_id=fuente_id, mercado=mercado, extra={"autor": host})
                    break
            except Exception:  # noqa: BLE001 -- una imagen rota no impide probar la siguiente
                continue
    print(f"  {len(entradas)} entradas en el feed" + (f"; la más reciente es de hace {min(edades):.0f} días" if edades else ""), flush=True)
    return nuevas, {}, {"ultima_foto_hace_dias": round(min(edades)) if edades else None}


def cosechar_imagen(url: str, estilo: str | None, fuente_id: str | None, existentes: dict) -> dict:
    cid = "url_" + hashlib.sha1(url.encode()).hexdigest()[:10]
    if cid in existentes:
        return {}
    if not descargar_imagen(url, IMG / f"{cid}.jpg", min_lado=200):
        raise ValueError("la imagen es demasiado pequeña")
    return {cid: nueva_candidata(cid, "enlace", urlparse(url).netloc.removeprefix("www."), "", url, url, estilo=estilo, fuente_id=fuente_id, solo_entrenamiento=True)}


COSECHA_ENLACE = {"tuit": cosechar_tuit, "pagina": cosechar_pagina, "imagen": cosechar_imagen}


def cosechar_urls(fichero: str, cands: dict) -> int:
    """Enlaces pegados en un fichero (uno por línea): tuits con fotos, imágenes directas o páginas web, sin estilo propuesto."""
    nuevos = 0
    for linea in Path(fichero).read_text(encoding="utf-8").splitlines():
        u = linea.strip()
        if not u or u.startswith("#"):
            continue
        try:
            r = interpretar_token(u, "x")
            if r["tipo"] not in COSECHA_ENLACE:
                print(f"  (ignorado: {TIPOS[r['tipo']][0]}; solo tuits, imágenes y páginas) {u[:80]}")
                continue
            nuevas = COSECHA_ENLACE[r["tipo"]](r["valor"], None, None, cands)
            anadir_candidatos(nuevas)
            cands.update(nuevas)
            nuevos += len(nuevas)
        except Exception as e:  # noqa: BLE001 -- un enlace malo no debe parar los demás
            print(f"  fallo con {u[:70]}: {e}")
    return nuevos


def cosechar_feed_reddit(url: str, comunidad: str, periodo: str, con_rank: bool, estilo: str | None, fuente_id: str | None, existentes: dict):
    """Un «top» de comunidad o el historial de un usuario. Devuelve (candidatas nuevas, publicaciones con imagen, segundos de espera) o None si no hay datos."""
    xml, reset = peticion_con_ritmo(url)
    if xml is None:
        return None
    entradas = parsear_rss(xml, comunidad, periodo, con_rank)
    nuevas = {}
    for c in entradas:
        cid = f"rd_{c['post']}"
        if cid in existentes or cid in nuevas:
            continue
        try:
            if descargar_imagen(c["imagen_url"], IMG / f"{cid}.jpg"):
                nuevas[cid] = {"id": cid, **c, "capturado": ahora(), **({"estilo_propuesto": estilo, "solo_si_confirmada": True} if estilo else {}),
                               **({"fuente_biblioteca": fuente_id} if fuente_id else {})}
        except Exception as e:  # noqa: BLE001
            print(f"  imagen no descargada ({c['imagen_url'][-30:]}): {e}")
        time.sleep(0.4)
    return nuevas, len(entradas), reset


def registrar_resultado(nuevas: dict, sid: str, estado: dict) -> None:
    anadir_candidatos(nuevas)

    def cambio(b):
        for s in b["fuentes"]:
            if s["id"] == sid:
                if "error" in estado:
                    s["estado"]["error"] = estado["error"]
                else:
                    s["estado"] = estado
    modificar_biblioteca(cambio)


def repetidas_fuera(nuevas: dict, existentes: dict, estado: dict) -> dict:
    """Quita las fotos que ya tenías y deja el recuento real en el estado de la fuente."""
    quitadas = quitar_repetidas(nuevas, existentes)
    if quitadas:
        print(f"  {quitadas} fotos descartadas por repetidas (ya las tenías o salían dos veces)", flush=True)
    if "fotos" in estado:
        estado = {**estado, "fotos": len(nuevas), **({"repetidas": quitadas} if quitadas else {})}
    return estado


def cosechar_biblioteca(existentes: dict, periodo: str, solo_enlaces: bool = False, solo_x: bool = False) -> int:
    """Descarga lo que hay en la Biblioteca: tuits, páginas e imágenes aún sin procesar y (si no `solo_enlaces`) las comunidades y usuarios de
    Reddit. Las candidatas llevan el estilo que indicaste: al clasificar se te proponen y confirmas con Enter."""
    fuentes = [s for s in leer_biblioteca()["fuentes"] if TIPOS[s["tipo"]][1]]
    enlaces = [s for s in fuentes if s["tipo"] in COSECHA_ENLACE and not s["estado"].get("ultima")]
    if solo_x:
        enlaces = []
    feeds = [] if (solo_enlaces or solo_x) else [s for s in fuentes if s["tipo"] in ("reddit_sub", "reddit_user")]
    cuentas = [] if solo_enlaces else [s for s in fuentes if s["tipo"] in ("x", "rss")]
    if not enlaces and not feeds and not cuentas:
        print("En la Biblioteca no hay nada que descargar: añade cuentas de X, comunidades de Reddit, tuits, páginas o imágenes (Instagram y TikTok no se leen solos).")
        return 0
    total = 0
    for k, s in enumerate(enlaces, 1):
        print(f"[enlace {k}/{len(enlaces)}] {texto_fuente(s)[:90]}  → {NOMBRE.get(s['estilo'], 'mercado')}", flush=True)
        try:
            nuevas = COSECHA_ENLACE[s["tipo"]](s["valor"], s["estilo"], s["id"], existentes)
            estado = {"ultima": ahora(), "fotos": len(nuevas)}
            print(f"  {len(nuevas)} fotos nuevas", flush=True)
        except Exception as e:  # noqa: BLE001
            nuevas, estado = {}, {"error": f"{type(e).__name__}: {e}"[:200]}
            print(f"  ✖ {estado['error']}", flush=True)
        estado = repetidas_fuera(nuevas, existentes, estado)
        registrar_resultado(nuevas, s["id"], estado)
        existentes.update(nuevas)
        total += len(nuevas)
    for k, s in enumerate(cuentas, 1):
        es_mercado = s["estilo"] == ESTILO_MERCADO
        print(f"[{'X' if s['tipo'] == 'x' else 'RSS'} {k}/{len(cuentas)}] {texto_fuente(s)}  → " + (f"mercado {MERCADOS.get(s.get('mercado'), '?')}" if es_mercado else NOMBRE[s["estilo"]]), flush=True)
        try:
            recoger = cosechar_cuenta_x if s["tipo"] == "x" else cosechar_rss
            nuevas, al_dia, info = recoger(s["valor"], None if es_mercado else s["estilo"], s["id"], existentes, s.get("mercado") if es_mercado else None)
            actualizar_candidatas(al_dia)
            estado = {"ultima": ahora(), "fotos": len(nuevas), **info}
            print(f"  {len(nuevas)} fotos nuevas", flush=True)
        except Exception as e:  # noqa: BLE001
            nuevas, estado = {}, {"error": f"{type(e).__name__}: {e}"[:200]}
            print(f"  ✖ {estado['error']}", flush=True)
        estado = repetidas_fuera(nuevas, existentes, estado)
        registrar_resultado(nuevas, s["id"], estado)
        existentes.update(nuevas)
        total += len(nuevas)
        time.sleep(1.5)
    for k, s in enumerate(feeds, 1):
        sub = s["tipo"] == "reddit_sub"
        etiqueta = f"r/{s['valor']}" if sub else f"u/{s['valor']}"
        print(f"[Reddit {k}/{len(feeds)}] {etiqueta}  → {NOMBRE.get(s['estilo'], 'mercado')}" + (f" (top {periodo})" if sub else " (sus publicaciones recientes)"), flush=True)
        url = (f"https://www.reddit.com/r/{s['valor']}/top/.rss?t={periodo}&limit=100" if sub
               else f"https://www.reddit.com/user/{s['valor']}/submitted/.rss?limit=100")
        r = cosechar_feed_reddit(url, etiqueta, periodo, sub, s["estilo"], s["id"], existentes)
        if r is None:
            print("  sin datos (privada, inexistente o bloqueada)", flush=True)
            registrar_resultado({}, s["id"], {"error": "Reddit no devolvió datos (privada, inexistente o bloqueada)"})
            time.sleep(20)
            continue
        nuevas, con_imagen, reset = r
        print(f"  {con_imagen} publicaciones con imagen directa, {len(nuevas)} nuevas", flush=True)
        registrar_resultado(nuevas, s["id"], repetidas_fuera(nuevas, existentes, {"ultima": ahora(), "fotos": len(nuevas), "con_imagen": con_imagen}))
        existentes.update(nuevas)
        total += len(nuevas)
        if k < len(feeds):
            time.sleep(max(reset, 15.0) + 3)
    return total


def cmd_cosechar(args):
    solo_enlaces = getattr(args, "solo_enlaces", False)
    if not args.reddit and not args.urls and not args.biblioteca:
        raise SystemExit("Indica de dónde cosechar, p. ej.:\n  python3 mercado.py cosechar --biblioteca\n  python3 mercado.py cosechar --reddit streetwear,malefashionadvice\n"
                         "  python3 mercado.py cosechar --urls mis_enlaces.txt")
    cands = leer_json(CANDIDATOS)
    antes = len(cands)
    if args.reddit:
        subs = [s.strip() for s in args.reddit.split(",") if s.strip()]
        for i, sub in enumerate(subs, 1):
            print(f"[{i}/{len(subs)}] r/{sub} (top {args.periodo})", flush=True)
            r = cosechar_feed_reddit(f"https://www.reddit.com/r/{sub}/top/.rss?t={args.periodo}&limit=100", f"r/{sub}", args.periodo, True, None, None, cands)
            if r is None:
                print("  sin datos (privada, inexistente o bloqueada)")
                time.sleep(20)
                continue
            nuevas, con_imagen, reset = r
            print(f"  {con_imagen} publicaciones con imagen directa, {len(nuevas)} nuevas", flush=True)
            anadir_candidatos(nuevas)   # tras cada comunidad: se puede interrumpir y reanudar
            cands.update(nuevas)
            if i < len(subs):
                time.sleep(max(reset, 15.0) + 3)
    if args.urls:
        cosechar_urls(args.urls, cands)
    if args.biblioteca:
        cosechar_biblioteca(cands, args.periodo, solo_enlaces, getattr(args, "solo_x", False))
    print(f"\nCandidatas: {len(cands)} ({len(cands) - antes} nuevas). Siguiente: en la app, pestaña «Clasificar» (o:  python3 mercado.py informe)")


# ---------------------------------------------------------------- app local (sin terminal)
def construir_cola(maximo: int = 0) -> list[dict]:
    """Candidatas sin etiquetar, con su sugerencia. Primero las que propusiste desde la Biblioteca (para confirmarlas con Enter); el resto en
    orden aleatorio (así el acierto del modelo que ves no tiene sesgo de orden)."""
    cands = leer_json(CANDIDATOS)
    completar_predicciones(cands)
    cands = leer_json(CANDIDATOS)
    et = leer_json(ETIQUETAS)
    pend = [c for c in cands.values() if "pred" in c and c["id"] not in et and not c.get("solo_mercado")]
    random.Random(1).shuffle(pend)
    pend.sort(key=lambda c: c.get("estilo_propuesto") not in ESTILOS)   # estable: las propuestas primero
    if maximo:
        pend = pend[:maximo]
    return [{"id": c["id"], "titulo": c.get("titulo", ""), "comunidad": c.get("comunidad", ""), "rank": c.get("rank"),
             "gate": c["gate"], "imagen_url": c.get("imagen_url"), "permalink": c.get("permalink"),
             "propuesto": [c["estilo_propuesto"], NOMBRE[c["estilo_propuesto"]]] if c.get("estilo_propuesto") in ESTILOS else None,
             "pred": [[e, p, NOMBRE[e]] for e, p in c["pred"]]} for c in pend]


TAREA = {"proc": None, "nombre": None, "inicio": None, "log": CACHE / "tarea.log"}
RE_SUB = re.compile(r"^[A-Za-z0-9_]{2,30}$")


def lanzar_tarea(nombre: str, argumentos: list[str]) -> bool:
    """Ejecuta `mercado.py <argumentos>` como proceso aparte (aislado: si falla, la app sigue) y deja su salida en un log."""
    with CANDADO:
        if TAREA["proc"] is not None and TAREA["proc"].poll() is None:
            return False
        CACHE.mkdir(exist_ok=True)
        TAREA["proc"] = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), *argumentos],
                                         stdout=open(TAREA["log"], "w", encoding="utf-8"), stderr=subprocess.STDOUT, cwd=AQUI)
        TAREA["nombre"], TAREA["inicio"] = nombre, ahora()
        return True


def estado_tarea() -> dict:
    p = TAREA["proc"]
    en_curso = p is not None and p.poll() is None
    log = ""
    if TAREA["log"].exists():
        lineas = TAREA["log"].read_text(encoding="utf-8", errors="ignore").splitlines()
        log = "\n".join(l for l in lineas if "warn" not in l.lower())[-3500:]
    return {"nombre": TAREA["nombre"], "en_curso": en_curso, "codigo": None if (en_curso or p is None) else p.returncode,
            "inicio": TAREA["inicio"], "log": log}


def resumen_estado() -> dict:
    cands, et = leer_json(CANDIDATOS), leer_json(ETIQUETAS)
    ok = [e for e in et.values() if e["decision"] == "ok"]
    medibles = [e for e in ok if e.get("origen") != "biblioteca"]   # lo que TÚ propusiste desde la Biblioteca no mide al modelo con fotos nuevas
    modelo, cambiada = None, False
    if MODELO.exists():
        m = cargar_modelo_estilos()
        modelo = {"cv_acc": round(m.cv_acc, 3), "cv_acc_fotos": round(m.cv_acc_fotos, 3), "n": m.n, "fecha": m.fecha, "lam": m.lam}
        cambiada = m.bib != hash_biblioteca()
    desde = [e for e in ok if modelo and e.get("t", "") > modelo["fecha"]]
    return {"estilos": [[e, NOMBRE[e], RASGOS[e]] for e in ESTILOS], "subs_por_defecto": SUBS_POR_DEFECTO,
            "candidatas": len(cands), "etiquetadas": len(ok), "descartadas": len(et) - len(ok),
            "pendientes": sum(1 for k, c in cands.items() if k not in et and not c.get("solo_mercado")),
            "fotos_mercado": sum(1 for c in cands.values() if c.get("solo_mercado")),
            "propuestas_pendientes": sum(1 for k, c in cands.items() if c.get("estilo_propuesto") and k not in et),
            "coincide": {"n": len(medibles), "k": sum(1 for e in medibles if e.get("sugerido") == e.get("estilo"))},
            "etiquetas_desde_modelo": len(desde), "modelo": modelo, "biblioteca_cambiada": cambiada, "tarea": estado_tarea(),
            "fuentes_biblioteca": sum(1 for s in leer_biblioteca()["fuentes"] if TIPOS[s["tipo"]][1]),
            "informe": datetime.fromtimestamp(INFORME_HTML.stat().st_mtime, timezone.utc).isoformat(timespec="seconds") if INFORME_HTML.exists() else None}


def periodo_valido(d: dict) -> str:
    periodo = d.get("periodo", "month")
    if periodo not in ("day", "week", "month", "year"):
        raise ValueError("periodo no válido")
    return periodo


def args_comunes(d: dict) -> list[str]:
    subs = [x.strip() for x in str(d.get("subs", "")).split(",") if x.strip()]
    if not subs or len(subs) > 15 or not all(RE_SUB.match(x) for x in subs):
        raise ValueError("comunidades de Reddit no válidas (letras, números y guion bajo; separadas por comas)")
    return ["--reddit", ",".join(subs), "--periodo", periodo_valido(d), "--biblioteca"]   # además, lo que tengas en la Biblioteca


META_FOTOS = 60   # objetivo cerrado de Víctor: 60 fotos confirmadas por estilo


def poner_etiqueta(cid: str, decision: str, estilo: str | None = None) -> bool:
    """Guarda tu decisión sobre una candidata («ok» con su estilo, o «descartada»). False si no existe o aún no tiene sugerencia del modelo."""
    c = leer_json(CANDIDATOS).get(cid)
    if c is None or "pred" not in c:
        return False

    def poner(et):
        et[cid] = {"decision": decision, "estilo": estilo if decision == "ok" else None, "sugerido": c["pred"][0][0], "prob": c["pred"][0][1],
                   "comunidad": c.get("comunidad"), "propuesto": c.get("estilo_propuesto"), "origen": "biblioteca" if c.get("estilo_propuesto") else "cola",
                   "imagen_url": c.get("imagen_url"), "permalink": c.get("permalink"), "t": ahora()}
    modificar_json(ETIQUETAS, poner)
    return True


def estado_biblioteca() -> dict:
    """Todo lo que pinta la pestaña Biblioteca: por estilo textos, fotos y cuántas fotos de entrenamiento hay (y cuánto acierta el modelo); y las fuentes."""
    b = leer_biblioteca()
    _, y, origen = datos_entrenamiento()
    cuenta = {e: {"galeria": 0, "clasificadas": 0, "biblioteca": 0} for e in ESTILOS}
    for estilo, o in zip(y.tolist(), origen.tolist()):
        cuenta[estilo][o] += 1
    modelo = cargar_modelo_estilos() if MODELO.exists() else None
    estilos = []
    for e in ESTILOS:
        estilos.append({"id": e, "nombre": NOMBRE[e], "rasgos": RASGOS[e], **b["estilos"][e], "n": cuenta[e], "total": sum(cuenta[e].values()),
                        "recall": (modelo.recall or {}).get(e) if modelo else None, "recall_fotos": (modelo.recall_fotos or {}).get(e) if modelo else None,
                        "n_modelo": (modelo.n_clase or {}).get(e) if modelo else None, "fotos": [p.stem for p in fotos_biblioteca(e)]})
    fuentes = [{"id": s["id"], "estilo": s["estilo"], "tipo": s["tipo"], "tipo_nombre": TIPOS[s["tipo"]][0], "descarga": TIPOS[s["tipo"]][1],
                "texto": texto_fuente(s), "url": url_fuente(s), "nombre": s.get("nombre"), "mercado": s.get("mercado"), "estado": s.get("estado", {})} for s in b["fuentes"]]
    return {"estilos": estilos, "fuentes": fuentes, "mercados": MERCADOS, "meta": META_FOTOS, "cambiada": bool(modelo) and modelo.bib != hash_biblioteca(),
            "modelo": {"lam": modelo.lam, "fecha": modelo.fecha, "cv_acc": modelo.cv_acc, "cv_acc_fotos": modelo.cv_acc_fotos} if modelo else None}


class ManejadorApp(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _env(self, cuerpo, tipo, codigo=200):
        cuerpo = cuerpo.encode("utf-8") if isinstance(cuerpo, str) else cuerpo
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, obj, codigo=200):
        self._env(json.dumps(obj, ensure_ascii=False), "application/json", codigo)

    def _imagen(self, cid):
        ruta = (IMG / f"{cid}.jpg").resolve()
        if re.fullmatch(r"[A-Za-z0-9_]+", cid) and ruta.is_file() and IMG.resolve() in ruta.parents:
            self._env(ruta.read_bytes(), "image/jpeg")
        else:
            self._env("no encontrada", "text/plain", 404)

    def _foto_biblioteca(self, clave):
        m = re.fullmatch(r"([a-z_]+)/([0-9a-f]{12})\.jpg", clave)
        ruta = BIB_IMG / m.group(1) / f"{m.group(2)}.jpg" if m and m.group(1) in ESTILOS else None
        if ruta is not None and ruta.is_file():
            self._env(ruta.read_bytes(), "image/jpeg")
        else:
            self._env("no encontrada", "text/plain", 404)

    def _local(self) -> bool:
        """La app solo atiende a tu navegador en este ordenador: rechaza otro `Host` (DNS rebinding) u `Origin` (otra página haciendo POST a localhost)."""
        ok_host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]") in ("localhost", "127.0.0.1", "::1")
        origen = self.headers.get("Origin")
        ok_origen = origen is None or (urlparse(origen).hostname or "") in ("localhost", "127.0.0.1", "::1")
        if not (ok_host and ok_origen):
            self._json({"error": "petición rechazada: la app solo responde a tu navegador en este ordenador"}, 403)
        return ok_host and ok_origen

    def do_GET(self):
        ruta, _, consulta = self.path.partition("?")
        if not self._local():
            return
        try:
            if ruta == "/":
                self._env((AQUI / "app.html").read_bytes(), "text/html; charset=utf-8")
            elif ruta == "/api/estado":
                self._json(resumen_estado())
            elif ruta == "/api/biblioteca":
                self._json(estado_biblioteca())
            elif ruta.startswith("/bib/"):
                self._foto_biblioteca(urllib.request.unquote(ruta[5:]))
            elif ruta == "/api/cola":
                m = re.search(r"max=(\d+)", consulta)
                self._json(construir_cola(int(m.group(1)) if m else 0))
            elif ruta == "/api/etiquetas":
                self._json(leer_json(ETIQUETAS))
            elif ruta.startswith("/img/"):
                self._imagen(urllib.request.unquote(ruta[5:]))
            elif ruta.startswith("/cache/img/") and ruta.endswith(".jpg"):   # miniaturas del informe
                self._imagen(urllib.request.unquote(ruta[11:-4]))
            elif ruta == "/informe_mercado.html" and INFORME_HTML.exists():
                self._env(INFORME_HTML.read_bytes(), "text/html; charset=utf-8")
            else:
                self._env("no encontrada", "text/plain", 404)
        except SystemExit as e:   # p. ej. falta el modelo: se lo contamos a la página en vez de romper
            self._json({"error": str(e)}, 409)
        except Exception as e:  # noqa: BLE001 -- un fallo no debe tumbar el servidor
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self):
        ruta, _, consulta = self.path.partition("?")
        if not self._local():
            return
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            if ruta == "/api/biblioteca/imagen":   # cuerpo = los bytes de la imagen (JPG, PNG o WebP)
                if not 0 < n <= 25_000_000:
                    raise ValueError("la imagen pesa demasiado (máximo 25 MB)")
                return self._json({"ok": True, **guardar_foto_biblioteca((re.search(r"estilo=([a-z_]+)", consulta) or [None, ""])[1], self.rfile.read(n))})
            d = json.loads(self.rfile.read(n or 2) or b"{}")
            if ruta == "/api/etiqueta":
                cola_ok = d["decision"] in ("ok", "descartada") and (d["decision"] == "descartada" or d["estilo"] in ESTILOS)
                assert cola_ok and poner_etiqueta(d["id"], d["decision"], d["estilo"])
                return self._json({"ok": True})
            if ruta == "/api/tarea":
                acc = d.get("accion")
                if acc == "analizar":
                    ok = lanzar_tarea("Analizar mercado", ["analizar", "--cosechar", *args_comunes(d)])
                elif acc == "buscar":
                    ok = lanzar_tarea("Buscar fotos con la Biblioteca", ["cosechar", "--biblioteca", "--periodo", periodo_valido(d)])
                elif acc == "informe":
                    ok = lanzar_tarea("Actualizar el informe", ["informe"])
                elif acc == "reentrenar":
                    ok = lanzar_tarea("Reentrenar el modelo", ["reentrenar"])
                else:
                    raise ValueError("acción desconocida")
                return self._json({"ok": ok, "motivo": None if ok else "ya hay una tarea en curso"}, 200 if ok else 409)
            if ruta == "/api/biblioteca/textos":
                return self._json({"ok": True, "frases": guardar_textos(d["estilo"], d.get("descripcion"), d.get("frases", []), d.get("referentes"), d.get("usar_texto"))})
            if ruta == "/api/biblioteca/borrar_foto":
                return self._json({"ok": borrar_foto_biblioteca(d["estilo"], d["id"])})
            if ruta == "/api/biblioteca/fuentes":
                res = anadir_fuentes(d["estilo"], d.get("texto", ""), d.get("plataforma", "x"), mercado=d.get("mercado"))
                res["descarga"] = bool(res["por_descargar"]) and lanzar_tarea(f"Descargar fotos de {res['por_descargar']} enlaces nuevos", ["cosechar", "--biblioteca", "--solo-enlaces"])
                return self._json({"ok": True, **res})
            if ruta == "/api/biblioteca/borrar_fuente":
                return self._json({"ok": borrar_fuente(d["id"])})
            if ruta == "/api/parar":
                with CANDADO:
                    p = TAREA["proc"]
                    if p is not None and p.poll() is None:
                        p.terminate()
                return self._json({"ok": True})
            self._env("no encontrada", "text/plain", 404)
        except (ValueError, KeyError, AssertionError, json.JSONDecodeError) as e:
            self._json({"error": str(e) or "petición no válida"}, 400)
        except Exception as e:  # noqa: BLE001
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def cmd_app(args):
    if not (AQUI / "app.html").exists():
        raise SystemExit("ERROR: falta app.html junto a mercado.py")
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", args.puerto), ManejadorApp)
    except OSError:
        print(f"La app ya está abierta en http://localhost:{args.puerto} (o el puerto está ocupado).")
        return
    print(f"App de «Analizar mercado» en  http://localhost:{args.puerto}   (cierra esta ventana para pararla)")
    if args.abrir:
        try:
            import webbrowser
            webbrowser.open(f"http://localhost:{args.puerto}")
        except Exception:  # noqa: BLE001
            pass
    srv.serve_forever()


def cmd_reentrenar(args):
    """Reentrena con las etiquetas nuevas y regenera el informe."""
    cmd_entrenar(args)
    cmd_informe(args)


# ---------------------------------------------------------------- informe («¿qué está de moda ahora mismo?»)
def detectar_idioma(texto: str | None) -> str | None:
    """«es» o «en» según las palabras de un título (los feeds RSS dicen un idioma que no siempre es el real); None si no hay pistas suficientes."""
    if not texto:
        return None
    palabras = re.findall(r"[a-záéíóúüñ]+", texto.lower())
    es, en = sum(p in _PALABRAS["es"] for p in palabras), sum(p in _PALABRAS["en"] for p in palabras)
    es += 2 * len(re.findall(r"[áéíóúñ¿¡]", texto.lower()))
    if max(es, en) < 2 or es == en:
        return None
    return "es" if es > en else "en"


def idioma_de(c: dict) -> str | None:
    return detectar_idioma(c.get("titulo")) if c.get("fuente") == "rss" else c.get("idioma")


def mercado_de(c: dict) -> str | None:
    """A qué mercado pertenece una candidata: el de su fuente (cuentas con etiqueta) o, en las comunidades de Reddit, el de habla inglesa."""
    return c.get("mercado") or (MERCADO_REDDIT if c.get("fuente") == "reddit" else None)


def peso_foto(c: dict, ahora_dt: datetime, vida_media: float) -> float:
    """Cuánto pesa una foto en el informe: popularidad × recencia. Popularidad: en X, la tasa de interacción del post (likes + 2·reposts frente a los
    seguidores del autor, para que una cuenta enorme no tape a una pequeña); en Reddit, el puesto en el «top»."""
    try:
        edad = max(0.0, (ahora_dt - datetime.fromisoformat(c["fecha"].replace("Z", "+00:00"))).total_seconds() / 86400)
    except Exception:  # noqa: BLE001
        edad = 0.0
    if c.get("likes") is not None:
        tasa = ((c.get("likes") or 0) + 2 * (c.get("reposts") or 0)) / max(c.get("seguidores_autor") or 0, 1000)
        popularidad = 0.3 + 0.7 * min(1.0, 100.0 * tasa)
    else:
        popularidad = 1.0 / (1.0 + math.log2(c["rank"])) if c.get("rank") else 0.6
    return popularidad * 0.5 ** (edad / vida_media)


def calcular_informe(args):
    """«¿Qué está de moda ahora?» por mercado. Una foto cuenta si es de una fuente de mercado (o de Reddit) y tiene estilo confirmado por ti o, sin
    revisar, parece una persona con ropa (la puerta CLIP); las propuestas de la Biblioteca solo si las confirmas. (El filtro «sirve / no sirve» aprendido
    de tus decisiones NO se usa aquí: sale de fotos de Reddit y de páginas y está mal calibrado para fotos de marcas y medios; solo ordena las hojas.)"""
    cands = leer_json(CANDIDATOS)
    completar_predicciones(cands)
    cands = leer_json(CANDIDATOS)
    et = leer_json(ETIQUETAS)
    modelo = cargar_modelo_estilos()
    ahora_dt = datetime.now(timezone.utc)
    dias = getattr(args, "dias", 45)
    grupos: dict = {}
    descartadas, fuera_idioma = 0, {}
    for c in cands.values():
        mercado = mercado_de(c)
        lab = et.get(c["id"])
        if "pred" not in c or not mercado or c.get("solo_entrenamiento") or (c.get("solo_si_confirmada") and not lab):
            continue
        try:
            if (ahora_dt - datetime.fromisoformat(c["fecha"].replace("Z", "+00:00"))).days > dias:
                continue
        except Exception:  # noqa: BLE001
            pass
        if lab and lab["decision"] == "descartada":
            descartadas += 1
            continue
        idioma = idioma_de(c)
        if idioma and MERCADO_IDIOMAS.get(mercado) and idioma not in MERCADO_IDIOMAS[mercado]:
            fuera_idioma[mercado] = fuera_idioma.get(mercado, 0) + 1   # p. ej. un post en inglés de una cuenta asignada a España
            continue
        if lab:
            estilo, conf, revisada = lab["estilo"], 1.0, True
        else:
            if c["gate"] < UMBRAL_PUERTA:
                descartadas += 1
                continue
            estilo, conf, revisada = c["pred"][0][0], c["pred"][0][1], False
        g = grupos.setdefault(mercado, {"peso": {e: 0.0 for e in ESTILOS}, "n": {e: 0 for e in ESTILOS}, "rev": {e: 0 for e in ESTILOS}, "ej": {e: [] for e in ESTILOS},
                                        "fuentes": {}, "idiomas": {}, "ubicaciones": {}, "usadas": 0})
        w = peso_foto(c, ahora_dt, args.vida_media)
        g["peso"][estilo] += w
        g["n"][estilo] += 1
        g["rev"][estilo] += int(revisada)
        g["ej"][estilo].append((w * conf, c["id"], conf, revisada))
        g["fuentes"][c.get("comunidad", "?")] = g["fuentes"].get(c.get("comunidad", "?"), 0) + 1
        if idioma:
            g["idiomas"][idioma] = g["idiomas"].get(idioma, 0) + 1
        if c.get("ubicacion_autor"):
            g["ubicaciones"][c["ubicacion_autor"]] = g["ubicaciones"].get(c["ubicacion_autor"], 0) + 1
        g["usadas"] += 1
    historial = leer_json(HISTORIAL)
    hoy = ahora_dt.date().isoformat()
    previo = max((f for f in historial if f <= (ahora_dt.date() - timedelta(days=3)).isoformat()), default=None)   # el último informe de hace ≥ 3 días
    mercados = {}
    for mercado, g in sorted(grupos.items(), key=lambda kv: -kv[1]["usadas"]):
        total = sum(g["peso"].values()) or 1.0
        maximo = max(g["peso"].values()) or 1.0
        antes = (historial.get(previo) or {}).get(mercado) if previo else None
        tendencias = []
        for e in sorted(ESTILOS, key=lambda k: -g["peso"][k]):
            cuota = g["peso"][e] / total
            ej = []
            for _, cid, conf, revisada in sorted(g["ej"][e], reverse=True)[:4]:
                c = cands[cid]
                ej.append({"id": cid, "comunidad": c.get("comunidad", ""), "puesto": c.get("rank"), "confianza": round(conf, 2), "revisada": revisada,
                           "autor": c.get("autor"), "idioma": c.get("idioma"), "likes": c.get("likes"), "fecha": c.get("fecha"), "enlace": c.get("permalink")})
            tendencias.append({
                "estilo": e, "nombre": NOMBRE[e], "cuota": round(cuota, 4), "intensidad": round(g["peso"][e] / maximo, 3), "n_fotos": g["n"][e],
                "n_revisadas_por_ti": g["rev"][e], "grupo_estilo_detectado": GRUPOS_ERP[e],
                "cambio_pp": round(100 * (cuota - antes[e]), 1) if antes and e in antes else None,
                "descripcion": "",   # la redacta el LLM con las definiciones del estilo (Experimento B, §6.2); pendiente
                "ejemplos": ej})
        mercados[mercado] = {"nombre": MERCADOS.get(mercado, mercado), "fotos_usadas": g["usadas"], "fuentes": g["fuentes"], "idiomas": g["idiomas"],
                             "fuera_de_idioma": fuera_idioma.get(mercado, 0),
                             "ubicaciones": dict(sorted(g["ubicaciones"].items(), key=lambda kv: -kv[1])[:5]), "comparado_con": previo if antes else None,
                             "tendencias": tendencias}
    historial[hoy] = {m: {t["estilo"]: t["cuota"] for t in v["tendencias"]} for m, v in mercados.items()}
    guardar_json(HISTORIAL, {f: historial[f] for f in sorted(historial)[-60:]})
    principal = "ES" if "ES" in mercados else (next(iter(mercados)) if mercados else None)
    return {"fecha_analisis": ahora(), "principal": principal, "mercados": mercados, "dias": dias, "vida_media_dias": args.vida_media,
            "fotos_usadas": sum(v["fotos_usadas"] for v in mercados.values()), "fotos_descartadas": descartadas,
            "acierto_modelo_validacion_cruzada": round(modelo.cv_acc, 3), "modelo_fecha": modelo.fecha,
            "tendencias": mercados[principal]["tendencias"] if principal else [], "fuentes": mercados[principal]["fuentes"] if principal else {},
            "aviso": "El mercado de cada foto es el que asignas a su fuente (cuenta de X o comunidad); idioma y ubicación se muestran para comprobarlo. "
                     "Son cuentas concretas, no el mercado entero."}


def fmt_n(n) -> str:
    """1234 → 1,2 K."""
    if n is None:
        return "–"
    return f"{n / 1000:.1f} K".replace(".", ",") if n >= 1000 else str(n)


def html_informe(inf: dict) -> str:
    esc = lambda s: html.escape(str(s))  # noqa: E731
    mercados = inf["mercados"]
    ahora_dt = datetime.now(timezone.utc)

    def edad_texto(iso):
        try:
            d = (ahora_dt - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
            return "hoy" if d <= 0 else f"hace {d} d"
        except Exception:  # noqa: BLE001
            return ""

    def seccion(clave, mk):
        filas = mk["tendencias"]
        barras = "".join(
            f'<div class="fila" tabindex="0" role="img" data-n="{esc(t["nombre"])}" data-c="{100 * t["cuota"]:.0f}" data-f="{t["n_fotos"]}" data-r="{t["n_revisadas_por_ti"]}" '
            f'aria-label="{esc(t["nombre"])}: {100 * t["cuota"]:.0f} % del total, {t["n_fotos"]} fotos">'
            f'<span class="et">{esc(t["nombre"])}</span><span class="pista"><span class="barra" style="width:{(0.9 * 100 * t["intensidad"]) if t["n_fotos"] else 0:.1f}%"></span>'
            f'<span class="val">{100 * t["cuota"]:.0f} %</span>'
            + (f'<span class="cambio {"sube" if t["cambio_pp"] > 0 else "baja" if t["cambio_pp"] < 0 else ""}">{"▲" if t["cambio_pp"] > 0 else "▼" if t["cambio_pp"] < 0 else "="} {abs(t["cambio_pp"]):.1f} pp</span>'
               if t["cambio_pp"] is not None else "") + '</span></div>' for t in filas)
        def cambio_txt(t):
            return "" if t["cambio_pp"] is None else "%+.1f pp" % t["cambio_pp"]
        tabla = "".join(f'<tr><td>{esc(t["nombre"])}</td><td>{100 * t["cuota"]:.1f} %</td><td>{cambio_txt(t)}</td><td>{t["n_fotos"]}</td>'
                        f'<td>{t["n_revisadas_por_ti"]}</td><td>{esc(", ".join(t["grupo_estilo_detectado"]))}</td></tr>' for t in filas)
        ejemplos = ""
        for t in filas:
            if not t["ejemplos"]:
                continue
            miniaturas = "".join(
                f'<figure><img src="cache/img/{esc(x["id"])}.jpg" alt="ejemplo de {esc(t["nombre"])}"><figcaption>'
                + (f'{esc(x["autor"])} · {esc(x["idioma"] or "?")} · ♥ {fmt_n(x["likes"])} · {edad_texto(x["fecha"])}' if x.get("autor") else
                   f'{esc(x["comunidad"])}{" · puesto " + str(x["puesto"]) if x["puesto"] else ""}')
                + (" · revisada" if x["revisada"] else f' · sugerida {round(100 * x["confianza"])} %') + '</figcaption></figure>' for x in t["ejemplos"])
            ejemplos += f'<h3>{esc(t["nombre"])} <small>{100 * t["cuota"]:.0f} % · {t["n_fotos"]} fotos</small></h3><div class="gal">{miniaturas}</div>'
        idiomas = mk["idiomas"]
        total_i = sum(idiomas.values()) or 1
        donde = (f'<p class="donde"><b>De dónde:</b> {esc(mk["nombre"])} · {mk["fotos_usadas"]} fotos de {len(mk["fuentes"])} fuentes'
                 + (f' · idioma de los posts: {", ".join(f"{esc(i)} {100 * n / total_i:.0f} %" for i, n in sorted(idiomas.items(), key=lambda kv: -kv[1])[:3])}' if idiomas else "")
                 + (f' · ubicación declarada de las cuentas: {", ".join(esc(u) for u in mk["ubicaciones"])}' if mk["ubicaciones"] else "")
                 + (f' · {mk["fuera_de_idioma"]} fotos descartadas por estar en otro idioma ({esc(", ".join(sorted(MERCADO_IDIOMAS.get(clave, set()))))} es lo que cuenta aquí)' if mk.get("fuera_de_idioma") else "")
                 + (f' · cambios frente al informe del {esc(mk["comparado_con"])}' if mk["comparado_con"] else " · aún sin informe anterior con el que comparar («sube / baja» aparece en cuanto haya uno de hace ≥ 3 días)")
                 + '</p>')
        return (f'<section class="mercado" id="m-{esc(clave)}" data-m="{esc(clave)}"{"" if clave == inf["principal"] else " hidden"}>{donde}'
                f'<figure class="graf"><h2>Cuota de cada estilo (% del total ponderado por popularidad y recencia)</h2>{barras}'
                f'<p style="margin:10px 0 0"><button class="conmuta" aria-expanded="false">Ver como tabla</button></p>'
                f'<table><thead><tr><th>Estilo</th><th>Cuota</th><th>Cambio</th><th>Fotos</th><th>Revisadas por ti</th><th>Grupo(s) del ERP</th></tr></thead><tbody>{tabla}</tbody></table></figure>'
                f'{ejemplos}<p class="pie">Fuentes: {esc(", ".join(f"{k} ({v})" for k, v in list(mk["fuentes"].items())[:14]))}.</p></section>')

    pestanas = "".join(f'<button role="tab" data-m="{esc(k)}" aria-selected="{"true" if k == inf["principal"] else "false"}">{esc(v["nombre"])} <small>{v["fotos_usadas"]}</small></button>'
                       for k, v in mercados.items())
    secciones = "".join(seccion(k, v) for k, v in mercados.items()) or '<p class="aviso">Todavía no hay fotos de fuentes de mercado: añade cuentas en la Biblioteca y pulsa «Analizar mercado».</p>'
    return f"""<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qué está de moda ahora</title>
<style>
:root{{--superficie:#fcfcfb;--plano:#f9f9f7;--tinta:#0b0b0b;--tinta2:#52514e;--apagado:#898781;--linea:#e1e0d9;--base:#c3c2b7;--serie:#2a78d6;--aviso:#f3ede0;--sube:#1d7a46;--baja:#b3402f}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--superficie:#1a1a19;--plano:#0d0d0d;--tinta:#fff;--tinta2:#c3c2b7;--linea:#2c2c2a;--base:#383835;--serie:#3987e5;--aviso:#2a2620;--sube:#58c486;--baja:#f08070}}}}
:root[data-theme="dark"]{{--superficie:#1a1a19;--plano:#0d0d0d;--tinta:#fff;--tinta2:#c3c2b7;--linea:#2c2c2a;--base:#383835;--serie:#3987e5;--aviso:#2a2620;--sube:#58c486;--baja:#f08070}}
body{{margin:0;background:var(--plano);color:var(--tinta);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:760px;margin:0 auto;padding:20px 16px 48px}}
h1{{font-size:1.35rem;margin:0}}h2{{font-size:1rem;margin:0 0 2px}}h3{{font-size:.95rem;margin:18px 0 6px}}h3 small{{color:var(--tinta2);font-weight:400}}
.sub{{color:var(--tinta2);margin:4px 0 12px}}.aviso{{background:var(--aviso);border-radius:10px;padding:10px 12px;font-size:.85rem;color:var(--tinta2);margin:0 0 14px}}
.pestanas{{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px}}
.pestanas button{{font:inherit;font-size:.88rem;background:var(--superficie);border:1px solid var(--linea);color:var(--tinta2);border-radius:999px;padding:5px 12px;cursor:pointer}}
.pestanas button[aria-selected="true"]{{border-color:var(--serie);color:var(--tinta);font-weight:600}}.pestanas small{{color:var(--apagado)}}
.donde{{font-size:.84rem;color:var(--tinta2);margin:0 0 10px}}
figure.graf{{background:var(--superficie);border:1px solid var(--linea);border-radius:12px;padding:14px 16px;margin:0 0 8px}}
.fila{{display:grid;grid-template-columns:130px 1fr;align-items:center;gap:10px;height:30px;outline-offset:2px;border-radius:6px}}
.et{{color:var(--tinta2);font-size:.86rem;white-space:nowrap}}.val{{font-weight:600;margin-left:8px;white-space:nowrap}}
.cambio{{margin-left:8px;font-size:.76rem;color:var(--tinta2);white-space:nowrap}}.cambio.sube{{color:var(--sube)}}.cambio.baja{{color:var(--baja)}}
.pista{{border-left:1px solid var(--base);height:20px;display:flex;align-items:center}}
.barra{{display:block;height:20px;background:var(--serie);border-radius:0 4px 4px 0;transition:filter .1s}}
.fila:hover .barra,.fila:focus-visible .barra{{filter:brightness(1.12)}}
.conmuta{{font:inherit;font-size:.82rem;background:none;border:1px solid var(--linea);color:var(--tinta2);border-radius:8px;padding:3px 10px;cursor:pointer}}
table{{width:100%;border-collapse:collapse;font-size:.86rem;display:none;margin-top:10px}}table.ver{{display:table}}
th,td{{text-align:left;padding:5px 6px;border-bottom:1px solid var(--linea)}}td:nth-child(n+2):nth-child(-n+5){{font-variant-numeric:tabular-nums}}
.gal{{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px}}figure{{margin:0}}.gal img{{width:100%;aspect-ratio:3/4;object-fit:cover;border-radius:8px;background:var(--linea)}}
figcaption{{font-size:.72rem;color:var(--tinta2);margin-top:2px;overflow-wrap:anywhere}}
#tip{{position:fixed;pointer-events:none;background:var(--superficie);border:1px solid var(--linea);border-radius:8px;padding:6px 9px;font-size:.8rem;box-shadow:0 4px 14px rgba(0,0,0,.15);display:none;z-index:5}}
#tip b{{font-size:.95rem;display:block}}
.pie{{color:var(--apagado);font-size:.78rem;margin-top:18px}}
</style><main>
<h1>Qué está de moda ahora mismo</h1>
<p class="sub">{inf["fotos_usadas"]} fotos de los últimos {inf["dias"]} días · {esc(inf["fecha_analisis"][:10])} · prototipo</p>
<div class="pestanas" role="tablist" aria-label="Mercado">{pestanas}</div>
<p class="aviso"><b>Prototipo.</b> {esc(inf["aviso"])} Cada foto pesa por su popularidad (X: interacciones frente a seguidores; Reddit: puesto en el «top») y lo reciente que es.
Sin revisar, el estilo es la predicción del modelo ({100 * inf["acierto_modelo_validacion_cruzada"]:.0f} % en validación cruzada; con fotos nuevas será menor); se ignoran las que no parecen una persona con ropa.</p>
{secciones}
<p class="pie">Vida media de la recencia: {inf["vida_media_dias"]} días. Descartadas por no ser un outfit o por ti: {inf["fotos_descartadas"]}. Las imágenes son de personas reales y se quedan en tu equipo (no las publiques).</p></main><div id="tip"></div>
<script>
const tip=document.getElementById('tip');
function mostrar(f,x,y){{tip.replaceChildren();const b=document.createElement('b');b.textContent=f.dataset.c+' %';const s=document.createElement('span');
  s.textContent=f.dataset.n+' · '+f.dataset.f+' fotos ('+f.dataset.r+' revisadas por ti)';tip.append(b,s);tip.style.display='block';
  tip.style.left=Math.min(x+12,innerWidth-tip.offsetWidth-8)+'px';tip.style.top=(y+12)+'px'}}
document.querySelectorAll('.fila').forEach(f=>{{f.addEventListener('pointermove',e=>mostrar(f,e.clientX,e.clientY));f.addEventListener('pointerleave',()=>tip.style.display='none');
  f.addEventListener('focus',()=>{{const r=f.getBoundingClientRect();mostrar(f,r.left+r.width/2,r.top)}});f.addEventListener('blur',()=>tip.style.display='none')}});
document.querySelectorAll('.conmuta').forEach(bt=>bt.addEventListener('click',()=>{{const tb=bt.closest('figure').querySelector('table');
  const v=tb.classList.toggle('ver');bt.textContent=v?'Ocultar tabla':'Ver como tabla';bt.setAttribute('aria-expanded',v)}}));
document.querySelectorAll('.pestanas button').forEach(b=>b.addEventListener('click',()=>{{
  document.querySelectorAll('.pestanas button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('section.mercado').forEach(s=>s.hidden=s.dataset.m!==b.dataset.m)}}));
</script></html>"""


def cmd_informe(args):
    inf = calcular_informe(args)
    guardar_json(INFORME_JSON, inf)
    INFORME_HTML.write_text(html_informe(inf), encoding="utf-8")
    print(f"\nQué está de moda (de {inf['fotos_usadas']} fotos; {inf['fotos_descartadas']} descartadas):")
    for clave, mk in inf["mercados"].items():
        print(f"\n  === {mk['nombre']}: {mk['fotos_usadas']} fotos de {len(mk['fuentes'])} fuentes ===")
        for t in mk["tendencias"]:
            cambio = "" if t["cambio_pp"] is None else f" ({t['cambio_pp']:+.1f} pp)"
            print(f"  {t['nombre']:20s} {100 * t['cuota']:4.0f} %{cambio:11s} {'█' * int(30 * t['intensidad']):30s} {t['n_fotos']:3d} fotos ({t['n_revisadas_por_ti']} revisadas)")
    print(f"\nInforme: {INFORME_HTML}\n         {INFORME_JSON}")


def motivo_reentrenar() -> str | None:
    """Por qué conviene reentrenar antes de analizar (o None si el modelo está al día)."""
    if not MODELO.exists():
        return "todavía no hay modelo"
    m = cargar_modelo_estilos()
    if m.bib != hash_biblioteca():
        return "has cambiado la Biblioteca (fotos o frases)"
    nuevas = sum(1 for e in leer_json(ETIQUETAS).values() if e.get("decision") == "ok" and e.get("t", "") > m.fecha)
    return f"has confirmado {nuevas} fotos desde el último entrenamiento" if nuevas >= 10 else None


def cmd_analizar(args):
    """El «botón»: [reentrenar si hace falta] → cosechar (opcional) → clasificar → informe."""
    motivo = motivo_reentrenar()
    if motivo:
        print(f"Antes de analizar reentreno el modelo: {motivo}.\n", flush=True)
        cmd_entrenar(args)
        print()
    if args.cosechar:
        cmd_cosechar(args)
    cmd_informe(args)


# ---------------------------------------------------------------- revisar desde el móvil (hojas numeradas por chat)
LETRA = {"old_money": "O", "lujo_ostentoso": "L", "clasico_tradicional": "C", "urbano": "U", "bohemio": "B", "alternativo_geek": "G", "convencional": "V"}
REVISION = CACHE / "revision_movil.json"   # {"C07": {"id": ..., "estado": "mostrada|ok|descartada"}}: para contestar con los números de las hojas
HOJAS = CACHE / "hojas"


def _fuente_letra(tam: int):
    from PIL import ImageFont
    for ruta in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tam)
    return ImageFont.load_default()


def puntuar_sirve(candidatas: list[dict]) -> dict:
    """Probabilidad de que cada candidata te sirva, con un filtro aprendido de TODAS tus decisiones (confirmadas frente a descartadas) sobre CLIP.
    Solo ordena las hojas: no esconde nada. Sin decisiones suficientes devuelve {} (todas valen lo mismo)."""
    from sklearn.linear_model import LogisticRegression
    et = leer_json(ETIQUETAS)
    ids = [k for k in et if (IMG / f"{k}.jpg").exists()]
    y = np.array([1 if et[k]["decision"] == "ok" else 0 for k in ids])
    if not candidatas or y.sum() < 10 or (1 - y).sum() < 10:
        return {}
    clf = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(embeber_imagenes([IMG / f"{k}.jpg" for k in ids], "candidatos"), y)
    Xc = embeber_imagenes([IMG / f"{c['id']}.jpg" for c in candidatas], "candidatos")
    return dict(zip([c["id"] for c in candidatas], clf.predict_proba(Xc)[:, 1].tolist()))


def muestra_de_mercado(cands: dict, et: dict, vistas: set, mercado: str, maximo: int) -> list:
    """Fotos de un mercado, al azar, que aún no has juzgado ni visto y que contarían en el informe (persona con ropa, idioma del mercado, recientes)."""
    ahora_dt = datetime.now(timezone.utc)
    pool = []
    for c in sorted(cands.values(), key=lambda c: c["id"]):
        if mercado_de(c) != mercado or "pred" not in c or c["id"] in et or c["id"] in vistas or c.get("solo_entrenamiento") or c["gate"] < UMBRAL_PUERTA:
            continue
        idioma = idioma_de(c)
        if idioma and MERCADO_IDIOMAS.get(mercado) and idioma not in MERCADO_IDIOMAS[mercado]:
            continue
        try:
            if (ahora_dt - datetime.fromisoformat(c["fecha"].replace("Z", "+00:00"))).days > DIAS_MAX_MERCADO:
                continue
        except Exception:  # noqa: BLE001
            pass
        pool.append(c)
    random.Random(11).shuffle(pool)
    return pool[:maximo]


def cmd_hojas(args):
    """Hojas de contactos (3×3, fotos grandes, cada una con su código C07, L12…) de las propuestas de un estilo que aún no has visto, para
    enseñártelas por el chat desde el móvil. Se reparten entre las fuentes para que una hoja no sea toda de la misma.
    Con --mercado ES: una muestra AL AZAR de fotos de ese mercado (códigos M01…) sin enseñar lo que predice el modelo, para medir su acierto real con `medir`."""
    from PIL import ImageDraw
    if bool(args.estilo) == bool(args.mercado):
        raise SystemExit("ERROR: indica --estilo (propuestas de un estilo) o --mercado (muestra para medir el acierto del modelo)")
    estilo, letra = args.estilo, ("M" if args.mercado else LETRA[args.estilo])
    cands = leer_json(CANDIDATOS)
    completar_predicciones(cands)
    cands, et, rev = leer_json(CANDIDATOS), leer_json(ETIQUETAS), leer_json(REVISION)
    vistas = {v["id"] for v in rev.values()}
    por, p_sirve, elegidas = {}, {}, []
    if args.mercado:
        elegidas = muestra_de_mercado(cands, et, vistas, args.mercado, args.max)
    for c in sorted(cands.values(), key=lambda c: c["id"]):
        if not args.mercado and c.get("estilo_propuesto") == estilo and "pred" in c and c["id"] not in et and c["id"] not in vistas:
            por.setdefault(c.get("comunidad") or "?", []).append(c)
    # lo que ya has contestado orienta lo siguiente: (a) la tasa de aciertos de cada fuente (suavizada: una fuente sin probar vale 0,5) y
    # (b) un filtro aprendido de tus decisiones. Puntuación = media de ambas; tope por fuente para que una hoja no sea toda de la misma.
    juzgadas = {}
    for v in rev.values():
        if v["estado"] in ("ok", "descartada") and v["id"] in cands:
            a = juzgadas.setdefault(cands[v["id"]].get("comunidad") or "?", [0, 0])
            a[0] += v["estado"] == "ok"
            a[1] += 1
    tasa = {fuente: (juzgadas.get(fuente, [0, 0])[0] + 1.0) / (juzgadas.get(fuente, [0, 0])[1] + 2.0) for fuente in por}
    todas = [c for lista in por.values() for c in lista]
    p_sirve = puntuar_sirve(todas) if not args.mercado else {}
    puntuacion = {c["id"]: 0.5 * tasa[c.get("comunidad") or "?"] + 0.5 * p_sirve.get(c["id"], 0.5) for c in todas}
    todas.sort(key=lambda c: (-puntuacion[c["id"]], c["id"]))
    tope, usadas = max(4, math.ceil(0.6 * args.max)), {}
    # exploración: un tercio de la tanda sale de fuentes con menos de 4 respuestas tuyas (si no, siempre ganarían las ya probadas y no veríamos nada nuevo)
    nuevas_fuentes = [c for c in todas if juzgadas.get(c.get("comunidad") or "?", [0, 0])[1] < 4] if not args.mercado else []
    cupo = math.ceil(args.max / 3) if nuevas_fuentes else 0
    por_fuente_explorada = {}
    for c in nuevas_fuentes:
        fuente = c.get("comunidad") or "?"
        if len(elegidas) < cupo and por_fuente_explorada.get(fuente, 0) < max(2, math.ceil(cupo / 3)):
            elegidas.append(c)
            por_fuente_explorada[fuente] = por_fuente_explorada.get(fuente, 0) + 1
            usadas[fuente] = usadas.get(fuente, 0) + 1
    elegidos_ids = {c["id"] for c in elegidas}
    for c in todas:
        fuente = c.get("comunidad") or "?"
        if c["id"] not in elegidos_ids and usadas.get(fuente, 0) < tope and len(elegidas) < args.max:
            elegidas.append(c)
            usadas[fuente] = usadas.get(fuente, 0) + 1
    if p_sirve and elegidas:
        print(f"Filtro aprendido de tus decisiones: probabilidad media de que te sirvan {100 * np.mean([p_sirve[c['id']] for c in elegidas]):.0f} % en las elegidas "
              f"(frente a {100 * np.mean(list(p_sirve.values())):.0f} % en todo lo pendiente)")
    if not elegidas:
        print("No hay fotos nuevas para enseñar." if args.mercado else f"No hay propuestas nuevas de {NOMBRE[estilo]} para enseñar.")
        return
    n = max([int(k[len(letra):]) for k in rev if k.startswith(letra)] or [0])
    HOJAS.mkdir(parents=True, exist_ok=True)
    lado, hueco, fuente, pequena = 420, 6, _fuente_letra(40), _fuente_letra(17)
    for ini in range(0, len(elegidas), args.por_hoja):
        grupo = elegidas[ini:ini + args.por_hoja]
        cols = 3
        filas = math.ceil(len(grupo) / cols)
        hoja = Image.new("RGB", (cols * lado + (cols + 1) * hueco, filas * lado + (filas + 1) * hueco), (24, 24, 24))
        codigos = []
        for k, c in enumerate(grupo):
            n += 1
            codigo = f"{letra}{n:02d}"
            codigos.append(codigo)
            rev[codigo] = {"id": c["id"], "estado": "mostrada", "p": round(p_sirve[c["id"]], 3) if c["id"] in p_sirve else None}
            im = Image.open(IMG / f"{c['id']}.jpg").convert("RGB")
            im.thumbnail((lado, lado))
            x, y = hueco + (k % cols) * (lado + hueco), hueco + (k // cols) * (lado + hueco)
            hoja.paste(im, (x + (lado - im.width) // 2, y + (lado - im.height) // 2))
            d = ImageDraw.Draw(hoja)
            d.rectangle([x, y, x + 96, y + 52], fill=(0, 0, 0))
            d.text((x + 8, y + 3), codigo, fill=(255, 255, 255), font=fuente)
            d.rectangle([x, y + lado - 26, x + lado, y + lado], fill=(0, 0, 0))
            d.text((x + 6, y + lado - 24), (c.get("comunidad") or "")[:34], fill=(220, 220, 220), font=pequena)
        ruta = HOJAS / f"{codigos[0]}-{codigos[-1]}.jpg"
        hoja.save(ruta, quality=86)
        print(f"{ruta}  ({codigos[0]}–{codigos[-1]}; fuentes: " + ", ".join(sorted({c.get('comunidad') or '?' for c in grupo})) + ")")
    guardar_json(REVISION, rev)


def _codigos(texto: str) -> list[str]:
    """«C01 C04-C06, L2» → ['C01', 'C04', 'C05', 'C06', 'L02']."""
    salida = []
    for tramo in re.split(r"[\s,;]+", texto or ""):
        if not tramo:
            continue
        m = re.fullmatch(r"([A-Za-z])0*(\d+)(?:-[A-Za-z]?0*(\d+))?", tramo)
        if not m:
            raise SystemExit(f"ERROR: no entiendo «{tramo}» (usa códigos como C07 o rangos C01-C09)")
        a, b = int(m.group(2)), int(m.group(3) or m.group(2))
        salida += [f"{m.group(1).upper()}{i:02d}" for i in range(a, b + 1)]
    return salida


def cmd_resolver(args):
    """Aplica tus respuestas de las hojas: lo que dices que está bien se confirma con el estilo propuesto; el resto de las revisadas se descarta."""
    rev = leer_json(REVISION)
    buenas, revisadas = set(_codigos(args.buenas)), _codigos(args.revisadas)
    desconocidos = [k for k in list(buenas) + revisadas if k not in rev]
    if desconocidos:
        raise SystemExit("ERROR: códigos que no se han enseñado: " + ", ".join(sorted(set(desconocidos))))
    cands = leer_json(CANDIDATOS)
    cuenta = {"ok": 0, "descartada": 0}
    for codigo in dict.fromkeys(revisadas + sorted(buenas)):
        cid = rev[codigo]["id"]
        decision = "ok" if codigo in buenas else "descartada"
        estilo = (cands.get(cid) or {}).get("estilo_propuesto")
        if poner_etiqueta(cid, decision, estilo):
            rev[codigo]["estado"] = decision
            cuenta[decision] += 1
    guardar_json(REVISION, rev)
    print(f"Aplicado: {cuenta['ok']} confirmadas con su estilo y {cuenta['descartada']} descartadas.")


MEDIDAS = DATOS / "medida_real.json"   # historial de «acierto real del modelo con fotos nuevas de mercado juzgadas por ti»


def cmd_medir(args):
    """Aplica tus respuestas a las hojas de mercado y calcula el ACIERTO REAL del modelo con esas fotos nuevas. Respuestas: `1C 2V 3x`: número de la foto y
    letra del estilo (O Old Money, L Lujo, C Clásico, U Urbano, B Bohemio, G Geek, V Convencional) o `x` = no sirve / no es un outfit. Lo no nombrado se ignora."""
    rev, cands = leer_json(REVISION), leer_json(CANDIDATOS)
    por_letra = {v: k for k, v in LETRA.items()}
    respuestas = re.findall(r"(?:M)?0*(\d+)\s*[=:]?\s*([A-Za-z])(?![A-Za-z])", args.respuestas.replace(",", " "))
    if not respuestas:
        raise SystemExit("ERROR: no entiendo las respuestas; usa p. ej.  1C 2V 3x 4O")
    filas, saltadas = [], []
    for n, letra in respuestas:
        codigo, letra = f"M{int(n):02d}", letra.upper()
        if codigo not in rev or rev[codigo]["estado"] != "mostrada" or (letra != "X" and letra not in por_letra):
            saltadas.append(f"{n}{letra}")
            continue
        cid = rev[codigo]["id"]
        sugerido = (cands.get(cid) or {}).get("pred", [[None]])[0][0]
        if letra == "X":
            ok = poner_etiqueta(cid, "descartada")
            estilo_real = None
        else:
            estilo_real = por_letra[letra]
            ok = poner_etiqueta(cid, "ok", estilo_real)
        if not ok:
            saltadas.append(f"{n}{letra}")
            continue
        rev[codigo]["estado"] = "descartada" if letra == "X" else "ok"
        filas.append((sugerido, estilo_real))
    guardar_json(REVISION, rev)
    juzgadas = [(p, r) for p, r in filas if r]
    aciertos = sum(1 for p, r in juzgadas if p == r)
    print(f"Aplicado: {len(juzgadas)} con estilo, {len(filas) - len(juzgadas)} descartadas (no eran un outfit)" + (f"; sin aplicar: {', '.join(saltadas)}" if saltadas else ""))
    if not juzgadas:
        return
    print(f"\nACIERTO REAL del modelo con fotos nuevas de mercado: {aciertos} de {len(juzgadas)} = {100 * aciertos / len(juzgadas):.0f} %   (azar ≈ 14 %)")
    print("Por estilo real (fotos · acierta · lo que más pone en su lugar):")
    for e in ESTILOS:
        propios = [p for p, r in juzgadas if r == e]
        if propios:
            mal = {}
            for p in propios:
                if p != e:
                    mal[p] = mal.get(p, 0) + 1
            peor = max(mal, key=mal.get) if mal else None
            print(f"   {NOMBRE[e]:20s} {len(propios):3d} fotos · acierta {sum(1 for p in propios if p == e):3d} ({100 * sum(1 for p in propios if p == e) / len(propios):3.0f} %)" + (f"   confunde con {NOMBRE[peor]} ({mal[peor]})" if peor else ""))
    historial = leer_json(MEDIDAS) or {"medidas": []}
    historial["medidas"].append({"fecha": ahora(), "fotos": len(juzgadas), "aciertos": aciertos, "descartadas": len(filas) - len(juzgadas),
                                 "por_estilo": {e: [sum(1 for p, r in juzgadas if r == e and p == e), sum(1 for p, r in juzgadas if r == e)] for e in ESTILOS if any(r == e for _, r in juzgadas)}})
    guardar_json(MEDIDAS, historial)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("entrenar", help="entrena el modelo de 7 estilos").set_defaults(f=cmd_entrenar)
    c = sub.add_parser("cosechar", help="descarga candidatas (Reddit lento / enlaces pegados)")
    c.add_argument("--reddit", default="", help=f"comunidades separadas por coma (p. ej. {SUBS_POR_DEFECTO})")
    c.add_argument("--periodo", default="month", choices=["day", "week", "month", "year"], help="top de Reddit (por defecto: month)")
    c.add_argument("--urls", default="", help="fichero de texto con enlaces de tuits, imágenes o páginas (uno por línea)")
    c.add_argument("--biblioteca", action="store_true", help="descargar lo que hay en la Biblioteca (comunidades/usuarios de Reddit, tuits, páginas, imágenes)")
    c.add_argument("--solo-enlaces", action="store_true", dest="solo_enlaces", help="con --biblioteca: solo los enlaces sin procesar (no las comunidades de Reddit)")
    c.add_argument("--solo-x", action="store_true", dest="solo_x", help="con --biblioteca: solo las cuentas de X y los feeds RSS (no Reddit ni enlaces sueltos)")
    c.set_defaults(f=cmd_cosechar)
    for nombre, ayuda in (("app", "abre la app en el navegador (la forma normal de usarlo, sin terminal)"),
                          ("revisar", "igual que `app` (la clasificación está en su pestaña «Clasificar»)")):
        r = sub.add_parser(nombre, help=ayuda)
        r.add_argument("--puerto", type=int, default=8766)
        r.add_argument("--abrir", action="store_true", help="abrir el navegador desde aquí (el lanzador de Windows ya lo hace)")
        r.set_defaults(f=cmd_app)
    h = sub.add_parser("hojas", help="hojas de fotos numeradas de las propuestas de un estilo (para revisarlas desde el móvil)")
    h.add_argument("--estilo", choices=ESTILOS)
    h.add_argument("--mercado", choices=list(MERCADOS), help="muestra al azar de fotos de ese mercado (para medir el acierto real con `medir`)")
    h.add_argument("--max", type=int, default=18, help="cuántas fotos nuevas enseñar")
    h.add_argument("--por-hoja", type=int, default=9, dest="por_hoja")
    h.set_defaults(f=cmd_hojas)
    rs = sub.add_parser("resolver", help="aplicar las respuestas a las hojas: --revisadas C01-C09 --buenas C01,C04")
    rs.add_argument("--revisadas", required=True, help="códigos que has visto (rangos con guion)")
    rs.add_argument("--buenas", default="", help="los que sirven con su estilo; el resto de las revisadas se descarta")
    rs.set_defaults(f=cmd_resolver)
    me = sub.add_parser("medir", help="aplicar tus respuestas a las hojas de mercado (M01…) y calcular el acierto REAL del modelo: --respuestas \"1C 2V 3x\"")
    me.add_argument("--respuestas", required=True)
    me.set_defaults(f=cmd_medir)
    rt = sub.add_parser("reentrenar", help="entrenar con las etiquetas nuevas y regenerar el informe")
    rt.add_argument("--vida-media", type=float, default=10.0, dest="vida_media")
    rt.set_defaults(f=cmd_reentrenar)
    i = sub.add_parser("informe", help="genera el informe de mercado")
    i.add_argument("--vida-media", type=float, default=10.0, dest="vida_media", help="días en que una foto pierde la mitad de su peso")
    i.add_argument("--dias", type=int, default=45, help="solo cuentan las fotos de los últimos N días")
    i.set_defaults(f=cmd_informe)
    a = sub.add_parser("analizar", help="el «botón»: [cosechar] + clasificar + informe")
    a.add_argument("--cosechar", action="store_true")
    a.add_argument("--reddit", default=SUBS_POR_DEFECTO)
    a.add_argument("--periodo", default="week", choices=["day", "week", "month", "year"])
    a.add_argument("--urls", default="")
    a.add_argument("--biblioteca", action="store_true", help="incluir lo que hay en la Biblioteca")
    a.add_argument("--vida-media", type=float, default=10.0, dest="vida_media")
    a.set_defaults(f=cmd_analizar)
    args = p.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
