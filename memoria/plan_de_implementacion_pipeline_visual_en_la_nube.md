# Plan de Implementación: Pipeline Visual en la Nube (Opción B)

**Documento de Referencia:** `TFM_briefing_opcion_B.md`
**Objetivo:** Resolver la baja precisión de la recogida de imágenes (17%) mediante un pipeline de filtrado visual 100% en la nube (coste 0$), y definir el protocolo de evaluación a ciegas para el Experimento B.

---

## 1. Descripción del Problema

El sistema actual de ingesta de tendencias sufre de un fallo estructural grave: **el filtro de texto es ciego a la imagen**. 
*   Las búsquedas programadas en X mediante Tavily devuelven imágenes que coinciden en texto (ej. "outfit"), pero visualmente son "basura" (arte anime, renders 3D, mapas del tiempo), desplomando la precisión al 17%.
*   El límite estricto de Tavily (≤20 resultados por consulta) provoca un rápido agotamiento del inventario relevante al usar consultas estáticas repetidas a diario.
*   El hardware local (WSL2, CPU, sin CUDA) impide correr Modelos de Lenguaje Visual (VLMs) para filtrar esta basura en tiempos razonables.

## 2. Descripción de la Solución: "Cloud Visual Pipeline"

La solución consiste en desacoplar la recolección de URLs del filtrado de imágenes, trasladando la carga computacional pesada a la nube gratuita (Kaggle) para no bloquear la ruta crítica del TFM local (ROS 2 / EGM).

El sistema se divide en tres fases automatizadas:
1.  **Recolección Desatendida (GitHub Actions):** Se expanden las consultas mediante LLM y se dirigen a dominios de alta confianza (cuentas específicas de X, Subreddits de moda). Solo se guardan las URLs en bruto en un archivo JSON.
2.  **Cerebro Visual (Kaggle Scheduled Notebook):** Un cron job en Kaggle lee las URLs. Aplica un filtro rápido local de CLIP (umbral 0.7) para descartar el 70% de la basura geométrica al instante. Las imágenes dudosas pasan por un VLM (ej. Qwen2.5-VL) acelerado por las GPUs T4 gratuitas de Kaggle para una decisión final binaria ("¿Es una foto real de una persona con ropa?").
3.  **Galería y Evaluación (Render / Local):** El JSON limpio se envía de vuelta al repo. Víctor valida el Top-N en la galería táctil, y se procede al "Experimento B" evaluando la similitud coseno de los centroides visuales contra el inventario mediante un sistema de agrupamiento (*Pooling*) a ciegas.

## 3. Esquema de Arquitectura

![Esquema de Arquitectura](https://kroki.io/mermaid/svg/eNp9ks1O20AQx-88xYhDBQdHEFRVyoGKJCQQnJCSkEMtVE3Wk2TL4nF3vdACfYQ-BA_Aqbde_WKdbD5Rpfpie_T_zdd_JoYf1AxtAcPmDsjj_HhqMZ_BBB0dQrLbkjcc1uCKFBtSSpe_M9hr6-LMj-FEFZozt797E-D5c5I0LGfQ4TE0NVrNNxBFx1BPTr_nmLmApwQNwbwp0EEcdzd0PYgbSb384755ShGGeK_ND6AMBlqKuSU80Zg94gZsBLCZtD3aFC1cX8VuDinMUp1iwe6Lsj5lV_nqOFtwlKU7_w5dXQ1drUGDLI0tw0g7jwb2LnA6NVLfsE8hgnb_env002SgZpR6Qyn0uKAx8-2bJbSSJjmFdrpqcN4Suk2GVpC1n1raFFL2qnzJdcrSR3zeh89kORrMuIBjOKh8-PhzjbUFk4oBPlvWKNDevBUMytegOH_qeHqEUdytwacHyqqV99Eo3mQ7X4h_BXEnEY9ldv0oPSuDTk-0QiWu0_Yq11zvctHFOtoJ_xeJXAz0vZuB7NFSzk4XLIuB-_JVTOZb-q8pRytTjmowbHUhZiV53slVZinZLQ_i5CTPl2FooyEb8pcvcqlm4UJ3b1S-KqkOmFtPY4SCczg8iKoH--s83SDtJY3yxShvOJwdZeKKlq_lPQytvrsTs7uEW3voBfRyfvAkAoEY6jXoMxudTQFBaZquXF-P24SoEh0_x0TQGVz2nuE0hC8W4bUJzxD_Bc97HBQ=)

## 4. Plan de Implementación Detallado

**Presupuesto de tiempo:** ~14 horas (encaja en el límite de ~16h sin comprometer la ruta crítica de Octubre).
**Restricciones:** $0 de gasto, herramientas de pesos abiertos.

### Paso 1: Modificación del flujo de Ingesta (GitHub Actions)
*   **Horas estimadas:** 2h
*   **Acciones:** 
    *   Modificar `.github/workflows/ingesta_x.yml`.
    *   Cambiar los  *strings*  estáticos de `textos_busqueda.py` por búsquedas restringidas con operadores (ej. `site:reddit.com/r/streetwear` o cuentas de X curadas).
    *   Evitar la descarga de imágenes en esta fase; el script solo debe poblar `candidatos_crudos.json`.
*   **Criterio de éxito:** El Action corre sin errores y el JSON se llena de URLs candidatas sin consumir almacenamiento excesivo.

### Paso 2: Desarrollo del "Cerebro Visual" en Kaggle
*   **Horas estimadas:** 5h
*   **Acciones:**
    *   Crear un *Kaggle Notebook* con acceso a Internet y GPU T4 x2.
    *   Escribir script para leer `candidatos_crudos.json` del repo público.
    *   Implementar inferencia de CLIP localmente en el notebook (umbral 0.7).
    *   Implementar inferencia de Qwen2.5-VL (o Llava) en HuggingFace Transformers para los casos dudosos.
    *   Configurar el volcado de resultados a `clasificaciones.json` y el uso de un Personal Access Token (PAT) de GitHub para hacer el *commit* de vuelta.
*   **Criterio de éxito:** El Notebook se ejecuta de principio a fin, filtra el ruido visual de manera efectiva (>75% precisión) y actualiza el repo automáticamente.

### Paso 3: Interfaz de Validación (Render) y Extracción de Vectores
*   **Horas estimadas:** 2h
*   **Acciones:**
    *   Asegurar que la app Flask en Render lee el nuevo formato de JSON limpio.
    *   Desarrollar un pequeño script local que tome las 10 fotos aprobadas por estilo y calcule la **Media Recortada (Trimmed Mean)** de los embeddings CLIP (descartando el 20% más alejado del centroide inicial para dar robustez frente a contaminación).
*   **Criterio de éxito:** Generación exitosa de los 7 vectores de tendencia visuales (1 por cada sub-estilo).

### Paso 4: Experimento B (Evaluación a Ciegas mediante Pooling)
*   **Horas estimadas:** 5h
*   **Acciones:**
    *   Generar los textos de búsqueda de línea base con un LLM ciego (sin mencionarle la taxonomía interna de 7 estilos).
    *   Correr el *catalog matching* sobre las 1.200 fotos de Kaggle para 3 métodos: Vector Texto, Vector Visual, y Fusión (α=0.5).
    *   Programar una interfaz de terminal simple que agrupe y desordene el Top-5 de los tres métodos (método *Pooling*).
    *   Víctor evalúa a ciegas (0=Mal, 1=Regular, 2=Bien).
    *   El script calcula automáticamente P@5 y NDCG@5.
*   **Criterio de éxito / Parada:** Obtención de la tabla comparativa final. Si la fusión no supera al texto por ≥ 5 pp de manera consistente, se documenta como resultado neutro en la memoria y se cierra la vía investigadora visual para centrarse en los brazos robóticos.