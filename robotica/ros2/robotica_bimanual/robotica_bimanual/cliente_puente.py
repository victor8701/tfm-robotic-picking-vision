"""Cliente TCP del puente EGM (protocolo JSON por línea). Sin rclpy: se prueba contra el puente real.

Un cliente por sesión (= por brazo). Si la conexión se cae, se reabre en la siguiente llamada.
Las respuestas de error del puente se devuelven como dict con "ok": False; nunca lanzan
excepciones por un comando rechazado. Solo los fallos de red lanzan OSError.
"""
from __future__ import annotations

import json
import socket

from nucleo.geometria import Pose

from .convertir import comando_objetivo


_IGUAL = object()   # "el tiempo de espera de siempre" (None ya significa sin limite)


class ClientePuente:
    def __init__(self, host: str, puerto: int, timeout_s: float = 0.5):
        self.host = host
        self.puerto = puerto
        self.timeout_s = timeout_s
        self._sock: socket.socket | None = None
        self._f = None

    def _conectar(self) -> None:
        self.cerrar()
        self._sock = socket.create_connection((self.host, self.puerto), timeout=self.timeout_s)
        self._f = self._sock.makefile("rwb")

    def cerrar(self) -> None:
        for recurso in (self._f, self._sock):
            if recurso is not None:
                try:
                    recurso.close()
                except OSError:
                    pass
        self._f = None
        self._sock = None

    def _enviar(self, dic: dict, espera_s=_IGUAL) -> dict:
        """espera_s: tiempo maximo de la respuesta de esta orden (None = sin limite); por defecto, el del cliente."""
        if self._f is None:
            self._conectar()
        try:
            if espera_s is not _IGUAL:
                self._sock.settimeout(espera_s)
            self._f.write((json.dumps(dic) + "\n").encode("utf-8"))
            self._f.flush()
            linea = self._f.readline()
            if espera_s is not _IGUAL:
                self._sock.settimeout(self.timeout_s)
        except OSError:
            self.cerrar()
            raise
        if not linea:
            self.cerrar()
            raise OSError("el puente ha cerrado la conexión")
        return json.loads(linea.decode("utf-8"))

    def objetivo(self, pose: Pose) -> dict:
        return self._enviar(comando_objetivo(pose))

    def estado(self) -> dict:
        return self._enviar({"cmd": "estado"})

    def parar(self) -> dict:
        return self._enviar({"cmd": "parar"})

    def arrancar(self) -> dict:
        return self._enviar({"cmd": "arrancar"})

    def reset(self) -> dict:
        return self._enviar({"cmd": "reset"})

    # ---- Socket de RAPID a traves del puente (el puente tiene la seccion "rapid" en su configuracion). rapid_recibir bloquea la conexion
    # hasta que RAPID contesta: para esperar la respuesta hay que usar un cliente aparte del que manda los objetivos.
    def rapid_estado(self) -> dict:
        return self._enviar({"cmd": "rapid_estado"})

    def rapid_enviar(self, mensaje: str) -> dict:
        return self._enviar({"cmd": "rapid_enviar", "msg": mensaje})

    def rapid_recibir(self, timeout_s: float | None = None) -> dict:
        """{"ok": True, "msg": ...} o {"ok": False, "codigo": "timeout" | "cerrado" | "desconectado", "error": ...}."""
        orden: dict = {"cmd": "rapid_recibir"}
        if timeout_s is not None:
            orden["timeout_s"] = float(timeout_s)
        return self._enviar(orden, None if timeout_s is None else timeout_s + 5.0)
