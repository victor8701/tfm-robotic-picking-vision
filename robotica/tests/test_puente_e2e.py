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
def puente_en_marcha(tmp_path: Path, semantica: str, partida=(0.0, 0.0, 400.0), rapid_puerto: int | None = None):
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
    if rapid_puerto is not None:   # el puente hace de servidor del socket de RAPID
        cfg["sesiones"][0]["rapid"] = {"ip": "127.0.0.1", "puerto": rapid_puerto}
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
        assert all(ln.count(",") == 11 for ln in datos[:5])  # 12 columnas, la ultima es la fase


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


# ---------------------------------------------------------------- relé del socket de RAPID
def _rapid_cliente(puerto: int) -> socket.socket:
    """Lo que hace T_COM: SocketConnect al puente."""
    return socket.create_connection(("127.0.0.1", puerto), timeout=5.0)


def _esperar_conectado(ctl: ClienteControl, conectado: bool = True, limite_s: float = 5.0) -> dict:
    fin = time.time() + limite_s
    while True:
        r = ctl.cmd({"cmd": "rapid_estado"})
        if r.get("conectado") is conectado or time.time() > fin:
            return r
        time.sleep(0.05)


def test_sin_seccion_rapid_el_puente_dice_que_no_tiene_socket(tmp_path):
    with puente_en_marcha(tmp_path, "absoluta") as (ctl, _, _):
        for orden in ({"cmd": "rapid_estado"}, {"cmd": "rapid_enviar", "msg": "x"}, {"cmd": "rapid_recibir", "timeout_s": 0.1}):
            r = ctl.cmd(orden)
            assert r["ok"] is False and "sección 'rapid'" in r["error"], r


def test_rele_rapid_ida_y_vuelta_con_el_orden_de_siempre(tmp_path):
    puerto = _puerto_libre(socket.SOCK_STREAM)
    with puente_en_marcha(tmp_path, "absoluta", rapid_puerto=puerto) as (ctl, _, _):
        assert ctl.cmd({"cmd": "rapid_estado"}) == {"ok": True, "conectado": False, "origen": ""}
        assert ctl.cmd({"cmd": "rapid_enviar", "msg": "cerrar"})["ok"] is False   # nadie conectado
        rapid = _rapid_cliente(puerto)
        try:
            r = _esperar_conectado(ctl)
            assert r["ok"] is True and r["conectado"] is True and r["origen"].startswith("127.0.0.1:"), r
            assert ctl.cmd({"cmd": "rapid_enviar", "msg": "cerrar"}) == {"ok": True}
            assert rapid.recv(256).decode() == "cerrar"                 # tal cual, sin separadores
            rapid.sendall(b"cerrada")
            assert ctl.cmd({"cmd": "rapid_recibir", "timeout_s": 2.0}) == {"ok": True, "msg": "cerrada"}
            # mensaje de la mesa: largo y con numeros, tal como lo manda T_COM
            texto = "mesa:-220:542:640:420:320:30:1500:790"
            rapid.sendall(texto.encode())
            assert ctl.cmd({"cmd": "rapid_recibir", "timeout_s": 2.0})["msg"] == texto
        finally:
            rapid.close()


def test_rele_rapid_timeout_cierre_y_reconexion(tmp_path):
    puerto = _puerto_libre(socket.SOCK_STREAM)
    with puente_en_marcha(tmp_path, "absoluta", rapid_puerto=puerto) as (ctl, _, _):
        assert ctl.cmd({"cmd": "rapid_recibir", "timeout_s": 0.1})["codigo"] == "desconectado"
        rapid = _rapid_cliente(puerto)
        _esperar_conectado(ctl)
        inicio = time.time()
        r = ctl.cmd({"cmd": "rapid_recibir", "timeout_s": 0.4})
        assert r["ok"] is False and r["codigo"] == "timeout", r
        assert 0.3 < time.time() - inicio < 2.0
        rapid.close()                                    # T_COM acaba (fin del programa)
        assert _esperar_conectado(ctl, conectado=False)["conectado"] is False
        assert ctl.cmd({"cmd": "rapid_recibir", "timeout_s": 1.0})["codigo"] == "cerrado"
        assert ctl.cmd({"cmd": "rapid_enviar", "msg": "abrir"})["ok"] is False
        nuevo = _rapid_cliente(puerto)                   # un Play nuevo: otra conexion, la sustituye
        try:
            assert _esperar_conectado(ctl)["conectado"] is True
            assert ctl.cmd({"cmd": "rapid_enviar", "msg": "abrir"}) == {"ok": True}
            assert nuevo.recv(256).decode() == "abrir"
        finally:
            nuevo.close()


def test_rele_rapid_rechaza_mensajes_de_mas_de_80_caracteres(tmp_path):
    puerto = _puerto_libre(socket.SOCK_STREAM)
    with puente_en_marcha(tmp_path, "absoluta", rapid_puerto=puerto) as (ctl, _, _):
        rapid = _rapid_cliente(puerto)
        try:
            _esperar_conectado(ctl)
            r = ctl.cmd({"cmd": "rapid_enviar", "msg": "x" * 81})
            assert r["ok"] is False and "80" in r["error"], r
            assert ctl.cmd({"cmd": "rapid_enviar", "msg": "x" * 80}) == {"ok": True}
        finally:
            rapid.close()


def test_esperar_la_respuesta_de_rapid_no_para_el_movimiento(tmp_path):
    """rapid_recibir bloquea su conexion de control, pero otra conexion sigue mandando objetivos y leyendo el estado."""
    puerto = _puerto_libre(socket.SOCK_STREAM)
    with puente_en_marcha(tmp_path, "absoluta", rapid_puerto=puerto) as (ctl, _, _):
        rapid = _rapid_cliente(puerto)
        try:
            _esperar_conectado(ctl)
            # segunda conexion de control
            cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
            otro = ClienteControl(socket.create_connection(("127.0.0.1", cfg["sesiones"][0]["puerto_control"]), timeout=5.0))
            import threading
            resultado = {}
            hilo = threading.Thread(target=lambda: resultado.update(otro.cmd({"cmd": "rapid_recibir", "timeout_s": 3.0})))
            hilo.start()
            time.sleep(0.2)
            _mantener(ctl, [30.0, 0.0, 400.0], 0.5)            # el movimiento sigue mientras el otro espera
            assert ctl.estado()["estado"] == "activo"
            rapid.sendall(b"fin_ok")
            hilo.join(5.0)
            assert resultado == {"ok": True, "msg": "fin_ok"}
            otro.cerrar()
        finally:
            rapid.close()


def test_rapid_por_puente_es_un_servidor_rapid_para_el_ciclo(tmp_path):
    """RapidPorPuente (lo que usa el ciclo con socket_rapid.via = "puente") contra el puente real y un T_COM falso."""
    from celda.rapid_puente import RapidPorPuente

    puerto = _puerto_libre(socket.SOCK_STREAM)
    with puente_en_marcha(tmp_path, "absoluta", rapid_puerto=puerto):
        cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        rapid = RapidPorPuente("127.0.0.1", cfg["sesiones"][0]["puerto_control"], espera_s=10.0)
        try:
            with pytest.raises(TimeoutError, match="aun no se ha conectado"):
                RapidPorPuente("127.0.0.1", cfg["sesiones"][0]["puerto_control"], espera_s=0.5).esperar_cliente()
            tcom = _rapid_cliente(puerto)
            rapid.esperar_cliente()
            rapid.enviar("lote")
            assert tcom.recv(256).decode() == "lote"
            tcom.sendall(b"lote:2:sim")
            assert rapid.recibir(2.0) == "lote:2:sim"
            with pytest.raises(TimeoutError, match="no ha contestado"):
                rapid.recibir(0.3)
            tcom.close()
            with pytest.raises(ConnectionError, match="cerrado"):
                rapid.recibir(2.0)
        finally:
            rapid.cerrar()


def test_rapid_por_puente_sin_puente_agota_la_espera_y_lo_dice(tmp_path):
    from celda.rapid_puente import RapidPorPuente

    libre = _puerto_libre(socket.SOCK_STREAM)
    with pytest.raises(TimeoutError, match="no llego al puente EGM"):
        RapidPorPuente("127.0.0.1", libre, espera_s=0.5).esperar_cliente()
