"""Programa para probar la visión en casa con imágenes cargadas, sin robot ni cámara de la celda.

Mide las cajas de cada foto (largo, ancho, alto, giro y posición) con la misma detección que usará la celda
(`vision.deteccion`) y deja una imagen anotada por foto y los resultados en CSV.

Dos formas de dar escala y marco de referencia:

  EN CASA (por defecto con --tablero): en cada foto aparece un tablero de ajedrez impreso (`python3 -m calibracion.camara tablero`)
  apoyado en la misma superficie que las cajas. El tablero da la escala, el origen (su esquina (0, 0)) y el plano z = 0; las
  posiciones salen en mm en el marco del tablero. Si no se conoce la cámara, `--fov` (campo de visión horizontal en grados, unos 65-70
  en un móvil) basta para tener las medidas con un error de pocos %; con `--intrinsecos` (de `calibracion.camara intrinsecos`) mejora.

  CON LA CALIBRACIÓN DE LA PUESTA EN MARCHA (--calibracion camara.json): fotos de la cámara de la celda; las posiciones salen en la
  base del robot y el plano de la cinta está a la altura `--z` (zCinta).

Uso:
    python3 -m vision.probar_en_casa fotos/ --tablero 9x6 --cuadro 25 --fov 65 --alto 120
    python3 -m vision.probar_en_casa fotos/ --calibracion camara.json --z 220 --alto 120
    python3 -m vision.probar_en_casa foto.jpg --tablero 9x6 --cuadro 25 --fov 65 --alto 120 --esperado 300,200 --interactivo

El alto de la caja se da con --alto (el mismo para todas) salvo con --modo profundidad y un mapa de profundidad junto a la foto
(`foto.npy` en mm). --modo fondo usa una foto `fondo.png` de la escena sin cajas (no depende del color de la caja). Con
--interactivo se abre una ventana con barras para ajustar el rango de color (HSV); Intro acepta y --guardar-params lo guarda.

Resultados en --salida (por defecto resultados_vision/): `<foto>_anotada.png`, `detecciones.csv` (todas las cajas con sus medidas) y
`caja_vision.csv` (una caja por foto en el formato `largo;ancho;alto;giro` de caja.csv, para alimentar la simulación con medidas reales).

Códigos de salida: 0 todas las fotos con caja; 1 alguna foto sin caja o sin tablero; 2 datos incorrectos.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibracion.camara import cargar_intrinsecos  # noqa: E402
from vision.camara import ModeloCamara, intrinsecos_por_campo_de_vision  # noqa: E402
from vision.deteccion import PARAMS_POR_DEFECTO, Deteccion, detectar_cajas, dibujar, elegir, mascara_color  # noqa: E402
from vision.proveedores import cargar_fotograma, listar_imagenes  # noqa: E402
from vision.tablero import Tablero, detectar_esquinas, modelo_desde_tablero  # noqa: E402


def _param_hsv(args, params: dict) -> dict:
    p = dict(params)
    if args.hsv_bajo:
        p["hsv_bajo"] = tuple(args.hsv_bajo)
    if args.hsv_alto:
        p["hsv_alto"] = tuple(args.hsv_alto)
    p["modo"] = args.modo
    if args.umbral_fondo is not None:
        p["umbral_fondo"] = args.umbral_fondo
    return p


def modelo_de_la_foto(bgr, args, tablero: Tablero | None, K, dist, fijo: ModeloCamara | None) -> ModeloCamara | None:
    """El modelo de cámara de esta foto: el de la calibración, o el que sale del tablero que aparece en ella."""
    if fijo is not None:
        if (bgr.shape[1], bgr.shape[0]) != tuple(fijo.tam):
            raise ValueError(f"la foto mide {bgr.shape[1]}x{bgr.shape[0]} y la calibración es de {fijo.tam[0]}x{fijo.tam[1]}")
        return fijo
    Ki = K if K is not None else intrinsecos_por_campo_de_vision((bgr.shape[1], bgr.shape[0]), args.fov)
    return modelo_desde_tablero(bgr, tablero, Ki, dist)


def procesar(ficheros: list[Path], args, params: dict, fijo: ModeloCamara | None, tablero: Tablero | None, K, dist,
             fondo: np.ndarray | None, salida: Path) -> tuple[list[dict], list[str]]:
    """Mide todas las fotos. Devuelve las filas de resultados y los avisos de las fotos que no se han podido medir."""
    filas, problemas = [], []
    for f in ficheros:
        fot = cargar_fotograma(f)
        modelo = modelo_de_la_foto(fot.bgr, args, tablero, K, dist, fijo)
        if modelo is None:
            problemas.append(f"{f.name}: no veo el tablero de {tablero.columnas}x{tablero.filas} esquinas (entero, enfocado, sin brillos)")
            cv2.imwrite(str(salida / f"{f.stem}_anotada.png"), _sin_resultado(fot.bgr, "sin tablero"))
            continue
        z_plano = 0.0 if fijo is None else args.z
        # el alto: el que se da con --alto; con profundidad (modo profundidad, o mapa junto a la foto y sin --alto) se mide en cada caja
        alto = None if args.modo == "profundidad" else args.alto
        dets = detectar_cajas(fot.bgr, modelo, z_plano, alto, params, fondo, fot.profundidad)
        elegida = elegir(dets)
        cv2.imwrite(str(salida / f"{f.stem}_anotada.png"), dibujar(fot.bgr, dets, elegida) if dets else _sin_resultado(fot.bgr, "sin caja"))
        if not dets:
            problemas.append(f"{f.name}: no encuentro ninguna caja (ajusta el color con --interactivo o usa --modo fondo)")
            continue
        for d in sorted(dets, key=lambda d: -d.area_px):
            filas.append({"imagen": f.name, "elegida": d is elegida, "d": d})
    return filas, problemas


def _sin_resultado(bgr, texto: str) -> np.ndarray:
    img = bgr.copy()
    cv2.putText(img, texto, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 255), 3, cv2.LINE_AA)
    return img


def escribir_resultados(filas: list[dict], salida: Path) -> None:
    with open(salida / "detecciones.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["imagen", "elegida", "largo", "ancho", "alto", "giro", "centro_x", "centro_y", "confianza", "recortada", "pared_mm"])
        for r in filas:
            d: Deteccion = r["d"]
            w.writerow([r["imagen"], int(r["elegida"]), f"{d.largo:.1f}", f"{d.ancho:.1f}", f"{d.alto:.1f}", f"{d.giro_deg:.1f}",
                        f"{d.centro[0]:.1f}", f"{d.centro[1]:.1f}", f"{d.confianza:.2f}", int(d.recortada), f"{d.pared_mm:.1f}"])
    with open(salida / "caja_vision.csv", "w", encoding="utf-8", newline="") as fh:
        for r in filas:
            if r["elegida"]:
                d = r["d"]
                fh.write(f"{d.largo:.1f};{d.ancho:.1f};{d.alto:.1f};{d.giro_deg:.1f}\n")


def ajustar_hsv(bgr: np.ndarray, params: dict) -> dict:
    """Ventana con barras para el rango HSV: a la izquierda la foto con la máscara en verde. Intro acepta, Esc cancela.
    Necesita pantalla (no vale por SSH ni en WSL sin servidor gráfico)."""
    p = dict(params)
    nombres = [("H min", 0, 180), ("S min", 0, 255), ("V min", 0, 255), ("H max", 0, 180), ("S max", 0, 255), ("V max", 0, 255)]
    inicial = list(p["hsv_bajo"]) + list(p["hsv_alto"])
    ventana = "Ajuste de color (Intro acepta, Esc cancela)"
    try:
        cv2.namedWindow(ventana, cv2.WINDOW_NORMAL)
        for (n, _, mx), v in zip(nombres, inicial):
            cv2.createTrackbar(n, ventana, int(v), mx, lambda _x: None)
    except cv2.error as e:
        raise ValueError("--interactivo necesita una pantalla (esta instalación de OpenCV no puede abrir ventanas)") from e
    escala = min(1.0, 900.0 / max(bgr.shape[:2]))
    while True:
        v = [cv2.getTrackbarPos(n, ventana) for n, _, _ in nombres]
        p["hsv_bajo"], p["hsv_alto"] = tuple(v[:3]), tuple(v[3:])
        m = mascara_color(bgr, p)
        vista = bgr.copy()
        vista[m > 0] = (0.5 * vista[m > 0] + 0.5 * np.array([0, 255, 0])).astype(np.uint8)
        vista = cv2.resize(vista, None, fx=escala, fy=escala)
        cv2.putText(vista, f"HSV {p['hsv_bajo']} - {p['hsv_alto']}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(vista, f"HSV {p['hsv_bajo']} - {p['hsv_alto']}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(ventana, vista)
        tecla = cv2.waitKey(30) & 0xFF
        if tecla in (13, 10):
            break
        if tecla == 27:
            cv2.destroyWindow(ventana)
            raise ValueError("ajuste cancelado")
    cv2.destroyWindow(ventana)
    return p


def _resumen(filas: list[dict], esperado) -> None:
    if not filas:
        return
    print(f"{'imagen':26s} {'':1s} {'largo':>6s} {'ancho':>6s} {'alto':>6s} {'giro':>6s} {'x':>7s} {'y':>7s} {'conf':>5s}  notas")
    for r in filas:
        d: Deteccion = r["d"]
        notas = []
        if d.recortada:
            notas.append("RECORTADA")
        if d.pared_mm > 5.0:
            notas.append(f"pared ~{d.pared_mm:.0f} mm: centra la caja o usa profundidad")
        if esperado and r["elegida"]:
            notas.append(f"error largo {d.largo - esperado[0]:+.1f} ancho {d.ancho - esperado[1]:+.1f} mm")
        print(f"{r['imagen'][:26]:26s} {'*' if r['elegida'] else ' '} {d.largo:6.1f} {d.ancho:6.1f} {d.alto:6.1f} {d.giro_deg:6.1f} "
              f"{d.centro[0]:7.1f} {d.centro[1]:7.1f} {d.confianza:5.2f}  {'; '.join(notas)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entradas", nargs="+", help="fotos o carpetas con fotos")
    ap.add_argument("--calibracion", help="camara.json de calibracion.camara (celda); sin él, el tablero de cada foto")
    ap.add_argument("--tablero", default="9x6", help="esquinas interiores del tablero, columnasxfilas")
    ap.add_argument("--cuadro", type=float, help="lado del cuadro del tablero en mm (medido con regla)")
    ap.add_argument("--intrinsecos", help="intrínsecos.json de la cámara usada")
    ap.add_argument("--fov", type=float, default=65.0, help="campo de visión horizontal (°) si no hay intrínsecos")
    ap.add_argument("--alto", type=float, help="alto de la caja en mm")
    ap.add_argument("--z", type=float, default=0.0, help="con --calibracion, altura de la cinta en la base (mm)")
    ap.add_argument("--modo", choices=("color", "fondo", "profundidad"), default="color")
    ap.add_argument("--fondo", help="foto de la escena sin cajas (modo fondo)")
    ap.add_argument("--umbral-fondo", type=int)
    ap.add_argument("--hsv-bajo", type=int, nargs=3, metavar=("H", "S", "V"))
    ap.add_argument("--hsv-alto", type=int, nargs=3, metavar=("H", "S", "V"))
    ap.add_argument("--params", help="JSON con parámetros de detección (el que guarda --guardar-params)")
    ap.add_argument("--interactivo", action="store_true", help="ajustar el color con barras en una ventana")
    ap.add_argument("--guardar-params", help="guarda los parámetros ajustados en este JSON")
    ap.add_argument("--esperado", help="largo,ancho reales de la caja (mm) para ver el error")
    ap.add_argument("--salida", default="resultados_vision")
    args = ap.parse_args(argv)

    try:
        ficheros = [f for e in args.entradas for f in listar_imagenes(e)]
        if not ficheros:
            raise ValueError("no hay imágenes")
        params = dict(PARAMS_POR_DEFECTO)
        if args.params:
            params.update(json.loads(Path(args.params).read_text(encoding="utf-8")))
        params = _param_hsv(args, params)
        if args.modo != "profundidad" and args.alto is None:
            sin_prof = [f for f in ficheros if not (f.with_suffix(".npy").is_file() or f.with_name(f.stem + "_prof.png").is_file())]
            if sin_prof:
                raise ValueError("falta --alto (alto de la caja en mm): sin mapa de profundidad no se puede medir")
        fijo = ModeloCamara.cargar(args.calibracion) if args.calibracion else None
        tablero = K = dist = None
        if fijo is None:
            if args.cuadro is None:
                raise ValueError("falta --cuadro (lado del cuadro del tablero en mm) o --calibracion")
            tablero = Tablero.desde_texto(args.tablero, args.cuadro)
            if args.intrinsecos:
                K, dist, _ = cargar_intrinsecos(args.intrinsecos)
        fondo = None
        if args.modo == "fondo":
            if not args.fondo:
                raise ValueError("el modo fondo necesita --fondo (foto de la escena sin cajas)")
            fondo = cv2.imread(args.fondo, cv2.IMREAD_COLOR)
            if fondo is None:
                raise ValueError(f"no puedo leer la foto de fondo {args.fondo}")
        esperado = None
        if args.esperado:
            esperado = tuple(float(v) for v in args.esperado.split(","))
            if len(esperado) != 2:
                raise ValueError("--esperado se escribe largo,ancho (mm)")
        if args.interactivo:
            if args.modo != "color":
                raise ValueError("--interactivo ajusta el color: usa --modo color")
            params = ajustar_hsv(cargar_fotograma(ficheros[0]).bgr, params)
            if args.guardar_params:
                Path(args.guardar_params).write_text(json.dumps({"hsv_bajo": list(params["hsv_bajo"]), "hsv_alto": list(params["hsv_alto"])},
                                                                indent=2), encoding="utf-8")
                print(f"parámetros guardados en {args.guardar_params}")
        salida = Path(args.salida)
        salida.mkdir(parents=True, exist_ok=True)
        filas, problemas = procesar(ficheros, args, params, fijo, tablero, K, dist, fondo, salida)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    escribir_resultados(filas, salida)
    _resumen(filas, esperado)
    for p in problemas:
        print("AVISO: " + p)
    print(f"{len({r['imagen'] for r in filas})} de {len(ficheros)} fotos con caja. Resultados en {salida}/ "
          "(imágenes anotadas, detecciones.csv y caja_vision.csv)")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
