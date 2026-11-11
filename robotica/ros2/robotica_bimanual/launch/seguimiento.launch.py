"""Lanza el nodo de seguimiento de la prueba y RViz con la vista preparada.

Antes de lanzar, en la misma terminal:
    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash
    ros2 launch robotica_bimanual seguimiento.launch.py
Si el registro del puente esta en otra carpeta: csv:=/ruta/a/puente.csv
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from robotica_bimanual.nodo_seguimiento import RUTA_CSV_POR_DEFECTO


def generate_launch_description():
    rviz = os.path.join(get_package_share_directory("robotica_bimanual"), "rviz", "seguimiento.rviz")
    return LaunchDescription([
        DeclareLaunchArgument("csv", default_value=RUTA_CSV_POR_DEFECTO),
        Node(
            package="robotica_bimanual",
            executable="nodo_seguimiento",
            name="nodo_seguimiento",
            output="screen",
            parameters=[{
                "csv": LaunchConfiguration("csv"),
                "sesion": "brazo1",
                "frecuencia_hz": 10.0,
                "marco": "base",
            }],
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            arguments=["-d", rviz],
            output="screen",
        ),
    ])
