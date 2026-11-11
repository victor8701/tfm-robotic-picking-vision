"""Nodo de seguimiento de la prueba: lee el registro del puente y publica lo que hace el robot.

Solo LEE el CSV que escribe el puente. No manda comandos ni al puente ni al robot.

Topics (posiciones en metros, marco "base"):
  salida:  /prueba/marcadores  (visualization_msgs/MarkerArray)
           linea del recorrido real, esfera en la posicion actual y texto con la fase
           /prueba/fase        (std_msgs/String): fase, estado y desviacion
           /prueba/pose        (geometry_msgs/PoseStamped): posicion real del TCP

Parametros:
  csv            ruta de registros/puente.csv (en WSL: /mnt/c/...)
  sesion         "brazo1" por defecto
  frecuencia_hz  cada cuanto se lee el fichero
  marco          marco de referencia de los marcadores ("base")
  puntos_maximos cuantos puntos de recorrido se dibujan (ventana deslizante)
"""
from __future__ import annotations

import rclpy
from geometry_msgs.msg import Point, PoseStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String
from visualization_msgs.msg import Marker, MarkerArray

from .seguimiento_csv import Muestra, Trayectoria, ultima_muestra

RUTA_CSV_POR_DEFECTO = (
    "/mnt/c/Users/Viktor/source/repos/TFM_Windows/robotica/puente_egm/PuenteEgm/"
    "bin/Release/net8.0/registros/puente.csv"
)


def _metros(mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return (mm[0] / 1000.0, mm[1] / 1000.0, mm[2] / 1000.0)


class NodoSeguimiento(Node):
    def __init__(self):
        super().__init__("nodo_seguimiento")
        self.declare_parameter("csv", RUTA_CSV_POR_DEFECTO)
        self.declare_parameter("sesion", "brazo1")
        self.declare_parameter("frecuencia_hz", 10.0)
        self.declare_parameter("marco", "base")
        self.declare_parameter("puntos_maximos", 3000)
        self._csv = str(self.get_parameter("csv").value)
        self._sesion = str(self.get_parameter("sesion").value)
        self._marco = str(self.get_parameter("marco").value)
        self._trayectoria = Trayectoria(maximo=int(self.get_parameter("puntos_maximos").value))
        self._aviso_error = ""
        self._pub_marcadores = self.create_publisher(MarkerArray, "/prueba/marcadores", 10)
        self._pub_fase = self.create_publisher(String, "/prueba/fase", 10)
        self._pub_pose = self.create_publisher(PoseStamped, "/prueba/pose", 10)
        self.create_timer(1.0 / float(self.get_parameter("frecuencia_hz").value), self._ciclo)
        self.get_logger().info(f"Siguiendo {self._csv} (sesion {self._sesion})")

    def _ciclo(self) -> None:
        try:
            muestra = ultima_muestra(self._csv, self._sesion)
        except (OSError, ValueError, KeyError) as error:
            # Se avisa una sola vez por error distinto; el fichero puede estar a medio escribir.
            if str(error) != self._aviso_error:
                self._aviso_error = str(error)
                self.get_logger().warning(f"No puedo leer el registro: {error}")
            return
        if muestra is None:
            return
        if self._trayectoria.añadir(muestra):
            self.get_logger().info("Nueva ejecucion: la linea del recorrido empieza de nuevo")
        self._publicar(muestra)

    def _publicar(self, m: Muestra) -> None:
        ahora = self.get_clock().now().to_msg()
        x, y, z = _metros(m.real)
        fase = m.fase or "sin prueba"

        marcadores = MarkerArray()
        marcadores.markers = [
            self._linea(ahora),
            self._esfera(ahora, x, y, z),
            self._texto(ahora, x, y, z, f"{fase} | {m.estado} | desv {m.desviacion_mm:.1f} mm"),
        ]
        self._pub_marcadores.publish(marcadores)

        pose = PoseStamped()
        pose.header.stamp = ahora
        pose.header.frame_id = self._marco
        pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = x, y, z
        pose.pose.orientation.w = 1.0
        self._pub_pose.publish(pose)

        self._pub_fase.publish(String(data=f"{fase} | {m.estado} | desv {m.desviacion_mm:.1f} mm"))

    def _marcador(self, ahora, tipo: int, identificador: int) -> Marker:
        marcador = Marker()
        marcador.header.stamp = ahora
        marcador.header.frame_id = self._marco
        marcador.ns = "prueba"
        marcador.id = identificador
        marcador.type = tipo
        marcador.action = Marker.ADD
        marcador.pose.orientation.w = 1.0
        return marcador

    def _linea(self, ahora) -> Marker:
        marcador = self._marcador(ahora, Marker.LINE_STRIP, 0)
        marcador.scale.x = 0.004  # 4 mm de grosor
        marcador.color.r, marcador.color.g, marcador.color.b, marcador.color.a = 0.1, 0.6, 1.0, 1.0
        marcador.points = [Point(x=x / 1000.0, y=y / 1000.0, z=z / 1000.0)
                           for x, y, z in self._trayectoria.puntos]
        return marcador

    def _esfera(self, ahora, x: float, y: float, z: float) -> Marker:
        marcador = self._marcador(ahora, Marker.SPHERE, 1)
        marcador.pose.position.x, marcador.pose.position.y, marcador.pose.position.z = x, y, z
        marcador.scale.x = marcador.scale.y = marcador.scale.z = 0.02
        marcador.color.r, marcador.color.g, marcador.color.b, marcador.color.a = 1.0, 0.2, 0.2, 1.0
        return marcador

    def _texto(self, ahora, x: float, y: float, z: float, texto: str) -> Marker:
        marcador = self._marcador(ahora, Marker.TEXT_VIEW_FACING, 2)
        marcador.pose.position.x, marcador.pose.position.y, marcador.pose.position.z = x, y, z + 0.05
        marcador.scale.z = 0.03
        marcador.color.r, marcador.color.g, marcador.color.b, marcador.color.a = 1.0, 1.0, 1.0, 1.0
        marcador.text = texto
        return marcador


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoSeguimiento()
    try:
        rclpy.spin(nodo)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        nodo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
