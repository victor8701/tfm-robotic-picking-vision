"""Lectura de caja.csv (simulacion): formato, orden y errores."""
from pathlib import Path

import pytest

from celda.percepcion import Caja, FuenteCsv

RAIZ = Path(__file__).resolve().parents[1]


def test_lee_las_cajas_en_orden(tmp_path):
    f = tmp_path / "caja.csv"
    f.write_text("300.0;200.0;120.0;-30.5\n150.0;100.0;80.0;45.0\n", encoding="utf-8")
    fuente = FuenteCsv(f)
    assert fuente.leer(0) == Caja(300.0, 200.0, 120.0, -30.5)
    assert fuente.leer(1) == Caja(150.0, 100.0, 80.0, 45.0)
    with pytest.raises(IndexError):
        fuente.leer(2)


@pytest.mark.parametrize("linea", ["300;200;120", "300;200;120;120", "300;-5;120;0"])
def test_rechaza_lineas_invalidas(tmp_path, linea):
    f = tmp_path / "caja.csv"
    f.write_text(linea + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        FuenteCsv(f).leer(0)


def test_fichero_inexistente_da_error_claro(tmp_path):
    with pytest.raises(FileNotFoundError):
        FuenteCsv(tmp_path / "no-existe.csv").leer(0)


def test_no_lee_el_fichero_hasta_la_primera_caja(tmp_path):
    f = tmp_path / "caja.csv"
    fuente = FuenteCsv(f)  # RAPID aun no ha escrito el fichero: crear la fuente no debe fallar
    f.write_text("300.0;200.0;120.0;0.0\n", encoding="utf-8")
    assert fuente.leer(0) == Caja(300.0, 200.0, 120.0, 0.0)


# ---------------------------------------------------------------- FuenteCamara (vision/) con imagenes sinteticas
import json  # noqa: E402

import cv2  # noqa: E402

from celda.config import cargar  # noqa: E402
from celda.percepcion import FuenteCamara, crear_fuente  # noqa: E402
from vision.escena import CajaSintetica, camara_cenital, escena, profundidad  # noqa: E402
from vision.proveedores import Fotograma  # noqa: E402

Z_CINTA = 220.0


class _Lista:
    """Proveedor de imagenes de prueba: los fotogramas dados, uno a uno (y luego, ninguno)."""

    def __init__(self, fotogramas):
        self._f = list(fotogramas)

    def siguiente(self):
        return self._f.pop(0) if self._f else None


def _cam():
    return camara_cenital(tam=(960, 720), altura_mm=650.0, centro_xy=(700.0, 0.0), z_plano=Z_CINTA)


def _foto(cajas, cam=None):
    """Un fotograma (imagen y profundidad) de la cinta con esas cajas. Calcular la profundidad cuesta: se reutiliza el mismo objeto."""
    cam = cam or _cam()
    return Fotograma(escena(cam, cajas, z_plano=Z_CINTA), profundidad(cam, cajas, z_plano=Z_CINTA), "x")


def _fuente(fotogramas, **kw):
    kw.setdefault("params", {"modo": "profundidad"})
    kw.setdefault("tiempo_max_s", 0.3)
    kw.setdefault("pausa_s", 0.01)
    return FuenteCamara(_Lista(fotogramas), _cam(), Z_CINTA, **kw)


def test_la_fuente_de_camara_da_la_caja_medida_en_la_base():
    caja = CajaSintetica(200.0, 140.0, 120.0, 20.0, (712.0, 9.0))
    c = _fuente([_foto([caja])]).leer(0)
    assert (c.largo, c.ancho, c.alto) == pytest.approx((200.0, 140.0, 120.0), abs=1.5)
    assert c.giro_deg == pytest.approx(20.0, abs=1.0) and c.centro == pytest.approx((712.0, 9.0), abs=1.0)


def test_espera_hasta_que_llega_una_caja_entera_y_elige_la_mas_cercana_al_punto():
    cerca, lejos = CajaSintetica(150.0, 100.0, 80.0, 0.0, (700.0, 0.0)), CajaSintetica(150.0, 100.0, 80.0, 0.0, (900.0, 20.0))
    vacio = _foto([])
    fuente = _fuente([vacio, vacio, _foto([lejos, cerca])], centro_nominal=(700.0, 0.0), tiempo_max_s=5.0)
    c = fuente.leer(0)
    assert c.centro == pytest.approx((700.0, 0.0), abs=1.0)


def test_si_no_hay_caja_a_tiempo_se_para_con_un_error_y_no_inventa_nada():
    fuente = _fuente([_foto([])] * 500, tiempo_max_s=0.2)
    with pytest.raises(RuntimeError, match="no ve ninguna caja entera en 0.2 s"):
        fuente.leer(0)


def test_una_caja_cortada_por_el_borde_no_vale_y_el_error_lo_dice():
    cortada = CajaSintetica(200.0, 140.0, 120.0, 0.0, (1000.0, 0.0))   # sale por la derecha de la imagen
    fuente = _fuente([_foto([cortada])] * 200, tiempo_max_s=0.2)
    with pytest.raises(RuntimeError, match="cortada por el borde"):
        fuente.leer(0)


def test_sin_mas_imagenes_o_sin_configurar_hay_un_error_claro():
    with pytest.raises(RuntimeError, match="no tiene mas imagenes"):
        _fuente([]).leer(0)
    with pytest.raises(RuntimeError, match="falta la seccion 'camara'"):
        FuenteCamara(motivo_sin_configurar="falta la seccion 'camara' en config_celda.json").leer(0)
    assert _fuente([]).total() is None


def test_la_fuente_se_configura_con_los_ajustes_de_rapid():
    from dataclasses import replace
    cfg = replace(cargar(RAIZ / "celda" / "config_celda.json"), z_cinta=250.0, centro_recogida=(650.0, 30.0), t_max_camara=2.5)
    f = _fuente([])
    f.configurar(cfg)
    assert (f.z_cinta, f.centro_nominal, f.tiempo_max_s) == (250.0, (650.0, 30.0), 2.5)


def _config_con_camara(carpeta, camara):
    """Escribe en `carpeta` una configuracion de la celda en modo real con esa seccion camara y devuelve su ruta."""
    d = json.loads((RAIZ / "celda" / "config_celda.json").read_text(encoding="utf-8"))
    d["modo_simulacion"] = False
    if camara is not None:
        d["camara"] = camara
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / "config.json"
    ruta.write_text(json.dumps(d), encoding="utf-8")
    return ruta


def test_la_configuracion_crea_la_fuente_de_camara_con_rutas_relativas_a_su_carpeta(tmp_path):
    cam = _cam()
    caja = CajaSintetica(200.0, 140.0, 120.0, 0.0, (700.0, 0.0))
    (tmp_path / "celda").mkdir()
    fotos = tmp_path / "celda" / "fotos"
    fotos.mkdir()
    cv2.imwrite(str(fotos / "a.png"), escena(cam, [caja], z_plano=Z_CINTA))
    import numpy as np
    np.save(fotos / "a.npy", profundidad(cam, [caja], z_plano=Z_CINTA))
    cam.guardar(tmp_path / "celda" / "camara.json")
    cfg = cargar(_config_con_camara(tmp_path / "celda", {"calibracion": "camara.json", "origen": {"tipo": "carpeta", "ruta": "fotos"}, "modo": "profundidad"}))
    assert cfg.camara["calibracion"] == str(tmp_path / "celda" / "camara.json")
    fuente = crear_fuente(cfg)
    assert isinstance(fuente, FuenteCamara)
    c = fuente.leer(0)
    assert (c.largo, c.ancho, c.alto) == pytest.approx((200.0, 140.0, 120.0), abs=1.5)


def test_sin_seccion_camara_la_fuente_real_lo_explica_al_leer(tmp_path):
    fuente = crear_fuente(cargar(_config_con_camara(tmp_path / "sin", None)))
    with pytest.raises(RuntimeError, match="falta la seccion 'camara'"):
        fuente.leer(0)


def test_una_configuracion_de_camara_incompleta_o_mala_se_rechaza(tmp_path):
    with pytest.raises(ValueError, match="camara.calibracion"):
        crear_fuente(cargar(_config_con_camara(tmp_path / "a", {"origen": {"tipo": "carpeta", "ruta": "."}})))
    _cam().guardar(tmp_path / "b" / "camara.json") if (tmp_path / "b").mkdir() is None else None
    with pytest.raises(ValueError, match="origen de imágenes desconocido"):
        crear_fuente(cargar(_config_con_camara(tmp_path / "b", {"calibracion": "camara.json", "origen": {"tipo": "ojos"}})))
    with pytest.raises(ValueError, match="no puedo leer la calibración"):
        crear_fuente(cargar(_config_con_camara(tmp_path / "c", {"calibracion": "no_existe.json", "origen": {"tipo": "carpeta", "ruta": "."}})))
