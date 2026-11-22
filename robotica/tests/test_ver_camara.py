"""vision.ver_camara: ver la camara en vivo sin robot. Con una camara falsa (fotogramas sinteticos) y sin abrir ventanas."""
import argparse

import cv2
import numpy as np
import pytest

from vision.camara import ModeloCamara
from vision.escena import CajaSintetica, camara_cenital, escena
from vision.proveedores import Fotograma
from vision.ver_camara import (AVISO_SIN_CALIBRAR, DESCARTAR_FOTOGRAMAS, abrir_camara, construir_fuente, listar_camaras, main, mosaico_de_camaras,
                               nombres_windows)
from vision.visor import Visor

ALTURA = 600.0
TAM = (960, 720)


class CamaraFalsa:
    """Da siempre el mismo fotograma (una caja sobre una mesa vista desde arriba) y cuenta cuantos ha dado."""

    def __init__(self, cajas=None, color=True):
        cam = camara_cenital(tam=TAM, altura_mm=ALTURA, centro_xy=(0.0, 0.0), z_plano=0.0)
        self.foto = Fotograma(escena(cam, cajas if cajas is not None else [CajaSintetica(200.0, 140.0, 100.0, 25.0, (30.0, -20.0))], z_plano=0.0), None, "x")
        self.dados = 0
        self.cerrada = False

    def siguiente(self):
        self.dados += 1
        return self.foto

    def cerrar(self):
        self.cerrada = True


def _args(**kw):
    base = dict(modo="color", fondo=None, calibracion=None, z=220.0, altura=ALTURA, fov=62.0, alto=100.0)
    base.update(kw)
    return argparse.Namespace(**base)


def test_sin_calibrar_mide_la_caja_con_un_modelo_cenital_aproximado():
    camara = CamaraFalsa()
    fuente, sin_calibrar = construir_fuente(camara, _args())
    assert sin_calibrar is True and camara.dados == DESCARTAR_FOTOGRAMAS            # los primeros fotogramas se tiran
    v = fuente.vista_previa()
    d = v.elegida
    assert d is not None
    assert (d.largo, d.ancho) == pytest.approx((200.0, 140.0), rel=0.04)
    assert d.giro_deg == pytest.approx(25.0, abs=2.0) and d.centro == pytest.approx((30.0, -20.0), abs=6.0)
    assert v.origen                                               # dice de donde viene la imagen


def test_con_calibracion_usa_la_de_la_celda_y_no_avisa(tmp_path):
    cam = camara_cenital(tam=TAM, altura_mm=ALTURA, centro_xy=(0.0, 0.0), z_plano=0.0)
    cam.guardar(tmp_path / "camara.json")
    fuente, sin_calibrar = construir_fuente(CamaraFalsa(), _args(calibracion=str(tmp_path / "camara.json"), z=0.0))
    assert sin_calibrar is False and isinstance(fuente.modelo, ModeloCamara)
    assert fuente.vista_previa().elegida.largo == pytest.approx(200.0, rel=0.03)


def test_errores_claros_si_no_hay_imagen_o_falta_el_fondo(tmp_path):
    class Muda:
        def siguiente(self):
            return None
    with pytest.raises(ValueError, match="no da imágenes"):
        construir_fuente(Muda(), _args())
    with pytest.raises(ValueError, match="necesita --fondo"):
        construir_fuente(CamaraFalsa(), _args(modo="fondo"))
    with pytest.raises(ValueError, match="no puedo leer"):
        construir_fuente(CamaraFalsa(), _args(modo="fondo", fondo=str(tmp_path / "no_existe.png")))


def test_el_visor_pone_el_aviso_de_sin_calibrar_en_la_banda():
    fuente, _ = construir_fuente(CamaraFalsa(), _args())
    con, sin = Visor(fuente, mostrar=False, aviso=AVISO_SIN_CALIBRAR), Visor(fuente, mostrar=False)
    con.actualizar()
    sin.actualizar()
    banda_con, banda_sin = con.imagen_actual()[:38], sin.imagen_actual()[:38]
    assert (banda_con != 0).sum() > (banda_sin != 0).sum()                            # mas texto en la banda


def test_main_con_una_camara_falsa_abre_el_visor_un_momento_y_la_deja_cerrada(capsys):
    camara = CamaraFalsa()
    assert main(["--sin-ventana", "--segundos", "0.3"], proveedor=camara) == 0
    salida = capsys.readouterr().out
    assert "SIN CALIBRAR" in salida and "Pulsa q" in salida
    assert camara.dados > DESCARTAR_FOTOGRAMAS                                       # el visor ha ido pidiendo imagen
    assert camara.cerrada is False                                                   # la camara de fuera no la cierra el programa


def test_main_con_calibracion_no_dice_sin_calibrar(tmp_path, capsys):
    camara_cenital(tam=TAM, altura_mm=ALTURA, centro_xy=(0.0, 0.0), z_plano=0.0).guardar(tmp_path / "camara.json")
    assert main(["--sin-ventana", "--segundos", "0.2", "--calibracion", str(tmp_path / "camara.json"), "--z", "0"], proveedor=CamaraFalsa()) == 0
    assert "SIN CALIBRAR" not in capsys.readouterr().out


def test_listar_dice_que_indices_abren_y_su_resolucion(monkeypatch, capsys):
    class Falsa:
        def __init__(self, i):
            self.i = i

        def isOpened(self):
            return self.i in (0, 2)

        def get(self, prop):
            return {cv2.CAP_PROP_FRAME_WIDTH: 1280, cv2.CAP_PROP_FRAME_HEIGHT: 720}[prop]

        def release(self):
            pass
    assert listar_camaras(abrir=Falsa) == [(0, (1280, 720)), (2, (1280, 720))]
    monkeypatch.setattr(cv2, "VideoCapture", Falsa)
    monkeypatch.setattr("vision.ver_camara.listar_camaras", lambda: listar_camaras(abrir=Falsa))
    assert main(["--listar"]) == 0
    salida = capsys.readouterr().out
    assert "cámara 0: abre (1280 x 720)" in salida and "cámara 2" in salida and "infrarrojos" in salida


def test_si_ninguna_camara_abre_el_error_explica_por_que(monkeypatch, capsys):
    class Cerrada:
        def __init__(self, *a):
            pass

        def isOpened(self):
            return False

        def get(self, prop):
            return 0

        def release(self):
            pass
    monkeypatch.setattr(cv2, "VideoCapture", Cerrada)
    assert main(["--listar"]) == 2
    assert "Ninguna cámara abre" in capsys.readouterr().out
    assert main(["--indice", "7", "--sin-ventana"]) == 2
    salida = capsys.readouterr().out
    assert "no puedo abrir la cámara 7" in salida and "Teams" in salida and "Privacidad" in salida
    with pytest.raises(ValueError, match="otro --indice"):
        abrir_camara(7, None)


def test_el_tamano_pedido_se_escribe_ancho_x_alto():
    from vision.ver_camara import _tam
    assert _tam("1280x720") == (1280, 720) and _tam("640X480") == (640, 480)
    with pytest.raises(argparse.ArgumentTypeError, match="ancho x alto"):
        _tam("grande")


def test_guardar_calibracion_deja_un_camara_json_que_ve_el_plano_de_la_cinta_a_la_altura_pedida(tmp_path, capsys):
    destino = tmp_path / "camara_webcam.json"
    assert main(["--sin-ventana", "--segundos", "0.1", "--altura", "600", "--z", "220", "--guardar-calibracion", str(destino)], proveedor=CamaraFalsa()) == 0
    assert "Guardada la cámara aproximada" in capsys.readouterr().out
    modelo = ModeloCamara.cargar(destino)
    assert modelo.tam == TAM and modelo.posicion[2] == pytest.approx(820.0)           # 600 sobre la cinta, que esta a z = 220
    assert tuple(modelo.posicion[:2]) == (700.0, 0.0)                                 # el centro de la imagen cae en la recogida (por defecto)
    assert modelo.info["origen"].startswith("cenital aproximada")
    # medir la tapa de una caja a 100 mm sobre la cinta con ese camara.json (plano de la cinta a z = 220) da lo mismo que con el modelo sin guardar
    from vision.deteccion import detectar_cajas
    cam = camara_cenital(tam=TAM, altura_mm=600.0, centro_xy=(0.0, 0.0), z_plano=220.0)
    img = escena(cam, [CajaSintetica(200.0, 140.0, 100.0, 25.0, (30.0, -20.0))], z_plano=220.0)
    d = detectar_cajas(img, modelo, 220.0, 100.0, {"modo": "color"})[0]
    assert (d.largo, d.ancho) == pytest.approx((200.0, 140.0), rel=0.04)


def test_guardar_calibracion_con_calibracion_real_se_rechaza(tmp_path, capsys):
    camara_cenital(tam=TAM, altura_mm=ALTURA, centro_xy=(0.0, 0.0)).guardar(tmp_path / "camara.json")
    assert main(["--sin-ventana", "--calibracion", str(tmp_path / "camara.json"), "--guardar-calibracion", str(tmp_path / "otra.json")],
                proveedor=CamaraFalsa()) == 2
    assert not (tmp_path / "otra.json").exists() and "ya tienes un camara.json" in capsys.readouterr().out


def test_la_camara_usb_se_abre_con_el_backend_pedido_y_en_windows_reintenta_con_directshow(monkeypatch):
    import vision.proveedores as P
    intentos = []

    class Cap:
        def __init__(self, indice, api=None):
            intentos.append(api)
            self.abierta = api == cv2.CAP_DSHOW

        def isOpened(self):
            return self.abierta

        def set(self, *a):
            pass

        def release(self):
            pass
    monkeypatch.setattr(cv2, "VideoCapture", Cap)
    monkeypatch.setattr(P.sys, "platform", "win32")
    P.abrir_camara_usb(0)
    assert intentos == [None, cv2.CAP_DSHOW]                           # el de por defecto no abre; DirectShow si
    intentos.clear()
    P.abrir_camara_usb(0, api="dshow")
    assert intentos == [cv2.CAP_DSHOW]                                  # forzado: solo ese
    intentos.clear()
    with pytest.raises(ValueError, match="no puedo abrir la cámara 3"):
        P.abrir_camara_usb(3, api="msmf")
    assert intentos == [cv2.CAP_MSMF]
    monkeypatch.setattr(P.sys, "platform", "linux")
    intentos.clear()
    with pytest.raises(ValueError):
        P.abrir_camara_usb(0)
    assert intentos == [None]                                           # fuera de Windows no hay segundo intento
    with pytest.raises(ValueError, match="api desconocido"):
        P.abrir_camara_usb(0, api="magia")
    monkeypatch.setattr(P.sys, "platform", "win32")
    assert P.abrir_proveedor({"tipo": "opencv", "indice": 0, "tam": [640, 480], "api": "dshow"}) is not None


def test_el_mosaico_enseña_una_miniatura_por_camara_con_su_indice(monkeypatch):
    class Cap:
        def __init__(self, i):
            self.i = i

        def read(self):
            if self.i == 3:
                return False, None
            return True, np.full((480, 640, 3), 40 * (self.i + 1), np.uint8)

        def release(self):
            pass
    img = mosaico_de_camaras([0, 1, 3], abrir=Cap)
    assert img.shape == (240, 960, 3)                                                  # tres miniaturas de 320 x 240
    assert img[100, 100, 0] == 40 and img[100, 420, 0] == 80                             # cada una con su imagen
    assert (img[:30, :320] != 0).any() and (img[100, 740] == 60).all()                   # la tercera, sin imagen: gris con el rotulo
    assert mosaico_de_camaras([], abrir=Cap).shape == (240, 320, 3)


def test_listar_con_ver_muestra_el_mosaico_y_con_sin_ventana_no(monkeypatch, capsys):
    class Falsa:
        def __init__(self, i):
            self.i = i

        def isOpened(self):
            return self.i in (0, 1)

        def get(self, prop):
            return 640

        def read(self):
            return True, np.zeros((480, 640, 3), np.uint8)

        def release(self):
            pass
    mostradas = []
    monkeypatch.setattr(cv2, "VideoCapture", Falsa)
    monkeypatch.setattr(cv2, "imshow", lambda titulo, img: mostradas.append((titulo, img.shape)))
    monkeypatch.setattr(cv2, "waitKey", lambda ms: -1)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    monkeypatch.setattr("vision.ver_camara.nombres_windows", lambda: ["USB2.0 HD IR UVC WebCam (x2)"])
    assert main(["--listar", "--ver"]) == 0
    salida = capsys.readouterr().out
    assert "Windows tiene conectadas: USB2.0 HD IR UVC WebCam (x2)" in salida and "conéctala por USB" in salida
    assert mostradas == [("Camaras (cualquier tecla cierra)", (240, 640, 3))]
    mostradas.clear()
    assert main(["--listar", "--ver", "--sin-ventana"]) == 0
    assert mostradas == []


def test_los_nombres_de_las_camaras_de_windows_agrupan_las_entradas_repetidas(monkeypatch):
    import vision.ver_camara as V
    monkeypatch.setattr(V.sys, "platform", "win32")
    monkeypatch.setattr(V.subprocess, "run", lambda *a, **k: argparse.Namespace(stdout="USB2.0 HD IR UVC WebCam\r\nUSB2.0 HD IR UVC WebCam\r\nLogitech C920\r\n"))
    assert nombres_windows() == ["USB2.0 HD IR UVC WebCam (x2)", "Logitech C920"]
    monkeypatch.setattr(V.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("sin powershell")))
    assert nombres_windows() == []
    monkeypatch.setattr(V.sys, "platform", "linux")
    assert nombres_windows() == []


def test_cajas_limita_cuantas_cajas_identifica_la_vista_previa(tmp_path):
    cajas = [CajaSintetica(160.0, 110.0, 100.0, 0.0, (-220.0, 100.0)), CajaSintetica(110.0, 70.0, 100.0, 0.0, (200.0, 110.0)), CajaSintetica(80.0, 60.0, 100.0, 0.0, (0.0, -140.0))]
    for pedidas, esperadas in ((None, 3), (3, 3), (2, 2), (1, 1)):
        fuente, _ = construir_fuente(CamaraFalsa(cajas), _args())
        fuente.max_cajas = pedidas
        v = fuente.vista_previa()
        assert len(v.detecciones) == esperadas
        assert v.elegida is not None and v.elegida in v.detecciones                       # la que se cogeria siempre sale
    # por defecto identifica 1: la que cogeria el ciclo (la mayor sin punto de recogida, la mas cercana a el con punto)
    from vision.deteccion import elegir
    todas, _ = construir_fuente(CamaraFalsa(cajas), _args())
    todas.max_cajas = None
    dets = todas.vista_previa().detecciones
    assert any(d.recortada for d in dets)                                             # la de la izquierda sale cortada por el borde: no se coge
    enteras = [d for d in dets if not d.recortada]
    arg = argparse.Namespace(**{**vars(_args()), "cajas": 1})
    fuente, _ = construir_fuente(CamaraFalsa(cajas), arg)
    assert fuente.max_cajas == 1
    assert [d.centro for d in fuente.vista_previa().detecciones] == [elegir(enteras).centro]
    assert main(["--sin-ventana", "--segundos", "0.1", "--cajas", "2"], proveedor=CamaraFalsa(cajas)) == 0
    for objetivo in ((200.0, 110.0), (0.0, -140.0)):
        fuente, _ = construir_fuente(CamaraFalsa(cajas), _args())
        fuente.max_cajas, fuente.centro_nominal = 1, objetivo
        (unica,) = fuente.vista_previa().detecciones
        assert unica.centro == elegir(enteras, objetivo).centro
        assert np.hypot(unica.centro[0] - objetivo[0], unica.centro[1] - objetivo[1]) < 40.0   # y es la caja que esta en ese punto


def test_la_calibracion_aproximada_centra_la_imagen_en_el_punto_de_recogida(tmp_path):
    from vision.ver_camara import guardar_calibracion_aproximada
    guardar_calibracion_aproximada(tmp_path / "c.json", TAM, 600.0, 62.0, 220.0, (700.0, 0.0))
    m = ModeloCamara.cargar(tmp_path / "c.json")
    ancho, alto = TAM
    centro = m.pixel_a_plano(np.array([[ancho / 2, alto / 2]]), 220.0)[0]
    derecha = m.pixel_a_plano(np.array([[ancho / 2 + 100, alto / 2]]), 220.0)[0]
    arriba = m.pixel_a_plano(np.array([[ancho / 2, alto / 2 - 100]]), 220.0)[0]
    assert tuple(np.round(centro, 3)) == (700.0, 0.0)                                  # el centro de la imagen es la recogida
    assert derecha[0] > 700.0 and derecha[1] == pytest.approx(0.0, abs=1e-6)           # a la derecha de la imagen, +x del robot
    assert arriba[1] > 0.0 and arriba[0] == pytest.approx(700.0, abs=1e-6)             # hacia arriba en la imagen, +y
    assert m.info["centro_de_la_imagen_en_la_base_mm"] == [700.0, 0.0]


def test_el_centro_y_el_tamano_de_la_cajas_se_validan():
    from vision.ver_camara import _centro
    assert _centro("700,0") == (700.0, 0.0) and _centro("650;-20") == (650.0, -20.0)
    with pytest.raises(argparse.ArgumentTypeError, match="x,y"):
        _centro("700")
