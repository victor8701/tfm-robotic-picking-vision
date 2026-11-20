"""Percepcion de la caja: en simulacion, las medidas que genero RAPID en caja.csv;
en el laboratorio, la camara (pendiente). La interfaz es la misma: leer(i) -> Caja."""
from __future__ import annotations

import math
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
    """Pendiente: la deteccion de la caja por camara en el laboratorio."""

    def leer(self, i: int) -> Caja:
        raise NotImplementedError("percepcion por camara: pendiente para el laboratorio")

    def total(self):
        return None  # sin fin conocido: manda n_cajas de la configuracion


def crear_fuente(cfg):
    if not cfg.modo_simulacion:
        return FuenteCamara()
    return FuenteCsv(cfg.csv_caja, cfg.centro_recogida[0], cfg.sensor_cinta_y)
