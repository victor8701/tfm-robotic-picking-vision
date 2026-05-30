# Solución Técnica: Adaptación del Sistema para Detección Binaria de Bolsas de Plástico Transparentes

**Autor:** Víctor Martín Parra 
**Entorno de Trabajo:** Windows + WSL (Ubuntu) + GPU NVIDIA GeForce GTX  

---

## 📋 Resumen Ejecutivo

Este documento proporciona la **propuesta técnica y de diseño** para adaptar el sistema anterior de detección de prendas a la **detección binaria de bolsas de plástico transparentes** ("bultos") apiladas.

**Objetivo de Picking:** El brazo robótico debe extraer las bolsas transparentes (todas idénticas y conteniendo objetos) de la caja de cartón lo más rápido posible y apilarlas en un **Destino B**. No se requiere separar bolsas por categorías ni realizar lecturas de códigos QR.

**Desafíos específicos:**
*   Transparencia y reflejos especulares.
*   Deformabilidad del film plástico al agarrar.
*   Apilamientos caóticos con oclusiones parciales.
*   Ausencia de textura visual.

---

## 1. Análisis del Entorno y Código Actual

### 1.1 El Dataset de Imágenes Reales (Análisis Visual)
Las imágenes reales en `images/02Dic/` representan las condiciones visuales a resolver:

| Imagen | Nombre de Fichero | Descripción de la Escena |
| :--- | :--- | :--- |
| **real1** | `real1.jpg` | Caja abierta vista desde arriba. **Bolsas pequeñas de plástico transparente muy arrugadas**, sin separadores, apiladas de forma caótica. Contiene electrónica/cables. |
| **real2** | `real2.jpg` | Caja cerrada y sellada con cinta. Vista exterior (no apta para picking). |
| **real3** | `real3.jpg` | Caja con **separadores de cartón** y **bolsas individuales en cada celda** (10-12 celdas). Contiene calzado. Vista cenital del robot. |
| **real4** | `real4.jpg` | **Primer plano** de bolsas transparentes. Bordes del plástico muy nítidos donde se aprecia la arruga característica del polietileno. |
| **real5** | `real5.jpg` | 3 bolsas sobre una superficie estriada metálica. Bolsas con calzado. Pliegues irregulares pero límites de bolsa definidos. |
| **real6** | `real6.jpg` | Caja con separadores, bolsas medianas translúcidas por celda. Cámara cenital. |

### 1.2 Componentes de Software Existentes
*   **`deteccion_bolsas.py`:** Actualmente ejecuta la detección de bolsas utilizando un pipeline de **CV Clásico** (Grayscale + GaussianBlur → Canny → MORPH_CLOSE → Bitwise AND con máscara de caja → findContours → Filtros de área y solidez).
*   **`deteccion_esquinas.py`:** Segmenta la caja mediante su color marrón (HSV) y detecta sus esquinas calculando las intersecciones de las líneas de borde obtenidas mediante la transformada de Hough (`HoughLinesP`).
*   **`main.py`:** Orquestador del pipeline completo que dibuja las esquinas (rojo) y las bboxes de las bolsas (azul) con su centro de agarre (verde).

---

## 2. Estrategia de Adaptación Recomendada (Deep Learning)

### 2.1 Modelo Base: YOLOv8s en WSL
Dado que el entorno de desarrollo cuenta con una tarjeta gráfica dedicada **NVIDIA GeForce GTX** bajo **WSL**, se recomienda entrenar un modelo **YOLOv8s** (versión Small) como baseline de Deep Learning.
*   **Ventaja:** YOLOv8s tiene solo 11.2M de parámetros, es rápido de entrenar en GPUs locales de gama media y ofrece una robustez muy superior al CV clásico frente a reflejos del plástico y oclusiones parciales.
*   **Clase Única:** El modelo se entrenará para una clase binaria única: `bulto` (que engloba a la bolsa de plástico completa).

### 2.2 Alternativa Avanzada: RGE-YOLO
Si el baseline de YOLOv8s estándar presenta problemas para detectar bolsas excesivamente arrugadas o superpuestas, se propone modificar la arquitectura a **RGE-YOLO** mediante cambios en el archivo `.yaml` de configuración:
1.  **Bloques RepViT:** Reemplazar bloques C2f en el backbone para aligerar parámetros.
2.  **Atención EMA (Efficient Multi-Scale Attention):** Añadir atención espacial global al final del backbone para capturar la forma global en lugar del color/textura.
3.  **GSConv:** Reemplazar convolutions del neck para preservar mejor la información de bordes sutiles en la transparencia.

---

## 3. Pipeline de Preprocesamiento y Augmentation

### 3.1 Preprocesamiento en Inferencia
Dado que las bolsas transparentes carecen de textura de color propia (reflejan el fondo y la iluminación), se aconseja convertir el frame RGB a escala de grises y después replicarlo a 3 canales antes de pasarlo al modelo de Deep Learning. Esto enseña al modelo a enfocarse exclusivamente en las formas y bordes de refracción.

```python
def preprocesar_para_yolo(imagen_bgr):
    gray = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2GRAY)
    imagen_procesada = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    return imagen_procesada
```

### 3.2 Data Augmentation para Película Plástica (Albumentations)
Para simular el movimiento de la cinta y el brillo del plástico arrugado, el pipeline de entrenamiento debe incluir:
*   **Linear Motion Blur (Desenfoque de movimiento):** Simula el movimiento de la cámara o la cinta transportadora (kernel 20-40px, `p=0.5`).
*   **Simulación de reflejos especulares:** Brillos aleatorios que el modelo debe aprender a ignorar.
*   **Copy-Paste sintético:** Permite pegar bolsas en posiciones aleatorias de la caja simulando apilamientos (IoU threshold < 0.1).

---

## 4. Cambios de Código para la Integración

### 4.1 Modificar Inferencia
El archivo `deteccion_bolsas_yolo.py` cargará el modelo entrenado binario y realizará las predicciones sin lógica de ordenación por QR:

```python
from ultralytics import YOLO

def detectar_bolsas_yolo(imagen_bgr, path_modelo='runs/detect/weights/best.pt', conf_min=0.25):
    model = YOLO(path_modelo)
    imagen_prep = preprocesar_para_yolo(imagen_bgr)
    results = model.predict(source=imagen_prep, conf=conf_min, imgsz=1280, augment=True)
    
    bolsas = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = box.conf[0].cpu().numpy()
            cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
            bolsas.append({"cx": cx, "cy": cy, "x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2), "conf": float(conf)})
    return bolsas
```

### 4.2 Orquestador Simplificado
`main.py` integrará la llamada seleccionando la caja con Hough y enviando las coordenadas directas del centro de cada bolsa al robot (Destino B), omitiendo filtrados espaciales complejos.
