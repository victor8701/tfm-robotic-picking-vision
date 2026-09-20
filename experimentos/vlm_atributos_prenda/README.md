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

> **Actualización (2026-09-20, dataset v2):** tras la revisión humana de 100 fichas, se
> cambiaron tres reglas de mapeo (`temporada` de `Jackets` → `todo_el_ano`, `grupo_estilo` de
> `Dresses` por estampado/liso en vez de fijo, filtro de ropa infantil por nombre además de por
> `gender`) — detalle y motivo en [`esquema_atributos.md`](esquema_atributos.md) y
> [`memoria/TFM_clasificador_visual_atributos.md`](../../memoria/TFM_clasificador_visual_atributos.md)
> §11.1. **`data/*.jsonl` ya está regenerado con estas reglas (v2)**; `modelos/florence2_base_lora_v1/`
> sigue siendo el adapter **v1** (entrenado con las reglas anteriores) — todos los resultados de
> este README hasta la sección "Looks completos" son v1. **`modelos/florence2_base_lora_v2/` ya
> está entrenado y evaluado** (Kaggle GPU vía API, `herramientas/kaggle_kernel/`) — no mejora el
> test global de v1 (cae `grupo_estilo` y `color_primario`, se explica en la memoria §11.2), pero
> hace lo que se pidió: ya no hace trampa con los vestidos y `temporada` distingue `todo_el_ano`
> para chaquetas. Comparación campo a campo completa en
> [`memoria/TFM_clasificador_visual_atributos.md`](../../memoria/TFM_clasificador_visual_atributos.md) §11.2.

## Estado: Stage 2 y Stage 3 (código) también listos

### Stage 2 — Baseline zero-shot

```bash
cd herramientas
python3 baseline_zero_shot.py          # las 500 de test.jsonl, ~1h en CPU
python3 baseline_zero_shot.py --limite 20   # prueba rápida
```

Pide a Florence-2 sin afinar una `<MORE_DETAILED_CAPTION>` (texto libre en inglés) y la
parsea por palabras clave contra el vocabulario cerrado de cada campo.

**Resultado real (500 imágenes de test.jsonl, ~65 min en CPU):**

| Campo | Accuracy |
|---|---|
| `categoria` | 276/500 = 55.2% |
| `color_primario` | 172/500 = 34.4% |
| `grupo_estilo` | 201/500 = 40.2% |
| `genero` | 317/500 = 63.4% |
| `temporada` | 291/500 = 58.2% |

**Aviso sobre el 40.2% de `grupo_estilo`**: no es directamente comparable al 32.8% de CLIP
zero-shot ya documentado en `clip_trend_matching/` — este parseo por palabras clave usa
`"casual"` como valor por defecto cuando la caption no menciona nada de estilo específico, y
`casual` es también la clase mayoritaria real del test set (167/500). Eso infla el número:
mirando la matriz de confusión, la mayoría de `streetwear`/`de_vestir`/`fiesta_noche` reales
también caen en `casual` por defecto, no porque el modelo las reconozca bien. Es un baseline
más parecido a "predice la clase mayoritaria" que a una clasificación real — exactamente el
tipo de "antes" flojo que se espera que el fine-tuning del Stage 3 mejore de forma honesta,
no inflada.

### Stage 3 — Fine-tuning LoRA (ejecutar en Colab)

El entrenamiento real **no** se ejecuta en esta máquina (CPU sin CUDA funcional, sería
cuestión de días) — se ejecuta en Colab con GPU T4 gratuita:

1. Sube esta rama a GitHub (`git push -u origin <rama>`).
2. Abre `herramientas/notebook_colab_entrenamiento.ipynb` en
   [Google Colab](https://colab.research.google.com/) (subir el `.ipynb` o abrirlo desde
   GitHub), activa GPU (`Entorno de ejecución > Cambiar tipo de entorno de ejecución > T4
   GPU`), y ejecuta las celdas en orden.
3. Descarga el `.zip` del adapter resultante y descomprímelo en
   `modelos/florence2_base_lora_v1/`.

`herramientas/entrenar_lora.py` es el script real (el notebook es solo un wrapper que lo
instala y lo llama). **Ya probado localmente en modo "prueba de humo"** (8 imágenes, 1 época,
CPU) para confirmar que el bucle completo —LoRA sobre las capas del decoder, forward,
backward, generación, guardado de checkpoint— corre sin errores antes de gastar horas de GPU
en el run real. LoRA aplicado: 1.9M parámetros entrenables de 233M totales (0.82%).

**Resultado real del entrenamiento** (3 épocas, GPU T4 de Colab, accuracy en validación —
500 imágenes, `resultados_entrenamiento.json` en el propio adapter):

| Campo | Época 1 | Época 2 | Época 3 (usada) |
|---|---|---|---|
| `categoria` | 96.6% | 98.4% | **98.4%** |
| `color_primario` | 64.6% | 71.8% | **72.6%** |
| `género` | 85.4% | 90.0% | **90.4%** |
| `grupo_estilo` | 81.8% | 88.2% | **88.0%** |
| `temporada` | 49.4% | 53.6% | **57.8%** |
| JSON válido | 100% | 100% | 100% |

Mejora clara sobre el baseline zero-shot en todos los campos (§Stage 2 arriba). `temporada`
apenas mejora (techo bajo esperado, ver aviso de esa sección).

**Aviso sobre el 88% de `grupo_estilo`, para no venderlo como más de lo que es**: no hay
motivo para pensar que el modelo ha aprendido "estilo" en un sentido abstracto — es mucho más
probable que haya aprendido a reconstruir la propia regla de mapeo
`articleType → grupo_estilo` de `preparar_dataset_florence2.py` a partir del tipo de prenda,
que tiene señal visual fuerte (y por eso `categoria` también borda el 98%). Es un resultado
real y útil para el catálogo, pero no contradice la limitación estructural ya anotada más
abajo (estilo como propiedad del *look* completo, no de una prenda sola) — de hecho la
confirma: el atajo tipo-de-prenda→estilo que aquí funciona tan bien es precisamente lo que no
va a estar disponible en una foto de Instagram con el outfit completo puesto.

### Revisión humana y prueba en fotos reales (primeros hallazgos)

Dos comprobaciones hechas *después* del entrenamiento, ambas con muestras pequeñas — leerlas
como indicios, no como métricas cerradas. Datos en `data/revision_humana/`.

> **Actualización (2026-09-20):** las cifras de esta sección son las de las **primeras 33 fichas**
> y se conservan como registro histórico. Con 100 fichas revisadas (`data/revision_humana/revisiones_app_n100_2026-09-20.json`)
> las conclusiones se mantienen; los números completos y actualizados están en
> [`memoria/TFM_clasificador_visual_atributos.md`](../../memoria/TFM_clasificador_visual_atributos.md) §7, y se recalculan con
> `herramientas/analizar_revision_humana.py`.

**1. Etiquetas humanas vs. etiquetas de Kaggle** (33 fichas revisadas a mano en la app
"Ficha de Prenda", sacadas del test set). Las etiquetas de
Kaggle son un *proxy*, y la revisión humana lo confirma:

| Campo | Acuerdo humano-Kaggle | Qué pasa |
|---|---|---|
| `genero` | 33/33 | fiable |
| `categoria` | 32/33 | única discrepancia: una chaqueta de forro polar (¿abrigo o ropa superior?) — frontera real de la taxonomía |
| `grupo_estilo` | 24 iguales, 6 con estilos extra, 3 distintos | varios estilos válidos a la vez; y `Dresses → fiesta_noche` (mi regla de mapeo) falla en 2 vestidos casuales |
| `color_primario` | 25 iguales, 6 con colores extra, 2 distintos | prendas multicolor — un solo color es una simplificación |
| `temporada` | **16/33** | en 13 de 33 marcó "todo el año" donde Kaggle fuerza una estación |

Conclusión: la `temporada` de Kaggle es la estación de la colección del comerciante, no la
estacionalidad de la prenda, y "todo el año" —clase válida en §3.4— no existe en el
entrenamiento. El ~60% de `temporada` es un techo de *definición de etiqueta*, no del modelo:
el modelo acierta a Kaggle un 58% en esas 33 y a las etiquetas humanas un 45%, es decir, apenas
por encima del propio acuerdo humano-Kaggle (52%).

**2. El modelo contra tus etiquetas** (mismas 33; acierto = la predicción cae dentro de lo que
marcó el revisor): media 81% frente a 85% contra Kaggle. Lo esencial aguanta (`categoria` 97%,
`color_primario` 85%, `grupo_estilo` 88%); se cae solo `temporada`. Los errores de
`grupo_estilo` incluyen el que ya se anticipaba: el modelo reproduce fielmente la regla
`Dresses → fiesta_noche` que le enseñé, defecto incluido.

**3. Fotos reales de calle** (19 fotos de *street fashion* de Wikimedia Commons, gente con
el outfit puesto y fondo real; `descargar_fotos_calle_wikimedia.py`; sin etiquetas, valoración
cualitativa mía sobre las miniaturas — no es una métrica):

- `categoria`: en **12 de 19** predice `accesorio`. Casi nunca es lo correcto: en un look
  completo hay varias prendas y el modelo, que solo ha visto prendas sueltas ocupando el
  encuadre, cae en "objeto pequeño en escena grande". Es un atajo de layout, no de prenda.
- `temporada`: **19/19 `primavera_verano`** — colapsa a una constante.
- `color_primario`: `negro` en 12 de 19 (la clase más frecuente del entrenamiento).
- `grupo_estilo`: es el campo que mejor sobrevive (a ojo, alrededor de la mitad plausibles):
  acierta los vestidos de lentejuelas (`fiesta_noche`), la camiseta amarilla (`casual`) y varios
  looks urbanos (`streetwear`), y falla con otros. El estilo es holístico y la imagen entera
  lo arrastra, aunque no por el mecanismo que se pretendía.
- El único caso limpio (una persona, una prenda, fondo neutro — la camiseta amarilla) sale
  bien en los 4 campos: el modelo funciona cuando la foto se parece a lo que vio.

Esto **confirma con imágenes** la limitación ya anotada: un clasificador de prenda única no es
un clasificador de looks. El paso lógico es *detectar → recortar → clasificar cada prenda →
agregar el estilo del outfit* (ver "Próximos pasos").

### Stage 4 — Evaluación final

```bash
cd herramientas
python3 evaluar_modelo.py
```

Compara zero-shot vs afinado por campo (accuracy + F1 por clase en `color_primario` y
`grupo_estilo`, tasa de JSON válido, latencia), y termina re-evaluando `grupo_estilo` sobre
las 1207 imágenes ya existentes en `clip_trend_matching/` para comparar directamente contra
el 32.8% de CLIP zero-shot ya documentado. Si `modelos/florence2_base_lora_v1/` todavía no
existe (no se ha bajado el adapter de Colab), solo corre la parte zero-shot.

**Resultado real** (test de 500 imágenes: categoría 99.6 %, color 76.2 %, estilo 90.8 %,
género 94.0 %, temporada 60.2 %, JSON válido 100 %): salida completa en
`modelos/florence2_base_lora_v1/evaluacion_test_2026-09-17.txt`.

**Aviso — la comparación con CLIP que imprime este script está contaminada.** Las 1207
imágenes salen del mismo dataset que train/val/test y el **36 % (434) son imágenes que el
modelo ya había visto** (348 en train), así que el 73.4 % que sale al final no es una prueba
de generalización. La comparación limpia (solo las no vistas, con CLIP evaluado sobre las
mismas imágenes) es `herramientas/evaluar_solape_1207.py`; resultado y análisis en
[`memoria/TFM_clasificador_visual_atributos.md`](../../memoria/TFM_clasificador_visual_atributos.md) §6.3 y §10.

### Looks completos: detectar → recortar → clasificar → agregar (prototipo)

```bash
cd herramientas
python3 analizar_outfit.py --carpeta ../data/fotos_calle --salida-json outfits.json \
    --salida-imagenes anotadas --cache cache.json     # ≈ 40 s por foto en CPU
python3 resumen_outfit.py --outfits outfits.json \
    --foto-entera ../data/revision_humana/predicciones_fotos_calle.json \
    --auditoria ../data/revision_humana/auditoria_outfit_calle.json
```

Mismo Florence-2 con dos capacidades: con el adapter **desactivado** detecta personas y prendas
(`<OD>` + *phrase grounding* de una frase cada vez) y con el adapter **activado** clasifica cada
recorte. El estilo del look es el voto ponderado de sus prendas. Es un prototipo heurístico
(la detección es la parte frágil) evaluado sobre 19 fotos, con una auditoría hecha por Claude y
guardas ajustadas mirando esas mismas fotos: leer los resultados como indicios, no como
métricas. Detalle y cifras en la memoria (§8).

## Próximos pasos

1. ~~Reentrenar v2~~ — **hecho** (Kaggle GPU vía API en vez de Colab —
   `herramientas/kaggle_kernel/`—, ver memoria §11.2-§11.3). No mejora el test global de 500
   imágenes, pero contra las 100 fichas revisadas a mano `color_primario` y `grupo_estilo` se
   quedan prácticamente igual que v1 — la caída del test grande parece más ruido de qué imágenes
   raras le tocaron que una pérdida de calidad real (contraste pareado en memoria §11.2).
2. **Terminar la revisión humana** de las 120 fichas de la app (van 100): daría un subconjunto
   del test verificado por una persona, que es una evaluación más honesta que la de Kaggle.
   Conviene hacerlo *sin* mostrar la predicción del modelo, para no sesgar las etiquetas.
3. ~~Looks completos: detectar → recortar → clasificar → agregar~~ — **hecho como prototipo**
   (ver arriba). Falta: sustituir las heurísticas de detección por un detector de prendas afinado
   (DeepFashion2) y validar los recortes con etiquetas humanas (el prototipo se auditó solo a ojo).
4. ~~Decisiones de esquema pendientes~~ — **resueltas** (2026-09-20): `temporada` de `Jackets` →
   `todo_el_ano`; `grupo_estilo` de vestidos por estampado/liso; filtro de ropa infantil por
   nombre; `deportivo`+`streetwear` se queda sin resolver (se descartó reetiquetar por marca) y
   la paleta de color no se toca. Detalle en la memoria (§11.1). ~~Sigue abierto: `temporada`
   del resto de tipos de prenda~~ — **resuelto también** (mismo día, más tarde): artifact
   "Reglas de temporada", 13 tipos más a `todo_el_ano` (antes solo `Jackets`); reentrenado como
   v3. Memoria §11.5.
5. Sobremuestrear la cola larga de tipos de prenda (el estilo cae al 3% en tipos con menos de
   10 ejemplos, §6.3) y las 5 clases de color con F1 0.00 en v2 (`fucsia`, `plateado`, `burdeos`,
   `dorado`, `naranja` — memoria §11.2): sigue mereciendo la pena aunque el punto 1 rebaje la
   urgencia, son las clases con menos datos de todo el esquema.

## Qué NO es (mismo aviso honesto que en `clip_trend_matching/`)

- Entrena y evalúa sobre fotos de catálogo (Kaggle), no fotos reales de redes sociales —
  `viral_clips` (la herramienta de ingesta de vídeo de §6.1) no existe todavía en este
  entorno. Se espera una caída de precisión real al pasar a fotos reales (fondos, gente,
  oclusión) — ver Stage 5 del plan para el camino a validarlo con un puñado de fotos reales.
  **Matiz importante para `grupo_estilo` en concreto**: no es solo un problema de fondo/luz —
  el estilo es una propiedad del *look* completo (varias prendas combinadas), no de una
  prenda aislada. Una zapatilla sola no dice "streetwear"; zapatilla + vaquero ancho +
  sudadera sí. Entrenar solo con prendas sueltas pone un techo estructural a este campo que
  no se arregla con más datos del mismo tipo — para acercarse de verdad al caso real
  (influencer con varias prendas puestas) hace falta un dataset con outfits completos, no
  solo más fotos de catálogo. Candidato natural ya citado en el estado del arte (§12.2):
  **DeepFashion2**, que incluye pares foto-consumidor (calle/selfie, outfit completo) +
  foto-tienda pensados exactamente para este salto de dominio.
- `material`, `estampado` y `fit` (§3.4) quedan fuera del esquema v1 — el dataset de Kaggle no
  tiene columnas ni señal de texto fiable para ninguno de los tres.
