"""Modelo de una cámara calibrada: intrínsecos, distorsión y pose en la base del robot (mm).

Con él se pasa de un píxel a un punto de un plano horizontal de la celda (la cinta, la tapa de una caja) y al revés.
Se guarda en un JSON que escribe el programa de calibración (`python -m calibracion.camara`) y que lee la detección
de cajas (`vision.deteccion`, `celda.percepcion.FuenteCamara`).

Marcos: base = el del robot (x, y en el plano de la cinta, z hacia arriba). La cámara se describe con
`T_base_cam`: pose del marco óptico (x a la derecha de la imagen, y hacia abajo, z hacia delante) en la base.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from nucleo.geometria import Pose

FORMATO = "camara-celda-1"


def intrinsecos_por_campo_de_vision(tam: tuple[int, int], fov_horizontal_deg: float) -> np.ndarray:
    """K aproximada de una cámara de la que solo se sabe el campo de visión horizontal (píxeles cuadrados, centro de la
    imagen). Vale para pruebas en casa con fotos de móvil; en la celda hay que calibrar (`calibracion.camara intrinsecos`)."""
    ancho, alto = tam
    f = (ancho / 2.0) / np.tan(np.radians(fov_horizontal_deg) / 2.0)
    return np.array([[f, 0.0, ancho / 2.0], [0.0, f, alto / 2.0], [0.0, 0.0, 1.0]])


@dataclass(frozen=True)
class ModeloCamara:
    K: np.ndarray
    dist: np.ndarray
    T_base_cam: Pose
    tam: tuple[int, int]                      # (ancho, alto) de la imagen en píxeles
    info: dict = field(default_factory=dict)  # lo que dejó la calibración: rms, criterio, fecha...

    @property
    def posicion(self) -> np.ndarray:
        """Centro óptico de la cámara en la base (mm)."""
        return self.T_base_cam.t

    def rayos_base(self, px) -> np.ndarray:
        """Direcciones unitarias, en la base, de los rayos que pasan por los píxeles (N, 2). Corrige la distorsión."""
        pts = np.asarray(px, dtype=np.float64).reshape(-1, 1, 2)
        n = cv2.undistortPoints(pts, self.K, self.dist).reshape(-1, 2)
        d_cam = np.hstack([n, np.ones((len(n), 1))])
        d = d_cam @ self.T_base_cam.matriz()[:3, :3].T
        return d / np.linalg.norm(d, axis=1, keepdims=True)

    def pixel_a_plano(self, px, z: float) -> np.ndarray:
        """(x, y) en la base de los puntos del plano horizontal de altura z (mm) que se ven en los píxeles (N, 2)."""
        d = self.rayos_base(px)
        o = self.posicion
        if np.any(np.abs(d[:, 2]) < 1e-9):
            raise ValueError("un rayo es paralelo al plano: la cámara no puede medir ahí")
        s = (z - o[2]) / d[:, 2]
        if np.any(s <= 0):
            raise ValueError(f"el plano z = {z:g} mm queda detrás de la cámara (cámara a z = {o[2]:g} mm) o no se ve desde ella")
        return (o + s[:, None] * d)[:, :2]

    def base_a_pixel(self, puntos) -> np.ndarray:
        """Píxeles (N, 2) donde se ven puntos 3D de la base (N, 3), con la distorsión del objetivo."""
        pts = np.asarray(puntos, dtype=np.float64).reshape(-1, 3)
        T = self.T_base_cam.inversa().matriz()
        rvec, _ = cv2.Rodrigues(T[:3, :3])
        px, _ = cv2.projectPoints(pts, rvec, T[:3, 3].reshape(3, 1), self.K, self.dist)
        return px.reshape(-1, 2)

    # ---------------------------------------------------------------- JSON
    def a_dict(self) -> dict:
        return {
            "formato": FORMATO,
            "tam": [int(self.tam[0]), int(self.tam[1])],
            "K": np.asarray(self.K, dtype=float).tolist(),
            "dist": np.asarray(self.dist, dtype=float).reshape(-1).tolist(),
            "T_base_cam": {"t": self.T_base_cam.t.tolist(), "q": self.T_base_cam.q.tolist()},
            "info": self.info,
        }

    @classmethod
    def desde_dict(cls, d: dict) -> "ModeloCamara":
        try:
            if d.get("formato") != FORMATO:
                raise ValueError(f"se esperaba formato {FORMATO!r} y es {d.get('formato')!r}")
            K = np.asarray(d["K"], dtype=np.float64)
            dist = np.asarray(d["dist"], dtype=np.float64).reshape(-1)
            if K.shape != (3, 3):
                raise ValueError("K debe ser 3x3")
            if len(d["tam"]) != 2:
                raise ValueError("tam debe ser [ancho, alto]")
            pose = Pose.crear(t=d["T_base_cam"]["t"], q=d["T_base_cam"]["q"])
        except (KeyError, TypeError) as e:
            raise ValueError(f"calibración de cámara incompleta: falta o sobra {e}") from None
        return cls(K, dist, pose, (int(d["tam"][0]), int(d["tam"][1])), dict(d.get("info", {})))

    def guardar(self, ruta) -> None:
        Path(ruta).write_text(json.dumps(self.a_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def cargar(cls, ruta) -> "ModeloCamara":
        try:
            datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        except OSError as e:
            raise ValueError(f"no puedo leer la calibración de la cámara {ruta}: {e}") from None
        except json.JSONDecodeError as e:
            raise ValueError(f"{ruta} no es un JSON válido: {e}") from None
        return cls.desde_dict(datos)
