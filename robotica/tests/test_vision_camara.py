"""Modelo de cámara, tablero y detección de cajas con escenas sintéticas (verdad conocida)."""
import cv2
import numpy as np
import pytest

from nucleo.geometria import Pose
from vision.camara import ModeloCamara, intrinsecos_por_campo_de_vision
from vision.deteccion import PARAMS_POR_DEFECTO, detectar_cajas, dibujar, elegir
from vision.escena import CajaSintetica, camara_cenital, escena, profundidad
from vision.tablero import Tablero, detectar_esquinas, modelo_desde_tablero


# ---------------------------------------------------------------- modelo de cámara
def test_un_pixel_se_pasa_al_plano_y_de_vuelta_con_inclinacion_y_distorsion():
    cam = camara_cenital(altura_mm=700.0, centro_xy=(300.0, 40.0), inclinacion_deg=6.0, z_plano=220.0,
                         distorsion=[-0.12, 0.03, 0.0005, -0.0004, 0.0])
    puntos = np.array([[250.0, 10.0, 220.0], [380.0, 90.0, 220.0], [320.0, -30.0, 340.0]])
    px = cam.base_a_pixel(puntos)
    for p, z, esperado in zip(px, (220.0, 220.0, 340.0), puntos):
        assert np.allclose(cam.pixel_a_plano(p, z)[0], esperado[:2], atol=1e-3)


def test_el_plano_detras_de_la_camara_o_paralelo_no_se_mide():
    cam = camara_cenital(altura_mm=500.0, z_plano=0.0)
    with pytest.raises(ValueError, match="detrás de la cámara"):
        cam.pixel_a_plano([[640.0, 480.0]], 800.0)   # un plano por encima de la cámara


def test_la_calibracion_de_la_camara_se_guarda_y_se_lee_igual(tmp_path):
    cam = camara_cenital(altura_mm=650.0, centro_xy=(690.0, 5.0), inclinacion_deg=3.0, z_plano=220.0)
    con_info = ModeloCamara(cam.K, np.array([-0.1, 0.02, 0, 0, 0.0]), cam.T_base_cam, cam.tam, {"criterio": "objetivo", "rms_px": 0.3})
    con_info.guardar(tmp_path / "camara.json")
    otra = ModeloCamara.cargar(tmp_path / "camara.json")
    assert np.allclose(otra.K, con_info.K) and np.allclose(otra.dist, con_info.dist)
    assert np.allclose(otra.T_base_cam.t, con_info.T_base_cam.t) and np.allclose(otra.T_base_cam.matriz(), con_info.T_base_cam.matriz())
    assert otra.tam == con_info.tam and otra.info["criterio"] == "objetivo"


def test_una_calibracion_mal_formada_se_rechaza_con_el_motivo(tmp_path):
    (tmp_path / "mal.json").write_text('{"formato": "otro"}', encoding="utf-8")
    (tmp_path / "roto.json").write_text("{no es json", encoding="utf-8")
    with pytest.raises(ValueError, match="formato"):
        ModeloCamara.cargar(tmp_path / "mal.json")
    with pytest.raises(ValueError, match="JSON"):
        ModeloCamara.cargar(tmp_path / "roto.json")
    with pytest.raises(ValueError, match="no puedo leer"):
        ModeloCamara.cargar(tmp_path / "no_existe.json")
    cam = camara_cenital()
    d = cam.a_dict()
    del d["T_base_cam"]
    with pytest.raises(ValueError, match="incompleta"):
        ModeloCamara.desde_dict(d)


def test_k_aproximada_por_campo_de_vision():
    K = intrinsecos_por_campo_de_vision((1280, 960), 62.0)
    assert K[0, 0] == pytest.approx(640.0 / np.tan(np.radians(31.0)))
    assert (K[0, 2], K[1, 2]) == (640.0, 480.0)


# ---------------------------------------------------------------- tablero
def test_el_tablero_se_lee_de_texto_y_valida_sus_medidas():
    t = Tablero.desde_texto("9x6", 25.0)
    assert (t.columnas, t.filas, t.n_esquinas, t.origen_inequivoco) == (9, 6, 54, True)
    assert Tablero.desde_texto("8×6", 25.0).origen_inequivoco is False
    for mal in ("9", "axb", "9x"):
        with pytest.raises(ValueError, match="columnasxfilas"):
            Tablero.desde_texto(mal, 25.0)
    with pytest.raises(ValueError):
        Tablero(2, 6, 25.0)
    with pytest.raises(ValueError, match="no existe"):
        t.indice(9, 0)
    p = t.puntos_plano()
    assert p[0].tolist() == [0.0, 0.0] and p[t.indice(8, 0)].tolist() == [200.0, 0.0] and p[t.indice(0, 5)].tolist() == [0.0, -125.0]


def test_el_tablero_se_detecta_con_las_esquinas_en_orden_aunque_este_girado_en_la_imagen():
    tab = Tablero(9, 6, 25.0)
    cam = camara_cenital(tam=(960, 720), altura_mm=700.0, centro_xy=(100.0, -60.0))
    for giro in (20.0, 150.0, -170.0):   # incluso casi al revés: la fila 0 queda siempre arriba
        a = np.radians(giro)
        R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
        from nucleo.geometria import desde_matriz
        T = Pose.crear(t=[0.0, 0.0, 0.0], q=desde_matriz(R))
        img = escena(cam, tablero=tab, T_base_tablero=T)
        esq = detectar_esquinas(img, tab)
        assert esq is not None, giro
        verdad = cam.base_a_pixel(T.aplicar(np.hstack([tab.puntos_plano(), np.zeros((54, 1))])))
        # la detección puede salir en el orden de la imagen (fila 0 arriba) o en el del marco girado: se acepta el que coincide
        # con el del marco solo si el giro es menor de 90°; con giros mayores el marco real queda "al revés" en la imagen
        if abs(giro) < 90:
            assert np.abs(esq - verdad).max() < 1.0, giro
        else:
            assert np.abs(esq - verdad[::-1]).max() < 1.0, giro


def test_sin_tablero_no_hay_esquinas_ni_modelo():
    tab = Tablero(9, 6, 25.0)
    img = np.full((480, 640, 3), 128, np.uint8)
    assert detectar_esquinas(img, tab) is None
    assert modelo_desde_tablero(img, tab, intrinsecos_por_campo_de_vision((640, 480), 62.0), None) is None


def test_la_camara_se_recupera_respecto_al_tablero():
    tab = Tablero(9, 6, 25.0)
    cam = camara_cenital(altura_mm=700.0, centro_xy=(100.0, -60.0), inclinacion_deg=5.0)
    img = escena(cam, tablero=tab, T_base_tablero=Pose.crear(t=[0.0, 0.0, 0.0]), ruido=1.5, semilla=3)
    m = modelo_desde_tablero(img, tab, cam.K, None)
    assert np.allclose(m.posicion, cam.posicion, atol=1.0)
    assert m.info["rms_px"] < 0.5


# ---------------------------------------------------------------- detección de cajas
CAJAS = [
    CajaSintetica(200.0, 140.0, 120.0, 0.0, (20.0, -10.0)),
    CajaSintetica(200.0, 140.0, 120.0, 37.0, (-30.0, 25.0)),
    CajaSintetica(150.0, 90.0, 80.0, -62.0, (40.0, 20.0)),
    CajaSintetica(220.0, 120.0, 150.0, 85.0, (0.0, 0.0)),
]


@pytest.mark.parametrize("caja", CAJAS)
def test_la_caja_centrada_se_mide_con_color_dentro_de_3_mm_y_1_grado(caja):
    cam = camara_cenital(altura_mm=800.0)
    img = escena(cam, [caja], ruido=3.0, semilla=1)
    dets = detectar_cajas(img, cam, 0.0, alto_mm=caja.alto)
    assert len(dets) == 1
    d = dets[0]
    assert abs(d.largo - caja.largo) < 3.0 and abs(d.ancho - caja.ancho) < 3.0 and d.alto == caja.alto
    dg = ((d.giro_deg - caja.giro_deg + 90.0) % 180.0) - 90.0
    assert abs(dg) < 1.0
    assert np.hypot(d.centro[0] - caja.centro[0], d.centro[1] - caja.centro[1]) < 3.0
    assert d.confianza > 0.95 and not d.recortada
    assert d.largo >= d.ancho and -90.0 <= d.giro_deg < 90.0


def test_con_profundidad_se_mide_la_tapa_exacta_aunque_la_caja_este_lejos_del_eje():
    cam = camara_cenital(altura_mm=800.0, centro_xy=(0.0, 0.0))
    caja = CajaSintetica(200.0, 140.0, 120.0, 25.0, (250.0, 150.0))
    img = escena(cam, [caja])
    prof = profundidad(cam, [caja])
    color = detectar_cajas(img, cam, 0.0, alto_mm=120.0)[0]
    exacta = detectar_cajas(img, cam, 0.0, params={"modo": "profundidad"}, profundidad=prof)[0]
    # con color la pared que ve la cámara infla la medida (y el aviso lo estima); con profundidad no
    # (la estimación sale de la silueta ya inflada, así que se queda algo corta: vale como orden de magnitud)
    assert color.largo > caja.largo + 3.0 and 0 < abs(color.largo - caja.largo) <= 1.5 * color.pared_mm + 3.0
    assert abs(exacta.largo - caja.largo) < 1.0 and abs(exacta.ancho - caja.ancho) < 1.0 and abs(exacta.alto - caja.alto) < 1.5
    assert np.hypot(exacta.centro[0] - 250.0, exacta.centro[1] - 150.0) < 1.0
    assert exacta.pared_mm == 0.0 and color.pared_mm > 5.0


def test_con_profundidad_cada_caja_lleva_su_alto():
    cam = camara_cenital(altura_mm=800.0)
    cajas = [CajaSintetica(150.0, 100.0, 60.0, 0.0, (-150.0, 0.0)), CajaSintetica(150.0, 100.0, 140.0, 0.0, (150.0, 0.0))]
    dets = detectar_cajas(escena(cam, cajas), cam, 0.0, params={"modo": "profundidad"}, profundidad=profundidad(cam, cajas))
    assert sorted(round(d.alto) for d in dets) == [60, 140]


def test_el_modo_fondo_no_depende_del_color_de_la_caja():
    cam = camara_cenital(altura_mm=800.0)
    fondo = escena(cam, [])
    img = fondo.copy()
    caja = CajaSintetica(200.0, 140.0, 100.0, 15.0, (0.0, 0.0))
    esq = np.round(cam.base_a_pixel(caja.esquinas_base(100.0))).astype(np.int32)
    cv2.fillConvexPoly(img, esq, (200, 80, 20))   # una caja azul: el rango de color del cartón no la ve
    assert detectar_cajas(img, cam, 0.0, alto_mm=100.0) == []
    d = detectar_cajas(img, cam, 0.0, alto_mm=100.0, params={"modo": "fondo"}, fondo=fondo)[0]
    assert abs(d.largo - 200.0) < 3.0 and abs(d.ancho - 140.0) < 3.0


def test_sin_cajas_no_hay_detecciones_y_el_ruido_pequeno_se_descarta():
    cam = camara_cenital(altura_mm=800.0)
    img = escena(cam, [], ruido=4.0, semilla=2)
    assert detectar_cajas(img, cam, 0.0, alto_mm=100.0) == []
    pequena = CajaSintetica(12.0, 8.0, 10.0, 0.0, (0.0, 0.0))   # mancha de pocos píxeles
    assert detectar_cajas(escena(cam, [pequena]), cam, 0.0, alto_mm=10.0) == []


def test_una_caja_cortada_por_el_borde_se_marca_recortada_y_pierde_confianza():
    cam = camara_cenital(altura_mm=800.0)
    caja = CajaSintetica(200.0, 140.0, 100.0, 0.0, (480.0, 0.0))   # sale por el borde derecho de la imagen
    d = detectar_cajas(escena(cam, [caja]), cam, 0.0, alto_mm=100.0)[0]
    assert d.recortada and d.confianza < 0.5


def test_una_caja_cuadrada_lleva_el_giro_en_menos_de_45_grados():
    cam = camara_cenital(altura_mm=800.0)
    for giro in (60.0, -80.0, 80.0):
        caja = CajaSintetica(150.0, 150.0, 100.0, giro, (0.0, 0.0))
        d = detectar_cajas(escena(cam, [caja]), cam, 0.0, alto_mm=100.0)[0]
        assert -45.0 <= d.giro_deg < 45.0
        resto = ((d.giro_deg - giro + 45.0) % 90.0) - 45.0   # igual que el verdadero salvo múltiplos de 90
        assert abs(resto) < 1.5


def test_errores_de_uso_de_la_deteccion():
    cam = camara_cenital()
    img = escena(cam, [])
    with pytest.raises(ValueError, match="alto"):
        detectar_cajas(img, cam, 0.0)                                             # sin alto ni profundidad
    with pytest.raises(ValueError, match="profundidad"):
        detectar_cajas(img, cam, 0.0, params={"modo": "profundidad"})
    with pytest.raises(ValueError, match="fondo"):
        detectar_cajas(img, cam, 0.0, alto_mm=100.0, params={"modo": "fondo"})
    with pytest.raises(ValueError, match="desconocido"):
        detectar_cajas(img, cam, 0.0, alto_mm=100.0, params={"modo": "magia"})
    with pytest.raises(ValueError, match="alineada"):
        detectar_cajas(img, cam, 0.0, params={"modo": "profundidad"}, profundidad=np.zeros((10, 10), np.float32))
    assert PARAMS_POR_DEFECTO["modo"] == "color"


def test_se_elige_la_caja_mas_cercana_al_punto_de_recogida_o_la_mayor():
    cam = camara_cenital(altura_mm=800.0)
    cajas = [CajaSintetica(100.0, 80.0, 60.0, 0.0, (-150.0, 0.0)), CajaSintetica(200.0, 140.0, 60.0, 0.0, (160.0, 20.0))]
    dets = detectar_cajas(escena(cam, cajas), cam, 0.0, alto_mm=60.0)
    assert len(dets) == 2
    assert elegir(dets).largo > 150.0                              # la mayor
    assert elegir(dets, (-140.0, 0.0)).largo < 150.0               # la más cercana al punto
    assert elegir([], (0.0, 0.0)) is None


def test_la_imagen_anotada_marca_cada_caja():
    cam = camara_cenital(altura_mm=800.0)
    img = escena(cam, [CAJAS[1]])
    dets = detectar_cajas(img, cam, 0.0, alto_mm=120.0)
    anotada = dibujar(img, dets, dets[0])
    assert anotada.shape == img.shape and np.any(anotada != img)
    assert np.array_equal(dibujar(img, [], None), img)
