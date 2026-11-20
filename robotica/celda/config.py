"""Configuracion de la celda (JSON). Unidades: mm y grados."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Limites del espacio de trabajo del puente. Deben coincidir con espacio_mm de
# puente_egm/config.celda.json (la recogida esta a 700 mm de la base: x pasa de 600).
LIMITE_X_MM = (-600.0, 800.0)
LIMITE_Y_MM = (-600.0, 800.0)
LIMITE_Z_MM = (0.0, 800.0)


@dataclass(frozen=True)
class Config:
    modo_simulacion: bool
    n_cajas: int
    csv_caja: str
    puente_host: str
    puente_puerto: int
    rapid_ip: str
    rapid_puerto: int
    rapid_espera_s: float
    z_cinta: float
    z_mesa: float
    z_seguro: float
    margen_aproximacion: float
    centro_recogida: tuple[float, float]
    mesa: tuple[float, float]
    eje_pinzado: str
    periodo_s: float
    tolerancia_pos: float
    tolerancia_rot: float
    max_iteraciones: int
    ventana_inicio: tuple[float, float, float]
    ventana_semiancho: float
    # Plano del sensor de final de cinta (mm, base). Solo simulacion: con el, la caja parada
    # queda en y = sensor_cinta_y - medio lado delantero. None = usar centro_recogida tal cual.
    sensor_cinta_y: float | None = None
    # Distancia (mm) de la brida al TCP de la pinza, a lo largo del eje de la herramienta. EGM
    # controla la brida (tool0), asi que el PC le manda la brida = TCP + este desfase. Debe ser el
    # TCP z de herrPinza en RAPID (147).
    largo_herramienta_mm: float = 147.0
    # Punto intermedio (x, y mm, base) del transporte, a la altura de aproximacion. Evita pasar cerca
    # de la base, donde el brazo no puede seguir la trayectoria. None = recogida -> mesa directo.
    via_transporte: tuple[float, float] | None = None
    # Limites que RAPID manda con el mensaje 'mesa' (PERS egmMaxPos y alcanceMax de MOD_CajaPinza.mod); estos
    # valores son los de RAPID por defecto. desviacion_egm_max: el controlador para el EGM si la referencia se
    # aleja mas de esto (\MaxPosDeviation) de la pose con la que empezo la sesion. alcance_max: radio maximo
    # (mm, en horizontal desde el eje de la base) hasta el que el TCP de la pinza llega con comodidad.
    desviacion_egm_max: float = 1500.0
    alcance_max: float = 790.0


def cargar(ruta) -> Config:
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    c, k, r, v = d["celda"], d["control"], d["socket_rapid"], d["ventana_egm"]
    cfg = Config(
        modo_simulacion=bool(d["modo_simulacion"]),
        n_cajas=int(d["n_cajas"]),
        csv_caja=str(d["percepcion"]["csv_caja"]),
        puente_host=str(d["puente"]["host"]),
        puente_puerto=int(d["puente"]["puerto_control"]),
        rapid_ip=str(r["ip_escucha"]),
        rapid_puerto=int(r["puerto"]),
        rapid_espera_s=float(r["espera_conexion_s"]),
        z_cinta=float(c["z_cinta"]),
        z_mesa=float(c["z_mesa"]),
        z_seguro=float(c["z_seguro"]),
        margen_aproximacion=float(c["margen_aproximacion"]),
        centro_recogida=(float(c["centro_recogida"][0]), float(c["centro_recogida"][1])),
        mesa=(float(c["mesa"][0]), float(c["mesa"][1])),
        eje_pinzado=str(c["eje_pinzado"]),
        periodo_s=float(k["periodo_s"]),
        tolerancia_pos=float(k["tolerancia_pos_mm"]),
        tolerancia_rot=float(k["tolerancia_rot_rad"]),
        max_iteraciones=int(k["max_iteraciones"]),
        ventana_inicio=tuple(float(x) for x in v["inicio_mm"]),
        ventana_semiancho=float(v["semiancho_mm"]),
        sensor_cinta_y=None if c.get("sensor_cinta_y") is None else float(c["sensor_cinta_y"]),
        largo_herramienta_mm=float(c["largo_herramienta_mm"]),
        via_transporte=None if c.get("via_transporte") is None
        else (float(c["via_transporte"][0]), float(c["via_transporte"][1])),
    )
    if cfg.n_cajas < 1:
        raise ValueError("n_cajas debe ser al menos 1")
    if cfg.eje_pinzado not in ("x", "y"):
        raise ValueError("eje_pinzado debe ser 'x' o 'y' (eje local de cierre de la pinza, ver CAD)")
    return cfg
