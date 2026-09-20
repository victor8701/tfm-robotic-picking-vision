#!/usr/bin/env python3
"""
Descarga fotos reales de "street fashion" (gente con el outfit completo
puesto, fondo real) de Wikimedia Commons, para medir el salto de dominio
del clasificador: entrenado con prendas sueltas de catalogo, ¿que hace
cuando ve un look completo como el de una foto de Instagram?

Commons, no una busqueda cualquiera en internet: todo lo que aloja tiene
licencia libre verificada, y cada descarga queda con su autor/licencia en
ATRIBUCIONES.txt.

Las imagenes NO se commitean (.gitignore): son fotos de personas
identificables. La licencia lo permite, pero no hace falta redistribuirlas
en un repo de TFM -- este script + ATRIBUCIONES.txt las hacen reproducibles.

Uso:
    python3 descargar_fotos_calle_wikimedia.py [--n 30]
"""
import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DESTINO = BASE_DIR / "data" / "fotos_calle"
API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "TFM-RoboticPickingVision-VLM/1.0 (educational research prototype)"
PAUSA = 1.5
ANCHO_DESCARGA_PX = 768
CATEGORIA_RAIZ = "Category:Street fashion"


def _abrir(req, timeout=30, reintentos=4):
    for intento in range(reintentos + 1):
        time.sleep(PAUSA)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code != 429 or intento == reintentos:
                raise
            espera = int(e.headers.get("Retry-After", 15))
            print(f"    (429, esperando {espera}s...)")
            time.sleep(espera)


def _api(params):
    url = API_URL + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with _abrir(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=20) as r:
        return json.loads(r.read())


def miembros(categoria, tipo, limite=100):
    data = _api({"action": "query", "list": "categorymembers", "cmtitle": categoria,
                 "cmtype": tipo, "cmlimit": limite})
    return [m["title"] for m in data.get("query", {}).get("categorymembers", [])]


def info_imagenes(titulos):
    if not titulos:
        return {}
    data = _api({"action": "query", "titles": "|".join(titulos), "prop": "imageinfo",
                 "iiprop": "url|size|mime|extmetadata", "iiurlwidth": ANCHO_DESCARGA_PX})
    out = {}
    for pag in data.get("query", {}).get("pages", {}).values():
        ii = (pag.get("imageinfo") or [None])[0]
        if ii:
            out[pag["title"]] = ii
    return out


def es_foto_de_cuerpo_entero(ii):
    """Retrato vertical y de buen tamano: heuristica barata para 'persona de
    cuerpo entero', que es lo que queremos ver."""
    w, h = ii.get("width", 0), ii.get("height", 0)
    return ii.get("mime") == "image/jpeg" and h >= 700 and h >= 1.2 * w


def licencia_y_autor(ii):
    meta = ii.get("extmetadata", {})
    lic = meta.get("LicenseShortName", {}).get("value", "desconocida")
    autor = re.sub("<[^<]+?>", "", meta.get("Artist", {}).get("value", "desconocido")).strip() or "desconocido"
    return lic, autor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30, help="Cuantas fotos descargar (por defecto 30).")
    args = parser.parse_args()

    DESTINO.mkdir(parents=True, exist_ok=True)

    print(f"Explorando {CATEGORIA_RAIZ} ...")
    titulos = miembros(CATEGORIA_RAIZ, "file")
    subcats = miembros(CATEGORIA_RAIZ, "subcat", limite=30)
    print(f"  {len(titulos)} ficheros directos, {len(subcats)} subcategorias")
    for sc in subcats:
        if len(titulos) >= args.n * 6:
            break
        titulos.extend(miembros(sc, "file", limite=40))

    vistos, atribuciones, guardadas = set(), [], 0
    for i in range(0, len(titulos), 20):
        if guardadas >= args.n:
            break
        lote = [t for t in titulos[i:i + 20] if t not in vistos]
        vistos.update(lote)
        for titulo, ii in info_imagenes(lote).items():
            if guardadas >= args.n:
                break
            if not es_foto_de_cuerpo_entero(ii):
                continue
            nombre = f"calle_{guardadas + 1:02d}.jpg"
            destino = DESTINO / nombre
            try:
                req = urllib.request.Request(ii.get("thumburl") or ii["url"], headers={"User-Agent": USER_AGENT})
                with _abrir(req, timeout=40) as r:
                    destino.write_bytes(r.read())
            except Exception as e:
                print(f"  (aviso) fallo con {titulo}: {e}")
                continue
            lic, autor = licencia_y_autor(ii)
            atribuciones.append(f"{nombre}\n  fuente: {ii['descriptionurl']}\n  autor: {autor}\n  licencia: {lic}")
            guardadas += 1
            print(f"  + {nombre}  <-  {titulo}")

    (DESTINO / "ATRIBUCIONES.txt").write_text("\n\n".join(atribuciones), encoding="utf-8")
    print(f"\n{guardadas} fotos en {DESTINO}")


if __name__ == "__main__":
    main()
