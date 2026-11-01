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

    def _enviar(self, dic: dict) -> dict:
        if self._f is None:
            self._conectar()
        try:
            self._f.write((json.dumps(dic) + "\n").encode("utf-8"))
            self._f.flush()
            linea = self._f.readline()
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
