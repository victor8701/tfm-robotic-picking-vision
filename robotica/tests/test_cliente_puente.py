"""El cliente ROS-independiente del puente contra el puente EGM real (mismo protocolo que usa nodo_puente)."""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2" / "robotica_bimanual"))

from robotica_bimanual.cliente_puente import ClientePuente  # noqa: E402
from nucleo.geometria import Pose  # noqa: E402
from test_puente_e2e import _puerto_libre, puente_en_marcha, pytestmark  # noqa: E402,F401


def _mantener(cliente: ClientePuente, pose: Pose, durante_s: float) -> None:
    fin = time.time() + durante_s
    while time.time() < fin:
        assert cliente.objetivo(pose)["ok"] is True
        time.sleep(0.04)


def test_cliente_completo_contra_el_puente(tmp_path):
    with puente_en_marcha(tmp_path, "desplazamiento") as (ctl, controlador, _):
        cfg_puerto = ctl._sock.getpeername()[1]
        cliente = ClientePuente("127.0.0.1", cfg_puerto)
        try:
            objetivo = Pose.crear(t=[40.0, 0.0, 400.0])
            _mantener(cliente, objetivo, 1.2)
            estado = cliente.estado()
            assert estado["ok"] is True and estado["estado"] == "activo", estado
            assert np.linalg.norm(np.array(estado["real"]["t"]) - objetivo.t) < 2.0
            assert cliente.parar()["ok"] is True
            assert cliente.estado()["estado"] == "parada"
            assert cliente.arrancar()["ok"] is True
            assert cliente.reset()["ok"] is False  # no hay fallo que rearmar
        finally:
            cliente.cerrar()


def test_cliente_se_reconecta_tras_una_caida(tmp_path):
    with puente_en_marcha(tmp_path, "desplazamiento") as (ctl, _, _):
        puerto = ctl._sock.getpeername()[1]
        cliente = ClientePuente("127.0.0.1", puerto)
        try:
            assert cliente.estado()["ok"] is True
            cliente.cerrar()                      # simula la caída de la conexión
            assert cliente.estado()["ok"] is True  # se abre otra al volver a llamar
        finally:
            cliente.cerrar()
