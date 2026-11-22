"""De dónde salen las imágenes: una carpeta (pruebas en casa), una cámara USB o una RealSense (celda).

Todos tienen `siguiente()`: el siguiente fotograma (`Fotograma`) o None si no hay más. La profundidad, si la hay, va alineada con el
color y en milímetros (0 = sin medida).
"""
from __future__ import annotations

import sys
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


def listar_carpetas(raiz) -> list[str]:
    """Nombres de las subcarpetas de `raiz` que se pueden usar como cámara de ensayo: tienen imágenes y su propia calibración
    (`camara.json`), porque cada juego de fotos se hizo con una cámara puesta de una manera. Sin ':' ni ';' en el nombre (van en los mensajes
    a RAPID). Ordenadas por nombre."""
    r = Path(raiz)
    if not r.is_dir():
        return []
    nombres = []
    for c in sorted(r.iterdir()):
        if not c.is_dir() or c.name.startswith(".") or ":" in c.name or ";" in c.name:
            continue
        if (c / "camara.json").is_file() and listar_imagenes(c):
            nombres.append(c.name)
    return nombres


def trocear_nombres(nombres, largo_max: int = 65, trozos_max: int = 3) -> tuple[list[str], int]:
    """Reparte los nombres en trozos de texto «a;b;c» de a lo sumo `largo_max` caracteres (lo que cabe en un mensaje a RAPID, que tiene 80 con
    el prefijo) y como mucho `trozos_max` trozos. Devuelve los trozos y cuántos nombres no han cabido."""
    trozos: list[str] = []
    actual = ""
    omitidos = 0
    for n in nombres:
        if len(n) > largo_max:
            omitidos += 1
            continue
        candidato = n if not actual else actual + ";" + n
        if len(candidato) <= largo_max:
            actual = candidato
        elif len(trozos) + 1 < trozos_max:
            trozos.append(actual)
            actual = n
        else:
            omitidos += 1
    if actual:
        trozos.append(actual)
    return trozos, omitidos


class Carpeta:
    """Imágenes guardadas, una a una. Si junto a `foto.png` hay `foto.npy` (o `foto_prof.png` de 16 bits), es su profundidad en mm.

    `siguiente()` gasta la imagen (es la que usa el ciclo); `ver()` enseña la actual sin gastarla (la vista previa)."""

    def __init__(self, ruta):
        self.ruta = Path(ruta)
        self.ficheros = listar_imagenes(ruta)
        if not self.ficheros:
            raise ValueError(f"no hay imágenes en {ruta} ({', '.join(EXTENSIONES)})")
        self._i = 0
        self._cache: tuple[int, Fotograma] | None = None

    @property
    def n(self) -> int:
        """Imágenes de la carpeta."""
        return len(self.ficheros)

    @property
    def indice(self) -> int:
        """Imagen actual, de 0 a n (n = ya no quedan)."""
        return self._i

    @property
    def nombre(self) -> str:
        return self.ruta.name if self.ruta.is_dir() else self.ruta.parent.name

    def _cargar(self, i: int) -> Fotograma:
        if self._cache is None or self._cache[0] != i:
            self._cache = (i, cargar_fotograma(self.ficheros[i]))
        return self._cache[1]

    def ver(self) -> Fotograma | None:
        return None if self._i >= len(self.ficheros) else self._cargar(self._i)

    def siguiente(self) -> Fotograma | None:
        if self._i >= len(self.ficheros):
            return None
        fot = self._cargar(self._i)
        self._i += 1
        return fot


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

    def __init__(self, indice: int = 0, tam: tuple[int, int] | None = None, api: int | None = None):
        """api: backend de OpenCV (p. ej. cv2.CAP_DSHOW en Windows); None = el de por defecto."""
        self.indice = indice
        self._cap = cv2.VideoCapture(indice) if api is None else cv2.VideoCapture(indice, api)
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


def abrir_camara_usb(indice: int = 0, tam: tuple[int, int] | None = None, api=None) -> "CamaraOpenCV":
    """Una cámara USB. api: 'dshow' o 'msmf' (o el número de backend de OpenCV); sin api, el de por defecto y, en Windows, si no abre, DirectShow
    (algunas webcams solo abren con uno de los dos)."""
    if isinstance(api, str):
        nombres = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "auto": None}
        if api.lower() not in nombres:
            raise ValueError(f"camara.origen.api desconocido: {api!r} (dshow, msmf o auto)")
        api = nombres[api.lower()]
    apis = [api] if api is not None else [None] + ([cv2.CAP_DSHOW] if sys.platform == "win32" else [])
    ultimo = None
    for a in apis:
        try:
            return CamaraOpenCV(indice, tam, a)
        except ValueError as e:
            ultimo = e
    raise ultimo


def abrir_proveedor(cfg: dict):
    """Proveedor a partir de la sección 'origen' de la configuración: {"tipo": "carpeta"|"opencv"|"realsense", ...}."""
    tipo = cfg.get("tipo")
    if tipo == "carpeta":
        return Carpeta(cfg["ruta"])
    if tipo == "opencv":
        tam = cfg.get("tam")
        return abrir_camara_usb(int(cfg.get("indice", 0)), None if tam is None else (int(tam[0]), int(tam[1])), cfg.get("api"))
    if tipo == "realsense":
        tam = cfg.get("tam", [1280, 720])
        return RealSense((int(tam[0]), int(tam[1])), int(cfg.get("fps", 15)))
    if tipo == "ros":
        raise ValueError("el origen 'ros' solo vale con nodo_celda (ros2 launch robotica_bimanual celda_real.launch.py), no con celda.ciclo")
    raise ValueError(f"origen de imágenes desconocido: {tipo!r} (carpeta, opencv o realsense)")
