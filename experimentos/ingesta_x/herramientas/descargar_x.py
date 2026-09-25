#!/usr/bin/env python3
"""Descarga fotos y vídeos de posts de X (Twitter) y extrae fotogramas de los vídeos.

Etapa 1 (mínimo viable) del plan de `memoria/TFM_ingesta_redes_sociales.md`: conseguir
fotogramas reales guardados en disco, trazables a su fuente original. Elegido X como primera
plataforma por ser la más accesible de las tres probadas (ver Anexo de esa memoria) -- no es
la que necesariamente tiene el contenido de moda más relevante, solo la más barata de construir.

Cómo decide foto vs vídeo: primero consulta el endpoint público de sindicación de X
(`cdn.syndication.twimg.com`, el mismo que usan los widgets de "insertar tuit" en cualquier
página web -- no hace falta sesión ni clave de API) para ver qué trae el post. Si tiene vídeo,
lo descarga con `yt-dlp` y extrae fotogramas a intervalos con `ffmpeg`. Si tiene foto(s)
nativas, las descarga directamente en su resolución original. Si no tiene ninguna de las dos
(solo texto, o solo una tarjeta de enlace a otra web), falla con un error claro.

Descubrimiento automático (buscar por hashtag, seguir una cuenta, listar el timeline de
alguien): **probado y descartado por ahora** (2026-09-25) -- X invalidó el token público que
usan las herramientas de scraping conocidas para pedir acceso de invitado a su API antigua, y
no hay ningún endpoint de búsqueda/timeline sin autenticar que no dé error o límite de
peticiones. Habría que autenticarse con una cuenta real, que es una decisión aparte (¿de quién
es la cuenta?, ¿qué pasa si X la banea?). Mientras tanto, la forma de "descubrir" contenido es
que una persona (o Claude por búsqueda web) recopile URLs concretas y se las pase a este script
por lote -- ver `--urls-file` más abajo.

Uso:
    python descargar_x.py URL [URL ...] --out ../data/mi_lote
    python descargar_x.py --urls-file lista.txt --out ../data/mi_lote --intervalo 2.0

`lista.txt`: una URL de X por línea; líneas vacías o que empiezan por # se ignoran.

Aviso de privacidad (pendiente de decisión consciente, ver S5.4 de la memoria): esto descarga
contenido con personas identificables reales, sin su consentimiento explícito para este uso
concreto. Aceptable para investigación académica sin redistribución, pero es una decisión, no
un descuido -- no usar estos fotogramas para nada más que evaluación/entrenamiento interno.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import imageio_ffmpeg
import requests
import yt_dlp

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SYNDICATION_URL = "https://cdn.syndication.twimg.com/tweet-result"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _id_de_tuit(url: str) -> str:
    m = re.search(r"status/(\d+)", url)
    if not m:
        raise ValueError(f"No se pudo sacar el ID de tuit de la URL: {url}")
    return m.group(1)


def _token_sindicacion(tweet_id: str) -> str:
    """Algoritmo público conocido (usado por react-tweet y herramientas similares) para el
    parámetro "token" del endpoint de sindicación -- no es una clave secreta, es un cálculo
    determinista a partir del ID; el endpoint no lo valida de forma estricta (probado)."""
    n = (int(tweet_id) / 1e15) * math.pi
    digitos = "0123456789abcdefghijklmnopqrstuvwxyz"
    entero = int(n)
    texto = digitos[0] if entero == 0 else ""
    ip = entero
    while ip:
        texto = digitos[ip % 36] + texto
        ip //= 36
    frac = n - entero
    frac_txt = ""
    for _ in range(20):
        frac *= 36
        d = int(frac)
        frac_txt += digitos[d]
        frac -= d
    return re.sub(r"(0+|\.)", "", f"{texto}.{frac_txt}")


def consultar_sindicacion(tweet_id: str) -> dict | None:
    """Consulta el post vía el endpoint público de sindicación (sin sesión). Devuelve None si
    no hay respuesta útil (post borrado/privado/bloqueado)."""
    resp = requests.get(
        SYNDICATION_URL,
        params={"id": tweet_id, "lang": "en", "token": _token_sindicacion(tweet_id)},
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    texto = resp.text.strip()
    if resp.status_code != 200 or not texto or texto == "{}":
        return None
    return resp.json()


def descargar_video(url: str, tmp_dir: Path) -> tuple[dict, Path]:
    """Descarga el vídeo de un post de X con yt-dlp."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": str(tmp_dir / "%(id)s.%(ext)s"),
        "format": "best",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        ruta = Path(ydl.prepare_filename(info))
    return info, ruta


def extraer_fotogramas(ruta_video: Path, out_dir: Path, prefijo: str, intervalo_seg: float) -> list[Path]:
    """Extrae un fotograma cada `intervalo_seg` segundos con ffmpeg (fps=1/intervalo)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    patron = str(out_dir / f"{prefijo}_%04d.jpg")
    cmd = [
        FFMPEG, "-y", "-loglevel", "error",
        "-i", str(ruta_video),
        "-vf", f"fps=1/{intervalo_seg}",
        "-q:v", "2",
        patron,
    ]
    subprocess.run(cmd, check=True)
    return sorted(out_dir.glob(f"{prefijo}_*.jpg"))


def descargar_fotos_nativas(sindicacion: dict, out_dir: Path, prefijo: str) -> list[Path]:
    """Descarga las fotos nativas del post (no la tarjeta de enlace) en resolución original."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rutas = []
    for i, foto in enumerate(sindicacion.get("photos") or [], start=1):
        # El campo con la URL de la foto varía según la forma de la respuesta: "url" en el
        # array "photos" (el caso normal, comprobado), "media_url_https" en el formato más
        # antiguo de "mediaDetails" -- se comprueban los dos por si acaso.
        url_img = foto.get("url") or foto.get("media_url_https")
        if not url_img:
            continue
        r = requests.get(url_img, params={"format": "jpg", "name": "orig"}, headers={"User-Agent": USER_AGENT}, timeout=20)
        r.raise_for_status()
        ruta = out_dir / f"{prefijo}_foto{i:02d}.jpg"
        ruta.write_bytes(r.content)
        rutas.append(ruta)
    return rutas


def procesar_url(url: str, out_dir: Path, tmp_dir: Path, intervalo_seg: float) -> dict:
    tweet_id = _id_de_tuit(url)
    prefijo = f"x_{tweet_id}"
    sindicacion = consultar_sindicacion(tweet_id)

    if sindicacion and sindicacion.get("video"):
        info, ruta_video = descargar_video(url, tmp_dir)
        fotogramas = extraer_fotogramas(ruta_video, out_dir, prefijo, intervalo_seg)
        ruta_video.unlink(missing_ok=True)
        tipo = "video"
        cuenta = info.get("uploader_id")
        cuenta_nombre = info.get("uploader")
        descripcion = info.get("description")
        fecha = (
            datetime.fromtimestamp(info["timestamp"], tz=timezone.utc).isoformat()
            if info.get("timestamp") else None
        )
    elif sindicacion and sindicacion.get("photos"):
        fotogramas = descargar_fotos_nativas(sindicacion, out_dir, prefijo)
        tipo = "foto"
        cuenta = sindicacion.get("user", {}).get("screen_name")
        cuenta_nombre = sindicacion.get("user", {}).get("name")
        descripcion = sindicacion.get("text")
        fecha = sindicacion.get("created_at")
    else:
        motivo = "post no accesible (borrado/privado/bloqueado)" if not sindicacion else "sin vídeo ni foto nativa (solo texto o solo tarjeta de enlace)"
        raise RuntimeError(motivo)

    metadata = {
        "fuente": "x_twitter",
        "tipo_contenido": tipo,
        "url_original": url,
        "tweet_id": tweet_id,
        "cuenta": cuenta,
        "cuenta_nombre": cuenta_nombre,
        "descripcion": descripcion,
        "fecha_publicacion": fecha,
        "intervalo_seg": intervalo_seg if tipo == "video" else None,
        "n_imagenes": len(fotogramas),
        "imagenes": [f.name for f in fotogramas],
        "descargado_en": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / f"{prefijo}_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2)
    )
    return metadata


def _leer_urls(args: argparse.Namespace) -> list[str]:
    urls = list(args.urls)
    if args.urls_file:
        for linea in Path(args.urls_file).read_text().splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#"):
                urls.append(linea)
    if not urls:
        sys.exit("No se ha dado ninguna URL (ni por argumento ni por --urls-file).")
    return urls


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("urls", nargs="*", help="URLs de posts de X (x.com/usuario/status/ID)")
    parser.add_argument("--urls-file", help="Fichero de texto con una URL de X por línea")
    parser.add_argument("--out", default="../data/fotogramas", help="Carpeta de salida")
    parser.add_argument("--intervalo", type=float, default=2.0, help="Segundos entre fotogramas (solo vídeo)")
    args = parser.parse_args()

    urls = _leer_urls(args)
    out_dir = Path(args.out)
    tmp_dir = out_dir / "_tmp_video"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    fallos = 0
    for url in urls:
        try:
            meta = procesar_url(url, out_dir, tmp_dir, args.intervalo)
            etiqueta = "fotograma(s)" if meta["tipo_contenido"] == "video" else "foto(s)"
            print(f"OK    {url} -> {meta['n_imagenes']} {etiqueta} ({meta['cuenta']})")
        except Exception as e:
            fallos += 1
            print(f"FALLO {url}: {e}", file=sys.stderr)

    shutil.rmtree(tmp_dir, ignore_errors=True)
    if fallos:
        sys.exit(1)


if __name__ == "__main__":
    main()
