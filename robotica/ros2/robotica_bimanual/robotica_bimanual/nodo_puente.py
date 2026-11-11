"""Nodo puente: reenvía los objetivos de ROS 2 a los puentes EGM y publica el estado real de cada brazo.

Topics (metros, cuaterniones x-y-z-w), un único robot (brazo1):
  entrada:  /brazo1/objetivo  (geometry_msgs/PoseStamped, pose en la base del brazo)
            /puentes/comando                   (std_msgs/String: parar | arrancar | reset)
  salida:   /brazo1/pose_real (PoseStamped, TCP real en la base)
            /brazo1/estado       (String, JSON tal como lo devuelve el puente)

Un objetivo que no se renueva en `plazo_objetivo_s` no se reenvía: el puente lo trata como
vencido y retiene el brazo. Así, si el coordinador deja de mandar objetivos, el brazo se para.
"""
from __future__ import annotations

import json
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from std_msgs.msg import String

from .cliente_puente import ClientePuente
from .convertir import pose_a_ros, pose_desde_estado_puente, pose_desde_ros

# Un único robot. La versión de dos brazos está en la rama robotica-bimanual.
BRAZOS = ("brazo1",)
PUERTOS_POR_DEFECTO = {"brazo1": 7001}


class NodoPuente(Node):
    def __init__(self):
        super().__init__("nodo_puente")
        self.declare_parameter("frecuencia_hz", 25.0)
        self.declare_parameter("plazo_objetivo_s", 0.2)
        self._plazo = float(self.get_parameter("plazo_objetivo_s").value)
        self._brazos: dict[str, dict] = {}
        for nombre in BRAZOS:
            self.declare_parameter(f"{nombre}.host", "127.0.0.1")
            self.declare_parameter(f"{nombre}.puerto", PUERTOS_POR_DEFECTO[nombre])
            cliente = ClientePuente(str(self.get_parameter(f"{nombre}.host").value),
                                    int(self.get_parameter(f"{nombre}.puerto").value))
            self._brazos[nombre] = {
                "cliente": cliente,
                "objetivo": None,
                "t_objetivo": 0.0,
                "pub_real": self.create_publisher(PoseStamped, f"/{nombre}/pose_real", 10),
                "pub_estado": self.create_publisher(String, f"/{nombre}/estado", 10),
            }
            self.create_subscription(PoseStamped, f"/{nombre}/objetivo",
                                     lambda m, n=nombre: self._recibir_objetivo(n, m), 10)
        self.create_subscription(String, "/puentes/comando", self._comando, 10)
        self.create_timer(1.0 / float(self.get_parameter("frecuencia_hz").value), self._ciclo)

    def _recibir_objetivo(self, nombre: str, msg: PoseStamped) -> None:
        p, q = msg.pose.position, msg.pose.orientation
        self._brazos[nombre]["objetivo"] = pose_desde_ros((p.x, p.y, p.z), (q.x, q.y, q.z, q.w))
        self._brazos[nombre]["t_objetivo"] = time.monotonic()

    def _comando(self, msg: String) -> None:
        metodo = {"parar": "parar", "arrancar": "arrancar", "reset": "reset"}.get(msg.data)
        if metodo is None:
            self.get_logger().warning(f"comando de puente desconocido: {msg.data!r}")
            return
        for nombre in BRAZOS:
            try:
                respuesta = getattr(self._brazos[nombre]["cliente"], metodo)()
                self.get_logger().info(f"{nombre} {metodo}: {respuesta}")
            except OSError as e:
                self.get_logger().error(f"{nombre} {metodo} sin conexión: {e}")

    def _ciclo(self) -> None:
        ahora = time.monotonic()
        for nombre in BRAZOS:
            b = self._brazos[nombre]
            if b["objetivo"] is not None and ahora - b["t_objetivo"] <= self._plazo:
                try:
                    b["cliente"].objetivo(b["objetivo"])
                except OSError as e:
                    self.get_logger().warning(f"{nombre}: objetivo no enviado: {e}", throttle_duration_sec=2.0)
            try:
                estado = b["cliente"].estado()
            except OSError as e:
                self.get_logger().warning(f"{nombre}: sin estado del puente: {e}", throttle_duration_sec=2.0)
                continue
            b["pub_estado"].publish(String(data=json.dumps(estado)))
            if estado.get("ok") and "real" in estado:
                real = pose_desde_estado_puente(estado["real"])
                (x, y, z), (qx, qy, qz, qw) = pose_a_ros(real)
                msg = PoseStamped()
                msg.header.stamp = self.get_clock().now().to_msg()
                msg.header.frame_id = f"base_{nombre}"
                msg.pose.position.x, msg.pose.position.y, msg.pose.position.z = x, y, z
                msg.pose.orientation.x, msg.pose.orientation.y = qx, qy
                msg.pose.orientation.z, msg.pose.orientation.w = qz, qw
                b["pub_real"].publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    nodo = NodoPuente()
    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        nodo.destroy_node()
        rclpy.shutdown()
