"""Programa de calibración de la cámara (intrínsecos y pose en la base) con fotos sintéticas de verdad conocida."""
import json

import cv2
import numpy as np
import pytest

from calibracion.camara import (Toque, anotar_tablero, calibrar_extrinsecos, calibrar_intrinsecos, cargar_intrinsecos, guardar_intrinsecos,
                                imagen_tablero, main)
from nucleo.geometria import Pose, desde_matriz
from vision.camara import ModeloCamara
from vision.escena import camara_cenital, escena
from vision.tablero import Tablero

TAB = Tablero(9, 6, 25.0)
Z_CINTA = 220.0


def _giro_z(grados):
    a = np.radians(grados)
    return np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])


TAM = (960, 720)   # más pequeña que la de la celda para que las pruebas vayan deprisa


def _fotos_intrinsecos(n=12):
    """Una cámara fija que ve el tablero en n posiciones e inclinaciones distintas."""
    real = camara_cenital(tam=TAM, altura_mm=700.0, fov_horizontal_deg=62.0)
    rng = np.random.default_rng(2)
    fotos = {}
    for i in range(n):
        inc, az = np.radians(rng.uniform(-35, 35)), np.radians(rng.uniform(-30, 30))
        Rx = np.array([[1, 0, 0], [0, np.cos(inc), -np.sin(inc)], [0, np.sin(inc), np.cos(inc)]])
        Ry = np.array([[np.cos(az), 0, np.sin(az)], [0, 1, 0], [-np.sin(az), 0, np.cos(az)]])
        T = Pose.crear(t=[rng.uniform(-160, -60), rng.uniform(-110, -30), rng.uniform(0, 60)], q=desde_matriz(_giro_z(rng.uniform(-35, 35)) @ Rx @ Ry))
        fotos[f"f{i:02d}.png"] = escena(real, tablero=TAB, T_base_tablero=T, ruido=1.0, semilla=i)
    return real, fotos


@pytest.fixture(scope="module")
def intrinsecos():
    real, fotos = _fotos_intrinsecos()
    return real, fotos, calibrar_intrinsecos(fotos, TAB)


def test_los_intrinsecos_se_recuperan_con_poco_error(intrinsecos):
    real, fotos, inf = intrinsecos
    assert inf.n_usadas >= 12 and inf.rms_px < 0.3
    assert abs(inf.K[0, 0] - real.K[0, 0]) / real.K[0, 0] < 0.01
    assert np.allclose(inf.K[:2, 2], real.K[:2, 2], atol=3.0)
    assert inf.tam == TAM and max(inf.rms_por_imagen.values()) < 0.5


def test_los_intrinsecos_se_guardan_y_se_leen(intrinsecos, tmp_path):
    _, _, inf = intrinsecos
    guardar_intrinsecos(inf, tmp_path / "i.json")
    K, dist, tam = cargar_intrinsecos(tmp_path / "i.json")
    assert np.allclose(K, inf.K) and np.allclose(dist, inf.dist) and tam == inf.tam
    (tmp_path / "otro.json").write_text(json.dumps({"formato": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="formato"):
        cargar_intrinsecos(tmp_path / "otro.json")


def test_con_pocas_fotos_o_de_distinto_tamano_no_se_calibra(intrinsecos):
    _, fotos, _ = intrinsecos
    pocas = dict(list(fotos.items())[:5])
    with pytest.raises(ValueError, match="al menos 8"):
        calibrar_intrinsecos(pocas, TAB)
    mezcla = dict(list(fotos.items())[:9])
    mezcla["pequena.png"] = cv2.resize(next(iter(fotos.values())), (480, 360))
    with pytest.raises(ValueError, match="misma cámara y resolución"):
        calibrar_intrinsecos(mezcla, TAB)
    con_vacia = dict(list(fotos.items())[:10])
    con_vacia["vacia.png"] = np.full((TAM[1], TAM[0], 3), 128, np.uint8)
    inf = calibrar_intrinsecos(con_vacia, TAB)
    assert inf.descartadas == ["vacia.png"] and inf.n_usadas == 10   # la foto sin tablero se descarta y se dice


# ---------------------------------------------------------------- extrínsecos
def _escena_cinta(inclinacion=3.0, ruido=1.0):
    """Cámara fija a 650 mm sobre la cinta y el tablero tendido en ella, girado 15°, con la esquina (0, 0) en (600, -120)."""
    T_bt = Pose.crear(t=[600.0, -120.0, Z_CINTA], q=desde_matriz(_giro_z(15.0)))
    cam = camara_cenital(tam=TAM, altura_mm=650.0, centro_xy=(680.0, 0.0), inclinacion_deg=inclinacion, z_plano=Z_CINTA)
    return cam, T_bt, escena(cam, tablero=TAB, T_base_tablero=T_bt, z_plano=Z_CINTA, ruido=ruido)


def _toque(T_bt, c, f, ruido=0.0):
    uv = TAB.puntos_plano()[TAB.indice(c, f)]
    p = T_bt.aplicar(np.array([[uv[0], uv[1], 0.0]]))[0]
    return Toque(c, f, float(p[0] + ruido), float(p[1]))


def test_la_camara_se_coloca_en_la_base_con_tres_toques_y_se_valida(intrinsecos):
    _, _, inf = intrinsecos
    cam, T_bt, img = _escena_cinta()
    toques = [_toque(T_bt, 0, 0, 0.3), _toque(T_bt, 8, 0, -0.4), _toque(T_bt, 0, 5, 0.2)]
    modelo, informe = calibrar_extrinsecos(img, inf.K, inf.dist, TAB, toques, Z_CINTA, [_toque(T_bt, 8, 5), _toque(T_bt, 4, 2)])
    assert np.allclose(modelo.posicion, cam.posicion, atol=1.5)
    assert informe.criterio == "objetivo" and informe.rms_validacion_mm < 1.0 and informe.rms_px < 0.5 and informe.avisos == []
    # con la calibración, un punto de la cinta se mide donde está
    caja_px = cam.base_a_pixel(np.array([[700.0, 10.0, Z_CINTA + 100.0]]))
    assert np.allclose(modelo.pixel_a_plano(caja_px, Z_CINTA + 100.0)[0], [700.0, 10.0], atol=1.0)
    assert modelo.info["criterio"] == "objetivo" and modelo.info["z_plano_mm"] == Z_CINTA


def test_dos_toques_bastan_pero_sin_validar_el_programa_avisa(intrinsecos):
    _, _, inf = intrinsecos
    cam, T_bt, img = _escena_cinta()
    modelo, informe = calibrar_extrinsecos(img, inf.K, inf.dist, TAB, [_toque(T_bt, 0, 0), _toque(T_bt, 8, 5)], Z_CINTA)
    assert np.allclose(modelo.posicion, cam.posicion, atol=1.5)
    assert informe.rms_validacion_mm is None and any("validación" in a for a in informe.avisos)


def test_un_toque_mal_medido_no_pasa_la_validacion(intrinsecos):
    _, _, inf = intrinsecos
    _, T_bt, img = _escena_cinta()
    toques = [_toque(T_bt, 0, 0), _toque(T_bt, 8, 0, 14.0), _toque(T_bt, 0, 5)]   # uno mide 14 mm de más
    _, informe = calibrar_extrinsecos(img, inf.K, inf.dist, TAB, toques, Z_CINTA, [_toque(T_bt, 8, 5), _toque(T_bt, 4, 2)])
    assert informe.criterio == "repetir" and informe.rms_validacion_mm > 5.0


def test_con_los_indices_cruzados_el_programa_lo_nota(intrinsecos):
    _, _, inf = intrinsecos
    _, T_bt, img = _escena_cinta()

    def con_indices(c_dado, f_dado, c_real, f_real):
        """Las coordenadas de la esquina (c_real, f_real) dadas con el índice (c_dado, f_dado): un índice mal puesto."""
        real = _toque(T_bt, c_real, f_real)
        return Toque(c_dado, f_dado, real.x, real.y)

    # las filas 0 y 5 intercambiadas (el tablero visto al revés)
    toques = [con_indices(0, 0, 0, 5), con_indices(8, 0, 8, 5), con_indices(0, 5, 0, 0), con_indices(8, 5, 8, 0)]
    _, informe = calibrar_extrinsecos(img, inf.K, inf.dist, TAB, toques, Z_CINTA)
    assert informe.criterio == "repetir" and any("reflejado" in a for a in informe.avisos)


def test_datos_incorrectos_de_extrinsecos(intrinsecos):
    _, _, inf = intrinsecos
    _, T_bt, img = _escena_cinta()
    dos = [_toque(T_bt, 0, 0), _toque(T_bt, 8, 0)]
    with pytest.raises(ValueError, match="al menos 2"):
        calibrar_extrinsecos(img, inf.K, inf.dist, TAB, dos[:1], Z_CINTA)
    with pytest.raises(ValueError, match="ambiguo"):
        calibrar_extrinsecos(img, inf.K, inf.dist, Tablero(8, 6, 25.0), dos, Z_CINTA)
    with pytest.raises(ValueError, match="no veo el tablero"):
        calibrar_extrinsecos(np.full((TAM[1], TAM[0], 3), 100, np.uint8), inf.K, inf.dist, TAB, dos, Z_CINTA)
    with pytest.raises(ValueError, match="no existe"):
        calibrar_extrinsecos(img, inf.K, inf.dist, TAB, [dos[0], Toque(20, 0, 1.0, 2.0)], Z_CINTA)


def test_un_punto_se_lee_de_texto():
    assert Toque.desde_texto("8,0:700,100.5") == Toque(8, 0, 700.0, 100.5)
    for mal in ("8,0", "8:700,100", "a,0:1,2", "8,0:700"):
        with pytest.raises(ValueError, match="COLUMNA,FILA:X,Y"):
            Toque.desde_texto(mal)


def test_la_foto_anotada_marca_las_esquinas_y_avisa_si_no_hay_tablero():
    _, _, img = _escena_cinta()
    anotada = anotar_tablero(img, TAB)
    assert np.any(anotada != img)
    vacia = np.full((200, 300, 3), 90, np.uint8)
    assert np.any(anotar_tablero(vacia, TAB) != vacia)


def test_el_tablero_para_imprimir_tiene_los_cuadros_a_escala():
    img = imagen_tablero(TAB, dpi=254, margen_mm=10.0)    # 10 puntos por mm
    px_mm = 10.0
    ancho_cuadros = (img.shape[1] - 2 * 10 * px_mm) / (TAB.columnas + 1)
    assert ancho_cuadros == pytest.approx(25.0 * px_mm, abs=1.0)
    # se detecta como tablero
    from vision.tablero import detectar_esquinas
    assert detectar_esquinas(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), TAB) is not None


# ---------------------------------------------------------------- línea de comandos
def test_el_programa_completo_por_linea_de_comandos(tmp_path, capsys, intrinsecos):
    real, fotos, _ = intrinsecos
    carpeta = tmp_path / "fotos"
    carpeta.mkdir()
    for n, f in fotos.items():
        cv2.imwrite(str(carpeta / n), f)
    assert main(["tablero", "--columnas", "9", "--filas", "6", "--cuadro", "25", "--salida", str(tmp_path / "tablero.png")]) == 0
    assert (tmp_path / "tablero.png").is_file()
    assert main(["intrinsecos", str(carpeta), "--tablero", "9x6", "--cuadro", "25", "--salida", str(tmp_path / "intr.json")]) == 0
    assert "error de reproyección" in capsys.readouterr().out

    cam, T_bt, img = _escena_cinta()
    cv2.imwrite(str(tmp_path / "cinta.png"), img)
    pt = lambda c, f: f"{c},{f}:{_toque(T_bt, c, f).x:.2f},{_toque(T_bt, c, f).y:.2f}"  # noqa: E731
    args = ["extrinsecos", str(tmp_path / "cinta.png"), "--intrinsecos", str(tmp_path / "intr.json"), "--tablero", "9x6", "--cuadro", "25",
            "--z", str(Z_CINTA), "--toca", pt(0, 0), "--toca", pt(8, 0), "--toca", pt(0, 5), "--valida", pt(8, 5),
            "--salida", str(tmp_path / "camara.json"), "--anotada", str(tmp_path / "tablero_detectado.png")]
    assert main(args) == 0
    salida = capsys.readouterr().out
    assert "criterio: objetivo" in salida and "VALIDACIÓN" in salida
    modelo = ModeloCamara.cargar(tmp_path / "camara.json")
    assert np.allclose(modelo.posicion, cam.posicion, atol=2.0)
    assert (tmp_path / "tablero_detectado.png").is_file()


def test_la_linea_de_comandos_devuelve_2_con_datos_incorrectos_y_1_si_hay_que_repetir(tmp_path, capsys, intrinsecos):
    cam, T_bt, img = _escena_cinta()
    cv2.imwrite(str(tmp_path / "cinta.png"), img)
    # sin intrínsecos ni --fov
    assert main(["extrinsecos", str(tmp_path / "cinta.png"), "--cuadro", "25", "--z", "220", "--toca", "0,0:1,2", "--toca", "8,0:3,4"]) == 2
    assert "falta --intrinsecos" in capsys.readouterr().err
    # foto que no existe
    assert main(["extrinsecos", str(tmp_path / "nada.png"), "--fov", "62", "--cuadro", "25", "--z", "220", "--toca", "0,0:1,2", "--toca", "8,0:3,4"]) == 2
    # con el campo de visión exacto de la cámara de la escena y un toque mal medido: repetir
    pt = lambda c, f, e=0.0: f"{c},{f}:{_toque(T_bt, c, f).x + e:.2f},{_toque(T_bt, c, f).y:.2f}"  # noqa: E731
    args = ["extrinsecos", str(tmp_path / "cinta.png"), "--fov", "62", "--cuadro", "25", "--z", "220", "--toca", pt(0, 0), "--toca", pt(8, 0, 20.0),
            "--toca", pt(0, 5), "--valida", pt(8, 5), "--valida", pt(4, 2), "--salida", str(tmp_path / "c.json"), "--anotada", str(tmp_path / "a.png")]
    assert main(args) == 1
    assert "criterio: repetir" in capsys.readouterr().out
