"""La ventana del asistente de calibracion (calibracion.app_camara) con una camara falsa: guia los cuatro pasos y deja el camara.json.
Necesita pantalla (en WSL, WSLg); sin ella se salta."""
import time
import tkinter as tk
from pathlib import Path

import numpy as np
import pytest

from vision.camara import ModeloCamara
from vision.proveedores import Fotograma

from test_asistente_calibracion import foto_del_tablero_en_la_cinta, fotos_tablero


def _hay_pantalla() -> bool:
    try:
        raiz = tk.Tk()
        raiz.destroy()
        return True
    except tk.TclError:
        return False


pytestmark = pytest.mark.skipif(not _hay_pantalla(), reason="no hay pantalla (Tk no puede abrir una ventana)")


class CamaraFalsa:
    """Da el fotograma que se le ponga con `poner(...)`; hace de cámara de verdad: siguiente() siempre contesta."""

    def __init__(self, bgr):
        self.bgr = bgr
        self.cerrada = False

    def poner(self, bgr):
        self.bgr = bgr

    def siguiente(self):
        time.sleep(0.005)
        return Fotograma(self.bgr, None, "falsa")

    def cerrar(self):
        self.cerrada = True


@pytest.fixture(scope="module")
def fotos():
    return fotos_tablero(12)


@pytest.fixture
def app(tmp_path, fotos):
    from calibracion.app_camara import App
    camara = CamaraFalsa(fotos[0])
    a = App(camara, indice=0, tam=None, salida=str(tmp_path / "camara_webcam.json"))
    a.camara_falsa = camara
    yield a
    try:
        if a.winfo_exists():
            a.cerrar()
    except tk.TclError:                                                        # el test ya la cerro
        pass


def bombear(app, hasta, limite_s=20.0):
    """Hace girar la ventana (sus after y su cola de trabajos) hasta que se cumpla la condicion."""
    fin = time.monotonic() + limite_s
    while time.monotonic() < fin:
        app.update()
        if hasta():
            return True
        time.sleep(0.01)
    return False


def esperar_trabajos(app):
    assert bombear(app, lambda: app._pendientes == 0 and not app._guardando), "los trabajos de la ventana no han terminado"


def test_la_ventana_arranca_con_la_camara_y_pinta_la_imagen(app):
    assert bombear(app, lambda: app._foto_tk is not None)
    assert app.canvas.find_all()                                              # hay imagen en el lienzo
    assert "imagen de 1280x960" in app.l_resolucion.cget("text")
    assert [app.nb.tab(i, "text") for i in range(4)] == ["1  Tablero", "2  Cámara", "3  Posición", "4  Probar y guardar"]


def test_el_tablero_se_cambia_y_avisa_si_el_origen_seria_ambiguo(app):
    app.v_columnas.set(9)
    app.v_filas.set(7)
    app._aplicar_tablero()
    assert "ambiguo" in app.l_aviso_tablero.cget("text")
    app.v_filas.set(6)
    app.v_cuadro.set("24,5")                                                  # con coma decimal tambien
    assert app._aplicar_tablero() and app.asistente.tablero.cuadro_mm == 24.5 and app.l_aviso_tablero.cget("text") == ""
    app.v_cuadro.set("grande")
    assert app._aplicar_tablero() is False and "no válido" in app._mensaje.get().lower()
    app.v_cuadro.set("25")
    app._aplicar_tablero()


def test_se_ve_el_tablero_en_vivo_y_se_guardan_las_fotos_con_espacio(app, fotos):
    app.nb.select(1)
    assert bombear(app, lambda: app._esq_vivas is not None)                   # lo detecta en vivo (la foto 0 lo tiene)
    guardadas = 0
    for f in fotos[:9]:
        app.camara_falsa.poner(f)
        time.sleep(0.05)
        app._esq_vivas = None
        app._guardar_foto()
        esperar_trabajos(app)
        guardadas = app.asistente.n_fotos
    assert guardadas == 9
    assert "Fotos: 9 de 15" in app.l_fotos.cget("text")
    app.camara_falsa.poner(fotos[8])                                          # una foto casi igual a la ultima: se rechaza y lo dice
    time.sleep(0.05)
    app._guardar_foto()
    esperar_trabajos(app)
    assert app.asistente.n_fotos == 9 and "casi igual" in app._mensaje.get()


def test_el_asistente_entero_deja_un_camara_json_que_mide(app, fotos, tmp_path):
    app.nb.select(1)
    for f in fotos:
        app.camara_falsa.poner(f)
        time.sleep(0.05)
        app._guardar_foto()
        esperar_trabajos(app)
    assert app.asistente.n_fotos >= 10
    app._calcular_intrinsecos()
    esperar_trabajos(app)
    assert app.asistente.K is not None and "píxeles" in app.l_resultado_int.cget("text") and "muy bien" in app.l_resultado_int.cget("text")

    app.nb.select(2)
    app.camara_falsa.poner(foto_del_tablero_en_la_cinta((700.0, 0.0), 0.0))     # el tablero tendido en la cinta, con su centro en la recogida
    time.sleep(0.05)
    app._calcular_posicion()                                                   # "en casa" por defecto: centro (700, 0), giro 0, z 220
    esperar_trabajos(app)
    texto = app.t_resultado_pos.get("1.0", "end")
    assert "Cámara en la base" in texto and "VALIDACIÓN" in texto and ("OBJETIVO" in texto or "ACEPTABLE" in texto)

    app.nb.select(3)
    from vision.escena import CajaSintetica, escena
    from test_asistente_calibracion import camara_de_la_celda
    app.camara_falsa.poner(escena(camara_de_la_celda(), [CajaSintetica(200.0, 140.0, 120.0, 20.0, (730.0, 30.0))], z_plano=220.0))
    assert bombear(app, lambda: bool(app._dets))                                # la caja que ve con la calibracion recien hecha
    assert app._dets[0].centro == pytest.approx((730.0, 30.0), abs=8.0)
    # pinchar en la imagen da las coordenadas en el robot de ese punto: el centro de la imagen es (casi) la recogida
    class Pinchazo:
        pass
    ev = Pinchazo()
    ev.x, ev.y = round(1280 / 2 * app._escala), round(960 / 2 * app._escala)
    app._pinchar(ev)
    assert "x = 7" in app.l_pinchado.cget("text") or "x = 6" in app.l_pinchado.cget("text")

    app._guardar()
    ruta = Path(app.v_salida.get())
    assert ruta.is_file() and "Guardada en" in app.l_uso.cget("text")
    m = ModeloCamara.cargar(ruta)
    assert m.tam == (1280, 960) and m.info["criterio"] in ("objetivo", "aceptable") and m.info["intrinsecos"] == "fotos"


def test_posicion_con_el_robot_lee_las_esquinas_tocadas_y_avisa_de_lineas_mal_escritas(app):
    from calibracion.app_camara import parsear_toques
    toques, valida = parsear_toques("0,0:700,-100\n8,0:700,100\n# comentario\n\n0,5:550,-100\nv 8,5:550,100\n")
    assert [(t.columna, t.fila, t.x, t.y) for t in toques] == [(0, 0, 700.0, -100.0), (8, 0, 700.0, 100.0), (0, 5, 550.0, -100.0)]
    assert [(t.columna, t.fila) for t in valida] == [(8, 5)]
    with pytest.raises(ValueError, match="línea 2"):
        parsear_toques("0,0:700,-100\nesto no es un punto")
    assert bombear(app, lambda: app.captura.ultimo() is not None)
    app.nb.select(2)
    app.v_modo.set("robot")
    app.t_toques.delete("1.0", "end")
    app.t_toques.insert("1.0", "basura")
    app._calcular_posicion()
    assert "línea 1" in app._mensaje.get()


def test_los_errores_se_dicen_y_no_rompen_nada(app):
    assert bombear(app, lambda: app.captura.ultimo() is not None)
    app.nb.select(2)
    app.asistente.K = None
    app._calcular_posicion()
    esperar_trabajos(app)
    assert "primero los intrínsecos" in app._mensaje.get()
    app.nb.select(3)
    app._guardar()
    assert "todavía no hay calibración" in app._mensaje.get()
    app.v_fov.set("5")
    app._usar_fov()
    assert "entre 20 y 140" in app._mensaje.get()
    app.v_fov.set("62")
    assert bombear(app, lambda: app.captura.ultimo() is not None)
    app._usar_fov()
    assert app.asistente.origen_intrinsecos.startswith("campo de visión") and "campo de visión" in app.l_resultado_int.cget("text")


def test_cerrar_para_la_camara_y_destruye_la_ventana(app):
    camara = app.camara_falsa
    app.cerrar()
    assert camara.cerrada is True and app.captura is None
    with pytest.raises(tk.TclError):                                           # la ventana ya no existe
        app.winfo_exists()


def test_una_camara_que_no_abre_lo_dice_y_la_ventana_sigue(tmp_path, monkeypatch):
    import calibracion.app_camara as A
    def no_abre(indice, tam, api=None, url=None):
        raise ValueError(f"no puedo abrir la cámara {indice}")
    monkeypatch.setattr(A, "abrir_camara_usb", no_abre)
    a = A.App(None, indice=3, tam=None, salida=str(tmp_path / "c.json"))
    try:
        a.update()
        assert a.captura is None and "no puedo abrir la cámara 3" in a._mensaje.get() and "Prueba otro índice" in a._mensaje.get()
    finally:
        a.cerrar()


def test_la_captura_avisa_si_la_camara_falla():
    from calibracion.app_camara import Captura

    class Rota:
        def siguiente(self):
            raise RuntimeError("se ha desconectado")
    c = Captura(Rota())
    fin = time.monotonic() + 3.0
    while c.error is None and time.monotonic() < fin:
        time.sleep(0.01)
    assert c.error == "se ha desconectado" and c.ultimo() is None
    c.cerrar()


def test_los_intrinsecos_se_cargan_de_un_camara_json_desde_la_ventana(app, tmp_path):
    from vision.escena import camara_cenital
    ruta = tmp_path / "vieja.json"
    camara_cenital(tam=(1280, 960), altura_mm=650.0, fov_horizontal_deg=62.0).guardar(ruta)
    app._cargar_intrinsecos(str(ruta))
    assert app.asistente.K is not None and "de vieja.json" in app.l_resultado_int.cget("text")
    app._cargar_intrinsecos(str(tmp_path / "no_existe.json"))
    assert "no puedo leer" in app._mensaje.get()


def test_se_abre_la_camara_del_movil_por_url_desde_la_ventana(app, monkeypatch):
    import calibracion.app_camara as A
    pedidas = []

    def abre(indice, tam, api=None, url=None):
        pedidas.append((indice, url))
        if url and "malo" in url:
            raise ValueError("no puedo abrir la URL " + url + ": ¿el móvil y el PC están en la misma Wi-Fi?")
        return CamaraFalsa(app.camara_falsa.bgr)
    monkeypatch.setattr(A, "abrir_camara_usb", abre)
    app.v_url.set("http://192.168.1.50:8080/video")
    app._abrir(None, 0, app.v_url.get().strip())
    assert pedidas[-1] == (0, "http://192.168.1.50:8080/video") and "del móvil" in app._mensaje.get() and app.captura is not None
    app._abrir(None, 1, "")
    assert pedidas[-1] == (1, None) and "Cámara 1 abierta" in app._mensaje.get()          # el botón Abrir vuelve a la cámara por número
    app._abrir(None, 0, "http://malo/video")
    assert "misma Wi-Fi" in app._mensaje.get() and "Prueba otro índice" not in app._mensaje.get() and app.captura is None
