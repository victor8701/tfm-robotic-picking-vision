"""Planificacion de la caja: orientacion de la pinza, alturas, tramos y limites."""
import math

import numpy as np
import pytest

from celda.config import Config
from celda.percepcion import Caja
from celda.planificacion import a_brida, envolver_giro, orientacion_pinza, planificar, validar_puntos
from nucleo.geometria import Pose, a_matriz, quat_desde_rotvec


def cfg_prueba(**cambios) -> Config:
    base = dict(
        modo_simulacion=True, n_cajas=5, csv_caja="no-se-usa", puente_host="127.0.0.1", puente_puerto=7001,
        rapid_ip="127.0.0.1", rapid_puerto=5010, rapid_espera_s=5.0,
        z_cinta=300.0, z_mesa=150.0, z_seguro=600.0, margen_aproximacion=150.0,
        centro_recogida=(400.0, 0.0), mesa=(200.0, 400.0), eje_pinzado="y",
        periodo_s=0.04, tolerancia_pos=2.0, tolerancia_rot=0.02, max_iteraciones=5000,
        ventana_inicio=(600.0, -6.5, 740.0), ventana_semiancho=600.0,
    )
    base.update(cambios)
    return Config(**base)


def test_la_pinza_mira_hacia_abajo_para_cualquier_giro():
    for giro in (-90.0, -45.0, 0.0, 30.0, 89.0):
        R = a_matriz(orientacion_pinza(giro, "y"))
        assert np.allclose(R[:, 2], [0.0, 0.0, -1.0], atol=1e-9)


def test_el_giro_se_envuelve_modulo_180():
    assert envolver_giro(120.0) == pytest.approx(-60.0)
    assert envolver_giro(-90.0) == pytest.approx(-90.0)
    assert envolver_giro(89.9) == pytest.approx(89.9)
    assert np.allclose(a_matriz(orientacion_pinza(120.0, "y")), a_matriz(orientacion_pinza(-60.0, "y")), atol=1e-9)


@pytest.mark.parametrize("eje", ["x", "y"])
@pytest.mark.parametrize("giro", [-80.0, -20.0, 0.0, 35.0, 80.0])
def test_las_mordazas_cierran_sobre_el_lado_corto(eje, giro):
    R = a_matriz(orientacion_pinza(giro, eje))
    local = {"x": np.array([1.0, 0.0, 0.0]), "y": np.array([0.0, 1.0, 0.0])}[eje]
    mordaza = (R @ local)[:2]
    mordaza = mordaza / np.linalg.norm(mordaza)
    lado_largo = np.array([math.cos(math.radians(giro)), math.sin(math.radians(giro))])
    assert abs(float(np.dot(mordaza, lado_largo))) < 1e-9


def test_tres_tramos_con_sus_acciones():
    tramos = planificar(Caja(300.0, 200.0, 120.0, 30.0), cfg_prueba())
    assert [t.nombre for t in tramos] == ["aproximacion", "transporte", "salida"]
    assert [t.accion_final for t in tramos] == ["cerrar", "abrir", "fin_caja"]


def test_alturas_segun_el_alto_de_la_caja():
    cfg = cfg_prueba()
    caja = Caja(300.0, 200.0, 120.0, 0.0)
    aprox = planificar(caja, cfg)[0].puntos
    transp = planificar(caja, cfg)[1].puntos
    assert aprox[-1].t[2] == pytest.approx(300.0 + 60.0)            # agarre a media altura de la caja
    assert aprox[-2].t[2] == pytest.approx(300.0 + 120.0 + 150.0)   # aproximacion por encima de la caja
    assert transp[-1].t[2] == pytest.approx(150.0 + 60.0)           # deposito con la caja sobre la mesa


def test_la_salida_deja_la_pinza_por_encima_de_la_caja_depositada():
    # El TCP agarra a media altura: tras soltar, la pinza tiene que subir por encima del techo de la caja
    # (mesa + alto) mas el margen, no solo hasta z_seguro. En la celda (mesa a 320, z_seguro 485) la salida
    # quedaba 35 mm por debajo del techo de la caja (15-nov).
    caja = Caja(200.0, 200.0, 200.0, 0.0)
    cfg = cfg_prueba(z_cinta=220.0, z_mesa=320.0, z_seguro=485.0, margen_aproximacion=65.0)
    assert planificar(caja, cfg)[2].puntos[-1].t[2] == pytest.approx(320.0 + 200.0 + 65.0)
    # si z_seguro ya es mas alto, se respeta
    cfg_alto = cfg_prueba(z_cinta=220.0, z_mesa=320.0, z_seguro=700.0, margen_aproximacion=65.0)
    assert planificar(caja, cfg_alto)[2].puntos[-1].t[2] == pytest.approx(700.0)


def test_la_pinza_mantiene_la_misma_orientacion_en_todo_el_ciclo():
    tramos = planificar(Caja(300.0, 200.0, 120.0, -40.0), cfg_prueba())
    qs = [p.q for t in tramos for p in t.puntos]
    for q in qs:
        assert np.allclose(q, qs[0], atol=1e-9)


def test_puntos_validos_dentro_de_limites():
    cfg = cfg_prueba()
    for giro in (-90.0, 0.0, 89.0):
        for alto in (80.0, 150.0):
            validar_puntos(planificar(Caja(350.0, 250.0, alto, giro), cfg), cfg)


def test_un_punto_fuera_de_la_ventana_se_rechaza():
    cfg = cfg_prueba(mesa=(-100.0, 400.0))  # x = -100 queda a 700 mm de la posicion inicial
    with pytest.raises(ValueError):
        validar_puntos(planificar(Caja(300.0, 200.0, 120.0, 0.0), cfg), cfg)


def test_a_brida_pone_la_brida_147_mm_por_encima_del_tcp():
    for giro in (-90.0, -30.0, 0.0, 60.0):
        tcp = Pose.crear(t=(700.0, 0.0, 320.0), q=orientacion_pinza(giro, "y"))
        brida = a_brida(tcp, 147.0)
        assert np.allclose(brida.t, [700.0, 0.0, 467.0], atol=1e-9)
        assert np.allclose(brida.q, tcp.q)


def test_a_brida_sigue_al_eje_de_la_herramienta_si_se_inclina():
    # el TCP es la brida mas 147 mm a lo largo del eje z de la herramienta, sea cual sea la orientacion
    tcp = Pose.crear(t=(500.0, -100.0, 400.0), q=quat_desde_rotvec([0.4, -0.3, 0.2]))
    brida = a_brida(tcp, 147.0)
    assert np.allclose(brida.t + a_matriz(brida.q) @ np.array([0.0, 0.0, 147.0]), tcp.t, atol=1e-9)


def test_la_brida_fuera_del_espacio_del_puente_se_rechaza():
    # con z_seguro 700 el TCP cabe, pero la brida (847 mm) supera el limite de 800 del puente
    cfg = cfg_prueba(z_seguro=700.0)
    with pytest.raises(ValueError, match="brida"):
        validar_puntos(planificar(Caja(300.0, 200.0, 120.0, 0.0), cfg), cfg)


# ---------------------------------------------------------------- deposito ordenado en la mesa
from dataclasses import replace  # noqa: E402

from celda.planificacion import Mesa, Reparto, SinSitio  # noqa: E402

MESA = Mesa(x0=-100.0, y0=100.0, largo=500.0, ancho=500.0, z=150.0, hueco=20.0)
MIXTAS = [Caja(150.0, 100.0, 120.0, 30.0), Caja(120.0, 80.0, 90.0, -60.0), Caja(100.0, 100.0, 150.0, 0.0),
          Caja(140.0, 60.0, 100.0, 75.0), Caja(130.0, 90.0, 110.0, -20.0), Caja(110.0, 70.0, 80.0, 45.0),
          Caja(150.0, 100.0, 120.0, 10.0), Caja(90.0, 90.0, 140.0, -80.0)]


def repartir(cajas, mesa=MESA, cfg=None):
    r = Reparto(mesa)
    cfg = cfg or cfg_prueba()
    return [r.colocar(c, cfg) for c in cajas]


@pytest.mark.parametrize("giro", [-75.0, -30.0, 0.0, 30.0, 60.0, 89.0])
def test_la_caja_se_deja_sin_girar_sea_cual_sea_el_giro_con_el_que_llego(giro):
    cfg = cfg_prueba()
    caja = Caja(150.0, 100.0, 120.0, giro)
    destino = Reparto(MESA).colocar(caja, cfg)
    agarre, transporte, salida = planificar(caja, cfg, destino)
    assert np.allclose(a_matriz(agarre.puntos[-1].q), a_matriz(orientacion_pinza(giro, "y")), atol=1e-9)
    alineada = a_matriz(orientacion_pinza(0.0, "y"))
    assert np.allclose(a_matriz(transporte.puntos[-1].q), alineada, atol=1e-9)   # deposito alineado con la mesa
    assert np.allclose(a_matriz(salida.puntos[-1].q), alineada, atol=1e-9)
    # el giro se hace en el aire, antes de entrar: la entrada y todo lo que sigue ya van alineados
    assert all(np.allclose(a_matriz(p.q), alineada, atol=1e-9) for p in transporte.puntos[2:])


def test_cajas_de_medidas_distintas_no_se_solapan_y_guardan_el_hueco_con_el_borde():
    cajas = MIXTAS
    destinos = repartir(cajas)
    rects = [(d.x - c.largo / 2, d.x + c.largo / 2, d.y - c.ancho / 2, d.y + c.ancho / 2) for c, d in zip(cajas, destinos)]
    for i, (x1, x2, y1, y2) in enumerate(rects):
        assert x1 >= MESA.x0 + MESA.hueco - 1e-6 and x2 <= MESA.x0 + MESA.largo - MESA.hueco + 1e-6
        assert y1 >= MESA.y0 + MESA.hueco - 1e-6 and y2 <= MESA.y0 + MESA.ancho - MESA.hueco + 1e-6
        for (u1, u2, v1, v2) in rects[i + 1:]:
            separadas_x = u1 >= x2 + MESA.hueco - 1e-6 or x1 >= u2 + MESA.hueco - 1e-6
            separadas_y = v1 >= y2 + MESA.hueco - 1e-6 or y1 >= v2 + MESA.hueco - 1e-6
            assert separadas_x or separadas_y


def test_las_filas_se_llenan_de_x_menor_a_mayor_y_la_siguiente_empieza_tras_la_caja_mas_ancha():
    cajas = [Caja(150.0, 100.0, 120.0, 0.0), Caja(120.0, 60.0, 90.0, 0.0), Caja(150.0, 100.0, 120.0, 0.0),
             Caja(150.0, 100.0, 120.0, 0.0)]
    d = repartir(cajas)
    # fila 1: 150 + 20 + 120 = 290 de 460 utiles; la tercera (150) no cabe en lo que queda (150 > 150? 20+150+20+120+20 = 330, +150 = 480 <= 480)
    filas = sorted({round(x.y - c.ancho / 2, 6) for x, c in zip(d, cajas)})
    assert filas[0] == pytest.approx(MESA.y0 + MESA.hueco)
    mismas = [x for x, c in zip(d, cajas) if abs(x.y - c.ancho / 2 - filas[0]) < 1e-6]
    assert [round(x.x - c.largo / 2, 6) for x, c in zip(d, cajas) if abs(x.y - c.ancho / 2 - filas[0]) < 1e-6] == sorted(
        round(x.x - c.largo / 2, 6) for x, c in zip(d, cajas) if abs(x.y - c.ancho / 2 - filas[0]) < 1e-6)
    assert len(mismas) >= 2
    if len(filas) > 1:   # la fila siguiente empieza tras la caja mas ancha de la anterior mas el hueco
        ancho_fila = max(c.ancho for x, c in zip(d, cajas) if abs(x.y - c.ancho / 2 - filas[0]) < 1e-6)
        assert filas[1] == pytest.approx(filas[0] + ancho_fila + MESA.hueco)


def test_la_caja_entra_deslizandose_por_x_a_la_altura_de_viaje_y_baja_en_vertical():
    cfg = cfg_prueba()
    caja = Caja(150.0, 100.0, 120.0, 0.0)
    destino = Reparto(MESA).colocar(caja, cfg)
    transporte = planificar(caja, cfg, destino)[1].puntos
    entrada, sobre, deposito = transporte[-3], transporte[-2], transporte[-1]
    assert entrada.t[0] >= MESA.x0 + MESA.largo + caja.largo / 2                 # entera fuera de la zona, por +x
    assert entrada.t[1] == pytest.approx(destino.y) and sobre.t[1] == pytest.approx(destino.y)
    assert entrada.t[2] == pytest.approx(sobre.t[2])                              # el deslizamiento va a z constante
    assert np.allclose(deposito.t[:2], sobre.t[:2]) and deposito.t[2] == pytest.approx(MESA.z + caja.alto / 2)


def test_la_salida_sube_por_encima_de_la_caja_mas_alta_ya_dejada():
    cfg = replace(cfg_prueba(), z_seguro=100.0)    # sin z_seguro de por medio, manda la altura de las cajas
    alta, baja = Caja(150.0, 100.0, 200.0, 0.0), Caja(150.0, 100.0, 80.0, 0.0)
    r = Reparto(MESA)
    r.colocar(alta, cfg)
    d = r.colocar(baja, cfg)
    salida = planificar(baja, cfg, d)[2].puntos[0]
    assert salida.t[2] >= MESA.z + alta.alto + cfg.margen_aproximacion - 1e-9      # por encima de la alta, no solo de la propia
    assert salida.t[2] > MESA.z + baja.alto + cfg.margen_aproximacion


def test_los_sitios_a_los_que_el_robot_no_llega_se_saltan_y_las_cajas_siguen_en_orden():
    cfg = cfg_prueba()
    libre = repartir([Caja(100.0, 100.0, 100.0, 0.0)] * 2, cfg=cfg)
    corto = replace(cfg, alcance_max=560.0)           # la entrada (x = 470) deja fuera las filas de y >= 290
    limitado = repartir([Caja(100.0, 100.0, 100.0, 0.0)] * 2, cfg=corto)
    assert all(np.hypot(d.x_entrada, d.y) <= 560.0 for d in limitado)
    assert limitado[0].y >= libre[0].y - 1e-9
    assert limitado[0].x < limitado[1].x or limitado[1].y > limitado[0].y     # en orden de llenado


def test_si_la_caja_no_cabe_se_dice_y_el_reparto_no_cambia():
    cfg = cfg_prueba()
    r = Reparto(MESA)
    r.colocar(Caja(150.0, 100.0, 120.0, 0.0), cfg)
    antes = (r._fila_y, r._fondo, r._cursor, r._alto_max, r.colocadas)
    with pytest.raises(SinSitio, match="no hay sitio"):
        r.colocar(Caja(600.0, 100.0, 120.0, 0.0), cfg)           # mas larga que la zona
    assert (r._fila_y, r._fondo, r._cursor, r._alto_max, r.colocadas) == antes
    llena = Reparto(Mesa(x0=-100.0, y0=100.0, largo=200.0, ancho=130.0, z=150.0, hueco=20.0))
    llena.colocar(Caja(150.0, 90.0, 100.0, 0.0), cfg)
    with pytest.raises(SinSitio):
        llena.colocar(Caja(150.0, 90.0, 100.0, 0.0), cfg)


def test_validar_puntos_rechaza_lo_que_el_egm_o_el_brazo_no_alcanzan():
    cfg = cfg_prueba()
    caja = Caja(150.0, 100.0, 120.0, 0.0)
    tramos = planificar(caja, cfg, Reparto(MESA).colocar(caja, cfg))
    validar_puntos(tramos, cfg)
    with pytest.raises(ValueError, match="alcance"):
        validar_puntos(tramos, replace(cfg, alcance_max=100.0))
    with pytest.raises(ValueError, match="inicio del EGM"):
        validar_puntos(tramos, replace(cfg, desviacion_egm_max=300.0))
