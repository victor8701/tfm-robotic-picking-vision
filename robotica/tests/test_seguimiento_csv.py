"""Lectura del registro CSV del puente y trayectoria recorrida (sin ROS)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ros2" / "robotica_bimanual"))

from robotica_bimanual.seguimiento_csv import Trayectoria, ultima_muestra  # noqa: E402

CABECERA = "t_s,sesion,seqno,estado,real_x,real_y,real_z,ref_x,ref_y,ref_z,desviacion_mm,fase"


def _fila(t, sesion, seqno, real, fase="xy_ida", estado="activo"):
    x, y, z = real
    return f"{t:.4f},{sesion},{seqno},{estado},{x:.3f},{y:.3f},{z:.3f},{x:.3f},{y:.3f},{z:.3f},0.000,{fase}"


def _escribir(tmp_path, filas, cabecera=CABECERA):
    ruta = tmp_path / "puente.csv"
    ruta.write_text("\n".join([cabecera, *filas]) + "\n", encoding="utf-8")
    return str(ruta)


def test_devuelve_la_ultima_muestra_de_la_sesion(tmp_path):
    ruta = _escribir(tmp_path, [
        _fila(1.0, "brazo1", 1, (600, -6.5, 390), fase="aprox"),
        _fila(1.1, "brazo2", 1, (10, 10, 10)),
        _fila(1.2, "brazo1", 2, (599, -5.5, 390), fase="xy_ida"),
        _fila(1.3, "brazo2", 2, (11, 11, 11)),
    ])
    m = ultima_muestra(ruta, "brazo1")
    assert m.seqno == 2
    assert m.real == (599.0, -5.5, 390.0)
    assert m.fase == "xy_ida"
    assert m.estado == "activo"


def test_sin_fichero_o_sin_datos_devuelve_none(tmp_path):
    assert ultima_muestra(str(tmp_path / "no_existe.csv")) is None
    ruta = _escribir(tmp_path, [_fila(1.0, "brazo2", 1, (0, 0, 0))])
    assert ultima_muestra(ruta, "brazo1") is None


def test_ignora_la_linea_a_medio_escribir(tmp_path):
    ruta = _escribir(tmp_path, [_fila(1.0, "brazo1", 1, (600, -6.5, 390), fase="aprox")])
    with open(ruta, "a", encoding="utf-8") as f:
        f.write("1.1000,brazo1,2,activo,599.0")  # cortada
    assert ultima_muestra(ruta, "brazo1").seqno == 1


def test_cabecera_antigua_sin_fase(tmp_path):
    antigua = "t_s,sesion,seqno,estado,real_x,real_y,real_z,ref_x,ref_y,ref_z,desviacion_mm"
    fila = "1.0,brazo1,1,esperando,1,2,3,1,2,3,0.000"
    ruta = _escribir(tmp_path, [fila], cabecera=antigua)
    m = ultima_muestra(ruta, "brazo1")
    assert m.real == (1.0, 2.0, 3.0)
    assert m.fase == ""


def test_lee_bien_un_fichero_grande(tmp_path):
    filas = [_fila(i * 0.004, "brazo1", i, (600, -6.5, 390 + i * 0.001)) for i in range(1, 5000)]
    ruta = _escribir(tmp_path, filas)
    assert ultima_muestra(ruta, "brazo1").seqno == 4999


def test_trayectoria_submuestrea_y_se_reinicia():
    from robotica_bimanual.seguimiento_csv import Muestra

    def m(seqno, x):
        return Muestra(t_s=0.0, seqno=seqno, estado="activo", real=(x, 0.0, 0.0),
                       ref=(x, 0.0, 0.0), desviacion_mm=0.0, fase="")

    tray = Trayectoria(min_paso_mm=1.0, maximo=50000)
    for i in range(1, 25):
        tray.añadir(m(i, 600 + i * 0.1))  # 0,1 mm por muestra, hasta 602,4 mm
    assert len(tray.puntos) == 3  # 600,1; 601,1 y 602,1: uno cada 1 mm
    assert tray.añadir(m(1, 600.0)) is True  # el seqno vuelve a empezar: ejecucion nueva
    assert len(tray.puntos) == 1


def test_la_trayectoria_guarda_solo_la_ventana():
    from robotica_bimanual.seguimiento_csv import Muestra

    tray = Trayectoria(min_paso_mm=1.0, maximo=3)
    for i in range(10):
        x = 10.0 * i
        tray.añadir(Muestra(t_s=0.0, seqno=i + 1, estado="activo", real=(x, 0.0, 0.0),
                            ref=(x, 0.0, 0.0), desviacion_mm=0.0, fase=""))
    assert tray.puntos == [(70.0, 0.0, 0.0), (80.0, 0.0, 0.0), (90.0, 0.0, 0.0)]
