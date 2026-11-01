import json

import pytest

from nucleo.parametros import cargar_celda


def test_celda_por_defecto_se_carga():
    c = cargar_celda()
    assert c.periodo_ciclo_s == pytest.approx(0.004)
    assert c.watchdog_s > 0
    assert c.limites.paso_mm > 0
    assert len(c.caja_mm) == 3
    assert c.espacio.xmin < c.espacio.xmax


def test_archivo_incompleto_falla(tmp_path):
    ruta = tmp_path / "celda.json"
    ruta.write_text(json.dumps({"periodo_ciclo_s": 0.004}), encoding="utf-8")
    with pytest.raises(KeyError):
        cargar_celda(ruta)
