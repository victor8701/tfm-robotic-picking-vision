import cv2
import sys
import os
import json
from deteccion_esquinas import border_sobel, obtener_mascara_carton_filtrada, detectar_esquinas_caja

CONFIG_FILE = "config_esquinas.json"
BASE_PATH = "../images/02Dic/"

def nothing(x):
    pass

def cargar_parametros_guardados():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 ajuste_parametros.py <nombre_imagen_sin_extension_o_ruta>")
        sys.exit(1)
        
    image_arg = sys.argv[1]
    
    # Intentar cargar
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
    image_gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image_bgr is None:
        print("No se pudo cargar la imagen.")
        sys.exit(1)

    # Crear ventana de controles
    cv2.namedWindow('Controles', cv2.WINDOW_NORMAL)
    
    # Cargar previos o defaults
    params = cargar_parametros_guardados()
    if not params:
        params = {
            "hsv_lower_h": 10, "hsv_lower_s": 65, "hsv_lower_v": 60,
            "hsv_upper_h": 30, "hsv_upper_s": 255, "hsv_upper_v": 255,
            "max_corners": 20, "quality_level": 0.05, "min_distance": 70, "block_size": 3,
            "edge_only": 1, "poly_epsilon": 20, "edge_thickness": 30
        }
    
    # Trackbars
    cv2.createTrackbar('H Min', 'Controles', params['hsv_lower_h'], 179, nothing)
    cv2.createTrackbar('S Min', 'Controles', params['hsv_lower_s'], 255, nothing)
    cv2.createTrackbar('V Min', 'Controles', params['hsv_lower_v'], 255, nothing)
    cv2.createTrackbar('H Max', 'Controles', params['hsv_upper_h'], 179, nothing)
    cv2.createTrackbar('S Max', 'Controles', params['hsv_upper_s'], 255, nothing)
    cv2.createTrackbar('V Max', 'Controles', params['hsv_upper_v'], 255, nothing)
    
    cv2.createTrackbar('maxCorners', 'Controles', params.get('max_corners', 20), 100, nothing)
    cv2.createTrackbar('qualLvlx1000', 'Controles', int(params.get('quality_level', 0.05) * 1000), 1000, nothing)
    cv2.createTrackbar('minDist', 'Controles', params.get('min_distance', 70), 500, nothing)
    cv2.createTrackbar('blockSize', 'Controles', params.get('block_size', 3), 15, nothing)
    cv2.createTrackbar('edgeOnly(0/1)', 'Controles', params.get('edge_only', 1), 1, nothing)
    cv2.createTrackbar('polyEpsilon', 'Controles', params.get('poly_epsilon', 20), 100, nothing)
    cv2.createTrackbar('edgeThick', 'Controles', params.get('edge_thickness', 30), 100, nothing)

    print("="*60)
    print("Herramienta Interactiva: Ajuste de Parámetros")
    print("="*60)
    print("1. Ajusta los parámetros en la ventana 'Controles'.")
    print("2. Presiona 's' para Guardar (Save) a config_esquinas.json")
    print("3. Presiona 'q' o ESC para salir.")
    print("="*60)

    sobel_img = border_sobel(image_gray)

    while True:
        # Leer valores
        h_min = cv2.getTrackbarPos('H Min', 'Controles')
        s_min = cv2.getTrackbarPos('S Min', 'Controles')
        v_min = cv2.getTrackbarPos('V Min', 'Controles')
        h_max = cv2.getTrackbarPos('H Max', 'Controles')
        s_max = cv2.getTrackbarPos('S Max', 'Controles')
        v_max = cv2.getTrackbarPos('V Max', 'Controles')
        
        m_corn = cv2.getTrackbarPos('maxCorners', 'Controles')
        ql_1000 = cv2.getTrackbarPos('qualLvlx1000', 'Controles')
        if ql_1000 == 0: ql_1000 = 1 # Avoid 0
        q_lvl = ql_1000 / 1000.0
        m_dist = cv2.getTrackbarPos('minDist', 'Controles')
        b_size = cv2.getTrackbarPos('blockSize', 'Controles')
        if b_size % 2 == 0: b_size += 1 # must be odd and > 0
        if b_size < 3: b_size = 3
        e_only = cv2.getTrackbarPos('edgeOnly(0/1)', 'Controles')
        p_eps = cv2.getTrackbarPos('polyEpsilon', 'Controles')
        e_thick = cv2.getTrackbarPos('edgeThick', 'Controles')

        current_params = {
            "hsv_lower_h": h_min, "hsv_lower_s": s_min, "hsv_lower_v": v_min,
            "hsv_upper_h": h_max, "hsv_upper_s": s_max, "hsv_upper_v": v_max,
            "max_corners": m_corn, "quality_level": q_lvl, "min_distance": m_dist, "block_size": b_size,
            "edge_only": e_only, "poly_epsilon": p_eps, "edge_thickness": e_thick
        }

        # Aplicar pipeline
        mask = obtener_mascara_carton_filtrada(image_bgr, current_params)
        
        # Ocultar prints
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            image_result, _ = detectar_esquinas_caja(
                sobel_img, image_bgr.copy(), mask, 
                bounding_boxes=None, margen=0, 
                params=current_params
            )
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout

        # Redimensionar si es muy grande
        max_height = 600
        h, w = image_result.shape[:2]
        if h > max_height:
            aspect = w/h
            image_result = cv2.resize(image_result, (int(max_height*aspect), max_height))
            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            mask_bgr = cv2.resize(mask_bgr, (int(max_height*aspect), max_height))
        else:
            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

        cv2.imshow('Deteccion Esquinas', image_result)
        cv2.imshow('Mascara Huecos/Carton', mask_bgr)

        key = cv2.waitKey(100) & 0xFF
        if key == ord('q') or key == 27: # q or esc
            break
        elif key == ord('s'):
            with open(CONFIG_FILE, 'w') as f:
                json.dump(current_params, f, indent=4)
            print(f"✅ ¡Parámetros guardados exitosamente en {CONFIG_FILE}!")

    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
