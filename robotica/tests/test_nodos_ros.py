"""Prueba de humo de los nodos ROS 2: se crean, se destruyen y leen su configuración.

Solo corre si el entorno tiene ROS 2 (por ejemplo: source /opt/ros/humble/setup.bash antes de pytest).
Sin ROS se salta. La lógica de los nodos está en nucleo/ y vision/, que se prueban aparte.
"""
import sys
from pathlib import Path

import pytest

rclpy = pytest.importorskip("rclpy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2" / "robotica_bimanual"))


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


def test_los_tres_nodos_se_crean(ros):
    from robotica_bimanual.nodo_caja import NodoCaja
    from robotica_bimanual.nodo_coordinador import NodoCoordinador
    from robotica_bimanual.nodo_puente import NodoPuente

    nodos = [NodoPuente(), NodoCaja(), NodoCoordinador()]
    try:
        nombres = {n.get_name() for n in nodos}
        assert nombres == {"nodo_puente", "nodo_caja", "nodo_coordinador"}
    finally:
        for n in nodos:
            n.destroy_node()


def test_el_coordinador_publica_el_estado_inicial(ros):
    from std_msgs.msg import String

    from robotica_bimanual.nodo_coordinador import NodoCoordinador

    nodo = NodoCoordinador()
    recibidos = []
    nodo.create_subscription(String, "/coordinador/estado", lambda m: recibidos.append(m.data), 10)
    try:
        import time
        limite = time.time() + 3.0
        while not recibidos and time.time() < limite:
            rclpy.spin_once(nodo, timeout_sec=0.05)
        assert recibidos, "el coordinador no publica /coordinador/estado"
        assert '"estado": "reposo"' in recibidos[0]
    finally:
        nodo.destroy_node()


def test_el_nodo_de_seguimiento_se_crea_con_su_configuracion(ros):
    from robotica_bimanual.nodo_seguimiento import NodoSeguimiento

    nodo = NodoSeguimiento()
    try:
        assert nodo.get_name() == "nodo_seguimiento"
        assert nodo.get_parameter("sesion").value == "brazo1"
        assert nodo.get_parameter("puntos_maximos").value == 3000
    finally:
        nodo.destroy_node()


def test_el_puente_ros_solo_tiene_el_brazo1(ros):
    from robotica_bimanual.nodo_puente import NodoPuente

    nodo = NodoPuente()
    try:
        temas = {nombre for nombre, _ in nodo.get_topic_names_and_types()}
        assert "/brazo1/estado" in temas
        assert not any(t.startswith("/brazo2/") for t in temas), temas
    finally:
        nodo.destroy_node()
