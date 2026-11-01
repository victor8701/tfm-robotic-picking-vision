"""Ley PBVS (control basado en la pose) para la cámara de muñeca del brazo maestro.

Modelo, con la caja quieta y el torsor de la cámara (v, w) expresado en su propio marco:
    d(t_cb)/dt = -v - w × t_cb        d(R_cb)/dt = -[w]× R_cb
donde T_cb es la pose de la caja en el marco de la cámara (caja → cámara).

Con Q = R_cb · R_des^T, para errores pequeños θ̇ = -w, siendo θ = log(Q). La ley es:
    w = λr · θ                       v = λt · (t_cb - t_des) - w × t_cb
que da d(t_cb - t_des)/dt = -λt (t_cb - t_des) y θ̇ = -λr θ. Es una aproximación en el
paso de control; integrar_camara() y simular_pbvs() permiten comprobarla numéricamente.
"""
from __future__ import annotations

import numpy as np

from .geometria import Pose, a_matriz, conjugado, multiplicar, quat_desde_rotvec, rotvec_desde_quat


def _limitar_norma(v, m: float) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    if n <= m or n < 1e-12:
        return v
    return v * (m / n)


def ley_pbvs(T_cb: Pose, T_cb_deseada: Pose, lam_t: float = 2.0, lam_r: float = 2.0,
             v_max: float = 100.0, w_max: float = 0.3,
             zona_t_mm: float = 0.5, zona_r_rad: float = 0.002) -> tuple[np.ndarray, np.ndarray]:
    """Torsor de cámara (v en mm/s, w en rad/s, en el marco de cámara) que reduce el error."""
    e_t = T_cb.t - T_cb_deseada.t
    theta = rotvec_desde_quat(multiplicar(T_cb.q, conjugado(T_cb_deseada.q)))
    if np.linalg.norm(e_t) < zona_t_mm and np.linalg.norm(theta) < zona_r_rad:
        return np.zeros(3), np.zeros(3)
    omega = lam_r * theta
    v = lam_t * e_t - np.cross(omega, T_cb.t)
    return _limitar_norma(v, v_max), _limitar_norma(omega, w_max)


def _antisimetrica(w) -> np.ndarray:
    return np.array([[0.0, -w[2], w[1]], [w[2], 0.0, -w[0]], [-w[1], w[0], 0.0]])


def _jacobiano_v(phi) -> np.ndarray:
    """Parte traslacional de la exponencial de SE(3) para la parte rotacional phi."""
    th = np.linalg.norm(phi)
    S = _antisimetrica(phi)
    if th < 1e-8:
        return np.eye(3) + 0.5 * S
    return np.eye(3) + (1.0 - np.cos(th)) / th**2 * S + (th - np.sin(th)) / th**3 * (S @ S)


def integrar_camara(T_cb: Pose, v, w, dt: float) -> Pose:
    """Avanza dt la pose caja→cámara cuando la cámara se mueve con torsor (v, w).

    Equivale a T_cb ← exp(-ξ·dt) · T_cb, con ξ = (v, w) en el marco de cámara.
    """
    phi = -np.asarray(w, dtype=float) * dt
    q_d = quat_desde_rotvec(phi)
    t_nuevo = a_matriz(q_d) @ T_cb.t + _jacobiano_v(phi) @ (-np.asarray(v, dtype=float) * dt)
    return Pose(t_nuevo, multiplicar(q_d, T_cb.q))


def error_pbvs(T_cb: Pose, T_cb_deseada: Pose) -> tuple[float, float]:
    """(|error de posición| en mm, |error de orientación| en rad)."""
    e_t = np.linalg.norm(T_cb.t - T_cb_deseada.t)
    e_r = np.linalg.norm(rotvec_desde_quat(multiplicar(T_cb.q, conjugado(T_cb_deseada.q))))
    return float(e_t), float(e_r)


def simular_pbvs(T0: Pose, T_des: Pose, pasos: int, dt: float, delay_pasos: int = 0,
                 **parametros) -> tuple[Pose, list[tuple[float, float]]]:
    """Simula la convergencia con retardo opcional de comandos. Devuelve (pose final, historia)."""
    historia = []
    cola: list[tuple[np.ndarray, np.ndarray]] = []
    T = T0
    for _ in range(pasos):
        cola.append(ley_pbvs(T, T_des, **parametros))
        if len(cola) > delay_pasos:
            v, w = cola.pop(0)
        else:
            v, w = np.zeros(3), np.zeros(3)
        T = integrar_camara(T, v, w, dt)
        historia.append(error_pbvs(T, T_des))
    return T, historia
