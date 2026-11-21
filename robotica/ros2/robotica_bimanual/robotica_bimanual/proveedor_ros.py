"""ProveedorRos: las imágenes de la cámara por topics de ROS 2 (driver de la RealSense o de una cámara USB).

Tiene la misma interfaz que los proveedores de `vision.proveedores` (`siguiente()` devuelve un `Fotograma`), así que `FuenteCamara` lo usa
igual. El nodo de ROS tiene que estar girando (spin) en otro hilo: las imágenes llegan por callbacks.

Con la RealSense (`realsense2_camera`, con `align_depth.enable:=true`):
    topic_color        = /camera/color/image_raw
    topic_profundidad  = /camera/aligned_depth_to_color/image_raw     (16UC1, mm, alineada con el color)
"""
from __future__ import annotations

import threading
import time

from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

from vision.proveedores import Fotograma

from .convertir import imagen_desde_ros, profundidad_desde_ros

# Los drivers de cámara publican con QoS «best effort» (sensor_data): con el QoS por defecto (fiable) no llegaría nada.
DESFASE_MAX_S = 0.25


class ProveedorRos:
    def __init__(self, nodo: Node, topic_color: str, topic_profundidad: str | None = None, espera_s: float = 2.0):
        self._topic_color = topic_color
        self._topic_prof = topic_profundidad
        self._espera_s = espera_s
        self._cerrojo = threading.Lock()
        self._color = None          # (bgr, t_s)
        self._prof = None           # (mm, t_s)
        self._n_color = 0
        self._n_devuelto = 0
        nodo.create_subscription(Image, topic_color, self._al_recibir_color, qos_profile_sensor_data)
        if topic_profundidad:
            nodo.create_subscription(Image, topic_profundidad, self._al_recibir_profundidad, qos_profile_sensor_data)

    @staticmethod
    def _t(msg: Image) -> float:
        return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

    def _al_recibir_color(self, msg: Image) -> None:
        bgr = imagen_desde_ros(msg)
        with self._cerrojo:
            self._color, self._n_color = (bgr, self._t(msg)), self._n_color + 1

    def _al_recibir_profundidad(self, msg: Image) -> None:
        prof = profundidad_desde_ros(msg)
        with self._cerrojo:
            self._prof = (prof, self._t(msg))

    def siguiente(self) -> Fotograma:
        """La siguiente imagen nueva (con su profundidad si se configuró). RuntimeError si no llega ninguna en `espera_s`."""
        limite = time.monotonic() + self._espera_s
        while True:
            with self._cerrojo:
                if self._n_color > self._n_devuelto and self._color is not None:
                    bgr, t_color = self._color
                    if not self._topic_prof:
                        self._n_devuelto = self._n_color
                        return Fotograma(bgr, None, "ros")
                    if self._prof is not None and abs(self._prof[1] - t_color) <= DESFASE_MAX_S:
                        self._n_devuelto = self._n_color
                        return Fotograma(bgr, self._prof[0], "ros")
            if time.monotonic() >= limite:
                if self._n_color == 0:
                    raise RuntimeError(f"no llegan imágenes por {self._topic_color}: ¿está en marcha el driver de la cámara? (ros2 topic list)")
                raise RuntimeError(f"no llega la profundidad de {self._topic_prof} sincronizada con el color: ¿está activada la alineación "
                                   "(align_depth.enable:=true)?")
            time.sleep(0.005)
