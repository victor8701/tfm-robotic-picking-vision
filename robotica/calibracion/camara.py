"""Programa de calibración de la cámara para la puesta en marcha de la celda.

Deja un JSON (`camara.json`) con los intrínsecos de la cámara y su pose en la base del robot, que usa la detección de cajas
(`vision.deteccion`, `celda.percepcion.FuenteCamara`). Se hace en tres pasos, con un tablero de ajedrez impreso:

  1. Imprimir el tablero a escala:
         python3 -m calibracion.camara tablero --columnas 9 --filas 6 --cuadro 25 --salida tablero.png
     (imprimir al 100 % y medir un cuadro con una regla; ese lado es el `--cuadro` de los pasos siguientes).

  2. Intrínsecos (una vez por cámara y objetivo): 12 a 20 fotos del tablero desde distintas posiciones e inclinaciones, en una
     carpeta, ocupando la imagen entera en alguna de ellas.
         python3 -m calibracion.camara intrinsecos fotos_tablero/ --tablero 9x6 --cuadro 25 --salida intrinsecos.json
     Si de momento solo se sabe el campo de visión (la RealSense trae calibración de fábrica), vale `--fov 69` en el paso 3.

  3. Posición de la cámara en la base: con la cámara FIJA donde va a trabajar, el tablero tendido boca arriba sobre la cinta (a la
     altura de la superficie donde apoyan las cajas) y entero en la imagen, una foto. Con el TCP de la pinza (o una punta) se tocan dos
     o más esquinas del tablero y se anotan sus coordenadas x, y en la base del robot (FlexPendant, Cartesiano, Base). Cada esquina
     se nombra por su columna y su fila (0, 0 es la de arriba a la izquierda en la foto; el programa guarda una foto anotada con los
     índices). Con tres o más puntos se comprueba que la medida es coherente; conviene tocar además dos o tres esquinas sin usar
     para validar (`--valida`).
         python3 -m calibracion.camara extrinsecos foto_cinta.png --intrinsecos intrinsecos.json --tablero 9x6 --cuadro 25 \\
             --z 220 --toca "0,0:700,-100" --toca "8,0:700,100" --toca "0,5:550,-100" --valida "8,5:550,100" --salida camara.json

Códigos de salida: 0 correcto (criterio "objetivo" o "aceptable"); 1 criterio "repetir"; 2 datos incorrectos.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nucleo.geometria import Pose, desde_matriz  # noqa: E402
from vision.camara import ModeloCamara, intrinsecos_por_campo_de_vision  # noqa: E402
from vision.proveedores import listar_imagenes  # noqa: E402
from vision.tablero import Tablero, detectar_esquinas, pose_tablero  # noqa: E402

UMBRAL_OBJETIVO_MM = 2.0
UMBRAL_ACEPTABLE_MM = 5.0
MIN_IMAGENES_INTRINSECOS = 8


# ---------------------------------------------------------------- tablero para imprimir
def imagen_tablero(tablero: Tablero, dpi: int = 300, margen_mm: float = 10.0) -> np.ndarray:
    """Imagen del tablero (cuadros de `cuadro_mm` exactos al imprimirla a `dpi`) con un margen blanco y una línea de texto."""
    px_mm = dpi / 25.4
    p = max(8, int(round(tablero.cuadro_mm * px_mm)))
    nc, nf = tablero.columnas + 1, tablero.filas + 1
    m = int(round(margen_mm * px_mm))
    pie = int(round(12 * px_mm))
    img = np.full((nf * p + 2 * m + pie, nc * p + 2 * m), 255, np.uint8)
    for f in range(nf):
        for c in range(nc):
            if (f + c) % 2 == 0:
                img[m + f * p:m + (f + 1) * p, m + c * p:m + (c + 1) * p] = 0
    texto = f"Tablero {tablero.columnas}x{tablero.filas} esquinas, cuadro {tablero.cuadro_mm:g} mm. Imprimir al 100 %."
    cv2.putText(img, texto, (m, img.shape[0] - int(pie * 0.35)), cv2.FONT_HERSHEY_SIMPLEX, p / 70.0 * 0.9, 0, max(1, p // 40), cv2.LINE_AA)
    return img


def guardar_tablero(tablero: Tablero, ruta, dpi: int = 300) -> None:
    img = imagen_tablero(tablero, dpi)
    try:
        from PIL import Image
        Image.fromarray(img).save(str(ruta), dpi=(dpi, dpi))   # con los puntos por pulgada: la impresora respeta la escala
    except ImportError:
        cv2.imwrite(str(ruta), img)


# ---------------------------------------------------------------- intrínsecos
@dataclass(frozen=True)
class InformeIntrinsecos:
    K: np.ndarray
    dist: np.ndarray
    tam: tuple[int, int]
    rms_px: float
    n_usadas: int
    rms_por_imagen: dict = field(default_factory=dict)
    descartadas: list = field(default_factory=list)


def calibrar_intrinsecos(imagenes: dict[str, np.ndarray], tablero: Tablero) -> InformeIntrinsecos:
    """Calibra K y la distorsión con fotos del tablero (nombre -> imagen BGR). Las fotos sin tablero se descartan y se dicen."""
    objp = np.hstack([tablero.puntos_plano(), np.zeros((tablero.n_esquinas, 1))]).astype(np.float32)
    objetos, imgs, nombres, descartadas = [], [], [], []
    tam = None
    for nombre, bgr in imagenes.items():
        t = (bgr.shape[1], bgr.shape[0])
        if tam is not None and t != tam:
            raise ValueError(f"{nombre} mide {t[0]}x{t[1]} y las demás {tam[0]}x{tam[1]}: todas las fotos tienen que ser de la misma cámara y resolución")
        tam = t
        esq = detectar_esquinas(bgr, tablero)
        if esq is None:
            descartadas.append(nombre)
            continue
        objetos.append(objp)
        imgs.append(esq.astype(np.float32).reshape(-1, 1, 2))
        nombres.append(nombre)
    if len(objetos) < MIN_IMAGENES_INTRINSECOS:
        raise ValueError(f"solo veo el tablero en {len(objetos)} fotos y hacen falta al menos {MIN_IMAGENES_INTRINSECOS} "
                         f"(sin tablero: {', '.join(descartadas) or 'ninguna'})")
    flags = cv2.CALIB_ZERO_TANGENT_DIST | cv2.CALIB_FIX_K3
    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(objetos, imgs, tam, None, None, flags=flags)
    por_imagen = {}
    for n, o, i, r, t in zip(nombres, objetos, imgs, rvecs, tvecs):
        proy, _ = cv2.projectPoints(o, r, t, K, dist)
        por_imagen[n] = float(np.sqrt(np.mean(np.sum((proy.reshape(-1, 2) - i.reshape(-1, 2)) ** 2, axis=1))))
    return InformeIntrinsecos(K, dist.reshape(-1), tam, float(rms), len(objetos), por_imagen, descartadas)


def guardar_intrinsecos(informe: InformeIntrinsecos, ruta) -> None:
    Path(ruta).write_text(json.dumps({
        "formato": "intrinsecos-1", "tam": list(informe.tam), "K": informe.K.tolist(), "dist": informe.dist.tolist(),
        "rms_px": informe.rms_px, "n_fotos": informe.n_usadas,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def cargar_intrinsecos(ruta) -> tuple[np.ndarray, np.ndarray, tuple[int, int]]:
    try:
        d = json.loads(Path(ruta).read_text(encoding="utf-8"))
        if d.get("formato") != "intrinsecos-1":
            raise ValueError(f"se esperaba formato 'intrinsecos-1' y es {d.get('formato')!r}")
        return np.asarray(d["K"], dtype=np.float64), np.asarray(d["dist"], dtype=np.float64).reshape(-1), (int(d["tam"][0]), int(d["tam"][1]))
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"no puedo leer los intrínsecos {ruta}: {e}") from None


# ---------------------------------------------------------------- extrínsecos: la cámara en la base del robot
@dataclass(frozen=True)
class Toque:
    """Una esquina del tablero (columna, fila) tocada con el TCP: sus coordenadas x, y en la base (mm)."""
    columna: int
    fila: int
    x: float
    y: float

    @classmethod
    def desde_texto(cls, texto: str) -> "Toque":
        """'8,0:700,100' -> columna 8, fila 0, x 700, y 100."""
        try:
            esquina, punto = texto.split(":")
            c, f = (int(v) for v in esquina.split(","))
            x, y = (float(v) for v in punto.split(","))
        except ValueError:
            raise ValueError(f"un punto se escribe COLUMNA,FILA:X,Y (por ejemplo 8,0:700,100) y es {texto!r}") from None
        return cls(c, f, x, y)


@dataclass(frozen=True)
class InformeExtrinsecos:
    n_esquinas: int
    rms_px: float                       # reproyección de las esquinas con la pose del tablero
    rms_toques_mm: float                # lo que se separan los puntos tocados del tablero rígido ajustado
    rms_validacion_mm: float | None     # error de la cámara en los puntos de validación (independientes del ajuste)
    max_validacion_mm: float | None
    criterio: str                       # "objetivo", "aceptable" o "repetir"
    avisos: list = field(default_factory=list)


def _kabsch_2d(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Giro R (2x2, sin reflexión) y traslación t con b ≈ R a + t, por mínimos cuadrados."""
    ca, cb = a.mean(axis=0), b.mean(axis=0)
    U, _, Vt = np.linalg.svd((a - ca).T @ (b - cb))
    d = np.sign(np.linalg.det(Vt.T @ U.T)) or 1.0
    R = Vt.T @ np.diag([1.0, d]) @ U.T
    return R, cb - R @ ca


def _residuos(a, b, R, t) -> np.ndarray:
    return np.linalg.norm(a @ R.T + t - b, axis=1)


def calibrar_extrinsecos(bgr: np.ndarray, K, dist, tablero: Tablero, toques: list[Toque], z_plano: float,
                         validacion: list[Toque] | None = None) -> tuple[ModeloCamara, InformeExtrinsecos]:
    """Pose de la cámara en la base a partir de una foto del tablero tendido sobre el plano z = z_plano y de las coordenadas de
    algunas esquinas tocadas con el TCP. Los puntos de `validacion` no entran en el ajuste: dan el error real de la cámara."""
    validacion = validacion or []
    if not tablero.origen_inequivoco:
        raise ValueError(f"un tablero de {tablero.columnas}x{tablero.filas} esquinas puede salir girado 180° en la foto y el origen sería "
                         "ambiguo: usa una cuenta par y otra impar (9x6, 7x4...)")
    if len(toques) < 2:
        raise ValueError("hacen falta al menos 2 esquinas tocadas con el TCP (mejor 3 o más, y alguna más para validar)")
    esq = detectar_esquinas(bgr, tablero)
    if esq is None:
        raise ValueError(f"no veo el tablero de {tablero.columnas}x{tablero.filas} esquinas en la imagen: que salga entero, sin brillos y enfocado")
    T_cam_tab, rms_px = pose_tablero(esq, tablero, K, dist)
    plano = tablero.puntos_plano()
    uv = np.array([plano[tablero.indice(t.columna, t.fila)] for t in toques])
    xy = np.array([[t.x, t.y] for t in toques])
    R2, t2 = _kabsch_2d(uv, xy)
    res = _residuos(uv, xy, R2, t2)
    avisos = []
    rms_toques = float(np.sqrt(np.mean(res ** 2)))
    # ¿se habrán cruzado los índices (tablero visto al revés)? Con una reflexión el ajuste mejora de golpe.
    if len(toques) >= 3 and rms_toques > UMBRAL_ACEPTABLE_MM:
        espejo = uv * np.array([1.0, -1.0])
        Re, te = _kabsch_2d(espejo, xy)
        if float(np.sqrt(np.mean(_residuos(espejo, xy, Re, te) ** 2))) < 0.5 * rms_toques:
            avisos.append("los puntos tocados encajan mucho mejor con el tablero reflejado: revisa las columnas y las filas que has "
                          "dado (la foto anotada marca las esquinas) o si has tocado las esquinas del otro lado")
    if rms_toques > UMBRAL_ACEPTABLE_MM:
        avisos.append(f"los puntos tocados no son coherentes con un tablero rígido (error {rms_toques:.1f} mm): repite el toque o revisa el índice")
    # marco del tablero -> base (el tablero está tendido sobre el plano z_plano, con su z hacia arriba)
    T_base_tab = np.eye(4)
    T_base_tab[:2, :2] = R2
    T_base_tab[:2, 3] = t2
    T_base_tab[2, 3] = z_plano
    T_base_cam = T_base_tab @ np.linalg.inv(T_cam_tab)
    modelo = ModeloCamara(np.asarray(K, dtype=np.float64), np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64),
                          Pose(T_base_cam[:3, 3].copy(), desde_matriz(T_base_cam[:3, :3])), (bgr.shape[1], bgr.shape[0]))
    if T_base_cam[2, 2] > -0.3:
        avisos.append("la cámara no mira hacia abajo con claridad (eje óptico poco vertical): la detección está pensada para cámara cenital")

    rms_val = max_val = None
    if validacion:
        px = np.array([esq[tablero.indice(t.columna, t.fila)] for t in validacion])
        pred = modelo.pixel_a_plano(px, z_plano)
        err = np.linalg.norm(pred - np.array([[t.x, t.y] for t in validacion]), axis=1)
        rms_val, max_val = float(np.sqrt(np.mean(err ** 2))), float(err.max())
    medida = rms_val if rms_val is not None else rms_toques
    criterio = "objetivo" if medida < UMBRAL_OBJETIVO_MM else ("aceptable" if medida < UMBRAL_ACEPTABLE_MM else "repetir")
    if rms_val is None:
        avisos.append("sin puntos de validación (--valida): el criterio se basa en lo coherentes que son los puntos tocados")
    informe = InformeExtrinsecos(len(esq), rms_px, rms_toques, rms_val, max_val, criterio, avisos)
    info = {"origen": "calibracion.camara", "fecha": datetime.now().isoformat(timespec="seconds"), "z_plano_mm": z_plano,
            "rms_px": rms_px, "rms_toques_mm": rms_toques, "rms_validacion_mm": rms_val, "criterio": criterio, "tablero": f"{tablero.columnas}x{tablero.filas}",
            "cuadro_mm": tablero.cuadro_mm}
    return ModeloCamara(modelo.K, modelo.dist, modelo.T_base_cam, modelo.tam, info), informe


def anotar_tablero(bgr: np.ndarray, tablero: Tablero) -> np.ndarray:
    """Foto con el tablero detectado y marcadas las esquinas de las cuatro puntas con su (columna, fila): para saber qué índice dar."""
    img = bgr.copy()
    esq = detectar_esquinas(bgr, tablero)
    if esq is None:
        cv2.putText(img, "tablero no detectado", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2, cv2.LINE_AA)
        return img
    cv2.drawChessboardCorners(img, (tablero.columnas, tablero.filas), esq.astype(np.float32).reshape(-1, 1, 2), True)
    for c, f in ((0, 0), (tablero.columnas - 1, 0), (0, tablero.filas - 1), (tablero.columnas - 1, tablero.filas - 1)):
        p = esq[tablero.indice(c, f)]
        cv2.putText(img, f"({c},{f})", (int(p[0]) + 8, int(p[1]) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(img, f"({c},{f})", (int(p[0]) + 8, int(p[1]) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
    return img


# ---------------------------------------------------------------- línea de comandos
def _imagenes(ruta) -> dict[str, np.ndarray]:
    out = {}
    for f in listar_imagenes(ruta):
        img = cv2.imread(str(f), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"no puedo leer la imagen {f}")
        out[f.name] = img
    return out


def _cmd_tablero(a) -> int:
    t = Tablero(a.columnas, a.filas, a.cuadro)
    guardar_tablero(t, a.salida, a.dpi)
    print(f"tablero {t.columnas}x{t.filas} esquinas ({t.columnas + 1}x{t.filas + 1} cuadros de {t.cuadro_mm:g} mm) en {a.salida}")
    print("Imprímelo al 100 % (sin ajustar a la página) y mide un cuadro con una regla: ese es el --cuadro de los pasos siguientes.")
    return 0


def _cmd_intrinsecos(a) -> int:
    inf = calibrar_intrinsecos(_imagenes(a.fotos), Tablero.desde_texto(a.tablero, a.cuadro))
    guardar_intrinsecos(inf, a.salida)
    print(f"{inf.n_usadas} fotos usadas, error de reproyección {inf.rms_px:.2f} px (bueno: menos de 0,5; revisar: más de 1)")
    f = inf.K[0, 0]
    print(f"distancia focal {f:.0f} px, centro ({inf.K[0, 2]:.0f}, {inf.K[1, 2]:.0f}), campo de visión horizontal {np.degrees(2 * np.arctan(inf.tam[0] / (2 * f))):.0f}°")
    peores = sorted(inf.rms_por_imagen.items(), key=lambda kv: -kv[1])[:3]
    print("peores fotos: " + ", ".join(f"{n} ({e:.2f} px)" for n, e in peores))
    if inf.descartadas:
        print(f"sin tablero detectado: {', '.join(inf.descartadas)}")
    return 1 if inf.rms_px > 1.0 else 0


def _cmd_extrinsecos(a) -> int:
    bgr = cv2.imread(a.foto, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"no puedo leer la imagen {a.foto}")
    tablero = Tablero.desde_texto(a.tablero, a.cuadro)
    if a.intrinsecos:
        K, dist, tam = cargar_intrinsecos(a.intrinsecos)
        if tam != (bgr.shape[1], bgr.shape[0]):
            raise ValueError(f"los intrínsecos son de {tam[0]}x{tam[1]} y la foto mide {bgr.shape[1]}x{bgr.shape[0]}")
    elif a.fov:
        K, dist = intrinsecos_por_campo_de_vision((bgr.shape[1], bgr.shape[0]), a.fov), np.zeros(5)
    else:
        raise ValueError("falta --intrinsecos (de calibracion.camara intrinsecos) o, de momento, --fov (campo de visión horizontal en grados)")
    cv2.imwrite(a.anotada, anotar_tablero(bgr, tablero))
    modelo, inf = calibrar_extrinsecos(bgr, K, dist, tablero, [Toque.desde_texto(t) for t in a.toca], a.z,
                                       [Toque.desde_texto(t) for t in (a.valida or [])])
    modelo.guardar(a.salida)
    o = modelo.posicion
    print(f"cámara en la base: x {o[0]:.0f}, y {o[1]:.0f}, z {o[2]:.0f} mm (a {o[2] - a.z:.0f} mm sobre el plano)")
    print(f"error de reproyección del tablero {inf.rms_px:.2f} px; puntos tocados vs tablero rígido {inf.rms_toques_mm:.2f} mm")
    if inf.rms_validacion_mm is not None:
        print(f"VALIDACIÓN: error {inf.rms_validacion_mm:.2f} mm (máximo {inf.max_validacion_mm:.2f} mm)")
    print(f"criterio: {inf.criterio} (objetivo < {UMBRAL_OBJETIVO_MM:g} mm, aceptable < {UMBRAL_ACEPTABLE_MM:g} mm)")
    for aviso in inf.avisos:
        print("AVISO: " + aviso)
    print(f"calibración en {a.salida}; foto con los índices de las esquinas en {a.anotada}")
    return 1 if inf.criterio == "repetir" else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden", required=True)

    t = sub.add_parser("tablero", help="genera el tablero para imprimir")
    t.add_argument("--columnas", type=int, default=9, help="esquinas interiores a lo ancho (par o impar, la otra cuenta al revés)")
    t.add_argument("--filas", type=int, default=6)
    t.add_argument("--cuadro", type=float, default=25.0, help="lado del cuadro en mm")
    t.add_argument("--dpi", type=int, default=300)
    t.add_argument("--salida", default="tablero.png")

    i = sub.add_parser("intrinsecos", help="intrínsecos y distorsión con fotos del tablero")
    i.add_argument("fotos", help="carpeta con las fotos del tablero")
    i.add_argument("--tablero", default="9x6", help="esquinas interiores, columnasxfilas")
    i.add_argument("--cuadro", type=float, required=True, help="lado del cuadro en mm (medido)")
    i.add_argument("--salida", default="intrinsecos.json")

    e = sub.add_parser("extrinsecos", help="pose de la cámara en la base del robot")
    e.add_argument("foto", help="foto de la cámara fija con el tablero sobre la cinta")
    e.add_argument("--intrinsecos", help="JSON de `intrinsecos`")
    e.add_argument("--fov", type=float, help="campo de visión horizontal (°) si no hay intrínsecos; menos preciso")
    e.add_argument("--tablero", default="9x6")
    e.add_argument("--cuadro", type=float, required=True)
    e.add_argument("--z", type=float, required=True, help="altura de la superficie donde está el tablero en la base (mm); zCinta")
    e.add_argument("--toca", action="append", required=True, metavar="COL,FILA:X,Y", help="esquina tocada con el TCP y sus x, y en la base (2 o más)")
    e.add_argument("--valida", action="append", metavar="COL,FILA:X,Y", help="esquina tocada que NO entra en el ajuste (valida)")
    e.add_argument("--salida", default="camara.json")
    e.add_argument("--anotada", default="tablero_detectado.png", help="foto con los índices de las esquinas")

    if not (sys.argv[1:] if argv is None else argv):
        # sin orden: en vez del error seco de argparse, la guia y las tres ordenes
        ap.print_help()
        print("\nFalta la orden: tablero, intrinsecos o extrinsecos (en ese orden, ver arriba). Por ejemplo:\n"
              "  python3 -m calibracion.camara tablero --columnas 9 --filas 6 --cuadro 25 --salida tablero.png\n"
              "  python3 -m calibracion.camara intrinsecos -h   (ayuda de una orden)", file=sys.stderr)
        return 2
    args = ap.parse_args(argv)
    try:
        return {"tablero": _cmd_tablero, "intrinsecos": _cmd_intrinsecos, "extrinsecos": _cmd_extrinsecos}[args.orden](args)
    except (OSError, ValueError, json.JSONDecodeError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
