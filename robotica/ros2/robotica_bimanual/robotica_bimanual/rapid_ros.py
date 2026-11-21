"""Canal con RAPID por ROS 2: mismos metodos que `celda.socket_rapid.ServidorRapid` (`esperar_cliente`, `enviar`, `recibir`, `cerrar`).

El socket de RAPID lo tiene el puente EGM; `nodo_puente` lo expone en tres topics (std_msgs/String):
  /rapid/orden      celda -> puente: el texto que se manda a RAPID ("cerrar", "lote", ...)
  /rapid/respuesta  puente -> celda: el texto con que contesta RAPID ("cerrada", "lote:2:sim", ...)
  /rapid/estado     puente -> celda: JSON {"conectado": bool, "origen": "ip:puerto"} o {"error": ...} cada 0,5 s
"""
from __future__ import annotations

import json
import queue
import threading
import time

from std_msgs.msg import String

PAUSA_S = 0.05


class RapidRos:
    def __init__(self, nodo, espera_s: float):
        self._espera_s = espera_s
        self._pub = nodo.create_publisher(String, "/rapid/orden", 10)
        self._respuestas: queue.Queue[str] = queue.Queue()
        self._bloqueo = threading.Lock()
        self._estado: dict | None = None
        nodo.create_subscription(String, "/rapid/respuesta", lambda m: self._respuestas.put(m.data), 50)
        nodo.create_subscription(String, "/rapid/estado", self._recibir_estado, 10)

    def _recibir_estado(self, msg: String) -> None:
        try:
            estado = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        with self._bloqueo:
            self._estado = estado

    def _ver_estado(self) -> dict | None:
        with self._bloqueo:
            return self._estado

    def esperar_cliente(self) -> None:
        """Espera a que nodo_puente diga que RAPID (T_COM) tiene abierto el socket del puente. Hay que llamarlo desde un hilo distinto del
        que hace girar el nodo (spin)."""
        fin = time.monotonic() + self._espera_s
        while True:
            estado = self._ver_estado()
            if estado is not None and estado.get("error"):
                raise ConnectionError(f"el puente no ofrece el socket de RAPID: {estado['error']}")
            if estado is not None and estado.get("conectado") and self._pub.get_subscription_count() > 0:
                while not self._respuestas.empty():   # lo que hubiera de una conexion anterior no es de esta
                    self._respuestas.get_nowait()
                return
            if time.monotonic() >= fin:
                if estado is None:
                    raise TimeoutError(f"no llega /rapid/estado en {self._espera_s:g} s: ¿estan en marcha nodo_puente (con rapid:=true) "
                                       "y el puente EGM (PuenteEgm.exe, con la seccion 'rapid')?")
                raise TimeoutError(f"RAPID no se ha conectado al socket del puente en {self._espera_s:g} s: ¿esta en marcha T_COM?")
            time.sleep(PAUSA_S)

    def enviar(self, orden: str) -> None:
        self._pub.publish(String(data=orden))

    def recibir(self, timeout_s: float | None = None) -> str:
        """La respuesta de RAPID. Sin limite por defecto; con timeout_s, TimeoutError si no contesta."""
        try:
            return self._respuestas.get(timeout=timeout_s)
        except queue.Empty:
            raise TimeoutError(f"RAPID no ha contestado en {timeout_s:g} s") from None

    def cerrar(self) -> None:
        pass
