"""Conversiones entre ROS 2 y el núcleo, sin depender de rclpy.

Convención: en ROS 2 las posiciones van en metros y los cuaterniones como (x, y, z, w) (REP 103).
En el núcleo y en el puente van en milímetros y (w, x, y, z). Todas las conversiones pasan por aquí.
"""
from __future__ import annotations

import numpy as np

from nucleo.geometria import Pose, normalizar

M_A_MM = 1000.0


def pose_desde_ros(posicion_m, orientacion_xyzw) -> Pose:
    """Pose del núcleo (mm, w-x-y-z) a partir de una pose de ROS (m, x-y-z-w)."""
    x, y, z = posicion_m
    qx, qy, qz, qw = orientacion_xyzw
    return Pose.crear(t=[x * M_A_MM, y * M_A_MM, z * M_A_MM], q=normalizar([qw, qx, qy, qz]))


def pose_a_ros(pose: Pose) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
    """(posición en m, orientación x-y-z-w) a partir de una pose del núcleo."""
    posicion = tuple(float(v) / M_A_MM for v in pose.t)
    w, x, y, z = (float(v) for v in pose.q)
    return posicion, (x, y, z, w)


def pose_desde_estado_puente(real: dict) -> Pose:
    """Pose del TCP reportada por el puente ({"t": [mm], "q": [w, x, y, z]})."""
    return Pose.crear(t=real["t"], q=real["q"])


def comando_objetivo(pose: Pose) -> dict:
    """Mensaje JSON del puente con el objetivo (mm, cuaternión w-x-y-z)."""
    return {"cmd": "objetivo", "t": [float(v) for v in pose.t], "q": [float(v) for v in pose.q]}


def imagen_desde_ros(msg) -> np.ndarray:
    """Imagen BGR (uint8) a partir de un sensor_msgs/Image con encoding bgr8 o rgb8."""
    if msg.encoding not in ("bgr8", "rgb8"):
        raise ValueError(f"encoding no soportado: {msg.encoding}")
    img = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(msg.height, msg.width, 3)
    return img if msg.encoding == "bgr8" else img[:, :, ::-1].copy()


def camara_desde_ros(k, d) -> tuple[np.ndarray, np.ndarray]:
    """Matriz intrínseca 3x3 y distorsión a partir de sensor_msgs/CameraInfo (K en orden fila a fila)."""
    K = np.asarray(k, dtype=float).reshape(3, 3)
    dist = np.asarray(d, dtype=float) if len(d) else np.zeros(5)
    return K, dist
