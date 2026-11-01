import numpy as np
import pytest

from nucleo import geometria as g
from nucleo.geometria import Pose

rng = np.random.default_rng(0)


def _q_aleatorio():
    return g.normalizar(rng.normal(size=4))


def test_matriz_y_cuaternion_ida_y_vuelta():
    for _ in range(200):
        q = _q_aleatorio()
        R = g.a_matriz(q)
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-12)
        assert np.isclose(np.linalg.det(R), 1.0)
        assert np.allclose(g.a_matriz(g.desde_matriz(R)), R, atol=1e-12)


def test_rotvec_exp_y_log_ida_y_vuelta():
    for _ in range(200):
        eje = rng.normal(size=3)
        eje /= np.linalg.norm(eje)
        r = eje * rng.uniform(0.0, 3.0)  # ángulo menor que pi
        assert np.allclose(g.rotvec_desde_quat(g.quat_desde_rotvec(r)), r, atol=1e-10)


def test_error_de_orientacion_lleva_actual_a_objetivo():
    for _ in range(200):
        qa, qo = _q_aleatorio(), _q_aleatorio()
        _, dr = g.error_pose(Pose.crear(q=qa), Pose.crear(q=qo))
        assert np.allclose(g.a_matriz(g.quat_desde_rotvec(dr)) @ g.a_matriz(qa), g.a_matriz(qo), atol=1e-9)


def test_error_de_posicion_es_la_diferencia():
    dt, _ = g.error_pose(Pose.crear(t=[1, 2, 3]), Pose.crear(t=[4, 6, 3]))
    assert np.allclose(dt, [3, 4, 0])


def test_inversa_da_identidad():
    p = Pose.crear(t=rng.normal(size=3) * 100, q=_q_aleatorio())
    assert np.allclose(p.matriz() @ p.inversa().matriz(), np.eye(4), atol=1e-9)
    I = p.componer(p.inversa())
    assert np.allclose(I.t, 0, atol=1e-9)
    assert g.angulo(I.q, [1, 0, 0, 0]) < 1e-9


def test_composicion_coincide_con_matrices():
    a = Pose.crear(t=rng.normal(size=3) * 100, q=_q_aleatorio())
    b = Pose.crear(t=rng.normal(size=3) * 100, q=_q_aleatorio())
    assert np.allclose(a.componer(b).matriz(), a.matriz() @ b.matriz(), atol=1e-9)


def test_aplicar_puntos_coincide_con_la_matriz():
    p = Pose.crear(t=[10, -5, 3], q=_q_aleatorio())
    puntos = rng.normal(size=(5, 3))
    homogeneos = np.hstack([puntos, np.ones((5, 1))])
    esperados = (p.matriz() @ homogeneos.T).T[:, :3]
    assert np.allclose(p.aplicar(puntos), esperados)


def test_slerp_extremos_y_velocidad_angular_constante():
    q0, q1 = _q_aleatorio(), _q_aleatorio()
    assert g.angulo(g.slerp(q0, q1, 0.0), q0) < 1e-9
    assert g.angulo(g.slerp(q0, q1, 1.0), q1) < 1e-9
    theta = g.angulo(q0, q1)
    for f in (0.25, 0.5, 0.75):
        assert np.isclose(g.angulo(q0, g.slerp(q0, q1, f)), f * theta, atol=1e-9)


def test_interpolar_posicion_lineal():
    a = Pose.crear(t=[0, 0, 0])
    b = Pose.crear(t=[10, 0, 0])
    assert np.allclose(g.interpolar(a, b, 0.3).t, [3, 0, 0])


def test_cuaternion_nulo_falla():
    with pytest.raises(ValueError):
        g.normalizar([0, 0, 0, 0])
