"""Controlador simulado: el lado robot de EGM por UDP, para probar el puente sin robot.

Simplificaciones (no son el robot real):
- Dinámica de primer orden con velocidad máxima hacia la referencia.
- La referencia se interpreta según 'semantica' (igual que el puente):
    'desplazamiento': referencia = pose de partida ⊕ planned (planned.q ⊗ q_partida)
    'absoluta':       referencia = planned
- Si seguir=False, el robot no se mueve (sirve para provocar desviaciones).
"""
from __future__ import annotations

import socket
import threading
import time

import numpy as np

from egm import protocolo
from nucleo.geometria import Pose, multiplicar, slerp


class ControladorSimulado:
    def __init__(self, destino: tuple[str, int], pose_partida: Pose, semantica: str = "desplazamiento",
                 tau_s: float = 0.03, v_max_mm_s: float = 300.0, periodo_s: float = 0.004):
        if semantica not in ("desplazamiento", "absoluta"):
            raise ValueError("semantica debe ser 'desplazamiento' o 'absoluta'")
        self.destino = destino
        self.partida = pose_partida
        self.semantica = semantica
        self.tau_s = tau_s
        self.v_max = v_max_mm_s
        self.periodo_s = periodo_s
        self.seguir = True
        self.real = Pose(pose_partida.t.copy(), pose_partida.q.copy())
        self.referencia = pose_partida
        self.ultimo_sensor: protocolo.EstadoSensor | None = None
        self.enviados = 0
        self.respuestas = 0
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.setblocking(False)
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None
        self._t0 = time.perf_counter()

    @property
    def puerto_local(self) -> int:
        return self._sock.getsockname()[1]

    def iniciar(self) -> None:
        self._hilo = threading.Thread(target=self._bucle, name="controlador-egm-simulado", daemon=True)
        self._hilo.start()

    def parar(self) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=2.0)
        self._sock.close()

    def _referencia_desde(self, sensor: protocolo.EstadoSensor) -> Pose:
        if sensor.pos is None:
            return self.referencia
        if self.semantica == "absoluta":
            return Pose(sensor.pos.copy(), sensor.q.copy())
        return Pose(self.partida.t + sensor.pos, multiplicar(sensor.q, self.partida.q))

    def _avanzar(self) -> None:
        if not self.seguir:
            return
        f = min(1.0, self.periodo_s / self.tau_s)
        err = self.referencia.t - self.real.t
        v = err / self.tau_s
        n = float(np.linalg.norm(v))
        if n > self.v_max:
            v = v * (self.v_max / n)
        self.real = Pose(self.real.t + v * self.periodo_s, slerp(self.real.q, self.referencia.q, f))

    def _bucle(self) -> None:
        siguiente = time.perf_counter()
        while not self._parar.is_set():
            tm = int((time.perf_counter() - self._t0) * 1000)
            self.enviados += 1
            datos = protocolo.crear_egm_robot(self.enviados, tm, self.real.t, self.real.q)
            self._sock.sendto(datos, self.destino)
            try:
                while True:
                    respuesta, _ = self._sock.recvfrom(4096)
                    self.ultimo_sensor = protocolo.leer_egm_sensor(respuesta)
                    self.respuestas += 1
                    self.referencia = self._referencia_desde(self.ultimo_sensor)
            except BlockingIOError:
                pass
            self._avanzar()
            siguiente += self.periodo_s
            espera = siguiente - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            else:
                siguiente = time.perf_counter()
