"""Lectura de caja.csv (simulacion): formato, orden y errores."""
from pathlib import Path

import pytest

from celda.percepcion import Caja, FuenteCsv

RAIZ = Path(__file__).resolve().parents[1]


def test_lee_las_cajas_en_orden(tmp_path):
    f = tmp_path / "caja.csv"
    f.write_text("300.0;200.0;120.0;-30.5\n150.0;100.0;80.0;45.0\n", encoding="utf-8")
    fuente = FuenteCsv(f)
    assert fuente.leer(0) == Caja(300.0, 200.0, 120.0, -30.5)
    assert fuente.leer(1) == Caja(150.0, 100.0, 80.0, 45.0)
    with pytest.raises(IndexError):
        fuente.leer(2)


@pytest.mark.parametrize("linea", ["300;200;120", "300;200;120;120", "300;-5;120;0"])
def test_rechaza_lineas_invalidas(tmp_path, linea):
    f = tmp_path / "caja.csv"
    f.write_text(linea + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        FuenteCsv(f).leer(0)


def test_fichero_inexistente_da_error_claro(tmp_path):
    with pytest.raises(FileNotFoundError):
        FuenteCsv(tmp_path / "no-existe.csv").leer(0)


def test_no_lee_el_fichero_hasta_la_primera_caja(tmp_path):
    f = tmp_path / "caja.csv"
    fuente = FuenteCsv(f)  # RAPID aun no ha escrito el fichero: crear la fuente no debe fallar
    f.write_text("300.0;200.0;120.0;0.0\n", encoding="utf-8")
    assert fuente.leer(0) == Caja(300.0, 200.0, 120.0, 0.0)


# ---------------------------------------------------------------- FuenteCamara (vision/) con imagenes sinteticas
import json  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from celda.config import cargar  # noqa: E402
from celda.percepcion import FuenteCamara, crear_fuente  # noqa: E402
from vision.escena import CajaSintetica, camara_cenital, escena, profundidad  # noqa: E402
from vision.proveedores import Fotograma  # noqa: E402

Z_CINTA = 220.0


class _Lista:
    """Proveedor de imagenes de prueba: los fotogramas dados, uno a uno (y luego, ninguno)."""

    def __init__(self, fotogramas):
        self._f = list(fotogramas)

    def siguiente(self):
        return self._f.pop(0) if self._f else None


def _cam():
    return camara_cenital(tam=(960, 720), altura_mm=650.0, centro_xy=(700.0, 0.0), z_plano=Z_CINTA)


def _foto(cajas, cam=None):
    """Un fotograma (imagen y profundidad) de la cinta con esas cajas. Calcular la profundidad cuesta: se reutiliza el mismo objeto."""
    cam = cam or _cam()
    return Fotograma(escena(cam, cajas, z_plano=Z_CINTA), profundidad(cam, cajas, z_plano=Z_CINTA), "x")


def _fuente(fotogramas, **kw):
    kw.setdefault("params", {"modo": "profundidad"})
    kw.setdefault("tiempo_max_s", 0.3)
    kw.setdefault("pausa_s", 0.01)
    return FuenteCamara(_Lista(fotogramas), _cam(), Z_CINTA, **kw)


def test_la_fuente_de_camara_da_la_caja_medida_en_la_base():
    caja = CajaSintetica(200.0, 140.0, 120.0, 20.0, (712.0, 9.0))
    c = _fuente([_foto([caja])]).leer(0)
    assert (c.largo, c.ancho, c.alto) == pytest.approx((200.0, 140.0, 120.0), abs=1.5)
    assert c.giro_deg == pytest.approx(20.0, abs=1.0) and c.centro == pytest.approx((712.0, 9.0), abs=1.0)


def test_espera_hasta_que_llega_una_caja_entera_y_elige_la_mas_cercana_al_punto():
    cerca, lejos = CajaSintetica(150.0, 100.0, 80.0, 0.0, (700.0, 0.0)), CajaSintetica(150.0, 100.0, 80.0, 0.0, (900.0, 20.0))
    vacio = _foto([])
    fuente = _fuente([vacio, vacio, _foto([lejos, cerca])], centro_nominal=(700.0, 0.0), tiempo_max_s=5.0)
    c = fuente.leer(0)
    assert c.centro == pytest.approx((700.0, 0.0), abs=1.0)


def test_si_no_hay_caja_a_tiempo_se_para_con_un_error_y_no_inventa_nada():
    fuente = _fuente([_foto([])] * 500, tiempo_max_s=0.2)
    with pytest.raises(RuntimeError, match="no ve ninguna caja entera en 0.2 s"):
        fuente.leer(0)


def test_una_caja_cortada_por_el_borde_no_vale_y_el_error_lo_dice():
    cortada = CajaSintetica(200.0, 140.0, 120.0, 0.0, (1000.0, 0.0))   # sale por la derecha de la imagen
    fuente = _fuente([_foto([cortada])] * 200, tiempo_max_s=0.2)
    with pytest.raises(RuntimeError, match="cortada por el borde"):
        fuente.leer(0)


def test_sin_mas_imagenes_o_sin_configurar_hay_un_error_claro():
    with pytest.raises(RuntimeError, match="no tiene mas imagenes"):
        _fuente([]).leer(0)
    with pytest.raises(RuntimeError, match="falta la seccion 'camara'"):
        FuenteCamara(motivo_sin_configurar="falta la seccion 'camara' en config_celda.json").leer(0)
    assert _fuente([]).total() is None


def test_la_fuente_se_configura_con_los_ajustes_de_rapid():
    from dataclasses import replace
    cfg = replace(cargar(RAIZ / "celda" / "config_celda.json"), z_cinta=250.0, centro_recogida=(650.0, 30.0), t_max_camara=2.5)
    f = _fuente([])
    f.configurar(cfg)
    assert (f.z_cinta, f.centro_nominal, f.tiempo_max_s) == (250.0, (650.0, 30.0), 2.5)


def _config_con_camara(carpeta, camara):
    """Escribe en `carpeta` una configuracion de la celda en modo real con esa seccion camara y devuelve su ruta."""
    d = json.loads((RAIZ / "celda" / "config_celda.json").read_text(encoding="utf-8"))
    d["modo_simulacion"] = False
    if camara is not None:
        d["camara"] = camara
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / "config.json"
    ruta.write_text(json.dumps(d), encoding="utf-8")
    return ruta


def test_la_configuracion_crea_la_fuente_de_camara_con_rutas_relativas_a_su_carpeta(tmp_path):
    cam = _cam()
    caja = CajaSintetica(200.0, 140.0, 120.0, 0.0, (700.0, 0.0))
    (tmp_path / "celda").mkdir()
    fotos = tmp_path / "celda" / "fotos"
    fotos.mkdir()
    cv2.imwrite(str(fotos / "a.png"), escena(cam, [caja], z_plano=Z_CINTA))
    import numpy as np
    np.save(fotos / "a.npy", profundidad(cam, [caja], z_plano=Z_CINTA))
    cam.guardar(tmp_path / "celda" / "camara.json")
    cfg = cargar(_config_con_camara(tmp_path / "celda", {"calibracion": "camara.json", "origen": {"tipo": "carpeta", "ruta": "fotos"}, "modo": "profundidad"}))
    assert cfg.camara["calibracion"] == str(tmp_path / "celda" / "camara.json")
    fuente = crear_fuente(cfg)
    assert isinstance(fuente, FuenteCamara)
    c = fuente.leer(0)
    assert (c.largo, c.ancho, c.alto) == pytest.approx((200.0, 140.0, 120.0), abs=1.5)


def test_sin_seccion_camara_la_fuente_real_lo_explica_al_leer(tmp_path):
    fuente = crear_fuente(cargar(_config_con_camara(tmp_path / "sin", None)))
    with pytest.raises(RuntimeError, match="falta la seccion 'camara'"):
        fuente.leer(0)


def test_una_configuracion_de_camara_incompleta_o_mala_se_rechaza(tmp_path):
    with pytest.raises(ValueError, match="camara.calibracion"):
        crear_fuente(cargar(_config_con_camara(tmp_path / "a", {"origen": {"tipo": "carpeta", "ruta": "."}})))
    _cam().guardar(tmp_path / "b" / "camara.json") if (tmp_path / "b").mkdir() is None else None
    with pytest.raises(ValueError, match="origen de imágenes desconocido"):
        crear_fuente(cargar(_config_con_camara(tmp_path / "b", {"calibracion": "camara.json", "origen": {"tipo": "ojos"}})))
    with pytest.raises(ValueError, match="no puedo leer la calibración"):
        crear_fuente(cargar(_config_con_camara(tmp_path / "c", {"calibracion": "no_existe.json", "origen": {"tipo": "carpeta", "ruta": "."}})))


# ---------------------------------------------------------------- vista previa, carpeta de ensayo y visor
def _carpeta_con_fotos(destino, n=2, calibrada=True, cam=None):
    """Una carpeta con n fotos de una caja (y profundidad) y, si calibrada, su camara.json."""
    import cv2
    cam = cam or _cam()
    destino.mkdir(parents=True, exist_ok=True)
    for k in range(n):
        caja = CajaSintetica(200.0 - 10 * k, 100.0, 120.0, 15.0 * k, (700.0 + 5 * k, 0.0))
        f = _foto([caja], cam)
        cv2.imwrite(str(destino / f"foto_{k + 1:02d}.png"), f.bgr)
        np.save(destino / f"foto_{k + 1:02d}.npy", f.profundidad)
    if calibrada:
        cam.guardar(destino / "camara.json")
    return destino


def test_carpeta_ver_no_gasta_la_imagen_y_siguiente_si(tmp_path):
    from vision.proveedores import Carpeta
    c = Carpeta(_carpeta_con_fotos(tmp_path / "juego", n=3))
    assert (c.n, c.indice, c.nombre) == (3, 0, "juego")
    a, b = c.ver(), c.ver()
    assert a.nombre == b.nombre == "foto_01.png" and c.indice == 0           # ver no avanza
    assert c.siguiente().nombre == "foto_01.png" and c.indice == 1
    assert c.ver().nombre == "foto_02.png"
    c.siguiente(); c.siguiente()
    assert c.ver() is None and c.siguiente() is None and c.indice == 3


def test_listar_carpetas_solo_da_las_que_tienen_fotos_y_calibracion(tmp_path):
    from vision.proveedores import listar_carpetas
    _carpeta_con_fotos(tmp_path / "bueno")
    _carpeta_con_fotos(tmp_path / "sin_calibrar", calibrada=False)
    _carpeta_con_fotos(tmp_path / "con;punto_y_coma")
    _carpeta_con_fotos(tmp_path / ".oculta")
    (tmp_path / "vacia").mkdir()
    (tmp_path / "vacia" / "camara.json").write_text("{}", encoding="utf-8")
    (tmp_path / "suelto.txt").write_text("x", encoding="utf-8")
    assert listar_carpetas(tmp_path) == ["bueno"]
    assert listar_carpetas(tmp_path / "no_existe") == []


def test_los_nombres_se_reparten_en_trozos_que_caben_en_un_mensaje_de_rapid():
    from vision.proveedores import trocear_nombres
    assert trocear_nombres(["a", "bb", "ccc"]) == (["a;bb;ccc"], 0)
    assert trocear_nombres([]) == ([], 0)
    nombres = [f"carpeta_{k:02d}" for k in range(30)]                       # 10 caracteres cada una
    trozos, omitidos = trocear_nombres(nombres, largo_max=65, trozos_max=3)
    assert len(trozos) == 3 and all(len(t) <= 65 for t in trozos)
    assert omitidos == 30 - sum(len(t.split(";")) for t in trozos) and omitidos > 0
    assert trocear_nombres(["x" * 70, "ok"]) == (["ok"], 1)                   # un nombre mas largo que el mensaje se omite


def test_vista_previa_ensena_la_foto_con_la_caja_sin_gastarla(tmp_path):
    from vision.proveedores import Carpeta
    f = FuenteCamara(Carpeta(_carpeta_con_fotos(tmp_path / "juego", n=2)), _cam(), Z_CINTA, params={"modo": "profundidad"}, tiempo_max_s=0.3, pausa_s=0.01)
    v1, v2 = f.vista_previa(), f.vista_previa()
    assert v1 is v2                                                          # misma foto: sale de la cache
    assert v1.elegida is not None and v1.elegida.largo == pytest.approx(200.0, abs=1.5)
    assert (v1.indice, v1.total, v1.origen) == (1, 2, "carpeta juego")
    assert f.n_imagenes() == 2 and f.total() is None
    c0 = f.leer(0)                                                           # el ciclo si la gasta...
    assert c0.largo == pytest.approx(200.0, abs=1.5)
    v3 = f.vista_previa()                                                    # ...y la vista previa pasa a la siguiente
    assert v3.indice == 2 and v3.elegida.largo == pytest.approx(190.0, abs=1.5)
    f.leer(1)
    agotada = f.vista_previa()
    assert agotada.fotograma is None and agotada.total == 2


def test_al_medir_avisa_con_la_foto_y_la_caja_elegida_y_un_fallo_no_para_el_ciclo(tmp_path):
    from vision.proveedores import Carpeta
    f = FuenteCamara(Carpeta(_carpeta_con_fotos(tmp_path / "juego", n=2)), _cam(), Z_CINTA, params={"modo": "profundidad"}, tiempo_max_s=0.3, pausa_s=0.01)
    avisos = []
    f.al_medir = lambda fot, dets, elegida, i: avisos.append((fot.nombre, elegida.largo, i))
    f.leer(0)
    assert avisos == [("foto_01.png", pytest.approx(200.0, abs=1.5), 0)]
    f.al_medir = lambda *a: 1 / 0
    assert f.leer(1).largo == pytest.approx(190.0, abs=1.5)                  # el aviso falla y la caja se mide igual


def test_usar_carpeta_cambia_de_fotos_y_de_calibracion_y_restaurar_vuelve(tmp_path):
    from vision.proveedores import Carpeta
    base = _carpeta_con_fotos(tmp_path / "base", n=1)
    otra_cam = camara_cenital(tam=(960, 720), altura_mm=500.0, centro_xy=(700.0, 0.0), z_plano=Z_CINTA)
    otra = _carpeta_con_fotos(tmp_path / "otra", n=3, cam=otra_cam)
    f = FuenteCamara(Carpeta(base), _cam(), Z_CINTA, params={"modo": "profundidad"}, tiempo_max_s=0.3, pausa_s=0.01)
    assert f.usar_carpeta(otra) == 3 and f.n_imagenes() == 3 and f.origen() == "carpeta otra"
    assert f.modelo.posicion[2] == pytest.approx(500.0 + 0.0, abs=1.0) or f.modelo is not f._modelo_base   # la calibracion es la de esa carpeta
    assert f.leer(0).largo == pytest.approx(200.0, abs=1.5)
    f.restaurar_origen()
    assert f.n_imagenes() == 1 and f.origen() == "carpeta base" and f.modelo is f._modelo_base
    with pytest.raises(ValueError, match="no existe"):
        f.usar_carpeta(tmp_path / "fantasma")
    sin = _carpeta_con_fotos(tmp_path / "sin", n=1, calibrada=False)
    with pytest.raises(ValueError, match="no tiene camara.json"):
        f.usar_carpeta(sin)
    assert f.usar_carpeta(sin, exigir_calibracion=False) == 1                # con la de la configuracion


def test_el_ciclo_y_la_vista_previa_desde_hilos_distintos_no_se_pisan(tmp_path):
    import threading
    from vision.proveedores import Carpeta
    f = FuenteCamara(Carpeta(_carpeta_con_fotos(tmp_path / "juego", n=6)), _cam(), Z_CINTA, params={"modo": "profundidad"}, tiempo_max_s=10.0, pausa_s=0.01)
    parar, fallos = threading.Event(), []

    def previa():
        while not parar.is_set():
            try:
                f.vista_previa()
            except Exception as e:   # noqa: BLE001
                fallos.append(repr(e))
    hilo = threading.Thread(target=previa)
    hilo.start()
    try:
        largos = [f.leer(i).largo for i in range(6)]
    finally:
        parar.set()
        hilo.join(5.0)
    assert fallos == [] and largos == pytest.approx([200.0, 190.0, 180.0, 170.0, 160.0, 150.0], abs=2.0)


def test_con_otra_resolucion_que_la_de_la_calibracion_no_se_mide_en_silencio(tmp_path):
    """Una imagen de 640x480 con una calibracion de 960x720 daria cajas de dos tercios de su tamano: tiene que parar y decirlo."""
    from vision.proveedores import Carpeta
    carpeta = _carpeta_con_fotos(tmp_path / "juego", n=2)
    chica = Fotograma(cv2.resize(cv2.imread(str(carpeta / "foto_01.png")), (640, 480)), None, "chica")
    fuente = FuenteCamara(_Lista([chica] * 20), _cam(), Z_CINTA, params={"modo": "color"}, alto_mm=120.0, tiempo_max_s=0.3, pausa_s=0.01)
    with pytest.raises(RuntimeError, match="la imagen mide 640x480 y la calibracion de la camara es de 960x720"):
        fuente.leer(0)
    fuente2 = FuenteCamara(Carpeta(carpeta), _cam(), Z_CINTA, params={"modo": "profundidad"}, tiempo_max_s=0.3, pausa_s=0.01)
    assert fuente2.vista_previa().elegida is not None                                  # con su resolucion, bien
    fuente2.proveedor = _Lista([chica])
    with pytest.raises(RuntimeError, match="misma resolucion"):
        fuente2.vista_previa()


class _PorRed(_Lista):
    """Como una camara por red: a veces no llega imagen y dice por que."""

    motivo = "el movil no envia fotos"

    def siguiente(self):
        f = super().siguiente()
        return None if f == "corte" else f


def test_un_corte_pasajero_de_la_camara_por_red_no_para_la_celda():
    foto = _foto([CajaSintetica(200.0, 140.0, 100.0, 25.0, (700.0, 20.0))])
    fuente = _fuente(["corte", foto])
    fuente.proveedor = _PorRed(["corte", foto])
    assert fuente.leer(0).largo == pytest.approx(200.0, abs=6)


def test_si_la_camara_por_red_no_vuelve_dice_por_que():
    fuente = _fuente([], tiempo_max_s=0.1)
    fuente.proveedor = _PorRed([])
    with pytest.raises(RuntimeError, match="la camara no da imagen: el movil no envia fotos"):
        fuente.leer(0)
