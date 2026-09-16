# Clasificador de características de prendas desde foto (VLM propio)

Programa que mira una foto de una prenda (estilo redes sociales / catálogo) y devuelve sus
características estructuradas: categoría, color, grupo de estilo, género, temporada. Es la
pieza **visual** que le faltaba al Trend Intelligence Agent de
[`memoria/Estado_arte.md`](../../memoria/Estado_arte.md) §6 — esa sección ya cubre el análisis
de *audio/texto* de vídeos (Whisper → Qwen2.5 → Claude), pero no analiza directamente el
contenido visual de una foto.

**Por qué no es simplemente "llamar a Claude/Gemini con la foto"**: por ser un TFM de
investigación, la aportación tiene que ser algo más propio que envolver una API comercial.
Este componente usa **Florence-2-base (232M parámetros, Microsoft, MIT license) afinado con
LoRA sobre datos propios** — pesos abiertos, autoalojado, reentrenado para esta tarea
concreta. Sigue la metodología de un paper reciente y directamente relevante, *"Fashion
Florence: Fine-Tuning Florence-2 for Structured Fashion Attribute Extraction"*
(arXiv:2605.09827, mayo 2026), que demuestra que un VLM pequeño afinado así **supera a
GPT-4o-mini y Gemini 2.5 Flash** en extracción de atributos de moda — el mismo tipo de
comparación que este experimento reproduce sobre la taxonomía propia de este TFM, no sobre la
de iMaterialist del paper original.

## Relación con `experimentos/clip_trend_matching/`

Esa carpeta ya validó (con 1207 fotos reales) que pedirle a **CLIP** que adivine el
`grupo_estilo` de una foto por zero-shot funciona mal (32.8% de acierto, `fiesta_noche/`
colapsa a 0%). Este experimento parte de ahí: en vez de forzar a CLIP a hacer un trabajo de
clasificación fina que no es el suyo, se entrena un modelo generativo específico para esa
tarea. Las 1207 imágenes de `clip_trend_matching/` se reutilizan más adelante (Stage 4) como
banco de comparación directa contra ese 32.8%.

## Estado: Stage 0 y Stage 1 completados

### Stage 0 — Entorno

```bash
cd experimentos/vlm_atributos_prenda
pip install -r requirements.txt
```

**Aviso importante de compatibilidad**: `transformers` está fijado a `==4.51.3` a propósito.
Florence-2 usa código remoto (`trust_remote_code=True`) que **se rompe** con `transformers >=
4.52.1` y con la serie `5.x` (`AttributeError: 'Florence2LanguageConfig' object has no
attribute 'forced_bos_token_id'` — incompatibilidad conocida y activa en la comunidad, sin fix
oficial a fecha de este commit). Verificado en este entorno: con `4.51.3` carga bien.

Si además ves errores de `numpy`/`scipy`/`PIL` al instalar (puede pasar si hay paquetes viejos
del sistema mezclados con los nuevos de pip), actualiza esos tres explícitamente:
```bash
pip install --upgrade scipy pillow
```

### Stage 1 — Preparar el dataset

```bash
cd herramientas
python3 preparar_dataset_florence2.py
```

Reutiliza el parquet ya cacheado por `clip_trend_matching/herramientas/poblar_muestras_dataset.py`
en `~/.cache/fashion-product-images-small/` (si no existe, hay que correr ese script primero
para descargarlo). Mapea cada fila a un JSON de 5 campos según las tablas de
[`esquema_atributos.md`](esquema_atributos.md), descarta la fila si falta algún campo, y
reparte el resultado en `data/train.jsonl` (4000), `data/val.jsonl` (500) y `data/test.jsonl`
(500), con las imágenes extraídas a `data/imagenes_cache/` (no se commitea, se regenera con
este mismo script + la semilla fija `42`).

De las 44072 filas del dataset, **24798 (56.3%) tienen los 5 campos mapeables** — el resto se
descarta por no tener columna de color reconocible, ser ropa étnica/infantil/no textil (mismos
criterios que `poblar_muestras_dataset.py`), o no encajar en ningún filtro de `grupo_estilo`.
`grupo_estilo` sigue siendo la señal más desequilibrada (`casual` domina con 14357 filas frente
a las 1651-2569 del resto) — esperable, es la misma clase que ya iba peor con CLIP.

## Próximos pasos (según el plan)

- **Stage 2** (`baseline_zero_shot.py`, local): Florence-2 sin afinar sobre `data/test.jsonl`,
  para tener un número "antes" documentado, igual que ya se hizo con CLIP.
- **Stage 3** (`entrenar_lora.py` + `notebook_colab_entrenamiento.ipynb`, en Google Colab):
  fine-tuning LoRA real sobre las 4000 imágenes de entrenamiento.
- **Stage 4** (`evaluar_modelo.py`, local): zero-shot vs afinado por campo, y comparación
  directa de `grupo_estilo` contra el 32.8% de CLIP sobre las mismas 1207 imágenes.

## Qué NO es (mismo aviso honesto que en `clip_trend_matching/`)

- Entrena y evalúa sobre fotos de catálogo (Kaggle), no fotos reales de redes sociales —
  `viral_clips` (la herramienta de ingesta de vídeo de §6.1) no existe todavía en este
  entorno. Se espera una caída de precisión real al pasar a fotos reales (fondos, gente,
  oclusión) — ver Stage 5 del plan para el camino a validarlo con un puñado de fotos reales.
- `material`, `estampado` y `fit` (§3.4) quedan fuera del esquema v1 — el dataset de Kaggle no
  tiene columnas ni señal de texto fiable para ninguno de los tres.
