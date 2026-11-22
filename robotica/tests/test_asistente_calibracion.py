"""Asistente de calibracion de la camara (calibracion.asistente), con fotos sinteticas del tablero: intrinsecos, posicion en casa y con toques."""
import numpy as np
import pytest

from calibracion.asistente import Asistente, FOTOS_RECOMENDADAS
from nucleo.geometria import Pose, desde_matriz
from vision.camara import ModeloCamara
from vision.escena import camara_cenital, escena
from vision.tablero import Tablero

TABLERO = Tablero(9, 6, 25.0)
TAM = (1280, 960)
CAM_FOTOS = camara_cenital(tam=TAM, altura_mm=700.0, fov_horizontal_deg=62.0)


def _rot(inc, az, g):
    Rx = np.array([[1, 0, 0], [0, np.cos(inc), -np.sin(inc)], [0, np.sin(inc), np.cos(inc)]])
    Ry = np.array([[np.cos(az), 0, np.sin(az)], [0, 1, 0], [-np.sin(az), 0, np.cos(az)]])
    Rz = np.array([[np.cos(g), -np.sin(g), 0], [np.sin(g), np.cos(g), 0], [0, 0, 1]])
    return Rz @ Rx @ Ry


def fotos_tablero(n=12, semilla=2):
    """n fotos del tablero en posiciones, giros e inclinaciones distintas (la camara fija, el tablero se mueve)."""
    rng = np.random.default_rng(semilla)
    fotos = []
    for k in range(n):
        inc, az, g = (np.radians(rng.uniform(-35, 35)), np.radians(rng.uniform(-30, 30)), np.radians(rng.uniform(-35, 35)))
        T = Pose.crear(t=[rng.uniform(-160, -20), rng.uniform(-110, 40), rng.uniform(0, 60)], q=desde_matriz(_rot(inc, az, g)))
        fotos.append(escena(CAM_FOTOS, tablero=TABLERO, T_base_tablero=T, ruido=1.0, semilla=k))
    return fotos


def camara_de_la_celda():
    return camara_cenital(tam=TAM, altura_mm=650.0, centro_xy=(700.0, 0.0), fov_horizontal_deg=62.0, inclinacion_deg=2.0, z_plano=220.0)


def foto_del_tablero_en_la_cinta(centro, giro_deg, z=220.0, cam=None):
    """Foto de la camara de la celda con el tablero tendido sobre la cinta: su centro en `centro` de la base y girado `giro_deg`."""
    cam = cam or camara_de_la_celda()
    a = np.radians(giro_deg)
    R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    centro_uv = np.array([(TABLERO.columnas - 1) * TABLERO.cuadro_mm / 2.0, -(TABLERO.filas - 1) * TABLERO.cuadro_mm / 2.0])
    o = np.array(centro) - R @ centro_uv
    R3 = np.eye(3)
    R3[:2, :2] = R
    T = Pose.crear(t=[o[0], o[1], z], q=desde_matriz(R3))
    return escena(cam, tablero=TABLERO, T_base_tablero=T, z_plano=z, ruido=1.0, semilla=5)


@pytest.fixture(scope="module")
def fotos():
    return fotos_tablero(12)


def test_cambiar_el_tablero_borra_las_fotos_y_avisa_si_el_origen_es_ambiguo(fotos):
    a = Asistente()
    assert a.guardar_foto(fotos[0])[0] and a.n_fotos == 1
    a.configurar_tablero(9, 6, 25.0)
    assert a.n_fotos == 1                                                  # el mismo tablero: se conservan
    a.configurar_tablero(7, 4, 30.0)
    assert a.n_fotos == 0 and a.tablero == Tablero(7, 4, 30.0)
    assert a.aviso_tablero == ""
    a.configurar_tablero(9, 7, 25.0)
    assert "ambiguo" in a.aviso_tablero                                    # cuentas las dos impares: el tablero puede salir girado 180 grados
    with pytest.raises(ValueError):
        a.configurar_tablero(2, 6, 25.0)


def test_guardar_foto_rechaza_sin_tablero_casi_repetidas_y_cambio_de_resolucion(fotos):
    a = Asistente()
    ok, motivo = a.guardar_foto(np.full((TAM[1], TAM[0], 3), 120, np.uint8))
    assert not ok and "no veo el tablero entero" in motivo
    assert a.guardar_foto(fotos[0]) == (True, "foto 1 guardada")
    ok, motivo = a.guardar_foto(fotos[0])
    assert not ok and "casi igual" in motivo and a.n_fotos == 1
    assert a.guardar_foto(fotos[1])[0] and a.n_fotos == 2
    ok, motivo = a.guardar_foto(np.zeros((480, 640, 3), np.uint8) + 120)
    assert not ok                                                         # sin tablero: antes que lo de la resolucion
    assert a.quitar_ultima() is True and a.n_fotos == 1
    a.borrar_fotos()
    assert a.n_fotos == 0 and a.quitar_ultima() is False


def test_el_resumen_dice_que_falta_y_las_9_zonas_de_la_imagen_se_cuentan(fotos):
    a = Asistente()
    assert "faltan al menos 8" in a.resumen().consejo
    for f in fotos[:3]:
        assert a.guardar_foto(f)[0]
    r = a.resumen()
    assert r.n == 3 and r.recomendadas == FOTOS_RECOMENDADAS and "faltan al menos 5" in r.consejo and 1 <= r.celdas_cubiertas <= 9
    for f in fotos[3:]:
        a.guardar_foto(f)
    r = a.resumen()
    assert r.n == 12 and "faltan" not in r.consejo and r.inclinadas >= 3


def test_la_deteccion_rapida_ve_el_tablero_en_la_imagen_entera_y_no_inventa_nada(fotos):
    from vision.tablero import detectar_esquinas
    a = Asistente()
    rapidas = a.esquinas_rapidas(fotos[0])
    precisas = detectar_esquinas(fotos[0], TABLERO)
    assert rapidas is not None and rapidas.shape == (54, 2)
    assert float(np.mean(np.linalg.norm(rapidas - precisas, axis=1))) < 4.0   # en la imagen entera, aunque algo menos precisa
    assert a.esquinas_rapidas(np.full((TAM[1], TAM[0], 3), 120, np.uint8)) is None


def test_los_intrinsecos_salen_de_las_fotos_guardadas_y_se_parecen_a_los_reales(fotos):
    a = Asistente()
    with pytest.raises(ValueError, match="no hay fotos"):
        a.calcular_intrinsecos()
    for f in fotos:
        a.guardar_foto(f)
    inf = a.calcular_intrinsecos()
    assert inf.rms_px < 1.0 and inf.n_usadas >= 8 and a.origen_intrinsecos == "fotos" and a.tam == TAM
    f_real = CAM_FOTOS.K[0, 0]
    assert a.K[0, 0] == pytest.approx(f_real, rel=0.03) and a.K[1, 1] == pytest.approx(f_real, rel=0.03)
    assert a.K[0, 2] == pytest.approx(TAM[0] / 2, abs=15) and a.K[1, 2] == pytest.approx(TAM[1] / 2, abs=15)
    assert Asistente.veredicto_intrinsecos(0.3) == "muy bien" and Asistente.veredicto_intrinsecos(0.8) == "aceptable"
    assert "repite" in Asistente.veredicto_intrinsecos(1.5)


def test_pocas_fotos_dan_un_error_claro():
    a = Asistente()
    for f in fotos_tablero(3, semilla=9):
        a.guardar_foto(f)
    with pytest.raises(ValueError, match="hacen falta al menos 8"):
        a.calcular_intrinsecos()


def test_los_toques_de_mentira_respetan_la_geometria_del_tablero_y_el_giro():
    a = Asistente()
    toques, valida = a.toques_en_casa(700.0, 0.0, 0.0)
    assert [(t.columna, t.fila) for t in toques] == [(0, 0), (8, 0), (0, 5)] and [(t.columna, t.fila) for t in valida] == [(8, 5), (4, 3)]
    p00, p80, p05 = (np.array([t.x, t.y]) for t in toques)
    assert np.linalg.norm(p80 - p00) == pytest.approx(8 * 25.0) and np.linalg.norm(p05 - p00) == pytest.approx(5 * 25.0)
    assert (p80 - p00)[0] > 0 and (p80 - p00)[1] == pytest.approx(0.0, abs=1e-9)          # derecho: las columnas van hacia +x
    assert (p05 - p00)[1] < 0 and (p05 - p00)[0] == pytest.approx(0.0, abs=1e-9)          # y las filas hacia abajo, -y
    assert np.mean([p00, p80, p05, np.array([valida[0].x, valida[0].y])], axis=0) == pytest.approx([700.0, 0.0], abs=1e-9)   # el centro es el pedido
    girados, _ = a.toques_en_casa(700.0, 0.0, 90.0)
    q00, q80 = np.array([girados[0].x, girados[0].y]), np.array([girados[1].x, girados[1].y])
    assert (q80 - q00)[1] > 0 and (q80 - q00)[0] == pytest.approx(0.0, abs=1e-9)          # girado 90 grados: las columnas van hacia +y


@pytest.mark.parametrize("giro", [0.0, 30.0, -20.0])
def test_la_posicion_de_la_camara_en_casa_sale_bien_con_los_intrinsecos_de_las_fotos(fotos, giro):
    a = Asistente()
    for f in fotos:
        a.guardar_foto(f)
    a.calcular_intrinsecos()
    cam = camara_de_la_celda()
    img = foto_del_tablero_en_la_cinta((700.0, 0.0), giro)
    toques, valida = a.toques_en_casa(700.0, 0.0, giro)
    modelo, informe = a.calcular_posicion(img, 220.0, toques, valida)
    assert informe.criterio in ("objetivo", "aceptable") and informe.rms_validacion_mm < 3.0
    # una esquina del tablero (la (8,5)) vista por la camara calibrada cae donde esta en la base, con unos mm de error
    esq = a.esquinas_rapidas(img)
    uv = TABLERO.puntos_plano()[TABLERO.indice(8, 5)]
    pred = modelo.pixel_a_plano(esq[TABLERO.indice(8, 5)].reshape(1, 2), 220.0)[0]
    verdad = np.array([valida[0].x, valida[0].y])
    assert np.linalg.norm(pred - verdad) < 3.0
    assert uv is not None and cam is not None


def test_con_el_campo_de_vision_basta_y_la_camara_queda_sobre_la_recogida():
    a = Asistente()
    a.usar_campo_de_vision(TAM, 62.0)
    assert a.origen_intrinsecos.startswith("campo de visión") and a.informe_intrinsecos is None
    img = foto_del_tablero_en_la_cinta((700.0, 0.0), 0.0)
    toques, valida = a.toques_en_casa(700.0, 0.0, 0.0)
    modelo, informe = a.calcular_posicion(img, 220.0, toques, valida)
    cam = camara_de_la_celda()
    # la camara de la prueba esta en (700, 0, 870) con 2 grados de inclinacion; con el centro del tablero en la recogida, la estimacion se le acerca
    assert modelo.posicion[2] == pytest.approx(cam.posicion[2], abs=15.0)
    assert informe.criterio in ("objetivo", "aceptable")


def test_errores_claros_sin_intrinsecos_o_con_otra_resolucion():
    a = Asistente()
    toques, valida = a.toques_en_casa(700.0, 0.0)
    with pytest.raises(ValueError, match="primero los intrínsecos"):
        a.calcular_posicion(foto_del_tablero_en_la_cinta((700.0, 0.0), 0.0), 220.0, toques, valida)
    a.usar_campo_de_vision((640, 480), 62.0)
    with pytest.raises(ValueError, match="usa la misma resolución"):
        a.calcular_posicion(foto_del_tablero_en_la_cinta((700.0, 0.0), 0.0), 220.0, toques, valida)
    a.usar_campo_de_vision(TAM, 62.0)
    with pytest.raises(ValueError, match="no veo el tablero"):
        a.calcular_posicion(np.full((TAM[1], TAM[0], 3), 120, np.uint8), 220.0, toques, valida)


def test_guardar_deja_un_camara_json_que_carga_y_dice_de_donde_salen_los_intrinsecos(tmp_path, fotos):
    a = Asistente()
    with pytest.raises(ValueError, match="todavía no hay calibración"):
        a.guardar(tmp_path / "camara.json")
    for f in fotos:
        a.guardar_foto(f)
    a.calcular_intrinsecos()
    toques, valida = a.toques_en_casa(700.0, 0.0, 0.0)
    a.calcular_posicion(foto_del_tablero_en_la_cinta((700.0, 0.0), 0.0), 220.0, toques, valida)
    ruta = a.guardar(tmp_path / "sub" / "camara.json")
    m = ModeloCamara.cargar(ruta)
    assert m.tam == TAM and m.info["intrinsecos"] == "fotos" and m.info["rms_intrinsecos_px"] < 1.0 and m.info["z_plano_mm"] == 220.0
    assert m.info["criterio"] in ("objetivo", "aceptable")
    # y mide: una caja a 100 mm sobre la cinta, vista con esa calibracion, sale donde esta
    from vision.deteccion import detectar_cajas
    from vision.escena import CajaSintetica
    cam = camara_de_la_celda()
    img = escena(cam, [CajaSintetica(200.0, 140.0, 100.0, 20.0, (730.0, 30.0))], z_plano=220.0)
    d = detectar_cajas(img, m, 220.0, 100.0, {"modo": "color"})[0]
    assert d.centro == pytest.approx((730.0, 30.0), abs=6.0) and d.largo == pytest.approx(200.0, rel=0.04)


def test_se_reutilizan_los_intrinsecos_de_un_camara_json_y_basta_repetir_la_posicion(tmp_path, fotos):
    a = Asistente()
    for f in fotos:
        a.guardar_foto(f)
    a.calcular_intrinsecos()
    toques, valida = a.toques_en_casa(700.0, 0.0, 0.0)
    a.calcular_posicion(foto_del_tablero_en_la_cinta((700.0, 0.0), 0.0), 220.0, toques, valida)
    anterior = a.guardar(tmp_path / "anterior.json")
    b = Asistente()
    with pytest.raises(ValueError, match="no puedo leer"):
        b.usar_intrinsecos_de(tmp_path / "no_existe.json")
    b.usar_intrinsecos_de(anterior)
    assert b.tam == TAM and b.origen_intrinsecos == "los de anterior.json" and np.allclose(b.K, a.K)
    t2, v2 = b.toques_en_casa(700.0, 0.0, 30.0)
    _, informe = b.calcular_posicion(foto_del_tablero_en_la_cinta((700.0, 0.0), 30.0), 220.0, t2, v2)
    assert informe.criterio in ("objetivo", "aceptable")
    assert ModeloCamara.cargar(b.guardar(tmp_path / "nueva.json")).info["intrinsecos"] == "los de anterior.json"
