"""Prueba de extremo a extremo: puente EGM en C# (ejecutable real) + controlador EGM simulado en Python.

Verifica el comportamiento de seguridad del puente tal como lo ejecuta el controlador: seguimiento,
watchdog, límites del espacio, fallo por desviación con rearme explícito, parada y comandos inválidos.
Se salta si el puente no está compilado o no hay .NET 8 (ver puente_egm/README.md).
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest

from mock.controlador_egm import ControladorSimulado
from nucleo.geometria import Pose

RAIZ = Path(__file__).resolve().parents[1]
DLL = RAIZ / "puente_egm" / "PuenteEgm" / "bin" / "Release" / "net8.0" / "PuenteEgm.dll"
DOTNET = shutil.which("dotnet") or str(Path.home() / ".local" / "bin" / "dotnet")

pytestmark = pytest.mark.skipif(
    not (DLL.exists() and Path(DOTNET).exists()),
    reason="puente EGM sin compilar (dotnet build -c Release) o sin .NET 8",
)

Q_IDENTIDAD = [1.0, 0.0, 0.0, 0.0]


def _puerto_libre(tipo: int) -> int:
    s = socket.socket(socket.AF_INET, tipo)
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    return puerto


class ClienteControl:
    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._f = sock.makefile("rwb")

    def cmd(self, dic: dict) -> dict:
        self._f.write((json.dumps(dic) + "\n").encode("utf-8"))
        self._f.flush()
        return json.loads(self._f.readline().decode("utf-8"))

    def estado(self) -> dict:
        return self.cmd({"cmd": "estado"})

    def cerrar(self) -> None:
        self._f.close()
        self._sock.close()


def _conectar(puerto: int, proc: subprocess.Popen) -> ClienteControl:
    limite = time.time() + 15.0
    while True:
        assert proc.poll() is None, "el puente se ha cerrado al arrancar"
        try:
            return ClienteControl(socket.create_connection(("127.0.0.1", puerto), timeout=2.0))
        except OSError:
            if time.time() > limite:
                raise
            time.sleep(0.1)


@contextmanager
def puente_en_marcha(tmp_path: Path, semantica: str, partida=(0.0, 0.0, 400.0)):
    puerto_egm = _puerto_libre(socket.SOCK_DGRAM)
    puerto_control = _puerto_libre(socket.SOCK_STREAM)
    registro = tmp_path / "puente.csv"
    cfg = {
        "registro_csv": str(registro),
        "sesiones": [{
            "nombre": "brazo1",
            "puerto_egm": puerto_egm,
            "ip_controlador": "127.0.0.1",
            "ip_control": "127.0.0.1",
            "puerto_control": puerto_control,
            "semantica": semantica,
            "watchdog_s": 0.1,
            "limites": {"paso_mm": 0.5, "giro_rad": 0.0025, "desviacion_mm": 20.0, "desviacion_rad": 0.1},
            "espacio_mm": {"x": [-600, 600], "y": [-600, 600], "z": [0, 800]},
        }],
    }
    ruta_cfg = tmp_path / "config.json"
    ruta_cfg.write_text(json.dumps(cfg), encoding="utf-8")
    salida = open(tmp_path / "salida.txt", "w", encoding="utf-8")
    proc = subprocess.Popen([DOTNET, str(DLL), str(ruta_cfg)], stdout=salida, stderr=subprocess.STDOUT,
                            cwd=str(tmp_path))
    ctl = controlador = None
    try:
        ctl = _conectar(puerto_control, proc)
        controlador = ControladorSimulado(("127.0.0.1", puerto_egm), Pose.crear(t=partida), semantica=semantica)
        controlador.iniciar()
        yield ctl, controlador, registro
    finally:
        if controlador is not None:
            controlador.parar()
        if ctl is not None:
            ctl.cerrar()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        salida.close()


def _mantener(ctl: ClienteControl, t, durante_s: float, q=Q_IDENTIDAD) -> None:
    """Reenvía el objetivo a unos 25 Hz: el watchdog exige flujo continuo de objetivos."""
    fin = time.time() + durante_s
    while time.time() < fin:
        r = ctl.cmd({"cmd": "objetivo", "t": [float(v) for v in t], "q": list(q)})
        assert r.get("ok") is True, r
        time.sleep(0.04)


def _real(estado: dict) -> np.ndarray:
    return np.array(estado["real"]["t"])


@pytest.fixture(params=["desplazamiento", "absoluta"])
def semantica(request):
    return request.param


def test_sigue_el_objetivo_y_registra_cada_ciclo(tmp_path, semantica):
    with puente_en_marcha(tmp_path, semantica) as (ctl, _, registro):
        _mantener(ctl, [50.0, 0.0, 400.0], 1.5)
        est = ctl.estado()
        assert est["estado"] == "activo", est
        assert np.linalg.norm(_real(est) - [50.0, 0.0, 400.0]) < 2.0, est
        assert est["intervalo_max_ms"] < 60.0, est  # cota de cordura, no garantía de tiempo real
        time.sleep(0.5)  # el registro se escribe en un hilo aparte, con un vaciado cada 200 ms
        lineas = registro.read_text(encoding="utf-8").splitlines()
        assert lineas[0].startswith("t_s,sesion,seqno,estado")
        datos = lineas[1:]
        assert len(datos) > 100
        assert all(ln.count(",") == 10 for ln in datos[:5])


def test_watchdog_retiene_la_posicion_sin_objetivos(tmp_path, semantica):
    with puente_en_marcha(tmp_path, semantica) as (ctl, _, _):
        _mantener(ctl, [50.0, 0.0, 400.0], 1.0)
        antes = _real(ctl.estado())
        time.sleep(0.5)  # sin objetivos durante más del plazo de 0,1 s
        est = ctl.estado()
        assert est["estado"] == "retener", est
        assert np.linalg.norm(_real(est) - antes) < 1.0, est


def test_limita_la_referencia_al_espacio_de_trabajo(tmp_path, semantica):
    with puente_en_marcha(tmp_path, semantica, partida=(590.0, 0.0, 400.0)) as (ctl, _, _):
        _mantener(ctl, [2000.0, 0.0, 400.0], 0.6)
        est = ctl.estado()
        assert est["estado"] == "activo", est
        assert est["referencia"]["t"][0] <= 600.0 + 1e-6, est
        assert est["referencia"]["t"][0] > 599.0, est


def test_desviacion_provoca_fallo_y_exige_rearme(tmp_path, semantica):
    with puente_en_marcha(tmp_path, semantica) as (ctl, controlador, _):
        controlador.seguir = False  # el robot no se mueve: la referencia se aleja hasta el límite
        _mantener(ctl, [100.0, 0.0, 400.0], 1.0)
        est = ctl.estado()
        assert est["estado"] == "fallo", est
        assert est["codigo"] == "desviacion_excesiva", est
        assert np.linalg.norm(np.array(est["referencia"]["t"]) - _real(est)) < 1.0, est

        _mantener(ctl, [100.0, 0.0, 400.0], 0.3)  # seguir mandando no sale del fallo
        assert ctl.estado()["estado"] == "fallo"

        assert ctl.cmd({"cmd": "reset"})["ok"] is True
        assert ctl.estado()["estado"] == "esperando"

        controlador.seguir = True
        _mantener(ctl, [0.0, 0.0, 400.0], 1.0)
        est = ctl.estado()
        assert est["estado"] == "activo", est
        assert np.linalg.norm(_real(est) - [0.0, 0.0, 400.0]) < 2.0, est


def test_parar_congela_y_arrancar_reanuda(tmp_path, semantica):
    with puente_en_marcha(tmp_path, semantica) as (ctl, _, _):
        _mantener(ctl, [10.0, 0.0, 400.0], 0.5)
        assert ctl.cmd({"cmd": "parar"})["ok"] is True
        congelada = _real(ctl.estado())
        _mantener(ctl, [60.0, 0.0, 400.0], 0.5)
        est = ctl.estado()
        assert est["estado"] == "parada", est
        assert np.linalg.norm(_real(est) - congelada) < 1.0, est

        assert ctl.cmd({"cmd": "arrancar"})["ok"] is True
        assert ctl.cmd({"cmd": "arrancar"})["ok"] is False  # ya no está parada
        _mantener(ctl, [30.0, 0.0, 400.0], 1.0)
        est = ctl.estado()
        assert est["estado"] == "activo", est
        assert np.linalg.norm(_real(est) - [30.0, 0.0, 400.0]) < 2.0, est


def test_rechaza_comandos_invalidos_sin_cambiar_el_estado(tmp_path, semantica):
    with puente_en_marcha(tmp_path, semantica) as (ctl, _, _):
        assert ctl.cmd({"cmd": "objetivo", "t": [1.0, 2.0], "q": Q_IDENTIDAD})["ok"] is False
        assert ctl.cmd({"cmd": "objetivo", "t": [1.0, 2.0, 3.0], "q": [0, 0, 0, 0]})["ok"] is False
        assert ctl.cmd({"cmd": "orden_inexistente"})["ok"] is False
        assert ctl.cmd({"cmd": "reset"})["ok"] is False  # no hay fallo que rearmar
        assert ctl.cmd({"cmd": "estado"})["ok"] is True
        assert ctl.estado()["estado"] == "esperando"
