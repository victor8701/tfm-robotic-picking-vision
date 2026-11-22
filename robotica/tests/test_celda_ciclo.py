"""Ciclo completo de la celda contra un puente falso (sigue cada objetivo al instante) y un RAPID
falso (cliente de socket que contesta como T_COM). Dos cajas."""
import json
import socket
import time
import threading

import numpy as np
import pytest

from celda.ciclo import Celda
from celda.config import Config
from celda.percepcion import FuenteCsv
from celda.socket_rapid import ServidorRapid
from robotica_bimanual.cliente_puente import ClientePuente  # ruta añadida por celda.ciclo


class PuenteFalso:
    """Puente de mentira. Los datagramas EGM 'suben' solo mientras hay una sesion activa."""

    def __init__(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(4)
        self.puerto = self._srv.getsockname()[1]
        self.egm = False
        self.ciclos = 0
        self.real_t = [600.0, -6.5, 740.0]
        self.real_q = [0.0, 0.0, 1.0, 0.0]
        self.objetivos: list[tuple] = []
        self.orientaciones: list[tuple] = []
        self._cerrado = False
        threading.Thread(target=self._aceptar, daemon=True).start()

    def _aceptar(self):
        while not self._cerrado:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._atender, args=(conn,), daemon=True).start()

    def _atender(self, conn):
        f = conn.makefile("rwb")
        for linea in f:
            d = json.loads(linea.decode("utf-8"))
            if d["cmd"] == "estado":
                if self.egm:
                    self.ciclos += 5
                resp = {"ok": True, "sesion": "brazo1", "estado": "activo" if self.egm else "esperando",
                        "codigo": "", "ciclos": self.ciclos, "errores": 0, "desviacion_mm": 0.0,
                        "real": {"t": self.real_t, "q": self.real_q},
                        "referencia": {"t": self.real_t, "q": self.real_q}}
            elif d["cmd"] == "objetivo":
                self.real_t = list(d["t"])
                self.real_q = list(d["q"])
                self.objetivos.append(tuple(d["t"]))
                self.orientaciones.append(tuple(d["q"]))
                resp = {"ok": True}
            else:
                resp = {"ok": False}
            f.write((json.dumps(resp) + "\n").encode("utf-8"))
            f.flush()

    def cerrar(self):
        self._cerrado = True
        self._srv.close()


# Zona de la mesa que "tiene" la app en los tests: x0, y0, largo, ancho, z, hueco, egmMaxPos, alcanceMax
MESA_PRUEBA = "-100.0:100.0:500.0:500.0:150.0:20.0:1000:790"
# Ajustes de puesta en marcha que "tiene" la app (los de la configuracion de prueba: recogida en (400, 0), z_cinta 300,
# margen 150, TCP 147 y punto seguro (600, -6.5, 740)): recogida, agarre y celda
AJUSTES_PRUEBA = {
    "recogida": "recogida:0:400.0:0.0:50.0:50.0:0.0:0.0:0.0:5.0",
    "agarre": "agarre:0:50.0:30.0:10.0:10.0:0.0:0.0:0.0",
    "celda": "celda:300.0:150.0:147.0:600.0:-6.5:740.0:100.0:0.0",
}


def _rapid_falso_camara(s, mensajes, errores, camara):
    """Lo que hace T_COM con la camara de ensayo MIENTRAS el PC espera a que arranque la tanda: da la carpeta que haya elegido la app
    (camara['carpetas'], una por pregunta; la ultima se repite), guarda la lista (camara['lista']) y lo que el PC avise (camara['info']).
    Termina cuando ha llegado camara['infos'] avisos (por defecto 1) o pasan camara['max_s'] s. camara['mudo']: un modulo antiguo, que no contesta."""
    camara.setdefault("lista", {})
    camara.setdefault("info", [])
    preguntas = 0
    fin = time.time() + camara.get("max_s", 20.0)
    s.settimeout(0.05)
    while time.time() < fin and len(camara["info"]) < camara.get("infos", 1):
        try:
            datos = s.recv(256)
        except socket.timeout:
            continue
        if not datos:
            return
        orden = datos.decode("utf-8").strip()
        mensajes.append(orden)
        if camara.get("mudo"):
            continue
        if orden == "camara":
            carpetas = camara["carpetas"]
            s.sendall(f"camara:{carpetas[min(preguntas, len(carpetas) - 1)]}".encode("utf-8"))
            preguntas += 1
        elif orden.startswith("camara_lista:"):
            k, _, texto = orden[len("camara_lista:"):].partition(":")
            camara["lista"][int(k)] = texto
            s.sendall(b"camara_ok")
        elif orden.startswith("camara_info:"):
            n, _, estado = orden[len("camara_info:"):].partition(":")
            camara["info"].append((int(n), estado))
            s.sendall(b"camara_ok")
        else:
            errores.append(f"orden inesperada esperando la tanda: {orden!r}")
            return
    s.settimeout(20)


def _rapid_falso(puerto, puente, n_cajas, mensajes, errores, modo="sim", n_lote=None, sin_lote=False,
                 mesa=MESA_PRUEBA, depositos=None, mudo_en=None, fallo_pinza_en=None, ajustes=None, camara=None):
    """Cliente de socket que contesta como T_COM. n_lote y modo son lo que la app del FlexPendant dejo en
    nCajas y modoSimulacion; mesa, la zona de deposito; sin_lote imita un modulo antiguo, que no contesta a lote,
    mesa ni giro. depositos: se anota la pose del robot cuando llega 'abrir' (donde se suelta cada caja)."""
    s = socket.create_connection(("127.0.0.1", puerto), timeout=20)
    try:
        if camara is not None:
            _rapid_falso_camara(s, mensajes, errores, camara)
        for _ in range(n_cajas):
            puente.egm = True  # RAPID arranca la sesion EGM de la caja
            while True:
                orden = s.recv(256).decode("utf-8").strip()
                mensajes.append(orden)
                if mudo_en is not None and orden == mudo_en:
                    continue   # RAPID abortado: no contesta
                if fallo_pinza_en is not None and orden == fallo_pinza_en:
                    s.sendall(b"fallo_pinza")   # PinzaCerrada no cambio a tiempo
                    return
                if orden == "cerrar":
                    s.sendall(b"cerrada")
                elif orden == "abrir":
                    if depositos is not None:
                        depositos.append((tuple(puente.real_t), tuple(puente.real_q)))
                    s.sendall(b"abierta")
                elif orden == "fin_caja":
                    puente.egm = False  # EGMStop
                    s.sendall(b"fin_ok")
                    break
                elif orden == "lote" and not sin_lote:
                    s.sendall(f"lote:{n_lote if n_lote is not None else n_cajas}:{modo}".encode("utf-8"))
                elif orden == "mesa" and not sin_lote:
                    s.sendall(f"mesa:{mesa}".encode("utf-8"))
                elif orden in AJUSTES_PRUEBA and not sin_lote:
                    s.sendall((ajustes or AJUSTES_PRUEBA)[orden].encode("utf-8"))
                elif orden.startswith("giro:") and not sin_lote:
                    s.sendall(b"giro_ok")
                elif sin_lote and (orden in ("lote", "mesa", "recogida", "agarre", "celda") or orden.startswith("giro:")):
                    pass  # un modulo antiguo ignora lo que no conoce
                else:
                    errores.append(f"orden inesperada: {orden!r}")
                    return
        orden = s.recv(256).decode("utf-8").strip()
        mensajes.append(orden)
        if orden != "fin_programa":
            errores.append(f"se esperaba fin_programa y llego {orden!r}")
    except Exception as e:  # noqa: BLE001 - el fallo se comprueba en el test
        errores.append(repr(e))
    finally:
        s.close()


def _puerto_libre() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    return puerto


def test_ciclo_completo_con_dos_cajas(tmp_path):
    csv = tmp_path / "caja.csv"
    csv.write_text("150.0;100.0;120.0;30.0\n150.0;100.0;120.0;-60.0\n", encoding="utf-8")
    puente = PuenteFalso()
    cfg = Config(
        modo_simulacion=True, n_cajas=2, csv_caja=str(csv), puente_host="127.0.0.1", puente_puerto=puente.puerto,
        rapid_ip="127.0.0.1", rapid_puerto=_puerto_libre(), rapid_espera_s=10.0,
        z_cinta=300.0, z_mesa=150.0, z_seguro=600.0, margen_aproximacion=150.0,
        centro_recogida=(400.0, 0.0), mesa=(200.0, 400.0), eje_pinzado="y",
        periodo_s=0.001, tolerancia_pos=2.0, tolerancia_rot=0.02, max_iteraciones=5000,
        ventana_inicio=(600.0, -6.5, 740.0), ventana_semiancho=600.0,
    )
    rapid = ServidorRapid(cfg.rapid_ip, cfg.rapid_puerto, cfg.rapid_espera_s)
    mensajes: list[str] = []
    errores: list[str] = []
    hilo = threading.Thread(target=_rapid_falso, args=(cfg.rapid_puerto, puente, 2, mensajes, errores), daemon=True)
    hilo.start()
    cliente = ClientePuente(cfg.puente_host, cfg.puente_puerto, timeout_s=2.0)
    try:
        rapid.esperar_cliente()
        Celda(cfg, FuenteCsv(csv), cliente, rapid).ejecutar()
    finally:
        rapid.cerrar()
        cliente.cerrar()
        puente.cerrar()
    hilo.join(timeout=10)

    assert errores == []
    # lote una vez, al empezar la tanda; giro de cada caja antes de moverse
    assert mensajes == ["lote", "mesa", "recogida", "agarre", "celda", "giro:30.0", "cerrar", "abrir", "fin_caja",
                        "giro:-60.0", "cerrar", "abrir", "fin_caja", "fin_programa"]
    assert puente.objetivos
    # la pinza va con la brida: el primer objetivo es el TCP de seguridad sobre la recogida, 147 mm mas arriba
    assert puente.objetivos[0] == pytest.approx((400.0, 0.0, 600.0 + 147.0))
    for x, y, z in puente.objetivos:
        assert abs(x) <= 600.0 and abs(y) <= 600.0 and 0.0 <= z <= 800.0


def test_el_numero_de_cajas_lo_marca_caja_csv_y_no_n_cajas_del_pc(tmp_path):
    # RAPID hizo 5 cajas con n_cajas = 1 en el PC: el PC solo agarraba la primera y RAPID recorria las demas
    # sin PC, con las cajas apareciendo y desapareciendo en la cinta (16-nov). La cuenta sale de caja.csv.
    csv = tmp_path / "caja.csv"
    csv.write_text("200.0;200.0;200.0;-75.0\n200.0;200.0;200.0;30.0\n200.0;200.0;200.0;60.0\n", encoding="utf-8")
    puente = PuenteFalso()
    cfg = Config(
        modo_simulacion=True, n_cajas=1, csv_caja=str(csv), puente_host="127.0.0.1", puente_puerto=puente.puerto,
        rapid_ip="127.0.0.1", rapid_puerto=_puerto_libre(), rapid_espera_s=10.0,
        z_cinta=300.0, z_mesa=150.0, z_seguro=600.0, margen_aproximacion=150.0,
        centro_recogida=(400.0, 0.0), mesa=(200.0, 400.0), eje_pinzado="y",
        periodo_s=0.001, tolerancia_pos=2.0, tolerancia_rot=0.02, max_iteraciones=5000,
        ventana_inicio=(600.0, -6.5, 740.0), ventana_semiancho=600.0,
    )
    rapid = ServidorRapid(cfg.rapid_ip, cfg.rapid_puerto, cfg.rapid_espera_s)
    mensajes: list[str] = []
    errores: list[str] = []
    hilo = threading.Thread(target=_rapid_falso, args=(cfg.rapid_puerto, puente, 3, mensajes, errores), daemon=True)
    hilo.start()
    cliente = ClientePuente(cfg.puente_host, cfg.puente_puerto, timeout_s=2.0)
    try:
        rapid.esperar_cliente()
        Celda(cfg, FuenteCsv(csv), cliente, rapid).ejecutar()
    finally:
        rapid.cerrar()
        cliente.cerrar()
        puente.cerrar()
    hilo.join(timeout=10)

    assert errores == []
    assert mensajes == ["lote", "mesa", "recogida", "agarre", "celda", "giro:-75.0", "cerrar", "abrir", "fin_caja",
                        "giro:30.0", "cerrar", "abrir", "fin_caja",
                        "giro:60.0", "cerrar", "abrir", "fin_caja", "fin_programa"]


def test_sin_fuente_con_total_manda_n_cajas_de_la_configuracion():
    # la camara no sabe cuantas cajas vendran: sin 'lote' se usa n_cajas
    from celda.percepcion import FuenteCamara
    assert FuenteCamara().total() is None


def _cfg(tmp_path, puente, **cambios):
    base = dict(
        modo_simulacion=True, n_cajas=1, csv_caja=str(tmp_path / "caja.csv"), puente_host="127.0.0.1",
        puente_puerto=puente.puerto, rapid_ip="127.0.0.1", rapid_puerto=_puerto_libre(), rapid_espera_s=10.0,
        z_cinta=300.0, z_mesa=150.0, z_seguro=600.0, margen_aproximacion=150.0,
        centro_recogida=(400.0, 0.0), mesa=(200.0, 400.0), eje_pinzado="y",
        periodo_s=0.001, tolerancia_pos=2.0, tolerancia_rot=0.02, max_iteraciones=5000,
        ventana_inicio=(600.0, -6.5, 740.0), ventana_semiancho=600.0,
    )
    base.update(cambios)
    return Config(**base)


def _ejecutar(cfg, puente, fuente, n_cajas_rapid, **rapid_kw):
    """Corre el PC contra el RAPID falso. Devuelve (mensajes, errores_del_rapid_falso, excepcion_del_pc)."""
    rapid = ServidorRapid(cfg.rapid_ip, cfg.rapid_puerto, cfg.rapid_espera_s)
    mensajes: list[str] = []
    errores: list[str] = []
    hilo = threading.Thread(target=_rapid_falso, args=(cfg.rapid_puerto, puente, n_cajas_rapid, mensajes, errores),
                            kwargs=rapid_kw, daemon=True)
    hilo.start()
    cliente = ClientePuente(cfg.puente_host, cfg.puente_puerto, timeout_s=2.0)
    excepcion = None
    try:
        rapid.esperar_cliente()
        Celda(cfg, fuente, cliente, rapid).ejecutar()
    except Exception as e:  # noqa: BLE001 - se devuelve para comprobarla
        excepcion = e
    finally:
        rapid.cerrar()
        cliente.cerrar()
        puente.cerrar()
    hilo.join(timeout=10)
    return mensajes, errores, excepcion


def test_la_tanda_de_la_app_manda_en_real_aunque_el_pc_tenga_otro_n_cajas(tmp_path):
    # Sin camara que cuente (total() = None) el PC se fiaba de n_cajas de su configuracion; ahora la cuenta es
    # la que la app dejo en nCajas de RAPID. Fuente sin total() = lo que hara la camara.
    from celda.percepcion import Caja

    class FuenteSinTotal:
        def leer(self, i):
            return Caja(200.0, 200.0, 200.0, 15.0 * i)

        def total(self):
            return None

    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False, n_cajas=1)
    mensajes, errores, excepcion = _ejecutar(cfg, puente, FuenteSinTotal(), 3, modo="real", n_lote=3)
    assert excepcion is None and errores == []
    assert mensajes == ["lote", "mesa", "recogida", "agarre", "celda", "giro:0.0", "cerrar", "abrir", "fin_caja",
                        "giro:15.0", "cerrar", "abrir", "fin_caja",
                        "giro:30.0", "cerrar", "abrir", "fin_caja", "fin_programa"]


def test_el_pc_se_niega_si_su_modo_no_es_el_de_rapid(tmp_path):
    # La app puede poner RAPID en real mientras el PC lee caja.csv (simulacion): leeria un fichero que RAPID no
    # ha escrito en esta tanda.
    csv = tmp_path / "caja.csv"
    csv.write_text("200.0;200.0;200.0;0.0\n", encoding="utf-8")
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    mensajes, _, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 1, modo="real", n_lote=1)
    assert isinstance(excepcion, RuntimeError)
    assert "real" in str(excepcion) and "simulacion" in str(excepcion)
    # no llega a mover nada (el '' del final es el cierre del socket que ve el RAPID falso)
    assert mensajes[0] == "lote" and not [m for m in mensajes if m.startswith("giro") or m == "cerrar"]
    assert puente.objetivos == []


def test_el_pc_se_niega_si_caja_csv_no_es_de_la_tanda_de_rapid(tmp_path):
    # caja.csv con 2 cajas (de una tanda anterior) y la app dejo nCajas = 3
    csv = tmp_path / "caja.csv"
    csv.write_text("200.0;200.0;200.0;0.0\n200.0;200.0;200.0;15.0\n", encoding="utf-8")
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    _, _, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 3, modo="sim", n_lote=3)
    assert isinstance(excepcion, RuntimeError)
    assert "caja.csv" in str(excepcion) and "3" in str(excepcion)


def test_un_rapid_antiguo_sin_lote_da_un_error_claro_y_no_cuelga_al_pc(tmp_path, monkeypatch):
    csv = tmp_path / "caja.csv"
    csv.write_text("200.0;200.0;200.0;0.0\n", encoding="utf-8")
    monkeypatch.setattr(Celda, "ESPERA_PREGUNTA_S", 0.3)
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    _, _, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 1, sin_lote=True)
    assert isinstance(excepcion, RuntimeError)
    assert "MOD_CajaPinza" in str(excepcion) and "lote" in str(excepcion)


def test_cajas_de_medidas_distintas_se_dejan_ordenadas_alineadas_y_sin_solaparse(tmp_path):
    from celda.planificacion import orientacion_pinza
    from nucleo.geometria import a_matriz

    medidas = [(150.0, 100.0, 120.0, 30.0), (120.0, 80.0, 90.0, -60.0), (100.0, 100.0, 150.0, 0.0), (140.0, 60.0, 100.0, 75.0)]
    csv = tmp_path / "caja.csv"
    csv.write_text("".join(f"{l};{a};{h};{g}\n" for l, a, h, g in medidas), encoding="utf-8")
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    depositos: list = []
    _, errores, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 4, depositos=depositos)
    assert excepcion is None and errores == [] and len(depositos) == 4
    alineada = a_matriz(orientacion_pinza(0.0, "y"))
    rects = []
    for (t, q), (largo, ancho, _alto, _giro) in zip(depositos, medidas):
        assert np.allclose(a_matriz(np.array(q)), alineada, atol=0.05)          # todas sin girar, vinieran como vinieran
        rects.append((t[0] - largo / 2, t[0] + largo / 2, t[1] - ancho / 2, t[1] + ancho / 2))
    for i, (x1, x2, y1, y2) in enumerate(rects):
        for (u1, u2, v1, v2) in rects[i + 1:]:
            assert u1 >= x2 + 19.9 or x1 >= u2 + 19.9 or v1 >= y2 + 19.9 or y1 >= v2 + 19.9   # hueco de 20 mm


def test_si_la_tanda_no_cabe_en_la_mesa_se_para_antes_de_mover_nada(tmp_path):
    csv = tmp_path / "caja.csv"
    csv.write_text("300.0;300.0;100.0;0.0\n300.0;300.0;100.0;0.0\n300.0;300.0;100.0;0.0\n", encoding="utf-8")
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    _, _, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 3)
    assert isinstance(excepcion, RuntimeError)
    assert "La caja 2 de 3 no cabe en la mesa" in str(excepcion)
    assert puente.objetivos == []


class PuenteEstancado:
    """El robot ha dejado de enviar datagramas EGM (ABORTAR, Stop...): ciclos no avanza."""

    def estado(self):
        return {"estado": "activo", "ciclos": 100, "real": {"t": [0.0, 0.0, 700.0], "q": [0.0, 0.0, 1.0, 0.0]}}

    def objetivo(self, _pose):
        return {"ok": True}


def test_si_el_egm_se_para_el_pc_lo_detecta_en_segundos_y_no_agota_las_iteraciones(tmp_path, monkeypatch):
    from celda.planificacion import Tramo, _pose
    from nucleo.geometria import Pose  # noqa: F401

    monkeypatch.setattr(Celda, "ESPERA_EGM_PARADO_S", 0.2)
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    celda = Celda(cfg, None, PuenteEstancado(), None)
    q = np.array([0.0, 0.0, 1.0, 0.0])
    with pytest.raises(RuntimeError, match="dejado de enviar datagramas EGM"):
        celda._seguir(Tramo("transporte", (_pose(400.0, 0.0, 600.0, q),), None))
    puente.cerrar()


def test_si_rapid_no_contesta_se_dice_en_vez_de_esperar_para_siempre(tmp_path, monkeypatch):
    csv = tmp_path / "caja.csv"
    csv.write_text("150.0;100.0;120.0;30.0\n", encoding="utf-8")
    monkeypatch.setattr(Celda, "ESPERA_RESPUESTA_S", 0.3)
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    _, _, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 1, mudo_en="cerrar")
    assert isinstance(excepcion, RuntimeError) and "no ha contestado a 'cerrar'" in str(excepcion)


def test_el_pc_muestra_cada_orden_de_pinza_y_su_confirmacion(tmp_path, capsys):
    csv = tmp_path / "caja.csv"
    csv.write_text("150.0;100.0;120.0;30.0\n150.0;100.0;120.0;-60.0\n", encoding="utf-8")
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    _, errores, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 2)
    assert errores == [] and excepcion is None
    lineas = [l for l in capsys.readouterr().out.splitlines() if l.startswith("Pinza:")]
    # dos cajas: cerrar y abrir en cada una, con lo que contesto RAPID y lo que tardo
    assert [l.split(" (")[0] for l in lineas] == ["Pinza: cerrar -> cerrada", "Pinza: abrir -> abierta"] * 2
    assert all(l.endswith(" s)") for l in lineas)


def test_si_la_pinza_no_confirma_la_apertura_el_error_lo_dice(tmp_path):
    csv = tmp_path / "caja.csv"
    csv.write_text("150.0;100.0;120.0;30.0\n", encoding="utf-8")
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    _, _, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 1, fallo_pinza_en="abrir")
    assert isinstance(excepcion, RuntimeError)
    assert "fallo_pinza" in str(excepcion) and "apertura" in str(excepcion) and "'abrir'" in str(excepcion)


def test_si_la_pinza_no_confirma_el_agarre_el_error_lo_dice(tmp_path):
    csv = tmp_path / "caja.csv"
    csv.write_text("150.0;100.0;120.0;30.0\n", encoding="utf-8")
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    _, _, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 1, fallo_pinza_en="cerrar")
    assert isinstance(excepcion, RuntimeError)
    assert "fallo_pinza" in str(excepcion) and "agarre" in str(excepcion) and "'cerrar'" in str(excepcion)


# ---------------------------------------------------------------- puesta en marcha: recogida, agarre, velocidad
from celda.percepcion import Caja  # noqa: E402
from nucleo.geometria import Pose  # noqa: E402


class _FuenteReal:
    """Lo que hara la camara: medidas y giro de cada caja y, si se le pide, su posicion."""

    def __init__(self, centro=None, alto=120.0, ancho=100.0):
        self._centro, self._alto, self._ancho = centro, alto, ancho

    def leer(self, i):
        return Caja(200.0, self._ancho, self._alto, 0.0, self._centro)

    def total(self):
        return None


def _ajustes(**cambios):
    """AJUSTES_PRUEBA con campos cambiados: recogida, agarre y celda ya como texto de RAPID."""
    a = dict(AJUSTES_PRUEBA)
    a.update(cambios)
    return a


def test_recogida_fija_en_real_manda_el_punto_de_la_app_para_todas_las_cajas(tmp_path):
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False)
    ajustes = _ajustes(recogida="recogida:0:500.0:100.0:50.0:50.0:0.0:0.0:0.0:5.0")
    _, errores, excepcion = _ejecutar(cfg, puente, _FuenteReal(centro=(430.0, -20.0)), 1, modo="real", ajustes=ajustes)
    assert excepcion is None and errores == []
    # el primer objetivo es el punto seguro sobre la recogida de la app (la camara no cuenta en modo fija), en brida
    assert puente.objetivos[0] == pytest.approx((500.0, 100.0, 600.0 + 147.0))


def test_recogida_con_camara_usa_su_punto_mas_la_correccion_y_corrige_el_giro(tmp_path):
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False)
    ajustes = _ajustes(recogida="recogida:1:500.0:100.0:50.0:50.0:-10.0:5.0:7.0:5.0")
    mensajes, errores, excepcion = _ejecutar(cfg, puente, _FuenteReal(centro=(520.0, 90.0)), 1, modo="real", ajustes=ajustes)
    assert excepcion is None and errores == []
    assert puente.objetivos[0] == pytest.approx((510.0, 95.0, 600.0 + 147.0))   # 520 - 10, 90 + 5
    assert "giro:7.0" in mensajes   # el giro que lee la camara (0) mas camaraOffsetGiro


def test_con_camara_una_caja_fuera_de_la_zona_permitida_no_se_mueve(tmp_path):
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False)
    ajustes = _ajustes(recogida="recogida:1:500.0:100.0:30.0:30.0:0.0:0.0:0.0:5.0")
    _, _, excepcion = _ejecutar(cfg, puente, _FuenteReal(centro=(560.0, 100.0)), 1, modo="real", ajustes=ajustes)
    assert isinstance(excepcion, RuntimeError)
    assert "fuera de la zona permitida" in str(excepcion) and "no me muevo" in str(excepcion)
    assert puente.objetivos == []


def test_con_camara_sin_posicion_el_pc_se_para_y_no_usa_el_punto_fijo(tmp_path):
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False)
    ajustes = _ajustes(recogida="recogida:1:500.0:100.0:50.0:50.0:0.0:0.0:0.0:5.0")
    _, _, excepcion = _ejecutar(cfg, puente, _FuenteReal(centro=None), 1, modo="real", ajustes=ajustes)
    assert isinstance(excepcion, RuntimeError) and "no ha dado la posicion" in str(excepcion)
    assert puente.objetivos == []


def test_una_caja_que_la_pinza_no_puede_agarrar_se_rechaza_antes_de_mover_nada(tmp_path):
    csv = tmp_path / "caja.csv"
    csv.write_text("150.0;100.0;120.0;30.0\n", encoding="utf-8")
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    ajustes = _ajustes(agarre="agarre:0:50.0:30.0:10.0:10.0:90.0:0.0:0.0")   # abre 90 mm y la caja mide 100 de ancho
    _, _, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 1, ajustes=ajustes)
    assert isinstance(excepcion, RuntimeError)
    assert "La caja 1 no se puede agarrar" in str(excepcion) and "aperturaPinza" in str(excepcion)
    assert puente.objetivos == []


def test_si_el_dedo_no_cabe_en_el_hueco_entre_cajas_se_dice(tmp_path):
    csv = tmp_path / "caja.csv"
    csv.write_text("150.0;100.0;120.0;30.0\n", encoding="utf-8")
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    ajustes = _ajustes(agarre="agarre:0:50.0:30.0:10.0:10.0:0.0:35.0:0.0")   # dedo de 35 mm y mesaHueco de 20
    _, _, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 1, ajustes=ajustes)
    assert isinstance(excepcion, RuntimeError) and "grosorDedo" in str(excepcion) and "mesaHueco" in str(excepcion)
    assert puente.objetivos == []


def test_ajustes_de_la_celda_fuera_de_rango_se_rechazan(tmp_path):
    csv = tmp_path / "caja.csv"
    csv.write_text("150.0;100.0;120.0;30.0\n", encoding="utf-8")
    for celda in ("celda:300.0:150.0:147.0:600.0:-6.5:740.0:150.0:0.0",     # velocidad por encima del tope del puente
                  "celda:300.0:150.0:0.0:600.0:-6.5:740.0:100.0:0.0"):      # tcpZ = 0
        puente = PuenteFalso()
        _, _, excepcion = _ejecutar(_cfg(tmp_path, puente), puente, FuenteCsv(csv), 1, ajustes=_ajustes(celda=celda))
        assert isinstance(excepcion, RuntimeError) and "Ajustes de la celda no validos" in str(excepcion)


def test_los_ajustes_de_rapid_llegan_a_la_configuracion_del_pc(tmp_path):
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente)
    rapid = ServidorRapid(cfg.rapid_ip, cfg.rapid_puerto, cfg.rapid_espera_s)
    ajustes = _ajustes(recogida="recogida:1:650.0:-30.0:40.0:60.0:2.0:-3.0:5.0:8.0",
                       agarre="agarre:1:60.0:25.0:15.0:12.0:90.0:8.0:10.0",
                       celda="celda:250.0:70.0:160.0:580.0:-5.0:520.0:60.0:200.0")
    mensajes: list[str] = []
    errores: list[str] = []
    hilo = threading.Thread(target=_rapid_falso, args=(cfg.rapid_puerto, puente, 1, mensajes, errores),
                            kwargs={"ajustes": ajustes}, daemon=True)   # el falso sigue esperando ordenes; no importa
    # solo el apreton de manos: lote, mesa y ajustes
    celda = Celda(cfg, None, None, rapid)
    hilo.start()
    try:
        rapid.esperar_cliente()
        celda._sincronizar_lote()
    finally:
        rapid.cerrar()
        puente.cerrar()
    c = celda.cfg
    assert (c.recogida_modo, c.centro_recogida, c.recogida_tol) == ("camara", (650.0, -30.0), (40.0, 60.0))
    assert (c.camara_offset, c.camara_offset_giro, c.t_max_camara) == ((2.0, -3.0), 5.0, 8.0)
    assert (c.agarre_modo, c.agarre_porcentaje, c.agarre_hundimiento) == ("tapa", 60.0, 25.0)
    assert (c.agarre_minimo, c.solape_minimo, c.apertura_pinza, c.grosor_dedo, c.giro_pinza) == (15.0, 12.0, 90.0, 8.0, 10.0)
    assert (c.z_cinta, c.margen_aproximacion, c.largo_herramienta_mm) == (250.0, 70.0, 160.0)
    assert (c.ventana_inicio, c.velocidad, c.z_minima) == ((580.0, -5.0, 520.0), 60.0, 200.0)


def test_la_velocidad_limitada_avanza_como_mucho_a_velocidad_mm_s(tmp_path):
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, velocidad=50.0)
    celda = Celda(cfg, None, None, None)
    q = np.array([0.0, 0.0, 1.0, 0.0])
    origen, objetivo = Pose.crear(t=(0.0, 0.0, 0.0), q=q), Pose.crear(t=(100.0, 0.0, 0.0), q=q)
    for t, x in ((0.0, 0.0), (1.0, 50.0), (1.5, 75.0), (2.0, 100.0), (9.0, 100.0)):   # 100 mm a 50 mm/s = 2 s
        assert celda._paso_limitado(origen, objetivo, t).t[0] == pytest.approx(x)
    # sin movimiento no hay que esperar
    assert celda._paso_limitado(origen, origen, 0.0).t[0] == pytest.approx(0.0)
    puente.cerrar()


def test_con_velocidad_limitada_el_pc_avanza_por_pasos_y_llega_a_todos_los_puntos(tmp_path, monkeypatch):
    csv = tmp_path / "caja.csv"
    csv.write_text("150.0;100.0;120.0;30.0\n", encoding="utf-8")

    class RelojFalso:
        """Reloj que solo avanza al dormir: el seguimiento va a 25 pasos por segundo sin esperar de verdad."""
        t = 0.0

        @classmethod
        def monotonic(cls):
            return cls.t

        @classmethod
        def sleep(cls, s):
            cls.t += s

    monkeypatch.setattr("celda.ciclo.time", RelojFalso)
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, periodo_s=0.04)
    ajustes = _ajustes(celda="celda:300.0:150.0:147.0:600.0:-6.5:740.0:50.0:0.0")   # 50 mm/s
    _, errores, excepcion = _ejecutar(cfg, puente, FuenteCsv(csv), 1, ajustes=ajustes)
    assert excepcion is None and errores == []
    pasos = np.linalg.norm(np.diff(np.array(puente.objetivos), axis=0), axis=1)
    # cada orden de seguimiento avanza como mucho v x periodo = 2 mm (los saltos mayores son el cambio de un punto del
    # plan al siguiente, que sale de la pose real) y hay muchos pasos: no se manda el punto final de golpe
    assert len(pasos) > 100
    assert np.percentile(pasos, 90) <= 2.0 + 1e-6


# ---------------------------------------------------------------- real con camara: la deteccion de vision/ alimenta al ciclo
class _ListaFotogramas:
    def __init__(self, fotogramas):
        self._f = list(fotogramas)

    def siguiente(self):
        return self._f.pop(0) if self._f else None


def _fuente_camara(cajas, repetir=1, tiempo_max_s=1.0):
    from celda.percepcion import FuenteCamara
    from vision.escena import camara_cenital, escena, profundidad
    from vision.proveedores import Fotograma
    cam = camara_cenital(tam=(960, 720), altura_mm=650.0, centro_xy=(700.0, 0.0), z_plano=220.0)
    foto = Fotograma(escena(cam, cajas, z_plano=220.0), profundidad(cam, cajas, z_plano=220.0), "x")
    return FuenteCamara(_ListaFotogramas([foto] * repetir), cam, 220.0, params={"modo": "profundidad"}, tiempo_max_s=tiempo_max_s, pausa_s=0.01)


def _ajustes_camara(tol="50.0:50.0", t_max="1.0"):
    return _ajustes(recogida=f"recogida:1:700.0:0.0:{tol}:0.0:0.0:0.0:{t_max}", celda="celda:220.0:150.0:147.0:600.0:-6.5:740.0:100.0:0.0")


def test_en_real_con_camara_el_pc_va_a_donde_ve_la_caja_y_cuenta_el_giro_medido(tmp_path):
    from vision.escena import CajaSintetica
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False)
    fuente = _fuente_camara([CajaSintetica(200.0, 140.0, 120.0, 20.0, (712.0, 9.0))])
    mensajes, errores, excepcion = _ejecutar(cfg, puente, fuente, 1, modo="real", n_lote=1, ajustes=_ajustes_camara())
    assert excepcion is None and errores == []
    assert puente.objetivos[0] == pytest.approx((712.0, 9.0, 600.0 + 147.0), abs=1.0)   # el punto seguro sobre la caja que ve la camara
    giro = [m for m in mensajes if m.startswith("giro:")][0]
    assert float(giro.split(":")[1]) == pytest.approx(20.0, abs=1.0)


def test_en_real_con_camara_una_caja_fuera_de_la_zona_permitida_no_se_mueve(tmp_path):
    from vision.escena import CajaSintetica
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False)
    fuente = _fuente_camara([CajaSintetica(150.0, 100.0, 80.0, 0.0, (780.0, 0.0))])   # a 80 mm del punto de recogida
    _, _, excepcion = _ejecutar(cfg, puente, fuente, 1, modo="real", n_lote=1, ajustes=_ajustes_camara(tol="30.0:30.0"))
    assert isinstance(excepcion, RuntimeError) and "fuera de la zona permitida" in str(excepcion)
    assert puente.objetivos == []


def test_en_real_con_camara_la_espera_maxima_es_la_de_rapid_y_si_no_ve_nada_para(tmp_path):
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False)
    fuente = _fuente_camara([], repetir=2000, tiempo_max_s=30.0)    # el tiempo de la fuente no cuenta: manda el de RAPID (0.2 s)
    _, _, excepcion = _ejecutar(cfg, puente, fuente, 1, modo="real", n_lote=1, ajustes=_ajustes_camara(t_max="0.2"))
    assert isinstance(excepcion, RuntimeError) and "no ve ninguna caja entera en 0.2 s" in str(excepcion)
    assert puente.objetivos == []


# ---------------------------------------------------------------- carpeta de fotos de ensayo elegida en la app
@pytest.fixture
def juegos(tmp_path, monkeypatch):
    """Dos carpetas de fotos calibradas bajo una raiz (juego_a: 1 foto; juego_b: 2 fotos, de 200 y 190 mm de largo, giros 0 y 15 grados) y un PC
    que pregunta la carpeta cada 50 ms."""
    from test_celda_percepcion import _carpeta_con_fotos
    raiz = tmp_path / "fotos"
    _carpeta_con_fotos(raiz / "juego_a", n=1)
    _carpeta_con_fotos(raiz / "juego_b", n=2)
    monkeypatch.setattr(Celda, "ESPERA_CAMARA_S", 0.05)
    return raiz


def _fuente_de(raiz, nombre="juego_a"):
    from celda.percepcion import FuenteCamara
    from test_celda_percepcion import Z_CINTA, _cam
    from vision.proveedores import Carpeta
    return FuenteCamara(Carpeta(raiz / nombre), _cam(), Z_CINTA, params={"modo": "profundidad"}, tiempo_max_s=1.0, pausa_s=0.01)


def _giros(mensajes):
    return [m for m in mensajes if m.startswith("giro:")]


def test_la_carpeta_elegida_en_la_app_se_abre_y_se_le_dice_cuantas_fotos_tiene(tmp_path, juegos):
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False, camara={"raiz_carpetas": str(juegos)})
    camara = {"carpetas": ["juego_b"]}
    mensajes, errores, excepcion = _ejecutar(cfg, puente, _fuente_de(juegos), 2, modo="real", n_lote=2, ajustes=_ajustes_camara(), camara=camara)
    assert excepcion is None and errores == []
    assert camara["lista"] == {1: "juego_a;juego_b", 2: "", 3: ""}              # la lista de carpetas que da el PC
    assert camara["info"] == [(2, "ok")]                                         # N.o de fotos de la carpeta elegida
    assert _giros(mensajes) == ["giro:0.0", "giro:15.0"]                         # las dos cajas son de juego_b (juego_a solo tiene una)


def test_si_la_app_vuelve_a_la_del_pc_el_pc_vuelve_a_su_origen(tmp_path, juegos):
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False, camara={"raiz_carpetas": str(juegos)})
    camara = {"carpetas": ["juego_b", ""], "infos": 2}
    mensajes, errores, excepcion = _ejecutar(cfg, puente, _fuente_de(juegos), 1, modo="real", n_lote=1, ajustes=_ajustes_camara(), camara=camara)
    assert excepcion is None and errores == []
    assert camara["info"] == [(2, "ok"), (1, "la de la configuracion: carpeta juego_a")]
    assert _giros(mensajes) == ["giro:0.0"]                                      # otra vez juego_a, de una sola foto


def test_una_carpeta_que_no_esta_en_la_lista_no_se_abre_ni_se_sale_de_la_raiz(tmp_path, juegos):
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False, camara={"raiz_carpetas": str(juegos)})
    camara = {"carpetas": ["../../etc"]}
    mensajes, errores, excepcion = _ejecutar(cfg, puente, _fuente_de(juegos), 1, modo="real", n_lote=1, ajustes=_ajustes_camara(), camara=camara)
    assert excepcion is None and errores == []
    assert camara["info"] == [(0, "no esta en la lista")]
    assert _giros(mensajes) == ["giro:0.0"]                                      # se sigue con la camara de la configuracion


def test_un_rapid_antiguo_sin_estos_mensajes_no_para_el_ciclo(tmp_path, juegos, monkeypatch, capsys):
    monkeypatch.setattr(Celda, "ESPERA_PREGUNTA_S", 0.3)
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False, camara={"raiz_carpetas": str(juegos)})
    camara = {"mudo": True, "max_s": 2.0}
    mensajes, errores, excepcion = _ejecutar(cfg, puente, _fuente_de(juegos), 1, modo="real", n_lote=1, ajustes=_ajustes_camara(), camara=camara)
    assert excepcion is None and errores == []
    assert "sin carpeta de fotos desde la app" in capsys.readouterr().out
    assert [m for m in mensajes if m.startswith("camara")] == ["camara_lista:1:juego_a;juego_b"]   # lo intenta una vez y no insiste
    assert _giros(mensajes) == ["giro:0.0"]


def test_en_simulacion_o_sin_raiz_de_carpetas_el_pc_no_toca_la_camara(tmp_path, juegos):
    puente = PuenteFalso()
    fuente = _fuente_de(juegos)
    assert Celda(_cfg(tmp_path, puente, modo_simulacion=False, camara={"raiz_carpetas": str(juegos)}), fuente, None, None)._camara_activa()
    assert not Celda(_cfg(tmp_path, puente, modo_simulacion=True, camara={"raiz_carpetas": str(juegos)}), fuente, None, None)._camara_activa()
    assert not Celda(_cfg(tmp_path, puente, modo_simulacion=False, camara={"visor": True}), fuente, None, None)._camara_activa()
    assert not Celda(_cfg(tmp_path, puente, modo_simulacion=False), fuente, None, None)._camara_activa()
    puente.cerrar()


def test_si_la_camara_de_la_configuracion_es_en_vivo_el_pc_lo_dice_en_vez_de_contar_fotos(tmp_path, juegos):
    """Con una camara de verdad (sin fotos que contar), al volver a la del PC el aviso es «en vivo: ...» y 0 fotos."""
    from celda.percepcion import FuenteCamara
    from test_celda_percepcion import Z_CINTA, _cam

    class CamaraEnVivo:
        def siguiente(self):
            return None
    CamaraEnVivo.__name__ = "CamaraOpenCV"
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False, camara={"raiz_carpetas": str(juegos)})
    fuente = FuenteCamara(CamaraEnVivo(), _cam(), Z_CINTA, params={"modo": "profundidad"}, tiempo_max_s=0.3, pausa_s=0.01)
    camara = {"carpetas": ["juego_b", ""], "infos": 2}
    _ejecutar(cfg, puente, fuente, 1, modo="real", n_lote=1, ajustes=_ajustes_camara(), camara=camara)
    assert camara["info"] == [(2, "ok"), (0, "en vivo: camara USB")]


def test_con_la_calibracion_de_la_webcam_el_pc_va_a_donde_esta_la_caja_en_la_imagen(tmp_path):
    """celda/camara_webcam.json (la que lleva config_celda_real_webcam.json) centra la imagen en la recogida (700, 0): una caja desplazada de ese punto
    en la imagen es una caja desplazada en el robot, y el PC va a ella (modo Camara y zona permitida de la app) con las medidas de la caja."""
    from pathlib import Path

    from celda.percepcion import FuenteCamara
    from vision.camara import ModeloCamara
    from vision.escena import CajaSintetica, escena
    from vision.proveedores import Fotograma
    modelo = ModeloCamara.cargar(Path(__file__).resolve().parents[1] / "celda" / "camara_webcam.json")
    caja = CajaSintetica(220.0, 140.0, 120.0, 30.0, (745.0, 38.0))               # 45 mm a la derecha y 38 mm arriba del centro de la imagen
    foto = Fotograma(escena(modelo, [caja], z_plano=220.0), None, "webcam")
    fuente = FuenteCamara(_ListaFotogramas([foto] * 50), modelo, 220.0, alto_mm=120.0, params={"modo": "color"}, tiempo_max_s=1.0, pausa_s=0.01)
    puente = PuenteFalso()
    cfg = _cfg(tmp_path, puente, modo_simulacion=False)
    ajustes = _ajustes(recogida="recogida:1:700.0:0.0:150.0:150.0:0.0:0.0:0.0:1.0", celda="celda:220.0:150.0:147.0:600.0:-6.5:740.0:100.0:0.0")
    mensajes, errores, excepcion = _ejecutar(cfg, puente, fuente, 1, modo="real", n_lote=1, ajustes=ajustes)
    assert excepcion is None and errores == []
    assert puente.objetivos[0] == pytest.approx((745.0, 38.0, 600.0 + 147.0), abs=2.0)    # el punto seguro sobre la caja que ve la webcam
    assert float([m for m in mensajes if m.startswith("giro:")][0].split(":")[1]) == pytest.approx(30.0, abs=1.5)
    # con la zona permitida de 30 mm (la de Fija es 50), esa caja ya esta fuera: el PC se para y no se mueve
    puente2 = PuenteFalso()
    cfg2 = _cfg(tmp_path, puente2, modo_simulacion=False)
    ajustes2 = _ajustes(recogida="recogida:1:700.0:0.0:30.0:30.0:0.0:0.0:0.0:1.0", celda="celda:220.0:150.0:147.0:600.0:-6.5:740.0:100.0:0.0")
    fuente2 = FuenteCamara(_ListaFotogramas([foto] * 50), modelo, 220.0, alto_mm=120.0, params={"modo": "color"}, tiempo_max_s=1.0, pausa_s=0.01)
    _, _, excepcion2 = _ejecutar(cfg2, puente2, fuente2, 1, modo="real", n_lote=1, ajustes=ajustes2)
    assert isinstance(excepcion2, RuntimeError) and "fuera de la zona permitida" in str(excepcion2)
    assert puente2.objetivos == []


# ---------------------------------------------------------------- --indice: que camara USB abre el ciclo
def test_indice_cambia_la_camara_usb_de_la_configuracion_sin_tocar_el_json(tmp_path):
    import json as _json
    from pathlib import Path

    from celda.ciclo import aplicar_indice_de_camara
    from celda.config import cargar
    cfg = cargar(Path(__file__).resolve().parents[1] / "celda" / "config_celda_real_webcam.json")
    assert cfg.camara["origen"]["tipo"] == "opencv" and cfg.camara["origen"]["indice"] == 1       # la webcam externa
    assert aplicar_indice_de_camara(cfg, None) is cfg
    otra = aplicar_indice_de_camara(cfg, 0)                                                         # la del portatil
    assert otra.camara["origen"]["indice"] == 0 and cfg.camara["origen"]["indice"] == 1             # la original no cambia
    assert otra.camara["origen"]["tam"] == cfg.camara["origen"]["tam"] and otra.camara["calibracion"] == cfg.camara["calibracion"]
    with pytest.raises(ValueError, match="0, 1, 2"):
        aplicar_indice_de_camara(cfg, -1)
    sim = cargar(Path(__file__).resolve().parents[1] / "celda" / "config_celda.json")
    with pytest.raises(ValueError, match="solo vale en modo Real con una cámara USB"):
        aplicar_indice_de_camara(sim, 1)
    carpeta = cargar(Path(__file__).resolve().parents[1] / "celda" / "config_celda_real_casa.json")
    with pytest.raises(ValueError, match="solo vale en modo Real con una cámara USB"):
        aplicar_indice_de_camara(carpeta, 1)
    assert _json is not None


def test_main_valida_el_indice_y_el_uso(capsys):
    from celda.ciclo import main
    main(["ciclo"])
    assert "uso: python -m celda.ciclo" in capsys.readouterr().out
    main(["ciclo", "celda/config_celda.json", "--indice"])
    assert "--indice necesita el número" in capsys.readouterr().out
    main(["ciclo", "celda/config_celda.json", "--indice", "uno"])
    assert "--indice necesita el número" in capsys.readouterr().out


def test_la_ventana_dice_que_camara_usb_es(tmp_path):
    from celda.percepcion import FuenteCamara

    class CamaraOpenCV:                    # el visor la reconoce por el nombre de la clase
        indice = 1

        def siguiente(self):
            return None
    assert FuenteCamara(CamaraOpenCV()).origen() == "camara USB 1"
    del CamaraOpenCV.indice
    assert FuenteCamara(CamaraOpenCV()).origen() == "camara USB"
