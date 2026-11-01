import numpy as np

from nucleo.bimanual import Configuracion, desviacion_interna, objetivos_manos, pose_caja_en_mundo
from nucleo.geometria import Pose, quat_desde_rotvec


def _cfg():
    return Configuracion(
        T_w_b1=Pose.crear(t=[0, 0, 0]),
        T_w_b2=Pose.crear(t=[1200, 0, 0], q=quat_desde_rotvec([0, 0, np.pi])),  # base 2 girada 180°
        T_caja_tcp1=Pose.crear(t=[-400, 0, 100], q=[0, 1, 0, 0]),
        T_caja_tcp2=Pose.crear(t=[400, 0, 100], q=[0, 1, 0, 0]),
    )


def test_objetivos_reproducen_los_tcp_sobre_la_caja():
    cfg = _cfg()
    T_caja = Pose.crear(t=[600, 0, 0], q=quat_desde_rotvec([0, 0, 0.3]))
    o1, o2 = objetivos_manos(T_caja, cfg)
    w1 = cfg.T_w_b1.componer(o1)
    w2 = cfg.T_w_b2.componer(o2)
    assert np.allclose(w1.matriz(), T_caja.componer(cfg.T_caja_tcp1).matriz(), atol=1e-9)
    assert np.allclose(w2.matriz(), T_caja.componer(cfg.T_caja_tcp2).matriz(), atol=1e-9)


def test_sin_desviacion_con_la_relacion_nominal():
    cfg = _cfg()
    T_caja = Pose.crear(t=[600, 0, 0], q=quat_desde_rotvec([0.1, 0.2, 0.3]))
    w1 = T_caja.componer(cfg.T_caja_tcp1)
    w2 = T_caja.componer(cfg.T_caja_tcp2)
    d_mm, d_rad = desviacion_interna(w1, w2, cfg.relativo_nominal())
    assert d_mm < 1e-9 and d_rad < 1e-9


def test_separacion_de_5_mm_se_detecta():
    cfg = _cfg()
    T_caja = Pose.crear(t=[600, 0, 0])
    w1 = T_caja.componer(cfg.T_caja_tcp1)
    w2 = T_caja.componer(cfg.T_caja_tcp2).componer(Pose.crear(t=[5, 0, 0]))
    d_mm, _ = desviacion_interna(w1, w2, cfg.relativo_nominal())
    assert np.isclose(d_mm, 5.0, atol=0.5)


def test_pose_de_la_caja_desde_la_camara_del_maestro():
    T_w_cam = Pose.crear(t=[500, 0, 900])
    T_cam_caja = Pose.crear(t=[0, 0, 400])
    T_w_caja = pose_caja_en_mundo(T_w_cam, T_cam_caja)
    assert np.allclose(T_w_caja.t, [500, 0, 1300])
