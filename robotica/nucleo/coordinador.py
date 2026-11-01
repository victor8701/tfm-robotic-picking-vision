"""Coordinador bimanual: máquina de estados, control PBVS y consignas de las dos manos.

Es lógica pura: no habla con ROS, ni con la cámara, ni con el robot. El nodo de ROS le pasa
las poses reales de los TCP y la detección de la caja en cada ciclo, y recibe los objetivos.

Mano maestra (1): su cámara de muñeca sigue la caja con PBVS hasta la pose de agarre.
Mano seguidora (2): sigue la caja estimada con la transformación fija de agarre.
La caja se considera rígida y sujeta cuando ambas manos están en fase de transporte; ahí una
separación de los TCP respecto a la geometría nominal es fuerza interna y se trata como fallo.

Las fases de cierre de pinza, verificación y soltar dependen del driver de la mano: el
coordinador espera los eventos AGARRE_HECHO, VERIFICADO y SOLTADO desde fuera.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .bimanual import Configuracion, desviacion_interna, objetivos_manos
from .control_pbvs import error_pbvs, exp_se3, ley_pbvs
from .geometria import Pose, error_pose
from .maquina_estados import Estado, Evento, MaquinaEstados

_SOSTENIENDO = {Estado.VERIFICAR_AGARRE, Estado.LEVANTAR, Estado.TRANSPORTAR, Estado.DEPOSITAR}
_INACTIVOS = {Estado.REPOSO, Estado.FIN, Estado.FALLO, Estado.PARADA_SEGURA}


@dataclass(frozen=True)
class ParametrosCoordinacion:
    camara_en_mano1: Pose        # cámara en el marco del TCP de la mano maestra (de la calibración mano-ojo)
    punto_b: Pose                # pose de la caja en el mundo para depositarla
    altura_aprox_mm: float = 150.0
    altura_levante_mm: float = 100.0
    tol_aprox_mm: float = 10.0
    tol_aprox_rad: float = 0.02
    tol_conv_mm: float = 5.0
    tol_conv_rad: float = 0.01
    caja_max_edad_s: float = 0.5
    desv_interna_mm: float = 5.0
    desv_interna_rad: float = 0.02
    lam_t: float = 2.0
    lam_r: float = 2.0
    v_max_mm_s: float = 100.0
    w_max_rad_s: float = 0.3


@dataclass(frozen=True)
class Salida:
    estado: Estado
    objetivo1: Pose | None       # objetivo en la base de la mano 1; None = mantener (el puente retiene)
    objetivo2: Pose | None
    parar: bool                  # True en FALLO o PARADA_SEGURA: el nodo debe parar los puentes
    eventos: tuple[Evento, ...]  # eventos generados por este ciclo, para el registro


def _cerca(objetivo: Pose, real: Pose, tol_mm: float, tol_rad: float) -> bool:
    dt, dr = error_pose(real, objetivo)
    return bool(np.linalg.norm(dt) < tol_mm and np.linalg.norm(dr) < tol_rad)


class Coordinador:
    def __init__(self, bimanual: Configuracion, parametros: ParametrosCoordinacion):
        self.cfg = bimanual
        self.p = parametros
        self.maquina = MaquinaEstados()
        # Cámara vista desde la caja en la pose de agarre de la mano 1: objetivo del PBVS.
        self._T_cb_deseada = parametros.camara_en_mano1.inversa().componer(bimanual.T_caja_tcp1.inversa())
        self._caja_entrada: Pose | None = None   # pose de la caja al entrar en LEVANTAR

    @property
    def estado(self) -> Estado:
        return self.maquina.estado

    def enviar(self, evento: Evento) -> Estado:
        """Evento externo (orden del operador, driver de la mano o parada). Devuelve el estado nuevo."""
        previo = self.maquina.estado
        nuevo = self.maquina.enviar(evento)
        if nuevo is not previo:
            self._caja_entrada = None
        return nuevo

    def paso(self, dt: float, real1: Pose | None, real2: Pose | None,
             caja_cam: Pose | None, edad_caja_s: float, eventos=()) -> Salida:
        """Un ciclo de control. real1/real2: TCP reales en la base de cada mano.
        caja_cam: pose caja→cámara del maestro, o None si no hay detección."""
        emitidos: list[Evento] = []
        for e in eventos:
            self.enviar(e)

        if real1 is None or real2 is None:
            if self.maquina.estado not in _INACTIVOS:
                self._emitir(Evento.ERROR, emitidos)   # sin posición real no se puede seguir
            return self._salida(None, None, emitidos)

        tcp1_w = self.cfg.T_w_b1.componer(real1)
        tcp2_w = self.cfg.T_w_b2.componer(real2)
        cam_w = tcp1_w.componer(self.p.camara_en_mano1)
        fresca = caja_cam is not None and edad_caja_s <= self.p.caja_max_edad_s
        caja_w = cam_w.componer(caja_cam) if fresca else None

        obj1 = obj2 = None
        for _ in range(3):   # como mucho tres transiciones internas por ciclo
            est = self.maquina.estado
            evento, obj1, obj2 = self._fase(est, dt, real1, real2, tcp1_w, tcp2_w,
                                            cam_w, caja_cam, caja_w, fresca)
            if evento is None:
                break
            self._emitir(evento, emitidos)
        return self._salida(obj1, obj2, emitidos)

    # ----- fases -----

    def _fase(self, est, dt, real1, real2, tcp1_w, tcp2_w, cam_w, caja_cam, caja_w, fresca):
        """(evento a emitir o None, objetivo1, objetivo2) para la fase actual."""
        if est in (Estado.REPOSO, Estado.FIN, Estado.AGARRAR):
            return None, None, None

        if est in (Estado.FALLO, Estado.PARADA_SEGURA):
            return None, None, None

        if est is Estado.BUSCAR_CAJA:
            return (Evento.CAJA_VISTA if fresca else None), None, None

        if est in _SOSTENIENDO and not self._desviacion_ok(tcp1_w, tcp2_w):
            return Evento.ERROR, None, None

        if est is Estado.APROXIMAR:
            if not fresca:
                return None, None, None
            pre = Pose.crear(t=[0.0, 0.0, self.p.altura_aprox_mm]).componer(caja_w)
            o1, o2 = self._objetivos(pre)
            llegada = _cerca(o1, real1, self.p.tol_aprox_mm, self.p.tol_aprox_rad) and \
                _cerca(o2, real2, self.p.tol_aprox_mm, self.p.tol_aprox_rad)
            return (Evento.LLEGADA_APROX if llegada else None), o1, o2

        if est is Estado.SERVOING:
            if not fresca:
                return Evento.ERROR, None, None
            v, w = ley_pbvs(caja_cam, self._T_cb_deseada, self.p.lam_t, self.p.lam_r,
                            self.p.v_max_mm_s, self.p.w_max_rad_s)
            cam_obj = cam_w.componer(exp_se3(v, w, dt))
            o1 = self.cfg.T_w_b1.inversa().componer(cam_obj.componer(self.p.camara_en_mano1.inversa()))
            o2 = self.cfg.T_w_b2.inversa().componer(caja_w.componer(self.cfg.T_caja_tcp2))
            e_t, e_r = error_pbvs(caja_cam, self._T_cb_deseada)
            converge = e_t < self.p.tol_conv_mm and e_r < self.p.tol_conv_rad
            return (Evento.CONVERGE if converge else None), o1, o2

        if est is Estado.VERIFICAR_AGARRE:
            return None, None, None   # esperando VERIFICADO desde fuera

        if est is Estado.LEVANTAR:
            if self._caja_entrada is None:
                self._caja_entrada = tcp1_w.componer(self.cfg.T_caja_tcp1.inversa())
            objetivo = Pose.crear(t=[0.0, 0.0, self.p.altura_levante_mm]).componer(self._caja_entrada)
            o1, o2 = self._objetivos(objetivo)
            ok = _cerca(o1, real1, self.p.tol_conv_mm, self.p.tol_conv_rad) and \
                _cerca(o2, real2, self.p.tol_conv_mm, self.p.tol_conv_rad)
            return (Evento.LEVANTADO if ok else None), o1, o2

        if est is Estado.TRANSPORTAR:
            o1, o2 = self._objetivos(self.p.punto_b)
            ok = _cerca(o1, real1, self.p.tol_conv_mm, self.p.tol_conv_rad) and \
                _cerca(o2, real2, self.p.tol_conv_mm, self.p.tol_conv_rad)
            return (Evento.LLEGADA_B if ok else None), o1, o2

        if est is Estado.DEPOSITAR:
            o1, o2 = self._objetivos(self.p.punto_b)
            return None, o1, o2   # esperando SOLTADO desde fuera

        if est is Estado.RETIRAR:
            retirada = Pose.crear(t=[0.0, 0.0, self.p.altura_aprox_mm]).componer(self.p.punto_b)
            o1, o2 = self._objetivos(retirada)
            ok = _cerca(o1, real1, self.p.tol_aprox_mm, self.p.tol_aprox_rad) and \
                _cerca(o2, real2, self.p.tol_aprox_mm, self.p.tol_aprox_rad)
            return (Evento.RETIRADO if ok else None), o1, o2

        return None, None, None

    # ----- utilidades -----

    def _objetivos(self, T_w_caja: Pose) -> tuple[Pose, Pose]:
        return objetivos_manos(T_w_caja, self.cfg)

    def _desviacion_ok(self, tcp1_w: Pose, tcp2_w: Pose) -> bool:
        mm, rad = desviacion_interna(tcp1_w, tcp2_w, self.cfg.relativo_nominal())
        return mm <= self.p.desv_interna_mm and rad <= self.p.desv_interna_rad

    def _emitir(self, evento: Evento, emitidos: list[Evento]) -> None:
        emitidos.append(evento)
        self.enviar(evento)

    def _salida(self, o1, o2, emitidos) -> Salida:
        est = self.maquina.estado
        return Salida(
            estado=est,
            objetivo1=o1,
            objetivo2=o2,
            parar=est in (Estado.FALLO, Estado.PARADA_SEGURA),
            eventos=tuple(emitidos),
        )
