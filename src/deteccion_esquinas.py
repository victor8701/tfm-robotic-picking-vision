import cv2
import numpy as np
import sys
import os

BASE_PATH = "../images/02Dic/"

DEFAULT_PARAMS = {
    "hsv_lower_h": 10,
    "hsv_lower_s": 65,
    "hsv_lower_v": 60,
    "hsv_upper_h": 30,
    "hsv_upper_s": 255,
    "hsv_upper_v": 255,
    "max_corners": 20,
    "quality_level": 0.05,
    "min_distance": 70,
    "block_size": 3
}

# Variables globales para mantener la estructura del C++
# En Python no son estrictamente necesarias si pasamos argumentos, 
# pero las dejo para imitar tu código original.
imagen = None       # Color
imageGray = None    # Gris

def border_sobel(gray_img):
    """
    Aplica el filtro Sobel en X e Y y los combina.
    Retorna la imagen con los bordes detectados.
    """
    # Gradiente en X
    # CV_16S para evitar desbordamiento con valores negativos
    grad_x = cv2.Sobel(gray_img, cv2.CV_16S, 1, 0, ksize=3)
    abs_grad_x = cv2.convertScaleAbs(grad_x)
    
    # Gradiente en Y
    grad_y = cv2.Sobel(gray_img, cv2.CV_16S, 0, 1, ksize=3)
    abs_grad_y = cv2.convertScaleAbs(grad_y)
    
    # Combinar ambos gradientes
    combined = cv2.addWeighted(abs_grad_x, 0.5, abs_grad_y, 0.5, 0)
    return combined

def obtener_mascara_carton_filtrada(imagen_bgr, params=None):
    """
    1. Detecta todo lo que sea color cartón (suelo + caja).
    2. Calcula dónde está la caja (contorno más grande) rellenando huecos.
    3. Devuelve la máscara de color ORIGINAL pero recortada solo a la zona de la caja.
    """
    if params is None:
        params = DEFAULT_PARAMS

    # Convertir a HSV
    hsv = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2HSV)
    
    # --- AJUSTE RESTRICTIVO CON PARÁMETROS DINÁMICOS ---
    lower_brown = np.array([params.get("hsv_lower_h", 10), params.get("hsv_lower_s", 65), params.get("hsv_lower_v", 60)]) 
    upper_brown = np.array([params.get("hsv_upper_h", 30), params.get("hsv_upper_s", 255), params.get("hsv_upper_v", 255)])
    
    # Esta máscara tiene: La caja, el suelo y HUECOS donde hay objetos (porque no son marrones)
    mask_color = cv2.inRange(hsv, lower_brown, upper_brown)
    
    # Limpieza básica de ruido (puntos blancos sueltos)
    kernel_small = np.ones((5, 5), np.uint8)
    mask_color = cv2.morphologyEx(mask_color, cv2.MORPH_OPEN, kernel_small, iterations=1)

    # 2. ENCONTRAR LA "ZONA DE LA CAJA" (ROI)
    # Creamos una copia temporal para "cerrar" los objetos y ver la caja como un bloque sólido
    mask_para_contornos = mask_color.copy()
    
    # Usamos un kernel grande o muchas iteraciones para cerrar los huecos de los objetos
    # y conectar las paredes de la caja si están separadas por un objeto.
    kernel_big = np.ones((15, 15), np.uint8)
    mask_para_contornos = cv2.morphologyEx(mask_para_contornos, cv2.MORPH_CLOSE, kernel_big, iterations=3)
    
    # Buscamos contornos en esta máscara "sólida"
    contours, _ = cv2.findContours(mask_para_contornos, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Máscara negra vacía que será nuestra "Zona Permitida"
    mask_roi = np.zeros_like(mask_color)
    
    if contours:
        # Asumimos que la caja es el objeto marrón más grande de la imagen
        caja_contour = max(contours, key=cv2.contourArea)
        
        if cv2.contourArea(caja_contour) > 1000:
            # Dibujamos el contorno de la caja RELLENO en blanco.
            # Esto crea un rectángulo blanco donde está la caja, ignorando lo que haya dentro.
            cv2.drawContours(mask_roi, [caja_contour], -1, 255, thickness=cv2.FILLED)
    
    # 3. COMBINACIÓN FINAL (INTERSECCIÓN)
    # Queremos: Píxeles que sean marrones (mask_color) Y que estén dentro de la caja (mask_roi).
    # - Si es suelo marrón: mask_color=1, mask_roi=0 -> Resultado 0 (Eliminado)
    # - Si es objeto gris dentro: mask_color=0, mask_roi=1 -> Resultado 0 (Eliminado)
    # - Si es cartón de la caja: mask_color=1, mask_roi=1 -> Resultado 1 (Conservado)
    final_mask = cv2.bitwise_and(mask_color, mask_roi)
    
    # Erosión final ligera para afinar bordes
    final_mask = cv2.erode(final_mask, kernel_small, iterations=2)
    
    return final_mask

def detectar_esquinas_caja(sobel_img, original_img, mask_color, bounding_boxes=None, margen=20, max_corners=None, quality_level=None, min_distance=None, block_size=None, params=None):
    """
    Detecta esquinas y muestra solo la caja con puntos grandes.
    
    Args:
        sobel_img: Imagen procesada con Sobel
        original_img: Imagen original
        mask_color: Máscara de color del cartón
        bounding_boxes: Lista de bounding boxes de YOLO [(x1, y1, x2, y2), ...]
        margen: Margen en píxeles alrededor de prendas
        max_corners: Número máximo de esquinas (opcional si se pasa en params)
        quality_level: Calidad mínima de esquinas (opcional)
        min_distance: Distancia mínima entre esquinas (opcional)
        block_size: Tamaño de bloque para esquinas (opcional)
        params: Diccionario de configuración general
    """
    height, width = sobel_img.shape[:2]

    if params is None:
        params = DEFAULT_PARAMS

    _max_corners = max_corners if max_corners is not None else params.get("max_corners", 20)
    _quality_level = quality_level if quality_level is not None else params.get("quality_level", 0.05)
    _min_distance = min_distance if min_distance is not None else params.get("min_distance", 70)
    _block_size = block_size if block_size is not None else params.get("block_size", 3)
    
    # 1. Crear máscara de exclusión basada en bounding boxes de YOLO
    mascara_exclusion = np.ones_like(mask_color) * 255  # Empezar con todo blanco (permitido)
    
    if bounding_boxes is not None and len(bounding_boxes) > 0:
        print(f"\n--- CREANDO MÁSCARA DE EXCLUSIÓN PARA {len(bounding_boxes)} PRENDAS ---")
        for i, (x1, y1, x2, y2) in enumerate(bounding_boxes):
            # Expandir la bounding box para asegurar que cubrimos los bordes
            x1_exp = max(0, int(x1) - margen)
            y1_exp = max(0, int(y1) - margen)
            x2_exp = min(width, int(x2) + margen)
            y2_exp = min(height, int(y2) + margen)
            
            # Pintar de negro (0) el área de la prenda en la máscara
            cv2.rectangle(mascara_exclusion, (x1_exp, y1_exp), (x2_exp, y2_exp), 0, -1)
            print(f"  Prenda {i+1}: Excluyendo área ({x1_exp}, {y1_exp}) a ({x2_exp}, {y2_exp})")
        
        # Combinar con la máscara de color original
        mask_color = cv2.bitwise_and(mask_color, mascara_exclusion)
        print(f"  ✓ Máscara de exclusión aplicada")
    
    # 2. Detección sobre el resultado de Sobel
    # corners devuelve un array numpy de forma (N, 1, 2)
    corners = cv2.goodFeaturesToTrack(
        sobel_img, 
        maxCorners=_max_corners, 
        qualityLevel=_quality_level, 
        minDistance=_min_distance,
        blockSize=_block_size, 
        useHarrisDetector=False, 
        k=0.04,
        mask=mask_color # AQUI usamos la máscara inteligente
    )

    # Visualización
    output_img = cv2.bitwise_and(original_img, original_img, mask=mask_color)
    
    # Lista para almacenar coordenadas de esquinas válidas
    esquinas_validas = []

    if corners is not None:
        # Convertimos a lista para poder ordenar fácilmente
        corners_list = list(corners)
        # Ordenar desde abajo-izquierda
        corners_list.sort(key=lambda c: (c[0][0]**2) + (height - c[0][1])**2)

        print("\n--- ESQUINAS ENCONTRADAS (Dentro de la caja) ---")
        for i, corner in enumerate(corners_list):
            x, y = corner.ravel()
            x_int, y_int = int(x), int(y)
            
            # Almacenar coordenadas
            esquinas_validas.append((x_int, y_int))
            
            # Dibujar en la imagen
            cv2.circle(output_img, (x_int, y_int), 10, (0, 0, 255), -1)
            cv2.putText(output_img, str(i + 1), (x_int + 15, y_int - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            print(f"  Esquina {i+1}: ({x_int}, {y_int})")
        print("-" * 40)
        return output_img, esquinas_validas
    else:
        print("No se encontraron esquinas.")
        return output_img, esquinas_validas

def charge_image(ruta_imagen=None, prendas_detectadas=None, mostrar_ventana=True, 
                 guardar_reporte=True, margen_exclusion=20, max_esquinas=None, 
                 quality_level=None, min_distance=None, params=None):
    """
    Detecta esquinas de la caja y opcionalmente dibuja centros de prendas.
    
    Args:
        ruta_imagen: Ruta a la imagen (si es None, pide al usuario)
        prendas_detectadas: Lista de tuplas [(nombre, conf, centro_x, centro_y, x1, y1, x2, y2), ...]
        mostrar_ventana: True/False para mostrar ventana
        guardar_reporte: True/False para guardar reporte
        margen_exclusion: Margen en píxeles alrededor de prendas
        max_esquinas: Número máximo de esquinas a detectar (si se omite usa params)
        quality_level: Calidad mínima de esquinas (0.0-1.0) (si se omite usa params)
        min_distance: Distancia mínima entre esquinas (píxeles) (si se omite usa params)
        params: Diccionario de configuración de ajustes interactivos
    
    Returns:
        imagen_result: Imagen procesada con esquinas y centros de prendas
        esquinas_caja: Lista de coordenadas de esquinas
        prendas_detectadas: Lista de prendas detectadas
    """
    global imagen, imageGray

    if ruta_imagen is None:
        print("Enter image name (.jpg format)")
        if sys.version_info[0] < 3:
            image_name = raw_input()
        else:
            image_name = input()
        
        # Construcción de la ruta
        # Si la carpeta es local, puedes quitar BASE_PATH y poner 'images/' + ...
        path = os.path.join(BASE_PATH, image_name + ".jpg")
        
        # Intentar cargar imagen (la ruta debe ser correcta o fallará)
        # Comprobamos si existe el archivo primero para evitar error de opencv
        if not os.path.isfile(path):
            # Fallback por si acaso la ruta absoluta no funciona, probamos local
            path = f"images/{image_name}.jpg"
            if not os.path.isfile(path):
                print(f"Error al cargar la imagen: {path}")
                sys.exit(1)
    else:
        path = ruta_imagen

    # Cargar en escala de grises
    imageGray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    # Cargar en color
    imagen = cv2.imread(path, cv2.IMREAD_COLOR)

    if imagen is None:
        print(f"Error al cargar la imagen (formato incorrecto o vacía): {path}")
        sys.exit(1)

    # 1. Filtro Sobel (Detecta todos los bordes de la imagen)
    imagen_sobel = border_sobel(imageGray)

    # 2. Máscara Inteligente (Color Cartón PERO limitado al área de la caja)
    mascara_filtrada = obtener_mascara_carton_filtrada(imagen, params)

    # 3. Extraer bounding boxes de las prendas detectadas (si existen)
    bboxes_prendas = None
    if prendas_detectadas is not None and len(prendas_detectadas) > 0:
        bboxes_prendas = []
        print(f"\n--- EXTRAYENDO BOUNDING BOXES DE {len(prendas_detectadas)} PRENDAS ---")
        for item in prendas_detectadas:
            # El formato puede ser (nombre, conf, cx, cy) o (nombre, conf, cx, cy, x1, y1, x2, y2)
            if len(item) == 8:
                nombre, conf, centro_x, centro_y, x1, y1, x2, y2 = item
                bboxes_prendas.append((x1, y1, x2, y2))
                print(f"  {nombre}: bbox real ({x1}, {y1}) a ({x2}, {y2})")
            else:
                # Formato antiguo, estimar bbox
                nombre, conf, centro_x, centro_y = item
                ancho_estimado = 150
                alto_estimado = 150
                x1 = centro_x - ancho_estimado // 2
                y1 = centro_y - alto_estimado // 2
                x2 = centro_x + ancho_estimado // 2
                y2 = centro_y + alto_estimado // 2
                bboxes_prendas.append((x1, y1, x2, y2))
                print(f"  {nombre}: bbox estimada ({x1}, {y1}) a ({x2}, {y2})")

    # 4. Detectar esquinas (ahora con exclusión de áreas de prendas)
    image_result, esquinas_caja = detectar_esquinas_caja(imagen_sobel, imagen, mascara_filtrada, bboxes_prendas, margen_exclusion, max_esquinas, quality_level, min_distance, block_size=None, params=params)

    # 4. Dibujar centros de prendas si se proporcionaron
    if prendas_detectadas is not None and len(prendas_detectadas) > 0:
        print(f"\n--- Dibujando {len(prendas_detectadas)} centros de prendas ---")
        for item in prendas_detectadas:
            # Desempaquetar según formato
            if len(item) == 8:
                nombre, conf, centro_x, centro_y, x1, y1, x2, y2 = item
            else:
                nombre, conf, centro_x, centro_y = item
            # Dibujar punto verde (BGR) para el centro de la prenda
            cv2.circle(image_result, (centro_x, centro_y), 8, (0, 255, 0), -1)
            # Dibujar etiqueta con el nombre de la prenda
            cv2.putText(image_result, nombre, (centro_x + 12, centro_y - 12),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            print(f"  ✓ {nombre}: ({centro_x}, {centro_y})")

    # 5. Guardar coordenadas en archivo de texto (coordenadas primero, luego YOLO)
    if guardar_reporte and (prendas_detectadas or esquinas_caja):
        # Crear directorio de salida si no existe
        output_dir = "resultados_deteccion"
        os.makedirs(output_dir, exist_ok=True)
        
        # Generar nombre de archivo basado en la imagen
        from pathlib import Path
        import glob
        nombre_imagen = Path(path).stem
        archivo_reporte = os.path.join(output_dir, f"{nombre_imagen}_reporte.txt")
        
        with open(archivo_reporte, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("REPORTE COMPLETO DE DETECCIÓN\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Imagen: {Path(path).name}\n")
            f.write(f"Ruta: {path}\n")
            f.write(f"Fecha: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # ============================================================
            # PARTE 1: COORDENADAS PARA ROBÓTICA (PRIMERO)
            # ============================================================
            f.write("=" * 80 + "\n")
            f.write("PARTE 1: COORDENADAS PARA ROBÓTICA\n")
            f.write("=" * 80 + "\n\n")
            
            # Guardar esquinas de la caja
            f.write("ESQUINAS DE LA CAJA (Coordenadas en píxeles)\n")
            f.write("-" * 80 + "\n")
            if esquinas_caja and len(esquinas_caja) > 0:
                for i, (x, y) in enumerate(esquinas_caja):
                    f.write(f"  Esquina {i+1}: x={x:4d}, y={y:4d}\n")
                f.write(f"\nTotal esquinas detectadas: {len(esquinas_caja)}\n\n")
            else:
                f.write("  ⚠️ No se detectaron esquinas\n\n")
            
            # Guardar centros de prendas
            f.write("CENTROS DE PRENDAS (Coordenadas en píxeles)\n")
            f.write("-" * 80 + "\n")
            if prendas_detectadas and len(prendas_detectadas) > 0:
                for i, item in enumerate(prendas_detectadas, 1):
                    # Desempaquetar según formato
                    if len(item) == 8:
                        nombre, conf, centro_x, centro_y, x1, y1, x2, y2 = item
                    else:
                        nombre, conf, centro_x, centro_y = item
                    f.write(f"  Prenda {i}: {nombre:12s} | x={centro_x:4d}, y={centro_y:4d} | Confianza: {conf:.2f} ({int(conf*100)}%)\n")
                f.write(f"\nTotal prendas detectadas: {len(prendas_detectadas)}\n")
            else:
                f.write("  ⚠️ No se detectaron prendas\n")
            
            # ============================================================
            # PARTE 2: REPORTE DETALLADO YOLO (SEGUNDO)
            # ============================================================
            f.write("\n" + "=" * 80 + "\n")
            f.write("PARTE 2: REPORTE DETALLADO DE YOLO\n")
            f.write("=" * 80 + "\n\n")
            
            # Buscar el archivo detecciones.txt más reciente en runs/detect
            archivo_yolo = None
            try:
                # Buscar en todos los directorios predict*
                predict_dirs = glob.glob("runs/detect/predict*")
                if predict_dirs:
                    # Ordenar por tiempo de modificación (más reciente primero)
                    predict_dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                    # Buscar detecciones.txt en el directorio más reciente
                    for predict_dir in predict_dirs:
                        posible_archivo = os.path.join(predict_dir, "detecciones.txt")
                        if os.path.exists(posible_archivo):
                            archivo_yolo = posible_archivo
                            break
            except Exception as e:
                print(f"  ⚠️ No se pudo buscar archivo YOLO: {e}")
            
            if archivo_yolo and os.path.exists(archivo_yolo):
                try:
                    with open(archivo_yolo, 'r', encoding='utf-8') as yolo_file:
                        contenido_yolo = yolo_file.read()
                        f.write(contenido_yolo)
                        f.write("\n")
                except Exception as e:
                    f.write(f"⚠️ Error al leer archivo YOLO: {e}\n\n")
            else:
                f.write("⚠️ No se encontró archivo de detecciones YOLO\n\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("FIN DEL REPORTE\n")
            f.write("=" * 80 + "\n")
        
        print(f"\n📄 Reporte completo guardado en: {archivo_reporte}")

    # Visualización final (opcional)
    if mostrar_ventana:
        imagen_combinada = cv2.hconcat([imagen, image_result])
        
        # Redimensionar si la imagen es muy grande para la pantalla
        max_height = 800  # Ajusta según tu resolución de pantalla
        height, width = imagen_combinada.shape[:2]
        if height > max_height:
            aspect_ratio = width / height
            new_height = max_height
            new_width = int(new_height * aspect_ratio)
            imagen_combinada = cv2.resize(imagen_combinada, (new_width, new_height))
        
        cv2.namedWindow("Procesado", cv2.WINDOW_AUTOSIZE)
        cv2.imshow("Procesado", imagen_combinada)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    return image_result, esquinas_caja, prendas_detectadas

if __name__ == "__main__":
    charge_image()