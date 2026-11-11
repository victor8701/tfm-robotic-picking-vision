"""Lanza la celda con un único robot: puente EGM y detección de la caja.

El coordinador bimanual (nodo_coordinador) no se lanza: necesita los dos brazos y queda pendiente
con la tarea de un robot.

Antes de lanzar, en la misma terminal:
    source /opt/ros/humble/setup.bash
    export PYTHONPATH=/ruta/al/repositorio/robotica:$PYTHONPATH
Los puentes EGM (puente_egm) deben estar en marcha en Windows o en la máquina que corresponda.

Valores que hay que poner aquí (detalle en docs/configuracion.md):
- brazo1.host: IP del PC con el puente vista desde WSL2
  (dentro de WSL2: ip route show default | awk '{print $3}'). Si ROS corre en Windows: 127.0.0.1.
- brazo1.puerto: debe coincidir con puerto_control de brazo1 en config.json (7001).
- topic_imagen y topic_info: tópicos reales del driver de la cámara (ros2 topic list). Los valores de abajo son de partida.
- ancho_mm y largo_mm: caja interior medida.
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
    ])
