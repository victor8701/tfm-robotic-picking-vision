# 📦 DeteccionRopa - Sistema de Visión por Computador

**Sistema de detección de prendas y esquinas de contenedores usando YOLO y procesamiento de imagen.**

<div align="center">
  <img src="assets/111.jpg" width="400" alt="Resultado Final">
</div>

Desarrollado como proyecto de la asignatura de Visión por Computador del Máster en Robótica y Automática (UC3M - 2025/2026).

---

## 🎯 Descripción

Este sistema combina dos módulos de visión por computador:

1. **Detección de Prendas (YOLO):** Identifica y localiza prendas de ropa dentro de una caja usando YOLO-World.
2. **Detección de Esquinas:** Detecta las esquinas de la caja de cartón usando segmentación HSV, operaciones morfológicas y el detector Shi-Tomasi.

### Aplicaciones
- Sistemas robóticos de picking y manipulación
- Automatización de almacenes
- Clasificación automática de textiles

---

## 📊 Resultados

### Detección de Esquinas
- **Precisión:** >90% en las 4 esquinas principales
- **Algoritmo:** Shi-Tomasi con precisión subpíxel
- **Robustez:** Funciona con diferentes iluminaciones gracias a HSV

### Detección de Prendas (YOLO)
- **Clases detectadas:** 14 tipos de prendas
- **Confianza mínima:** 50% (configurable)
- **Modelo:** YOLO-World (vocabulario abierto)


### Métricas de Rendimiento
Para validar el sistema, se realizaron entrenamientos exhaustivos monitorizando la precisión y las pérdidas del modelo.

#### Evolución de Pérdidas
<img src="assets/grafico_perdidas.png" width="700">

#### Matriz de Precisión-Recall
<img src="assets/Precision_Recall.png" width="700">

#### Métricas Generales
<img src="assets/grafico_metricas.png" width="700">

#### Curvas de Aprendizaje
<img src="assets/Perdidas_Arendizaje.png" width="700">

---

## 🚀 Uso Rápido

```bash
cd src
python3 main.py
```

Introduce el nombre de la imagen (sin extensión .jpg) cuando se solicite.

---

## ⚙️ Configuración

**Todos los parámetros están centralizados en `main.py` (líneas 16-68)**

### Parámetros Principales

| Parámetro                 | Valor por defecto     | Descripción                                   |
|-----------------------    |-------------------    |-------------                                  |
| `CONFIANZA_MINIMA`        | 0.5                   | Umbral YOLO (↑ más preciso, ↓ más detecciones)|
| `MARGEN_EXCLUSION_PRENDAS`| 20                    | Margen en píxeles alrededor de prendas        |
| `MAX_ESQUINAS`            | 20                    | Número máximo de esquinas a detectar          |
| `QUALITY_LEVEL`           | 0.05                  | Calidad mínima para Shi-Tomasi                |
| `MIN_DISTANCE`            | 70                    | Distancia mínima entre esquinas               |
---

## 🔧 Estructura del Proyecto

```
DeteccionRopa/
├── src/
│   ├── main.py                 # Script principal (configuración centralizada)
│   ├── deteccion_ropa.py       # Detección YOLO de prendas
│   ├── deteccion_esquinas.py   # Detección de esquinas de caja
│   └── *.md                    # Documentación técnica
├── images/
│   └── 02Dic/                  # Imágenes de prueba
└── README.md
```

---

## 📦 Dependencias

```bash
pip install ultralytics opencv-python numpy
```

---

## 📥 Modelos YOLO

Los archivos de modelos (`.pt`) **no están incluidos** debido a su tamaño. Se descargan automáticamente al ejecutar el código.

---

## 🎯 Clases de Prendas Detectadas

| Categoría     | Clases                                        |
|---------------|-----------------------------------------------|
| Ropa superior | top, dress, outer, shirt                      |
| Ropa inferior | pants, shorts, skirt                          |
| Calzado       | footwear, boots                               |
| Accesorios    | bag, belt, sunglasses, scarf, tie, headwear   |

---

## 📖 Proceso de Detección de Esquinas

1. **Filtro Sobel** - Detección de bordes
2. **Segmentación HSV** - Máscara de color cartón
3. **Operaciones Morfológicas** - Kernel 15×15 con MORPH_CLOSE
4. **Máscara ROI** - Encontrar contorno de la caja
5. **Intersección AND** - Eliminar suelo
6. **Exclusión YOLO** - Margen alrededor de prendas
7. **Shi-Tomasi** - Detectar esquinas

| Proceso de Esquinas | Ejemplo de Detección |
|:---:|:---:|
| <img src="assets/paso4_comparacion.jpg" width="500"> | <img src="assets/111.jpg" width="500"> |

---


---

## 👥 Autor

Víctor Martín Parra
Máster en Robótica y Automática - Universidad Carlos III de Madrid (2024/2025)

---
