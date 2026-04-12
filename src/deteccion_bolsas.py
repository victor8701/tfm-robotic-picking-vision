import cv2
import os
import json
import numpy as np

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_bolsas.json")

DEFAULT_PARAMS = {
    "blur_kernel":        3,
    "canny_low":         30,
    "canny_high":        90,
    "morph_close_kernel": 15,
    "morph_iterations":   3,
    "area_min":        5000,
    "area_max":      500000,
    "solidez_min":       50,
}


def _cargar_params():
    """Carga config_bolsas.json si existe, si no usa defaults."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_PARAMS)


def detectar_bolsas_cv(ruta_imagen=None, image_bgr=None, params=None, mask_caja=None, mostrar_ventana=False):
    """
    Detecta bolsas de plástico en una imagen usando CV clásico.

    Pipeline:
        1. Grayscale + GaussianBlur  → reduce reflejos especulares del plástico
        2. Canny                     → bordes nítidos del film transparente
        3. MORPH_CLOSE               → cierra los bordes discontinuos del film
        3b. Aplicar mask_caja        → filtra solo la zona interior de la caja de cartón
        4. findContours              → busca contornos cerrados
        5. Filtrar por área          → elimina ruido y el fondo completo
        6. Filtrar por solidez       → bolsas son aproximadamente convexas
        7. Calcular bbox + centro    → salida para el robot

    Args:
        ruta_imagen    : ruta absoluta o relativa a la imagen (opcional si se pasa image_bgr)
        image_bgr      : imagen opencv (opcional si se usa ruta_imagen)
        params         : diccionario de parámetros (si None, carga config_bolsas.json)
        mask_caja      : máscara binaria de la caja (devuelta por deteccion_esquinas)
        mostrar_ventana: True para abrir ventana OpenCV con resultado

    Returns:
        bolsas : lista de dicts con claves:
                 'cx', 'cy', 'x1', 'y1', 'x2', 'y2', 'area', 'solidez'
        imagen_resultado : imagen BGR anotada (bboxes azules, centros verdes)
    """
    if params is None:
        params = _cargar_params()

    # ── Parámetros ────────────────────────────────────────────────────────────
    blur_k   = max(1, params.get("blur_kernel",        3))
    if blur_k % 2 == 0:
        blur_k += 1   # GaussianBlur requiere kernel impar
    canny_lo = params.get("canny_low",              30)
    canny_hi = params.get("canny_high",             90)
    morph_k  = max(1, params.get("morph_close_kernel", 15))
    morph_it = max(1, params.get("morph_iterations",    3))
    area_min = params.get("area_min",            5000)
    area_max = params.get("area_max",          500000)
    # solidez_min: si viene como entero 0-100 (de ajuste_bolsas.py) lo normaliza a 0-1
    solidez_raw = params.get("solidez_min", 50)
    solidez_min = solidez_raw / 100.0 if solidez_raw > 1.0 else solidez_raw

    # ── Cargar imagen ─────────────────────────────────────────────────────────
    if image_bgr is not None:
        imagen = image_bgr.copy()
    elif ruta_imagen is not None:
        imagen = cv2.imread(ruta_imagen, cv2.IMREAD_COLOR)
    else:
        print("❌ ERROR: Debes proporcionar ruta_imagen o image_bgr")
        return [], None

    if imagen is None:
        print(f"❌ ERROR: No se pudo cargar la imagen")
        return [], None

    # ── Paso 1: Grayscale + Blur ──────────────────────────────────────────────
    gray    = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)

    # ── Paso 2: Canny → bordes del plástico ──────────────────────────────────
    edges = cv2.Canny(blurred, canny_lo, canny_hi)

    # ── Paso 3: MORPH_CLOSE → cierra bordes discontinuos del film ────────────
    kernel     = np.ones((morph_k, morph_k), np.uint8)
    mask_close = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=morph_it)

    # ── Paso 3b: Aplicar mask_caja (si fue provista) ─────────────────────────
    if mask_caja is not None:
        # Erosión de la máscara de la caja para evitar que los bordes del cartón
        # se detecten como bordes de bolsa.
        k_erosion = np.ones((25, 25), np.uint8)
        mask_caja_erodida = cv2.erode(mask_caja, k_erosion, iterations=1)
        mask_close = cv2.bitwise_and(mask_close, mask_caja_erodida)

    # ── Paso 4 & 5: Contornos + filtros ──────────────────────────────────────
    contours, _ = cv2.findContours(mask_close, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    imagen_resultado = imagen.copy()
    bolsas = []
    idx = 1

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < area_min or area > area_max:
            continue

        # Paso 6: Solidez
        hull      = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0:
            continue
        solidez = area / hull_area
        if solidez < solidez_min:
            continue

        # Paso 7: Bbox y centro
        x, y, w, h = cv2.boundingRect(cnt)
        cx = x + w // 2
        cy = y + h // 2

        bolsas.append({
            "id":     idx,
            "cx":     cx,
            "cy":     cy,
            "x1":     x,
            "y1":     y,
            "x2":     x + w,
            "y2":     y + h,
            "area":   int(area),
            "solidez": round(solidez, 3),
        })

        # ── Visualización ─────────────────────────────────────────────────────
        # Contorno (cian)
        cv2.drawContours(imagen_resultado, [cnt], -1, (255, 200, 0), 2)
        # Bbox (azul)
        cv2.rectangle(imagen_resultado, (x, y), (x + w, y + h), (255, 80, 0), 2)
        # Centro (verde)
        cv2.circle(imagen_resultado, (cx, cy), 10, (0, 255, 0), -1)
        # Etiqueta
        label = f"Bolsa {idx}  ({int(area / 1000)}k px  s={solidez:.2f})"
        cv2.putText(imagen_resultado, label, (x, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 220, 0), 2, cv2.LINE_AA)
        idx += 1

    # Contador global en esquina
    cv2.putText(imagen_resultado, f"Bolsas: {len(bolsas)}", (12, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 180), 2, cv2.LINE_AA)

    # ── Log por consola ───────────────────────────────────────────────────────
    print(f"\n--- BOLSAS DETECTADAS ({len(bolsas)}) ---")
    for b in bolsas:
        print(f"  Bolsa {b['id']}: centro=({b['cx']}, {b['cy']})  "
              f"bbox=[{b['x1']},{b['y1']},{b['x2']},{b['y2']}]  "
              f"area={b['area']}px  solidez={b['solidez']}")
    if not bolsas:
        print("  (ninguna detectada con los parámetros actuales)")
    print("-" * 40)

    # ── Mostrar ventana (opcional) ────────────────────────────────────────────
    if mostrar_ventana:
        max_h = 800
        h_img, w_img = imagen_resultado.shape[:2]
        if h_img > max_h:
            scale    = max_h / h_img
            new_size = (int(w_img * scale), max_h)
            img_show = cv2.resize(imagen_resultado, new_size)
        else:
            img_show = imagen_resultado

        cv2.namedWindow("Deteccion Bolsas", cv2.WINDOW_AUTOSIZE)
        cv2.imshow("Deteccion Bolsas", img_show)
        print("✅ Pulsa cualquier tecla sobre la ventana para cerrar.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return bolsas, imagen_resultado


# ── Ejecución directa (prueba rápida) ─────────────────────────────────────────
if __name__ == "__main__":
    import sys

    script_dir  = os.path.dirname(os.path.abspath(__file__))
    carpeta_img = os.path.abspath(os.path.join(script_dir, "..", "images"))

    if len(sys.argv) > 1:
        nombre = sys.argv[1]
    else:
        print("Introduce el nombre de la imagen (sin .jpg) o ruta completa:")
        nombre = input().strip()

    # Resolver ruta
    if os.path.isfile(nombre):
        ruta = nombre
    else:
        # Intentar images/<nombre>.jpg o images/02Dic/<nombre>.jpg
        candidatos = [
            os.path.join(carpeta_img, nombre + ".jpg"),
            os.path.join(carpeta_img, "02Dic", nombre + ".jpg"),
        ]
        ruta = next((c for c in candidatos if os.path.isfile(c)), None)
        if ruta is None:
            print(f"❌ No se encontró la imagen: {nombre}")
            sys.exit(1)

    print(f"📷 Procesando: {ruta}")
    detectar_bolsas_cv(ruta, mostrar_ventana=True)
