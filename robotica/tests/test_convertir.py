import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2" / "robotica_bimanual"))

from robotica_bimanual.convertir import (camara_desde_ros, comando_objetivo, imagen_desde_ros,  # noqa: E402
                                         pose_a_ros, pose_desde_ros)
from nucleo.geometria import Pose, quat_desde_rotvec, angulo  # noqa: E402


def test_pose_ida_y_vuelta_entre_ros_y_el_nucleo():
    T = Pose.crear(t=[600.0, -150.0, 450.0], q=quat_desde_rotvec([0.2, -0.4, 0.9]))
    posicion, (x, y, z, w) = pose_a_ros(T)
    back = pose_desde_ros(posicion, (x, y, z, w))
    assert np.allclose(back.t, T.t, atol=1e-9)
    assert angulo(back.q, T.q) < 1e-9


def test_metros_a_milimetros_y_orden_del_cuaternion():
    p = pose_desde_ros((0.6, -0.15, 0.45), (0.0, 1.0, 0.0, 0.0))   # x-y-z-w de ROS
    assert np.allclose(p.t, [600.0, -150.0, 450.0])
    assert np.allclose(p.q, [0.0, 0.0, 1.0, 0.0])                  # w-x-y-z del núcleo


def test_comando_del_puente_va_en_milimetros():
    cmd = comando_objetivo(Pose.crear(t=[1.0, 2.0, 3.0]))
    assert cmd == {"cmd": "objetivo", "t": [1.0, 2.0, 3.0], "q": [1.0, 0.0, 0.0, 0.0]}


def test_imagen_bgr_y_rgb_se_leen_igual():
    bgr = np.zeros((4, 6, 3), np.uint8)
    bgr[..., 0] = 10   # canal azul
    bgr[..., 2] = 200  # canal rojo
    msg_bgr = SimpleNamespace(height=4, width=6, encoding="bgr8", data=bgr.tobytes())
    msg_rgb = SimpleNamespace(height=4, width=6, encoding="rgb8", data=bgr[:, :, ::-1].tobytes())
    assert np.array_equal(imagen_desde_ros(msg_bgr), bgr)
    assert np.array_equal(imagen_desde_ros(msg_rgb), bgr)


def test_encoding_no_soportado_falla():
    msg = SimpleNamespace(height=1, width=1, encoding="mono16", data=b"\x00\x00")
    with pytest.raises(ValueError):
        imagen_desde_ros(msg)


def test_intrinsecos_y_distorsion_desde_camera_info():
    K, D = camara_desde_ros([800.0, 0.0, 320.0, 0.0, 800.0, 240.0, 0.0, 0.0, 1.0], [])
    assert K.shape == (3, 3) and K[0, 2] == 320.0
    assert np.allclose(D, np.zeros(5))
