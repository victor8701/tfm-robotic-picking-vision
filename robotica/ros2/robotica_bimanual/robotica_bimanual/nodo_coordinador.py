"""Nodo coordinador: ejecuta el Coordinador de nucleo/coordinador.py a una frecuencia fija.

Entrada:  /caja/pose_camara (PoseStamped), /brazo1/pose_real y /brazo2/pose_real (PoseStamped),
          /coordinador/orden (String: iniciar | parar | reset | agarre_hecho | verificado | soltar).
Salida:   /brazo1/objetivo, /brazo2/objetivo (PoseStamped en cada base; no se publica si se mantiene),
          /coordinador/estado (String JSON), /puentes/comando (String: parar | reset).

Las lecturas viejas (más de `plazo_lectura_s`) cuentan como ausentes: el coordinador entra en FALLO
si pierde la posición real o la visión durante una fase activa.
"""
from __future__ import annotations

import json

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from std_msgs.msg import String

from nucleo.coordinador import Coordinador
from nucleo.maquina_estados import Evento
from nucleo.parametros import RUTA_POR_DEFECTO, cargar_celda

from .convertir import pose_a_ros, pose_desde_ros

ORDENES = {
    "iniciar": Evento.INICIAR,
    "parar": Evento.PARADA,
    "reset": Evento.RESET,
    "agarre_hecho": Evento.AGARRE_HECHO,
    "verificado": Evento.VERIFICADO,
    "soltar": Evento.SOLTADO,
}


class NodoCoordinador(Node):
    def __init__(self):
        super().__init__("nodo_coordinador")
        self.declare_parameter("celda", str(RUTA_POR_DEFECTO))
        self.declare_parameter("periodo_s", 0.04)
        self.declare_parameter("plazo_lectura_s", 0.3)
        celda = cargar_celda(str(self.get_parameter("celda").value))
        self._celda = celda
        self._co = Coordinador(celda.bimanual, celda.coordinacion)
        self._periodo = float(self.get_parameter("periodo_s").value)
        self._plazo = float(self.get_parameter("plazo_lectura_s").value)
        self._caja = None
        self._t_caja = None
        self._real: dict[str, tuple[object, float] | None] = {"brazo1": None, "brazo2": None}
        self._pendientes = []
        self._parada_avisada = False

        self._pub_obj = {n: self.create_publisher(PoseStamped, f"/{n}/objetivo", 10)
                         for n in ("brazo1", "brazo2")}
        self._pub_estado = self.create_publisher(String, "/coordinador/estado", 10)
        self._pub_puentes = self.create_publisher(String, "/puentes/comando", 10)
        self.create_subscription(PoseStamped, "/caja/pose_camara", self._caja_cb, 10)
        self.create_subscription(PoseStamped, "/brazo1/pose_real", lambda m: self._real_cb("brazo1", m), 10)
        self.create_subscription(PoseStamped, "/brazo2/pose_real", lambda m: self._real_cb("brazo2", m), 10)
        self.create_subscription(String, "/coordinador/orden", self._orden_cb, 10)
        self.create_timer(self._periodo, self._ciclo)

    def _ahora(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _caja_cb(self, msg: PoseStamped) -> None:
        p, q = msg.pose.position, msg.pose.orientation
        self._caja = pose_desde_ros((p.x, p.y, p.z), (q.x, q.y, q.z, q.w))
        self._t_caja = self._ahora()

    def _real_cb(self, nombre: str, msg: PoseStamped) -> None:
        p, q = msg.pose.position, msg.pose.orientation
        self._real[nombre] = (pose_desde_ros((p.x, p.y, p.z), (q.x, q.y, q.z, q.w)), self._ahora())

    def _orden_cb(self, msg: String) -> None:
        evento = ORDENES.get(msg.data)
        if evento is None:
            self.get_logger().warning(f"orden desconocida: {msg.data!r}")
            return
        self._pendientes.append(evento)
        if evento is Evento.RESET:
            self._parada_avisada = False
            self._pub_puentes.publish(String(data="reset"))
        if evento is Evento.INICIAR:
            self._parada_avisada = False

    def _leer(self, nombre: str, ahora: float):
        dato = self._real[nombre]
        if dato is None or ahora - dato[1] > self._plazo:
            return None
        return dato[0]

    def _ciclo(self) -> None:
        ahora = self._ahora()
        real1 = self._leer("brazo1", ahora)
        real2 = self._leer("brazo2", ahora)
        edad = np.inf if self._t_caja is None else ahora - self._t_caja
        caja = self._caja if edad <= self._celda.coordinacion.caja_max_edad_s else None

        pendientes, self._pendientes = self._pendientes, []
        salida = self._co.paso(self._periodo, real1, real2, caja, edad, pendientes)

        for nombre, objetivo in (("brazo1", salida.objetivo1), ("brazo2", salida.objetivo2)):
            if objetivo is None:
                continue
            (x, y, z), (qx, qy, qz, qw) = pose_a_ros(objetivo)
            msg = PoseStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = f"base_{nombre}"
            msg.pose.position.x, msg.pose.position.y, msg.pose.position.z = x, y, z
            msg.pose.orientation.x, msg.pose.orientation.y = qx, qy
            msg.pose.orientation.z, msg.pose.orientation.w = qz, qw
            self._pub_obj[nombre].publish(msg)

        if salida.parar and not self._parada_avisada:
            self._pub_puentes.publish(String(data="parar"))
            self._parada_avisada = True
            self.get_logger().error(f"coordinador en {salida.estado.value}: se paran los puentes")

        self._pub_estado.publish(String(data=json.dumps({
            "estado": salida.estado.value,
            "parar": salida.parar,
            "eventos": [e.value for e in salida.eventos],
        })))


def main(args=None) -> None:
    rclpy.init(args=args)
    nodo = NodoCoordinador()
    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        nodo.destroy_node()
        rclpy.shutdown()
