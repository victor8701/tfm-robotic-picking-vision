#!/usr/bin/env python3
"""
Sistema Integrado de Detección de Ropa y Esquinas de Caja

Este script coordina dos módulos:
1. detectarRopaYolov8: Detecta prendas de ropa y sus centros
2. DeteccionRopa: Detecta esquinas de la caja y dibuja los centros de las prendas

Autor: Sistema de detección para robótica
Fecha: 2025-12-06
"""

import os
import sys

# ============================================================================
# CONFIGURACIÓN CENTRALIZADA - MODIFICAR AQUÍ PARA AJUSTAR EL SISTEMA
# ============================================================================

# --- VISUALIZACIÓN ---
MOSTRAR_VENTANA_YOLO = True  # True: Muestra ventana con detecciones YOLO
                             # False: No muestra ventana (más rápido)

MOSTRAR_VENTANA_ESQUINAS = True  # True: Muestra ventana con esquinas detectadas
                                  # False: No muestra ventana

# --- GUARDADO DE ARCHIVOS ---
GUARDAR_IMAGENES_YOLO = False  # True: Guarda imágenes en runs/detect/predictX/
                              # False: No guarda imágenes

GUARDAR_REPORTE_COMPLETO = False  # True: Guarda reporte unificado en resultados_deteccion/
                                 # False: No guarda reporte

# --- DETECCIÓN DE PRENDAS (YOLO) ---
CONFIANZA_MINIMA = 0.5  # Umbral de confianza minima (0.0 - 1.0)
                        # Valores más altos = menos detecciones pero más precisas
                        # Valores más bajos = más detecciones pero con más errores
                        # Recomendado: 0.5 - 0.75

IOU_THRESHOLD = 0.3  # Umbral de IoU para eliminar duplicados (0.0 - 1.0)
                     # Valores más bajos = más estricto (elimina más duplicados)
                     # Valores más altos = más permisivo (permite más solapamiento)
                     # Recomendado: 0.3

# --- DETECCIÓN DE ESQUINAS ---
MARGEN_EXCLUSION_PRENDAS = 20  # Margen en píxeles alrededor de cada prenda
                               # para excluir de la detección de esquinas
                               # Valores más altos = excluye más área (menos esquinas falsas)
                               # Valores más bajos = excluye menos área (más esquinas)
                               # Recomendado: 15 - 30

# --- RUTAS ---
CARPETA_IMAGENES = "02Dic"  # Subcarpeta dentro de images/ donde están las imágenes
                            # Cambiar según tu estructura de carpetas

# ============================================================================
# FIN DE CONFIGURACIÓN
# ============================================================================

# Importar los módulos de detección
import json
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


def sistema_completo(nombre_imagen):
    """
    Ejecuta el pipeline completo para UNA imagen.

    Args:
        nombre_imagen: Nombre de la imagen (sin extensión)
    Retorna True si se procesó correctamente, False si no se encontró la imagen.
    """
    ruta_imagen = _resolver_ruta(nombre_imagen)
    if ruta_imagen is None:
        return False
    
    print(f"\n📷 Procesando imagen: {nombre_imagen}.jpg")
    print(f"   Ruta: {ruta_imagen}")
    
    prendas_detectadas = []
    # (Detección de prendas desactivada temporalmente para enfocar en calibrar las esquinas)
    
    # =========================================================================
    # PASO 2: Detectar esquinas
    # =========================================================================
    print("\n" + "="*60)
    print("PASO 2: DETECCIÓN DE ESQUINAS Y VISUALIZACIÓN")
    print("="*60)
    
    print("\n🔍 Detectando esquinas de la caja...")
    
    # Cargar parámetros configurados si existen
    params = None
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_esquinas.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                params = json.load(f)
            print("⚙️  Parámetros cargados desde config_esquinas.json")
        except Exception as e:
            print(f"⚠️  No se pudo cargar config_esquinas.json: {e}")
    else:
        print("ℹ️  Usando parámetros por defecto (no se encontró config_esquinas.json)")
    
    imagen_resultado = charge_image(
        ruta_imagen=ruta_imagen,
        prendas_detectadas=prendas_detectadas,
        mostrar_ventana=MOSTRAR_VENTANA_ESQUINAS,
        guardar_reporte=GUARDAR_REPORTE_COMPLETO,
        margen_exclusion=MARGEN_EXCLUSION_PRENDAS,
        params=params,
    )
    
    # =========================================================================
    # RESUMEN FINAL
    # =========================================================================
    print("\n" + "="*60)
    print("✅ PROCESO COMPLETADO")
    print("="*60)
    print(f"📊 Prendas detectadas: {len(prendas_detectadas) if prendas_detectadas else 0}")
    print(f"👁️  Visualización: Imagen con esquinas (rojos) y centros de prendas (verdes)")
    print("="*60)
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("SISTEMA INTEGRADO DE DETECCIÓN")
    print("=" * 60)
    print("  Escribe el nombre de la imagen (sin .jpg) y pulsa Enter.")
    print("  Escribe 'q' o deja vacío para salir.")
    print("=" * 60)

    # Si se pasa argumento por línea de comandos, se procesa primero
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
            print("👋 Saliendo del sistema.")
            break

        sistema_completo(nombre)

