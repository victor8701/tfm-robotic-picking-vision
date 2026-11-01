import cv2
import numpy as np
import pytest

from nucleo.geometria import Pose, quat_desde_rotvec, rotvec_desde_quat, angulo
from vision.esquinas import esquinas_por_contorno, esquinas_por_lineas
from vision.pose_caja import pose_desde_esquinas, puntos_objeto

ESQUINAS_VERDADERAS = np.array([[200, 120], [450, 140], [470, 380], [180, 360]], dtype=np.float32)
CARTON_BGR = (70, 110, 150)     # marrón de cartón (RGB 150, 110, 70)
FONDO_BGR = (120, 120, 120)     # gris neutro, sin color de cartón


def _imagen(esquinas, ruido=0.0, semilla=0):
    img = np.full((480, 640, 3), FONDO_BGR, np.uint8)
    cv2.fillPoly(img, [np.round(esquinas).astype(np.int32)], CARTON_BGR)
    if ruido > 0:
        rng = np.random.default_rng(semilla)
        img = np.clip(img + rng.normal(0, ruido, img.shape), 0, 255).astype(np.uint8)
    return img


def test_contorno_encuentra_las_cuatro_esquinas():
    esq = esquinas_por_contorno(_imagen(ESQUINAS_VERDADERAS))
    assert esq is not None
    assert np.max(np.linalg.norm(esq - ESQUINAS_VERDADERAS, axis=1)) < 4.0


def test_contorno_resiste_ruido_de_imagen():
    esq = esquinas_por_contorno(_imagen(ESQUINAS_VERDADERAS, ruido=10.0))
    assert esq is not None
    assert np.max(np.linalg.norm(esq - ESQUINAS_VERDADERAS, axis=1)) < 6.0


def test_lineas_encuentra_las_esquinas_con_tolerancia_mayor():
    esq = esquinas_por_lineas(_imagen(ESQUINAS_VERDADERAS))
    assert esq is not None
    assert np.max(np.linalg.norm(esq - ESQUINAS_VERDADERAS, axis=1)) < 10.0


def test_sin_caja_no_hay_esquinas():
    img = np.full((480, 640, 3), FONDO_BGR, np.uint8)
    assert esquinas_por_contorno(img) is None
    assert esquinas_por_lineas(img) is None


K = np.array([[800.0, 0.0, 320.0], [0.0, 800.0, 240.0], [0.0, 0.0, 1.0]])
ANCHO, LARGO = 700.0, 650.0


def _proyectar(T: Pose) -> np.ndarray:
    rvec = rotvec_desde_quat(T.q).reshape(3, 1)
    tvec = T.t.reshape(3, 1)
    px, _ = cv2.projectPoints(puntos_objeto(ANCHO, LARGO), rvec, tvec, K, np.zeros(5))
    return px.reshape(4, 2)


def test_pose_de_la_caja_se_recupera_con_ruido_de_pixel():
    T_verdadera = Pose.crear(t=[40.0, -30.0, 700.0], q=quat_desde_rotvec([0.35, -0.2, 0.1]))
    rng = np.random.default_rng(3)
    px = _proyectar(T_verdadera) + rng.normal(0, 0.3, (4, 2))
    est = pose_desde_esquinas(px, K, None, ANCHO, LARGO)
    assert np.linalg.norm(est.T_cam_caja.t - T_verdadera.t) < 5.0
    assert angulo(est.T_cam_caja.q, T_verdadera.q) < np.deg2rad(1.0)
    assert est.rms_px < 1.5
    assert est.ambiguedad > 1.0


def test_pose_exacta_sin_ruido():
    T_verdadera = Pose.crear(t=[-60.0, 25.0, 900.0], q=quat_desde_rotvec([-0.1, 0.25, 0.3]))
    est = pose_desde_esquinas(_proyectar(T_verdadera), K, None, ANCHO, LARGO)
    assert np.allclose(est.T_cam_caja.t, T_verdadera.t, atol=1e-3)
    assert est.rms_px < 1e-3


def test_orden_de_las_esquinas_del_detector_coincide_con_el_modelo():
    T = Pose.crear(t=[0.0, 0.0, 600.0])
    px = _proyectar(T)
    # Con la caja frente a la cámara, TL/TR/BR/BL del modelo caen en orden horario en la imagen.
    assert px[0, 0] < px[1, 0] and px[0, 1] < px[3, 1]
    assert px[2, 0] > px[3, 0] and px[2, 1] > px[1, 1]
