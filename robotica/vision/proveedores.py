"""De dónde salen las imágenes: una carpeta (pruebas en casa), una cámara USB o una RealSense (celda).

Todos tienen `siguiente()`: el siguiente fotograma (`Fotograma`) o None si no hay más. La profundidad, si la hay, va alineada con el
color y en milímetros (0 = sin medida).
"""
from __future__ import annotations

import http.client
import json
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

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
    """Una cámara USB (o la de un portátil) o, con una URL, la cámara de un móvil (apps tipo «IP Webcam», DroidCam por Wi-Fi...) con OpenCV. Sin profundidad.

    Con una URL (http://... MJPEG, rtsp://...) un hilo lee sin parar y `siguiente()` da siempre el fotograma MÁS RECIENTE y nuevo: un vídeo por red
    se acumula en un búfer y, si no se vacía, se mediría una imagen vieja (la de hace un segundo)."""

    def __init__(self, indice: int | str = 0, tam: tuple[int, int] | None = None, api: int | None = None):
        """indice: número de la cámara o URL del vídeo. api: backend de OpenCV (p. ej. cv2.CAP_DSHOW en Windows); None = el de por defecto."""
        self.url = indice if isinstance(indice, str) else None
        self.indice = None if self.url else indice
        if self.url and api is None:
            api = cv2.CAP_FFMPEG
        self._cap = cv2.VideoCapture(indice) if api is None else cv2.VideoCapture(indice, api)
        if not self._cap.isOpened():
            raise ValueError(f"no puedo abrir {'la URL ' + self.url if self.url else 'la cámara ' + str(indice)}")
        if tam is not None and not self.url:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, tam[0])
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, tam[1])
        self._ultimo = None
        self._numero = 0
        self._visto = 0
        self._parar = threading.Event()
        self._cond = threading.Condition()
        self._hilo = None
        if self.url:
            self._hilo = threading.Thread(target=self._leer_sin_parar, name="camara-url", daemon=True)
            self._hilo.start()

    def _leer_sin_parar(self) -> None:
        fallos = 0
        while not self._parar.is_set():
            ok, bgr = self._cap.read()
            if not ok:
                fallos += 1
                if fallos > 100:
                    break
                time.sleep(0.02)
                continue
            fallos = 0
            with self._cond:
                self._ultimo, self._numero = bgr, self._numero + 1
                self._cond.notify_all()
        with self._cond:
            self._numero = -1          # el vídeo se ha cortado: siguiente() deja de esperar
            self._cond.notify_all()

    def siguiente(self) -> Fotograma | None:
        if self._hilo is None:
            ok, bgr = self._cap.read()
            return Fotograma(bgr, None, "camara") if ok else None
        with self._cond:
            nuevo = self._cond.wait_for(lambda: self._numero != self._visto, timeout=3.0)
            if not nuevo or self._numero in (0, -1) or self._ultimo is None:
                return None            # sin imagen nueva en 3 s (o el video se ha cortado): una imagen vieja nunca se da por actual
            self._visto = self._numero
            return Fotograma(self._ultimo.copy(), None, "camara")

    def cerrar(self) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(2.0)
        self._cap.release()


def es_pagina_del_movil(url: str) -> bool:
    """¿Es la dirección de la página de movil_camara (…/c/<clave>) y no el vídeo de una aplicación del móvil?"""
    partes = urlsplit(url)
    return partes.scheme in ("http", "https") and re.fullmatch(r"/c/[^/]+/?", partes.path) is not None


class CamaraMovil:
    """La cámara de un móvil a través de la página de movil_camara (p. ej. en Render). url: la misma dirección que abre el teléfono,
    https://servidor/c/<clave>.

    Cada `siguiente()` pide una foto que el teléfono haya hecho DESPUÉS de pedirla, así que nunca se mide con una imagen vieja. None si no llega
    ninguna en `espera_s`; `motivo` dice por qué. Como mucho una cada `intervalo_s`: lo que baja del servidor gasta el tráfico mensual gratuito
    de Render."""

    SIN_FOTOS = "el móvil no está enviando fotos: ¿la página está abierta, con la cámara encendida, en horizontal y con la pantalla encendida?"
    descartar = 1            # un teléfono no da los primeros fotogramas negros de una webcam: no hace falta tirar ninguno

    def __init__(self, url: str, espera_s: float = 6.0, arranque_s: float = 90.0, espera_movil_s: float = 15.0, intervalo_s: float = 1.0):
        partes = urlsplit(url)
        self.url = url.rstrip("/")
        self.indice = None
        self.espera_s = espera_s
        self.intervalo_s = intervalo_s
        self._ultima_peticion = -intervalo_s
        self.motivo: str | None = None
        self._ruta = partes.path.rstrip("/")
        self._tipo = http.client.HTTPSConnection if partes.scheme == "https" else http.client.HTTPConnection
        self._destino = partes.netloc
        self._conexion = None
        self._esperar_servidor(arranque_s)
        limite = time.monotonic() + espera_movil_s
        while self.siguiente() is None:
            if time.monotonic() >= limite:
                self.cerrar()
                raise ValueError(f"{self.motivo} Abre en el móvil {self.url}")

    def _esperar_servidor(self, arranque_s: float) -> None:
        """El servidor contesta y la clave vale. Un servidor gratuito de Render dormido tarda alrededor de un minuto en despertar."""
        limite = time.monotonic() + arranque_s
        avisado = False
        while True:
            try:
                codigo, cuerpo = self._pedir("/estado", max(1.0, limite - time.monotonic()))
                if codigo == 404:
                    self.cerrar()
                    raise ValueError(f"{self._destino} no reconoce {self.url}: revisa que sea la dirección del servicio y que acabe en /c/ y su variable CLAVE")
                if codigo == 200 and "fotos" in json.loads(cuerpo):
                    return
                fallo = f"contesta {codigo}"
            except (OSError, http.client.HTTPException, json.JSONDecodeError) as e:
                fallo = str(e) or type(e).__name__
            if time.monotonic() >= limite:
                self.cerrar()
                raise ValueError(f"no puedo conectar con el servidor de la cámara {self._destino} ({fallo})")
            if not avisado:
                print(f"Esperando al servidor de la cámara {self._destino} (si estaba dormido tarda como un minuto)...", flush=True)
                avisado = True
            time.sleep(min(2.0, max(0.0, limite - time.monotonic())))

    def _pedir(self, recurso: str, plazo_s: float) -> tuple[int, bytes]:
        """GET por una conexión que se reutiliza (abrir una https por foto cuesta décimas). Si la reutilizada estaba cortada, se abre otra."""
        while True:
            con = self._conexion        # en una variable: otro hilo puede llamar a cerrar() mientras se espera la foto
            reutilizada = con is not None
            if not reutilizada:
                con = self._conexion = self._tipo(self._destino, timeout=plazo_s)
            try:
                if con.sock is not None:
                    con.sock.settimeout(plazo_s)
                con.request("GET", self._ruta + recurso, headers={"User-Agent": "celda-camara"})
                respuesta = con.getresponse()
                return respuesta.status, respuesta.read()
            except (OSError, http.client.HTTPException) as e:
                self.cerrar()
                if not reutilizada or isinstance(e, TimeoutError):
                    raise

    def siguiente(self) -> Fotograma | None:
        resto = self._ultima_peticion + self.intervalo_s - time.monotonic()
        if resto > 0:
            time.sleep(resto)
        self._ultima_peticion = time.monotonic()
        try:
            codigo, cuerpo = self._pedir(f"/ultima?espera={self.espera_s:g}", self.espera_s + 10.0)
        except (OSError, http.client.HTTPException) as e:
            self.motivo = f"sin conexión con el servidor de la cámara ({str(e) or type(e).__name__})."
            time.sleep(0.5)          # sin red no hay que reintentar en bucle cerrado
            return None
        if codigo == 200:
            bgr = cv2.imdecode(np.frombuffer(cuerpo, np.uint8), cv2.IMREAD_COLOR)
            if bgr is not None:
                self.motivo = None
                return Fotograma(bgr, None, "camara")
        self.motivo = self.SIN_FOTOS if codigo == 204 else f"el servidor de la cámara contesta {codigo}."
        if codigo != 204:
            time.sleep(0.5)
        return None

    def cerrar(self) -> None:
        if self._conexion is not None:
            self._conexion.close()
            self._conexion = None


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


def abrir_camara_usb(indice: int = 0, tam: tuple[int, int] | None = None, api=None, url: str | None = None) -> "CamaraOpenCV | CamaraMovil":
    """Una cámara USB, o la de un móvil por red si se da `url`: la página de movil_camara (https://servidor/c/<clave>) o el vídeo de una aplicación
    (http://IP:puerto/video, rtsp://...). api: 'dshow' o 'msmf' (o el número de backend de OpenCV); sin api, el de por defecto y, en Windows, si no
    abre, DirectShow (algunas webcams solo abren con uno de los dos)."""
    if url:
        if es_pagina_del_movil(url):
            return CamaraMovil(url)
        try:
            return CamaraOpenCV(url, tam)
        except ValueError as e:
            raise ValueError(f"{e}: ¿el móvil y el PC están en la misma Wi-Fi?, ¿la aplicación de cámara del móvil está en marcha?, ¿la URL es la que "
                             "muestra la aplicación (con http:// y el puerto)?") from None
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
    """Proveedor a partir de la sección 'origen' de la configuración: {"tipo": "carpeta"|"opencv"|"realsense", ...}. "opencv" abre una cámara USB ("indice") o la de un móvil por red ("url")."""
    tipo = cfg.get("tipo")
    if tipo == "carpeta":
        return Carpeta(cfg["ruta"])
    if tipo == "opencv":
        tam = cfg.get("tam")
        return abrir_camara_usb(int(cfg.get("indice", 0)), None if tam is None else (int(tam[0]), int(tam[1])), cfg.get("api"), cfg.get("url") or None)
    if tipo == "realsense":
        tam = cfg.get("tam", [1280, 720])
        return RealSense((int(tam[0]), int(tam[1])), int(cfg.get("fps", 15)))
    if tipo == "ros":
        raise ValueError("el origen 'ros' solo vale con nodo_celda (ros2 launch robotica_bimanual celda_real.launch.py), no con celda.ciclo")
    raise ValueError(f"origen de imágenes desconocido: {tipo!r} (carpeta, opencv o realsense)")
