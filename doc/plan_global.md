# Hoja de Ruta Global del TFM: Pick-and-Place de Bolsas Transparentes

Este documento define de manera detallada y extensa la planificación general, los desafíos técnicos, la estrategia de hardware y el plan de desarrollo para el Trabajo de Fin de Máster (TFM) "Robotic Picking Vision".

---

## 🎯 Objetivo General del Proyecto

El objetivo principal de este TFM es diseñar e implementar un sistema de visión artificial robusto y de tiempo real para guiar un brazo robótico industrial en el desembalaje de contenedores de cartón.

El flujo de trabajo es el siguiente:
1.  **Detección de la Zona de Trabajo:** Localizar con precisión la caja de cartón en la escena cenital, determinando sus límites y sus 4 esquinas principales.
2.  **Localización de Bultos:** Detectar la posición en 2D (bounding box y centro geométrico) de bolsas de plástico transparentes que contienen prendas de ropa o calzado apiladas dentro de la caja.
3.  **Extracción Dinámica:** Enviar estas coordenadas de agarre al robot para que extraiga cada bolsa de la caja de forma secuencial y a la máxima velocidad posible, depositándolas ordenadamente en un **Destino B**.

*Simplificación Clave:* No existe clasificación multiclase ni códigos QR. Todas las bolsas son idénticas en la escena y se consideran bajo la clase binaria `bulto` / `bolsa`. El sistema debe centrarse exclusivamente en la velocidad y la tasa de acierto del agarre.

---

## 🔍 Desafíos del Plástico Transparente (Fisica y Óptica)

La detección de objetos transparentes y deformables es uno de los problemas más complejos en Visión por Computador debido a varios factores:

1.  **Ausencia de Textura Interna:** Las bolsas transparentes no poseen un color o patrón visual propio. Las características que el sensor capta provienen directamente del fondo (el color marrón del cartón) o de los objetos que están dentro de la bolsa (ropa de colores variables).
2.  **Reflejos Especulares (Brillos):** La superficie lisa del film plástico (polietileno) actúa como un espejo parcial, reflejando focos de luz e iluminación ambiental. Estos reflejos confunden a los algoritmos convencionales y generan falsos bordes.
3.  **Deformabilidad Extrema:** Las bolsas cambian de forma drásticamente al ser manipuladas, al apilarse unas sobre otras, o al arrugarse. No tienen una forma geométrica canónica o fija.
4.  **Refracción de Luz en Límites:** El principal indicio visual de la presencia del plástico transparente son sus bordes, donde la luz se refracta y genera un contorno fino de alta frecuencia y alto contraste.

---

## 🤖 Estrategia del Gripper y Visión

El acoplamiento entre el sistema de visión y el actuador físico determina los requisitos de precisión:

*   **Uso de Soft Grippers (Pinzas Blandas Deformables):**
    Se propone el uso de actuadores como el **Origami Magic Ball Gripper** o **Dedos Neumáticos (Pneumatic Fingers)**. Estos dispositivos poseen una adaptación mecánica pasiva extrema: al hacer contacto con un objeto deformable irregular (como una bolsa con ropa), la pinza se deforma neumática o mecánicamente para envolver y sellar el agarre.
*   **Impacto en la Visión (Simplificación):**
    Gracias a la tolerancia física del soft gripper, **no es necesario realizar una segmentación 3D precisa o calcular la orientación exacta del film**. La visión no requiere estimar la pose exacta de los pliegues de la bolsa. Es suficiente con:
    1.  Obtener una Bounding Box aproximada del bulto.
    2.  Estimar las coordenadas 2D de su centro geométrico para posicionar el gripper cenitalmente.
    Esto permite usar un pipeline de detección rápida de cajas delimitadoras (YOLO) en lugar de arquitecturas complejas de segmentación de instancias o estimación de pose 6D.

---

## 🗺️ Fases del TFM y Planificación

El proyecto está diseñado para transicionar de técnicas clásicas controladas a Deep Learning robusto:

### Fase 1: Prototipo Basado en Visión Clásica (Estado Actual)
Actualmente, el sistema funciona mediante procesamiento de gradientes y morfología en [src/deteccion_bolsas.py](file:///home/ubuntu22/Ubuntu22humble_ws/src/TFM_pick_place_prendas/tfm-robotic-picking-vision/src/deteccion_bolsas.py):
*   **Bordes Canny:** Para capturar las refracciones del plástico.
*   **Morfología CLOSE:** Para conectar los bordes discontinuos del film plástico y formar un área contigua.
*   **Filtros de Área y Solidez:** Elimina el ruido y descarta contornos irregulares.
*   **Calibrador:** Los scripts de trackbars permiten al usuario sintonizar el pipeline en función de la iluminación.

### Fase 2: Construcción y Anotación del Dataset
*   **Dataset Real:** Se utilizarán las imágenes capturadas en [images/02Dic/](file:///home/ubuntu22/Ubuntu22humble_ws/src/TFM_pick_place_prendas/tfm-robotic-picking-vision/images/02Dic/) (`real1.jpg` a `real6.jpg`) que representan el escenario real de cajas con celdas y celdas sin separadores.
*   **Anotación:** Etiquetado binario delimitando la totalidad de la bolsa plástica visible como clase única `bulto`.

### Fase 3: Entrenamiento YOLOv8s en WSL
*   **Entorno:** Entrenamiento e inferencia local en WSL usando una GPU NVIDIA GeForce GTX.
*   **Estrategia de Robustez:** Dado que el plástico es transparente, se aplicarán aumentos agresivos de datos (`Albumentations`):
    *   *Linear Motion Blur:* Desenfoque de 20-40px para simular movimiento de cinta o cámara.
    *   *Copy-Paste:* Insertar siluetas de bolsas sobre fondos de cajas vacías para generar escenarios sintéticos de apilamiento denso.
*   **Entrenamiento:** Ajuste de hiperparámetros y optimización de curvas de pérdida.

### Fase 4: Optimización Arquitectónica (RGE-YOLO / YOLOv12)
Si YOLOv8s presenta problemas con oclusiones severas o reflejos muy fuertes, se escalará a RGE-YOLO modificando el archivo de configuración `.yaml` para añadir:
*   *EMA (Efficient Multi-Scale Attention):* Para enfocar el aprendizaje en las relaciones espaciales del contorno global en lugar de la textura interna del plástico.
*   *GSConv y RepViT:* Para optimizar el procesamiento de bordes finos de refracción y mantener una alta tasa de FPS en inferencia local.

### Fase 5: Integración Robótica y Control de Trayectorias
*   Publicación de coordenadas y centros de bolsas en ROS 2 Humble.
*   Controlador de agarre secuencial (priorizando el bulto superior u ocluido en menor medida).
*   Movimiento de pick-and-place físico guiado hacia el Destino B.
