"""PuenteRos: el puente EGM visto desde ROS 2, con la misma interfaz que `ClientePuente` (estado y objetivo).

`celda.ciclo.Celda` solo necesita `estado()` y `objetivo(pose)`. Con `ClientePuente` van por TCP directamente al puente C#; con esta
clase van por topics de ROS 2 a `nodo_puente`, que es quien habla TCP con el puente:

    Celda --objetivo(pose)--> /brazo1/objetivo (PoseStamped) --> nodo_puente --TCP 7001--> PuenteEgm.exe --EGM--> robot
    Celda <---estado()------- /brazo1/estado   (String JSON) <-- nodo_puente <--TCP 7001-- PuenteEgm.exe <--EGM-- robot

El nodo de ROS tiene que estar girando (spin) en otro hilo mientras se llama a estas funciones: las respuestas llegan por callbacks.
"""
from __future__ import annotations

import json
import threading
import time

from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from std_msgs.msg import String

from nucleo.geometria import Pose

from .convertir import pose_a_ros


class PuenteRos:
    def __init__(self, nodo: Node, sesion: str = "brazo1", espera_estado_s: float = 1.5, caducidad_estado_s: float = 1.0,
                 vigencia_rechazo_s: float = 0.5):
        self._nodo = nodo
        self._sesion = sesion
        self._espera_estado_s = espera_estado_s
        self._caducidad_estado_s = caducidad_estado_s
        self._vigencia_rechazo_s = vigencia_rechazo_s
        self._cerrojo = threading.Lock()
        self._estado: dict | None = None
        self._t_estado = 0.0
        self._rechazo: dict | None = None
        self._t_rechazo = 0.0
        self._pub = nodo.create_publisher(PoseStamped, f"/{sesion}/objetivo", 10)
        nodo.create_subscription(String, f"/{sesion}/estado", self._al_recibir_estado, 10)
        nodo.create_subscription(String, f"/{sesion}/rechazo", self._al_recibir_rechazo, 10)

    def _al_recibir_estado(self, msg: String) -> None:
        try:
            dic = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        with self._cerrojo:
            self._estado, self._t_estado = dic, time.monotonic()

    def _al_recibir_rechazo(self, msg: String) -> None:
        try:
            dic = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        with self._cerrojo:
            self._rechazo, self._t_rechazo = dic, time.monotonic()

    def estado(self) -> dict:
        """Ultimo estado que publico nodo_puente (el dict que devuelve el puente C#). OSError si no llega ninguno reciente."""
        limite = time.monotonic() + self._espera_estado_s
        while True:
            with self._cerrojo:
                if self._estado is not None and time.monotonic() - self._t_estado <= self._caducidad_estado_s:
                    return dict(self._estado)
            if time.monotonic() >= limite:
                raise OSError(f"no llega /{self._sesion}/estado: ¿estan en marcha nodo_puente y el puente EGM (PuenteEgm.exe)?")
            time.sleep(0.005)

    def objetivo(self, pose: Pose) -> dict:
        """Publica el objetivo (brida, en la base). Devuelve {"ok": True} o, si el puente rechazo el ultimo objetivo hace un momento,
        la respuesta del puente ({"ok": False, ...}), como hace ClientePuente."""
        (x, y, z), (qx, qy, qz, qw) = pose_a_ros(pose)
        msg = PoseStamped()
        msg.header.stamp = self._nodo.get_clock().now().to_msg()
        msg.header.frame_id = f"base_{self._sesion}"
        msg.pose.position.x, msg.pose.position.y, msg.pose.position.z = x, y, z
        msg.pose.orientation.x, msg.pose.orientation.y, msg.pose.orientation.z, msg.pose.orientation.w = qx, qy, qz, qw
        self._pub.publish(msg)
        with self._cerrojo:
            if self._rechazo is not None and time.monotonic() - self._t_rechazo <= self._vigencia_rechazo_s:
                rechazo, self._rechazo = self._rechazo, None
                return rechazo
        return {"ok": True}
