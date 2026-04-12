import cv2
import numpy as np
import sys
import os

BASE_PATH = "../images/02Dic/"

DEFAULT_PARAMS = {
    # --- Máscara de color HSV ---
    "hsv_lower_h": 10,
    "hsv_lower_s": 65,
    "hsv_lower_v": 60,
    "hsv_upper_h": 30,
    "hsv_upper_s": 255,
    "hsv_upper_v": 255,
    # --- HoughLinesP ---
    "hough_threshold": 80,      # Votos mínimos para considerar una línea
    "hough_min_line":  150,     # Longitud mínima del segmento detectado (px)
    "hough_max_gap":   15,      # Hueco máximo entre puntos del mismo segmento (px)
    # --- Selección y agrupación ---
    "n_top_lines":     8,       # Nº de líneas más largas a usar
    "angle_tol":       20,      # Tolerancia para considerar dos líneas paralelas (grados)
    "cluster_dist":    80,      # Distancia para agrupar intersecciones en la misma esquina (px)
    "corner_margin":   120,     # Margen exterior a la imagen donde aún se aceptan esquinas (px)
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
            cv2.drawContours(mask_solida, [contorno_caja], -1, 255, thickness=cv2.FILLED)

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

    # Línea vertical
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
    Intersección de dos segmentos/líneas (formato x1,y1,x2,y2).
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

def _seleccionar_4_esquinas(puntos, h, w):
    """
    De todos los puntos candidatos selecciona los 4 que mejor
    representan un cuadrilátero convexo (tl, tr, bl, br).
    """
    if len(puntos) <= 4:
        return puntos

    pts_arr = np.array(puntos, dtype=np.float32)
    hull = cv2.convexHull(pts_arr.reshape(-1, 1, 2))
    hull_pts = [tuple(p[0].astype(int)) for p in hull]

    if len(hull_pts) < 4:
        return hull_pts

    # Tl = mín (x+y), Tr = mín (-x+y), Bl = mín (x-y), Br = máx (x+y)
    tl = min(hull_pts, key=lambda p: p[0] + p[1])
    tr = min(hull_pts, key=lambda p: -p[0] + p[1])
    bl = max(hull_pts, key=lambda p: -p[0] + p[1])   # = mín(x-y) → mín(-x+y)^-1
    br = max(hull_pts, key=lambda p: p[0] + p[1])

    # Eliminar duplicados manteniendo orden
    seen = set()
    result = []
    for p in [tl, tr, br, bl]:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# DETECCIÓN PRINCIPAL POR LÍNEAS
# ─────────────────────────────────────────────────────────────────────────────

def detectar_esquinas_por_lineas(mask_roi_solida, original_img, params=None, bounding_boxes=None, margen=20):
    """
    Detecta las 4 esquinas de la caja como intersección de las líneas de borde más largas.

    Algoritmo:
      1. Canny sobre la máscara sólida → bordes del contorno
      2. HoughLinesP → segmentos de línea
      3. Ordenar por longitud → elegir los N más largos
      4. Extender cada segmento a línea completa
      5. Calcular intersecciones de pares no paralelos
      6. Filtrar dentro de la imagen, agrupar cercanas
      7. Tomar las 4 esquinas del cuadrilátero convexo

    Args:
        mask_roi_solida : máscara binaria sólida del área de la caja
        original_img    : imagen BGR para visualización
        params          : diccionario de parámetros
        bounding_boxes  : [(x1,y1,x2,y2), ...] zonas a excluir (prendas YOLO)
        margen          : píxeles de margen alrededor de cada bounding box

    Returns:
        output_img : imagen con líneas (verde) y esquinas (rojo) dibujadas
        esquinas   : lista de (x, y)
    """
    if params is None:
        params = DEFAULT_PARAMS

    h, w = original_img.shape[:2]
    output_img = original_img.copy()

    # ── 1. Bordes del contorno de la máscara ─────────────────────────────────
    edges = cv2.Canny(mask_roi_solida, 50, 150)

    # ── 2. HoughLinesP ───────────────────────────────────────────────────────
    threshold  = max(10, params.get("hough_threshold", 80))
    min_line   = max(10, params.get("hough_min_line",  150))
    max_gap    = max(1,  params.get("hough_max_gap",    15))

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.radians(1.0),
        threshold=threshold,
        minLineLength=min_line,
        maxLineGap=max_gap,
    )

    if lines is None:
        print("⚠️  HoughLinesP no encontró líneas. Ajusta hough_threshold / hough_min_line.")
        return output_img, []

    # ── 3. Calcular longitud y ángulo, ordenar por longitud ──────────────────
    lineas_info = []
    for seg in lines:
        x1, y1, x2, y2 = seg[0]
        lineas_info.append({
            "seg":    (x1, y1, x2, y2),
            "length": _longitud(x1, y1, x2, y2),
            "angle":  _angulo(x1, y1, x2, y2),
        })
    lineas_info.sort(key=lambda d: d["length"], reverse=True)

    # ── 4. Seleccionar las N más largas ──────────────────────────────────────
    n_top = max(2, params.get("n_top_lines", 8))
    top   = lineas_info[:n_top]

    # ── 5. Extender cada segmento a línea completa ───────────────────────────
    lineas_ext = []
    for d in top:
        x1, y1, x2, y2 = d["seg"]
        le = _extender_linea(x1, y1, x2, y2, h, w)
        lineas_ext.append({"line": le, "angle": d["angle"], "length": d["length"]})

    # ── 6. Dibujar segmentos originales (azul) y líneas extendidas (verde) ───
    for d in top:
        x1, y1, x2, y2 = d["seg"]
        cv2.line(output_img, (x1, y1), (x2, y2), (255, 100, 0), 3)   # segmento – azul
    for d in lineas_ext:
        x1, y1, x2, y2 = d["line"]
        cv2.line(output_img, (x1, y1), (x2, y2), (0, 220, 0), 1)     # extendida – verde tenue

    # ── 7. Calcular intersecciones de pares no paralelos ─────────────────────
    angle_tol = params.get("angle_tol", 20)
    intersecciones = []
    for i in range(len(lineas_ext)):
        for j in range(i + 1, len(lineas_ext)):
            if _son_paralelas(lineas_ext[i]["angle"], lineas_ext[j]["angle"], angle_tol):
                continue
            pt = _interseccion(lineas_ext[i]["line"], lineas_ext[j]["line"])
            if pt is not None:
                intersecciones.append(pt)

    # ── 8. Filtrar intersecciones dentro de la imagen (+ margen) ─────────────
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
                if (bx1 - mg <= pt[0] <= bx2 + mg and
                        by1 - mg <= pt[1] <= by2 + mg):
                    return True
            return False
        intersecciones = [pt for pt in intersecciones
                          if not _en_bbox(pt, bounding_boxes, margen)]

    # ── 9. Agrupar intersecciones cercanas ────────────────────────────────────
    cluster_dist = params.get("cluster_dist", 80)
    candidatas   = _agrupar_cercanos(intersecciones, cluster_dist)

    # ── 10. Seleccionar las 4 mejores esquinas ────────────────────────────────
    esquinas = _seleccionar_4_esquinas(candidatas, h, w)

    # ── 11. Dibujar esquinas ──────────────────────────────────────────────────
    print(f"\n--- ESQUINAS POR LÍNEAS ({len(esquinas)} encontradas) ---")
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
    Pipeline completo: carga imagen → máscara → detección por líneas → visualización.

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

    # ── Detección de esquinas por líneas ─────────────────────────────────────
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
            f.write("REPORTE DE DETECCIÓN – MÉTODO LÍNEAS\n")
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