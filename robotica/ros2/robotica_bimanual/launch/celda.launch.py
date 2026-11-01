"""Lanza los tres nodos de la celda: puente EGM, detección de la caja y coordinador.

Antes de lanzar, en la misma terminal:
    source /opt/ros/humble/setup.bash
    export PYTHONPATH=/ruta/al/repositorio/robotica:$PYTHONPATH
Los puentes EGM (puente_egm) deben estar en marcha en Windows o en la máquina que corresponda.
"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="robotica_bimanual",
            executable="nodo_puente",
            name="nodo_puente",
            output="screen",
            parameters=[{
                "brazo1.host": "127.0.0.1",
                "brazo1.puerto": 7001,
                "brazo2.host": "127.0.0.1",
                "brazo2.puerto": 7002,
                "frecuencia_hz": 25.0,
                "plazo_objetivo_s": 0.2,
            }],
        ),
        Node(
            package="robotica_bimanual",
            executable="nodo_caja",
            name="nodo_caja",
            output="screen",
            parameters=[{
                "topic_imagen": "/camara/color/image_raw",
                "topic_info": "/camara/color/camera_info",
                "metodo": "contorno",
                "ancho_mm": 700.0,
                "largo_mm": 650.0,
            }],
        ),
        Node(
            package="robotica_bimanual",
            executable="nodo_coordinador",
            name="nodo_coordinador",
            output="screen",
            parameters=[{
                "periodo_s": 0.04,
                "plazo_lectura_s": 0.3,
            }],
        ),
    ])
