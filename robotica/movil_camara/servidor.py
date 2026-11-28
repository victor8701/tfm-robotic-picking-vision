#!/usr/bin/env python3
"""El móvil como cámara de la celda: una página para el teléfono y un buzón que guarda solo la ÚLTIMA foto.

    móvil   https://<servidor>/c/<clave>            la página: pide la cámara y va enviando fotos JPEG
    PC      --url https://<servidor>/c/<clave>      pide una foto hecha después de pedirla (vision.proveedores.CamaraMovil)

Las fotos solo están en memoria (nada en disco) y sin la clave no se ve ni se envía nada. Solo librería estándar de Python.
En Render: directorio raíz robotica/movil_camara, arranque `python servidor.py` y la variable de entorno CLAVE (docs/manual_robotstudio_cajapinza.md,
11.3 d). En el PC, para pruebas: CLAVE=una-clave-larga python servidor.py (un teléfono solo da la cámara a una página con https).
"""
from __future__ import annotations

import hmac
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

MAX_BYTES = 3_000_000        # una foto de 1280x720 en JPEG pesa 0,1 o 0,2 MB
ESPERA_MAX_S = 20.0
PC_ACTIVO_S = 15.0           # si el PC ha pedido una foto hace menos de esto, el móvil envía todo lo rápido que puede
FOTOS_NUEVAS = 2             # la primera que llega tras la petición pudo hacerse antes de ella; la segunda ya es seguro posterior
CLAVE_VALIDA = re.compile(r"[A-Za-z0-9_-]{8,64}")
PAGINA = Path(__file__).with_name("pagina.html")


class Buzon:
    """La última foto recibida y cuántas han llegado."""

    def __init__(self):
        self._cond = threading.Condition()
        self._foto: bytes | None = None
        self._numero = 0
        self._llegada: float | None = None
        self._peticion_pc: float | None = None

    def dejar(self, foto: bytes) -> int:
        with self._cond:
            self._foto, self._llegada = foto, time.monotonic()
            self._numero += 1
            self._cond.notify_all()
            return self._numero

    def recoger(self, espera_s: float, nuevas: int = FOTOS_NUEVAS) -> bytes | None:
        """Una foto hecha después de esta llamada: espera a que lleguen `nuevas` fotos más. None si no llegan en espera_s (nunca una vieja)."""
        with self._cond:
            self._peticion_pc = time.monotonic()
            hasta = self._numero + nuevas
            llegaron = self._cond.wait_for(lambda: self._numero >= hasta, timeout=espera_s)
            self._peticion_pc = time.monotonic()
            return self._foto if llegaron else None

    def pc_activo(self) -> bool:
        with self._cond:
            return self._peticion_pc is not None and time.monotonic() - self._peticion_pc < PC_ACTIVO_S

    def estado(self) -> dict:
        with self._cond:
            hace = None if self._llegada is None else round(time.monotonic() - self._llegada, 1)
            numero = self._numero
        return {"fotos": numero, "ultima_hace_s": hace, "pc": self.pc_activo()}


class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 60

    def log_message(self, *args):        # ni una línea por foto, ni la clave en los registros
        pass

    def _responder(self, codigo: int, cuerpo: bytes = b"", tipo: str = "text/plain; charset=utf-8") -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def _json(self, dato: dict) -> None:
        self._responder(200, json.dumps(dato).encode(), "application/json")

    def _ruta(self):
        """(recurso, consulta) si la dirección es /c/<clave>[/recurso] con la clave buena; None si no."""
        partes = urlsplit(self.path)
        trozos = partes.path.strip("/").split("/")
        if len(trozos) not in (2, 3) or trozos[0] != "c" or not hmac.compare_digest(trozos[1].encode(), self.server.clave.encode()):
            return None
        return (trozos[2] if len(trozos) == 3 else ""), parse_qs(partes.query)

    def do_GET(self) -> None:
        if urlsplit(self.path).path in ("/", "/salud"):
            self._responder(200, "Cámara de la celda en marcha. Abre /c/<tu clave>.".encode())
            return
        ruta = self._ruta()
        if ruta is None:
            time.sleep(0.5)              # no ayudar a quien vaya probando claves
            self._responder(404, "clave o dirección incorrecta".encode())
            return
        recurso, consulta = ruta
        if recurso == "":
            self._responder(200, PAGINA.read_bytes(), "text/html; charset=utf-8")
        elif recurso == "estado":
            self._json(self.server.buzon.estado())
        elif recurso == "ultima":
            try:
                espera = min(max(float(consulta.get("espera", ["5"])[0]), 0.0), ESPERA_MAX_S)
            except ValueError:
                self._responder(400, b"espera no es un numero")
                return
            foto = self.server.buzon.recoger(espera)
            if foto is None:
                self._responder(204)
            else:
                self._responder(200, foto, "image/jpeg")
        else:
            self._responder(404, b"no existe")

    do_HEAD = do_GET

    def do_POST(self) -> None:
        ruta = self._ruta()
        try:
            largo = int(self.headers.get("Content-Length", ""))
        except ValueError:
            largo = -1
        if ruta is None or ruta[0] != "foto" or not 0 < largo <= MAX_BYTES:
            self.close_connection = True      # no se lee lo que venga: se contesta y se corta
            if ruta is None or ruta[0] != "foto":
                self._responder(404, "clave o dirección incorrecta".encode())
            else:
                self._responder(413, b"foto demasiado grande o vacia")
            return
        foto = self.rfile.read(largo)
        if len(foto) != largo or not foto.startswith(b"\xff\xd8"):
            self.close_connection = True
            self._responder(400, b"no es una foto JPEG entera")
            return
        numero = self.server.buzon.dejar(foto)
        self._json({"fotos": numero, "pc": self.server.buzon.pc_activo()})


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, direccion, clave: str):
        if not CLAVE_VALIDA.fullmatch(clave or ""):
            raise ValueError("falta la variable de entorno CLAVE o no vale: de 8 a 64 caracteres entre letras sin tilde, números, - y _")
        super().__init__(direccion, Manejador)
        self.clave = clave
        self.buzon = Buzon()

    def handle_error(self, request, client_address) -> None:
        if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):   # que un móvil o un PC se desconecten no es un error
            super().handle_error(request, client_address)


def main(entorno=os.environ) -> int:
    puerto = int(entorno.get("PORT", "8000"))
    try:
        servidor = Servidor(("0.0.0.0", puerto), entorno.get("CLAVE", ""))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr, flush=True)
        return 2
    print(f"Escuchando en el puerto {puerto}. La dirección del móvil y del PC es <este servidor>/c/<CLAVE>", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
