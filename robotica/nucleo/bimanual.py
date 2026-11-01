"""Configuración bimanual: dos bases, dos TCP sobre la caja y coordinación maestro-seguidor.

La caja rígida fija la relación entre los dos TCP. Con la pose de la caja en el mundo
T_w_caja, cada mano recibe su objetivo en su propia base. Si la pareja de TCP se separa
de la relación nominal, hay fuerzas internas: eso se trata como fallo (ver desviacion_interna).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geometria import Pose, rotvec_desde_quat


@dataclass(frozen=True)
class Configuracion:
    """Geometría de la pareja: bases en el mundo y TCP de cada mano en el marco de la caja."""

    T_w_b1: Pose
    T_w_b2: Pose
    T_caja_tcp1: Pose
    T_caja_tcp2: Pose

    def relativo_nominal(self) -> Pose:
        """Pose de TCP2 respecto a TCP1 medida en la caja (constante si la caja es rígida)."""
        return self.T_caja_tcp1.inversa().componer(self.T_caja_tcp2)


def pose_caja_en_mundo(T_w_camara: Pose, T_camara_caja: Pose) -> Pose:
    """Pose de la caja en el mundo a partir de la estimación de la cámara del maestro."""
    return T_w_camara.componer(T_camara_caja)


def objetivos_manos(T_w_caja: Pose, cfg: Configuracion) -> tuple[Pose, Pose]:
    """Objetivo de la mano 1 y de la mano 2, cada uno en su propia base."""
    tcp1_w = T_w_caja.componer(cfg.T_caja_tcp1)
    tcp2_w = T_w_caja.componer(cfg.T_caja_tcp2)
    return cfg.T_w_b1.inversa().componer(tcp1_w), cfg.T_w_b2.inversa().componer(tcp2_w)


def desviacion_interna(tcp1_w: Pose, tcp2_w: Pose, relativo_nominal: Pose) -> tuple[float, float]:
    """(mm, rad) en que la pareja de TCP se separa de la relación nominal de la caja.

    Es una medida aproximada: la norma de la traslación y del giro de E = nominal⁻¹ · (tcp1⁻¹ · tcp2).
    """
    E = relativo_nominal.inversa().componer(tcp1_w.inversa().componer(tcp2_w))
    return float(np.linalg.norm(E.t)), float(np.linalg.norm(rotvec_desde_quat(E.q)))
