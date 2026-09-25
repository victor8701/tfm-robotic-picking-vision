#!/usr/bin/env python3
"""Descarga vídeos de posts de X (Twitter) y extrae fotogramas a intervalos.

Etapa 1 (mínimo viable) del plan de `memoria/TFM_ingesta_redes_sociales.md`: conseguir
fotogramas reales guardados en disco, trazables a su fuente original. Elegido X como primera
plataforma por ser la más accesible de las tres probadas (ver Anexo de esa memoria) -- no es
la que necesariamente tiene el contenido de moda más relevante, solo la más barata de construir.

Alcance de esta v1, a propósito reducido:
- Solo tuits CON vídeo. Los tuits de solo foto no se descargan aquí -- yt-dlp no expone la URL
  de la imagen para Twitter (solo formatos de vídeo), habría que resolverlo aparte si hace falta.
- Solo por URL de post concreto, uno a uno. No hay descubrimiento automático (buscar por
  hashtag, seguir una cuenta) -- eso es un paso posterior, no está en el alcance de "empezar".
- No se guarda el vídeo descargado, solo los fotogramas extraídos + su metadata -- mismo motivo
  por el que el propio `viral_clips` no guarda el vídeo fuente salvo que se pida explícitamente.

Uso:
    python descargar_x.py URL [URL ...] --out ../data --intervalo 2.0

Aviso de privacidad (pendiente de decisión consciente, ver S5.4 de la memoria): esto descarga
contenido con personas identificables reales, sin su consentimiento explícito para este uso
concreto. Aceptable para investigación académica sin redistribución, pero es una decisión, no
un descuido -- no usar estos fotogramas para nada más que evaluación/entrenamiento interno.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import imageio_ffmpeg
import yt_dlp

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def descargar_video(url: str, tmp_dir: Path) -> tuple[dict, Path]:
    """Descarga el vídeo de un post de X con yt-dlp. Falla si el post no tiene vídeo (solo foto)."""
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


def procesar_url(url: str, out_dir: Path, tmp_dir: Path, intervalo_seg: float) -> dict:
    info, ruta_video = descargar_video(url, tmp_dir)
    tweet_id = info.get("id")
    prefijo = f"x_{tweet_id}"
    fotogramas = extraer_fotogramas(ruta_video, out_dir, prefijo, intervalo_seg)
    ruta_video.unlink(missing_ok=True)

    metadata = {
        "fuente": "x_twitter",
        "url_original": url,
        "tweet_id": tweet_id,
        "cuenta": info.get("uploader_id"),
        "cuenta_nombre": info.get("uploader"),
        "descripcion": info.get("description"),
        "fecha_publicacion": (
            datetime.fromtimestamp(info["timestamp"], tz=timezone.utc).isoformat()
            if info.get("timestamp")
            else None
        ),
        "duracion_seg": info.get("duration"),
        "intervalo_seg": intervalo_seg,
        "n_fotogramas": len(fotogramas),
        "fotogramas": [f.name for f in fotogramas],
        "descargado_en": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / f"{prefijo}_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2)
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("urls", nargs="+", help="URLs de posts de X con vídeo (x.com/usuario/status/ID)")
    parser.add_argument("--out", default="../data/fotogramas", help="Carpeta de salida")
    parser.add_argument("--intervalo", type=float, default=2.0, help="Segundos entre fotogramas")
    args = parser.parse_args()

    out_dir = Path(args.out)
    tmp_dir = out_dir / "_tmp_video"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    fallos = 0
    for url in args.urls:
        try:
            meta = procesar_url(url, out_dir, tmp_dir, args.intervalo)
            print(f"OK    {url} -> {meta['n_fotogramas']} fotogramas ({meta['cuenta']})")
        except Exception as e:
            fallos += 1
            print(f"FALLO {url}: {e}", file=sys.stderr)

    shutil.rmtree(tmp_dir, ignore_errors=True)
    if fallos:
        sys.exit(1)


if __name__ == "__main__":
    main()
