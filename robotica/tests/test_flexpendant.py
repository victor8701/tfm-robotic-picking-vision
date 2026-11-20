"""App CajaPinza del FlexPendant: coherente con MOD_CajaPinza.mod y EIO.cfg, y probada con Node.

Las pruebas de JavaScript (logica.test.js y app.test.js, en tests/js) se lanzan con Node si esta; la de
pantalla ademas necesita jsdom (CAJAPINZA_JSDOM = carpeta con node_modules/jsdom, o `npm install` en
tests/js). Sin Node o sin jsdom se saltan."""
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "flexpendant" / "CajaPinza"
JS = RAIZ / "tests" / "js"
MODULO = (RAIZ / "rapid" / "MOD_CajaPinza.mod").read_text(encoding="utf-8")
EIO = (RAIZ / "rapid" / "cfg" / "EIO" / "EIO.cfg").read_text(encoding="utf-8")


# ---------------------------------------------------------------- Node
def _node():
    windows = "/mnt/c/Program Files/nodejs/node.exe"  # WSL: el Node de Windows
    if re.match(r"^[A-Za-z]:\\", os.environ.get("CAJAPINZA_JSDOM", "")) and os.path.exists(windows):
        return windows   # jsdom instalado en una carpeta de Windows: lo ve el Node de Windows
    return shutil.which("node") or (windows if os.path.exists(windows) else None)


def _ruta(exe: str, ruta: Path) -> str:
    """El Node de Windows necesita rutas de Windows."""
    if exe.lower().endswith(".exe"):
        return subprocess.check_output(["wslpath", "-w", str(ruta)], text=True).strip()
    return str(ruta)


def _lanzar(script: Path, *args: str, timeout: int = 240) -> subprocess.CompletedProcess:
    exe = _node()
    return subprocess.run([exe, _ruta(exe, script), *args], capture_output=True, text=True, timeout=timeout)


requiere_node = pytest.mark.skipif(_node() is None, reason="Node no esta instalado")


def _tablas() -> dict:
    r = _lanzar(JS / "volcar_tablas.js")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ---------------------------------------------------------------- RAPID <-> app
@requiere_node
def test_las_fases_de_la_app_son_las_del_modulo_rapid():
    en_rapid = {m.group(1): int(m.group(2)) for m in re.finditer(r"CONST num FASE_(\w+) := (\d+);", MODULO)}
    assert en_rapid == _tablas()["FASES"]


def test_cada_fase_de_rapid_se_asigna_en_algun_sitio():
    # una fase que nadie pone es un paso que la pantalla nunca mostraria (PARADO es solo el valor inicial)
    for nombre in re.findall(r"CONST num FASE_(\w+) := \d+;", MODULO):
        if nombre != "PARADO":
            assert f"hmiFase := FASE_{nombre};" in MODULO, f"FASE_{nombre} no se asigna nunca"


@requiere_node
def test_las_pers_de_la_app_existen_en_rapid_con_su_tipo():
    for nombre, definicion in _tablas()["VARIABLES"].items():
        m = re.search(rf"PERS (bool|num|string) {nombre} := ", MODULO)
        assert m, f"MOD_CajaPinza.mod no declara PERS {nombre}"
        assert m.group(1) == definicion["tipo"], f"{nombre}: la app lo lee como {definicion['tipo']} y RAPID lo declara {m.group(1)}"


@requiere_node
def test_las_constantes_de_la_app_son_las_de_rapid():
    t = _tablas()
    const = {n: int(v) for n, v in re.findall(r"CONST num (\w+) := (-?\d+);", MODULO)}
    assert t["MAX_CAJAS"] == const["maxCajas"]
    assert t["N_GIROS"] == const["nGiros"]
    assert t["GIRO_MIN"] == const["giroMin"]
    assert t["GIRO_PASO"] == const["giroPaso"]
    assert t["SIN_GIRO"] == const["sinGiro"]
    assert re.search(rf"MODULE {t['MODULO']}\b", MODULO)
    assert t["TAREA"] == "T_ROB1"  # las PERS se leen en la tarea con robot; T_COM las comparte


@requiere_node
def test_las_senales_que_muestra_la_app_existen_con_acceso_all():
    for nombre in _tablas()["SENALES"].values():
        assert re.search(rf'-Name "{nombre}" -SignalType "\w+" -Access "All"', EIO), f"{nombre} no esta en EIO.cfg con Access All"


@requiere_node
def test_la_lista_de_giros_de_la_app_es_la_que_calcula_rapid():
    # Mismo generador que MOD_CajaPinza.mod: se comprueba que el texto de RAPID sigue siendo este y que
    # la app (JavaScript) da lo mismo que una version en Python.
    assert "semilla := (semilla * 1021 + 11) MOD 8192;" in MODULO
    assert "k := ((semilla DIV 16) MOD nGiros) + 1;" in MODULO
    assert "IF indiceFijo >= 1 AND indiceFijo <= nGiros THEN" in MODULO

    def en_python(semilla, indice_fijo, n):
        salida, s = [], semilla
        for _ in range(n):
            s = (s * 1021 + 11) % 8192
            k = indice_fijo if 1 <= indice_fijo <= 12 else ((s // 16) % 12) + 1
            salida.append(-90 + (k - 1) * 15)
        return salida

    for caso in _tablas()["secuencias"]:
        assert caso["giros"] == en_python(caso["semilla"], caso["indiceFijo"], caso["n"]), caso


def test_rapid_espera_las_ordenes_de_la_app_y_las_devuelve_a_false():
    assert re.search(r"WaitUntil hmiIniciar;\s*hmiIniciar := FALSE;", MODULO)
    assert re.search(r"WaitUntil hmiCajaEnPosicion;\s*hmiCajaEnPosicion := FALSE;", MODULO)
    # la orden vieja no puede disparar la caja siguiente: se baja antes de esperar
    assert re.search(r"hmiCajaEnPosicion := FALSE;\s*hmiFase := FASE_ESPERA_CAJA;", MODULO)


def test_rapid_contesta_a_los_mensajes_nuevos_del_pc():
    ciclo = (RAIZ / "celda" / "ciclo.py").read_text(encoding="utf-8")
    assert 'orden = "lote"' in MODULO and '_preguntar("lote")' in ciclo
    assert 'StrPart(orden, 1, 5) = "giro:"' in MODULO and 'f"giro:{' in ciclo
    for respuesta in ('"giro_ok"', '"giro_mal"', '"lote:" + NumToStr(nCajas, 0) + ":sim"', '"lote:" + NumToStr(nCajas, 0) + ":real"'):
        assert respuesta in MODULO
    assert '"giro_ok"' in ciclo


def test_sintaxis_basica_del_modulo_rapid():
    """No sustituye a compilar en RobotStudio, pero caza lo tipico: bloques sin cerrar, cadenas de mas de
    80 caracteres, identificadores de mas de 32 o caracteres que no son ASCII."""
    assert MODULO.isascii()

    def sin_comentario(linea: str) -> str:
        salida, dentro = [], False
        for ch in linea:
            if ch == '"':
                dentro = not dentro
            if ch == "!" and not dentro:
                break
            salida.append(ch)
        return "".join(salida)

    cierres = {"IF": "ENDIF", "FOR": "ENDFOR", "WHILE": "ENDWHILE", "TEST": "ENDTEST", "PROC": "ENDPROC",
               "FUNC": "ENDFUNC", "MODULE": "ENDMODULE"}
    pila = []
    for n, linea in enumerate(MODULO.splitlines(), start=1):
        t = sin_comentario(linea)
        texto = t.strip()
        m = re.match(r"(IF|FOR|WHILE|TEST|PROC|FUNC|MODULE)\b", texto)
        if m:
            pila.append((m.group(1), n))
        m = re.match(r"(ENDIF|ENDFOR|ENDWHILE|ENDTEST|ENDPROC|ENDFUNC|ENDMODULE)\b", texto)
        if m:
            assert pila, f"linea {n}: {m.group(1)} de mas"
            abre, donde = pila.pop()
            assert cierres[abre] == m.group(1), f"linea {n}: {m.group(1)} cierra el {abre} de la linea {donde}"
        for cadena in re.findall(r'"([^"]*)"', t):
            assert len(cadena) <= 80, f"linea {n}: cadena de {len(cadena)} caracteres (maximo 80)"
        for ident in re.findall(r"\b[A-Za-z_]\w*\b", t):
            assert len(ident) <= 32, f"linea {n}: identificador {ident} de mas de 32 caracteres"
    assert pila == []


# ---------------------------------------------------------------- la carpeta de la app
def test_appinfo_apunta_a_ficheros_que_existen():
    raiz = ET.parse(APP / "appinfo.xml").getroot()
    assert raiz.tag == "WebApp"
    assert raiz.findtext("name")
    for etiqueta in ("icon", "path"):
        assert (APP / raiz.findtext(etiqueta)).is_file(), etiqueta


def test_index_html_solo_carga_ficheros_que_existen_y_app_js_solo_usa_ids_que_existen():
    html = (APP / "index.html").read_text(encoding="utf-8")
    for ruta in re.findall(r'(?:src|href)="([^"]+)"', html):
        assert (APP / ruta).is_file(), f"index.html carga {ruta} y no esta"
    # las hojas de estilo que cargan por su cuenta los componentes de ABB
    for js in (APP / "fp-components").glob("*.js"):
        for css in re.findall(r'fpComponentsLoadCSS\("([^"]+)"\)', js.read_text(encoding="utf-8")):
            assert (APP / css).is_file(), f"{js.name} carga {css} y no esta"
    ids = set(re.findall(r'id="([^"]+)"', html))
    app = (APP / "app.js").read_text(encoding="utf-8")
    usados = set(re.findall(r"\$\('([\w-]+)'\)", app)) | set(re.findall(r"attachToId\('([\w-]+)'\)", app))
    assert usados <= ids, f"app.js usa ids que index.html no tiene: {sorted(usados - ids)}"


def test_la_app_no_pide_a_rapid_nada_que_no_este_en_la_tabla_de_variables():
    app = (APP / "app.js").read_text(encoding="utf-8")
    logica = (APP / "logica.js").read_text(encoding="utf-8")
    declaradas = set(re.findall(r"^\s{8}(\w+):\s+\{tipo:", logica, flags=re.M))
    pedidas = set(re.findall(r"(?:orden|ajustar|escribir)\('(\w+)'", app))
    assert pedidas and pedidas <= declaradas, sorted(pedidas - declaradas)


# ---------------------------------------------------------------- JavaScript con Node
@requiere_node
def test_sintaxis_de_los_ficheros_javascript_de_la_app():
    for nombre in ("logica.js", "app.js", "demo-rws.js"):
        exe = _node()
        r = subprocess.run([exe, "--check", _ruta(exe, APP / nombre)], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, f"{nombre}: {r.stderr}"


@requiere_node
def test_logica_de_la_app_en_node():
    r = _lanzar(JS / "logica.test.js")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]
    assert re.search(r"(ℹ fail 0|# fail 0)\b", r.stdout), r.stdout[-2000:]


def _carpeta_jsdom():
    if os.environ.get("CAJAPINZA_JSDOM"):
        return os.environ["CAJAPINZA_JSDOM"]
    if (JS / "node_modules" / "jsdom").is_dir():
        return str(JS)
    return None


@requiere_node
def test_pantalla_de_la_app_en_jsdom_contra_un_rapid_simulado():
    carpeta = _carpeta_jsdom()
    if carpeta is None:
        pytest.skip("sin jsdom: npm install en robotica/tests/js, o CAJAPINZA_JSDOM con la carpeta que tenga node_modules/jsdom")
    r = _lanzar(JS / "app.test.js", carpeta)
    if "JSDOM_NO_DISPONIBLE" in r.stdout:
        pytest.skip("jsdom no se encuentra en " + carpeta)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-1000:]
    assert re.search(r"(ℹ fail 0|# fail 0)\b", r.stdout), r.stdout[-3000:]
    assert not re.search(r"(ℹ|#) pass 0\b", r.stdout)


# ---------------------------------------------------------------- mesa de deposito
def test_los_valores_por_defecto_de_la_mesa_y_los_limites_son_los_de_rapid_y_el_pc():
    from celda.config import Config, cargar
    por_defecto = {n: float(v) for n, v in re.findall(r"PERS num (mesa\w+|egmMaxPos|alcanceMax) := (-?\d+);", MODULO)}
    assert set(por_defecto) == {"mesaX0", "mesaY0", "mesaLargo", "mesaAncho", "mesaZ", "mesaHueco", "egmMaxPos", "alcanceMax"}
    cfg = cargar(RAIZ / "celda" / "config_celda.json")
    assert por_defecto["mesaZ"] == cfg.z_mesa                    # la superficie de la mesa de la simulacion
    assert por_defecto["egmMaxPos"] == Config.__dataclass_fields__["desviacion_egm_max"].default
    assert por_defecto["alcanceMax"] == Config.__dataclass_fields__["alcance_max"].default
    assert cfg.ventana_semiancho == por_defecto["egmMaxPos"] - 100.0   # 1400 con el limite de 1500
    assert "\\MaxPosDeviation:=egmMaxPos" in MODULO                 # el EGM usa el mismo valor que el PC
    # la zona por defecto es la mesa_marron de la estacion colocada en (-700, 350, 500) mm del mundo:
    # x de -900 a 300 e y de 150 a 1150 respecto a la base (que esta en 200, 200, 200 mm)
    assert por_defecto["mesaX0"] + por_defecto["mesaLargo"] == 300 and por_defecto["mesaY0"] + por_defecto["mesaAncho"] == 1150
    assert (por_defecto["mesaX0"] + 200, por_defecto["mesaY0"] + 200) == (-700, 350)


@requiere_node
def test_las_constantes_de_la_app_para_la_mesa_son_las_de_rapid_y_la_configuracion():
    t = _tablas()
    rapid = {n: float(v) for n, v in re.findall(r"PERS num (mesa\w+) := (-?\d+);", MODULO)}
    assert t["MESA_SIM"] == rapid
    caja = {n: float(v) for n, v in re.findall(r"PERS num (caja(?:Largo|Ancho|Alto)) := (\d+);", MODULO)}
    assert t["CAJA_SIM"] == caja
    cfg = json.loads((RAIZ / "celda" / "config_celda.json").read_text(encoding="utf-8"))
    puente = json.loads((RAIZ / "puente_egm" / "config.celda.json").read_text(encoding="utf-8"))["sesiones"][0]["espacio_mm"]
    pc = t["PC"]
    assert pc["inicio"] == cfg["ventana_egm"]["inicio_mm"]
    assert (pc["zCinta"], pc["zSeguro"], pc["margen"], pc["tcp"]) == (
        cfg["celda"]["z_cinta"], cfg["celda"]["z_seguro"], cfg["celda"]["margen_aproximacion"], cfg["celda"]["largo_herramienta_mm"])
    assert (pc["puente"]["x"], pc["puente"]["y"], pc["puente"]["z"]) == (puente["x"], puente["y"], puente["z"])


@requiere_node
def test_el_reparto_de_la_app_es_el_que_hace_el_pc_con_cajas_de_medidas_distintas():
    """La app (JavaScript) y el PC (Python) reparten la mesa igual, caja a caja: si no, la app diria que caben cajas que
    el PC luego se niega a dejar."""
    from dataclasses import replace

    from celda.config import cargar
    from celda.percepcion import Caja
    from celda.planificacion import Mesa, Reparto, SinSitio

    base = cargar(RAIZ / "celda" / "config_celda.json")
    for caso in _tablas()["repartos"]:
        cfg = replace(base, desviacion_egm_max=caso["egm"], alcance_max=caso["alcance"], ventana_semiancho=caso["egm"] - 100.0)
        mesa = Mesa(caso["mesaX0"], caso["mesaY0"], caso["mesaLargo"], caso["mesaAncho"], caso["mesaZ"], caso["mesaHueco"])
        reparto, pc, sin_sitio = Reparto(mesa), [], None
        for i, c in enumerate(caso["cajas"]):
            try:
                d = reparto.colocar(Caja(c["largo"], c["ancho"], c["alto"], 0.0), cfg)
            except SinSitio:
                sin_sitio = i
                break
            pc.append((d.x, d.y))
        assert sin_sitio == caso["sinSitio"], caso
        assert len(pc) == len(caso["destinos"]), caso
        for (x, y), (xj, yj) in zip(pc, caso["destinos"]):
            assert x == pytest.approx(xj, abs=1e-6) and y == pytest.approx(yj, abs=1e-6), caso
    # con el limite de RAPID (1000) caben 2 cajas de 200 mm en la mesa de la simulacion; con 1500, 5
    repartos = _tablas()["repartos"]
    assert [len(repartos[0]["destinos"]), len(repartos[1]["destinos"])] == [2, 5]


def test_todos_los_avisos_de_rapid_pasan_por_nota_y_asi_el_interruptor_de_mensajes_vale():
    """hmiMensajes apaga TPWrite: no puede quedar ninguno fuera de Nota."""
    tpwrite = [l for l in MODULO.splitlines() if re.match(r"\s*TPWrite\b", l)]
    assert len(tpwrite) == 1
    m = re.search(r"PROC Nota\(string texto\)\s*IF hmiMensajes THEN\s*TPWrite texto;\s*ENDIF\s*ENDPROC", MODULO)
    assert m, "Nota debe ser el unico sitio con TPWrite y estar condicionada a hmiMensajes"
    assert re.search(r"PROC Aviso\(string texto\)\s*hmiMensaje := texto;\s*Nota texto;", MODULO)


def test_la_pinza_espera_confirmacion_al_cerrar_y_al_abrir():
    """T_COM: cerrar pone PinzaCerrar a 1 y espera PinzaCerrada = 1; abrir lo pone a 0 y espera PinzaCerrada = 0
    (en simulacion lo baja el SmartComponent VacuumPen_SComp). En los dos casos, 3 s como maximo y fallo_pinza."""
    cerrar = MODULO.split('orden = "cerrar" THEN')[1].split('ELSEIF orden = "abrir"')[0]
    abrir = MODULO.split('ELSEIF orden = "abrir" THEN')[1].split('ELSEIF orden = "fin_caja"')[0]
    assert "SetDO PinzaCerrar, 1;" in cerrar and "WaitDI PinzaCerrada, 1 \\MaxTime:=3 \\TimeFlag:=fallo;" in cerrar
    assert "SetDO PinzaCerrar, 0;" in abrir and "WaitDI PinzaCerrada, 0 \\MaxTime:=3 \\TimeFlag:=fallo;" in abrir
    assert abrir.index("SetDO PinzaCerrar, 0;") < abrir.index("WaitDI PinzaCerrada, 0")
    assert 'SocketSend sock \\Str:="fallo_pinza";' in abrir and 'SocketSend sock \\Str:="abierta";' in abrir
    assert abrir.index("fallo_pinza") < abrir.index('"abierta"')
