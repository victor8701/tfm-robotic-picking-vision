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
# Velocidad a la que el puente mueve la referencia (paso_mm 0.4 por ciclo de 4 ms en config.celda.json) y giro
# correspondiente (giro_rad 0.0025 por ciclo). El PC solo puede ir mas despacio: para ir mas rapido hay que cambiar el
# puente (y su desviacion_mm).
VELOCIDAD_PUENTE_MM_S = 100.0
GIRO_PUENTE_RAD_S = 0.625


@dataclass(frozen=True)
class Config:
    modo_simulacion: bool
    n_cajas: int
    csv_caja: str
    puente_host: str
    puente_puerto: int
    rapid_ip: str       # solo con rapid_via = "pc": donde escucha el PC
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
    # Quien es el servidor del socket de RAPID (T_COM es siempre el cliente): "puente" = el puente EGM (seccion "rapid" de su
    # configuracion; el PC habla con RAPID por la conexion de control del puente) o "pc" = el propio PC (rapid_ip:rapid_puerto).
    rapid_via: str = "pc"
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
    # ---- Puesta en marcha: PERS de MOD_CajaPinza.mod que ajusta la ventana Parametros de la app y que el PC pide a
    # RAPID con los mensajes 'recogida', 'agarre' y 'celda'. Estos valores son los de RAPID por defecto. ----
    # Recogida (solo real; en simulacion el punto lo da el sensor de la cinta). 'fija': el centro de la caja es
    # centro_recogida para todas; 'camara': el que mide la camara mas camara_offset, dentro de +-recogida_tol de
    # centro_recogida. t_max_camara: espera maxima a una deteccion antes de parar.
    recogida_modo: str = "fija"
    recogida_tol: tuple[float, float] = (50.0, 50.0)
    camara_offset: tuple[float, float] = (0.0, 0.0)
    camara_offset_giro: float = 0.0
    t_max_camara: float = 5.0
    # Agarre. Altura h del punto de agarre sobre la base de la caja: 'porcentaje' = alto * agarre_porcentaje / 100;
    # 'tapa' = alto - agarre_hundimiento. Despues h >= agarre_minimo (los dedos sobresalen bajo el TCP) y la caja se
    # rechaza si alto < solape_minimo. apertura_pinza y grosor_dedo: 0 = sin comprobar.
    agarre_modo: str = "porcentaje"
    agarre_porcentaje: float = 50.0
    agarre_hundimiento: float = 30.0
    agarre_minimo: float = 10.0
    solape_minimo: float = 10.0
    apertura_pinza: float = 0.0
    grosor_dedo: float = 0.0
    giro_pinza: float = 0.0   # grados sumados al giro de las mordazas (eje_pinzado 'y' = 0)
    # Movimiento. velocidad: mm/s maximos del TCP (el puente limita a VELOCIDAD_PUENTE_MM_S). z_minima: suelo del
    # TCP (0 = el menor de z_cinta y z_mesa).
    velocidad: float = 100.0
    z_minima: float = 0.0
    # Percepcion por camara (solo real): calibracion (camara.json de calibracion.camara), origen de las imagenes, alto de la caja si no se mide
    # con profundidad, modo de deteccion y parametros. Ver docs/vision.md. None = sin camara configurada. Dos claves mas: visor (true = ventana
    # en tiempo real con lo que ve la camara y lo que considera la caja, vision/visor.py) y raiz_carpetas (carpeta con subcarpetas de fotos de
    # ensayo, cada una con su camara.json: la app deja elegir una de ellas, vision.proveedores.listar_carpetas).
    camara: dict | None = None


def _resolver_camara(cam: dict | None, base: Path) -> dict | None:
    """Las rutas de la seccion camara que no son absolutas se toman desde la carpeta del JSON de la celda."""
    if cam is None:
        return None
    cam = json.loads(json.dumps(cam))   # copia
    for clave in ("calibracion", "fondo", "raiz_carpetas"):
        if cam.get(clave) and not Path(cam[clave]).is_absolute():
            cam[clave] = str(base / cam[clave])
    origen = cam.get("origen") or {}
    if origen.get("ruta") and not Path(origen["ruta"]).is_absolute():
        origen["ruta"] = str(base / origen["ruta"])
    return cam


def cargar(ruta) -> Config:
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    c, k, r, v = d["celda"], d["control"], d["socket_rapid"], d["ventana_egm"]
    cfg = Config(
        modo_simulacion=bool(d["modo_simulacion"]),
        n_cajas=int(d["n_cajas"]),
        csv_caja=str(d["percepcion"]["csv_caja"]),
        puente_host=str(d["puente"]["host"]),
        puente_puerto=int(d["puente"]["puerto_control"]),
        rapid_ip=str(r.get("ip_escucha", "")),
        rapid_puerto=int(r.get("puerto", 0)),
        rapid_espera_s=float(r["espera_conexion_s"]),
        rapid_via=str(r.get("via", "pc")),
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
        camara=_resolver_camara(d.get("camara"), Path(ruta).resolve().parent),
    )
    if cfg.n_cajas < 1:
        raise ValueError("n_cajas debe ser al menos 1")
    if cfg.rapid_via not in ("puente", "pc"):
        raise ValueError(f"socket_rapid.via debe ser 'puente' o 'pc' (y es {cfg.rapid_via!r})")
    if cfg.rapid_via == "pc" and (not cfg.rapid_ip or cfg.rapid_puerto <= 0):
        raise ValueError("socket_rapid.via = 'pc' necesita ip_escucha y puerto")
    if cfg.eje_pinzado not in ("x", "y"):
        raise ValueError("eje_pinzado debe ser 'x' o 'y' (eje local de cierre de la pinza, ver CAD)")
    return cfg
