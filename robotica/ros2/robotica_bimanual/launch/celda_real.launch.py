"""Lanza la celda por ROS 2: el puente (nodo_puente) y el ciclo de cajas (nodo_celda).

    source /opt/ros/humble/setup.bash
    source ~/ros2_ws/install/setup.bash
    export PYTHONPATH=/home/ubuntu22/repos/tfm-robotica-bimanual/robotica:$PYTHONPATH
    ros2 launch robotica_bimanual celda_real.launch.py config:=/home/ubuntu22/repos/tfm-robotica-bimanual/robotica/celda/config_celda.json host:=<IP de Windows>

Antes, en Windows, el puente EGM (PuenteEgm.exe con config.celda.json). La cámara por ROS (origen.tipo = "ros" en la sección camara de la
configuración) se lanza aparte, por ejemplo la RealSense:
    ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true
Argumentos: config (obligatorio), host (IP del PC con el puente, vista desde aquí; 127.0.0.1 si ROS corre en Windows), puerto (7001).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("config", description="ruta de celda/config_celda.json"),
        DeclareLaunchArgument("host", default_value="127.0.0.1", description="IP del PC con PuenteEgm.exe, vista desde ROS"),
        DeclareLaunchArgument("puerto", default_value="7001", description="puerto de control del puente"),
        DeclareLaunchArgument("rapid", default_value="true", description="llevar el socket de RAPID del puente a /rapid/* (socket_rapid.via = puente)"),
        Node(
            package="robotica_bimanual",
            executable="nodo_puente",
            name="nodo_puente",
            output="screen",
            parameters=[{
                "brazo1.host": LaunchConfiguration("host"),
                "brazo1.puerto": LaunchConfiguration("puerto"),
                "frecuencia_hz": 25.0,
                "plazo_objetivo_s": 0.2,
                "rapid": ParameterValue(LaunchConfiguration("rapid"), value_type=bool),
            }],
        ),
        Node(
            package="robotica_bimanual",
            executable="nodo_celda",
            name="nodo_celda",
            output="screen",
            parameters=[{"config": LaunchConfiguration("config")}],
        ),
    ])
