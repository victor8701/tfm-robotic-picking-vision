"""Límites de seguridad de la referencia que se envía al controlador, por ciclo.

Reglas:
- La referencia se recorta al espacio de trabajo de cada robot.
- Un salto mayor que `paso_mm` (o un giro mayor que `giro_rad`) por ciclo se limita.
- Si el objetivo es viejo (Vigilante), se retiene la posición real del robot.
- Si la referencia se separa más de `desviacion` de la posición real, es FALLO y se
  retiene la posición real hasta que alguien rearme el sistema.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from .geometria import Pose, angulo, error_pose, slerp


class Resultado(Enum):
    OK = "ok"
    LIMITADO = "limitado"
    FALLO = "fallo"


@dataclass(frozen=True)
class EspacioTrabajo:
    """Caja alineada con la base del robot (mm)."""

    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float

    def __post_init__(self):
        if self.xmin >= self.xmax or self.ymin >= self.ymax or self.zmin >= self.zmax:
            raise ValueError("espacio de trabajo vacío o mal ordenado")

    def ajustar(self, p) -> np.ndarray:
        p = np.asarray(p, dtype=float).reshape(3)
        return np.array([
            np.clip(p[0], self.xmin, self.xmax),
            np.clip(p[1], self.ymin, self.ymax),
            np.clip(p[2], self.zmin, self.zmax),
        ])

    def contiene(self, p) -> bool:
        p = np.asarray(p, dtype=float).reshape(3)
        return bool(np.allclose(self.ajustar(p), p))


@dataclass(frozen=True)
class Limites:
    """Límites por ciclo: paso de la referencia y desviación respecto al robot real."""

    paso_mm: float
    giro_rad: float
    desviacion_mm: float
    desviacion_rad: float

    def __post_init__(self):
        if min(self.paso_mm, self.giro_rad, self.desviacion_mm, self.desviacion_rad) <= 0:
            raise ValueError("los límites deben ser positivos")


class Vigilante:
    """Watchdog: si no llega un objetivo nuevo en `plazo_s`, la consigna está vencida."""

    def __init__(self, plazo_s: float):
        if plazo_s <= 0:
            raise ValueError("el plazo debe ser positivo")
        self.plazo_s = float(plazo_s)
        self._ultimo: float | None = None

    def marcar(self, instante_s: float) -> None:
        self._ultimo = float(instante_s)

    def vencido(self, instante_s: float) -> bool:
        return self._ultimo is None or (instante_s - self._ultimo) > self.plazo_s


def retener(real: Pose) -> Pose:
    """Consigna de retención: la posición real del robot."""
    return Pose(real.t.copy(), real.q.copy())


def filtrar(ref_previa: Pose, objetivo: Pose, real: Pose,
            espacio: EspacioTrabajo, limites: Limites) -> tuple[Pose, Resultado]:
    """Siguiente referencia segura a partir de la anterior, el objetivo y el robot real."""
    limitado = False

    t_obj = espacio.ajustar(objetivo.t)
    if not np.allclose(t_obj, objetivo.t):
        limitado = True
    paso = t_obj - ref_previa.t
    n = float(np.linalg.norm(paso))
    if n > limites.paso_mm:
        paso = paso * (limites.paso_mm / n)
        limitado = True
    t_nuevo = ref_previa.t + paso

    theta = angulo(ref_previa.q, objetivo.q)
    if theta <= limites.giro_rad:
        q_nuevo = objetivo.q
    else:
        q_nuevo = slerp(ref_previa.q, objetivo.q, limites.giro_rad / theta)
        limitado = True
    ref = Pose(t_nuevo, q_nuevo)

    dt, dr = error_pose(real, ref)
    if np.linalg.norm(dt) > limites.desviacion_mm or np.linalg.norm(dr) > limites.desviacion_rad:
        return retener(real), Resultado.FALLO
    return ref, (Resultado.LIMITADO if limitado else Resultado.OK)
