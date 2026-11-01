"""Consigna por ciclo con límites: de objetivos a 20–50 Hz a referencias de cada ciclo."""
from __future__ import annotations

import numpy as np

from .geometria import Pose, angulo, slerp


def _limitar_norma(v, m: float) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    if n <= m or n < 1e-12:
        return v
    return v * (m / n)


class SeguidorConsigna:
    """Persigue un objetivo que puede saltar, con límites de velocidad, aceleración y giro.

    Posición: control proporcional con saturación de velocidad (mm/s) y de aceleración (mm/s²).
    Orientación: slerp con un giro máximo por ciclo (rad/s).
    No usa el reloj: cada llamada a paso() avanza exactamente dt segundos.
    """

    def __init__(self, v_max: float = 125.0, a_max: float = 400.0, w_max: float = 0.6, kp: float = 5.0):
        if min(v_max, a_max, w_max, kp) <= 0:
            raise ValueError("los límites y la ganancia deben ser positivos")
        self.v_max = float(v_max)
        self.a_max = float(a_max)
        self.w_max = float(w_max)
        self.kp = float(kp)
        self.reset(Pose.crear())

    def reset(self, pose: Pose) -> None:
        self.pose = pose
        self.velocidad = np.zeros(3)

    def paso(self, objetivo: Pose, dt: float) -> Pose:
        if dt <= 0:
            raise ValueError("dt debe ser positivo")
        v_des = _limitar_norma(self.kp * (objetivo.t - self.pose.t), self.v_max)
        dv = _limitar_norma(v_des - self.velocidad, self.a_max * dt)
        self.velocidad = self.velocidad + dv
        t_nuevo = self.pose.t + self.velocidad * dt

        theta = angulo(self.pose.q, objetivo.q)
        giro = self.w_max * dt
        f = 1.0 if theta <= giro else giro / theta
        q_nuevo = slerp(self.pose.q, objetivo.q, f)

        self.pose = Pose(t_nuevo, q_nuevo)
        return self.pose
