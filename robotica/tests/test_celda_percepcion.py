"""Lectura de caja.csv (simulacion): formato, orden y errores."""
import pytest

from celda.percepcion import Caja, FuenteCsv


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
