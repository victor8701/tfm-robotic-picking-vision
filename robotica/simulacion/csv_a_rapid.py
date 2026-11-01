"""Convierte una trayectoria en CSV en un módulo RAPID con robtargets y un procedimiento de recorrido.

Formato de entrada (el mismo que usan el add-in y EGM_VS del proyecto previo), con cabecera:
    x,y,z,qw,qx,qy,qz
en mm (posición en la base del brazo) y cuaternión unitario (w, x, y, z).

Uso (desde robotica/):
    python3 simulacion/csv_a_rapid.py trayectoria.csv MOD_Trayectoria.mod [--velocidad v20]

Se rechaza cualquier punto fuera del espacio de trabajo de simulacion/celda.json, o un cuaternión
nulo o no finito. NO PROBADO en controlador: revisar el módulo en RobotStudio antes de usarlo.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nucleo.geometria import Pose, normalizar  # noqa: E402
from nucleo.parametros import cargar_celda  # noqa: E402

COLUMNAS = ["x", "y", "z", "qw", "qx", "qy", "qz"]
EJES_EXTERNOS = "[9E9, 9E9, 9E9, 9E9, 9E9, 9E9]"


def leer_csv(ruta: str | Path, espacio) -> list[Pose]:
    """Lee y valida la trayectoria. Devuelve las poses en mm con cuaternión unitario."""
    with open(ruta, newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        if lector.fieldnames is None or [c.strip() for c in lector.fieldnames] != COLUMNAS:
            raise ValueError(f"la cabecera debe ser exactamente {','.join(COLUMNAS)}")
        poses: list[Pose] = []
        for n, fila in enumerate(lector, start=2):
            try:
                valores = [float(fila[c]) for c in COLUMNAS]
            except (TypeError, ValueError) as e:
                raise ValueError(f"línea {n}: valor no numérico") from e
            if not all(math.isfinite(v) for v in valores):
                raise ValueError(f"línea {n}: valor no finito")
            x, y, z, qw, qx, qy, qz = valores
            if math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz) < 1e-9:
                raise ValueError(f"línea {n}: cuaternión nulo")
            p = Pose.crear(t=[x, y, z], q=normalizar([qw, qx, qy, qz]))
            if not espacio.contiene(p.t):
                raise ValueError(f"línea {n}: punto fuera del espacio de trabajo: {p.t.round(1).tolist()}")
            poses.append(p)
    if not poses:
        raise ValueError("la trayectoria no tiene puntos")
    return poses


def _robtarget(nombre: str, p: Pose) -> str:
    x, y, z = (f"{v:.3f}" for v in p.t)
    q1, q2, q3, q4 = (f"{v:.6f}" for v in p.q)
    return f"    CONST robtarget {nombre} := [[{x},{y},{z}],[{q1},{q2},{q3},{q4}],[0,0,0,0],{EJES_EXTERNOS}];"


def generar_modulo(poses: list[Pose], nombre_modulo: str = "MOD_Trayectoria", velocidad: str = "v20") -> str:
    lineas = [
        f"MODULE {nombre_modulo}",
        "    ! Trayectoria generada por simulacion/csv_a_rapid.py. NO PROBADO en controlador.",
        "    ! Revisar en RobotStudio y ejecutar primero en el controlador virtual.",
        "",
    ]
    nombres = [f"p{i + 1:03d}" for i in range(len(poses))]
    lineas += [_robtarget(n, p) for n, p in zip(nombres, poses)]
    lineas += [
        "",
        "    PROC Ejecutar_Trayectoria()",
    ]
    for i, n in enumerate(nombres):
        zona = "fine" if i == len(nombres) - 1 else "z5"
        lineas.append(f"        MoveL {n}, {velocidad}, {zona}, tool0;")
    lineas += [
        "    ENDPROC",
        "",
        f"ENDMODULE",
        "",
    ]
    return "\n".join(lineas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv")
    parser.add_argument("salida")
    parser.add_argument("--velocidad", default="v20", help="velocidad RAPID de los MoveL (por defecto v20)")
    parser.add_argument("--celda", default=None, help="JSON de la celda (por defecto simulacion/celda.json)")
    args = parser.parse_args(argv)
    celda = cargar_celda(args.celda) if args.celda else cargar_celda()
    try:
        poses = leer_csv(args.csv, celda.espacio)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    Path(args.salida).write_text(generar_modulo(poses, velocidad=args.velocidad), encoding="utf-8")
    print(f"{len(poses)} puntos escritos en {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
