import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "simulacion"))

from csv_a_rapid import generar_modulo, leer_csv, main  # noqa: E402
from nucleo.parametros import cargar_celda  # noqa: E402

EJEMPLO = Path(__file__).resolve().parents[1] / "simulacion" / "trayectoria_ejemplo.csv"
ESPACIO = cargar_celda().espacio


def _csv(tmp_path, texto):
    ruta = tmp_path / "t.csv"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_ejemplo_se_lee_y_genera_un_robtarget_por_punto():
    poses = leer_csv(EJEMPLO, ESPACIO)
    assert len(poses) == 5
    modulo = generar_modulo(poses)
    assert modulo.count("CONST robtarget") == 5
    assert modulo.count("MoveL ") == 5
    assert "fine, tool0;" in modulo and modulo.count("fine") == 1


def test_cuaterniones_salen_unitarios_y_los_puntos_coinciden(tmp_path):
    ruta = _csv(tmp_path, "x,y,z,qw,qx,qy,qz\n100,-50,300,2,0,0,0\n")
    (p,) = leer_csv(ruta, ESPACIO)
    assert np.allclose(p.t, [100, -50, 300])
    assert np.isclose(np.linalg.norm(p.q), 1.0)


def test_cabecera_incorrecta_falla(tmp_path):
    with pytest.raises(ValueError, match="cabecera"):
        leer_csv(_csv(tmp_path, "x,y,z,qx,qy,qz,qw\n1,2,3,1,0,0,0\n"), ESPACIO)


def test_punto_fuera_del_espacio_falla(tmp_path):
    with pytest.raises(ValueError, match="espacio de trabajo"):
        leer_csv(_csv(tmp_path, "x,y,z,qw,qx,qy,qz\n9000,0,300,1,0,0,0\n"), ESPACIO)


def test_cuaternion_nulo_falla(tmp_path):
    with pytest.raises(ValueError, match="cuaternión nulo"):
        leer_csv(_csv(tmp_path, "x,y,z,qw,qx,qy,qz\n100,0,300,0,0,0,0\n"), ESPACIO)


def test_valor_no_numerico_falla(tmp_path):
    with pytest.raises(ValueError, match="no numérico"):
        leer_csv(_csv(tmp_path, "x,y,z,qw,qx,qy,qz\n100,abc,300,1,0,0,0\n"), ESPACIO)


def test_archivo_sin_puntos_falla(tmp_path):
    with pytest.raises(ValueError, match="no tiene puntos"):
        leer_csv(_csv(tmp_path, "x,y,z,qw,qx,qy,qz\n"), ESPACIO)


def test_linea_de_comando_escribe_el_modulo(tmp_path):
    salida = tmp_path / "MOD_Trayectoria.mod"
    assert main([str(EJEMPLO), str(salida), "--velocidad", "v50"]) == 0
    texto = salida.read_text(encoding="utf-8")
    assert texto.startswith("MODULE MOD_Trayectoria")
    assert "v50, z5" in texto and texto.rstrip().endswith("ENDMODULE")


def test_linea_de_comando_devuelve_error_si_la_trayectoria_es_mala(tmp_path):
    mala = _csv(tmp_path, "x,y,z,qw,qx,qy,qz\n9000,0,300,1,0,0,0\n")
    assert main([str(mala), str(tmp_path / "x.mod")]) == 1
