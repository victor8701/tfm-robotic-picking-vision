# Plan: Detección de Bolsas de Plástico con Prendas en su Interior

## Análisis Visual de las Imágenes Reales (`images/real1`–`real6`)

Antes de definir la estrategia, conviene entender exactamente qué ve la cámara:

| Imagen | Descripción observada |
|---|---|
| `real1` | Caja abierta vista desde arriba. **Bolsas pequeñas de plástico transparente muy arrugadas**, sin separadores, apiladas de forma caótica. Objetos dentro: electrónica/cables. |
| `real2` | Caja cerrada y sellada con cinta. Vista exterior. |
| `real3` | Caja con **separadores de cartón** y **bolsas individuales en cada celda** (10–12 celdas). Calzado dentro. Vista cenital del robot. |
| `real4` | **Primer plano** de bolsas transparentes. Bordes del plástico muy nítidos. Se ve claramente la arruga característica del polietileno. |
| `real5` | 3 bolsas sobre superficie estriada metálica. Bolsas con calzado. Pliegues irregulares pero bordes definidos. |
| `real6` | Caja con separadores, bolsas medianas translúcidas por celda. Cámara cenital. |

**Conclusiones clave:**
- Las bolsas son **siempre transparentes** y **del mismo tamaño y contenido** por tipo de caja.
- El entorno es **muy controlado**: cámara cenital fija, fondo constante (caja de cartón marrón).
- Las bolsas tienen **bordes nítidos del plástico** visibles claramente en las imágenes.
- A veces hay **separadores de cartón** entre bolsas que pueden usarse como referencia espacial.

---

## Contexto del Proyecto

El sistema actual (branch `plastico_transparente`) detecta **esquinas de la caja** usando:
- `deteccion_esquinas.py` → máscara HSV color cartón + HoughLinesP + intersección de líneas ✅ *Se mantiene sin cambios*
- `main.py` → orquestador que carga parámetros desde `config_esquinas.json`

El fichero `deteccion_ropa.py` del branch `proyecto_VC` se usó **solo como referencia** para entender la arquitectura anterior. No se integra en el sistema nuevo.

**Nuevo objetivo:** Añadir un módulo que detecte las **bolsas de plástico** en la imagen (su posición y bounding box) para que el robot sepa dónde agarrar.

---

## ¿Hay que usar YOLO?

> [!IMPORTANT]
> **Respuesta: NO en la Fase 1.** Este es el punto más crítico del plan revisado.

El sistema anterior necesitaba YOLO porque el problema era de **clasificación multi-clase** (distinguir 14 tipos de prendas). Ese es un problema genuinamente difícil para CV clásico.

El nuevo problema es **fundamentalmente diferente**:
- Solo hay **1 tipo de objeto** a detectar (bolsa de plástico)
- El entorno es **muy controlado** (cámara fija, fondo de cartón uniforme)
- Las bolsas son visibles gracias a sus **bordes nítidos** (el plástico refracta la luz)
- Siempre son **del mismo tamaño y forma aproximada** por tipo de caja

Esto es exactamente el tipo de problema que CV clásico resuelve bien:
```
Canny (detecta bordes del plástico)
  → Morfología CLOSE (cierra los bordes discontinuos del film)
  → findContours (encuentra cada bolsa como contorno cerrado)
  → Filtrar por área y solidez (elimina ruido del fondo)
  → BBox de cada bolsa → Centro para el robot
```

| Estrategia | Pros | Contras |
|---|---|---|
| **CV Clásico** (Fase 1) | Sin dataset, sin GPU, funciona hoy mismo, ajustable con sliders | Menos robusto a cambios de iluminación extremos |
| **YOLO** (Fase 2, opcional) | Más robusto, manejará oclusiones complejas | Requiere anotar ~200+ imágenes + GPU (Kaggle o alquiler) |

**Estrategia:** CV clásico primero con las imágenes disponibles. Si los resultados son buenos en las fotos reales que se tomen, YOLO no es necesario. Si hay casos difíciles que CV no resuelve, se pasa a Fase 2.

---

## Proposed Changes

---

### Fase 1 — Prototipo CV Clásico (sin YOLO, sin dataset)

#### [NEW] `src/deteccion_bolsas_cv.py`

Módulo principal de la Fase 1. Pipeline completo basado en Canny + morfología:

```python
def preprocesar(imagen_bgr):
    """
    Grayscale + GaussianBlur suave para reducir reflejos especulares del plástico.
    No usar blur fuerte: perdería los bordes finos del film.
    """

def detectar_bolsas_cv(ruta_imagen, params=None, mostrar_ventana=True):
    """
    Pipeline:
      1. Cargar imagen
      2. Grayscale + GaussianBlur(3,3)
      3. Canny(low, high) → bordes del plástico
      4. MORPH_CLOSE con kernel grande → cierra bordes del film (son discontinuos)
      5. findContours en máscara MORPH_CLOSE
      6. Filtrar contornos por:
           - área mínima y máxima (elimina ruido y el fondo completo)
           - solidez > 0.5 (bolsas son convexas aproximadamente)
      7. Para cada contorno válido → calcular bbox + centro
      8. Retornar lista de (cx, cy, x1, y1, x2, y2)
    """
```

**Parámetros configurables** en `config_bolsas.json`:

```json
{
  "canny_low": 30,
  "canny_high": 90,
  "blur_kernel": 3,
  "morph_close_kernel": 15,
  "morph_iterations": 3,
  "area_min": 5000,
  "area_max": 500000,
  "solidez_min": 0.5
}
```

> [!NOTE]
> Los separadores de cartón entre bolsas (visibles en real3 y real6) actúan como delimitadores naturales. Si la caja siempre tiene separadores, podría filtrarse por el ROI de cada celda. Esto se decide al ver los resultados con las fotos reales.

---

#### [NEW] `src/config_bolsas.json`

Fichero de configuración análogo al `config_esquinas.json` existente. Permite cambiar parámetros sin tocar código.

---

#### [NEW] `src/ajuste_bolsas.py`

Script de ajuste de parámetros **exclusivo para bolsas**. `ajuste_parametros.py` **no se toca** — es específico de esquinas y funciona bien.

`ajuste_bolsas.py` sigue el mismo patrón: sliders en ventana OpenCV → resultado en tiempo real → `'s'` para guardar en `config_bolsas.json`, `'i'` para cambiar imagen.

---

#### [MODIFY] `src/main.py`

Integrar la detección de bolsas en el pipeline junto con las esquinas:

```python
from deteccion_bolsas_cv import detectar_bolsas_cv  # Fase 1
from deteccion_esquinas import charge_image          # Sin cambios

def procesar_imagen(nombre_imagen):
    ruta = _resolver_ruta(nombre_imagen)

    # Paso 1: Esquinas de la caja (sin cambios)
    _, esquinas, _ = charge_image(ruta_imagen=ruta, params=params_esquinas, ...)

    # Paso 2: Detectar bolsas de plástico
    bolsas = detectar_bolsas_cv(ruta, params=params_bolsas)

    # Paso 3 (opcional): Filtrar bolsas dentro del área de la caja
    bolsas_en_caja = filtrar_por_roi_caja(bolsas, esquinas)

    # Paso 4: Visualización combinada
    #   - Esquinas de caja: círculos rojos (ya implementado)
    #   - BBox de cada bolsa: rectángulo azul + centro verde
    #   - Etiqueta: "Bolsa N"
```

---

### Fase 2 — YOLO (solo si CV clásico no es suficiente)

> [!NOTE]
> Esta fase es **opcional y condicional**. Solo se ejecuta si la Fase 1 presenta fallos frecuentes en las fotos reales (falsos positivos por reflejos, bolsas muy aplastadas, etc.).

#### Condición de activación
Si CV clásico tiene una tasa de detección correcta < 85% en las fotos reales.

#### Dataset
- Fotografiar las bolsas en distintas condiciones (en caja, fuera, con/sin separadores)
- **Mínimo ~100 imágenes** para baseline; ~300 para resultado robusto
- Anotar con **LabelImg** o **Roboflow** — clase única: `bolsa`
- Dividir: 70% train / 20% val / 10% test

#### GPU
- **Kaggle Notebooks** (gratis, 30h/semana de GPU P100)
- O **alquiler de GPU por horas** (vast.ai, Lambda Labs: ~0.30–0.50 $/h para RTX 3090)

#### Modelo base
- **YOLOv8s** como baseline — no RGE-YOLO aún (añade complejidad innecesaria si el dataset es pequeño)
- Si mAP < 75% con YOLOv8s, entonces considerar RGE-YOLO (ver `solucion_deteccion_bolsas_plasticas.md` sección 2.2)

#### [NEW] `src/deteccion_bolsas.py` (Fase 2)

```python
def detectar_bolsas(ruta_imagen, conf_min=0.25, mostrar_ventana=True):
    """
    Detecta bolsas usando YOLO entrenado (clase única: 'bolsa').
    Parámetros: conf=0.25, imgsz=1280, augment=True, iou=0.45
    Retorna: [(cx, cy, x1, y1, x2, y2, conf), ...]
    """
```

`main.py` se actualiza para importar de `deteccion_bolsas` en lugar de `deteccion_bolsas_cv` cuando el modelo entrenado esté disponible.

---

## Módulos que NO cambian

| Módulo | Estado |
|---|---|
| `deteccion_esquinas.py` | ✅ Se mantiene exactamente como está |
| `config_esquinas.json` | ✅ Sin cambios |
| `ajuste_parametros.py` | ✅ Sin cambios — exclusivo de esquinas |
| `deteccion_ropa.py` (proyecto_VC) | 📄 Solo referencia histórica, no se integra |

---

## Orden de Ejecución

```
━━━ FASE 1: CV Clásico (sin fotos nuevas, sin GPU) ━━━━━━━━━
[1] Implementar deteccion_bolsas_cv.py
[2] Crear config_bolsas.json con valores iniciales
[3] Añadir modo bolsas a ajuste_parametros.py
[4] Integrar en main.py (esquinas + bolsas)
[5] Probar con real1–real6 y ajustar parámetros

━━━ FOTO-SESIÓN (pendiente) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[6] Fotografiar cajas con bolsas en distintas condiciones
[7] Probar Fase 1 sobre nuevas fotos → evaluar robustez
    → Si OK: el trabajo está terminado
    → Si falla: continuar con Fase 2

━━━ FASE 2: YOLO (solo si CV no es suficiente) ━━━━━━━━━━━━
[8] Anotar imágenes con LabelImg/Roboflow
[9] Entrenar YOLOv8s en Kaggle/GPU alquilada
[10] Implementar deteccion_bolsas.py
[11] Sustituir deteccion_bolsas_cv en main.py
```

---

## Verification Plan

### Fase 1 (CV Clásico)
- `python3 src/deteccion_bolsas_cv.py` con `real1`–`real6`
- Verificar visualmente que los bboxes encuadran cada bolsa
- Ajustar `canny_low`, `canny_high`, `morph_close_kernel` con sliders hasta resultado estable
- **Criterio de éxito:** ≥ 90% de bolsas detectadas sin falsos positivos evidentes

### Integración con esquinas
- `python3 src/main.py` → imagen con caja + bolsas
- Verificar que se dibujan esquinas de caja (rojo) + bboxes de bolsas (azul)
- El centro de cada bolsa debe estar dentro del área delimitada por las esquinas

### Fase 2 (YOLO, si aplica)
- mAP@0.5 ≥ 75% baseline / ≥ 85% objetivo
- Precision ≥ 80%, Recall ≥ 75%
- Evaluar en conjunto de test nunca visto
