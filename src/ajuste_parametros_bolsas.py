import cv2
import sys
import os
import json
import numpy as np
from deteccion_esquinas import obtener_mascara_roi_solida

CONFIG_FILE = "config_bolsas.json"
BASE_PATH   = "../images/"

# Parámetros por defecto (espejo de config_bolsas.json)
DEFAULT_PARAMS = {
    "blur_kernel":        3,
    "canny_low":         30,
    "canny_high":        90,
    "morph_close_kernel": 15,
    "morph_iterations":   3,
    "area_min":        5000,
    "area_max":      500000,
    "solidez_min":       50,   # 0-100 (porcentaje * 100)
}

# ── Info panel ────────────────────────────────────────────────────────────────
PARAM_INFO = [
    ("BlurKernel",   "BlurKernel  (suavizado, impar)",   ""),
    ("CannyLow",     "CannyLow    (umbral Canny bajo)",   ""),
    ("CannyHigh",    "CannyHigh   (umbral Canny alto)",   ""),
    ("MorphKernel",  "MorphKernel (tamaño cierre)",       "px"),
    ("MorphIter",    "MorphIter   (iteraciones cierre)",  ""),
    ("AreaMin",      "AreaMin     (area min contorno)",   "px²"),
    ("AreaMax",      "AreaMax     (area max contorno)",   "px²"),
    ("SolidezMin",   "SolidezMin  (solidez min *100)",   ""),
]


def nothing(x):
    pass


def cargar_parametros_guardados():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None


def _render_info_panel(current_params, saved=False):
    """Panel informativo con los valores actuales de los parámetros."""
    row_h   = 28
    padding = 12
    width   = 580
    n_rows  = len(PARAM_INFO) + 4
    height  = n_rows * row_h + padding * 2

    panel = np.zeros((height, width, 3), dtype=np.uint8)
    panel[:] = (30, 30, 30)

    font = cv2.FONT_HERSHEY_SIMPLEX
    y    = padding + row_h

    cv2.putText(panel, "=== PARAMETROS BOLSAS (CV Clasico) ===", (10, y),
                font, 0.55, (0, 220, 180), 1, cv2.LINE_AA)
    y += row_h
    cv2.line(panel, (10, y - 8), (width - 10, y - 8), (80, 80, 80), 1)

    tb_map = {
        "BlurKernel":  current_params.get("blur_kernel", 3),
        "CannyLow":    current_params.get("canny_low",  30),
        "CannyHigh":   current_params.get("canny_high", 90),
        "MorphKernel": current_params.get("morph_close_kernel", 15),
        "MorphIter":   current_params.get("morph_iterations",    3),
        "AreaMin":     current_params.get("area_min",   5000),
        "AreaMax":     current_params.get("area_max", 500000),
        "SolidezMin":  current_params.get("solidez_min",  50),
    }

    for tb_name, label, unit in PARAM_INFO:
        val  = tb_map.get(tb_name, 0)
        text = f"{label}: {val}{unit}"
        cv2.putText(panel, text, (14, y), font, 0.46, (200, 230, 200), 1, cv2.LINE_AA)
        y += row_h

    y += 4
    cv2.line(panel, (10, y - 8), (width - 10, y - 8), (80, 80, 80), 1)
    cv2.putText(panel, "  's' guardar   |   'i' cambiar imagen   |   'q'/ESC salir", (14, y + 4),
                font, 0.44, (160, 160, 160), 1, cv2.LINE_AA)
    y += row_h

    if saved:
        cv2.putText(panel, "  GUARDADO en config_bolsas.json", (14, y),
                    font, 0.46, (0, 255, 120), 1, cv2.LINE_AA)

    return panel


def _cargar_imagen(image_arg):
    """Resuelve el argumento de imagen a una imagen BGR cargada, o None si falla."""
    # Ruta absoluta o relativa directa
    if os.path.isfile(image_arg):
        path = image_arg
    else:
        # Buscar en images/ (sin subcarpeta fija, acepta ruta relativa)
        candidates = [
            os.path.join(BASE_PATH, image_arg + ".jpg"),
            os.path.join(BASE_PATH, "02Dic", image_arg + ".jpg"),
            image_arg + ".jpg",
        ]
        path = None
        for c in candidates:
            if os.path.isfile(c):
                path = c
                break
        if path is None:
            print(f"\n❌ No se encontró la imagen: {image_arg}")
            return None, None

    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        print(f"\n❌ No se pudo cargar: {path}")
        return None, None
    print(f"✅ Imagen cargada: {path}")
    return img, path


def detectar_bolsas_preview(image_bgr, params, mask_caja=None):
    """
    Ejecuta el pipeline de detección de bolsas y devuelve la imagen anotada
    y la máscara binaria de contornos.
    """
    blur_k   = max(1, params.get("blur_kernel", 3))
    # blur_kernel debe ser impar
    if blur_k % 2 == 0:
        blur_k += 1
    canny_lo = params.get("canny_low",   30)
    canny_hi = params.get("canny_high",  90)
    morph_k  = max(1, params.get("morph_close_kernel", 15))
    morph_it = max(1, params.get("morph_iterations",    3))
    area_min = params.get("area_min",   5000)
    area_max = params.get("area_max", 500000)
    # solidez_min se guarda como entero 0-100 (= porcentaje × 100 → dividir entre 100)
    solidez_min = params.get("solidez_min", 50) / 100.0

    # 1. Grayscale + blur suave
    gray    = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)

    # 2. Canny → bordes del plástico
    edges = cv2.Canny(blurred, canny_lo, canny_hi)

    # 3. MORPH_CLOSE → cierra los bordes discontinuos del film
    kernel     = np.ones((morph_k, morph_k), np.uint8)
    mask_close = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=morph_it)
    
    if mask_caja is not None:
        mask_close = cv2.bitwise_and(mask_close, mask_caja)

    # 4. Encontrar contornos
    contours, _ = cv2.findContours(mask_close, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    output   = image_bgr.copy()
    n_bolsas = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < area_min or area > area_max:
            continue

        # Solidez = área / área convex hull (1.0 = perfectamente convexo)
        hull    = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0:
            continue
        solidez = area / hull_area
        if solidez < solidez_min:
            continue

        # Bbox y centro
        x, y, w, h = cv2.boundingRect(cnt)
        cx = x + w // 2
        cy = y + h // 2
        n_bolsas += 1

        # Dibujar contorno (cian) + bbox (azul) + centro (verde) + etiqueta
        cv2.drawContours(output, [cnt], -1, (255, 200, 0), 2)
        cv2.rectangle(output, (x, y), (x + w, y + h), (255, 80, 0), 2)
        cv2.circle(output, (cx, cy), 8, (0, 255, 0), -1)
        cv2.putText(output, f"Bolsa {n_bolsas}  s={solidez:.2f}", (x, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 220, 0), 2, cv2.LINE_AA)

    cv2.putText(output, f"Bolsas detectadas: {n_bolsas}", (12, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 180), 2, cv2.LINE_AA)

    return output, mask_close


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 ajuste_bolsas.py <nombre_imagen_sin_extension_o_ruta>")
        print("     La imagen debe estar en images/ o en images/02Dic/")
        sys.exit(1)

    image_bgr, _ = _cargar_imagen(sys.argv[1])
    if image_bgr is None:
        sys.exit(1)

    # Cargar parámetros previos o usar defaults
    params = cargar_parametros_guardados()
    if not params:
        params = dict(DEFAULT_PARAMS)

    # Cargar parámetros de esquinas para generar la máscara
    params_esquinas = None
    config_esquinas_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_esquinas.json")
    if os.path.exists(config_esquinas_path):
        with open(config_esquinas_path, "r") as f:
            params_esquinas = json.load(f)

    # ── Ventana de controles ──────────────────────────────────────────────────
    cv2.namedWindow("Controles Bolsas", cv2.WINDOW_NORMAL)

    cv2.createTrackbar("BlurKernel",  "Controles Bolsas", params.get("blur_kernel",        3),  21, nothing)
    cv2.createTrackbar("CannyLow",    "Controles Bolsas", params.get("canny_low",          30), 255, nothing)
    cv2.createTrackbar("CannyHigh",   "Controles Bolsas", params.get("canny_high",         90), 255, nothing)
    cv2.createTrackbar("MorphKernel", "Controles Bolsas", params.get("morph_close_kernel", 15),  51, nothing)
    cv2.createTrackbar("MorphIter",   "Controles Bolsas", params.get("morph_iterations",    3),  10, nothing)
    cv2.createTrackbar("AreaMin",     "Controles Bolsas", params.get("area_min",         5000) // 100, 1000, nothing)  # ×100
    cv2.createTrackbar("AreaMax",     "Controles Bolsas", params.get("area_max",       500000) // 1000, 1000, nothing) # ×1000
    cv2.createTrackbar("SolidezMin",  "Controles Bolsas", params.get("solidez_min",       50),  100, nothing)

    cv2.namedWindow("Info Bolsas", cv2.WINDOW_NORMAL)

    print("=" * 60)
    print("Herramienta: Ajuste de Parámetros — Detección de Bolsas")
    print("=" * 60)
    print("  Ajusta los sliders en 'Controles Bolsas'.")
    print("  'i'     -> Cambiar imagen")
    print("  's'     -> Guardar en config_bolsas.json")
    print("  'q'/ESC -> Salir")
    print("=" * 60)

    just_saved = False

    while True:
        # Leer trackbars
        blur_k   = cv2.getTrackbarPos("BlurKernel",  "Controles Bolsas")
        canny_lo = cv2.getTrackbarPos("CannyLow",    "Controles Bolsas")
        canny_hi = cv2.getTrackbarPos("CannyHigh",   "Controles Bolsas")
        morph_k  = cv2.getTrackbarPos("MorphKernel", "Controles Bolsas")
        morph_it = cv2.getTrackbarPos("MorphIter",   "Controles Bolsas")
        area_min_raw = cv2.getTrackbarPos("AreaMin", "Controles Bolsas")
        area_max_raw = cv2.getTrackbarPos("AreaMax", "Controles Bolsas")
        solidez_min  = cv2.getTrackbarPos("SolidezMin", "Controles Bolsas")

        # Escalado de area (slider va de 0-1000 representando ×100 y ×1000)
        area_min = max(100, area_min_raw * 100)
        area_max = max(1000, area_max_raw * 1000)

        current_params = {
            "blur_kernel":        max(1, blur_k),
            "canny_low":          canny_lo,
            "canny_high":         max(canny_lo + 1, canny_hi),
            "morph_close_kernel": max(1, morph_k),
            "morph_iterations":   max(1, morph_it),
            "area_min":           area_min,
            "area_max":           area_max,
            "solidez_min":        solidez_min,
        }

        # Pipeline
        mask_caja = None
        if params_esquinas is not None:
            mask_caja, _ = obtener_mascara_roi_solida(image_bgr, params_esquinas)
            
        result_img, mask = detectar_bolsas_preview(image_bgr, current_params, mask_caja)

        # Mostrar imágenes
        max_h = 600
        h_img, w_img = result_img.shape[:2]
        if h_img > max_h:
            scale    = max_h / h_img
            new_size = (int(w_img * scale), max_h)
            result_show = cv2.resize(result_img, new_size)
            mask_show   = cv2.resize(mask,       new_size)
        else:
            result_show = result_img
            mask_show   = mask

        cv2.imshow("Deteccion Bolsas (CV Clasico)", result_show)
        cv2.imshow("Mascara Canny+CLOSE",           cv2.cvtColor(mask_show, cv2.COLOR_GRAY2BGR))

        # Panel informativo
        info_panel = _render_info_panel(current_params, saved=just_saved)
        cv2.imshow("Info Bolsas", info_panel)

        key = cv2.waitKey(100) & 0xFF
        just_saved = False

        if key == ord("q") or key == 27:
            break
        elif key == ord("i"):
            print("\n📂 Nombre de la nueva imagen (sin .jpg): ", end="", flush=True)
            try:
                nuevo = input().strip()
            except (EOFError, KeyboardInterrupt):
                nuevo = ""
            if nuevo.lower() in ("", "q", "quit", "exit", "salir"):
                break
            if nuevo:
                nueva_img, _ = _cargar_imagen(nuevo)
                if nueva_img is not None:
                    image_bgr = nueva_img
                else:
                    print("  Manteniendo imagen anterior.")
        elif key == ord("s"):
            with open(CONFIG_FILE, "w") as f:
                json.dump(current_params, f, indent=4)
            print(f"\n✅ Parámetros guardados en {CONFIG_FILE}")
            just_saved = True

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
