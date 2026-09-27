#!/usr/bin/env python3
"""Lanza búsquedas de "Buscar en X" automáticamente para varios estilos, sin que nadie tenga que
entrar en el panel y darle a un botón -- pensado para correr solo, en el mismo horario programado
que ya usa procesar_cola.py (ver .github/workflows/ingesta_x.yml, que llama a este script justo
antes que a ese).

Reutiliza al máximo lo que ya existe, a propósito: los mismos textos de búsqueda
(textos_busqueda.py, los mismos que usa el formulario "predeterminado" del panel), y el propio
buscar_x.py para buscar (híbrido: cuentas de confianza + descubrimiento abierto, ver
consultar_tavily_hibrido), filtrar y encolar -- este script solo decide qué estilos tocan hoy y
crea la solicitud; toda la lógica de búsqueda de verdad sigue viviendo en un solo sitio.

Uso:
    python lanzar_busquedas_automaticas.py                       # los 7 estilos
    python lanzar_busquedas_automaticas.py --estilos old_money,urbano
    python lanzar_busquedas_automaticas.py --cantidad 12
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import buscar_x as bx  # noqa: E402
from textos_busqueda import CATEGORIAS, calcular_texto_busqueda  # noqa: E402


def crear_solicitud_automatica(estilo: str, cantidad: int) -> str:
    """Mismo formato exacto que crea /buscar-x en app.py (modo "predeterminado", sin ocasión) --
    para que el panel la muestre igual que si Víctor la hubiera lanzado a mano."""
    texto = calcular_texto_busqueda(estilo, "ninguna", "predeterminado", "")
    nuevo_id = f"sol_{int(time.time() * 1000)}"
    solicitud = {
        "estilo": estilo, "ocasion": "ninguna", "modo": "predeterminado",
        "texto_busqueda": texto, "cantidad": cantidad,
        "estado": "pendiente", "pasos": [], "creado_en": bx._ahora(),
    }
    bx.añadir_paso(solicitud, "Solicitud creada automáticamente (sin intervención manual).")

    def _preparar() -> None:
        datos = bx.cargar_solicitudes()
        datos[nuevo_id] = solicitud
        bx._escribir_solicitudes_json(datos)

    bx.guardar_con_reintentos(_preparar, f"lanzar_busquedas_automaticas: crea {nuevo_id} ({estilo})")
    return nuevo_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--estilos", default="", help="Coma-separado (p. ej. old_money,urbano); vacío = los 7")
    parser.add_argument("--cantidad", type=int, default=8)
    args = parser.parse_args()

    estilos_validos = [clave for clave, _ in CATEGORIAS]
    if args.estilos:
        estilos = [e.strip() for e in args.estilos.split(",") if e.strip()]
        desconocidos = [e for e in estilos if e not in estilos_validos]
        if desconocidos:
            print(f"Estilo(s) desconocido(s), se ignoran: {desconocidos}", file=sys.stderr)
        estilos = [e for e in estilos if e in estilos_validos]
    else:
        estilos = estilos_validos

    if not estilos:
        print("Nada que lanzar (lista de estilos vacía tras validar).", file=sys.stderr)
        return 1

    fallos = 0
    for estilo in estilos:
        print(f"\n=== {estilo} ===")
        try:
            solicitud_id = crear_solicitud_automatica(estilo, args.cantidad)
            print(f"  solicitud creada: {solicitud_id}")
        except Exception as exc:  # noqa: BLE001 -- un fallo creando la solicitud no debe parar los demás estilos
            print(f"  fallo creando la solicitud: {exc}", file=sys.stderr)
            fallos += 1
            continue

        # Se procesa en el mismo proceso, llamando directamente a buscar_x.main() -- ya estamos
        # dentro de un job de Actions, así que disparar otro run por la API sería redundante y
        # más lento (esperar a que se programe, arranque una VM nueva, clone el repo otra vez...).
        sys.argv = ["buscar_x.py", "--solicitud-id", solicitud_id]
        try:
            if bx.main() != 0:
                fallos += 1
        except Exception as exc:  # noqa: BLE001 -- idem, un estilo no debe tirar abajo los demás
            print(f"  fallo procesando {solicitud_id}: {exc}", file=sys.stderr)
            fallos += 1

    print(f"\n{len(estilos) - fallos}/{len(estilos)} estilo(s) completados sin error.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
