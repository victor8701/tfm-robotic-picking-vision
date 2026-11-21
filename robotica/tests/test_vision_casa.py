"""Programa de pruebas en casa (vision.probar_en_casa) y generador de ejemplos."""
import csv
import shutil

import cv2
import numpy as np
import pytest

from celda.percepcion import FuenteCsv
from vision.generar_ejemplos import generar
from vision.probar_en_casa import main


@pytest.fixture(scope="module")
def ejemplos(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("ejemplos")
    generar(carpeta)
    return carpeta


def _verdad(ejemplos):
    with open(ejemplos / "verdad.csv", encoding="utf-8") as fh:
        return {r["imagen"]: {k: float(v) for k, v in r.items() if k != "imagen"} for r in csv.DictReader(fh, delimiter=";")}


def _detecciones(salida):
    with open(salida / "detecciones.csv", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def _subcarpeta(ejemplos, tmp_path, nombres, con_profundidad=True):
    d = tmp_path / "fotos"
    d.mkdir()
    for n in nombres:
        shutil.copy(ejemplos / "casa" / f"{n}.png", d)
        if con_profundidad:
            shutil.copy(ejemplos / "casa" / f"{n}.npy", d)
    return d


def test_en_casa_con_profundidad_se_mide_cada_foto_casi_exacta(ejemplos, tmp_path, capsys):
    salida = tmp_path / "res"
    assert main([str(ejemplos / "casa"), "--tablero", "9x6", "--cuadro", "25", "--fov", "62", "--modo", "profundidad", "--salida", str(salida)]) == 0
    verdad = _verdad(ejemplos)
    filas = _detecciones(salida)
    assert len(filas) == 5 and all(f["elegida"] == "1" for f in filas)
    for f in filas:
        v = verdad[f"casa/{f['imagen']}"]
        assert abs(float(f["largo"]) - max(v["largo"], v["ancho"])) < 1.0 and abs(float(f["ancho"]) - min(v["largo"], v["ancho"])) < 1.0
        assert abs(float(f["alto"]) - v["alto"]) < 1.5
        assert np.hypot(float(f["centro_x"]) - v["centro_x"], float(f["centro_y"]) - v["centro_y"]) < 1.0
        if abs(v["largo"] - v["ancho"]) > 5:
            dg = ((float(f["giro"]) - v["giro"] + 90.0) % 180.0) - 90.0
            assert abs(dg) < 1.0, f
        assert (salida / f"{f['imagen'][:-4]}_anotada.png").is_file()
    assert "5 de 5 fotos con caja" in capsys.readouterr().out


def test_en_casa_con_color_y_alto_dado_el_error_cabe_en_lo_que_avisa_el_programa(ejemplos, tmp_path, capsys):
    carpeta = _subcarpeta(ejemplos, tmp_path, ["casa_01", "casa_02"], con_profundidad=False)
    salida = tmp_path / "res"
    assert main([str(carpeta), "--tablero", "9x6", "--cuadro", "25", "--fov", "62", "--alto", "120", "--esperado", "200,140", "--salida", str(salida)]) == 0
    out = capsys.readouterr().out
    assert "error largo" in out
    for f in _detecciones(salida):
        assert abs(float(f["largo"]) - 200.0) <= 1.5 * float(f["pared_mm"]) + 3.0
        assert abs(float(f["ancho"]) - 140.0) <= 1.5 * float(f["pared_mm"]) + 3.0


def test_el_csv_para_la_simulacion_es_el_de_caja_csv_y_lo_lee_el_pc(ejemplos, tmp_path):
    salida = tmp_path / "res"
    assert main([str(ejemplos / "casa"), "--tablero", "9x6", "--cuadro", "25", "--fov", "62", "--modo", "profundidad", "--salida", str(salida)]) == 0
    lineas = (salida / "caja_vision.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(lineas) == 5 and all(len(l.split(";")) == 4 for l in lineas)
    fuente = FuenteCsv(salida / "caja_vision.csv")      # es el formato de caja.csv de RAPID
    assert fuente.total() == 5
    c = fuente.leer(1)
    assert (c.largo, c.ancho, c.alto) == pytest.approx((200.0, 140.0, 120.7), abs=1.5) and c.giro_deg == pytest.approx(25.0, abs=1.0)


def test_con_la_calibracion_de_la_celda_las_posiciones_salen_en_la_base_del_robot(ejemplos, tmp_path):
    salida = tmp_path / "res"
    assert main([str(ejemplos / "celda"), "--calibracion", str(ejemplos / "celda" / "camara.json"), "--z", "220", "--salida", str(salida)]) == 0
    verdad = _verdad(ejemplos)
    for f in _detecciones(salida):
        v = verdad[f"celda/{f['imagen']}"]
        assert np.hypot(float(f["centro_x"]) - v["centro_x"], float(f["centro_y"]) - v["centro_y"]) < 1.0
        assert abs(float(f["largo"]) - max(v["largo"], v["ancho"])) < 6.0     # color con profundidad solo para el alto: algo de pared
        assert abs(float(f["alto"]) - v["alto"]) < 2.0


def test_el_modo_fondo_usa_la_foto_de_la_escena_sin_cajas(ejemplos, tmp_path):
    carpeta = _subcarpeta(ejemplos, tmp_path, ["casa_03"], con_profundidad=False)
    salida = tmp_path / "res"
    assert main([str(carpeta), "--tablero", "9x6", "--cuadro", "25", "--fov", "62", "--alto", "120", "--modo", "fondo", "--fondo", str(ejemplos / "fondo.png"),
                 "--salida", str(salida)]) == 0
    f = _detecciones(salida)[0]
    assert abs(float(f["largo"]) - 200.0) < 12.0 and abs(float(f["ancho"]) - 140.0) < 12.0


def test_sin_alto_ni_profundidad_el_programa_lo_pide(ejemplos, tmp_path, capsys):
    carpeta = _subcarpeta(ejemplos, tmp_path, ["casa_01"], con_profundidad=False)
    assert main([str(carpeta), "--tablero", "9x6", "--cuadro", "25", "--fov", "62", "--salida", str(tmp_path / "res")]) == 2
    assert "falta --alto" in capsys.readouterr().err


def test_datos_incorrectos_dan_codigo_2(ejemplos, tmp_path, capsys):
    assert main([str(tmp_path / "no_existe"), "--tablero", "9x6", "--cuadro", "25", "--alto", "100"]) == 2
    carpeta = _subcarpeta(ejemplos, tmp_path, ["casa_01"])
    assert main([str(carpeta), "--alto", "100"]) == 2                                   # sin --cuadro ni --calibracion
    assert "falta --cuadro" in capsys.readouterr().err
    assert main([str(carpeta), "--tablero", "9x6", "--cuadro", "25", "--modo", "fondo", "--alto", "100"]) == 2   # fondo sin --fondo
    assert main([str(carpeta), "--tablero", "9x6", "--cuadro", "25", "--alto", "100", "--esperado", "200"]) == 2
    assert main([str(carpeta), "--tablero", "9x6", "--cuadro", "25", "--alto", "100", "--interactivo", "--modo", "fondo"]) == 2


def test_una_foto_sin_tablero_o_sin_caja_se_avisa_y_da_codigo_1(ejemplos, tmp_path, capsys):
    d = tmp_path / "fotos"
    d.mkdir()
    cv2.imwrite(str(d / "gris.png"), np.full((720, 960, 3), 120, np.uint8))
    assert main([str(d), "--tablero", "9x6", "--cuadro", "25", "--fov", "62", "--alto", "100", "--salida", str(tmp_path / "res")]) == 1
    out = capsys.readouterr().out
    assert "gris.png: no veo el tablero" in out and "0 de 1 fotos con caja" in out
    assert (tmp_path / "res" / "gris_anotada.png").is_file()
    # con tablero pero sin caja
    sin_caja = cv2.imread(str(ejemplos / "fondo.png"))
    cv2.imwrite(str(d / "gris.png"), sin_caja)
    assert main([str(d), "--tablero", "9x6", "--cuadro", "25", "--fov", "62", "--alto", "100", "--salida", str(tmp_path / "res")]) == 1
    assert "no encuentro ninguna caja" in capsys.readouterr().out


def test_el_generador_deja_las_fotos_la_profundidad_el_fondo_y_la_verdad(ejemplos):
    assert len(list((ejemplos / "casa").glob("*.png"))) == 5 and len(list((ejemplos / "casa").glob("*.npy"))) == 5
    assert (ejemplos / "fondo.png").is_file() and (ejemplos / "celda" / "camara.json").is_file() and len(_verdad(ejemplos)) == 8
