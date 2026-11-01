"""Coordinador bimanual en simulación: un ciclo completo de agarre, transporte y depósito, y los fallos.

Simulación (no es el robot): cada brazo sigue su consigna con dinámica de primer orden y velocidad
máxima; la caja se mueve con la mano 1 cuando está sujeta; la cámara de muñeca ve la caja si su
centro está dentro de un cono de media apertura de 80°. Ese campo es generoso a propósito: con la
geometría de partida de celda.json la caja NO entra en un campo de cámara típico en la pose de
agarre (ver README, riesgos). Aquí se prueba la lógica de control, no la visibilidad real.
"""
import numpy as np

from nucleo.bimanual import desviacion_interna
from nucleo.coordinador import Coordinador
from nucleo.geometria import Pose, quat_desde_rotvec, slerp
from nucleo.maquina_estados import Estado, Evento
from nucleo.parametros import cargar_celda

DT = 0.04
CAMPO_MEDIA_APERTURA_DEG = 80.0


def _visible(T_cam_caja: Pose) -> bool:
    x, y, z = T_cam_caja.t
    return 50.0 < z < 3000.0 and np.hypot(x, y) < np.tan(np.deg2rad(CAMPO_MEDIA_APERTURA_DEG)) * z


def _seguir(actual: Pose, objetivo: Pose, dt: float, tau: float = 0.1, v_max: float = 300.0) -> Pose:
    v = (objetivo.t - actual.t) / tau
    n = float(np.linalg.norm(v))
    if n > v_max:
        v = v * (v_max / n)
    return Pose(actual.t + v * dt, slerp(actual.q, objetivo.q, min(1.0, dt / tau)))


def _escenario(eventos_de_fallo=None, ticks_max=4000):
    celda = cargar_celda()
    cfg = celda.bimanual
    X = celda.coordinacion.camara_en_mano1
    co = Coordinador(cfg, celda.coordinacion)

    caja = Pose.crear(t=[600.0, 0.0, 100.0])
    tcp1 = Pose.crear(t=[300.0, -150.0, 450.0], q=[0, 1, 0, 0])
    tcp2 = Pose.crear(t=[900.0, 150.0, 450.0], q=[0, 1, 0, 0])

    t = 0.0
    pendientes = [Evento.INICIAR]
    sostenida = False
    t_en_estado = 0.0
    ultima_vista = None
    bloqueo_hasta = -1.0
    desvios = []
    salidas = []
    estado_previo = co.estado
    fallo_inyectado = False

    for _ in range(ticks_max):
        real1 = cfg.T_w_b1.inversa().componer(tcp1)
        real2 = cfg.T_w_b2.inversa().componer(tcp2)
        cam = tcp1.componer(X)
        caja_cam_real = cam.inversa().componer(caja)
        if t < bloqueo_hasta or not _visible(caja_cam_real):
            caja_cam = None
        else:
            caja_cam = caja_cam_real
            ultima_vista = t
        edad = np.inf if ultima_vista is None else t - ultima_vista

        salida = co.paso(DT, real1, real2, caja_cam, edad, pendientes)
        salidas.append(salida)
        pendientes = []

        if co.estado is not estado_previo:
            estado_previo = co.estado
            t_en_estado = 0.0
            if co.estado is Estado.SERVOING and eventos_de_fallo == "vision":
                bloqueo_hasta = t + 3.0
            if co.estado is Estado.VERIFICAR_AGARRE and eventos_de_fallo == "desvio":
                tcp2 = Pose.crear(t=tcp2.t + np.array([10.0, 0.0, 0.0]), q=tcp2.q)
                fallo_inyectado = True
        t_en_estado += DT

        if co.estado is Estado.AGARRAR and t_en_estado >= 0.3:
            pendientes.append(Evento.AGARRE_HECHO)
            sostenida = True
        if co.estado is Estado.VERIFICAR_AGARRE:
            pendientes.append(Evento.VERIFICADO)
        if co.estado is Estado.DEPOSITAR and t_en_estado >= 0.3:
            pendientes.append(Evento.SOLTADO)
            sostenida = False

        if salida.objetivo1 is not None:
            tcp1 = _seguir(tcp1, cfg.T_w_b1.componer(salida.objetivo1), DT)
        if salida.objetivo2 is not None:
            tcp2 = _seguir(tcp2, cfg.T_w_b2.componer(salida.objetivo2), DT)
        if sostenida:
            caja = tcp1.componer(cfg.T_caja_tcp1.inversa())
            desvios.append(desviacion_interna(tcp1, tcp2, cfg.relativo_nominal()))

        if salida.estado in (Estado.FIN, Estado.FALLO, Estado.PARADA_SEGURA):
            break
        t += DT

    return {
        "co": co,
        "celda": celda,
        "historial": list(co.maquina.historial),
        "salidas": salidas,
        "desvios": desvios,
        "caja": caja,
        "fallo_inyectado": fallo_inyectado,
    }


def test_ciclo_completo_de_agarre_transporte_y_deposito():
    r = _escenario()
    assert r["historial"] == [
        Estado.REPOSO, Estado.BUSCAR_CAJA, Estado.APROXIMAR, Estado.SERVOING, Estado.AGARRAR,
        Estado.VERIFICAR_AGARRE, Estado.LEVANTAR, Estado.TRANSPORTAR, Estado.DEPOSITAR,
        Estado.RETIRAR, Estado.FIN,
    ]
    assert r["desvios"], "la caja debe haberse sujetado en algún momento"
    assert max(mm for mm, _ in r["desvios"]) < 5.0
    assert max(rad for _, rad in r["desvios"]) < 0.02
    punto_b = r["celda"].coordinacion.punto_b
    assert np.linalg.norm(r["caja"].t - punto_b.t) < 10.0


def test_perder_la_vision_durante_el_servoing_es_fallo_y_parada():
    r = _escenario(eventos_de_fallo="vision")
    assert r["historial"][-1] is Estado.FALLO
    ultima = r["salidas"][-1]
    assert ultima.parar is True
    assert ultima.objetivo1 is None and ultima.objetivo2 is None


def test_desvio_de_una_pinza_al_sostener_la_caja_es_fallo():
    r = _escenario(eventos_de_fallo="desvio")
    assert r["fallo_inyectado"]
    assert r["historial"][-1] is Estado.FALLO
    assert r["salidas"][-1].parar is True


def test_parada_externa_lleva_a_parada_segura():
    celda = cargar_celda()
    co = Coordinador(celda.bimanual, celda.coordinacion)
    co.paso(DT, None, None, None, np.inf, [Evento.INICIAR])
    co.enviar(Evento.PARADA)
    assert co.estado is Estado.PARADA_SEGURA
    salida = co.paso(DT, Pose.crear(), Pose.crear(), None, np.inf)
    assert salida.parar is True and salida.objetivo1 is None


def test_sin_posicion_real_durante_el_servoing_es_error():
    celda = cargar_celda()
    co = Coordinador(celda.bimanual, celda.coordinacion)
    co.paso(DT, Pose.crear(), Pose.crear(), None, np.inf, [Evento.INICIAR])
    co.enviar(Evento.CAJA_VISTA)
    co.enviar(Evento.LLEGADA_APROX)
    assert co.estado is Estado.SERVOING
    salida = co.paso(DT, None, Pose.crear(), None, np.inf)
    assert salida.estado is Estado.FALLO and salida.parar is True
