import cv2
import sys
import os
import json
import numpy as np
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


# ── Panel de información de parámetros ───────────────────────────────────────
# Lista ordenada: (nombre_trackbar, etiqueta_legible, unidad)
PARAM_INFO = [
    ("H Min",        "H Min  (tono min TSV)",       ""),
    ("S Min",        "S Min  (saturo min)",          ""),
    ("V Min",        "V Min  (valor min)",           ""),
    ("H Max",        "H Max  (tono max)",            ""),
    ("S Max",        "S Max  (saturo max)",          ""),
    ("V Max",        "V Max  (valor max)",           ""),
    ("HoughThresh",  "HoughThresh  (votos Hough)",   ""),
    ("MinLineLen",   "MinLineLen   (min seg, px)",   "px"),
    ("MaxLineGap",   "MaxLineGap   (max hueco, px)", "px"),
    ("NTopLines",    "NTopLines    (N lineas top)",  ""),
    ("AngleTol",     "AngleTol     (tol paralelas)", "°"),
    ("ClusterDist",  "ClusterDist  (agrupa esqs)",   "px"),
    ("CornerMargin", "CornerMargin (margen img)",    "px"),
    ("MaxCorners",   "MaxCorners   (esqs max)",      ""),
]


def _render_info_panel(current_params, saved=False):
    """
    Crea una imagen BGR con los nombres y valores de todos los parámetros.
    Así los parámetros son siempre visibles aunque Qt no cargue fuentes.
    """
    row_h   = 28
    padding = 12
    width   = 560
    n_rows  = len(PARAM_INFO) + 4          # +4 para cabecera, separador, ayuda, estado
    height  = n_rows * row_h + padding * 2

    panel = np.zeros((height, width, 3), dtype=np.uint8)
    panel[:] = (30, 30, 30)                # fondo gris oscuro

    font    = cv2.FONT_HERSHEY_SIMPLEX
    y       = padding + row_h

    # Cabecera
    cv2.putText(panel, "=== PARAMETROS ACTUALES ===", (10, y),
                font, 0.55, (0, 200, 255), 1, cv2.LINE_AA)
    y += row_h

    cv2.line(panel, (10, y - 8), (width - 10, y - 8), (80, 80, 80), 1)

    tb_map = {
        "H Min":        current_params.get("hsv_lower_h", 0),
        "S Min":        current_params.get("hsv_lower_s", 0),
        "V Min":        current_params.get("hsv_lower_v", 0),
        "H Max":        current_params.get("hsv_upper_h", 0),
        "S Max":        current_params.get("hsv_upper_s", 0),
        "V Max":        current_params.get("hsv_upper_v", 0),
        "HoughThresh":  current_params.get("hough_threshold", 0),
        "MinLineLen":   current_params.get("hough_min_line", 0),
        "MaxLineGap":   current_params.get("hough_max_gap", 0),
        "NTopLines":    current_params.get("n_top_lines", 0),
        "AngleTol":     current_params.get("angle_tol", 0),
        "ClusterDist":  current_params.get("cluster_dist", 0),
        "CornerMargin": current_params.get("corner_margin", 0),
        "MaxCorners":   current_params.get("max_corners", 4),
    }

    for tb_name, label, unit in PARAM_INFO:
        val   = tb_map.get(tb_name, 0)
        color = (200, 230, 200)
        text  = f"{label}: {val}{unit}"
        cv2.putText(panel, text, (14, y), font, 0.46, color, 1, cv2.LINE_AA)
        y += row_h

    y += 4
    cv2.line(panel, (10, y - 8), (width - 10, y - 8), (80, 80, 80), 1)

    # Ayuda teclas
    cv2.putText(panel, "  's' guardar   |   'q'/ESC salir", (14, y + 4),
                font, 0.44, (160, 160, 160), 1, cv2.LINE_AA)
    y += row_h

    # Estado guardado
    if saved:
        cv2.putText(panel, "  ✓ GUARDADO en config_esquinas.json", (14, y),
                    font, 0.46, (0, 255, 120), 1, cv2.LINE_AA)

    return panel


def _cargar_imagen(image_arg):
    """Resuelve el argumento de imagen a una imagen BGR cargada, o None si falla."""
    if os.path.isfile(image_arg):
        path = image_arg
    else:
        path = os.path.join(BASE_PATH, image_arg + ".jpg")
        if not os.path.isfile(path):
            path = f"images/{image_arg}.jpg"
            if not os.path.isfile(path):
                print(f"\n❌ No se encontró la imagen: {image_arg}")
                return None, None
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        print(f"\n❌ No se pudo cargar: {path}")
        return None, None
    print(f"✅ Imagen cargada: {path}")
    return img, path


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 ajuste_parametros.py <nombre_imagen_sin_extension_o_ruta>")
        sys.exit(1)

    image_bgr, _ = _cargar_imagen(sys.argv[1])
    if image_bgr is None:
        sys.exit(1)

    # ── Cargar parámetros previos o usar defaults ─────────────────────────────
    params = cargar_parametros_guardados()
    if not params:
        params = dict(DEFAULT_PARAMS)

    # ── Ventana de controles (trackbars) ─────────────────────────────────────
    cv2.namedWindow("Controles", cv2.WINDOW_NORMAL)

    # Máscara – color HSV
    cv2.createTrackbar("H Min",        "Controles", params.get("hsv_lower_h", 10),  179, nothing)
    cv2.createTrackbar("S Min",        "Controles", params.get("hsv_lower_s", 65),  255, nothing)
    cv2.createTrackbar("V Min",        "Controles", params.get("hsv_lower_v", 60),  255, nothing)
    cv2.createTrackbar("H Max",        "Controles", params.get("hsv_upper_h", 30),  179, nothing)
    cv2.createTrackbar("S Max",        "Controles", params.get("hsv_upper_s", 255), 255, nothing)
    cv2.createTrackbar("V Max",        "Controles", params.get("hsv_upper_v", 255), 255, nothing)

    # HoughLinesP
    cv2.createTrackbar("HoughThresh",  "Controles", params.get("hough_threshold", 40),   500, nothing)
    cv2.createTrackbar("MinLineLen",   "Controles", params.get("hough_min_line",   60),  1000, nothing)
    cv2.createTrackbar("MaxLineGap",   "Controles", params.get("hough_max_gap",    20),   200, nothing)

    # Selección y agrupación
    cv2.createTrackbar("NTopLines",    "Controles", params.get("n_top_lines",    8),  30, nothing)
    cv2.createTrackbar("AngleTol",     "Controles", params.get("angle_tol",     20),  89, nothing)
    cv2.createTrackbar("ClusterDist",  "Controles", params.get("cluster_dist",  80), 300, nothing)
    cv2.createTrackbar("CornerMargin", "Controles", params.get("corner_margin", 120), 400, nothing)

    # Nuevo: maximo de esquinas
    cv2.createTrackbar("MaxCorners",   "Controles", params.get("max_corners",    4),  20, nothing)

    # Ventana del panel informativo
    cv2.namedWindow("Info Parametros", cv2.WINDOW_NORMAL)

    print("=" * 60)
    print("Herramienta Interactiva: Ajuste de Parametros - Metodo Lineas")
    print("=" * 60)
    print("  Ajusta los sliders en la ventana 'Controles'.")
    print("  Los valores actuales se muestran en 'Info Parametros'.")
    print("  'i'     -> Cambiar imagen (escribe el nombre en terminal)")
    print("  's'     -> Guardar parametros en config_esquinas.json")
    print("  'q'/ESC -> Salir")
    print("=" * 60)

    just_saved = False

    while True:
        # ── Leer trackbars ────────────────────────────────────────────────────
        h_min = cv2.getTrackbarPos("H Min",        "Controles")
        s_min = cv2.getTrackbarPos("S Min",        "Controles")
        v_min = cv2.getTrackbarPos("V Min",        "Controles")
        h_max = cv2.getTrackbarPos("H Max",        "Controles")
        s_max = cv2.getTrackbarPos("S Max",        "Controles")
        v_max = cv2.getTrackbarPos("V Max",        "Controles")

        hough_thresh = max(5,  cv2.getTrackbarPos("HoughThresh",  "Controles"))
        min_line     = max(5,  cv2.getTrackbarPos("MinLineLen",   "Controles"))
        max_gap      = max(1,  cv2.getTrackbarPos("MaxLineGap",   "Controles"))

        n_top        = max(2,  cv2.getTrackbarPos("NTopLines",    "Controles"))
        angle_tol    = max(1,  cv2.getTrackbarPos("AngleTol",     "Controles"))
        cluster_dist = max(1,  cv2.getTrackbarPos("ClusterDist",  "Controles"))
        corner_marg  = max(0,  cv2.getTrackbarPos("CornerMargin", "Controles"))
        max_corners  = max(3,  cv2.getTrackbarPos("MaxCorners",   "Controles"))

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
            "max_corners":     max_corners,
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

        # ── Mostrar resultado ─────────────────────────────────────────────────
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

        # ── Panel de información (siempre visible con texto claro) ────────────
        info_panel = _render_info_panel(current_params, saved=just_saved)
        cv2.imshow("Info Parametros", info_panel)

        key = cv2.waitKey(100) & 0xFF
        just_saved = False

        if key == ord("q") or key == 27:
            break
        elif key == ord("i"):
            # Cambiar imagen desde terminal
            print("\n📂 Nombre de la nueva imagen (sin .jpg): ", end="", flush=True)
            try:
                nuevo = input().strip()
            except (EOFError, KeyboardInterrupt):
                nuevo = ""
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
