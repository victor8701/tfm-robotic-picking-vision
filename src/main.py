#!/usr/bin/env python3
"""
Deteccion de Esquinas de Caja – Pipeline principal

Carga una imagen, aplica la mascara de color HSV para segmentar la caja,
detecta sus esquinas por interseccion de lineas (HoughLinesP) y muestra
el resultado en ventana OpenCV.

Autor: TFM Robotic Picking Vision
"""

import os
import sys
import json

# ============================================================================
# CONFIGURACION – modificar aqui para ajustar el sistema
# ============================================================================

MOSTRAR_VENTANA    = True   # True: muestra ventana OpenCV con el resultado
GUARDAR_REPORTE    = False  # True: guarda reporte .txt en resultados_deteccion/
CARPETA_IMAGENES   = "02Dic"  # Subcarpeta dentro de images/

# ============================================================================

from deteccion_esquinas import charge_image


def _resolver_ruta(nombre_imagen):
    """Devuelve la ruta absoluta de la imagen o None si no existe."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    carpeta = os.path.abspath(os.path.join(script_dir, "..", "images", CARPETA_IMAGENES))
    ruta = os.path.join(carpeta, f"{nombre_imagen}.jpg")
    if not os.path.exists(ruta):
        print(f"❌ ERROR: No existe la imagen {ruta}")
        return None
    return ruta


def procesar_imagen(nombre_imagen):
    """
    Ejecuta el pipeline completo de deteccion de esquinas para una imagen.

    Args:
        nombre_imagen: nombre del fichero sin extension
    Returns:
        True si se proceso correctamente, False si no se encontro la imagen.
    """
    ruta_imagen = _resolver_ruta(nombre_imagen)
    if ruta_imagen is None:
        return False

    print(f"\n📷 Procesando: {nombre_imagen}.jpg")
    print(f"   Ruta: {ruta_imagen}")

    # ── Cargar parametros desde config_esquinas.json si existe ────────────────
    params = None
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_esquinas.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                params = json.load(f)
            print("⚙️  Parametros cargados desde config_esquinas.json")
        except Exception as e:
            print(f"⚠️  No se pudo cargar config_esquinas.json: {e}")
    else:
        print("ℹ️  Usando parametros por defecto (no hay config_esquinas.json)")

    # ── Deteccion de esquinas ─────────────────────────────────────────────────
    _, esquinas, _ = charge_image(
        ruta_imagen=ruta_imagen,
        prendas_detectadas=None,
        mostrar_ventana=MOSTRAR_VENTANA,
        guardar_reporte=GUARDAR_REPORTE,
        params=params,
    )

    print(f"\n{'='*60}")
    print(f"✅ COMPLETADO – {len(esquinas)} esquina(s) detectada(s)")
    print(f"{'='*60}")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("DETECCION DE ESQUINAS DE CAJA")
    print("=" * 60)
    print("  Escribe el nombre de la imagen (sin .jpg) y pulsa Enter.")
    print("  Escribe 'q' o deja vacio para salir.")
    print("=" * 60)

    # Si se pasa argumento por linea de comandos, procesarlo primero
    primera = sys.argv[1] if len(sys.argv) > 1 else None

    while True:
        if primera is not None:
            nombre = primera
            primera = None
        else:
            print("\n📂 Imagen (o 'q' para salir): ", end="", flush=True)
            try:
                nombre = input().strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSaliendo...")
                break

        if nombre.lower() in ("", "q", "quit", "exit", "salir"):
            print("👋 Saliendo.")
            break

        procesar_imagen(nombre)
