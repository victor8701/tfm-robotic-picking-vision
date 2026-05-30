# tfm-robotic-picking-vision

Este repositorio contiene el sistema de visión cenital para la detección de esquinas de caja y localización de bolsas de plástico transparentes para pick-and-place robótico en el TFM.

---

## 🗺️ Mapa de Navegación Inicial para la IA

Cuando inicies una nueva sesión, debes abrir y leer los siguientes archivos en orden para comprender el estado del proyecto y las instrucciones activas:

1.  **[input.md](input.md)** (Raíz)
    *   *Propósito:* Canal de instrucciones activo del usuario para la sesión y reglas de desarrollo permanentes. **Es tu punto de entrada principal para saber qué hacer.** Contiene el protocolo `"me voy"` de cierre y el handover entre IAs.
2.  **[doc_2026-05-30/feedback.md](doc_2026-05-30/feedback.md)** (Carpeta Activa)
    *   *Propósito:* Reporte de estado dinámico que registra el progreso actual, tareas y posibles bloqueos. Debes actualizarlo al final de cada turno.
3.  **[doc_2026-05-30/implementation_plan.md](doc_2026-05-30/implementation_plan.md)** (Carpeta Activa)
    *   *Propósito:* Plan técnico detallado a corto plazo para el sprint o hito de desarrollo actual.
4.  **[doc_2026-05-30/plan_global.md](doc_2026-05-30/plan_global.md)** (Carpeta Activa)
    *   *Propósito:* Hoja de ruta extendida del TFM a largo plazo, detallando el objetivo del picking, los retos del plástico arrugado y la estrategia de agarres pasivos.
5.  **[solucion_deteccion_bolsas_plasticas.md](solucion_deteccion_bolsas_plasticas.md)** (Raíz)
    *   *Propósito:* Documento técnico de diseño que detalla la propuesta e investigación para migrar de visión clásica a YOLO (Deep Learning) en la detección de bolsas. Incluye el catálogo y descripción detallada de todas las imágenes reales.
6.  **[doc_2026-05-30/bitacora_desarrollo.md](doc_2026-05-30/bitacora_desarrollo.md)** (Carpeta Activa)
    *   *Propósito:* Diario cronológico de cambios de código estructurado en una tabla compacta para ahorrar tokens. Debe modificarse ante cualquier cambio y revisarse al finalizar para marcar metas instantáneas.

---

## 📁 Estructura del Repositorio

A continuación se detalla la estructura física del proyecto con enlaces directos para acceder a cada recurso:

### Documentación Histórica (Snapshots)
*   **[doc/](doc/)**: Directorio que almacena el snapshot maestro e inmutable de la documentación, actualizado únicamente por la IA al cerrar sesión.
    *   [doc/implementation_plan.md](doc/implementation_plan.md)
    *   [doc/plan_global.md](doc/plan_global.md)
    *   [doc/feedback.md](doc/feedback.md)
    *   [doc/bitacora_desarrollo.md](doc/bitacora_desarrollo.md)

### Código Fuente del Pipeline (`src/`)
*   **[src/main.py](src/main.py)**: Script principal orquestador del pipeline.
*   **[src/deteccion_esquinas.py](src/deteccion_esquinas.py)**: Módulo de segmentación de caja HSV y detección de esquinas por HoughLinesP.
*   **[src/deteccion_bolsas.py](src/deteccion_bolsas.py)**: Módulo de localización de bolsas plásticas por visión clásica (Canny, Close, Contornos).
*   **[src/ajuste_parametros_esquinas.py](src/ajuste_parametros_esquinas.py)**: Interfaz OpenCV de calibración para la caja de cartón.
*   **[src/ajuste_parametros_bolsas.py](src/ajuste_parametros_bolsas.py)**: Interfaz OpenCV de calibración para las bolsas.
*   **[src/debug_detection.py](src/debug_detection.py)**: Pruebas rápidas de máscaras de depuración.
*   **[src/config_esquinas.json](src/config_esquinas.json)**: Archivo de parámetros guardado de la caja.
*   **[src/config_bolsas.json](src/config_bolsas.json)**: Archivo de parámetros guardado de las bolsas.

### Datasets e Historial de Código
*   **[images/02Dic/](images/02Dic/)**: Contiene las imágenes reales de prueba y dataset (`real1.jpg` a `real6.jpg`).
*   **[proyecto_VC/deteccion_ropa.py](proyecto_VC/deteccion_ropa.py)**: Código de referencia del antiguo modelo YOLOv8 de ropa.

---

## 🚀 Cómo Ejecutar

> Todos los comandos se ejecutan desde la carpeta **`src/`** salvo que se indique lo contrario.

### Pipeline principal
Procesa una imagen (o varias en bucle interactivo). Pasa el nombre sin extensión como argumento, o déjalo vacío para el modo interactivo.

```bash
cd src
python3 main.py          # modo interactivo: pide el nombre de imagen por teclado
python3 main.py real1    # procesa images/02Dic/real1.jpg directamente
```

### Calibración de parámetros — caja de cartón
Abre una ventana OpenCV con sliders para ajustar los parámetros HSV y Hough. Al cerrar, guarda `src/config_esquinas.json`.

```bash
cd src
python3 ajuste_parametros_esquinas.py real1
```

### Calibración de parámetros — bolsas de plástico
Igual que el anterior pero para los parámetros Canny/morfológicos. Guarda `src/config_bolsas.json`.

```bash
cd src
python3 ajuste_parametros_bolsas.py real1
```

### Debug de máscaras
Ejecuta detección sobre `real1`, `real3` y `real4` y vuelca imágenes de depuración (`debug_<img>_mask_caja.jpg`, `debug_<img>_result.jpg`) en la raíz del proyecto. Necesita los `.json` de config ya generados.

```bash
# Desde la raíz del proyecto (no desde src/)
python3 src/debug_detection.py
```
