"""Línea de comandos para procesar en el laboratorio los datos medidos (visita 1).

Homografía de la mesa. Entrada JSON:
    {"src": [[u, v], ...], "dst": [[x, y], ...], "n_validacion": 2}
    src: píxeles de la cámara; dst: milímetros en la mesa. Mínimo 6 puntos.
Salida: H (3x3), RMS de ajuste y de validación, criterio ("objetivo", "aceptable" o "repetir").

Mano-ojo de la cámara de muñeca. Entrada JSON:
    {"base_mano": [{"t": [x, y, z], "q": [w, x, y, z]}, ...],
     "objetivo_camara": [{"t": [x, y, z], "q": [w, x, y, z]}, ...]}
    base_mano: pose del TCP en la base (mm); objetivo_camara: pose del tablero en la cámara (mm). Mínimo 3 pares.
Salida: X (pose de la cámara en la mano) y la dispersión de la pose del tablero en la base.

Uso (desde robotica/):
    python3 -m calibracion.cli homografia datos.json resultado.json
    python3 -m calibracion.cli mano_ojo datos.json resultado.json

Códigos de salida: 0 correcto; 1 homografía con criterio "repetir"; 2 datos incorrectos.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibracion.handeye import calibrar_mano_ojo, dispersion_objetivo_en_base  # noqa: E402
from calibracion.homografia import evaluar  # noqa: E402
from nucleo.geometria import Pose  # noqa: E402


def _poses(lista) -> list[Pose]:
    return [Pose.crear(t=p["t"], q=p["q"]) for p in lista]


def cmd_homografia(datos: dict) -> dict:
    informe = evaluar(np.asarray(datos["src"], dtype=float), np.asarray(datos["dst"], dtype=float),
                      n_validacion=int(datos.get("n_validacion", 2)))
    return {
        "H": informe.H.tolist(),
        "n_puntos": informe.n_puntos,
        "n_inliers": informe.n_inliers,
        "rms_ajuste_mm": informe.rms_ajuste_mm,
        "rms_validacion_mm": informe.rms_validacion_mm,
        "criterio": informe.criterio,
    }


def cmd_mano_ojo(datos: dict) -> dict:
    base = _poses(datos["base_mano"])
    camara = _poses(datos["objetivo_camara"])
    X = calibrar_mano_ojo(base, camara)
    mm, rad = dispersion_objetivo_en_base(base, camara, X)
    return {
        "X": {"t": X.t.tolist(), "q": X.q.tolist()},
        "dispersion_mm": mm,
        "dispersion_rad": rad,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="orden", required=True)
    for nombre in ("homografia", "mano_ojo"):
        p = sub.add_parser(nombre)
        p.add_argument("entrada")
        p.add_argument("salida")
    args = parser.parse_args(argv)

    try:
        datos = json.loads(Path(args.entrada).read_text(encoding="utf-8"))
        resultado = cmd_homografia(datos) if args.orden == "homografia" else cmd_mano_ojo(datos)
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    Path(args.salida).write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.orden == "homografia":
        print(f"criterio: {resultado['criterio']}  RMS validación: {resultado['rms_validacion_mm']:.2f} mm")
        return 1 if resultado["criterio"] == "repetir" else 0
    print(f"dispersión del tablero en la base: {resultado['dispersion_mm']:.3f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
