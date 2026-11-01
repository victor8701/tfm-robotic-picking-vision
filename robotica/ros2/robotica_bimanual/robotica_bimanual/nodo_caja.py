"""Nodo de la caja: detecta las esquinas en la imagen de la cámara de muñeca y publica la pose de la caja.

Entrada:  imagen (sensor_msgs/Image, bgr8 o rgb8) e intrínsecos (sensor_msgs/CameraInfo).
Salida:   /caja/pose_camara (PoseStamped, caja→cámara, metros) y /caja/estado (String).
          El estado es "ok", "dudosa" (error de reproyección o ambigüedad altos: la pose no se publica)
          o "sin_caja".
"""
from __future__ import annotations

import json

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String

from vision.esquinas import esquinas_por_contorno, esquinas_por_lineas
from vision.pose_caja import pose_desde_esquinas

from .convertir import camara_desde_ros, imagen_desde_ros, pose_a_ros


class NodoCaja(Node):
    def __init__(self):
        super().__init__("nodo_caja")
        self.declare_parameter("topic_imagen", "/camara/color/image_raw")
        self.declare_parameter("topic_info", "/camara/color/camera_info")
        self.declare_parameter("metodo", "contorno")          # "contorno" o "lineas"
        self.declare_parameter("ancho_mm", 700.0)
        self.declare_parameter("largo_mm", 650.0)
        self.declare_parameter("rms_max_px", 2.0)
        self.declare_parameter("ambiguedad_min", 1.2)
        self._K = None
        self._dist = None
        self._pub_pose = self.create_publisher(PoseStamped, "/caja/pose_camara", 10)
        self._pub_estado = self.create_publisher(String, "/caja/estado", 10)
        self.create_subscription(CameraInfo, str(self.get_parameter("topic_info").value), self._info, 10)
        self.create_subscription(Image, str(self.get_parameter("topic_imagen").value), self._imagen, 10)

    def _info(self, msg: CameraInfo) -> None:
        self._K, self._dist = camara_desde_ros(msg.k, msg.d)

    def _publicar_estado(self, estado: str) -> None:
        self._pub_estado.publish(String(data=json.dumps({"estado": estado})))

    def _imagen(self, msg: Image) -> None:
        if self._K is None:
            return
        img = imagen_desde_ros(msg)
        if self.get_parameter("metodo").value == "lineas":
            esquinas = esquinas_por_lineas(img)
        else:
            esquinas = esquinas_por_contorno(img)
        if esquinas is None:
            self._publicar_estado("sin_caja")
            return
        est = pose_desde_esquinas(esquinas, self._K, self._dist,
                                  float(self.get_parameter("ancho_mm").value),
                                  float(self.get_parameter("largo_mm").value))
        if est.rms_px > float(self.get_parameter("rms_max_px").value) or \
                est.ambiguedad < float(self.get_parameter("ambiguedad_min").value):
            self._publicar_estado("dudosa")
            return
        (x, y, z), (qx, qy, qz, qw) = pose_a_ros(est.T_cam_caja)
        out = PoseStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = msg.header.frame_id or "camara_color"
        out.pose.position.x, out.pose.position.y, out.pose.position.z = x, y, z
        out.pose.orientation.x, out.pose.orientation.y = qx, qy
        out.pose.orientation.z, out.pose.orientation.w = qz, qw
        self._pub_pose.publish(out)
        self._publicar_estado("ok")


def main(args=None) -> None:
    rclpy.init(args=args)
    nodo = NodoCaja()
    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        nodo.destroy_node()
        rclpy.shutdown()
