"""La configuracion de la celda es coherente entre el PC, el modulo RAPID, el EIO.cfg y el puente."""
import json
import re
from pathlib import Path

import pytest

from celda.config import LIMITE_X_MM, LIMITE_Y_MM, LIMITE_Z_MM, Config, cargar
from celda.percepcion import Caja, centro_parada
from celda.planificacion import a_brida, planificar, validar_puntos

RAIZ = Path(__file__).resolve().parents[1]
MODULO = (RAIZ / "rapid" / "MOD_CajaPinza.mod").read_text(encoding="utf-8")


def _constante(nombre: str) -> float:
    m = re.search(rf"CONST num {nombre} := (-?\d+);", MODULO)
    assert m, f"MOD_CajaPinza.mod no declara {nombre}"
    return float(m.group(1))


def _giros_rapid():
    n, giro_min, paso = int(_constante("nGiros")), _constante("giroMin"), _constante("giroPaso")
    return [giro_min + k * paso for k in range(n)]


def _secuencia_rapid(semilla: int, cajas: int):
    """El generador de MOD_CajaPinza: x := (1021 x + 11) mod 8192, k := ((x div 16) mod 12) + 1."""
    giros, x, salida = _giros_rapid(), semilla, []
    for _ in range(cajas):
        x = (x * 1021 + 11) % 8192
        salida.append(giros[(x // 16) % len(giros)])
    return salida


def test_los_doce_giros_caben_en_el_espacio_y_en_la_ventana_egm():
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    giros = _giros_rapid()
    assert len(giros) == 12 and giros[0] == -90.0 and giros[-1] == 75.0
    for giro in giros:
        centro = centro_parada(200.0, 200.0, giro, cfg.centro_recogida[0], cfg.sensor_cinta_y)
        validar_puntos(planificar(Caja(200.0, 200.0, 200.0, giro, centro), cfg), cfg)


def test_los_giros_del_modulo_son_validos_para_percepcion():
    # percepcion exige el giro en [-90, 90)
    assert all(-90.0 <= g < 90.0 for g in _giros_rapid())


def test_secuencia_del_generador_de_rapid():
    # semilla por defecto de MOD_CajaPinza
    assert re.search(r"PERS num semillaGiros := 1234;", MODULO)
    assert _secuencia_rapid(1234, 5) == [-75.0, 30.0, 60.0, -75.0, -30.0]


def test_el_generador_tiene_periodo_completo_y_cuentas_exactas():
    x, vistos = 1234, set()
    for _ in range(8192):
        assert x * 1021 + 11 < 2 ** 24  # exacto en num (float de 24 bits de mantisa)
        x = (x * 1021 + 11) % 8192
        vistos.add(x)
    assert len(vistos) == 8192


def test_el_modulo_declara_las_senales_que_el_eio_crea():
    eio = (RAIZ / "rapid" / "cfg" / "EIO" / "EIO.cfg").read_text(encoding="utf-8")
    creadas = set(re.findall(r'-Name "(\w+)" -SignalType', eio))
    usadas = {f"CajaPos{k:02d}" for k in range(1, 13)} | {"CintaMover", "CajaEnRecogida", "FinCajaEGM"}
    assert usadas <= creadas
    for nombre in usadas:
        assert nombre in MODULO


def test_el_puente_de_la_celda_permite_todos_los_puntos_del_pc():
    cfg = json.loads((RAIZ / "puente_egm" / "config.celda.json").read_text(encoding="utf-8"))
    (sesion,) = cfg["sesiones"]
    e = sesion["espacio_mm"]
    assert (tuple(e["x"]), tuple(e["y"]), tuple(e["z"])) == (LIMITE_X_MM, LIMITE_Y_MM, LIMITE_Z_MM)


def test_pseguro_del_modulo_es_el_inicio_de_la_ventana_egm():
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    m = re.search(r"VAR robtarget pSeguro := \[\[(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\]", MODULO)
    assert m
    assert tuple(float(v) for v in m.groups()) == cfg.ventana_inicio


@pytest.mark.parametrize("nombre,valor", [("cajaLargo", 200), ("cajaAncho", 200), ("cajaAlto", 200)])
def test_la_caja_de_referencia_del_modulo_es_la_del_3d(nombre, valor):
    m = re.search(rf"PERS num {nombre} := (\d+);", MODULO)
    assert m and float(m.group(1)) == valor


def test_la_caja_sin_giro_para_en_el_centro_de_recogida():
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    x, y = centro_parada(200.0, 200.0, 0.0, cfg.centro_recogida[0], cfg.sensor_cinta_y)
    assert (x, y) == tuple(cfg.centro_recogida)


def test_con_giro_el_sensor_la_para_antes():
    # un cubo de 200 mm girado 45 grados tiene medio lado delantero de 141,4 mm
    x, y = centro_parada(200.0, 200.0, 45.0, 700.0, 100.0)
    assert x == 700.0 and abs(y - (100.0 - 100.0 * 2 ** 0.5)) < 1e-9
    # 90 grados en una caja de 300 x 200: ahora el largo mira a la cinta
    assert abs(centro_parada(300.0, 200.0, -90.0, 700.0, 100.0)[1] - (100.0 - 150.0)) < 1e-9


def test_la_fuente_csv_de_simulacion_calcula_el_centro(tmp_path):
    from celda.percepcion import FuenteCsv
    csv = tmp_path / "caja.csv"
    csv.write_text("200.0;200.0;200.0;-45.0\n", encoding="utf-8")
    caja = FuenteCsv(csv, 700.0, 100.0).leer(0)
    assert caja.centro is not None and abs(caja.centro[1] - (100.0 - 100.0 * 2 ** 0.5)) < 1e-9
    assert FuenteCsv(csv).leer(0).centro is None  # sin sensor: se usa el centro de la config


def test_el_desfase_de_la_brida_es_el_tcp_de_la_pinza_en_rapid():
    # EGM controla la brida: el PC le suma el TCP de herrPinza para que el TCP llegue a su punto
    m = re.search(r"PERS tooldata herrPinza := \[TRUE,\[\[0,0,(-?[\d.]+)\],\[1,0,0,0\]\]", MODULO)
    assert m, "herrPinza no tiene el TCP en la forma esperada"
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    assert float(m.group(1)) == cfg.largo_herramienta_mm
    assert cargar(RAIZ / "celda" / "config_celda_windows.json").largo_herramienta_mm == cfg.largo_herramienta_mm


def test_egm_controla_la_brida_y_no_el_tcp():
    # si EGMActPose pasara a usar el TCP de la pinza, sobraria el desfase del PC (a_brida): quitarlo
    assert re.search(r"EGMActPose egmID, pose_cero,", MODULO)


def test_el_modulo_de_prueba_de_alcance_usa_la_misma_pinza_y_pseguro():
    prueba = (RAIZ / "rapid" / "MOD_PruebaAlcance.mod").read_text(encoding="utf-8")
    assert re.search(r"PERS tooldata herrPinza := \[TRUE,\[\[0,0,147\],\[1,0,0,0\]\]", prueba)
    assert re.search(r"CONST robtarget pSeguro := \[\[600,-6\.5,543\]", prueba)


def test_los_movimientos_de_la_celda_y_el_egm_usan_la_misma_herramienta():
    # EGMActPose controla tool0 (pose_cero): el movimiento antes de la sesion tambien debe ir con tool0.
    # Con herrPinza (TCP a 147 mm) el controlador tendria dos herramientas distintas y el brazo se movería al empezar.
    assert re.search(r"EGMActPose egmID, pose_cero,", MODULO)
    assert re.search(r"VAR robtarget pSeguroBrida := \[\[600,-6\.5,690\]", MODULO)
    cuerpo = MODULO.split("PROC main_movimiento()")[1].split("ENDPROC")[0]
    assert "herrPinza" not in cuerpo and "tool0" in cuerpo


def test_pseguro_brida_es_pseguro_mas_el_largo_de_la_pinza():
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    tcp = re.search(r"VAR robtarget pSeguro := \[\[(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\]", MODULO)
    brida = re.search(r"VAR robtarget pSeguroBrida := \[\[(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\]", MODULO)
    assert tcp and brida
    x, y, z = (float(v) for v in tcp.groups())
    xb, yb, zb = (float(v) for v in brida.groups())
    assert (xb, yb) == (x, y)
    assert zb == pytest.approx(z + cfg.largo_herramienta_mm)


def test_el_transporte_pasa_por_el_punto_intermedio_a_altura_de_aproximacion():
    # El via evita la zona de la base: la recta recogida -> mesa pasa a unos 355 mm de la base.
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    assert cfg.via_transporte == (400.0, 500.0)
    tramos = planificar(Caja(200.0, 200.0, 200.0, 0.0, cfg.centro_recogida), cfg)
    assert tramos[1].nombre == "transporte"
    z_aprox = cfg.z_cinta + 200.0 + cfg.margen_aproximacion
    assert tuple(float(v) for v in tramos[1].puntos[1].t) == pytest.approx((400.0, 500.0, z_aprox))
    validar_puntos(tramos, cfg)


def test_los_giros_de_la_caja_no_pasan_de_90_grados():
    # El PC envuelve el giro a [-90, 90) (percepcion lo exige). La ventana EGM no limita el giro: es el
    # criterio de convergencia (ver test_la_ventana_de_convergencia_distingue_el_reposo_de_la_marcha).
    assert max(abs(g) for g in _giros_rapid()) <= 90.0


def test_la_sesion_egm_termina_por_convergencia_y_no_por_interrupcion():
    # EGMStop desde una interrupcion no cerraba la sesion (15-nov): el programa seguia dentro de EGMRunPose,
    # sin movimiento y con el EGM abierto. La sesion termina cuando el robot queda convergido en la consigna
    # final; despues se cierra con EGMReset, se avisa a T_COM y la tanda acaba con Stop.
    assert not re.search(r"^\s*(ISignalDO|CONNECT|IDelete|EGMStop|TRAP)\b", MODULO, re.M)
    assert re.search(r"\\CondTime:=tiempoConv\b", MODULO)
    cuerpo = MODULO.split("PROC main_movimiento()")[1].split("ENDPROC")[0]
    i_run = cuerpo.index("EGMRunPose")
    i_reset = cuerpo.index("EGMReset egmID;", i_run)
    i_aviso = cuerpo.index("egmParado := TRUE;", i_reset)
    assert i_run < i_reset < i_aviso
    # sin Stop al final, en modo continuo el programa arrancaria otra tanda de cajas
    assert cuerpo.rstrip().endswith("Stop;")


def test_la_ventana_de_convergencia_distingue_el_reposo_de_la_marcha():
    # La ventana (mm) es el criterio de fin de sesion. Tiene que ser mayor que la tolerancia con la que el PC
    # da por alcanzado un punto y menor que el retraso del robot en marcha (v x 0,205 s, medido el 11-nov) a
    # la velocidad del puente: si no, la sesion terminaria con el robot en movimiento.
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    m = re.search(r"CONST egm_minmax ventanaPos := \[(-?[\d.]+),\s*(-?[\d.]+)\];", MODULO)
    assert m, "MOD_CajaPinza.mod no declara ventanaPos"
    ventana = float(m.group(2))
    assert float(m.group(1)) == -ventana
    (sesion,) = json.loads((RAIZ / "puente_egm" / "config.celda.json").read_text(encoding="utf-8"))["sesiones"]
    v_mm_s = sesion["limites"]["paso_mm"] / 0.004
    assert cfg.tolerancia_pos < ventana < 0.205 * v_mm_s


def test_el_tiempo_de_convergencia_cabe_en_la_espera_de_fin_caja():
    t = float(re.search(r"PERS num tiempoConv := ([\d.]+);", MODULO).group(1))
    assert 1.0 <= t <= 5.0
    assert re.search(r"WaitUntil egmParado \\MaxTime:=tiempoConv \+ 10\b", MODULO)


def test_el_arranque_va_a_pstart_y_luego_al_punto_de_espera_con_tool0():
    # pStart (740) y luego pSeguroBrida (690, el punto de espera), con tool0, antes de activar EGM.
    m = re.search(r"VAR robtarget pStart := \[\[(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\]", MODULO)
    assert m and tuple(float(v) for v in m.groups()) == (600.0, -6.5, 740.0)
    antes_egm = MODULO.split("PROC main_movimiento()")[1].split("EGMActPose")[0]
    assert "MoveJ pStart, v100, fine, tool0;" in antes_egm
    assert "MoveJ pSeguroBrida, v100, fine, tool0;" in antes_egm
    assert antes_egm.index("MoveJ pStart") < antes_egm.index("MoveJ pSeguroBrida")


def test_todos_los_puntos_del_plan_caben_en_la_ventana_del_pc_desde_pseguro_brida():
    # La ventana del PC (ventana_egm.semiancho_mm, 1400 = egmMaxPos - 100) se mide desde pSeguroBrida, donde arranca la sesion
    # EGM. No es la ventana del modulo (esa es el criterio de convergencia). Se comprueba en la brida, que
    # es lo que recibe EGM.
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    lo, hi = -cfg.ventana_semiancho, cfg.ventana_semiancho
    m = re.search(r"VAR robtarget pSeguroBrida := \[\[(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\]", MODULO)
    assert m
    origen = [float(v) for v in m.groups()]
    for giro in _giros_rapid():
        centro = centro_parada(200.0, 200.0, giro, cfg.centro_recogida[0], cfg.sensor_cinta_y)
        for tramo in planificar(Caja(200.0, 200.0, 200.0, giro, centro), cfg):
            for punto in tramo.puntos:
                brida = a_brida(punto, cfg.largo_herramienta_mm).t
                for valor, ref in zip(brida, origen):
                    assert lo <= float(valor) - ref <= hi, (giro, tramo.nombre, brida)


def test_el_puente_usa_semantica_absoluta():
    # El controlador lee EgmSensor.planned como pose absoluta en la base (pruebas del 11-nov y TFG). Con
    # "desplazamiento" el puente manda (0, 0, 0) al empezar y el robot va al origen de la base (15-nov).
    for nombre in ("config.celda.json", "config.ejemplo.json"):
        cfg = json.loads((RAIZ / "puente_egm" / nombre).read_text(encoding="utf-8"))
        assert all(s["semantica"] == "absoluta" for s in cfg["sesiones"]), nombre
    config_cs = (RAIZ / "puente_egm" / "PuenteEgm" / "Config.cs").read_text(encoding="utf-8")
    assert re.search(r'string Semantica \{ get; set; \} = "absoluta";', config_cs)


def test_la_vuelta_entre_cajas_es_por_articulaciones_y_sin_confj_off():
    # MoveJ con ConfJ Off dejaba al controlador elegir la configuracion del brazo y acabo con "Joint Out of
    # Range" (15-nov). La vuelta va por articulaciones (MoveAbsJ) a las tomadas al llegar a pSeguroBrida.
    cuerpo = MODULO.split("PROC main_movimiento()")[1].split("ENDPROC")[0]
    assert not re.search(r"^\s*Conf[JL]\b", cuerpo, re.M)
    i_llegada = cuerpo.index("MoveJ pSeguroBrida, v100, fine, tool0;")
    i_toma = cuerpo.index("jSeguroBrida := CJointT();")
    i_bucle = cuerpo.index("WHILE cajaNum < nCajas DO")
    assert i_llegada < i_toma < i_bucle
    assert "MoveAbsJ jSeguroBrida, v300, fine, tool0;" in cuerpo
    assert re.search(r"^\s*VAR jointtarget jSeguroBrida;", MODULO, re.M)


def test_la_salida_de_la_celda_libra_el_techo_de_la_caja_y_cabe_en_el_puente():
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    for giro in _giros_rapid():
        centro = centro_parada(200.0, 200.0, giro, cfg.centro_recogida[0], cfg.sensor_cinta_y)
        tramos = planificar(Caja(200.0, 200.0, 200.0, giro, centro), cfg)
        salida = tramos[-1].puntos[-1]
        assert tramos[-1].nombre == "salida"
        assert float(salida.t[2]) >= cfg.z_mesa + 200.0 + cfg.margen_aproximacion  # techo de la caja + margen
        validar_puntos(tramos, cfg)  # la brida (TCP + 147) sigue dentro del espacio del puente


def test_la_desviacion_permitida_cubre_el_retraso_del_robot_a_la_velocidad_del_puente():
    # El robot sigue la referencia con ~0,2 s de retraso (205 ms medidos el 11-nov con el puente real): en
    # marcha queda a v x 0,205 s de ella. Si desviacion_mm no lo cubre con margen, al subir la velocidad el
    # puente entra en fallo (desviacion_excesiva).
    (sesion,) = json.loads((RAIZ / "puente_egm" / "config.celda.json").read_text(encoding="utf-8"))["sesiones"]
    limites = sesion["limites"]
    v_mm_s = limites["paso_mm"] / 0.004  # un paso por ciclo de 4 ms
    assert limites["desviacion_mm"] >= 1.5 * v_mm_s * 0.205, (v_mm_s, limites)


def test_rapid_para_si_el_egm_termina_sin_que_el_pc_pida_fin_caja():
    # Con el EGM terminando por convergencia, si el PC no esta (o cuenta menos cajas), la sesion acaba sola a
    # los tiempoConv s y RAPID recorria las cajas sin agarrarlas (16-nov). Ahora se para con un mensaje.
    assert re.search(r"^\s*PERS bool finCajaRecibido := FALSE;", MODULO, re.M)
    cuerpo = MODULO.split("PROC main_movimiento()")[1].split("ENDPROC")[0]
    assert cuerpo.index("finCajaRecibido := FALSE;") < cuerpo.index("EGMRunPose")
    assert re.search(r"IF NOT finCajaRecibido THEN.*?Stop;\s*ENDIF", cuerpo.split("EGMRunPose")[1], re.S)
    pinza = MODULO.split("PROC main_pinza()")[1].split("ENDPROC")[0]
    assert pinza.index("finCajaRecibido := TRUE;") < pinza.index("WaitUntil egmParado")


def test_el_punto_de_espera_queda_por_encima_de_la_caja_que_llega():
    # En la cinta, el techo de la caja es z_cinta + alto. Con el punto de espera a 243 mm de TCP la pinza
    # quedaba dentro de la caja que llega (16-nov): tiene que quedar por encima de la altura de aproximacion.
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    m = re.search(r"VAR robtarget pSeguro := \[\[(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\]", MODULO)
    assert m
    assert float(m.group(3)) >= cfg.z_cinta + 200.0 + cfg.margen_aproximacion


# ---------------------------------------------------------------- puesta en marcha: PERS de RAPID <-> configuracion del PC
MENSAJES_AJUSTES = {
    "recogida": ["recogidaModo", "recogidaX", "recogidaY", "recogidaTolX", "recogidaTolY", "camaraOffsetX", "camaraOffsetY",
                 "camaraOffsetGiro", "tMaxCamara"],
    "agarre": ["agarreModo", "agarrePorcentaje", "agarreHundimiento", "agarreMinimo", "solapeMinimo", "aperturaPinza",
               "grosorDedo", "giroPinza"],
    "celda": ["zCinta", "margenAproximacion", "tcpZ", "seguroX", "seguroY", "seguroZ", "velocidad", "zMinima"],
}


def _pers_num(nombre):
    m = re.search(r"PERS num " + nombre + r" := (-?[\d.]+);", MODULO)
    assert m, f"falta PERS num {nombre} en MOD_CajaPinza.mod"
    return float(m.group(1))


def test_cada_mensaje_de_ajustes_de_rapid_manda_las_pers_en_el_orden_que_lee_el_pc():
    for mensaje, nombres in MENSAJES_AJUSTES.items():
        rama = MODULO.split(f'ELSEIF orden = "{mensaje}" THEN')[1].split("ELSEIF")[0]
        mandados = re.findall(r"NumToStr\((\w+), \d\)", rama)
        assert mandados == nombres, (mensaje, mandados)
        assert f'SocketSend sock \\Str:=textoAjustes;' in rama
        for n in nombres:
            _pers_num(n)
        # el mensaje cabe en las 80 posiciones de un string de RAPID con valores de hasta 7 caracteres (-2000.0)
        assert len(mensaje) + 1 + 7 + 8 * (len(nombres) - 1) <= 80, mensaje


def test_los_valores_por_defecto_de_rapid_son_los_de_la_configuracion_del_pc():
    c = Config.__dataclass_fields__
    d = lambda campo: c[campo].default  # noqa: E731
    assert (_pers_num("recogidaModo") == 0) == (d("recogida_modo") == "fija")
    assert (_pers_num("recogidaTolX"), _pers_num("recogidaTolY")) == d("recogida_tol")
    assert (_pers_num("camaraOffsetX"), _pers_num("camaraOffsetY")) == d("camara_offset")
    assert _pers_num("camaraOffsetGiro") == d("camara_offset_giro")
    assert _pers_num("tMaxCamara") == d("t_max_camara")
    assert (_pers_num("agarreModo") == 0) == (d("agarre_modo") == "porcentaje")
    for pers, campo in (("agarrePorcentaje", "agarre_porcentaje"), ("agarreHundimiento", "agarre_hundimiento"),
                        ("agarreMinimo", "agarre_minimo"), ("solapeMinimo", "solape_minimo"),
                        ("aperturaPinza", "apertura_pinza"), ("grosorDedo", "grosor_dedo"), ("giroPinza", "giro_pinza"),
                        ("velocidad", "velocidad"), ("zMinima", "z_minima")):
        assert _pers_num(pers) == d(campo), pers
    # las que ya estaban en el JSON: los valores por defecto de RAPID son los de la configuracion de la celda
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    assert _pers_num("zCinta") == cfg.z_cinta
    assert _pers_num("margenAproximacion") == cfg.margen_aproximacion
    assert _pers_num("tcpZ") == cfg.largo_herramienta_mm
    assert (_pers_num("recogidaX"), _pers_num("recogidaY")) == cfg.centro_recogida
    assert (_pers_num("seguroX"), _pers_num("seguroY"), _pers_num("seguroZ")) == cfg.ventana_inicio
    assert _pers_num("velocidad") <= 100.0   # el tope del puente (VELOCIDAD_PUENTE_MM_S)


def test_los_puntos_seguros_se_recalculan_con_el_punto_de_espera_y_el_tcp():
    cuerpo = MODULO.split("PROC AplicarSeguro()")[1].split("ENDPROC")[0]
    assert "pSeguro.trans := [seguroX, seguroY, seguroZ];" in cuerpo
    assert "pSeguroBrida.trans := [seguroX, seguroY, seguroZ + tcpZ];" in cuerpo
    assert "pStart.trans := [seguroX, seguroY, seguroZ + tcpZ + 50];" in cuerpo
    assert "herrPinza.tframe.trans.z := tcpZ;" in cuerpo
    # se aplica antes de moverse al punto de espera
    arranque = MODULO.split("PROC main_movimiento()")[1]
    assert arranque.index("AplicarSeguro;") < arranque.index("MoveJ pStart, v100, fine, tool0;")


def test_los_tiempos_de_rapid_son_los_de_la_app_y_no_valores_fijos():
    com = MODULO.split("PROC main_pinza()")[1]
    assert re.search(r"WaitDI PinzaCerrada, 1 \\MaxTime:=esperaPinza", com) and re.search(r"WaitDI PinzaCerrada, 0 \\MaxTime:=esperaPinza", com)
    assert "esperaPinza := tMaxPinza;" in com and "WaitTime tAgarre;" in com and "WaitTime tSuelta;" in com
    mov = MODULO.split("PROC main_movimiento()")[1].split("ENDPROC")[0]
    assert "WaitDI CajaEnRecogida, 1 \\MaxTime:=tMaxCaja \\TimeFlag:=sinCaja;" in mov and "WaitTime tAntesAgarrar;" in mov
    assert "\\MaxTime:=40" not in MODULO


def test_el_socket_de_rapid_del_puente_coincide_con_ipPC_y_puertoPC_de_rapid():
    """T_COM se conecta a ipPC:puertoPC; con socket_rapid.via = puente, el puente tiene que escuchar ahi (en el controlador virtual, el mismo PC)."""
    puente = json.loads((RAIZ / "puente_egm" / "config.celda.json").read_text(encoding="utf-8"))["sesiones"][0]
    assert puente["rapid"]["puerto"] == int(_constante("puertoPC"))
    assert puente["rapid"]["ip"] == re.search(r'CONST string ipPC := "([^"]+)";', MODULO).group(1)
    for nombre in ("config_celda.json", "config_celda_windows.json"):
        assert cargar(RAIZ / "celda" / nombre).rapid_via == "puente"


def test_socket_rapid_via_solo_admite_puente_o_pc(tmp_path):
    base = json.loads((RAIZ / "celda" / "config_celda.json").read_text(encoding="utf-8"))

    def con(socket_rapid):
        ruta = tmp_path / "c.json"
        ruta.write_text(json.dumps({**base, "socket_rapid": socket_rapid}), encoding="utf-8")
        return ruta

    with pytest.raises(ValueError, match="ip_escucha y puerto"):
        cargar(con({"espera_conexion_s": 5}))                       # sin via = pc, y sin donde escuchar
    assert cargar(con({"ip_escucha": "127.0.0.1", "puerto": 5010, "espera_conexion_s": 5})).rapid_via == "pc"   # configuraciones antiguas
    assert cargar(con({"via": "puente", "espera_conexion_s": 5})).rapid_via == "puente"   # el puente decide ip y puerto
    with pytest.raises(ValueError, match="'puente' o 'pc'"):
        cargar(con({"via": "udp", "espera_conexion_s": 5}))


def test_la_configuracion_de_la_prueba_en_casa_del_modo_real_carga_y_apunta_a_los_ejemplos():
    """celda/config_celda_real_casa.json (vision.md, Prueba 10): modo Real con las fotos de ejemplo como camara."""
    cfg = cargar(RAIZ / "celda" / "config_celda_real_casa.json")
    assert cfg.modo_simulacion is False and cfg.rapid_via == "puente"
    assert cfg.camara["origen"]["tipo"] == "carpeta" and cfg.camara["modo"] == "profundidad"
    ejemplos = RAIZ / "ejemplos_vision" / "celda"
    if ejemplos.exists():   # ejemplos_vision/ no esta en git: se genera con vision.generar_ejemplos
        assert Path(cfg.camara["calibracion"]).is_file() and Path(cfg.camara["origen"]["ruta"]).is_dir()
