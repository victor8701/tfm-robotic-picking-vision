import cv2
import numpy as np
import sys
import os

BASE_PATH = "../images/02Dic/"

DEFAULT_PARAMS = {
    # --- Mascara de color HSV ---
    "hsv_lower_h": 10,
    "hsv_lower_s": 65,
    "hsv_lower_v": 60,
    "hsv_upper_h": 30,
    "hsv_upper_s": 255,
    "hsv_upper_v": 255,
    # --- HoughLinesP ---
    "hough_threshold": 40,      # Votos minimos (bajar si no encuentra lineas)
    "hough_min_line":  60,      # Longitud minima del segmento detectado (px)
    "hough_max_gap":   20,      # Hueco maximo entre puntos del mismo segmento (px)
    # --- Seleccion y agrupacion ---
    "n_top_lines":     8,       # N lineas a usar (se distribuyen entre direcciones)
    "angle_tol":       20,      # Tolerancia para considerar dos lineas paralelas (grados)
    "cluster_dist":    80,      # Distancia para agrupar intersecciones en la misma esquina (px)
    "corner_margin":   120,     # Margen exterior a la imagen donde se aceptan esquinas (px)
    "max_corners":     4,       # N maximo de esquinas (caja cerrada=4, abierta con solapas=8-16)
}

# ─────────────────────────────────────────────────────────────────────────────
# MÁSCARA DE COLOR
# ─────────────────────────────────────────────────────────────────────────────

def obtener_mascara_roi_solida(imagen_bgr, params=None):
    """
    Genera la máscara SÓLIDA del área de la caja (sin huecos).
    Sirve como base para detectar el contorno sobre el que se aplica Canny+Hough.
    Devuelve: (mask_solida, contorno_caja)
    """
    if params is None:
        params = DEFAULT_PARAMS

    hsv = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2HSV)
    lower = np.array([params.get("hsv_lower_h", 10),
                      params.get("hsv_lower_s", 65),
                      params.get("hsv_lower_v", 60)])
    upper = np.array([params.get("hsv_upper_h", 30),
                      params.get("hsv_upper_s", 255),
                      params.get("hsv_upper_v", 255)])
    mask_color = cv2.inRange(hsv, lower, upper)

    # Limpieza de ruido
    k5 = np.ones((5, 5), np.uint8)
    mask_color = cv2.morphologyEx(mask_color, cv2.MORPH_OPEN, k5, iterations=1)

    # Cerrar huecos grandes para obtener la "caja sólida"
    k15 = np.ones((15, 15), np.uint8)
    mask_cerrada = cv2.morphologyEx(mask_color, cv2.MORPH_CLOSE, k15, iterations=3)

    contours, _ = cv2.findContours(mask_cerrada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    mask_solida = np.zeros_like(mask_color)
    contorno_caja = None
    if contours:
        contorno_caja = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contorno_caja) > 1000:
            # Usar Convex Hull para asegurar que el interior de la caja
            # se incluya aunque el color del cartón esté ocluido por las bolsas.
            hull = cv2.convexHull(contorno_caja)
            cv2.drawContours(mask_solida, [hull], -1, 255, thickness=cv2.FILLED)

    return mask_solida, contorno_caja


def obtener_mascara_carton_filtrada(imagen_bgr, params=None):
    """
    Máscara de color cartón recortada al ROI de la caja (sin huecos).
    Se mantiene por compatibilidad con visualización.
    """
    if params is None:
        params = DEFAULT_PARAMS

    mask_solida, _ = obtener_mascara_roi_solida(imagen_bgr, params)
    hsv = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2HSV)
    lower = np.array([params.get("hsv_lower_h", 10),
                      params.get("hsv_lower_s", 65),
                      params.get("hsv_lower_v", 60)])
    upper = np.array([params.get("hsv_upper_h", 30),
                      params.get("hsv_upper_s", 255),
                      params.get("hsv_upper_v", 255)])
    mask_color = cv2.inRange(hsv, lower, upper)
    k5 = np.ones((5, 5), np.uint8)
    mask_color = cv2.morphologyEx(mask_color, cv2.MORPH_OPEN, k5, iterations=1)
    return cv2.bitwise_and(mask_color, mask_solida)


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES GEOMÉTRICAS
# ─────────────────────────────────────────────────────────────────────────────

def _longitud(x1, y1, x2, y2):
    return float(np.hypot(x2 - x1, y2 - y1))

def _angulo(x1, y1, x2, y2):
    """Ángulo en grados normalizado a [0°, 180°)."""
    return float(np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180)

def _extender_linea(x1, y1, x2, y2, h, w):
    """Extiende un segmento hasta los bordes de la imagen."""
    pts = []
    dx = x2 - x1
    dy = y2 - y1

    # linea vertical
    if abs(dx) < 1e-6:
        return (x1, 0, x1, h - 1)

    m = dy / dx
    b = y1 - m * x1

    # Intersección con x = 0
    yi = m * 0 + b
    if 0 <= yi <= h - 1:
        pts.append((0, int(round(yi))))
    # Intersección con x = w-1
    yi = m * (w - 1) + b
    if 0 <= yi <= h - 1:
        pts.append((w - 1, int(round(yi))))
    # Intersección con y = 0
    if abs(m) > 1e-6:
        xi = (0 - b) / m
        if 0 <= xi <= w - 1:
            pts.append((int(round(xi)), 0))
    # Intersección con y = h-1
    if abs(m) > 1e-6:
        xi = (h - 1 - b) / m
        if 0 <= xi <= w - 1:
            pts.append((int(round(xi)), h - 1))

    if len(pts) >= 2:
        return (pts[0][0], pts[0][1], pts[-1][0], pts[-1][1])
    return (x1, y1, x2, y2)

def _interseccion(l1, l2):
    """
    Intersección de dos segmentos/lineas (formato x1,y1,x2,y2).
    Retorna (x, y) o None si son paralelas.
    """
    x1, y1, x2, y2 = l1
    x3, y3, x4, y4 = l2
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-6:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    x = x1 + t * (x2 - x1)
    y = y1 + t * (y2 - y1)
    return (int(round(x)), int(round(y)))

def _son_paralelas(a1, a2, tolerancia=20):
    """True si los ángulos a1 y a2 son paralelos dentro de la tolerancia."""
    diff = abs(a1 - a2) % 180
    if diff > 90:
        diff = 180 - diff
    return diff < tolerancia

def _agrupar_cercanos(pts, dist_min):
    """
    Agrupa puntos cuya distancia euclidea sea < dist_min.
    Retorna el centroide de cada grupo.
    """
    if not pts:
        return []
    usados = [False] * len(pts)
    grupos = []
    for i, p in enumerate(pts):
        if usados[i]:
            continue
        grupo = [p]
        usados[i] = True
        for j, q in enumerate(pts):
            if usados[j]:
                continue
            if np.hypot(p[0] - q[0], p[1] - q[1]) < dist_min:
                grupo.append(q)
                usados[j] = True
        cx = int(round(np.mean([g[0] for g in grupo])))
        cy = int(round(np.mean([g[1] for g in grupo])))
        grupos.append((cx, cy))
    return grupos

def _seleccionar_esquinas(puntos, h, w, max_corners=4):
    """
    De todos los puntos candidatos selecciona hasta `max_corners` que mejor
    representan un polígono convexo.

    Estrategia:
      - Calcula los 4 extremos geométricos del convex hull (tl, tr, br, bl).
      - Si max_corners <= 4: devuelve los primeros max_corners de esos extremos.
      - Si max_corners >  4: añade puntos adicionales del hull espaciados
        uniformemente hasta completar max_corners.

    Así el slider MaxCorners controla exactamente cuántas esquinas se devuelven,
    entre 3 (una esquina tapada) y N (formas con más aristas visibles).
    """
    max_corners = max(3, int(max_corners))

    if len(puntos) == 0:
        return []

    if len(puntos) <= max_corners:
        return puntos

    pts_arr = np.array(puntos, dtype=np.float32)
    hull = cv2.convexHull(pts_arr.reshape(-1, 1, 2))
    hull_pts = [tuple(p[0].astype(int)) for p in hull]

    if len(hull_pts) <= max_corners:
        return hull_pts

    # --- Los 4 extremos geométricos (siempre útiles para cajas) --------------
    tl = min(hull_pts, key=lambda p: p[0] + p[1])   # arriba-izquierda
    tr = min(hull_pts, key=lambda p: -p[0] + p[1])  # arriba-derecha
    br = max(hull_pts, key=lambda p: p[0] + p[1])   # abajo-derecha
    bl = max(hull_pts, key=lambda p: -p[0] + p[1])  # abajo-izquierda

    seen   = set()
    result = []
    for p in [tl, tr, br, bl]:
        if p not in seen:
            seen.add(p)
            result.append(p)

    # Si el usuario pidió menos de 4, truncamos
    if max_corners <= len(result):
        return result[:max_corners]

    # Si pidió más de 4, completamos con puntos del hull espaciados uniformemente
    n = len(hull_pts)
    extra_needed = max_corners - len(result)
    step = max(1, n // (extra_needed + 1))
    for i in range(1, n, step):
        p = hull_pts[i]
        if p not in seen:
            seen.add(p)
            result.append(p)
        if len(result) >= max_corners:
            break

    return result


# ─────────────────────────────────────────────────────────────────────────────
# DETECCIÓN PRINCIPAL POR lineaS
# ─────────────────────────────────────────────────────────────────────────────

def detectar_esquinas_por_lineas(mask_roi_solida, original_img, params=None, bounding_boxes=None, margen=20):
    """
    Detecta las esquinas de la caja como interseccion de las lineas de borde.

    Algoritmo:
      1. Extrae el borde 1px de la mascara solida por morfologia (mas limpio que Canny en binario)
      2. HoughLinesP -> segmentos de linea sobre el borde
      3. Agrupa segmentos por direccion angular
      4. Seleccion round-robin entre grupos: garantiza lineas en TODAS las direcciones
         (FIX: el codigo anterior tomaba los N mas largos globalmente, por lo que todos
          podian ser paralelos entre si -> 0 intersecciones -> 0 esquinas)
      5. Extiende cada segmento a linea completa
      6. Calcula intersecciones de pares no paralelos
      7. Filtra por margen de imagen, agrupa cercanas
      8. Devuelve las max_corners mejores esquinas del poligono convexo

    Args:
        mask_roi_solida : mascara binaria solida del area de la caja
        original_img    : imagen BGR para visualizacion
        params          : diccionario de parametros
        bounding_boxes  : [(x1,y1,x2,y2), ...] zonas a excluir (prendas YOLO)
        margen          : pixeles de margen alrededor de cada bounding box

    Returns:
        output_img : imagen con lineas (azul/verde) y esquinas (rojo) dibujadas
        esquinas   : lista de (x, y)
    """
    if params is None:
        params = DEFAULT_PARAMS

    h, w = original_img.shape[:2]
    output_img = original_img.copy()

    # -- 1. Borde morfologico de la mascara -----------------------------------
    # Para mascara binaria (0/255), la frontera exacta es: mascara - erosion.
    # Es mas limpio que Canny porque no depende de gradientes suavizados.
    kernel3 = np.ones((3, 3), np.uint8)
    edges = mask_roi_solida - cv2.erode(mask_roi_solida, kernel3, iterations=1)
    # Dilatar ligeramente para que Hough acumule mas votos por borde
    edges = cv2.dilate(edges, kernel3, iterations=1)

    # -- 2. HoughLinesP -------------------------------------------------------
    threshold = max(5, params.get("hough_threshold", 40))
    min_line  = max(5, params.get("hough_min_line",  60))
    max_gap   = max(1, params.get("hough_max_gap",   20))

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.radians(1.0),
        threshold=threshold,
        minLineLength=min_line,
        maxLineGap=max_gap,
    )

    if lines is None:
        print("No se encontraron lineas. Baja HoughThresh o MinLineLen.")
        return output_img, []

    # -- 3. Calcular longitud y angulo de cada segmento -----------------------
    lineas_info = []
    for seg in lines:
        x1, y1, x2, y2 = seg[0]
        lineas_info.append({
            "seg":    (x1, y1, x2, y2),
            "length": _longitud(x1, y1, x2, y2),
            "angle":  _angulo(x1, y1, x2, y2),
        })
    lineas_info.sort(key=lambda d: d["length"], reverse=True)

    # -- 4. Agrupar por direccion angular y seleccionar en round-robin --------
    # PROBLEMA ANTERIOR: top = lineas_info[:n_top] toma los N mas largos
    # globalmente. Si los N mas largos son todos horizontales (borde superior
    # e inferior de la caja son los mas largos), no hay lineas verticales
    # -> no hay intersecciones perpendiculares -> 0 esquinas detectadas.
    #
    # SOLUCION: agrupar por angulo, luego round-robin entre grupos para
    # garantizar que se seleccionan lineas en todas las direcciones presentes.
    n_top     = max(2, params.get("n_top_lines", 8))
    angle_tol = max(1, params.get("angle_tol", 20))

    grupos = []   # [{"ang": float, "lineas": [info, ...]}, ...]
    for info in lineas_info:   # ya ordenados de mayor a menor longitud
        ang = info["angle"]
        asignado = False
        for g in grupos:
            diff = abs(ang - g["ang"]) % 180
            if diff > 90:
                diff = 180 - diff
            if diff < angle_tol:
                g["lineas"].append(info)
                asignado = True
                break
        if not asignado:
            grupos.append({"ang": ang, "lineas": [info]})

    # Round-robin: tomar la siguiente mejor linea de cada grupo rotando
    top = []
    ptr = [0] * len(grupos)
    while len(top) < n_top:
        avance = False
        for i, g in enumerate(grupos):
            if ptr[i] < len(g["lineas"]):
                top.append(g["lineas"][ptr[i]])
                ptr[i] += 1
                avance = True
                if len(top) >= n_top:
                    break
        if not avance:
            break

    # -- 5. Extender cada segmento a linea completa ---------------------------
    lineas_ext = []
    for d in top:
        x1, y1, x2, y2 = d["seg"]
        le = _extender_linea(x1, y1, x2, y2, h, w)
        lineas_ext.append({"line": le, "angle": d["angle"], "length": d["length"]})

    # -- 6. Dibujar segmentos (azul) y lineas extendidas (verde) --------------
    for d in top:
        x1, y1, x2, y2 = d["seg"]
        cv2.line(output_img, (x1, y1), (x2, y2), (255, 100, 0), 3)
    for d in lineas_ext:
        x1, y1, x2, y2 = d["line"]
        cv2.line(output_img, (x1, y1), (x2, y2), (0, 220, 0), 1)

    # -- 7. Intersecciones de pares no paralelos ------------------------------
    intersecciones = []
    for i in range(len(lineas_ext)):
        for j in range(i + 1, len(lineas_ext)):
            if _son_paralelas(lineas_ext[i]["angle"], lineas_ext[j]["angle"], angle_tol):
                continue
            pt = _interseccion(lineas_ext[i]["line"], lineas_ext[j]["line"])
            if pt is not None:
                intersecciones.append(pt)

    # -- 8. Filtrar por margen de imagen --------------------------------------
    corner_margin = params.get("corner_margin", 120)
    intersecciones = [
        pt for pt in intersecciones
        if (-corner_margin <= pt[0] <= w + corner_margin and
            -corner_margin <= pt[1] <= h + corner_margin)
    ]

    # Excluir intersecciones dentro de bounding boxes de prendas
    if bounding_boxes:
        def _en_bbox(pt, bboxes, mg):
            for (bx1, by1, bx2, by2) in bboxes:
                if bx1 - mg <= pt[0] <= bx2 + mg and by1 - mg <= pt[1] <= by2 + mg:
                    return True
            return False
        intersecciones = [pt for pt in intersecciones
                          if not _en_bbox(pt, bounding_boxes, margen)]

    # -- 9. Agrupar intersecciones cercanas ------------------------------------
    cluster_dist = params.get("cluster_dist", 80)
    candidatas   = _agrupar_cercanos(intersecciones, cluster_dist)

    # -- 10. Seleccionar las N mejores esquinas --------------------------------
    max_corners = max(3, params.get("max_corners", 4))
    esquinas    = _seleccionar_esquinas(candidatas, h, w, max_corners)

    # -- 11. Dibujar esquinas --------------------------------------------------
    print(f"\n--- ESQUINAS ({len(esquinas)} encontradas | candidatas={len(candidatas)} | grupos_dir={len(grupos)}) ---")
    for i, (x, y) in enumerate(esquinas):
        cv2.circle(output_img, (x, y), 12, (0, 0, 255), -1)
        cv2.putText(output_img, str(i + 1), (x + 15, y - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        print(f"  Esquina {i + 1}: ({x}, {y})")
    print("-" * 40)

    return output_img, esquinas



# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL (llamada desde main.py)
# ─────────────────────────────────────────────────────────────────────────────

def charge_image(ruta_imagen=None, prendas_detectadas=None, mostrar_ventana=True,
                 guardar_reporte=True, margen_exclusion=20, params=None):
    """
    Pipeline completo: carga imagen → máscara → detección por lineas → visualización.

    Args:
        ruta_imagen        : ruta a la imagen (si None, la pide al usuario)
        prendas_detectadas : lista [(nombre, conf, cx, cy, x1, y1, x2, y2), ...]
        mostrar_ventana    : mostrar ventana OpenCV
        guardar_reporte    : guardar reporte txt
        margen_exclusion   : margen alrededor de prendas YOLO
        params             : diccionario de configuración (config_esquinas.json)

    Returns:
        imagen_result, esquinas_caja, prendas_detectadas
    """
    global imagen, imageGray

    if params is None:
        params = DEFAULT_PARAMS

    # ── Cargar imagen ─────────────────────────────────────────────────────────
    if ruta_imagen is None:
        print("Introduce el nombre de la imagen (sin .jpg):")
        image_name = input().strip()
        path = os.path.join(BASE_PATH, image_name + ".jpg")
        if not os.path.isfile(path):
            path = f"images/{image_name}.jpg"
            if not os.path.isfile(path):
                print(f"Error al cargar la imagen: {path}")
                sys.exit(1)
    else:
        path = ruta_imagen

    imageGray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    imagen    = cv2.imread(path, cv2.IMREAD_COLOR)

    if imagen is None:
        print(f"Error al cargar la imagen: {path}")
        sys.exit(1)

    # ── Máscara sólida del área de la caja ───────────────────────────────────
    mask_solida, _ = obtener_mascara_roi_solida(imagen, params)

    # ── Extraer bounding boxes de prendas ────────────────────────────────────
    bboxes_prendas = None
    if prendas_detectadas:
        bboxes_prendas = []
        for item in prendas_detectadas:
            if len(item) == 8:
                _, _, _, _, x1, y1, x2, y2 = item
                bboxes_prendas.append((x1, y1, x2, y2))
            else:
                _, _, cx, cy = item[:4]
                dxy = 75
                bboxes_prendas.append((cx - dxy, cy - dxy, cx + dxy, cy + dxy))

    # ── Detección de esquinas por lineas ─────────────────────────────────────
    image_result, esquinas_caja = detectar_esquinas_por_lineas(
        mask_solida, imagen.copy(), params, bboxes_prendas, margen_exclusion
    )

    # ── Dibujar centros de prendas ────────────────────────────────────────────
    if prendas_detectadas:
        for item in prendas_detectadas:
            if len(item) == 8:
                nombre, conf, cx, cy, *_ = item
            else:
                nombre, conf, cx, cy = item[:4]
            cv2.circle(image_result, (cx, cy), 8, (0, 255, 0), -1)
            cv2.putText(image_result, nombre, (cx + 12, cy - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # ── Guardar reporte ───────────────────────────────────────────────────────
    if guardar_reporte and (prendas_detectadas or esquinas_caja):
        from pathlib import Path
        output_dir = "resultados_deteccion"
        os.makedirs(output_dir, exist_ok=True)
        nombre_img = Path(path).stem
        archivo_rep = os.path.join(output_dir, f"{nombre_img}_reporte.txt")
        import datetime
        with open(archivo_rep, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("REPORTE DE DETECCIÓN – MÉTODO lineaS\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Imagen : {Path(path).name}\n")
            f.write(f"Fecha  : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("ESQUINAS DE LA CAJA (x, y)\n")
            f.write("-" * 40 + "\n")
            for i, (x, y) in enumerate(esquinas_caja):
                f.write(f"  Esquina {i+1}: x={x:4d}, y={y:4d}\n")
            if not esquinas_caja:
                f.write("  ⚠️  No se detectaron esquinas\n")
        print(f"\n📄 Reporte guardado en: {archivo_rep}")

    # ── Visualización ─────────────────────────────────────────────────────────
    if mostrar_ventana:
        combinada = cv2.hconcat([imagen, image_result])
        max_h = 800
        hh, ww = combinada.shape[:2]
        if hh > max_h:
            combinada = cv2.resize(combinada, (int(ww * max_h / hh), max_h))
        cv2.namedWindow("Procesado", cv2.WINDOW_AUTOSIZE)
        cv2.imshow("Procesado", combinada)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return image_result, esquinas_caja, prendas_detectadas


# ─────────────────────────────────────────────────────────────────────────────
# Variables globales (compatibilidad)
imagen    = None
imageGray = None

if __name__ == "__main__":
    charge_image()