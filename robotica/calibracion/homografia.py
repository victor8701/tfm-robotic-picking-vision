"""Homografía píxel → mesa (mm) con validación con puntos no usados.

Corrige tres fallos de la calibración del curso (ver README del proyecto y docs/guion_V1.md):
- Se exigen al menos 6 puntos: 4 para ajustar y 2 para validar. Con 4 puntos el error es cero
  siempre y no valida nada.
- La validación se hace con puntos que no entran en el ajuste.
- Hay RANSAC para descartar puntos mal medidos.
La homografía solo vale para un plano; el plano debe ser el de la altura de referencia (ver README).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

UMBRAL_OBJETIVO_MM = 5.0
UMBRAL_ACEPTABLE_MM = 15.0


def _normalizar(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centro = pts.mean(axis=0)
    escala = np.sqrt(2.0) / np.mean(np.linalg.norm(pts - centro, axis=1))
    T = np.array([[escala, 0.0, -escala * centro[0]], [0.0, escala, -escala * centro[1]], [0.0, 0.0, 1.0]])
    return T, (np.hstack([pts, np.ones((len(pts), 1))]) @ T.T)[:, :2]


def estimar_homografia(src, dst) -> np.ndarray:
    """DLT normalizada (Hartley) por mínimos cuadrados. Requiere al menos 4 correspondencias."""
    src = np.asarray(src, dtype=float).reshape(-1, 2)
    dst = np.asarray(dst, dtype=float).reshape(-1, 2)
    if len(src) < 4 or len(src) != len(dst):
        raise ValueError("hacen falta al menos 4 correspondencias")
    Ts, s = _normalizar(src)
    Td, d = _normalizar(dst)
    filas = []
    for (x, y), (u, v) in zip(s, d):
        filas.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        filas.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, vt = np.linalg.svd(np.asarray(filas))
    Hn = vt[-1].reshape(3, 3)
    H = np.linalg.inv(Td) @ Hn @ Ts
    return H / H[2, 2]


def aplicar(H: np.ndarray, pts) -> np.ndarray:
    pts = np.asarray(pts, dtype=float).reshape(-1, 2)
    h = np.hstack([pts, np.ones((len(pts), 1))]) @ H.T
    return h[:, :2] / h[:, 2:3]


def errores(H: np.ndarray, src, dst) -> np.ndarray:
    """Distancia (mm) entre H(src) y dst, punto a punto."""
    return np.linalg.norm(aplicar(H, src) - np.asarray(dst, dtype=float).reshape(-1, 2), axis=1)


def homografia_ransac(src, dst, umbral_mm: float = 3.0, iteraciones: int = 500,
                      semilla: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Ajuste robusto: devuelve (H, máscara de inliers). Reajusta con todos los inliers al final."""
    src = np.asarray(src, dtype=float).reshape(-1, 2)
    dst = np.asarray(dst, dtype=float).reshape(-1, 2)
    n = len(src)
    if n < 4:
        raise ValueError("hacen falta al menos 4 correspondencias")
    rng = np.random.default_rng(semilla)
    mejor_mascara = None
    mejor_cuenta = -1
    for _ in range(iteraciones):
        idx = rng.choice(n, size=4, replace=False)
        try:
            Hc = estimar_homografia(src[idx], dst[idx])
        except (ValueError, np.linalg.LinAlgError):
            continue
        mascara = errores(Hc, src, dst) < umbral_mm
        cuenta = int(mascara.sum())
        if cuenta > mejor_cuenta:
            mejor_cuenta, mejor_mascara = cuenta, mascara
    if mejor_mascara is None or mejor_cuenta < 4:
        raise ValueError("RANSAC no encuentra un ajuste con 4 o más inliers")
    return estimar_homografia(src[mejor_mascara], dst[mejor_mascara]), mejor_mascara


@dataclass(frozen=True)
class InformeCalibracion:
    H: np.ndarray
    n_puntos: int
    n_inliers: int
    rms_ajuste_mm: float
    rms_validacion_mm: float
    criterio: str   # "objetivo", "aceptable" o "repetir"


def evaluar(src, dst, n_validacion: int = 2, umbral_mm: float = 3.0) -> InformeCalibracion:
    """Calibra con todos los puntos menos los n_validacion últimos, y valida con estos últimos."""
    src = np.asarray(src, dtype=float).reshape(-1, 2)
    dst = np.asarray(dst, dtype=float).reshape(-1, 2)
    if len(src) < 6:
        raise ValueError("hacen falta al menos 6 puntos (4 para ajustar y 2 para validar)")
    if n_validacion < 2:
        raise ValueError("hacen falta al menos 2 puntos de validación")
    corte = len(src) - n_validacion
    H, mascara = homografia_ransac(src[:corte], dst[:corte], umbral_mm=umbral_mm)
    e_ajuste = errores(H, src[:corte][mascara], dst[:corte][mascara])
    e_val = errores(H, src[corte:], dst[corte:])
    rms_val = float(np.sqrt(np.mean(e_val ** 2)))
    if rms_val < UMBRAL_OBJETIVO_MM:
        criterio = "objetivo"
    elif rms_val < UMBRAL_ACEPTABLE_MM:
        criterio = "aceptable"
    else:
        criterio = "repetir"
    return InformeCalibracion(
        H=H,
        n_puntos=len(src),
        n_inliers=int(mascara.sum()),
        rms_ajuste_mm=float(np.sqrt(np.mean(e_ajuste ** 2))),
        rms_validacion_mm=rms_val,
        criterio=criterio,
    )
