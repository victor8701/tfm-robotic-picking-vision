"""El móvil como cámara por la página propia (movil_camara) y su lado del PC (vision.proveedores.CamaraMovil), con un teléfono de mentira."""
import http.client
import json
import socket
import threading
import time
import urllib.error
import urllib.request

import cv2
import numpy as np
import pytest

from celda.percepcion import FuenteCamara
from movil_camara import servidor as S
from vision import proveedores as P
from vision.escena import CajaSintetica, camara_cenital, escena
from vision.ver_camara import main as ver_camara

CLAVE = "clave-de-prueba-1"


@pytest.fixture
def servidor():
    s = S.Servidor(("127.0.0.1", 0), CLAVE)
    threading.Thread(target=s.serve_forever, args=(0.05,), daemon=True).start()
    yield s
    s.shutdown()
    s.server_close()


def _url(s, clave=CLAVE):
    return f"http://127.0.0.1:{s.server_address[1]}/c/{clave}"


def _jpg(bgr):
    return cv2.imencode(".jpg", bgr)[1].tobytes()


def _gris(valor):
    return _jpg(np.full((90, 160, 3), valor, np.uint8))


def _pedir(url, datos=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=datos), timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class Movil:
    """Un teléfono de mentira: sube sin parar las fotos que le dé `foto(i)`."""

    def __init__(self, url, foto=lambda i: _gris(i % 250), cada=0.05):
        self.url, self.foto, self.cada = url, foto, cada
        self.respuestas = []
        self._parar = threading.Event()
        self._hilo = threading.Thread(target=self._bucle, daemon=True)

    def _bucle(self):
        i = 0
        while not self._parar.is_set():
            codigo, cuerpo = _pedir(self.url + "/foto", self.foto(i))
            assert codigo == 200
            self.respuestas.append(json.loads(cuerpo))
            i += 1
            self._parar.wait(self.cada)

    def __enter__(self):
        self._hilo.start()
        return self

    def __exit__(self, *_):
        self._parar.set()
        self._hilo.join(5.0)


# ---------------------------------------------------------------- servidor
@pytest.mark.parametrize("clave", ["", "corta", "con espacio y larga", "con/barra/larga", "con#almohadilla", "con?pregunta", "con%porciento",
                                   "con'comilla-larga", 'con"comillas-dobles', "con\\barra-inversa", "con-eñe-larga"])
def test_sin_una_clave_larga_no_arranca(clave):
    with pytest.raises(ValueError, match="CLAVE"):
        S.Servidor(("127.0.0.1", 0), clave)


def test_main_sin_clave_lo_dice_y_acaba(capsys):
    assert S.main({"PORT": "0"}) == 2
    assert "CLAVE" in capsys.readouterr().err


def test_la_pagina_solo_sale_con_la_clave(servidor):
    base = f"http://127.0.0.1:{servidor.server_address[1]}"
    for ruta in (f"/c/{CLAVE}", f"/c/{CLAVE}/"):
        codigo, cuerpo = _pedir(base + ruta)
        assert codigo == 200 and "Encender la cámara" in cuerpo.decode()
    assert _pedir(base + "/")[0] == 200                                   # para saber que está en marcha
    for ruta in ("/c/otra-clave-larga", "/c/otra-clave-larga/ultima", f"/c/{CLAVE}/nada", "/c", f"/x/{CLAVE}"):
        codigo, cuerpo = _pedir(base + ruta)
        assert codigo == 404 and CLAVE.encode() not in cuerpo


def test_la_clave_puede_llevar_signos():
    clave = "Prueba$&!12.+"
    s = S.Servidor(("127.0.0.1", 0), clave)
    threading.Thread(target=s.serve_forever, args=(0.05,), daemon=True).start()
    try:
        base = f"http://127.0.0.1:{s.server_address[1]}/c/"
        for escrita in (clave, "Prueba%24%26%2112.%2B"):          # tal cual o como la codifique el navegador
            assert _pedir(base + escrita)[0] == 200
        assert _pedir(base + "Prueba")[0] == 404
        with Movil(base + clave):
            cam = P.abrir_camara_usb(url=base + clave)
            assert cam.siguiente() is not None
            cam.cerrar()
    finally:
        s.shutdown()
        s.server_close()


def test_solo_acepta_fotos_jpeg_con_la_clave(servidor):
    assert _pedir(_url(servidor) + "/foto", b"esto no es una foto")[0] == 400
    assert _pedir(_url(servidor, "otra-clave-larga") + "/foto", _gris(1))[0] == 404
    con = http.client.HTTPConnection("127.0.0.1", servidor.server_address[1], timeout=5)
    con.putrequest("POST", f"/c/{CLAVE}/foto")
    con.putheader("Content-Length", str(S.MAX_BYTES + 1))
    con.endheaders()
    assert con.getresponse().status == 413
    con.close()
    assert servidor.buzon.estado()["fotos"] == 0
    codigo, cuerpo = _pedir(_url(servidor) + "/foto", _gris(1))
    assert codigo == 200 and json.loads(cuerpo) == {"fotos": 1, "pc": False}


def test_nunca_da_una_foto_anterior_a_la_peticion(servidor):
    _pedir(_url(servidor) + "/foto", _gris(10))
    _pedir(_url(servidor) + "/foto", _gris(20))
    assert _pedir(_url(servidor) + "/ultima?espera=0.3") == (204, b"")    # hay foto, pero es vieja
    resultado = []
    hilo = threading.Thread(target=lambda: resultado.append(_pedir(_url(servidor) + "/ultima?espera=5")))
    hilo.start()
    time.sleep(0.2)
    _pedir(_url(servidor) + "/foto", _gris(100))     # pudo hacerse antes de pedirla: todavía no vale
    time.sleep(0.2)
    assert not resultado
    codigo, cuerpo = _pedir(_url(servidor) + "/foto", _gris(200))
    assert json.loads(cuerpo)["pc"] is True          # el móvil se entera de que el PC está mirando
    hilo.join(5.0)
    codigo, foto = resultado[0]
    assert codigo == 200
    assert abs(int(cv2.imdecode(np.frombuffer(foto, np.uint8), cv2.IMREAD_COLOR)[0, 0, 0]) - 200) <= 3


def test_espera_mal_escrita(servidor):
    assert _pedir(_url(servidor) + "/ultima?espera=mucho")[0] == 400


# ---------------------------------------------------------------- el PC
@pytest.mark.parametrize("url, es", [("https://celda.onrender.com/c/abc12345", True), ("http://127.0.0.1:8000/c/abc12345/", True),
                                     ("http://192.168.1.50:8080/video", False), ("rtsp://192.168.1.50/c/abc", False),
                                     ("https://celda.onrender.com/c/", False)])
def test_distingue_la_pagina_del_video_de_una_aplicacion(url, es):
    assert P.es_pagina_del_movil(url) is es


def test_abrir_con_la_direccion_de_la_pagina_usa_la_camara_del_movil(servidor):
    with Movil(_url(servidor)):
        cam = P.abrir_proveedor({"tipo": "opencv", "url": _url(servidor)})
        try:
            assert isinstance(cam, P.CamaraMovil) and cam.indice is None
            a, b = cam.siguiente(), cam.siguiente()
            assert a.bgr.shape == (90, 160, 3) and a.profundidad is None
            assert int(b.bgr[0, 0, 0]) > int(a.bgr[0, 0, 0])               # cada vez, una foto más nueva
            assert cam.motivo is None
        finally:
            cam.cerrar()


def test_no_baja_mas_de_una_foto_por_intervalo(servidor):
    with Movil(_url(servidor)):
        t = time.monotonic()
        cam = P.CamaraMovil(_url(servidor), intervalo_s=0.4)             # abrir ya pide una foto: con estas dos, tres peticiones
        assert cam.siguiente() is not None and cam.siguiente() is not None
        assert time.monotonic() - t >= 0.8
        cam.cerrar()


def test_si_el_movil_no_envia_no_abre_y_dice_que_hacer(servidor):
    with pytest.raises(ValueError, match="no está enviando fotos.*Abre en el móvil"):
        P.CamaraMovil(_url(servidor), espera_s=0.2, espera_movil_s=0.3)


def test_si_el_movil_se_para_no_repite_la_ultima_foto(servidor):
    with Movil(_url(servidor)):
        cam = P.CamaraMovil(_url(servidor), espera_s=0.5)
    assert cam.siguiente() is None
    assert "no está enviando fotos" in cam.motivo
    cam.cerrar()


def test_clave_equivocada(servidor):
    with pytest.raises(ValueError, match="CLAVE"):
        P.CamaraMovil(_url(servidor, "otra-clave-larga"))


def test_sin_servidor():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    with pytest.raises(ValueError, match="no puedo conectar"):
        P.CamaraMovil(f"http://127.0.0.1:{puerto}/c/{CLAVE}", arranque_s=0.3)


def test_si_se_corta_la_conexion_abre_otra(servidor):
    with Movil(_url(servidor)):
        cam = P.CamaraMovil(_url(servidor))
        cam._conexion.sock.shutdown(socket.SHUT_RDWR)
        assert cam.siguiente() is not None
        cam.cerrar()
        assert cam.siguiente() is not None


def test_la_celda_mide_una_caja_vista_por_el_movil(servidor):
    modelo = camara_cenital(tam=(960, 720), altura_mm=650.0, centro_xy=(700.0, 0.0), z_plano=220.0)
    foto = _jpg(escena(modelo, [CajaSintetica(200.0, 140.0, 100.0, 25.0, (700.0, 20.0))], z_plano=220.0))
    with Movil(_url(servidor), lambda i: foto):
        cam = P.CamaraMovil(_url(servidor))
        fuente = FuenteCamara(cam, modelo, 220.0, alto_mm=100.0, params={"modo": "color"})
        caja = fuente.leer(0)
        assert fuente.origen() == "camara del movil (URL)"
        cam.cerrar()
    assert caja.largo == pytest.approx(200.0, abs=6) and caja.ancho == pytest.approx(140.0, abs=6)


def test_ver_camara_con_la_pagina(servidor, capsys):
    foto = _jpg(escena(camara_cenital(tam=(960, 720), altura_mm=600.0), [CajaSintetica(200.0, 140.0, 100.0, 0.0, (0.0, 0.0))]))
    with Movil(_url(servidor), lambda i: foto):
        assert ver_camara(["--url", _url(servidor), "--sin-ventana", "--segundos", "0.5"]) == 0
    assert "Cámara abierta" in capsys.readouterr().out
