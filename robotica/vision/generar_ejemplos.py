"""Genera imágenes de ejemplo para probar los programas de visión sin cámara ni robot.

    python3 -m vision.generar_ejemplos ejemplos_vision/

Crea en esa carpeta:
  casa/            fotos cenitales de una mesa con un tablero de ajedrez 9x6 (cuadro de 25 mm) y una caja de cartón de tamaño y giro
                   distintos en cada una, con la profundidad (.npy) de cada foto en `casa_prof/`
  fondo.png        la misma escena sin cajas (para --modo fondo)
  celda/           fotos de una cámara fija sobre la cinta de la celda (base del robot) y `camara.json` con su calibración
  verdad.csv       lo que mide cada caja y dónde está (para comparar con lo que da el programa)

Después:
    python3 -m vision.probar_en_casa ejemplos_vision/casa --tablero 9x6 --cuadro 25 --fov 62     (alto medido con la profundidad .npy)
    python3 -m vision.probar_en_casa ejemplos_vision/casa --tablero 9x6 --cuadro 25 --fov 62 --alto 120 --esperado 200,140
    python3 -m vision.probar_en_casa ejemplos_vision/celda --calibracion ejemplos_vision/celda/camara.json --z 220
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nucleo.geometria import Pose, desde_matriz  # noqa: E402
from vision.escena import CajaSintetica, camara_cenital, escena, profundidad  # noqa: E402
from vision.tablero import Tablero  # noqa: E402

TABLERO = Tablero(9, 6, 25.0)
# (largo, ancho, alto, giro, centro): una caja por foto
# El tablero ocupa x de 0 a 200 e y de -125 a 0 (esquina (0, 0) arriba a la izquierda): las cajas van a su derecha.
CAJAS_CASA = [
    (200.0, 140.0, 120.0, 0.0, (400.0, -60.0)),
    (200.0, 140.0, 120.0, 25.0, (410.0, -70.0)),
    (200.0, 140.0, 120.0, -40.0, (395.0, -55.0)),
    (180.0, 180.0, 100.0, 10.0, (405.0, -65.0)),
    (150.0, 90.0, 80.0, 70.0, (400.0, -60.0)),
]


def generar(carpeta: Path) -> None:
    casa, prof, celda = carpeta / "casa", carpeta / "casa_prof", carpeta / "celda"
    for d in (casa, prof, celda):
        d.mkdir(parents=True, exist_ok=True)
    verdad = []
    # En casa: el tablero (esquina (0, 0) en el origen) y la caja sobre la misma mesa, cámara a 800 mm
    cam = camara_cenital(altura_mm=800.0, centro_xy=(250.0, -60.0), fov_horizontal_deg=62.0, inclinacion_deg=2.0)
    T_tab = Pose.crear(t=[0.0, 0.0, 0.0])
    for n, (l, a, h, g, c) in enumerate(CAJAS_CASA, start=1):
        caja = CajaSintetica(l, a, h, g, c)
        nombre = f"casa_{n:02d}"
        cv2.imwrite(str(casa / f"{nombre}.png"), escena(cam, [caja], TABLERO, T_tab, ruido=2.0, semilla=n))
        np.save(casa / f"{nombre}.npy", profundidad(cam, [caja]))
        verdad.append([f"casa/{nombre}.png", l, a, h, g, c[0], c[1]])
    cv2.imwrite(str(carpeta / "fondo.png"), escena(cam, [], TABLERO, T_tab, ruido=2.0, semilla=99))
    # En la celda: cámara fija 650 mm sobre la cinta (z = 220), cerca de la recogida (700, 0)
    cam_c = camara_cenital(altura_mm=650.0, centro_xy=(690.0, 5.0), fov_horizontal_deg=62.0, inclinacion_deg=2.0, z_plano=220.0)
    from vision.camara import ModeloCamara
    ModeloCamara(cam_c.K, cam_c.dist, cam_c.T_base_cam, cam_c.tam, {"origen": "ejemplo sintetico"}).guardar(celda / "camara.json")
    cajas_celda = [(200.0, 140.0, 120.0, 0.0, (700.0, 0.0)), (200.0, 140.0, 120.0, -45.0, (715.0, -10.0)), (160.0, 100.0, 90.0, 60.0, (690.0, 15.0))]
    for n, (l, a, h, g, c) in enumerate(cajas_celda, start=1):
        caja = CajaSintetica(l, a, h, g, c)
        nombre = f"celda_{n:02d}"
        cv2.imwrite(str(celda / f"{nombre}.png"), escena(cam_c, [caja], z_plano=220.0, ruido=2.0, semilla=n))
        np.save(celda / f"{nombre}.npy", profundidad(cam_c, [caja], z_plano=220.0))
        verdad.append([f"celda/{nombre}.png", l, a, h, g, c[0], c[1]])
    with open(carpeta / "verdad.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["imagen", "largo", "ancho", "alto", "giro", "centro_x", "centro_y"])
        w.writerows(verdad)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", nargs="?", default="ejemplos_vision")
    args = ap.parse_args(argv)
    generar(Path(args.carpeta))
    print(f"ejemplos en {args.carpeta}/ (casa/, fondo.png, celda/ y verdad.csv); mira la cabecera de vision/generar_ejemplos.py para probarlos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
