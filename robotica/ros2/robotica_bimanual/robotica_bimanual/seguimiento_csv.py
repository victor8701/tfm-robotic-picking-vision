"""Lectura del registro CSV del puente y trayectoria recorrida. Sin rclpy: se prueba aparte.

El puente escribe una línea por ciclo (unos 250 por segundo) en registros/puente.csv:
    t_s,sesion,seqno,estado,real_x,real_y,real_z,ref_x,ref_y,ref_z,desviacion_mm,fase
Posiciones en mm, en la base del robot. Este módulo solo LEE el fichero: no manda nada al puente.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Muestra:
    t_s: float
    seqno: int
    estado: str
    real: tuple[float, float, float]
    ref: tuple[float, float, float]
    desviacion_mm: float
    fase: str


def _filas_recientes(ruta: str, max_bytes: int = 65536) -> tuple[list[str], list[list[str]]]:
    """Devuelve (cabecera, filas completas al final del fichero). No lee el fichero entero."""
    with open(ruta, "rb") as f:
        cabecera = f.readline().decode("utf-8").strip().split(",")
        fin_cabecera = f.tell()
        tam = f.seek(0, os.SEEK_END)
        inicio = max(fin_cabecera, tam - max_bytes)
        f.seek(inicio)
        trozo = f.read().decode("utf-8", errors="ignore")
    lineas = trozo.split("\n")
    if inicio > fin_cabecera:
        lineas = lineas[1:]  # la primera puede estar cortada a mitad
    filas = [ln.strip().split(",") for ln in lineas if ln.strip()]
    return cabecera, [fila for fila in filas if len(fila) == len(cabecera)]


def ultima_muestra(ruta: str, sesion: str = "brazo1") -> Muestra | None:
    """Última muestra de la sesión indicada, o None si el fichero no existe o aún no tiene datos."""
    if not os.path.exists(ruta):
        return None
    cabecera, filas = _filas_recientes(ruta)
    indice = {nombre: i for i, nombre in enumerate(cabecera)}
    for fila in reversed(filas):
        if fila[indice["sesion"]] == sesion:
            return _muestra(fila, indice)
    return None


def _muestra(fila: list[str], indice: dict[str, int]) -> Muestra:
    def campo(nombre: str) -> str:
        return fila[indice[nombre]] if nombre in indice else ""

    return Muestra(
        t_s=float(campo("t_s")),
        seqno=int(campo("seqno")),
        estado=campo("estado"),
        real=(float(campo("real_x")), float(campo("real_y")), float(campo("real_z"))),
        ref=(float(campo("ref_x")), float(campo("ref_y")), float(campo("ref_z"))),
        desviacion_mm=float(campo("desviacion_mm")),
        fase=campo("fase"),
    )


def _distancia(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.dist(a, b)


class Trayectoria:
    """Puntos recorridos por la posición real (mm).

    Se reinicia cuando empieza una ejecución nueva (el seqno vuelve a empezar, es decir,
    el puente se ha reiniciado). Guarda un punto solo si el robot se ha movido al menos
    `min_paso_mm` desde el último, y solo los últimos `maximo` puntos (ventana deslizante),
    para que la línea no crezca sin control.
    """

    def __init__(self, min_paso_mm: float = 1.0, maximo: int = 3000):
        self.min_paso_mm = min_paso_mm
        self.maximo = maximo
        self.puntos: list[tuple[float, float, float]] = []
        self._ultimo_seqno = -1

    def añadir(self, muestra: Muestra) -> bool:
        """Añade la muestra. Devuelve True si la trayectoria se ha reiniciado."""
        reinicio = muestra.seqno < self._ultimo_seqno
        if reinicio:
            self.puntos.clear()
        self._ultimo_seqno = muestra.seqno
        if not self.puntos or _distancia(muestra.real, self.puntos[-1]) >= self.min_paso_mm:
            self.puntos.append(muestra.real)
            if len(self.puntos) > self.maximo:
                del self.puntos[0]  # ventana: se olvidan los puntos mas antiguos
        return reinicio
