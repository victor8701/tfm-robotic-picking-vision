"""Canal con RAPID por socket: el PC es servidor y T_COM de RAPID es cliente.

Protocolo sin separadores y sin concurrencia: el PC manda una orden y espera la respuesta antes de
mandar otra. Cada recv devuelve un mensaje completo.
"""
from __future__ import annotations

import socket


class ServidorRapid:
    def __init__(self, ip: str, puerto: int, espera_s: float):
        self._espera_s = espera_s
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((ip, puerto))
        self._srv.listen(1)
        self._conn: socket.socket | None = None

    def esperar_cliente(self) -> None:
        self._srv.settimeout(self._espera_s)
        self._conn, _ = self._srv.accept()
        # Sin limite: RAPID puede tardar en responder mientras cierra la pinza o la abre.
        self._conn.settimeout(None)

    def enviar(self, orden: str) -> None:
        self._conn.sendall(orden.encode("utf-8"))

    def recibir(self, timeout_s: float | None = None) -> str:
        """Espera la respuesta de RAPID. Sin limite por defecto (RAPID puede tardar mientras cierra la
        pinza); con timeout_s, TimeoutError si no contesta (para las preguntas que un RAPID antiguo
        no entiende y dejaria al PC esperando para siempre)."""
        if timeout_s is not None:
            self._conn.settimeout(timeout_s)
        try:
            datos = self._conn.recv(256)
        except socket.timeout:
            raise TimeoutError(f"RAPID no ha contestado en {timeout_s:g} s") from None
        finally:
            if timeout_s is not None:
                self._conn.settimeout(None)
        if not datos:
            raise ConnectionError("RAPID ha cerrado el socket")
        return datos.decode("utf-8").strip()

    def cerrar(self) -> None:
        for recurso in (self._conn, self._srv):
            if recurso is not None:
                try:
                    recurso.close()
                except OSError:
                    pass
        self._conn = None
