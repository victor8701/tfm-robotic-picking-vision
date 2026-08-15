# Arquitectura de Modos de Operación: Inteligencia Visual y Toma de Decisiones

El sistema robótico bimanual propuesto implementa una arquitectura de control dinámico que escala desde la operativa física básica hasta la toma de decisiones basada en inteligencia de mercado en tiempo real.

---

## 1. Módulos de Operación Progresivos

### Modo 1: Vaciado Geométrico (Singulation)
* **Concepto:** Despaletizado y separación de unidades.
* **Justificación:** Procesamiento masivo en logística inversa.
* **Tecnología:** Procesamiento de nubes de puntos (PCL) + YOLO-obb para detección de cajas.

### Modo 2: Clasificación Supervisada (Supervised Sorting)
* **Concepto:** Clasificación por categorías predefinidas (ej. camisetas, zapatos, pantalones).
* **Justificación:** Normalización de flujos de inventario en almacén.
* **Tecnología:** YOLOv8/11 (entrenamiento supervisado).

### Modo 3: Reposición por Demanda Geográfica (Inventory-Driven)
* **Concepto:** Reposición basada en necesidades de stock de mercados específicos (simulado vía JSON cuyos datos se generaran de forma aleatoria).
* **Justificación:** Automatización de la cadena de suministro conectada al ERP.

### Modo 4: Clasificación por Tendencias de Mercado (Trend-Driven Fulfillment)
* **Concepto:** El sistema actúa como un **Agente de Inteligencia de Mercado**. Ante la orden de un país (ej. "Reino Unido"), el sistema consulta dinámicamente qué es tendencia.
* **Análisis de Tendencias:** El sistema no solo consulta datos históricos, sino que analiza fuentes de influencia actual:
  * **Influencers y Cantantes:** Monitorización de etiquetas y menciones en redes sociales.
  * **Eventos y Viralidad:** Análisis de hashtags en X (Twitter) sobre moda urbana.
  * **Base de Influencia:** Procesamiento de tendencias en tiempo real para extraer atributos (ej. "estética retro", "colores neon").
* **IA/Visión:** **Modelos Multimodales (CLIP / Grounding DINO)**. El sistema traduce las tendencias extraídas en consultas vectoriales para identificar prendas en el inventario que cumplan con dicho "espíritu" de moda.

### Modo 5: Gestión Integral (3 + 4)
* **Concepto:** Optimización multiobjetivo. El sistema debe reponer stock en un país (Modo 3) priorizando los artículos que mejor encajan con la moda detectada en ese mercado (Modo 4).

---

## 2. Investigación: El Análisis de Tendencias como Fuente de Datos

Para validar el Modo 4, tu TFM debe demostrar cómo los datos no estructurados de internet se convierten en órdenes de trabajo para el robot. El enfoque de investigación se divide en tres capas:

### Capa A: Ingesta y Análisis (Market Intelligence Pipeline)
En lugar de una API real compleja, diseña un **"Trend Ingestor"** que procese fuentes como:
* **Social Media Monitoring (Simulado):** Un script que analiza menciones de términos clave asociados a figuras (influencers/futbolistas) y eventos.
* **Extracción de Atributos:** El sistema extrae *tags* de moda (ej. "oversize", "urbano", "minimalista") de estas fuentes.

### Capa B: Vectorización Semántica (El "Match")
Aquí reside la carga investigadora de tu TFM:
* Utilizarás **CLIP (OpenAI)** para crear un "espacio semántico compartido".
* El texto (tendencia extraída de redes) y la imagen (prenda detectada por YOLO) se convierten en vectores en el mismo espacio. 
* **La métrica de éxito:** La distancia coseno entre el vector de tendencia (influencers de UK) y el vector de la prenda determina la probabilidad de que esa prenda sea la correcta para el pedido.

### Capa C: Ejecución Robótica (Realización Física)
El sistema finalmente traslada el resultado de la IA a coordenadas (X, Y, Z) para que los cobots ABB GoFa ejecuten el *picking* bimanual, garantizando que el pedido preparado no solo es correcto por tipo, sino por **tendencia de mercado**.

---

## Cuadro Resumen: Escalamiento Industrial

| Modo | Objetivo Industrial | Fuente de Datos | Complejidad de IA |
| :--- | :--- | :--- | :--- |
| **1. Vaciado** | *Singulation* | Geometría 3D | Baja |
| **2. Sorting** | Clasificación fija | Dataset Supervisado | Media |
| **3. Stock** | Reposición geográfica | JSON (ERP Simulado) | Alta |
| **4. Trend** | **Inteligencia de Moda** | **Influencers/Social Media** | **Muy Alta** |
| **5. Gestión** | Planta Inteligente | Híbrido (ERP + Tendencias) | Máxima |



---

### Nota para la Memoria de Investigación
Tu TFM se justifica como investigación porque **cierra el bucle** entre:
1.  **IT (Marketing/Tendencias):** Qué quieren los usuarios hoy.
2.  **Middleware (ROS 2):** Cómo transformar esa moda en comandos de visión.
3.  **OT (Robots GoFa):** Cómo ejecutar físicamente la preparación de ese pedido tendencia.

Este enfoque no solo demuestra que sabes programar robots, sino que entiendes cómo la robótica colaborativa moderna debe **adaptarse a las fluctuaciones del mercado global** en tiempo real.