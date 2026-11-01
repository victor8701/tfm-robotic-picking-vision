"""Parámetros de la celda, leídos de un JSON.

Los valores de partida de simulacion/celda.json NO están medidos. Cada uno se sustituye
tras la visita 1 (docs/guion_V1.md). El JSON admite claves que empiezan por "_" como notas.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .bimanual import Configuracion
from .geometria import Pose
from .seguridad import EspacioTrabajo, Limites

RUTA_POR_DEFECTO = Path(__file__).resolve().parents[1] / "simulacion" / "celda.json"


@dataclass(frozen=True)
class Celda:
    bimanual: Configuracion
    espacio: EspacioTrabajo
    limites: Limites
    lam_t: float
    lam_r: float
    v_max_control: float
    w_max_control: float
    caja_mm: tuple[float, float, float]
    watchdog_s: float
    periodo_ciclo_s: float


def _pose(d: dict) -> Pose:
    return Pose.crear(d["t"], d["q"])


def cargar_celda(ruta: str | Path = RUTA_POR_DEFECTO) -> Celda:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    b = datos["bimanual"]
    e = datos["espacio_trabajo_mm"]
    l = datos["limites_ciclo"]
    c = datos["control"]
    return Celda(
        bimanual=Configuracion(_pose(b["base_1"]), _pose(b["base_2"]),
                               _pose(b["tcp_caja_1"]), _pose(b["tcp_caja_2"])),
        espacio=EspacioTrabajo(e["x"][0], e["x"][1], e["y"][0], e["y"][1], e["z"][0], e["z"][1]),
        limites=Limites(l["paso_mm"], l["giro_rad"], l["desviacion_mm"], l["desviacion_rad"]),
        lam_t=float(c["lam_t"]),
        lam_r=float(c["lam_r"]),
        v_max_control=float(c["v_max_mm_s"]),
        w_max_control=float(c["w_max_rad_s"]),
        caja_mm=tuple(float(x) for x in datos["caja_interior_mm"]),
        watchdog_s=float(datos["watchdog_s"]),
        periodo_ciclo_s=float(datos["periodo_ciclo_s"]),
    )
