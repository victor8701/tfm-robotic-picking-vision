import numpy as np
import pytest

from nucleo import geometria as g
from nucleo.geometria import Pose, quat_desde_rotvec
from nucleo.seguridad import EspacioTrabajo, Limites, Resultado, Vigilante, filtrar, retener

ESPACIO = EspacioTrabajo(-600, 600, -600, 600, 0, 800)
LIMITES = Limites(paso_mm=0.5, giro_rad=0.0025, desviacion_mm=20.0, desviacion_rad=0.1)


def test_espacio_recorta_y_detecta():
    assert np.allclose(ESPACIO.ajustar([700, 0, 100]), [600, 0, 100])
    assert ESPACIO.contiene([0, 0, 400])
    assert not ESPACIO.contiene([0, 0, 900])


def test_espacio_mal_ordenado_falla():
    with pytest.raises(ValueError):
        EspacioTrabajo(1, 0, 0, 1, 0, 1)


def test_limites_no_positivos_fallan():
    with pytest.raises(ValueError):
        Limites(0.0, 0.1, 1.0, 0.1)


def test_paso_limitado_por_ciclo():
    ref = Pose.crear(t=[0, 0, 400])
    nuevo, res = filtrar(ref, Pose.crear(t=[100, 0, 400]), ref, ESPACIO, LIMITES)
    assert res is Resultado.LIMITADO
    assert np.isclose(np.linalg.norm(nuevo.t - ref.t), LIMITES.paso_mm)


def test_objetivo_cercano_pasa_sin_limitar():
    ref = Pose.crear(t=[0, 0, 400])
    objetivo = Pose.crear(t=[0.2, 0, 400])
    nuevo, res = filtrar(ref, objetivo, ref, ESPACIO, LIMITES)
    assert res is Resultado.OK
    assert np.allclose(nuevo.t, objetivo.t)


def test_objetivo_fuera_del_espacio_se_recorta():
    ref = Pose.crear(t=[590, 0, 400])
    nuevo, res = filtrar(ref, Pose.crear(t=[900, 0, 400]), ref, ESPACIO, LIMITES)
    assert res is Resultado.LIMITADO
    assert nuevo.t[0] <= 600.0 + 1e-9


def test_giro_limitado_por_ciclo():
    ref = Pose.crear(t=[0, 0, 400])
    objetivo = Pose.crear(t=[0, 0, 400], q=quat_desde_rotvec([0, 0, 1.0]))
    nuevo, res = filtrar(ref, objetivo, ref, ESPACIO, LIMITES)
    assert res is Resultado.LIMITADO
    assert np.isclose(g.angulo(ref.q, nuevo.q), LIMITES.giro_rad)


def test_desviacion_provoca_fallo_y_retencion():
    ref = Pose.crear(t=[0, 0, 400])
    real = Pose.crear(t=[0, 0, 300])  # el robot va 100 mm por detrás de la referencia
    nuevo, res = filtrar(ref, Pose.crear(t=[0, 0, 401]), real, ESPACIO, LIMITES)
    assert res is Resultado.FALLO
    assert np.allclose(nuevo.t, real.t)


def test_vigilante_plazo():
    v = Vigilante(0.1)
    assert v.vencido(0.0)  # sin ningún objetivo todavía
    v.marcar(1.0)
    assert not v.vencido(1.05)
    assert v.vencido(1.2)


def test_vigilante_plazo_invalido_falla():
    with pytest.raises(ValueError):
        Vigilante(0.0)


def test_retener_copia_la_posicion_real():
    real = Pose.crear(t=[1, 2, 3])
    r = retener(real)
    assert np.allclose(r.t, real.t)
    assert r.t is not real.t
