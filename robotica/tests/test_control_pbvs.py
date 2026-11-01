import numpy as np

from nucleo.control_pbvs import error_pbvs, integrar_camara, ley_pbvs, simular_pbvs
from nucleo.geometria import Pose, quat_desde_rotvec

DESEADA = Pose.crear(t=[0.0, 0.0, 400.0])


def test_comando_nulo_en_la_pose_deseada():
    v, w = ley_pbvs(DESEADA, DESEADA)
    assert np.allclose(v, 0) and np.allclose(w, 0)


def test_el_signo_de_la_rotacion_reduce_el_error():
    T = Pose.crear(t=[0.0, 0.0, 400.0], q=quat_desde_rotvec([0.0, 0.0, 0.2]))
    v, w = ley_pbvs(T, DESEADA)
    T2 = integrar_camara(T, v, w, 0.01)
    assert error_pbvs(T2, DESEADA)[1] < error_pbvs(T, DESEADA)[1]


def test_el_signo_de_la_traslacion_reduce_el_error():
    T = Pose.crear(t=[20.0, -10.0, 400.0])
    v, w = ley_pbvs(T, DESEADA)
    T2 = integrar_camara(T, v, w, 0.01)
    assert error_pbvs(T2, DESEADA)[0] < error_pbvs(T, DESEADA)[0]


def test_la_integracion_conserva_una_rotacion_valida():
    T = Pose.crear(t=[10.0, 0.0, 300.0], q=quat_desde_rotvec([0.3, -0.2, 0.1]))
    for _ in range(100):
        T = integrar_camara(T, np.array([5.0, -3.0, 2.0]), np.array([0.1, 0.2, -0.05]), 0.02)
    R = T.matriz()[:3, :3]
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-10)


def test_convergencia_desde_la_zona_de_captura():
    rng = np.random.default_rng(1)
    casos = 40
    ok = 0
    for _ in range(casos):
        t0 = [rng.uniform(-150, 150), rng.uniform(-150, 150), rng.uniform(300, 600)]
        eje = rng.normal(size=3)
        eje /= np.linalg.norm(eje)
        T0 = Pose.crear(t=t0, q=quat_desde_rotvec(eje * rng.uniform(0.0, np.deg2rad(40))))
        T, _ = simular_pbvs(T0, DESEADA, pasos=2000, dt=0.02)
        et, er = error_pbvs(T, DESEADA)
        ok += et < 0.5 and er < 0.002
    assert ok == casos


def test_converge_con_retardo_de_tres_fotogramas():
    T0 = Pose.crear(t=[60.0, -40.0, 500.0], q=quat_desde_rotvec([0.0, 0.1, 0.2]))
    T, historia = simular_pbvs(T0, DESEADA, pasos=1500, dt=0.033, delay_pasos=3)
    et, er = error_pbvs(T, DESEADA)
    assert et < 1.0 and er < 0.01
    assert max(e for e, _ in historia[-100:]) < 1.0
