"""Geometría de la celda: posiciones en milímetros y rotaciones como cuaterniones.

Convenciones del proyecto. No cambiarlas sin cambiar también el puente EGM:
- Posiciones en mm, vectores como np.ndarray de forma (3,).
- Cuaterniones unitarios (w, x, y, z) con producto de Hamilton. R(q) es rotación activa.
- Pose: transformación que lleva coordenadas del marco hijo al padre: p_padre = R p_hijo + t.
- Error de orientación en el marco base: r = rotvec(q_obj ⊗ conj(q_act)), es decir,
  exp(r) · R_act = R_obj.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_EPS = 1e-12


def normalizar(q) -> np.ndarray:
    """Cuaternión unitario con w >= 0 (un único representante por rotación)."""
    q = np.asarray(q, dtype=float).reshape(4)
    n = np.linalg.norm(q)
    if n < _EPS:
        raise ValueError("cuaternión nulo")
    q = q / n
    return q if q[0] >= 0.0 else -q


def multiplicar(a, b) -> np.ndarray:
    """Producto de Hamilton a ⊗ b. Cumple R(a ⊗ b) = R(a) R(b)."""
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ])


def conjugado(q) -> np.ndarray:
    w, x, y, z = np.asarray(q, dtype=float).reshape(4)
    return np.array([w, -x, -y, -z])


def a_matriz(q) -> np.ndarray:
    """Matriz 3x3 de rotación de un cuaternión."""
    w, x, y, z = normalizar(q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def desde_matriz(R) -> np.ndarray:
    """Cuaternión de una matriz de rotación (método de Shepperd, estable en todos los casos)."""
    R = np.asarray(R, dtype=float).reshape(3, 3)
    tr = np.trace(R)
    if tr > 0.0:
        s = 2.0 * np.sqrt(tr + 1.0)
        q = [0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        q = [(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s]
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        q = [(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s]
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        q = [(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s]
    return normalizar(q)


def rotvec_desde_quat(q) -> np.ndarray:
    """Logaritmo de la rotación: vector cuya norma es el ángulo (rad, en [0, π])."""
    q = normalizar(q)
    v = q[1:]
    nv = np.linalg.norm(v)
    if nv < _EPS:
        return 2.0 * v
    return v / nv * (2.0 * np.arctan2(nv, q[0]))


def quat_desde_rotvec(r) -> np.ndarray:
    """Exponencial de la rotación (inversa de rotvec_desde_quat)."""
    r = np.asarray(r, dtype=float).reshape(3)
    theta = np.linalg.norm(r)
    if theta < _EPS:
        return normalizar([1.0, *(0.5 * r)])
    eje = r / theta
    return normalizar([np.cos(theta / 2.0), *(np.sin(theta / 2.0) * eje)])


def angulo(q1, q2) -> float:
    """Ángulo (rad) de la rotación que lleva q1 a q2."""
    rel = multiplicar(conjugado(normalizar(q1)), normalizar(q2))
    return float(np.linalg.norm(rotvec_desde_quat(rel)))


def slerp(q0, q1, f: float) -> np.ndarray:
    """Recorre la fracción f (0..1) del camino más corto entre dos orientaciones."""
    q0 = normalizar(q0)
    q1 = normalizar(q1)
    d = float(np.dot(q0, q1))
    if d < 0.0:
        q1, d = -q1, -d
    if d > 0.9995:
        return normalizar(q0 + f * (q1 - q0))
    theta = np.arccos(d)
    s0 = np.sin((1.0 - f) * theta) / np.sin(theta)
    s1 = np.sin(f * theta) / np.sin(theta)
    return normalizar(s0 * q0 + s1 * q1)


@dataclass(frozen=True, eq=False)
class Pose:
    """Transformación rígida: posición t (mm) y orientación q (cuaternión)."""

    t: np.ndarray
    q: np.ndarray

    @classmethod
    def crear(cls, t=(0.0, 0.0, 0.0), q=(1.0, 0.0, 0.0, 0.0)) -> "Pose":
        return cls(np.asarray(t, dtype=float).reshape(3), normalizar(q))

    @classmethod
    def desde_matriz(cls, T) -> "Pose":
        T = np.asarray(T, dtype=float)
        return cls(T[:3, 3].copy(), desde_matriz(T[:3, :3]))

    def matriz(self) -> np.ndarray:
        T = np.eye(4)
        T[:3, :3] = a_matriz(self.q)
        T[:3, 3] = self.t
        return T

    def inversa(self) -> "Pose":
        qi = conjugado(self.q)
        return Pose(-a_matriz(qi) @ self.t, qi)

    def componer(self, otra: "Pose") -> "Pose":
        """self ∘ otra: primero se aplica otra (marco hijo) y después self."""
        return Pose(a_matriz(self.q) @ otra.t + self.t, multiplicar(self.q, otra.q))

    def aplicar(self, puntos) -> np.ndarray:
        """Transforma puntos (N, 3) del marco hijo al marco padre."""
        puntos = np.asarray(puntos, dtype=float).reshape(-1, 3)
        return puntos @ a_matriz(self.q).T + self.t


def error_pose(actual: Pose, objetivo: Pose) -> tuple[np.ndarray, np.ndarray]:
    """Error (dt en mm, dr en rad) para llevar 'actual' a 'objetivo', en el marco base."""
    dt = objetivo.t - actual.t
    dr = rotvec_desde_quat(multiplicar(objetivo.q, conjugado(actual.q)))
    return dt, dr


def interpolar(a: Pose, b: Pose, f: float) -> Pose:
    """Interpolación lineal de la posición y slerp de la orientación (f en 0..1)."""
    f = float(np.clip(f, 0.0, 1.0))
    return Pose(a.t + f * (b.t - a.t), slerp(a.q, b.q, f))
