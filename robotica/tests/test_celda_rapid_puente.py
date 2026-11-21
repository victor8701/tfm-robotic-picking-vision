"""El ciclo de la celda con el socket de RAPID a traves del puente EGM real (C#): T_COM falso <-> puente <-> RapidPorPuente <-> Celda.

El movimiento va a un puente falso (PuenteFalso): aqui solo se comprueba el canal con RAPID, que es lo que cambia con socket_rapid.via = "puente".
"""
import json
import socket
import threading

import pytest

from celda.config import Config
from celda.ciclo import Celda, crear_rapid
from celda.percepcion import FuenteCsv
from celda.rapid_puente import RapidPorPuente
from robotica_bimanual.cliente_puente import ClientePuente
from test_celda_ciclo import PuenteFalso, _puerto_libre, _rapid_falso
from test_puente_e2e import DLL, DOTNET, puente_en_marcha
from pathlib import Path

pytestmark = pytest.mark.skipif(not (DLL.exists() and Path(DOTNET).exists()), reason="puente EGM sin compilar (dotnet build -c Release) o sin .NET 8")


def _cfg(csv, movimiento, control_rapid, via="puente"):
    return Config(
        modo_simulacion=True, n_cajas=2, csv_caja=str(csv), puente_host="127.0.0.1", puente_puerto=control_rapid,
        rapid_ip="127.0.0.1", rapid_puerto=_puerto_libre(), rapid_espera_s=10.0,
        z_cinta=300.0, z_mesa=150.0, z_seguro=600.0, margen_aproximacion=150.0,
        centro_recogida=(400.0, 0.0), mesa=(200.0, 400.0), eje_pinzado="y",
        periodo_s=0.001, tolerancia_pos=2.0, tolerancia_rot=0.02, max_iteraciones=5000,
        ventana_inicio=(600.0, -6.5, 740.0), ventana_semiancho=600.0, rapid_via=via,
    )


def test_ciclo_de_dos_cajas_con_rapid_a_traves_del_puente(tmp_path):
    csv = tmp_path / "caja.csv"
    csv.write_text("150.0;100.0;120.0;30.0\n150.0;100.0;120.0;-60.0\n", encoding="utf-8")
    movimiento = PuenteFalso()
    puerto_rapid = _puerto_libre()
    mensajes: list[str] = []
    errores: list[str] = []
    with puente_en_marcha(tmp_path, "absoluta", rapid_puerto=puerto_rapid):
        control = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["sesiones"][0]["puerto_control"]
        cfg = _cfg(csv, movimiento, control)
        rapid = crear_rapid(cfg)                      # via = "puente" -> RapidPorPuente contra el control del puente
        assert isinstance(rapid, RapidPorPuente)
        tcom = threading.Thread(target=_rapid_falso, args=(puerto_rapid, movimiento, 2, mensajes, errores), daemon=True)
        tcom.start()
        cliente = ClientePuente("127.0.0.1", movimiento.puerto, timeout_s=2.0)
        try:
            rapid.esperar_cliente()
            Celda(cfg, FuenteCsv(csv), cliente, rapid).ejecutar()
        finally:
            rapid.cerrar()
            cliente.cerrar()
            movimiento.cerrar()
        tcom.join(timeout=10)
    assert errores == []
    assert mensajes == ["lote", "mesa", "recogida", "agarre", "celda", "giro:30.0", "cerrar", "abrir", "fin_caja",
                        "giro:-60.0", "cerrar", "abrir", "fin_caja", "fin_programa"]


def test_crear_rapid_elige_el_servidor_del_pc_o_el_del_puente(tmp_path):
    from celda.socket_rapid import ServidorRapid

    movimiento = PuenteFalso()
    try:
        rapid = crear_rapid(_cfg(tmp_path / "x.csv", movimiento, movimiento.puerto, via="pc"))
        assert isinstance(rapid, ServidorRapid)
        rapid.cerrar()
        assert isinstance(crear_rapid(_cfg(tmp_path / "x.csv", movimiento, movimiento.puerto, via="puente")), RapidPorPuente)
    finally:
        movimiento.cerrar()
