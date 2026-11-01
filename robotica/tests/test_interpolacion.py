import numpy as np
import pytest

from nucleo.geometria import Pose, angulo, quat_desde_rotvec
from nucleo.interpolacion import SeguidorConsigna

DT = 0.004


def _simular(seg, objetivo, pasos):
    return np.array([seg.paso(objetivo, DT).t.copy() for _ in range(pasos)])


def test_converge_respetando_velocidad_y_aceleracion():
    seg = SeguidorConsigna(v_max=125.0, a_max=400.0, w_max=0.6, kp=5.0)
    seg.reset(Pose.crear(t=[0, 0, 0]))
    objetivo = Pose.crear(t=[200.0, -100.0, 50.0])
    tr = _simular(seg, objetivo, 3000)  # 12 s

    assert np.linalg.norm(tr[-1] - objetivo.t) < 0.2
    v = np.diff(tr, axis=0) / DT
    assert np.linalg.norm(v, axis=1).max() <= 125.0 + 1e-6
    a = np.diff(v, axis=0) / DT
    assert np.linalg.norm(a, axis=1).max() <= 400.0 + 1e-3


def test_no_se_pasa_del_objetivo_mas_de_2_mm():
    seg = SeguidorConsigna(v_max=125.0, a_max=400.0, kp=5.0)
    seg.reset(Pose.crear(t=[0, 0, 0]))
    objetivo = Pose.crear(t=[300.0, 0.0, 0.0])
    tr = _simular(seg, objetivo, 4000)
    sobrepaso = max(0.0, tr[:, 0].max() - 300.0)
    assert sobrepaso < 2.0


def test_orientacion_respeta_el_giro_maximo_por_ciclo():
    seg = SeguidorConsigna(w_max=0.6)
    seg.reset(Pose.crear())
    objetivo = Pose.crear(q=quat_desde_rotvec([0, 0, np.pi / 2]))
    anterior = seg.pose.q
    paso_max = 0.0
    for _ in range(2000):
        nuevo = seg.paso(objetivo, DT).q
        paso_max = max(paso_max, angulo(anterior, nuevo))
        anterior = nuevo
    assert paso_max <= 0.6 * DT + 1e-9
    assert angulo(seg.pose.q, objetivo.q) < 1e-6


def test_reset_borra_la_velocidad():
    seg = SeguidorConsigna()
    seg.reset(Pose.crear(t=[0, 0, 0]))
    seg.paso(Pose.crear(t=[100, 0, 0]), DT)
    assert np.linalg.norm(seg.velocidad) > 0
    seg.reset(Pose.crear(t=[5, 5, 5]))
    assert np.allclose(seg.velocidad, 0)


def test_parametros_invalidos_fallan():
    with pytest.raises(ValueError):
        SeguidorConsigna(v_max=0.0)
    seg = SeguidorConsigna()
    with pytest.raises(ValueError):
        seg.paso(Pose.crear(), 0.0)
