"""La celda por ROS 2: PuenteRos, ProveedorRos y nodo_celda contra un puente y una cámara falsos que hablan por topics.

Solo corre con ROS 2 cargado (source /opt/ros/humble/setup.bash antes de pytest); sin ROS se salta.
"""
import json
import socket
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

rclpy = pytest.importorskip("rclpy")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "ros2" / "robotica_bimanual"))

from geometry_msgs.msg import PoseStamped  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from sensor_msgs.msg import Image  # noqa: E402
from std_msgs.msg import String  # noqa: E402

from test_celda_ciclo import AJUSTES_PRUEBA, _puerto_libre, _rapid_falso  # noqa: E402
from vision.escena import CajaSintetica, camara_cenital, escena, profundidad  # noqa: E402


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


class PuenteFalsoRos(Node):
    """Hace de nodo_puente + puente EGM: recibe /brazo1/objetivo, da por alcanzado el objetivo y publica /brazo1/estado como el puente."""

    def __init__(self):
        super().__init__("puente_falso")
        self.egm = False                     # lo pone RAPID (el hilo falso): sesion EGM abierta
        self.ciclos = 0
        self.real_t = [600.0, -6.5, 740.0]   # brida, mm
        self.real_q = [0.0, 0.0, 1.0, 0.0]   # w, x, y, z
        self.objetivos: list[tuple] = []
        self.orientaciones: list[tuple] = []
        self._pub = self.create_publisher(String, "/brazo1/estado", 10)
        self._pub_rechazo = self.create_publisher(String, "/brazo1/rechazo", 10)
        self.create_subscription(PoseStamped, "/brazo1/objetivo", self._objetivo, 10)
        self.create_timer(0.01, self._publicar)

    def _objetivo(self, msg: PoseStamped) -> None:
        p, q = msg.pose.position, msg.pose.orientation
        self.real_t = [p.x * 1000.0, p.y * 1000.0, p.z * 1000.0]
        self.real_q = [q.w, q.x, q.y, q.z]
        self.objetivos.append(tuple(self.real_t))
        self.orientaciones.append(tuple(self.real_q))

    def _publicar(self) -> None:
        if self.egm:
            self.ciclos += 5
        estado = {"ok": True, "sesion": "brazo1", "estado": "activo" if self.egm else "esperando", "codigo": "", "ciclos": self.ciclos,
                  "errores": 0, "desviacion_mm": 0.0, "real": {"t": self.real_t, "q": self.real_q},
                  "referencia": {"t": self.real_t, "q": self.real_q}}
        self._pub.publish(String(data=json.dumps(estado)))


class ReleRapidFalso(Node):
    """Hace de nodo_puente + puente EGM para el socket de RAPID: es el servidor TCP al que se conecta T_COM (el RAPID falso) y lo lleva a /rapid/*."""

    def __init__(self, puerto):
        super().__init__("rele_rapid_falso")
        self._srv = socket.socket()
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", puerto))
        self._srv.listen(1)
        self._conn = None
        self.ordenes: list[str] = []
        self._pub_respuesta = self.create_publisher(String, "/rapid/respuesta", 50)
        self._pub_estado = self.create_publisher(String, "/rapid/estado", 10)
        self.create_subscription(String, "/rapid/orden", self._orden, 50)
        self.create_timer(0.1, self._estado)
        threading.Thread(target=self._aceptar, daemon=True).start()

    def _aceptar(self):
        try:
            self._conn, _ = self._srv.accept()
            while True:
                datos = self._conn.recv(256)
                if not datos:
                    break
                self._pub_respuesta.publish(String(data=datos.decode().strip()))
        except OSError:
            pass

    def _orden(self, msg):
        self.ordenes.append(msg.data)
        if self._conn is not None:
            self._conn.sendall(msg.data.encode())

    def _estado(self):
        self._pub_estado.publish(String(data=json.dumps({"conectado": self._conn is not None, "origen": "127.0.0.1:0"})))

    def destroy_node(self):
        for r in (self._conn, self._srv):
            if r is not None:
                r.close()
        return super().destroy_node()


def _con_rele(puerto, via):
    """Los nodos que hacen falta para el socket de RAPID: con via = puente, el relé; con pc, ninguno (lo abre nodo_celda)."""
    return [ReleRapidFalso(puerto)] if via == "puente" else []


def _girar(nodos, hasta, limite_s=30.0):
    """Hace girar los nodos en el hilo principal hasta que hasta() sea cierto o pase el limite."""
    ejecutor = SingleThreadedExecutor()
    for n in nodos:
        ejecutor.add_node(n)
    fin = time.monotonic() + limite_s
    try:
        while time.monotonic() < fin and not hasta():
            ejecutor.spin_once(timeout_sec=0.01)
    finally:
        for n in nodos:
            ejecutor.remove_node(n)


def _config(tmp_path, puerto_rapid, csv=None, real=False, camara=None, via="puente"):
    """celda/config_celda.json en pequeño: lo justo para el nodo (periodo de 10 ms para no inundar los topics)."""
    d = {"modo_simulacion": not real, "n_cajas": 1, "percepcion": {"csv_caja": str(csv or tmp_path / "caja.csv")},
         "puente": {"host": "127.0.0.1", "puerto_control": 7001},
         "socket_rapid": {"via": via, "ip_escucha": "127.0.0.1", "puerto": puerto_rapid, "espera_conexion_s": 10},
         "celda": {"z_cinta": 300.0, "z_mesa": 150.0, "z_seguro": 600.0, "margen_aproximacion": 150.0, "centro_recogida": [400.0, 0.0],
                   "mesa": [200.0, 400.0], "eje_pinzado": "y", "largo_herramienta_mm": 147.0},
         "control": {"periodo_s": 0.01, "tolerancia_pos_mm": 2.0, "tolerancia_rot_rad": 0.02, "max_iteraciones": 5000},
         "ventana_egm": {"inicio_mm": [600.0, -6.5, 740.0], "semiancho_mm": 600.0}}
    if camara is not None:
        d["camara"] = camara
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(d), encoding="utf-8")
    return ruta


def _crear_nodo_celda(ruta):
    from robotica_bimanual.nodo_celda import NodoCelda
    from rclpy.parameter import Parameter
    # el nodo lee su parametro 'config' de los argumentos de ROS; se pasa por parameter_overrides al construir
    original = Node.__init__

    def con_parametro(self, *a, **k):
        k["parameter_overrides"] = [Parameter("config", value=str(ruta))]
        original(self, *a, **k)
    Node.__init__ = con_parametro
    try:
        return NodoCelda()
    finally:
        Node.__init__ = original


def _recoger(nodo, topic, tipo):
    recibidos = []
    nodo.create_subscription(tipo, topic, lambda m: recibidos.append(m), 50)
    return recibidos


# ---------------------------------------------------------------- PuenteRos
def test_puente_ros_da_el_estado_y_publica_los_objetivos(ros):
    from nucleo.geometria import Pose
    from robotica_bimanual.puente_ros import PuenteRos

    falso = PuenteFalsoRos()
    nodo = Node("cliente")
    puente = PuenteRos(nodo)
    resultado = {}

    def pedir():
        resultado["estado"] = puente.estado()
        resultado["objetivo"] = puente.objetivo(Pose.crear(t=[500.0, 20.0, 600.0]))
    hilo = threading.Thread(target=pedir)
    hilo.start()
    _girar([falso, nodo], lambda: not hilo.is_alive(), 10.0)
    hilo.join(2.0)
    assert resultado["estado"]["ok"] and resultado["estado"]["real"]["t"] == [600.0, -6.5, 740.0]
    assert resultado["objetivo"] == {"ok": True}
    _girar([falso, nodo], lambda: bool(falso.objetivos), 5.0)
    assert falso.objetivos[-1] == pytest.approx((500.0, 20.0, 600.0), abs=1e-6)   # en mm, como lo ve el puente
    for n in (falso, nodo):
        n.destroy_node()


def test_sin_estado_del_puente_el_error_dice_que_falta(ros):
    from robotica_bimanual.puente_ros import PuenteRos

    nodo = Node("cliente")
    puente = PuenteRos(nodo, espera_estado_s=0.2)
    with pytest.raises(OSError, match="no llega /brazo1/estado"):
        puente.estado()
    nodo.destroy_node()


def test_si_el_puente_rechaza_un_objetivo_el_ciclo_se_entera(ros):
    from nucleo.geometria import Pose
    from robotica_bimanual.puente_ros import PuenteRos

    falso = PuenteFalsoRos()
    nodo = Node("cliente")
    puente = PuenteRos(nodo)
    falso._pub_rechazo.publish(String(data=json.dumps({"ok": False, "error": "fuera del espacio del puente"})))
    _girar([falso, nodo], lambda: False, 0.3)      # llega el rechazo
    r = puente.objetivo(Pose.crear(t=[500.0, 20.0, 600.0]))
    assert r["ok"] is False and "fuera del espacio" in r["error"]
    assert puente.objetivo(Pose.crear(t=[500.0, 20.0, 600.0])) == {"ok": True}   # se entrega una sola vez
    for n in (falso, nodo):
        n.destroy_node()


def test_nodo_puente_publica_en_rechazo_lo_que_rechaza_el_puente_tcp(tmp_path):
    """nodo_puente contra un puente TCP falso que rechaza z > 1000: la respuesta sale por /brazo1/rechazo."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    puerto = srv.getsockname()[1]

    def servir():
        conn, _ = srv.accept()
        f = conn.makefile("rwb")
        for linea in f:
            d = json.loads(linea)
            if d["cmd"] == "estado":
                r = {"ok": True, "estado": "esperando", "ciclos": 0, "real": {"t": [0, 0, 0], "q": [1, 0, 0, 0]}}
            else:
                r = {"ok": d["t"][2] <= 1000.0, "error": "fuera del espacio del puente"}
            f.write((json.dumps(r) + "\n").encode())
            f.flush()
    threading.Thread(target=servir, daemon=True).start()
    rclpy.init(args=["--ros-args", "-p", f"brazo1.puerto:={puerto}"])
    try:
        from robotica_bimanual.nodo_puente import NodoPuente
        nodo = NodoPuente()
        cliente = Node("cliente")
        rechazos = _recoger(cliente, "/brazo1/rechazo", String)
        pub = cliente.create_publisher(PoseStamped, "/brazo1/objetivo", 10)

        def objetivo(z):
            m = PoseStamped()
            m.pose.position.z = z
            m.pose.orientation.w = 1.0
            pub.publish(m)
        _girar([nodo, cliente], lambda: False, 0.3)
        objetivo(0.5)            # 500 mm: lo acepta
        _girar([nodo, cliente], lambda: False, 0.3)
        assert rechazos == []
        objetivo(1.5)            # 1500 mm: lo rechaza
        _girar([nodo, cliente], lambda: bool(rechazos), 3.0)
        assert rechazos and json.loads(rechazos[0].data)["ok"] is False
        nodo.destroy_node()
        cliente.destroy_node()
    finally:
        rclpy.shutdown()
        srv.close()


# ---------------------------------------------------------------- nodo_celda en simulacion (caja.csv)
@pytest.mark.parametrize("via", ["puente", "pc"])
def test_nodo_celda_hace_el_ciclo_completo_por_topics(ros, tmp_path, via):
    (tmp_path / "caja.csv").write_text("150.0;100.0;120.0;30.0\n150.0;100.0;120.0;-60.0\n", encoding="utf-8")
    puerto = _puerto_libre()
    reles = _con_rele(puerto, via)
    nodo = _crear_nodo_celda(_config(tmp_path, puerto, via=via))
    falso = PuenteFalsoRos()
    observador = Node("observador")
    estados = _recoger(observador, "/celda/estado", String)
    cajas = _recoger(observador, "/celda/caja", PoseStamped)
    mensajes, errores = [], []
    rapid = threading.Thread(target=_rapid_falso, args=(puerto, falso, 2, mensajes, errores), daemon=True)
    rapid.start()
    nodo.iniciar()
    _girar([nodo, falso, observador, *reles], nodo.terminado.is_set, 40.0)
    _girar([observador], lambda: False, 0.2)   # lo ultimo publicado llega
    rapid.join(5.0)
    assert nodo.terminado.is_set() and nodo.error is None, nodo.error
    assert errores == []
    assert mensajes == ["lote", "mesa", "recogida", "agarre", "celda", "giro:30.0", "cerrar", "abrir", "fin_caja",
                        "giro:-60.0", "cerrar", "abrir", "fin_caja", "fin_programa"]
    # el robot (el puente falso) ha recibido objetivos por el topic: el primero, el punto seguro sobre la recogida (brida = TCP + 147)
    assert falso.objetivos and falso.objetivos[0] == pytest.approx((400.0, 0.0, 600.0 + 147.0), abs=1.0)
    eventos = [json.loads(m.data) for m in estados]
    assert [e["evento"] for e in eventos if e["evento"] in ("inicio", "fin")] == ["inicio", "fin"]
    assert [e["n"] for e in eventos if e["evento"] == "caja"] == [1, 2]
    assert [(e["orden"], e["respuesta"]) for e in eventos if e["evento"] == "pinza"] == [
        ("cerrar", "cerrada"), ("abrir", "abierta"), ("cerrar", "cerrada"), ("abrir", "abierta")]
    assert cajas == []     # con caja.csv no hay posición de caja (solo medidas y giro): /celda/caja queda en silencio
    if via == "puente":    # todo lo de RAPID salió por /rapid/orden: la pinza, la mesa, los ajustes y el fin del programa
        assert reles[0].ordenes[:2] == ["lote", "mesa"] and reles[0].ordenes[-1] == "fin_programa"
        assert reles[0].ordenes.count("cerrar") == 2 and reles[0].ordenes.count("abrir") == 2
    for n in (nodo, falso, observador, *reles):
        n.destroy_node()


def test_nodo_celda_publica_el_error_si_el_ciclo_se_para(ros, tmp_path):
    (tmp_path / "caja.csv").write_text("150.0;100.0;120.0;30.0\n", encoding="utf-8")
    puerto = _puerto_libre()
    reles = _con_rele(puerto, "puente")
    nodo = _crear_nodo_celda(_config(tmp_path, puerto))
    falso = PuenteFalsoRos()
    observador = Node("observador")
    estados = _recoger(observador, "/celda/estado", String)
    mensajes, errores = [], []
    # RAPID mudo en cerrar: no contesta, y con una espera corta el ciclo se para con un error
    from celda.ciclo import Celda
    Celda.ESPERA_RESPUESTA_S = 0.5
    try:
        rapid = threading.Thread(target=_rapid_falso, args=(puerto, falso, 1, mensajes, errores), kwargs={"mudo_en": "cerrar"}, daemon=True)
        rapid.start()
        nodo.iniciar()
        _girar([nodo, falso, observador, *reles], nodo.terminado.is_set, 30.0)
        _girar([observador], lambda: False, 0.2)
    finally:
        Celda.ESPERA_RESPUESTA_S = 40.0
    assert nodo.error is not None and "no ha contestado a 'cerrar'" in str(nodo.error)
    ultimo = json.loads(estados[-1].data)
    assert ultimo["evento"] == "error" and "no ha contestado" in ultimo["mensaje"]
    for n in (nodo, falso, observador, *reles):
        n.destroy_node()


def test_nodo_celda_sin_config_dice_que_falta(ros):
    from robotica_bimanual.nodo_celda import NodoCelda
    with pytest.raises(ValueError, match="falta el parametro 'config'"):
        NodoCelda()


# ---------------------------------------------------------------- camara por ROS
def _imagen_ros(bgr, encoding="bgr8"):
    m = Image()
    m.height, m.width = bgr.shape[:2]
    m.encoding = encoding
    m.step = bgr.strides[0]
    m.data = bgr.tobytes()
    return m


class CamaraFalsaRos(Node):
    """Publica una foto (y su profundidad) de la celda cada 0,1 s por los topics de un driver de camara."""

    def __init__(self, bgr, prof_mm, topic_color="/camara/color", topic_prof="/camara/prof", con_profundidad=True):
        super().__init__("camara_falsa")
        from rclpy.qos import qos_profile_sensor_data
        self._color = _imagen_ros(bgr)
        self._prof = None
        if prof_mm is not None and con_profundidad:
            p = prof_mm.astype(np.uint16)
            self._prof = _imagen_ros(p, "16UC1")
            self._prof.step = p.strides[0]
        self._pub_c = self.create_publisher(Image, topic_color, qos_profile_sensor_data)
        self._pub_p = self.create_publisher(Image, topic_prof, qos_profile_sensor_data)
        self.create_timer(0.1, self._publicar)

    def _publicar(self) -> None:
        ahora = self.get_clock().now().to_msg()
        self._color.header.stamp = ahora
        self._pub_c.publish(self._color)
        if self._prof is not None:
            self._prof.header.stamp = ahora
            self._pub_p.publish(self._prof)


def _escena_celda(caja):
    cam = camara_cenital(tam=(640, 480), altura_mm=650.0, centro_xy=(700.0, 0.0), z_plano=220.0)
    return cam, escena(cam, [caja], z_plano=220.0), profundidad(cam, [caja], z_plano=220.0)


def test_proveedor_ros_da_la_imagen_nueva_con_su_profundidad(ros):
    from robotica_bimanual.proveedor_ros import ProveedorRos

    cam, img, prof = _escena_celda(CajaSintetica(200.0, 140.0, 120.0, 20.0, (712.0, 9.0)))
    camara = CamaraFalsaRos(img, prof)
    nodo = Node("receptor")
    proveedor = ProveedorRos(nodo, "/camara/color", "/camara/prof", espera_s=5.0)
    salida = {}

    def pedir():
        salida["a"] = proveedor.siguiente()
        salida["b"] = proveedor.siguiente()      # otra imagen distinta (la siguiente que llega)
    hilo = threading.Thread(target=pedir)
    hilo.start()
    _girar([camara, nodo], lambda: not hilo.is_alive(), 10.0)
    hilo.join(2.0)
    f = salida["a"]
    assert f.bgr.shape == img.shape and np.array_equal(f.bgr, img)
    assert f.profundidad.shape == img.shape[:2] and f.profundidad.dtype == np.float32
    assert np.allclose(f.profundidad, prof.astype(np.uint16).astype(np.float32))
    assert salida["b"] is not None and salida["b"] is not f
    for n in (camara, nodo):
        n.destroy_node()


def test_proveedor_ros_sin_imagenes_o_sin_profundidad_lo_dice(ros):
    from robotica_bimanual.proveedor_ros import ProveedorRos

    nodo = Node("receptor")
    sin_nada = ProveedorRos(nodo, "/camara/color", None, espera_s=0.2)
    with pytest.raises(RuntimeError, match="no llegan imágenes por /camara/color"):
        sin_nada.siguiente()
    cam, img, prof = _escena_celda(CajaSintetica(200.0, 140.0, 120.0, 0.0, (700.0, 0.0)))
    solo_color = CamaraFalsaRos(img, prof, topic_color="/c2", topic_prof="/p2", con_profundidad=False)
    con_prof = ProveedorRos(nodo, "/c2", "/p2", espera_s=0.5)
    hilo_error = {}

    def pedir():
        try:
            con_prof.siguiente()
        except RuntimeError as e:
            hilo_error["e"] = str(e)
    hilo = threading.Thread(target=pedir)
    hilo.start()
    _girar([solo_color, nodo], lambda: not hilo.is_alive(), 5.0)
    hilo.join(2.0)
    assert "no llega la profundidad" in hilo_error["e"] and "align_depth" in hilo_error["e"]
    for n in (solo_color, nodo):
        n.destroy_node()


def test_nodo_celda_en_real_con_la_camara_por_ros_va_donde_ve_la_caja(ros, tmp_path):
    cam, img, prof = _escena_celda(CajaSintetica(200.0, 140.0, 120.0, 20.0, (712.0, 9.0)))
    cam.guardar(tmp_path / "camara.json")
    puerto = _puerto_libre()
    reles = _con_rele(puerto, "puente")
    ruta = _config(tmp_path, puerto, real=True, camara={
        "calibracion": "camara.json", "origen": {"tipo": "ros", "color": "/camara/color", "profundidad": "/camara/prof"},
        "modo": "profundidad"})
    nodo = _crear_nodo_celda(ruta)
    falso = PuenteFalsoRos()
    camara = CamaraFalsaRos(img, prof)
    observador = Node("observador")
    cajas = _recoger(observador, "/celda/caja", PoseStamped)
    mensajes, errores = [], []
    ajustes = dict(AJUSTES_PRUEBA, recogida="recogida:1:700.0:0.0:50.0:50.0:0.0:0.0:0.0:5.0", celda="celda:220.0:150.0:147.0:600.0:-6.5:740.0:100.0:0.0")
    rapid = threading.Thread(target=_rapid_falso, args=(puerto, falso, 1, mensajes, errores),
                             kwargs={"modo": "real", "n_lote": 1, "ajustes": ajustes}, daemon=True)
    rapid.start()
    nodo.iniciar()
    _girar([nodo, falso, camara, observador, *reles], nodo.terminado.is_set, 60.0)
    _girar([observador], lambda: False, 0.2)
    rapid.join(5.0)
    assert nodo.terminado.is_set() and nodo.error is None, nodo.error
    assert errores == []
    assert falso.objetivos[0] == pytest.approx((712.0, 9.0, 600.0 + 147.0), abs=1.5)    # el punto seguro sobre la caja que ve la camara
    giro = float([m for m in mensajes if m.startswith("giro:")][0].split(":")[1])
    assert giro == pytest.approx(20.0, abs=1.5)
    assert cajas and cajas[0].pose.position.x == pytest.approx(0.712, abs=2e-3) and cajas[0].pose.position.z == pytest.approx(0.22)
    for n in (nodo, falso, camara, observador, *reles):
        n.destroy_node()


# ---------------------------------------------------------------- RAPID por topics
def test_rapid_ros_sin_nodo_puente_dice_que_falta(ros):
    from robotica_bimanual.rapid_ros import RapidRos

    nodo = Node("celda")
    rapid = RapidRos(nodo, espera_s=0.3)
    with pytest.raises(TimeoutError, match="no llega /rapid/estado"):
        rapid.esperar_cliente()
    with pytest.raises(TimeoutError, match="no ha contestado"):
        rapid.recibir(0.1)
    nodo.destroy_node()


def test_rapid_ros_si_el_puente_no_tiene_socket_lo_dice_enseguida(ros):
    from robotica_bimanual.rapid_ros import RapidRos

    nodo = Node("celda")
    falso = Node("puente_falso")
    pub = falso.create_publisher(String, "/rapid/estado", 10)
    rapid = RapidRos(nodo, espera_s=10.0)
    falso.create_timer(0.05, lambda: pub.publish(String(data=json.dumps({"conectado": False, "error": "falta la sección 'rapid'"}))))
    salida = {}

    def esperar():
        try:
            rapid.esperar_cliente()
        except ConnectionError as e:
            salida["e"] = str(e)
    hilo = threading.Thread(target=esperar)
    hilo.start()
    _girar([nodo, falso], lambda: not hilo.is_alive(), 5.0)
    hilo.join(1.0)
    assert "falta la sección 'rapid'" in salida["e"]
    for n in (nodo, falso):
        n.destroy_node()


def test_nodo_puente_lleva_el_socket_de_rapid_a_topics(tmp_path):
    """nodo_puente con rapid:=true contra un puente TCP falso: /rapid/orden -> rapid_enviar; lo que contesta RAPID -> /rapid/respuesta."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    puerto = srv.getsockname()[1]
    enviados: list[str] = []
    respuestas: list[str] = []
    hay = threading.Condition()

    def atender(conn):
        f = conn.makefile("rwb")
        for linea in f:
            d = json.loads(linea)
            if d["cmd"] == "estado":
                r = {"ok": True, "estado": "esperando", "ciclos": 0, "real": {"t": [0, 0, 0], "q": [1, 0, 0, 0]}}
            elif d["cmd"] == "rapid_estado":
                r = {"ok": True, "conectado": True, "origen": "127.0.0.1:5555"}
            elif d["cmd"] == "rapid_enviar":
                with hay:
                    enviados.append(d["msg"])
                    respuestas.append({"cerrar": "cerrada", "abrir": "abierta"}.get(d["msg"], "?"))
                    hay.notify_all()
                r = {"ok": True}
            elif d["cmd"] == "rapid_recibir":
                with hay:
                    hay.wait_for(lambda: bool(respuestas), timeout=d.get("timeout_s", 1.0))
                    r = {"ok": True, "msg": respuestas.pop(0)} if respuestas else {"ok": False, "codigo": "timeout", "error": "RAPID no ha contestado"}
            else:
                r = {"ok": True}
            f.write((json.dumps(r) + "\n").encode())
            f.flush()

    def aceptar():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            threading.Thread(target=atender, args=(conn,), daemon=True).start()
    threading.Thread(target=aceptar, daemon=True).start()
    rclpy.init(args=["--ros-args", "-p", f"brazo1.puerto:={puerto}", "-p", "rapid:=true"])
    try:
        from robotica_bimanual.nodo_puente import NodoPuente
        nodo = NodoPuente()
        celda = Node("celda")
        pub = celda.create_publisher(String, "/rapid/orden", 10)
        respuestas_ros = _recoger(celda, "/rapid/respuesta", String)
        estados_ros = _recoger(celda, "/rapid/estado", String)
        _girar([nodo, celda], lambda: pub.get_subscription_count() > 0 and bool(estados_ros), 5.0)
        assert json.loads(estados_ros[-1].data) == {"conectado": True, "origen": "127.0.0.1:5555"}
        pub.publish(String(data="cerrar"))
        _girar([nodo, celda], lambda: bool(respuestas_ros), 5.0)
        assert enviados == ["cerrar"] and [m.data for m in respuestas_ros] == ["cerrada"]
        pub.publish(String(data="abrir"))
        _girar([nodo, celda], lambda: len(respuestas_ros) == 2, 5.0)
        assert [m.data for m in respuestas_ros] == ["cerrada", "abierta"]
        nodo.destroy_node()
        celda.destroy_node()
    finally:
        rclpy.shutdown()
        srv.close()


def test_cadena_completa_de_rapid_topics_nodo_puente_puente_csharp_y_t_com(tmp_path):
    """Todos los saltos de verdad: /rapid/orden -> nodo_puente -> TCP -> PuenteEgm (C#) -> socket -> T_COM falso y la vuelta por /rapid/respuesta."""
    from test_puente_e2e import DLL, DOTNET, _puerto_libre as puerto_libre_tipo, puente_en_marcha
    from robotica_bimanual.rapid_ros import RapidRos

    if not (DLL.exists() and Path(DOTNET).exists()):
        pytest.skip("puente EGM sin compilar (dotnet build -c Release) o sin .NET 8")
    puerto_rapid = puerto_libre_tipo(socket.SOCK_STREAM)
    with puente_en_marcha(tmp_path, "absoluta", rapid_puerto=puerto_rapid):
        cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        puerto_control = cfg["sesiones"][0]["puerto_control"]
        tcom = socket.create_connection(("127.0.0.1", puerto_rapid), timeout=10.0)   # T_COM: SocketConnect
        rclpy.init(args=["--ros-args", "-p", f"brazo1.puerto:={puerto_control}", "-p", "rapid:=true"])
        try:
            from robotica_bimanual.nodo_puente import NodoPuente
            nodo = NodoPuente()
            celda = Node("celda")
            rapid = RapidRos(celda, espera_s=15.0)
            salida = {}

            def dialogo():
                rapid.esperar_cliente()
                rapid.enviar("lote")
                salida["recibido_por_tcom"] = tcom.recv(256).decode()
                tcom.sendall(b"lote:2:sim")
                salida["respuesta"] = rapid.recibir(10.0)
                rapid.enviar("fin_programa")
                salida["ultimo"] = tcom.recv(256).decode()
            hilo = threading.Thread(target=dialogo)
            hilo.start()
            _girar([nodo, celda], lambda: not hilo.is_alive(), 30.0)
            hilo.join(2.0)
            assert salida == {"recibido_por_tcom": "lote", "respuesta": "lote:2:sim", "ultimo": "fin_programa"}
            nodo.destroy_node()
            celda.destroy_node()
        finally:
            rclpy.shutdown()
            tcom.close()


def test_nodo_puente_no_se_cae_si_el_puente_aun_no_tiene_pose_real():
    """El puente sin robot en EGM da real.q = [0, 0, 0, 0] (cuaternion nulo): nodo_puente sigue vivo, publica el estado y no publica pose_real."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    puerto = srv.getsockname()[1]

    def atender(conn):
        f = conn.makefile("rwb")
        for linea in f:
            r = {"ok": True, "estado": "esperando", "ciclos": 0, "real": {"t": [0, 0, 0], "q": [0, 0, 0, 0]}}
            f.write((json.dumps(r) + "\n").encode())
            f.flush()

    def aceptar():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            threading.Thread(target=atender, args=(conn,), daemon=True).start()
    threading.Thread(target=aceptar, daemon=True).start()
    rclpy.init(args=["--ros-args", "-p", f"brazo1.puerto:={puerto}"])
    try:
        from robotica_bimanual.nodo_puente import NodoPuente
        nodo = NodoPuente()
        observador = Node("observador")
        estados = _recoger(observador, "/brazo1/estado", String)
        poses = _recoger(observador, "/brazo1/pose_real", PoseStamped)
        _girar([nodo, observador], lambda: len(estados) >= 5, 5.0)
        assert len(estados) >= 5 and poses == []
        nodo.destroy_node()
        observador.destroy_node()
    finally:
        rclpy.shutdown()
        srv.close()
