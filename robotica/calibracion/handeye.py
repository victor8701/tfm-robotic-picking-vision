"""Calibración mano-ojo (cámara en la muñeca) con OpenCV y comprobación de consistencia.

Modelo: el objetivo de calibración está fijo en la base. Para cada pose i:
    G_i · X · C_i = Z
donde G_i = pose de la mano en la base, X = pose de la cámara en la mano (lo que buscamos),
C_i = pose del objetivo en la cámara y Z = pose del objetivo en la base (incógnita fija).
La consistencia se mide con la dispersión de Z_i = G_i · X · C_i.
"""
from __future__ import annotations

import cv2
import numpy as np

from nucleo.geometria import Pose, angulo


def calibrar_mano_ojo(T_base_mano: list[Pose], T_cam_objetivo: list[Pose],
                      metodo: int = cv2.CALIB_HAND_EYE_PARK) -> Pose:
    """Devuelve X = pose de la cámara en el marco de la mano (mm)."""
    if len(T_base_mano) != len(T_cam_objetivo) or len(T_base_mano) < 3:
        raise ValueError("hacen falta al menos 3 pares de poses")
    Rg = [p.matriz()[:3, :3] for p in T_base_mano]
    tg = [p.t.reshape(3, 1) for p in T_base_mano]
    Rt = [p.matriz()[:3, :3] for p in T_cam_objetivo]
    tt = [p.t.reshape(3, 1) for p in T_cam_objetivo]
    R, t = cv2.calibrateHandEye(Rg, tg, Rt, tt, method=metodo)
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t.reshape(3)
    return Pose.desde_matriz(T)


def dispersion_objetivo_en_base(T_base_mano: list[Pose], T_cam_objetivo: list[Pose], X: Pose) -> tuple[float, float]:
    """(mm, rad): desviación típica de la pose del objetivo en la base según cada par de poses."""
    Zs = [G.componer(X).componer(C) for G, C in zip(T_base_mano, T_cam_objetivo)]
    t = np.array([z.t for z in Zs])
    centro = t.mean(axis=0)
    mm = float(np.sqrt(np.mean(np.sum((t - centro) ** 2, axis=1))))
    q0 = Zs[0].q
    rad = float(np.sqrt(np.mean([angulo(q0, z.q) ** 2 for z in Zs])))
    return mm, rad
