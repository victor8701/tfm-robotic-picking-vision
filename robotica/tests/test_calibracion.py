import numpy as np
import pytest

from calibracion.handeye import calibrar_mano_ojo, dispersion_objetivo_en_base
from calibracion.homografia import (aplicar, errores, estimar_homografia, evaluar,
                                    homografia_ransac)
from nucleo.geometria import Pose, angulo, quat_desde_rotvec

rng = np.random.default_rng(7)

H_VERDADERA = np.array([
    [0.80, 0.10, 100.0],
    [-0.05, 0.90, 50.0],
    [1e-4, 2e-4, 1.0],
])


def _puntos(n=12):
    src = rng.uniform([0, 0], [640, 480], size=(n, 2))
    dst = aplicar(H_VERDADERA, src)
    return src, dst


def test_homografia_exacta_sin_ruido():
    src, dst = _puntos()
    H = estimar_homografia(src, dst)
    assert np.max(errores(H, src, dst)) < 1e-6


def test_evaluacion_con_ruido_da_criterio_objetivo():
    src, dst = _puntos(14)
    dst = dst + rng.normal(0, 0.3, dst.shape)
    informe = evaluar(src, dst, n_validacion=3)
    assert informe.criterio == "objetivo"
    assert informe.rms_validacion_mm < 1.0
    assert informe.n_inliers >= 11


def test_ransac_descarta_un_punto_mal_medido():
    src, dst = _puntos(12)
    dst[4] += np.array([60.0, -40.0])
    H, mascara = homografia_ransac(src, dst, umbral_mm=3.0)
    assert not mascara[4]
    assert mascara.sum() == 11
    assert np.max(errores(H, src[mascara], dst[mascara])) < 1e-6


def test_la_validacion_detecta_una_calibracion_mala():
    src, dst = _puntos(12)
    dst[-1] += np.array([30.0, 30.0])   # punto de validación mal medido
    dst[-2] += np.array([-25.0, 20.0])
    informe = evaluar(src, dst, n_validacion=2)
    assert informe.rms_validacion_mm > 15.0
    assert informe.criterio == "repetir"


def test_menos_de_seis_puntos_no_se_aceptan():
    src, dst = _puntos(5)
    with pytest.raises(ValueError):
        evaluar(src, dst)


def _poses_mano(n=14):
    poses = []
    for _ in range(n):
        eje = rng.normal(size=3)
        eje /= np.linalg.norm(eje)
        q = quat_desde_rotvec(eje * rng.uniform(0.3, 1.3))
        poses.append(Pose.crear(t=rng.uniform(-200, 200, 3), q=q))
    return poses


def test_mano_ojo_recupera_la_pose_de_la_camara():
    X = Pose.crear(t=[30.0, -20.0, 80.0], q=quat_desde_rotvec([0.2, -0.1, 0.4]))
    Z = Pose.crear(t=[600.0, 100.0, 0.0], q=quat_desde_rotvec([0.0, 0.0, 0.5]))
    G = _poses_mano()
    C = [X.inversa().componer(g.inversa()).componer(Z) for g in G]   # objetivo en la cámara
    est = calibrar_mano_ojo(G, C)
    assert np.linalg.norm(est.t - X.t) < 0.5
    assert angulo(est.q, X.q) < np.deg2rad(0.1)
    mm, rad = dispersion_objetivo_en_base(G, C, est)
    assert mm < 0.5 and rad < 1e-3


def test_mano_ojo_exige_al_menos_tres_pares():
    G = _poses_mano(2)
    with pytest.raises(ValueError):
        calibrar_mano_ojo(G, G)
