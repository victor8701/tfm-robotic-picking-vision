#!/usr/bin/env python3
"""
Descarga imagenes de Wikimedia Commons para poblar las carpetas de
muestras del POC de CLIP (../<grupo_estilo>/), una prenda por imagen.

Por que Wikimedia Commons: no requiere API key, y todo lo que aloja
tiene licencia libre verificada (CC0, CC-BY, CC-BY-SA o dominio
publico) -- evita meter fotos de catalogo de marcas con copyright en
un repo academico.

No es perfecto: la busqueda de texto de Commons no garantiza "foto de
producto de una sola prenda sobre fondo limpio" -- puede devolver fotos
de museo, de gente llevando la prenda puesta, colecciones, etc. Por
eso se descargan varios candidatos por termino y se deja al usuario
borrar a mano los que no sirvan (igual que con cualquier dataset real).

Cada carpeta de destino incluye un ATRIBUCIONES.txt con la fuente,
autor y licencia de cada imagen descargada, por si el repo se hace
publico.

Uso:
    python3 descargar_muestras_wikimedia.py
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "TFM-RoboticPickingVision-CLIP-POC/1.0 (educational research prototype)"

CANDIDATOS_POR_TERMINO = 6
DESCARGAS_POR_TERMINO = 2
ANCHO_MINIMO_PX = 400
ANCHO_DESCARGA_PX = 800  # pedimos thumbnail, no el original -- mas rapido y
                         # menos probable que dispare el limitador de Commons
PAUSA_ENTRE_PETICIONES = 1.2  # segundos, cortesia con la API de Commons
REINTENTOS_429 = 4

# Titulos/fragmentos que delatan que NO es una foto de producto de una
# sola prenda (fotos de coleccion, mapas, escudos, gente en la calle...).
PALABRAS_EXCLUIDAS = [
    "wall of", "reference", "collection", "museum", "map", "flag",
    "logo", "diagram", "coat of arms", "runway", "fashion week",
    "parade", "crowd", "advertisement", "storefront", "shop front",
    "illustration", "drawing", "painting", "postcard", "stamp",
]

# grupo_estilo -> terminos de busqueda en Wikimedia Commons
CATEGORIAS = {
    "casual": [
        "blue jeans product photo",
        "white t-shirt flat lay",
        "cardigan sweater",
        "chino trousers",
        "denim jacket",
    ],
    "streetwear": [
        "sneakers shoes product photo",
        "hoodie sweatshirt",
        "baseball cap",
        "cargo pants",
        "bomber jacket",
    ],
    "de_vestir": [
        "blazer suit jacket",
        "dress shirt product",
        "oxford shoes leather",
        "formal trousers suit",
        "necktie",
    ],
    "fiesta_noche": [
        "sequin dress",
        "evening gown",
        "high heels black shoes",
        "cocktail dress",
        "evening clutch bag",
    ],
    "deportivo": [
        "running shoes product photo",
        "leggings sportswear",
        "tracksuit",
        "sports bra",
        "gym shorts",
    ],
    "playa_resort": [
        "straw sun hat",
        "swimsuit product photo",
        "flip flops sandals",
        "floral sundress",
        "aviator sunglasses",
    ],
}


def _abrir_con_reintento(req, timeout):
    """urlopen con espera antes de cada intento y reintento con backoff
    ante 429 (respeta Retry-After si Commons lo manda)."""
    for intento in range(REINTENTOS_429 + 1):
        time.sleep(PAUSA_ENTRE_PETICIONES)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code != 429 or intento == REINTENTOS_429:
                raise
            espera = int(e.headers.get("Retry-After", 10))
            print(f"    (429, esperando {espera}s antes de reintentar...)")
            time.sleep(espera)
    raise RuntimeError("no deberia llegar aqui")


def _get(params):
    params = {**params, "format": "json"}
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _abrir_con_reintento(req, timeout=20) as resp:
        return json.loads(resp.read())


def buscar_titulos(termino, limite=CANDIDATOS_POR_TERMINO):
    data = _get({
        "action": "query", "list": "search", "srnamespace": 6,
        "srlimit": limite, "srsearch": termino,
    })
    titulos = [r["title"] for r in data.get("query", {}).get("search", [])]
    return [t for t in titulos if not _excluido(t)]


def _excluido(titulo):
    t = titulo.lower()
    return any(palabra in t for palabra in PALABRAS_EXCLUIDAS)


def info_imagenes(titulos):
    if not titulos:
        return {}
    data = _get({
        "action": "query", "titles": "|".join(titulos),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": ANCHO_DESCARGA_PX,  # pedimos tambien un thumbnail
    })
    paginas = data.get("query", {}).get("pages", {})
    resultado = {}
    for pagina in paginas.values():
        info = (pagina.get("imageinfo") or [None])[0]
        if info:
            resultado[pagina["title"]] = info
    return resultado


def licencia_y_autor(info):
    meta = info.get("extmetadata", {})
    licencia = meta.get("LicenseShortName", {}).get("value", "desconocida")
    autor = meta.get("Artist", {}).get("value", "desconocido")
    # quitar posibles etiquetas HTML del campo Artist
    import re
    autor = re.sub("<[^<]+?>", "", autor).strip() or "desconocido"
    return licencia, autor


def descargar_archivo(url, destino):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _abrir_con_reintento(req, timeout=30) as resp, open(destino, "wb") as f:
        f.write(resp.read())


def slug(texto):
    return "".join(c if c.isalnum() else "_" for c in texto.lower()).strip("_")


def main():
    for categoria, terminos in CATEGORIAS.items():
        carpeta = BASE_DIR / categoria
        carpeta.mkdir(exist_ok=True)
        atribuciones_path = carpeta / "ATRIBUCIONES.txt"
        atribuciones = []
        if atribuciones_path.exists():
            # conserva las entradas de una ejecucion anterior cuyo fichero
            # todavia existe (si el usuario ya borro alguna, se cae sola)
            for bloque in atribuciones_path.read_text(encoding="utf-8").split("\n\n"):
                primera_linea = bloque.strip().split("\n", 1)[0].strip()
                if primera_linea and (carpeta / primera_linea).exists():
                    atribuciones.append(bloque.strip())
        descargadas = 0

        print(f"\n=== {categoria} ===")
        for termino in terminos:
            # Si una ejecucion anterior ya dejo suficientes ficheros para
            # este termino (p.ej. tras un 429), nos lo saltamos sin volver
            # a llamar a la API -- hace que relanzar el script sea barato.
            ya_hay = list(carpeta.glob(f"{slug(termino)}_*.*"))
            if len(ya_hay) >= DESCARGAS_POR_TERMINO:
                print(f"  (ya habia {len(ya_hay)} para '{termino}', se omite)")
                descargadas += len(ya_hay)
                continue

            titulos = buscar_titulos(termino)
            info = info_imagenes(titulos)

            aceptados = 0
            for titulo, datos in info.items():
                if aceptados >= DESCARGAS_POR_TERMINO:
                    break
                if datos.get("mime") not in ("image/jpeg", "image/png"):
                    continue
                if datos.get("width", 0) < ANCHO_MINIMO_PX:
                    continue

                ext = ".jpg" if datos["mime"] == "image/jpeg" else ".png"
                nombre = f"{slug(termino)}_{aceptados + 1}{ext}"
                destino = carpeta / nombre
                url_descarga = datos.get("thumburl") or datos["url"]

                if destino.exists():
                    print(f"  = {nombre} ya existe, se mantiene")
                else:
                    try:
                        descargar_archivo(url_descarga, destino)
                    except Exception as e:
                        print(f"  (aviso) fallo al descargar {titulo}: {e}")
                        continue
                    print(f"  + {nombre}  <-  {titulo}")

                licencia, autor = licencia_y_autor(datos)
                atribuciones.append(
                    f"{nombre}\n  fuente: {datos['descriptionurl']}\n"
                    f"  autor: {autor}\n  licencia: {licencia}"
                )
                aceptados += 1
                descargadas += 1
                time.sleep(0.3)  # cortesia con la API de Commons

        atribuciones_path.write_text("\n\n".join(atribuciones), encoding="utf-8")
        print(f"  Total en {categoria}: {descargadas} imagenes")


if __name__ == "__main__":
    main()
