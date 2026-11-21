"""De dónde salen las imágenes: una carpeta (pruebas en casa), una cámara USB o una RealSense (celda).

Todos tienen `siguiente()`: el siguiente fotograma (`Fotograma`) o None si no hay más. La profundidad, si la hay, va alineada con el
color y en milímetros (0 = sin medida).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

EXTENSIONES = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


@dataclass(frozen=True)
class Fotograma:
    bgr: np.ndarray
    profundidad: np.ndarray | None = None
    nombre: str = ""


def listar_imagenes(ruta) -> list[Path]:
    """Las imágenes de una carpeta, ordenadas por nombre, o el fichero si es una imagen. Ignora las anotadas y la profundidad."""
    r = Path(ruta)
    if r.is_file():
        return [r]
    if not r.is_dir():
        raise ValueError(f"no existe {r}")
    return sorted(f for f in r.iterdir()
                  if f.suffix.lower() in EXTENSIONES and not f.stem.endswith(("_anotada", "_prof", "_fondo")) and f.stem != "fondo")


class Carpeta:
    """Imágenes guardadas, una a una. Si junto a `foto.png` hay `foto.npy` (o `foto_prof.png` de 16 bits), es su profundidad en mm."""

    def __init__(self, ruta):
        self.ficheros = listar_imagenes(ruta)
        if not self.ficheros:
            raise ValueError(f"no hay imágenes en {ruta} ({', '.join(EXTENSIONES)})")
        self._i = 0

    def siguiente(self) -> Fotograma | None:
        if self._i >= len(self.ficheros):
            return None
        f = self.ficheros[self._i]
        self._i += 1
        return cargar_fotograma(f)


def cargar_fotograma(fichero: Path) -> Fotograma:
    bgr = cv2.imread(str(fichero), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"no puedo leer la imagen {fichero}")
    prof = None
    npy = fichero.with_suffix(".npy")
    png = fichero.with_name(fichero.stem + "_prof.png")
    if npy.is_file():
        prof = np.load(npy).astype(np.float32)
    elif png.is_file():
        prof = cv2.imread(str(png), cv2.IMREAD_UNCHANGED).astype(np.float32)
    if prof is not None and prof.shape[:2] != bgr.shape[:2]:
        raise ValueError(f"la profundidad de {fichero.name} mide {prof.shape[1]}x{prof.shape[0]} y la imagen {bgr.shape[1]}x{bgr.shape[0]}")
    return Fotograma(bgr, prof, fichero.name)


class CamaraOpenCV:
    """Una cámara USB (o la de un portátil) con OpenCV. Sin profundidad."""

    def __init__(self, indice: int = 0, tam: tuple[int, int] | None = None):
        self._cap = cv2.VideoCapture(indice)
        if not self._cap.isOpened():
            raise ValueError(f"no puedo abrir la cámara {indice}")
        if tam is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, tam[0])
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, tam[1])

    def siguiente(self) -> Fotograma | None:
        ok, bgr = self._cap.read()
        return Fotograma(bgr, None, "camara") if ok else None

    def cerrar(self) -> None:
        self._cap.release()


class RealSense:
    """Intel RealSense (color y profundidad alineada) con pyrealsense2. SIN PROBAR: no hay cámara ni librería en el equipo de
    desarrollo. La profundidad sale en mm, alineada con el color."""

    def __init__(self, tam=(1280, 720), fps: int = 15):
        try:
            import pyrealsense2 as rs
        except ImportError:
            raise ValueError("falta pyrealsense2 (pip install pyrealsense2) para usar la RealSense") from None
        self._rs = rs
        self._pipe = rs.pipeline()
        cfg = rs.config()
        cfg.enable_stream(rs.stream.color, tam[0], tam[1], rs.format.bgr8, fps)
        cfg.enable_stream(rs.stream.depth, tam[0], tam[1], rs.format.z16, fps)
        perfil = self._pipe.start(cfg)
        self._escala_mm = perfil.get_device().first_depth_sensor().get_depth_scale() * 1000.0
        self._alinear = rs.align(rs.stream.color)

    def siguiente(self) -> Fotograma | None:
        marcos = self._alinear.process(self._pipe.wait_for_frames())
        c, d = marcos.get_color_frame(), marcos.get_depth_frame()
        if not c or not d:
            return None
        return Fotograma(np.asanyarray(c.get_data()).copy(), np.asanyarray(d.get_data()).astype(np.float32) * self._escala_mm, "realsense")

    def cerrar(self) -> None:
        self._pipe.stop()


def abrir_proveedor(cfg: dict):
    """Proveedor a partir de la sección 'origen' de la configuración: {"tipo": "carpeta"|"opencv"|"realsense", ...}."""
    tipo = cfg.get("tipo")
    if tipo == "carpeta":
        return Carpeta(cfg["ruta"])
    if tipo == "opencv":
        tam = cfg.get("tam")
        return CamaraOpenCV(int(cfg.get("indice", 0)), None if tam is None else (int(tam[0]), int(tam[1])))
    if tipo == "realsense":
        tam = cfg.get("tam", [1280, 720])
        return RealSense((int(tam[0]), int(tam[1])), int(cfg.get("fps", 15)))
    raise ValueError(f"origen de imágenes desconocido: {tipo!r} (carpeta, opencv o realsense)")
