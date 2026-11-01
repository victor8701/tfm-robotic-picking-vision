"""Pose de la caja respecto a la cámara a partir de sus cuatro esquinas.

La caja se modela como un rectángulo plano de ancho x largo (su borde superior o su fondo).
El origen del marco de la caja está en su centro; x a lo largo del ancho, y a lo largo del largo.
Las esquinas se pasan en el orden TL, TR, BR, BL del detector (esquinas.py).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from nucleo.geometria import Pose, desde_matriz


@dataclass(frozen=True)
class PoseCaja:
    T_cam_caja: Pose        # caja → cámara (mm)
    rms_px: float           # error de reproyección medio de las cuatro esquinas
    ambiguedad: float       # error del segundo mejor candidato / error del mejor (cerca de 1: dudosa)


def puntos_objeto(ancho_mm: float, largo_mm: float) -> np.ndarray:
    """Esquinas del rectángulo en el marco de la caja, en el orden TL, TR, BR, BL."""
    a, b = ancho_mm / 2.0, largo_mm / 2.0
    return np.array([[-a, -b, 0.0], [a, -b, 0.0], [a, b, 0.0], [-a, b, 0.0]], dtype=np.float64)


def pose_desde_esquinas(esquinas_px, K, dist, ancho_mm: float, largo_mm: float) -> PoseCaja:
    """Estima la pose de la caja con IPPE (plano) y elige la solución de menor error de reproyección."""
    img = np.asarray(esquinas_px, dtype=np.float64).reshape(4, 2)
    obj = puntos_objeto(ancho_mm, largo_mm)
    K = np.asarray(K, dtype=np.float64)
    dist = np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64)

    n, rvecs, tvecs, errores = cv2.solvePnPGeneric(obj, img, K, dist, flags=cv2.SOLVEPNP_IPPE)
    if n == 0:
        raise ValueError("no se pudo estimar la pose de la caja")
    orden = np.argsort(errores.reshape(-1))
    mejor = orden[0]
    ambiguedad = float(errores.reshape(-1)[orden[1]] / max(errores.reshape(-1)[mejor], 1e-12)) if n > 1 else float("inf")

    R, _ = cv2.Rodrigues(rvecs[mejor])
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = tvecs[mejor].reshape(3)
    rms = float(np.sqrt(np.mean(np.sum((cv2.projectPoints(obj, rvecs[mejor], tvecs[mejor], K, dist)[0].reshape(4, 2) - img) ** 2, axis=1))))
    return PoseCaja(Pose(T[:3, 3].copy(), desde_matriz(R)), rms, ambiguedad)
