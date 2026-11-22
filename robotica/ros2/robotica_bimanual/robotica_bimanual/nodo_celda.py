"""Nodo de la celda: el ciclo de cajas (`celda.ciclo.Celda`) como nodo de ROS 2.

Es el mismo cerebro que `python -m celda.ciclo`, pero habla con el robot y con la cámara por ROS 2 en vez de por TCP y USB directos:

  movimiento:  Celda -> /brazo1/objetivo -> nodo_puente -> (TCP 7001) -> PuenteEgm.exe -> EGM -> robot    (PuenteRos)
  estado:      robot -> PuenteEgm.exe -> nodo_puente -> /brazo1/estado -> Celda                           (PuenteRos)
  cámara:      driver de la cámara -> /camera/color/image_raw (+ profundidad) -> Celda                    (ProveedorRos, si origen.tipo = "ros")
  RAPID:       T_COM <-(TCP 5010)-> PuenteEgm.exe <-(TCP 7001)-> nodo_puente <-> /rapid/orden y /rapid/respuesta <-> Celda   (RapidRos)
               (con socket_rapid.via = "pc", T_COM habla directamente con este nodo por el socket 5010, como antes)

Salidas:  /celda/estado (std_msgs/String, JSON con los hechos del ciclo: inicio, caja, pinza, fin o error)
          /celda/caja   (geometry_msgs/PoseStamped: centro de la caja que ve la cámara, en la base del robot, con su giro; en metros)

Parámetros: config (ruta de celda/config_celda.json, obligatoria), sesion (brazo1), topic_color y topic_profundidad (si la configuración no los da).
El ciclo corre en un hilo; este nodo gira (spin) en el principal para recibir el estado y las imágenes.
"""
from __future__ import annotations

import json
import math
import threading
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from std_msgs.msg import String

from celda.ciclo import Celda, donde_espera_rapid
from celda.config import cargar
from celda.percepcion import FuenteCamara, crear_fuente
from celda.socket_rapid import ServidorRapid
from vision.visor import crear_visor

from .proveedor_ros import ProveedorRos
from .puente_ros import PuenteRos
from .rapid_ros import RapidRos


class NodoCelda(Node):
    def __init__(self):
        super().__init__("nodo_celda")
        self.declare_parameter("config", "")
        self.declare_parameter("sesion", "brazo1")
        self.declare_parameter("topic_color", "/camera/color/image_raw")
        self.declare_parameter("topic_profundidad", "/camera/aligned_depth_to_color/image_raw")
        ruta = str(self.get_parameter("config").value)
        if not ruta:
            raise ValueError("falta el parametro 'config': la ruta de celda/config_celda.json "
                             "(ros2 launch robotica_bimanual celda_real.launch.py config:=/ruta/config_celda.json)")
        self.cfg = cargar(ruta)
        self._pub_estado = self.create_publisher(String, "/celda/estado", 10)
        self._pub_caja = self.create_publisher(PoseStamped, "/celda/caja", 10)
        self.puente = PuenteRos(self, str(self.get_parameter("sesion").value))
        self.fuente = self._crear_fuente()
        self.visor = crear_visor(self.fuente, self.cfg)   # ventana en tiempo real (camara.visor): se bombea en el bucle principal
        # Con socket_rapid.via = "puente", RAPID habla con el puente EGM y este nodo por /rapid/* (nodo_puente con rapid:=true);
        # con "pc", este nodo abre el socket (el servidor en el PC, como antes).
        self.rapid = (RapidRos(self, self.cfg.rapid_espera_s) if self.cfg.rapid_via == "puente"
                      else ServidorRapid(self.cfg.rapid_ip, self.cfg.rapid_puerto, self.cfg.rapid_espera_s))
        self.celda = Celda(self.cfg, self.fuente, self.puente, self.rapid)
        self.celda.informar = self._informar
        self.terminado = threading.Event()
        self.error: Exception | None = None
        self._hilo = threading.Thread(target=self._trabajo, name="ciclo-celda", daemon=True)

    def _crear_fuente(self):
        """caja.csv en simulacion; en real, la camara: la de ROS (origen.tipo = ros) o la de la configuracion (carpeta, opencv, realsense)."""
        cfg = self.cfg
        origen = ((cfg.camara or {}).get("origen") or {}) if not cfg.modo_simulacion else {}
        if origen.get("tipo") != "ros":
            return crear_fuente(cfg)
        c = cfg.camara
        con_profundidad = c.get("modo") == "profundidad" or c.get("alto_mm") is None
        color = origen.get("color") or str(self.get_parameter("topic_color").value)
        prof = (origen.get("profundidad") or str(self.get_parameter("topic_profundidad").value)) if con_profundidad else None
        self.get_logger().info(f"camara por ROS 2: color {color}" + (f", profundidad {prof}" if prof else ", sin profundidad"))
        return FuenteCamara.desde_config(cfg, ProveedorRos(self, color, prof))

    def iniciar(self) -> None:
        if self.visor is not None:
            self.visor.iniciar()
        self._hilo.start()

    def _informar(self, datos: dict) -> None:
        """Publica un hecho del ciclo en /celda/estado y, si es una caja, su pose en /celda/caja."""
        self._pub_estado.publish(String(data=json.dumps(datos)))
        if datos.get("evento") == "caja" and datos.get("x") is not None:
            msg = PoseStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = f"base_{self.get_parameter('sesion').value}"
            msg.pose.position.x, msg.pose.position.y = datos["x"] / 1000.0, datos["y"] / 1000.0
            msg.pose.position.z = self.celda.cfg.z_cinta / 1000.0   # la de la celda: en real la manda RAPID, no el fichero
            a = math.radians(datos["giro"]) / 2.0
            msg.pose.orientation.z, msg.pose.orientation.w = math.sin(a), math.cos(a)
            self._pub_caja.publish(msg)

    def _trabajo(self) -> None:
        try:
            self.get_logger().info(f"Esperando {donde_espera_rapid(self.cfg) if self.cfg.rapid_via == 'pc' else 'a RAPID por /rapid/estado (socket del puente)'}...")
            self.rapid.esperar_cliente()
            self.celda.ejecutar()
            self.get_logger().info("Celda: todas las cajas recogidas.")
        except Exception as e:   # noqa: BLE001 - se cuenta por ROS y se sale con codigo de error
            self.error = e
            self.get_logger().error(f"el ciclo de la celda se ha parado: {e}")
            self._informar({"evento": "error", "mensaje": str(e)})
        finally:
            time.sleep(0.5)   # el ultimo mensaje (fin_programa) sale por un topic: hay que dejarlo llegar antes de cerrar el nodo
            self.rapid.cerrar()
            self.terminado.set()

    def cerrar(self) -> None:
        if self.visor is not None:
            self.visor.parar()
        self.rapid.cerrar()


def main(args=None) -> int:
    rclpy.init(args=args)
    nodo = NodoCelda()
    nodo.iniciar()
    try:
        while rclpy.ok() and not nodo.terminado.is_set():
            rclpy.spin_once(nodo, timeout_sec=0.05 if nodo.visor is not None else 0.1)
            if nodo.visor is not None:
                nodo.visor.bombear()
        if nodo.visor is not None:   # la ultima imagen se queda unos segundos
            fin = time.monotonic() + 3.0
            while time.monotonic() < fin and rclpy.ok() and nodo.visor.bombear():
                rclpy.spin_once(nodo, timeout_sec=0.03)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            nodo.cerrar()
            nodo.destroy_node()
        except KeyboardInterrupt:   # el launch manda otro Ctrl+C a cada nodo mientras se cierra
            pass
        if rclpy.ok():   # con Ctrl+C el launch ya lo ha cerrado
            rclpy.shutdown()
    return 1 if nodo.error else 0


if __name__ == "__main__":
    raise SystemExit(main())
