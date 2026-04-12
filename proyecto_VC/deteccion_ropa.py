import cv2
from ultralytics import YOLO
import sys
import os

def detectar_ropa(ruta_imagen=None, mostrar_ventana=None, guardar_archivos=None, confianza_minima=None, iou_threshold=None):
    """
    Detecta prendas de ropa en una imagen usando YOLO.
    
    Args:
        ruta_imagen: Ruta a la imagen (si es None, pide al usuario)
        mostrar_ventana: True/False para mostrar ventana (si es None, usa configuración)
        guardar_archivos: True/False para guardar archivos (si es None, usa configuración)
        confianza_minima: Umbral de confianza mínima (si es None, usa 0.5)
        iou_threshold: Umbral de IoU para duplicados (si es None, usa 0.3)
    
    Returns:
        Lista de tuplas: [(nombre, confianza, centro_x, centro_y, x1, y1, x2, y2), ...]
    """
    # ============================================
    # CONFIGURACIÓN
    # ============================================
    GUARDAR_IMAGENES = guardar_archivos if guardar_archivos is not None else True
    MOSTRAR_IMAGEN = mostrar_ventana if mostrar_ventana is not None else True
    
    # Confianza mínima para detecciones (0.0 - 1.0):
    CONFIANZA_MINIMA = confianza_minima if confianza_minima is not None else 0.5
    
    # Filtrado de duplicados:
    IOU_THRESHOLD = iou_threshold if iou_threshold is not None else 0.3
    
    print("--- Cargando YOLO-World (Modelo de Vocabulario Abierto) ---")
    
    # Cargamos el modelo
    try:
        # CAMBIO PRINCIPAL: Apuntamos a tu archivo entrenado
        # Ajusta esta ruta si tu carpeta 'runs' no está justo al lado de este script
        path_modelo = 'runs/detect/train/weights/best.pt'
        
        # Verificación rápida de seguridad
        if not os.path.exists(path_modelo):
            print(f"ERROR CRÍTICO: No encuentro el archivo en: {path_modelo}")
            print("Verifica que estás ejecutando el script desde la carpeta 'src' o ajusta la ruta.")
            sys.exit(1)
            
        model = YOLO(path_modelo)  
    except Exception as e:
        print(f"Error cargando modelo: {e}")
        sys.exit(1)

    # Definimos qué buscar (Clases ya incluidas en best.pt)
    # mis_clases = [
    #     "belt",
    #     "boots", "sneakers", "heels",
    #     "jacket", "dress",
    #     "sunglasses", "hat",
    #     "trousers", "skirt",
    #     "shirt", "top",
    #     "scarf", "tie"
    # ]
    # print(f"Configurando clases: {mis_clases}")
    # model.set_classes(mis_clases)
    # -----------------------------------------------------------------------

    # RUTA BASE
    if ruta_imagen is None:
        #Me estaba dando problemas la ruta y la IA me ha recomendado usar esto qeu define las rutas segun la ubicación de este archivo
        script_dir = os.path.dirname(os.path.abspath(__file__))
        carpeta_base = os.path.join(script_dir, "..", "images")
        carpeta_base = os.path.abspath(carpeta_base)
        #carpeta_base = "../images/"
        #carpeta_base = "/home/ubuntu20/Ubuntu20_ws/src/DeteccionRopa/images"
        #carpeta_base = "/home/ubuntu20/Ubuntu20_ws/src/DeteccionRopa/src/Clothing_Detection_YOLO/tests"

        print(f"\nBuscando en: {carpeta_base}")
        print("Introduce el nombre de la imagen (sin .jpg):")
        
        try:
            nombre = input().strip()
        except EOFError:
            return []

        nombre = "02Dic/" + nombre  
        ruta_imagen = os.path.join(carpeta_base, f"{nombre}.jpg")
    
    if not os.path.exists(ruta_imagen):
        print(f"ERROR: No existe {ruta_imagen}")
        return []

    print(f"Procesando imagen...")

    # PREDICCIÓN
    # Usamos un threshold muy bajo (0.1) para capturar TODAS las detecciones
    # Luego filtraremos manualmente según CONFIANZA_MINIMA
    results_raw = model.predict(source=ruta_imagen, save=False, conf=0.1, imgsz=1280, augment=True, iou=0.5)
    
    # Separar detecciones válidas y descartadas
    r_raw = results_raw[0]
    indices_validos_conf = []
    indices_descartados_conf = []
    
    for idx in range(len(r_raw.boxes)):
        conf = float(r_raw.boxes.conf[idx])
        if conf >= CONFIANZA_MINIMA:
            indices_validos_conf.append(idx)
        else:
            indices_descartados_conf.append(idx)

    # -----------------------------------------------------------
    # FILTRADO DE DUPLICADOS
    # -----------------------------------------------------------
    def calcular_iou(box1, box2):
        """
        Calcula Intersection over Union (IoU) entre dos cajas.
        box: [x1, y1, x2, y2]
        """
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        # Área de intersección
        xi_min = max(x1_min, x2_min)
        yi_min = max(y1_min, y2_min)
        xi_max = min(x1_max, x2_max)
        yi_max = min(y1_max, y2_max)
        
        if xi_max <= xi_min or yi_max <= yi_min:
            return 0.0
        
        area_interseccion = (xi_max - xi_min) * (yi_max - yi_min)
        
        # Áreas individuales
        area_box1 = (x1_max - x1_min) * (y1_max - y1_min)
        area_box2 = (x2_max - x2_min) * (y2_max - y2_min)
        
        # IoU
        area_union = area_box1 + area_box2 - area_interseccion
        return area_interseccion / area_union if area_union > 0 else 0.0
    
    
    def filtrar_duplicados(boxes, clases, confs, nombres_clases, iou_threshold=0.3):
        """
        Elimina detecciones duplicadas de la misma clase que se superponen mucho.
        Excepto para zapatos/tacones que van en pares (permitimos 2 detecciones cercanas).
        
        Considera duplicado si:
        - IoU > threshold, O
        - Centros muy cercanos (< 20% del tamaño de la caja) Y tamaño similar
        """
        # Categorías que van en pares (pueden estar cerca pero no superpuestas)
        categorias_pares = ["boots", "sneakers", "heels", "shoes", "zapatos", "botas"]
        
        indices_a_mantener = []
        duplicados_eliminados = []  # Lista de (índice, nombre, conf, razón)
        n = len(boxes)
        
        print(f"\n[DEBUG] Total de detecciones originales: {n}")
        print(f"[DEBUG] Threshold IoU: {iou_threshold}")
        
        # Convertir a numpy para facilitar el procesamiento
        boxes_list = boxes.cpu().numpy() if hasattr(boxes, 'cpu') else boxes
        clases_list = clases.cpu().numpy() if hasattr(clases, 'cpu') else clases
        confs_list = confs.cpu().numpy() if hasattr(confs, 'cpu') else confs
        
        # Ordenar por confianza descendente (primero procesamos las más confiables)
        indices_ordenados = sorted(range(n), key=lambda i: confs_list[i], reverse=True)
        
        print("\n[DEBUG] Procesando detecciones...")
        for i in indices_ordenados:
            mantener = True
            razon_eliminacion = ""
            clase_i = int(clases_list[i])
            nombre_i = nombres_clases[clase_i]
            box_i = boxes_list[i]
            conf_i = confs_list[i]
            
            # Calcular centro y tamaño de la caja i
            x1_i, y1_i, x2_i, y2_i = box_i
            centro_x_i = (x1_i + x2_i) / 2
            centro_y_i = (y1_i + y2_i) / 2
            ancho_i = x2_i - x1_i
            alto_i = y2_i - y1_i
            area_i = ancho_i * alto_i
            
            # Comprobar si es una categoría de pares
            es_par = any(cat in nombre_i.lower() for cat in categorias_pares)
            
            print(f"\n  Evaluando: {nombre_i} (conf={conf_i:.2f})")
            
            for j in indices_a_mantener:
                clase_j = int(clases_list[j])
                
                # Solo comparar si son de la misma clase
                if clase_i == clase_j:
                    nombre_j = nombres_clases[clase_j]
                    box_j = boxes_list[j]
                    conf_j = confs_list[j]
                    
                    # Calcular IoU
                    iou = calcular_iou(box_i, box_j)
                    
                    # Calcular distancia entre centros
                    x1_j, y1_j, x2_j, y2_j = box_j
                    centro_x_j = (x1_j + x2_j) / 2
                    centro_y_j = (y1_j + y2_j) / 2
                    ancho_j = x2_j - x1_j
                    alto_j = y2_j - y1_j
                    area_j = ancho_j * alto_j
                    
                    import math
                    distancia_centros = math.sqrt((centro_x_i - centro_x_j)**2 + (centro_y_i - centro_y_j)**2)
                    
                    # Distancia relativa al tamaño de la caja
                    tamano_promedio = (max(ancho_i, alto_i) + max(ancho_j, alto_j)) / 2
                    distancia_relativa = distancia_centros / tamano_promedio if tamano_promedio > 0 else 999
                    
                    # Similitud de tamaño
                    ratio_area = min(area_i, area_j) / max(area_i, area_j) if max(area_i, area_j) > 0 else 0
                    
                    # Para pares de zapatos, usar threshold más alto (permitir más solapamiento)
                    threshold_iou = 0.7 if es_par else iou_threshold
                    
                    # Criterio para duplicados:
                    # 1. IoU alto (superpuestos)
                    # 2. O centros muy cercanos (< 30% del tamaño) Y tamaño similar (> 70%)
                    es_duplicado_iou = iou > threshold_iou
                    es_duplicado_cercano = (distancia_relativa < 0.3 and ratio_area > 0.7) and not es_par
                    
                    print(f"    vs {nombre_j} (conf={conf_j:.2f}): IoU={iou:.3f}, dist_rel={distancia_relativa:.3f}, ratio_área={ratio_area:.3f}")
                    
                    if es_duplicado_iou or es_duplicado_cercano:
                        razon_eliminacion = f"Duplicado de {nombre_j} (conf={conf_j:.2f})"
                        if es_duplicado_iou:
                            razon_eliminacion += f" - IoU={iou:.3f}"
                        else:
                            razon_eliminacion += f" - Muy cercano (dist={distancia_relativa:.2f})"
                        print(f"    ❌ DUPLICADO ELIMINADO ({razon_eliminacion})")
                        mantener = False
                        break
            
            if mantener:
                indices_a_mantener.append(i)
                print(f"    ✅ MANTENIDO")
            else:
                duplicados_eliminados.append((i, nombre_i, conf_i, razon_eliminacion))
        
        print(f"\n[DEBUG] Detecciones finales: {len(indices_a_mantener)} de {n}")
        return sorted(indices_a_mantener), duplicados_eliminados
    
    
    
    # -----------------------------------------------------------
    # APLICAR FILTRADO Y VISUALIZACIÓN
    # -----------------------------------------------------------
    
    # Inicializar variable
    indices_validos_duplicados = []
    duplicados_eliminados = []
    
    # Trabajar solo con detecciones que pasaron el filtro de confianza
    if len(indices_validos_conf) > 0:
        r_validos = r_raw.boxes[indices_validos_conf]
        
        # Filtrar duplicados solo entre las detecciones válidas
        indices_validos_duplicados, duplicados_eliminados = filtrar_duplicados(
            r_validos.xyxy, 
            r_validos.cls, 
            r_validos.conf, 
            model.names,
            iou_threshold=IOU_THRESHOLD
        )
        
        # Generar imagen con solo las detecciones filtradas
        if len(indices_validos_duplicados) > 0:
            # Crear copia de resultados con solo las detecciones válidas
            boxes_finales = r_validos[indices_validos_duplicados]
            
            # Crear nuevo objeto Results con las detecciones filtradas
            from copy import deepcopy
            r_filtrado = deepcopy(r_raw)
            r_filtrado.boxes = boxes_finales
            
            # Generar imagen renderizada
            imagen_resultados = r_filtrado.plot()
            
            # Guardar si está configurado (solo con detecciones filtradas)
            if GUARDAR_IMAGENES:
                from pathlib import Path
                
                # Crear directorio de salida
                save_dir = Path("runs/detect")
                save_dir.mkdir(parents=True, exist_ok=True)
                
                # Encontrar el siguiente número de carpeta predict
                existing_dirs = [d for d in save_dir.iterdir() if d.is_dir() and d.name.startswith("predict")]
                if existing_dirs:
                    # Obtener el número más alto
                    nums = []
                    for d in existing_dirs:
                        name = d.name
                        if name == "predict":
                            nums.append(0)
                        elif name.startswith("predict") and name[7:].isdigit():
                            nums.append(int(name[7:]))
                    next_num = max(nums) + 1 if nums else 1
                    output_dir = save_dir / f"predict{next_num}"
                else:
                    output_dir = save_dir / "predict"
                
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Guardar imagen
                output_path = output_dir / Path(ruta_imagen).name
                cv2.imwrite(str(output_path), imagen_resultados)
                print(f"Results saved to {output_dir}")
        else:
            imagen_resultados = r_raw.orig_img
    else:
        imagen_resultados = r_raw.orig_img

    # -----------------------------------------------------------
    # MOSTRAR DETECCIONES DESCARTADAS POR BAJA CONFIANZA
    # -----------------------------------------------------------
    if len(indices_descartados_conf) > 0:
        print(f"\n⚠️  --- OBJETOS DESCARTADOS (confianza < {CONFIANZA_MINIMA:.0%}) ---")
        for idx in indices_descartados_conf:
            clase = int(r_raw.boxes.cls[idx])
            nombre = model.names[clase]
            conf = float(r_raw.boxes.conf[idx])
            print(f"  ❌ {nombre}: {conf:.2f} ({int(conf*100)}%) - Descartado por baja confianza")
        print(f"Total descartados: {len(indices_descartados_conf)}")

    # -----------------------------------------------------------
    # MOSTRAR DUPLICADOS ELIMINADOS
    # -----------------------------------------------------------
    if len(duplicados_eliminados) > 0:
        print(f"\n🔄 --- DUPLICADOS ELIMINADOS ---")
        for idx, nombre, conf, razon in duplicados_eliminados:
            print(f"  🔁 {nombre}: {conf:.2f} ({int(conf*100)}%) - {razon}")
        print(f"Total duplicados eliminados: {len(duplicados_eliminados)}")

    # Imprimir detecciones correctamente (con porcentajes correctos y centro)
    print("\n--- OBJETOS DETECTADOS ---")
    detecciones_con_centro = []  # Lista para guardar (nombre, conf, centro_x, centro_y)
    
    if len(indices_validos_conf) > 0 and len(indices_validos_duplicados) > 0:
        for idx_local in indices_validos_duplicados:
            idx_global = indices_validos_conf[idx_local]
            clase = int(r_raw.boxes.cls[idx_global])
            nombre = model.names[clase]
            conf = float(r_raw.boxes.conf[idx_global])
            
            # Calcular centro y obtener bounding box completa
            box = r_raw.boxes.xyxy[idx_global].cpu().numpy()
            x1, y1, x2, y2 = box
            centro_x = int((x1 + x2) / 2)
            centro_y = int((y1 + y2) / 2)
            
            # Guardar para el reporte (ahora incluye bbox completa)
            detecciones_con_centro.append((nombre, conf, centro_x, centro_y, int(x1), int(y1), int(x2), int(y2)))
            
            print(f"- {nombre}: {conf:.2f} ({int(conf*100)}%) - Centro: ({centro_x}, {centro_y}) px")
        print(f"\nTotal: {len(indices_validos_duplicados)} objetos detectados")
    else:
        print("No se detectaron objetos")

    # -----------------------------------------------------------
    # GUARDAR REPORTE EN ARCHIVO DE TEXTO
    # -----------------------------------------------------------
    if GUARDAR_IMAGENES and 'output_dir' in locals():
        from pathlib import Path
        report_path = output_dir / "detecciones.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("REPORTE DE DETECCIÓN DE ROPA\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Imagen: {Path(ruta_imagen).name}\n")
            f.write(f"Confianza mínima: {CONFIANZA_MINIMA:.0%}\n")
            f.write(f"Threshold IoU duplicados: {IOU_THRESHOLD}\n\n")
            
            # Objetos descartados por baja confianza
            if len(indices_descartados_conf) > 0:
                f.write("⚠️  OBJETOS DESCARTADOS (confianza < {:.0%})\n".format(CONFIANZA_MINIMA))
                f.write("-" * 60 + "\n")
                for idx in indices_descartados_conf:
                    clase = int(r_raw.boxes.cls[idx])
                    nombre = model.names[clase]
                    conf = float(r_raw.boxes.conf[idx])
                    f.write(f"  ❌ {nombre}: {conf:.2f} ({int(conf*100)}%) - Descartado por baja confianza\n")
                f.write(f"\nTotal descartados: {len(indices_descartados_conf)}\n\n")
            else:
                f.write("✅ No hay objetos descartados por baja confianza\n\n")
            
            # Duplicados eliminados
            if len(duplicados_eliminados) > 0:
                f.write("🔄 DUPLICADOS ELIMINADOS\n")
                f.write("-" * 60 + "\n")
                for idx, nombre, conf, razon in duplicados_eliminados:
                    f.write(f"  🔁 {nombre}: {conf:.2f} ({int(conf*100)}%) - {razon}\n")
                f.write(f"\nTotal duplicados eliminados: {len(duplicados_eliminados)}\n\n")
            else:
                f.write("✅ No hay duplicados eliminados\n\n")
            
            # Objetos detectados
            f.write("OBJETOS DETECTADOS\n")
            f.write("-" * 60 + "\n")
            if len(detecciones_con_centro) > 0:
                for item in detecciones_con_centro:
                    # Desempaquetar según el formato (puede tener 4 o 8 elementos)
                    if len(item) == 8:
                        nombre, conf, centro_x, centro_y, x1, y1, x2, y2 = item
                    else:
                        nombre, conf, centro_x, centro_y = item
                    f.write(f"  ✓ {nombre}: {conf:.2f} ({int(conf*100)}%)\n")
                    f.write(f"     Centro: ({centro_x}, {centro_y}) px\n")
                f.write(f"\nTotal detectados: {len(detecciones_con_centro)} objetos\n")
            else:
                f.write("No se detectaron objetos\n")
            
            f.write("\n" + "=" * 60 + "\n")
        
        print(f"\n📄 Reporte guardado en: {report_path}")

    if MOSTRAR_IMAGEN:
        print("\nIntentando abrir ventana gráfica...")
        try:
            # Título de la ventana
            nombre_ventana = "Resultado Deteccion Ropa"
            
            # Redimensionar si la imagen es muy grande para la pantalla
            max_height = 800  # Ajusta según tu resolución de pantalla
            height, width = imagen_resultados.shape[:2]
            if height > max_height:
                aspect_ratio = width / height
                new_height = max_height
                new_width = int(new_height * aspect_ratio)
                imagen_resultados = cv2.resize(imagen_resultados, (new_width, new_height))
            
            # Usar WINDOW_AUTOSIZE en lugar de WINDOW_NORMAL para evitar problemas de redimensionamiento
            cv2.namedWindow(nombre_ventana, cv2.WINDOW_AUTOSIZE)
            
            # Mostrar la imagen
            cv2.imshow(nombre_ventana, imagen_resultados)
            
            print("✅ Ventana abierta. Pulsa cualquier tecla sobre la imagen para cerrar.")
            # Esperar tecla
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            
        except Exception as e:
            # Si falla (común en WSL sin entorno gráfico configurado)
            print("\n⚠️ AVISO: No se pudo abrir la ventana en este terminal.")
            print(f"ERROR TÉCNICO: {e}")
            print("Pero NO PASA NADA. La imagen con los recuadros se ha guardado aquí:")
            print(f"👉 {results[0].save_dir}")
        print("Puedes ir a esa carpeta y abrir el archivo .jpg resultante.")
    
    # Retornar las detecciones para uso externo
    return detecciones_con_centro

if __name__ == "__main__":
    detectar_ropa()