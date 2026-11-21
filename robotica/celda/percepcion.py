"""Percepcion de la caja: en simulacion, las medidas que genero RAPID en caja.csv;
en el laboratorio, la camara (vision/, calibracion/camara.py). La interfaz es la misma: leer(i) -> Caja."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Caja:
    largo: float
    ancho: float
    alto: float
    giro_deg: float
    # Centro de la caja (x, y) en mm respecto a la base. None = el centro de recogida de la config.
    centro: tuple[float, float] | None = None


def centro_parada(largo: float, ancho: float, giro_deg: float, centro_x: float, sensor_y: float):
    """Donde queda el centro de la caja cuando el sensor de final de cinta la para.

    La cinta lleva la caja en +y y se para cuando su cara delantera toca el plano del sensor
    (y = sensor_y). Con giro 0, el largo va en x. Es lo que veria una camara en la simulacion.
    """
    g = math.radians(giro_deg)
    medio_y = (largo / 2.0) * abs(math.sin(g)) + (ancho / 2.0) * abs(math.cos(g))
    return (centro_x, sensor_y - medio_y)


def _linea(texto: str, n: int) -> Caja:
    partes = texto.strip().split(";")
    if len(partes) != 4:
        raise ValueError(f"caja.csv, linea {n}: se esperan 4 campos (largo;ancho;alto;giro) y hay {len(partes)}")
    largo, ancho, alto, giro = (float(p) for p in partes)
    if min(largo, ancho, alto) <= 0.0:
        raise ValueError(f"caja.csv, linea {n}: las dimensiones deben ser positivas")
    if not -90.0 <= giro < 90.0:
        raise ValueError(f"caja.csv, linea {n}: el giro debe estar en [-90, 90)")
    return Caja(largo, ancho, alto, giro)


class FuenteCsv:
    """Cajas de la simulacion. RAPID escribe caja.csv al arrancar, asi que el fichero se lee
    en la primera caja (no al crear la fuente, que puede ser antes que RAPID)."""

    def __init__(self, ruta, centro_x: float | None = None, sensor_y: float | None = None):
        self._ruta = Path(ruta)
        self._centro_x = centro_x
        self._sensor_y = sensor_y
        self._cajas: list[Caja] | None = None

    def _cargar(self) -> list[Caja]:
        if not self._ruta.is_file():
            raise FileNotFoundError(f"no existe {self._ruta}: ¿esta RAPID en marcha y ha generado caja.csv?")
        lineas = [ln for ln in self._ruta.read_text(encoding="utf-8").splitlines() if ln.strip()]
        cajas = [_linea(ln, n) for n, ln in enumerate(lineas, start=1)]
        if self._sensor_y is None or self._centro_x is None:
            return cajas
        return [Caja(c.largo, c.ancho, c.alto, c.giro_deg,
                     centro_parada(c.largo, c.ancho, c.giro_deg, self._centro_x, self._sensor_y)) for c in cajas]

    def leer(self, i: int) -> Caja:
        if self._cajas is None:
            self._cajas = self._cargar()
        if not 0 <= i < len(self._cajas):
            raise IndexError(f"caja {i} fuera de caja.csv ({len(self._cajas)} cajas)")
        return self._cajas[i]

    def total(self) -> int:
        """Cajas de la tanda: las que RAPID ha escrito en caja.csv, una por linea. Asi el PC y RAPID no
        pueden discrepar en la cuenta (con n_cajas = 1 en el PC y nCajas = 5 en RAPID, RAPID hacia las
        cajas 2 a 5 sin que el PC las agarrara)."""
        if self._cajas is None:
            self._cajas = self._cargar()
        return len(self._cajas)


class FuenteCamara:
    """La caja que ve la camara, medida en la base del robot (vision.deteccion): largo, ancho, alto, giro y centro.

    Cada leer() pide fotogramas al proveedor hasta ver una caja entera (no recortada por el borde de la imagen) o agotar tiempo_max_s
    (PERS tMaxCamara de RAPID): entonces para con un error, nunca inventa una posicion. El PC la configura al empezar la tanda con
    los ajustes de RAPID (configurar): altura de la cinta, punto de recogida (para elegir la caja mas cercana si hay varias) y espera."""

    def __init__(self, proveedor=None, modelo=None, z_cinta: float = 220.0, alto_mm: float | None = None, params=None, fondo=None,
                 centro_nominal=None, tiempo_max_s: float = 5.0, pausa_s: float = 0.1, motivo_sin_configurar: str | None = None):
        self.proveedor = proveedor
        self.modelo = modelo
        self.z_cinta = z_cinta
        self.alto_mm = alto_mm
        self.params = params
        self.fondo = fondo
        self.centro_nominal = centro_nominal
        self.tiempo_max_s = tiempo_max_s
        self.pausa_s = pausa_s
        self._motivo = motivo_sin_configurar

    @classmethod
    def desde_config(cls, cfg) -> "FuenteCamara":
        """A partir de la seccion 'camara' de la configuracion de la celda (ver docs/vision.md)."""
        import cv2

        from vision.camara import ModeloCamara
        from vision.proveedores import abrir_proveedor
        c = cfg.camara
        if not c:
            return cls(motivo_sin_configurar="falta la seccion 'camara' en config_celda.json (calibracion, origen de las imagenes y alto "
                                              "de la caja): ver docs/vision.md")
        if not c.get("calibracion"):
            raise ValueError("camara.calibracion: falta la ruta del camara.json de calibracion.camara")
        params = dict(c.get("params") or {})
        for clave in ("modo", "hsv_bajo", "hsv_alto", "umbral_fondo"):
            if clave in c:
                params[clave] = c[clave]
        fondo = None
        if c.get("fondo"):
            fondo = cv2.imread(c["fondo"], cv2.IMREAD_COLOR)
            if fondo is None:
                raise ValueError(f"camara.fondo: no puedo leer {c['fondo']}")
        modelo = ModeloCamara.cargar(c["calibracion"])   # antes que abrir la camara: si falta la calibracion, que lo diga primero
        return cls(abrir_proveedor(c.get("origen") or {}), modelo, cfg.z_cinta,
                   None if c.get("alto_mm") is None else float(c["alto_mm"]), params, fondo, cfg.centro_recogida, cfg.t_max_camara)

    def configurar(self, cfg) -> None:
        """Pone lo que RAPID dice (la app del FlexPendant): altura de la cinta, punto de recogida y espera maxima a la camara."""
        self.z_cinta = cfg.z_cinta
        self.centro_nominal = cfg.centro_recogida
        self.tiempo_max_s = cfg.t_max_camara

    def leer(self, i: int) -> Caja:
        if self.proveedor is None:
            raise RuntimeError("percepcion por camara sin configurar: " + (self._motivo or "falta el proveedor de imagenes"))
        from vision.deteccion import detectar_cajas, elegir
        limite = time.monotonic() + self.tiempo_max_s
        recortada = False
        while True:
            fot = self.proveedor.siguiente()
            if fot is None:
                raise RuntimeError("la camara no tiene mas imagenes (carpeta agotada o camara cerrada)")
            dets = detectar_cajas(fot.bgr, self.modelo, self.z_cinta, self.alto_mm, self.params, self.fondo, fot.profundidad)
            enteras = [d for d in dets if not d.recortada]
            recortada = recortada or (bool(dets) and not enteras)
            d = elegir(enteras, self.centro_nominal)
            if d is not None:
                return d.a_caja()
            if time.monotonic() >= limite:
                raise RuntimeError(f"la camara no ve ninguna caja entera en {self.tiempo_max_s:g} s (tMaxCamara)"
                                   + ("; la que ve esta cortada por el borde de la imagen" if recortada else ""))
            time.sleep(self.pausa_s)

    def total(self):
        return None  # sin fin conocido: manda nCajas de RAPID (la app)


def crear_fuente(cfg):
    if not cfg.modo_simulacion:
        return FuenteCamara.desde_config(cfg)
    return FuenteCsv(cfg.csv_caja, cfg.centro_recogida[0], cfg.sensor_cinta_y)
