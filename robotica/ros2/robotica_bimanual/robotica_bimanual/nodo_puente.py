"""Nodo puente: reenvía los objetivos de ROS 2 a los puentes EGM y publica el estado real de cada brazo.

Topics (metros, cuaterniones x-y-z-w), un único robot (brazo1):
  entrada:  /brazo1/objetivo  (geometry_msgs/PoseStamped, pose en la base del brazo)
            /puentes/comando                   (std_msgs/String: parar | arrancar | reset)
            /rapid/orden                       (String: texto para RAPID, solo con rapid:=true)
  salida:   /brazo1/pose_real (PoseStamped, TCP real en la base)
            /brazo1/estado       (String, JSON tal como lo devuelve el puente)
            /brazo1/rechazo      (String, JSON de la respuesta del puente cuando rechaza un objetivo)
            /rapid/respuesta     (String: lo que contesta RAPID)
            /rapid/estado        (String, JSON: {"conectado": bool, "origen": ...} o {"error": ...})

Con el parametro `rapid` (true por defecto en el launch de la celda) el nodo tambien lleva el socket de RAPID del puente a ROS: manda
/rapid/orden a RAPID y publica lo que RAPID contesta. Usa dos conexiones de control propias (una para enviar y mirar el estado, otra
que espera las respuestas), porque esperar bloquea la conexion y el movimiento no puede parar.

Un objetivo que no se renueva en `plazo_objetivo_s` no se reenvía: el puente lo trata como
vencido y retiene el brazo. Así, si el coordinador deja de mandar objetivos, el brazo se para.
"""
from __future__ import annotations

import json
import threading
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
                "pub_rechazo": self.create_publisher(String, f"/{nombre}/rechazo", 10),
            }
            self.create_subscription(PoseStamped, f"/{nombre}/objetivo",
                                     lambda m, n=nombre: self._recibir_objetivo(n, m), 10)
        self.create_subscription(String, "/puentes/comando", self._comando, 10)
        self.create_timer(1.0 / float(self.get_parameter("frecuencia_hz").value), self._ciclo)
        self.declare_parameter("rapid", False)
        self._parar_rapid = threading.Event()
        if bool(self.get_parameter("rapid").value):
            self._iniciar_rapid()

    # ---- socket de RAPID del puente <-> /rapid/*
    def _iniciar_rapid(self) -> None:
        host = str(self.get_parameter("brazo1.host").value)
        puerto = int(self.get_parameter("brazo1.puerto").value)
        self._rapid_tx = ClientePuente(host, puerto, timeout_s=2.0)    # enviar y estado: respuestas inmediatas
        self._rapid_rx = ClientePuente(host, puerto, timeout_s=2.0)    # esperar a RAPID: bloquea hasta que contesta
        self._pub_rapid_estado = self.create_publisher(String, "/rapid/estado", 10)
        self._pub_rapid_respuesta = self.create_publisher(String, "/rapid/respuesta", 50)
        self.create_subscription(String, "/rapid/orden", self._rapid_orden, 50)
        self.create_timer(0.5, self._rapid_estado)
        self._hilo_rapid = threading.Thread(target=self._rapid_escuchar, name="rapid-rx", daemon=True)
        self._hilo_rapid.start()

    def _rapid_orden(self, msg: String) -> None:
        try:
            r = self._rapid_tx.rapid_enviar(msg.data)
        except OSError as e:
            self.get_logger().error(f"RAPID: orden {msg.data!r} no enviada: {e}")
            return
        if not r.get("ok", False):
            self.get_logger().error(f"RAPID: el puente no ha podido mandar {msg.data!r}: {r.get('error', r)}")

    def _rapid_estado(self) -> None:
        try:
            r = self._rapid_tx.rapid_estado()
        except OSError as e:
            self.get_logger().warning(f"RAPID: sin estado del puente: {e}", throttle_duration_sec=2.0)
            return
        if r.get("ok", False):
            dato = {"conectado": bool(r.get("conectado")), "origen": r.get("origen", "")}
        else:
            dato = {"conectado": False, "error": str(r.get("error", r))}
        self._pub_rapid_estado.publish(String(data=json.dumps(dato)))

    def _rapid_escuchar(self) -> None:
        """Hilo: pide al puente, una y otra vez, lo que RAPID haya contestado, y lo publica."""
        while not self._parar_rapid.is_set():
            try:
                r = self._rapid_rx.rapid_recibir(1.0)
            except OSError:
                self._parar_rapid.wait(0.5)
                continue
            if r.get("ok", False):
                self._pub_rapid_respuesta.publish(String(data=str(r["msg"])))
            elif r.get("codigo") != "timeout":
                self._parar_rapid.wait(0.2)   # desconectado o cerrado, o el puente sin socket de RAPID: se vuelve a preguntar enseguida

    def destroy_node(self):
        self._parar_rapid.set()
        return super().destroy_node()

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
                    respuesta = b["cliente"].objetivo(b["objetivo"])
                    if not respuesta.get("ok", False):   # el puente rechaza el objetivo (fuera de su espacio, giro...): se avisa a ROS
                        b["pub_rechazo"].publish(String(data=json.dumps(respuesta)))
                        self.get_logger().warning(f"{nombre}: el puente rechaza el objetivo: {respuesta}", throttle_duration_sec=2.0)
                except OSError as e:
                    self.get_logger().warning(f"{nombre}: objetivo no enviado: {e}", throttle_duration_sec=2.0)
            try:
                estado = b["cliente"].estado()
            except OSError as e:
                self.get_logger().warning(f"{nombre}: sin estado del puente: {e}", throttle_duration_sec=2.0)
                continue
            b["pub_estado"].publish(String(data=json.dumps(estado)))
            if estado.get("ok") and "real" in estado:
                try:
                    real = pose_desde_estado_puente(estado["real"])
                except ValueError:   # el puente aun no ha recibido datos del robot (cuaternion de ceros): no hay pose real que publicar
                    continue
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
        try:
            nodo.destroy_node()
        except KeyboardInterrupt:   # el launch manda otro Ctrl+C a cada nodo mientras se cierra
            pass
        if rclpy.ok():   # con Ctrl+C el launch ya lo ha cerrado
            rclpy.shutdown()