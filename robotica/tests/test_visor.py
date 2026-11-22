"""El visor en tiempo real: vista previa sin gastar fotos, resultado de cada caja, errores y falta de pantalla (sin abrir ventanas)."""
import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from celda.percepcion import FuenteCamara, FuenteCsv
from test_celda_percepcion import Z_CINTA, _cam, _carpeta_con_fotos
from vision.proveedores import Carpeta
from vision.visor import ALTO_BANDA, MEDIDA_S, Visor, crear_visor, ejecutar_con_visor


def _fuente(tmp_path, n=2, **kw):
    return FuenteCamara(Carpeta(_carpeta_con_fotos(tmp_path / "juego", n=n)), _cam(), Z_CINTA, params={"modo": "profundidad"},
                        tiempo_max_s=0.3, pausa_s=0.01, **kw)


class Reloj:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def test_la_vista_previa_dibuja_la_caja_y_no_gasta_la_foto(tmp_path):
    fuente = _fuente(tmp_path)
    visor = Visor(fuente, mostrar=False)
    assert visor.imagen_actual() is None
    visor.actualizar()
    img = visor.imagen_actual()
    cam = _cam()
    assert img.shape == (cam_alto(fuente) + ALTO_BANDA, cam_ancho(fuente), 3)
    sin_dibujo = cv2.cvtColor(cv2.imread(str(fuente.proveedor.ficheros[0])), cv2.COLOR_BGR2RGB)
    assert (img[ALTO_BANDA:] != cv2.imread(str(fuente.proveedor.ficheros[0]))).any()                # el contorno, el hilo y el centro
    assert (img[:ALTO_BANDA] != 0).any()                                                             # el texto de la banda
    assert fuente.proveedor.indice == 0                                                              # no se ha gastado nada
    assert sin_dibujo is not None and cam is not None


def cam_alto(fuente):
    return fuente.vista_previa().fotograma.bgr.shape[0]


def cam_ancho(fuente):
    return fuente.vista_previa().fotograma.bgr.shape[1]


def test_al_medir_el_resultado_se_queda_unos_segundos_y_luego_vuelve_la_vista_previa(tmp_path):
    reloj = Reloj()
    fuente = _fuente(tmp_path)
    visor = Visor(fuente, mostrar=False, reloj=reloj)
    visor.actualizar()
    previa = visor.imagen_actual()
    fuente.leer(0)                                     # el ciclo mide la caja 1: FuenteCamara avisa al visor
    medida = visor.imagen_actual()
    assert medida is not previa
    reloj.t += MEDIDA_S - 0.1
    assert visor.imagen_actual() is medida
    reloj.t += 0.2
    assert visor.imagen_actual() is previa             # pasado el tiempo, otra vez la vista previa


def test_si_no_hay_caja_no_quedan_fotos_o_falla_la_camara_el_visor_lo_dice_y_no_se_cae(tmp_path, capsys):
    reloj = Reloj()
    fuente = _fuente(tmp_path, n=1)
    visor = Visor(fuente, mostrar=False, reloj=reloj)
    fuente.leer(0)                                     # se gasta la unica foto
    reloj.t += MEDIDA_S + 1.0                          # y el resultado de esa caja ya no se ensena
    visor.actualizar()
    assert visor.imagen_actual().shape[0] == 360 + ALTO_BANDA                                        # lienzo «no quedan fotos»
    fuente.proveedor = None
    visor.actualizar()
    assert visor.imagen_actual() is not None                                                         # «sin camara configurada»

    class Rota:
        def vista_previa(self):
            raise RuntimeError("la camara se ha desconectado")
        al_medir = None
    visor2 = Visor(Rota(), mostrar=False)
    visor2.actualizar()
    visor2.actualizar()
    assert visor2.imagen_actual() is not None
    assert capsys.readouterr().out.count("la camara se ha desconectado") == 1                       # avisa una vez, no en cada pasada


def test_el_hilo_del_visor_actualiza_solo_y_se_para(tmp_path):
    visor = Visor(_fuente(tmp_path), hz=50.0, mostrar=False)
    visor.iniciar()
    try:
        limite = time.time() + 5.0
        while visor.imagen_actual() is None and time.time() < limite:
            time.sleep(0.02)
        assert visor.imagen_actual() is not None
    finally:
        visor.parar()
    assert not visor._hilo.is_alive()


def test_sin_ventana_o_sin_pantalla_bombear_no_rompe_nada(tmp_path, monkeypatch):
    visor = Visor(_fuente(tmp_path), mostrar=False)
    visor.actualizar()
    assert visor.bombear() is False                    # sin ventana pedida

    pantalla = Visor(_fuente(tmp_path / "otra"), mostrar=True)
    pantalla.actualizar()

    def sin_gui(*a, **k):
        raise cv2.error("The function is not implemented. Rebuild the library with GTK support")
    monkeypatch.setattr(cv2, "imshow", sin_gui)
    assert pantalla.bombear() is False and pantalla.sin_pantalla is True                            # avisa y sigue sin ventana
    assert pantalla.bombear() is False


def test_crear_visor_solo_con_la_opcion_y_una_camara(tmp_path):
    fuente = _fuente(tmp_path)
    assert crear_visor(fuente, SimpleNamespace(camara=None)) is None
    assert crear_visor(fuente, SimpleNamespace(camara={"visor": False})) is None
    assert isinstance(crear_visor(fuente, SimpleNamespace(camara={"visor": True})), Visor)
    csv = tmp_path / "caja.csv"
    csv.write_text("1;1;1;0\n", encoding="utf-8")
    assert crear_visor(FuenteCsv(csv), SimpleNamespace(camara={"visor": True})) is None             # en simulacion no hay camara que ver


def test_ejecutar_con_visor_corre_el_ciclo_en_otro_hilo_y_relanza_sus_errores(tmp_path):
    visor = Visor(_fuente(tmp_path), mostrar=False)
    hilos = []
    ejecutar_con_visor(lambda: hilos.append(threading.current_thread().name), visor, mantener_s=0.0)
    assert hilos == ["ciclo-celda"]

    def falla():
        raise RuntimeError("el ciclo se ha parado")
    with pytest.raises(RuntimeError, match="el ciclo se ha parado"):
        ejecutar_con_visor(falla, Visor(_fuente(tmp_path / "b"), mostrar=False), mantener_s=0.0)
