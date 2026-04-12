#!/usr/bin/env python3
"""
Pipeline principal — Detección de Esquinas + Detección de Bolsas de Plástico

Módulos activos:
  - deteccion_esquinas.py  → esquinas de la caja de cartón (sin cambios)
  - deteccion_bolsas_cv.py → bolsas de plástico con prendas (CV clásico)

Autor: TFM Robotic Picking Vision
"""

import os
import sys
import json
import cv2
import numpy as np

# ============================================================================
# CONFIGURACIÓN – modificar aquí para ajustar el sistema
# ============================================================================

MOSTRAR_VENTANA    = True    # True: muestra ventana OpenCV con el resultado
GUARDAR_REPORTE    = False   # True: guarda reporte .txt en resultados_deteccion/
CARPETA_IMAGENES   = "02Dic" # Subcarpeta dentro de images/  (vacío → raíz de images/)

# ============================================================================

from deteccion_esquinas   import charge_image, obtener_mascara_roi_solida
from deteccion_bolsas_cv  import detectar_bolsas_cv


def _resolver_ruta(nombre_imagen):
    """Devuelve la ruta absoluta de la imagen o None si no existe."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Buscar con subcarpeta configurada
    if CARPETA_IMAGENES:
        ruta = os.path.abspath(
            os.path.join(script_dir, "..", "images", CARPETA_IMAGENES, f"{nombre_imagen}.jpg")
        )
        if os.path.exists(ruta):
            return ruta

    # Buscar en la raíz de images/
    ruta = os.path.abspath(
        os.path.join(script_dir, "..", "images", f"{nombre_imagen}.jpg")
    )
    if os.path.exists(ruta):
        return ruta

    print(f"❌ ERROR: No existe la imagen '{nombre_imagen}' "
          f"en images/{CARPETA_IMAGENES}/ ni en images/")
    return None


def _cargar_config(nombre_fichero):
    """Carga un JSON de configuración si existe, o retorna None."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), nombre_fichero)
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                datos = json.load(f)
            print(f"⚙️  Parámetros cargados desde {nombre_fichero}")
            return datos
        except Exception as e:
            print(f"⚠️  No se pudo cargar {nombre_fichero}: {e}")
    else:
        print(f"ℹ️  No hay {nombre_fichero}, usando valores por defecto")
    return None


def _combinar_resultados(img_esquinas, bolsas):
    """
    Dibuja las bboxes y centros de las bolsas sobre la imagen que ya tiene
    las esquinas de la caja pintadas.
    """
    output = img_esquinas.copy()
    for b in bolsas:
        # Bbox de bolsa (azul oscuro)
        cv2.rectangle(output, (b["x1"], b["y1"]), (b["x2"], b["y2"]), (255, 80, 0), 2)
        # Centro (verde brillante)
        cv2.circle(output, (b["cx"], b["cy"]), 10, (0, 255, 0), -1)
        # Etiqueta
        cv2.putText(output, f"Bolsa {b['id']}", (b["x1"], b["y1"] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 220, 0), 2, cv2.LINE_AA)
    return output


def procesar_imagen(nombre_imagen):
    """
    Ejecuta el pipeline completo para una imagen:
      1. Detección de esquinas (deteccion_esquinas.py)
      2. Detección de bolsas   (deteccion_bolsas_cv.py)
      3. Visualización combinada

    Args:
        nombre_imagen: nombre del fichero sin extensión
    Returns:
        True si se procesó correctamente, False si la imagen no existe.
    """
    ruta_imagen = _resolver_ruta(nombre_imagen)
    if ruta_imagen is None:
        return False

    print(f"\n{'='*60}")
    print(f"📷 Procesando: {nombre_imagen}.jpg")
    print(f"   Ruta: {ruta_imagen}")
    print(f"{'='*60}")

    # ── 1. Parámetros ─────────────────────────────────────────────────────────
    params_esquinas = _cargar_config("config_esquinas.json")
    params_bolsas   = _cargar_config("config_bolsas.json")

    # ── 2. Detección de esquinas de la caja ───────────────────────────────────
    print("\n[1/2] Detectando esquinas de la caja...")
    img_esquinas, esquinas, _ = charge_image(
        ruta_imagen=ruta_imagen,
        prendas_detectadas=None,
        mostrar_ventana=False,      # la ventana la abrimos abajo combinada
        guardar_reporte=GUARDAR_REPORTE,
        params=params_esquinas,
    )

    # ── 3. Detección de bolsas ────────────────────────────────────────────────
    print("\n[2/2] Detectando bolsas de plástico...")
    
    # Obtener máscara de la caja para restringir la búsqueda
    imagen_bgr = cv2.imread(ruta_imagen)
    mask_caja, _ = obtener_mascara_roi_solida(imagen_bgr, params_esquinas)
    
    bolsas, _ = detectar_bolsas_cv(
        image_bgr=imagen_bgr,
        params=params_bolsas,
        mask_caja=mask_caja,
        mostrar_ventana=False,      # la ventana la abrimos abajo combinada
    )

    # ── 4. Combinar resultados ────────────────────────────────────────────────
    imagen_final = _combinar_resultados(img_esquinas, bolsas)

    # ── 5. Resumen ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"✅ COMPLETADO")
    print(f"   Esquinas detectadas : {len(esquinas)}")
    print(f"   Bolsas detectadas   : {len(bolsas)}")
    print(f"{'='*60}")

    # ── 6. Mostrar ventana combinada ──────────────────────────────────────────
    if MOSTRAR_VENTANA:
        max_h = 800
        h, w  = imagen_final.shape[:2]
        if h > max_h:
            scale    = max_h / h
            new_size = (int(w * scale), max_h)
            img_show = cv2.resize(imagen_final, new_size)
        else:
            img_show = imagen_final

        cv2.namedWindow("Esquinas + Bolsas", cv2.WINDOW_AUTOSIZE)
        cv2.imshow("Esquinas + Bolsas", img_show)
        print("\nPulsa cualquier tecla sobre la ventana para continuar...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return True


# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("DETECCIÓN DE ESQUINAS + BOLSAS DE PLÁSTICO")
    print("=" * 60)
    print("  Escribe el nombre de la imagen (sin .jpg) y pulsa Enter.")
    print("  Escribe 'q' o deja vacío para salir.")
    print(f"  Carpeta: images/{CARPETA_IMAGENES}/")
    print("=" * 60)

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
