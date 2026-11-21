"""Canal con RAPID a traves del puente EGM: el puente es el servidor del socket de RAPID (T_COM se conecta a el) y el PC habla con RAPID por
su conexion de control. Mismos metodos que `ServidorRapid` (`esperar_cliente`, `enviar`, `recibir`, `cerrar`), asi que el ciclo no distingue uno de otro.

Con esto RAPID solo habla con el puente: el EGM (UDP) y el socket de pinza y ajustes (TCP) acaban en el mismo programa, y el PC no necesita que
el controlador le llegue (en WSL2, el controlador real no llega a un servidor que corra dentro).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2" / "robotica_bimanual"))  # ClientePuente, sin rclpy
from robotica_bimanual.cliente_puente import ClientePuente  # noqa: E402

PAUSA_S = 0.2


def _explicar(error: str) -> str:
    if "comando desconocido" in error:
        return f"{error}: el puente es una version anterior al relé de RAPID; recompilalo (puente_egm/README.md)"
    return error


class RapidPorPuente:
    def __init__(self, host: str, puerto: int, espera_s: float):
        self._espera_s = espera_s
        self._puente = f"{host}:{puerto}"
        self._c = ClientePuente(host, puerto, timeout_s=2.0)

    def esperar_cliente(self) -> None:
        """Espera a que RAPID (T_COM) tenga abierto el socket del puente. El puente puede arrancar despues que el PC: se reintenta."""
        fin = time.monotonic() + self._espera_s
        ultimo_fallo = ""
        avisado = False
        while True:
            try:
                r = self._c.rapid_estado()
                if not r.get("ok", False):
                    raise ConnectionError(_explicar(str(r.get("error", r))))
                if r.get("conectado"):
                    return
                ultimo_fallo = "el puente esta en marcha pero RAPID aun no se ha conectado (T_COM)"
            except OSError as e:
                ultimo_fallo = f"no llego al puente EGM en {self._puente}: {e}"
                if not avisado:   # una vez, para que se vea por que se queda esperando
                    print(f"(aun no llego al puente EGM en {self._puente}: {e}. Sigo intentandolo. ¿Esta en marcha, y escucha en esa IP? "
                          "Mira ip_control en su configuracion)")
                    avisado = True
            if time.monotonic() >= fin:
                raise TimeoutError(f"RAPID no se ha conectado en {self._espera_s:g} s: {ultimo_fallo}")
            time.sleep(PAUSA_S)

    def enviar(self, orden: str) -> None:
        r = self._c.rapid_enviar(orden)
        if not r.get("ok", False):
            raise ConnectionError(_explicar(str(r.get("error", r))))

    def recibir(self, timeout_s: float | None = None) -> str:
        """La respuesta de RAPID. Sin limite por defecto; con timeout_s, TimeoutError si no contesta."""
        r = self._c.rapid_recibir(timeout_s)
        if r.get("ok", False):
            return str(r["msg"])
        if r.get("codigo") == "timeout":
            raise TimeoutError(str(r.get("error", "RAPID no ha contestado")))
        raise ConnectionError(_explicar(str(r.get("error", r))))

    def cerrar(self) -> None:
        self._c.cerrar()
