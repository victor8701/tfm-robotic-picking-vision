import cv2
import sys
import os
import json
from deteccion_esquinas import (
    obtener_mascara_roi_solida,
    detectar_esquinas_por_lineas,
    DEFAULT_PARAMS,
)

CONFIG_FILE = "config_esquinas.json"
BASE_PATH   = "../images/02Dic/"


def nothing(x):
    pass


def cargar_parametros_guardados():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 ajuste_parametros.py <nombre_imagen_sin_extension_o_ruta>")
        sys.exit(1)

    image_arg = sys.argv[1]

    if os.path.isfile(image_arg):
        path = image_arg
    else:
        path = os.path.join(BASE_PATH, image_arg + ".jpg")
        if not os.path.isfile(path):
            path = f"images/{image_arg}.jpg"
            if not os.path.isfile(path):
                print(f"Error al cargar la imagen: {path}")
                sys.exit(1)

    image_bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if image_bgr is None:
        print("No se pudo cargar la imagen.")
        sys.exit(1)

    # ── Cargar parámetros previos o usar defaults ─────────────────────────────
    params = cargar_parametros_guardados()
    if not params:
        params = dict(DEFAULT_PARAMS)

    # ── Ventana de controles ──────────────────────────────────────────────────
    cv2.namedWindow("Controles", cv2.WINDOW_NORMAL)

    # Máscara – color HSV
    cv2.createTrackbar("H Min",        "Controles", params.get("hsv_lower_h", 10),  179, nothing)
    cv2.createTrackbar("S Min",        "Controles", params.get("hsv_lower_s", 65),  255, nothing)
    cv2.createTrackbar("V Min",        "Controles", params.get("hsv_lower_v", 60),  255, nothing)
    cv2.createTrackbar("H Max",        "Controles", params.get("hsv_upper_h", 30),  179, nothing)
    cv2.createTrackbar("S Max",        "Controles", params.get("hsv_upper_s", 255), 255, nothing)
    cv2.createTrackbar("V Max",        "Controles", params.get("hsv_upper_v", 255), 255, nothing)

    # HoughLinesP
    cv2.createTrackbar("HoughThresh",  "Controles", params.get("hough_threshold", 80),   500, nothing)
    cv2.createTrackbar("MinLineLen",   "Controles", params.get("hough_min_line",  150),  1000, nothing)
    cv2.createTrackbar("MaxLineGap",   "Controles", params.get("hough_max_gap",    15),   200, nothing)

    # Selección y agrupación
    cv2.createTrackbar("NTopLines",    "Controles", params.get("n_top_lines",    8),  30, nothing)
    cv2.createTrackbar("AngleTol",     "Controles", params.get("angle_tol",     20),  89, nothing)
    cv2.createTrackbar("ClusterDist",  "Controles", params.get("cluster_dist",  80), 300, nothing)
    cv2.createTrackbar("CornerMargin", "Controles", params.get("corner_margin", 120), 400, nothing)

    print("=" * 60)
    print("Herramienta Interactiva: Ajuste de Parámetros – Método Líneas")
    print("=" * 60)
    print("  Ajusta los sliders en la ventana 'Controles'.")
    print("  's'   → Guardar parámetros en config_esquinas.json")
    print("  'q'/ESC → Salir")
    print("=" * 60)

    while True:
        # ── Leer trackbars ────────────────────────────────────────────────────
        h_min = cv2.getTrackbarPos("H Min",        "Controles")
        s_min = cv2.getTrackbarPos("S Min",        "Controles")
        v_min = cv2.getTrackbarPos("V Min",        "Controles")
        h_max = cv2.getTrackbarPos("H Max",        "Controles")
        s_max = cv2.getTrackbarPos("S Max",        "Controles")
        v_max = cv2.getTrackbarPos("V Max",        "Controles")

        hough_thresh = max(10, cv2.getTrackbarPos("HoughThresh",  "Controles"))
        min_line     = max(10, cv2.getTrackbarPos("MinLineLen",   "Controles"))
        max_gap      = max(1,  cv2.getTrackbarPos("MaxLineGap",   "Controles"))

        n_top        = max(2,  cv2.getTrackbarPos("NTopLines",    "Controles"))
        angle_tol    = max(1,  cv2.getTrackbarPos("AngleTol",     "Controles"))
        cluster_dist = max(1,  cv2.getTrackbarPos("ClusterDist",  "Controles"))
        corner_marg  = max(0,  cv2.getTrackbarPos("CornerMargin", "Controles"))

        current_params = {
            "hsv_lower_h":    h_min,
            "hsv_lower_s":    s_min,
            "hsv_lower_v":    v_min,
            "hsv_upper_h":    h_max,
            "hsv_upper_s":    s_max,
            "hsv_upper_v":    v_max,
            "hough_threshold": hough_thresh,
            "hough_min_line":  min_line,
            "hough_max_gap":   max_gap,
            "n_top_lines":     n_top,
            "angle_tol":       angle_tol,
            "cluster_dist":    cluster_dist,
            "corner_margin":   corner_marg,
        }

        # ── Pipeline ──────────────────────────────────────────────────────────
        mask_solida, _ = obtener_mascara_roi_solida(image_bgr, current_params)

        # Suprimir prints internos
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            image_result, _ = detectar_esquinas_por_lineas(
                mask_solida, image_bgr.copy(), current_params
            )
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout

        # ── Mostrar ───────────────────────────────────────────────────────────
        max_h = 600
        h_img, w_img = image_result.shape[:2]
        if h_img > max_h:
            scale = max_h / h_img
            new_size = (int(w_img * scale), max_h)
            image_result_show = cv2.resize(image_result, new_size)
            mask_show = cv2.resize(mask_solida, new_size)
        else:
            image_result_show = image_result
            mask_show = mask_solida

        mask_bgr = cv2.cvtColor(mask_show, cv2.COLOR_GRAY2BGR)

        cv2.imshow("Deteccion Esquinas (lineas)", image_result_show)
        cv2.imshow("Mascara Solida Caja",         mask_bgr)

        key = cv2.waitKey(100) & 0xFF
        if key == ord("q") or key == 27:
            break
        elif key == ord("s"):
            with open(CONFIG_FILE, "w") as f:
                json.dump(current_params, f, indent=4)
            print(f"\n✅ Parámetros guardados en {CONFIG_FILE}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
