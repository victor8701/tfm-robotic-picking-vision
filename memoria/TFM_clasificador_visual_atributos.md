# Clasificador visual de atributos de prenda (VLM propio): proceso y resultados

**Autor:** Víctor Martín Parra  
**Máster:** Robótica y Automatización — UC3M (2025/2027)  
**Fecha:** 20 de septiembre de 2026  
**Versión:** 0.7 (documento vivo: v0.1 = resultados del dataset/adapter v1; v0.2 = decisiones de esquema del autor y
dataset v2 regenerado, §11.1; v0.3 = adapter v2 entrenado y evaluado, comparación con v1, §11.2; v0.4 = resto de
`temporada` decidido y dataset v3 regenerado, §11.4; v0.5 = adapter v3 entrenado y evaluado — mejor que v1 y v2 contra
el humano, §11.4; v0.6 = sobremuestreo de colores raros, dataset v4 regenerado, §11.5; v0.7 = adapter v4 entrenado y
evaluado — arregla 3 clases de color, a costa de la media global, §11.5)  
**Código y datos:** [`experimentos/vlm_atributos_prenda/`](../experimentos/vlm_atributos_prenda/) (rama `clip-trend-semantic-matching-poc`)  
**Relación con el estado del arte:** este documento cubre la pieza *visual* del Trend Intelligence Agent
([`Estado_arte.md`](Estado_arte.md) §6) y el matching semántico (§7). **No modifica `Estado_arte.md`**: el autor pidió
no tocarlo en profundidad, así que el vocabulario de color de §3.4 se queda como está (§11.1).

---

## Índice

0. [Resumen: inicial frente a final](#0-resumen-inicial-frente-a-final)
1. [Objetivo y contexto](#1-objetivo-y-contexto)
2. [Cronología](#2-cronología)
3. [Punto de partida: CLIP zero-shot](#3-punto-de-partida-clip-zero-shot)
4. [Datos](#4-datos)
5. [Método: Florence-2-base + LoRA](#5-método-florence-2-base--lora)
6. [Resultados sobre fotos de catálogo](#6-resultados-sobre-fotos-de-catálogo)
7. [Revisión humana (app «Ficha de Prenda»)](#7-revisión-humana-app-ficha-de-prenda)
8. [Fotos reales de calle: de la foto entera a los looks](#8-fotos-reales-de-calle-de-la-foto-entera-a-los-looks)
9. [Limitaciones y amenazas a la validez](#9-limitaciones-y-amenazas-a-la-validez)
10. [Correcciones a lo dicho antes](#10-correcciones-a-lo-dicho-antes)
11. [Decisiones abiertas y próximos pasos](#11-decisiones-abiertas-y-próximos-pasos)
12. [Reproducibilidad](#12-reproducibilidad)

---

## 0. Resumen: inicial frente a final

El programa recibe una foto y devuelve un JSON con cinco atributos de la prenda (`categoria`, `color_primario`,
`grupo_estilo`, `genero`, `temporada`). Se parte de CLIP zero-shot (que no sirve para clasificar estilo) y se llega a un
VLM de pesos abiertos, **Florence-2-base (232M) afinado con LoRA (0.82 % de parámetros entrenables)**, más un prototipo
que lo aplica a fotos con personas (detectar → recortar → clasificar cada prenda → agregar el estilo del look).

| Qué se mide | Inicial | Final | Comentario |
|---|---|---|---|
| Estilo de una prenda de catálogo, 1 de 6 (imágenes de `clip_trend_matching/`) | CLIP zero-shot **32.8 %** en las 1207 (`fiesta_noche` 0 %) | Florence-2 afinado **63.9 %** en 371 imágenes **no vistas** (CLIP en esas mismas: 36.9 %); **75.6 %** (CLIP 41.8 %) si el tipo de prenda tiene ≥ 10 ejemplos en train; `fiesta_noche` 0 % → **90.9 %** | La cifra anterior (73.4 %) estaba contaminada, §6.3 y §10. CLIP gana en `de_vestir`; el afinado casi no acierta en tipos no vistos (3 %) |
| Test de catálogo (500 imágenes), media de los 5 campos | Florence-2 sin afinar **50.3 %** | **84.2 %** | +33.9 puntos; JSON válido 100 % |
| `grupo_estilo` en test | 40.2 % (inflado por defecto `casual`) | **90.8 %** | probablemente aprende la regla de etiquetado, ver §6.4 |
| `temporada` en test | 58.2 % (mayoritaria: 56.8 %) | 60.2 % | apenas mejora: el problema es la definición de la etiqueta, ver §7.3 |
| Acuerdo del modelo con etiquetas **humanas** (100 fichas) | — | **79 %** de media (87.8 % sin `temporada`) | Kaggle frente al humano: 45 % en `temporada`, 86 % en estilo |
| Foto de calle **entera**: categoría predicha | `accesorio` en **12 de 19** fotos | — | síntoma del salto de dominio, §8.2 |
| Foto de calle: estilo del look dentro de lo aceptable (persona principal, 19 fotos) | 13/19 = 68 % (foto entera) | **16/19 = 84 %** (looks por prenda) | muestra pequeña, guardas ajustadas sobre las mismas fotos, auditada por Claude, §8.4 |
| Looks: cajas de prenda correctas / prendas visibles detectadas | — | **93 %** (80/86) / **98 %** (82/84) | ídem |
| Looks: `temporada` por prenda | — | 83 de 84 recortes → `primavera_verano` | inservible fuera del catálogo |

*(Esta tabla es el "antes/después" del adapter **v1**. Hay tres vueltas más — v2 (`temporada` de
`Jackets`, `grupo_estilo` de `Dresses`), v3 (`temporada` de otros 13 tipos) y v4 (sobremuestreo de
colores raros) — con resultado real y comparación campo a campo en §11.2, §11.4 y §11.5. Contra las
100 fichas revisadas a mano (más fiable que el test de 500, que cambia de contenido entre
versiones): v2 se queda prácticamente igual que v1 salvo `temporada`, que cae por el motivo
esperado; **v3 es la mejor de las cuatro versiones en acuerdo medio (85 %)**, con `temporada`
subiendo de 44 %/38 % a 68 %; **v4 arregla de verdad 3 de los 5 colores que llevaban en F1 0.00
desde v1** (`naranja`, `dorado`, `plateado`) pero a costa de `color_primario` en general —
media 82 %, peor que v3 aunque sigue por delante de v1/v2 — un trade-off real, no una mejora
limpia.)*

Seis conclusiones:

1. **El ajuste fino funciona sobre catálogo** y con un coste mínimo (≈21 min de GPU T4, adapter de 7.7 MB), pero el
   techo lo pone la calidad de las etiquetas de Kaggle, no el modelo.
2. **`temporada` es un problema de definición de etiqueta**, no del modelo: Kaggle da la estación de la *colección del
   comerciante* y las etiquetas humanas usan `todo_el_ano` en 43 de 100 fichas (una clase que el modelo de 2 valores no
   puede responder). Sobre las 57 fichas «respondibles» el modelo acierta el 77 % y la etiqueta de Kaggle el 79 %.
3. **La comparación con CLIP que se dio como resultado principal estaba contaminada**: el 36 % de las 1207 imágenes son
   imágenes que el modelo afinado ya había visto (§10). Recalculada solo con no vistas: **63.9 % frente a 36.9 %** de CLIP
   (+27 puntos, no +40.6; diferencia significativa), con `fiesta_noche` 0 % → 90.9 % y `casual` 18 % → 87 %, pero **CLIP
   gana en `de_vestir` (87 % frente a 57 %)**.
4. **Las etiquetas de Kaggle son fiables para categoría, color y género (94–99 %) y flojas para estilo (86 %) y temporada
   (45 %)**; la regla `Dresses → fiesta_noche` es incorrecta en la mayoría de los vestidos, y ~2.8 % del entrenamiento
   son prendas infantiles que se colaron.
5. **El salto de dominio es real y se puede mitigar**: el clasificador de prenda suelta colapsa sobre una foto entera
   (`accesorio`, `temporada` constante); con detectar → recortar → clasificar el estilo del look mejora y la
   estructura del look aparece, aunque `temporada` y el color siguen siendo débiles.
6. **La detección es la parte frágil** del prototipo (heurísticas sobre Florence-2 sin afinar) y está evaluada sobre
   19 fotos, con ajustes hechos mirando esas mismas fotos.

---

## 1. Objetivo y contexto

Hasta que haya acceso a los robots físicos, el trabajo se centra en la parte de IA. El Trend Intelligence Agent de
`Estado_arte.md` §6 analiza audio y texto de vídeos de redes sociales, pero no el **contenido visual**: qué prendas
aparecen y con qué características. Este componente es esa pieza.

Requisito del autor, por ser un TFM de investigación: la clasificación no puede ser «llamar a Claude o Gemini con la
foto». Se busca un modelo **lo más propio posible**: pesos abiertos, autoalojado y afinado con datos propios. Se sigue la
metodología de *Fashion Florence: Fine-Tuning Florence-2 for Structured Fashion Attribute Extraction* (arXiv:2605.09827),
que según sus autores supera a GPT-4o-mini y Gemini 2.5 Flash en extracción de atributos de moda (cifras del paper, no
reproducidas aquí). Queda pendiente la comparación propia con un LLM comercial (§11).

Esquema de salida (v1), detallado en [`esquema_atributos.md`](../experimentos/vlm_atributos_prenda/esquema_atributos.md):

```json
{"categoria":"ropa_superior","color_primario":"negro","grupo_estilo":"streetwear","genero":"masculino","temporada":"otono_invierno"}
```

`material`, `estampado` y `fit` (§3.4) quedan fuera de v1: Kaggle no tiene columna ni señal de texto fiable para ellos.

---

## 2. Cronología

| Fecha | Hito | Commits |
|---|---|---|
| 2026-09-16 | POC de matching semántico CLIP prenda↔tendencia (§7) con guía de uso | `f591901`…`bcb3912` |
| 2026-09-16 | 1207 imágenes en 6 carpetas de estilo + evaluación cuantitativa (accuracy, confusión, Precision@K) | `1ea7210`, `9e6e10d` |
| 2026-09-16 | Decisión: modelo propio (Florence-2-base + LoRA). Etapas 0–2: entorno, dataset, baseline zero-shot | `1fe67e8`, `f28294f` |
| 2026-09-17 | Etapa 3: entrenamiento LoRA en Colab (T4); correcciones de precisión mixta | `1da9a05`…`46cd0ff` |
| 2026-09-17 | Etapa 4: evaluación en test, F1 por clase y comparación con CLIP (resultados sin registrar en el repositorio hasta este documento) | |
| 2026-09-20 | App de revisión humana, fotos de calle, prototipo de looks, auditoría del solape con CLIP | `e03385f` y el commit de este documento |
| 2026-09-20 (tarde) | Decisiones de esquema del autor (§11.1) implementadas; dataset v2 regenerado | commit de esta actualización |
| 2026-09-20 (noche) | Adapter v2 entrenado y evaluado (Kaggle GPU, vía API — §11.3); comparación v1/v2 en §11.2 | commit de esta actualización |
| 2026-09-20 (noche, más tarde) | `temporada` decidida para 13 tipos más vía artifact; dataset v3 regenerado (Kaggle vía API) | `bbd78a0` |
| 2026-09-20 (noche, aún más tarde) | Adapter v3 entrenado y evaluado — mejor que v1 y v2 contra el humano, sobre todo en `temporada` (§11.4) | `0cd5316` |
| 2026-09-20 (noche, todavía más tarde) | Sobremuestreo de colores raros; dataset v4 regenerado (Kaggle vía API) | `6962797` |
| 2026-09-20 (noche, última) | Adapter v4 entrenado y evaluado — arregla 3 colores, cae la media global (§11.5) | commit de esta actualización |

---

## 3. Punto de partida: CLIP zero-shot

POC de `Estado_arte.md` §7 (ViT-B/32 `openai`, QuickGELU): similitud coseno entre la foto y el texto de una tendencia, más
un *boost* categórico de estilo (β = 0.1). Como tarea auxiliar se le pidió elegir el `grupo_estilo` de cada foto entre 6
frases (una por grupo). Se evaluó sobre **1207 fotos de producto** de 6 carpetas (una por grupo de estilo).

### 3.1 Accuracy 1 de 6 (`evaluar_precision_grupo_estilo.py`)

| Grupo (carpeta) | n | Frase única | Ensemble de plantillas |
|---|---|---|---|
| casual | 250 | 35 = 14.0 % | 68 = 27.2 % |
| streetwear | 200 | 88 = 44.0 % | 129 = 64.5 % |
| de_vestir | 175 | 147 = 84.0 % | 122 = 69.7 % |
| fiesta_noche | 136 | **0 = 0.0 %** | 4 = 2.9 % |
| deportivo | 229 | 67 = 29.3 % | 59 = 25.8 % |
| playa_resort | 217 | 59 = 27.2 % | 99 = 45.6 % |
| **Total** | **1207** | **396 = 32.8 %** (IC95 30.2–35.5) | **481 = 39.9 %** (IC95 37.1–42.6) |

Referencias: azar 16.7 %; clase mayoritaria (`casual`) 20.7 %. `fiesta_noche` cae en `de_vestir` en 109 de 136 casos (80 %);
`casual` se reparte entre `streetwear` (104) y `de_vestir` (86); `playa_resort` va a `streetwear` en 89 de 217.
(El ensemble salió de un script desechable que no está en el repositorio; la columna de frase única se reproduce con
`evaluar_solape_1207.py`.) El ensemble de plantillas sube 7.1 puntos pero no arregla `fiesta_noche`: no es un problema de redacción del prompt, una
foto de producto sin contexto no lleva la señal visual «de fiesta».

### 3.2 Ranking por tendencia y Precision@K

Puntuación semántica media por carpeta para tres tendencias de ejemplo: en 1 de las 3 la carpeta esperada queda primera
(streetwear: 0.2031 frente a 0.2015 de deportivo, margen de 0.0016). En las otras dos queda segunda, por detrás de
`fiesta_noche`. Precision@K con solo la parte semántica: 50 / 48 / 34 % (streetwear), 25 / 48 / 31 % (quiet luxury),
20 / 20 / 20 % (resort) para K = 20 / 50 / 100. Con el *boost* real de §7.2 sale 100 % en todo, pero **es tautológico**: el
boost (0.1) es mayor que la dispersión de la parte semántica (≈0.03), así que el ranking lo decide la etiqueta y no CLIP.

### 3.3 Qué se aprendió

- Pedir a CLIP que *adivine* el estilo no es viable (32.8–39.9 %).
- La señal semántica directa foto↔texto existe pero es pequeña y ruidosa a esta escala.
- Sí hace falta que «algo» mire una foto de moda y le asigne características: eso motiva un clasificador específico.

---

## 4. Datos

**Fuente:** *Fashion Product Images (Small)* (Param Aggarwal, Kaggle; espejo `ashraq/fashion-product-images-small` en
Hugging Face). 44 072 filas, 135 `articleType`, imágenes de **60×80 px**. Sin licencia libre explícita (origen e-commerce):
uso de prototipo académico.

**Mapeo a v1** (tablas completas en `esquema_atributos.md`): `categoria` (6 cabeceras de §3.3), `color_primario` (paleta
de §3.4; `Purple → lavanda` como aproximación, `Multi` descartado), `grupo_estilo` (6 valores de §3.4.1, por regla
`articleType`/`usage`, y `Dresses`+`Heels`+`Clutches`+`Jumpsuit → fiesta_noche`), `genero` (`Men/Women/Unisex`) y
`temporada` (`Summer/Spring → primavera_verano`, `Fall/Winter → otono_invierno`). Se excluyen ropa étnica, ropa interior
y de estar por casa, artículos no textiles, `Boys`/`Girls` y filas sin algún campo.

**Embudo:** 44 072 filas → **24 798 mapeables (56.3 %)** → muestreo estratificado (semilla 42; duro por `categoria`, suave
por `grupo_estilo`) de **4000 train / 500 val / 500 test**.

Distribución (herramienta `estadisticas_dataset.py`):

| `categoria` | train | val | test |
|---|---|---|---|
| accesorio | 891 (22.3 %) | 100 (20.0 %) | 98 (19.6 %) |
| ropa_superior | 867 (21.7 %) | 116 (23.2 %) | 106 (21.2 %) |
| calzado | 865 (21.6 %) | 109 (21.8 %) | 115 (23.0 %) |
| ropa_inferior | 851 (21.3 %) | 114 (22.8 %) | 123 (24.6 %) |
| cuerpo_entero | 317 (7.9 %) | 38 (7.6 %) | 38 (7.6 %) |
| abrigo | 209 (5.2 %) | 23 (4.6 %) | 20 (4.0 %) |

| `grupo_estilo` | train | val | test |
|---|---|---|---|
| casual | 1375 (34.4 %) | 183 (36.6 %) | 167 (33.4 %) |
| streetwear | 849 (21.2 %) | 91 (18.2 %) | 92 (18.4 %) |
| fiesta_noche | 592 (14.8 %) | 68 (13.6 %) | 76 (15.2 %) |
| de_vestir | 505 (12.6 %) | 60 (12.0 %) | 75 (15.0 %) |
| deportivo | 417 (10.4 %) | 62 (12.4 %) | 60 (12.0 %) |
| playa_resort | 262 (6.6 %) | 36 (7.2 %) | 30 (6.0 %) |

| `genero` | train | val | test |
|---|---|---|---|
| masculino | 2096 (52.4 %) | 269 (53.8 %) | 268 (53.6 %) |
| femenino | 1390 (34.8 %) | 177 (35.4 %) | 177 (35.4 %) |
| neutro | 514 (12.8 %) | 54 (10.8 %) | 55 (11.0 %) |

| `temporada` | train | val | test |
|---|---|---|---|
| primavera_verano | 2271 (56.8 %) | 272 (54.4 %) | 284 (56.8 %) |
| otono_invierno | 1729 (43.2 %) | 228 (45.6 %) | 216 (43.2 %) |

`color_primario` (train): negro 27.1 %, azul 15.7 %, gris 9.6 %, blanco 8.9 %, camel 7.2 %, navy 5.9 %, rojo 5.6 %,
verde 4.8 %, lavanda 3.8 %, rosa 3.0 %, beige 2.9 %, naranja 1.4 %, burdeos 1.2 %, amarillo 1.1 %, dorado 1.1 %,
**plateado 0.6 % (24 imágenes)**, **fucsia 0.1 % (4 imágenes)**.

**Clase mayoritaria en test** (referencia mínima de cualquier clasificador): categoría 24.6 %, color 26.6 %, estilo 33.4 %,
género 53.6 %, temporada 56.8 % (media 39.0 %).

### Problemas conocidos de las etiquetas (documentados antes de entrenar, confirmados después)

- `temporada` de Kaggle = estación de la **colección del comerciante**, no estacionalidad de la prenda.
- `grupo_estilo` sale de una regla por tipo de prenda, no de una anotación visual de estilo.
- Prendas infantiles que pasan el filtro `Boys/Girls` (marcas como *Gini and Jony*, *Doodle Kids*…): **111 de 4000 (2.8 %)**
  en train, 15/500 en val, 7/500 en test (por nombre); en `Dresses`, 27 de 317 (8.5 %) de train.
- Imágenes de 60×80 px: mucha menos información de la que verá el modelo en una foto real.

> **Los tres puntos de arriba ya no describen el dataset actual.** El 2026-09-20, con las
> respuestas del autor a §11.1, se corrigieron los dos primeros (`temporada` de `Jackets`,
> `grupo_estilo` de `Dresses`) y el filtro de ropa infantil se hizo mucho más estricto (por
> nombre, no solo por `gender`; sube de 111/4000 a un pool completo de 713 filas detectadas).
> **Las tablas de esta sección y los resultados de §6–§8 son del dataset y el adapter v1**
> (`modelos/florence2_base_lora_v1/`) — quedan como estaban a propósito, para que los números de
> entrenamiento/evaluación de esas secciones sigan siendo coherentes entre sí. `data/*.jsonl` ya
> está en su versión **v3** (reglas de §11.1 + §11.4); los adapters v2
> (`modelos/florence2_base_lora_v2/`) y v3 (`_v3/`) **ya están entrenados y evaluados** — conteos
> del dataset en §11.1/§11.4, resultados y comparación campo a campo en §11.2/§11.4.

---

## 5. Método: Florence-2-base + LoRA

| Elemento | Valor |
|---|---|
| Modelo base | `microsoft/Florence-2-base`, 232M parámetros, licencia MIT (visión DaViT + encoder-decoder tipo BART), `trust_remote_code=True` |
| Tarea | prompt `<ATRIBUTOS_PRENDA>` → el JSON compacto de 5 campos (máx. 96 tokens objetivo) |
| LoRA | r = 16, α = 32, dropout 0.05, sobre `q/k/v/out` de la autoatención y atención cruzada del decoder y `fc1/fc2`; visión congelada |
| Parámetros entrenables | **1 916 928 de 233 330 944 (0.8215 %)** |
| Optimización | AdamW, LR 2e-4, weight decay 0.01, calentamiento 5 %, decaimiento lineal; micro-batch 4 × acumulación 4 = **16** |
| Épocas / pasos | 3 épocas, 1000 micro-pasos por época (250 pasos de optimizador), semilla 42 |
| Hardware | Google Colab, GPU T4; precisión mixta (pesos fp32 + autocast fp16 + GradScaler: la T4 no tiene kernels de convolución bf16) |
| Tiempo | ≈ 0.41 s por micro-paso → ≈ 7 min por época, **≈ 21 min** de entrenamiento |
| Tamaño del adapter | 7.7 MB (`modelos/florence2_base_lora_v1/`) |
| Entorno | `transformers==4.51.3` (Florence-2 falla con ≥ 4.52.1 y 5.x), PEFT; inferencia local en CPU (8 hilos, 7.7 GB de RAM, GPU local inutilizable) |

Accuracy en **validación** (500 imágenes) por época:

| Campo | Época 1 | Época 2 | Época 3 (usada) |
|---|---|---|---|
| `categoria` | 96.6 | 98.4 | **98.4** |
| `color_primario` | 64.6 | 71.8 | **72.6** |
| `grupo_estilo` | 81.8 | 88.2 | **88.0** |
| `genero` | 85.4 | 90.0 | **90.4** |
| `temporada` | 49.4 | 53.6 | **57.8** |
| JSON válido | 100 | 100 | 100 |
| **Media** | 75.6 | 80.4 | **81.4** |

---

## 6. Resultados sobre fotos de catálogo

### 6.1 Test (500 imágenes no vistas): antes y después del ajuste fino

| Campo | Mayoritaria | Zero-shot (sin afinar) | **Afinado** | Δ frente a zero-shot | IC95 del afinado |
|---|---|---|---|---|---|
| `categoria` | 24.6 | 55.2 | **99.6** | +44.4 | 98.6 – 99.9 |
| `color_primario` | 26.6 | 34.4 | **76.2** | +41.8 | 72.3 – 79.7 |
| `grupo_estilo` | 33.4 | 40.2 (\*) | **90.8** | +50.6 | 87.9 – 93.0 |
| `genero` | 53.6 | 63.4 | **94.0** | +30.6 | 91.6 – 95.8 |
| `temporada` | 56.8 | 58.2 | **60.2** | +2.0 | 55.8 – 64.4 |
| **Media** | 39.0 | 50.3 | **84.2** | +33.9 | |
| JSON válido | — | (texto libre parseado por palabras clave) | **100 %** (500/500) | | |

(\*) El baseline zero-shot usa `casual` por defecto cuando la descripción no menciona estilo, y `casual` es la clase
mayoritaria: es más cercano a «predice la mayoritaria» que a clasificar. Su `temporada` (58.2) está dentro del ruido de la
mayoritaria (56.8), y la del afinado (60.2) también: **el ajuste fino no aporta nada real en `temporada`**.

Latencia en CPU: 6.5 s por imagen (afinado, voraz, ≤ 96 tokens) frente a ≈ 7.8 s del baseline (65 min para 500). La GPU no
se ha medido.

### 6.2 Precisión, recall y F1 por clase (test, afinado)

| `grupo_estilo` | Precisión | Recall | F1 | | `color_primario` | Precisión | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| streetwear | 0.98 | 0.93 | **0.96** | | negro | 0.85 | 0.86 | **0.86** |
| fiesta_noche | 0.95 | 0.96 | **0.95** | | blanco | 0.79 | 0.84 | 0.82 |
| de_vestir | 0.94 | 0.89 | **0.92** | | azul | 0.80 | 0.81 | 0.81 |
| casual | 0.91 | 0.92 | **0.91** | | rojo | 0.74 | 0.83 | 0.78 |
| playa_resort | 0.81 | 0.83 | **0.82** | | rosa | 0.67 | 0.93 | 0.78 |
| deportivo | 0.78 | 0.83 | **0.81** | | amarillo | 0.82 | 0.75 | 0.78 |
| | | | | | camel | 0.76 | 0.76 | 0.76 |
| | | | | | dorado | 1.00 | 0.60 | 0.75 |
| | | | | | verde | 0.71 | 0.77 | 0.74 |
| | | | | | navy | 0.71 | 0.69 | 0.70 |
| | | | | | gris | 0.63 | 0.66 | 0.64 |
| | | | | | lavanda | 0.50 | 0.83 | 0.62 |
| | | | | | naranja | 1.00 | 0.40 | 0.57 |
| | | | | | beige | 0.57 | 0.29 | 0.38 |
| | | | | | burdeos | 0.50 | 0.14 | 0.22 |
| | | | | | **fucsia** | 0.00 | 0.00 | **0.00** |
| | | | | | **plateado** | 0.00 | 0.00 | **0.00** |

`fucsia` y `plateado` valen 0.00 porque casi no hay ejemplos: 4 y 24 imágenes de entrenamiento y 3 y 3 de test.

### 6.3 Comparación con CLIP sobre las 1207 imágenes (corregida)

Las 1207 imágenes de `clip_trend_matching/` salen del **mismo dataset** que train/val/test, y su etiqueta (la carpeta) sale
de la misma regla `articleType → grupo_estilo`. Comparando por contenido de píxeles (60×80, diferencia media < 3):

| Solape de las 1207 con el ajuste fino | Imágenes |
|---|---|
| Ya vistas en **train** | 348 (28.8 %) |
| En val | 38 (3.1 %) |
| En test | 48 (4.0 %) |
| **No vistas** | **773 (64.0 %)** |

Por carpeta, vistas / total: casual 48/250, streetwear 126/200, de_vestir 63/175, fiesta_noche 81/136, deportivo 75/229,
playa_resort 41/217. La contaminación es mayor justo donde el resultado era más llamativo (`fiesta_noche` 60 %,
`streetwear` 63 %).

**Comparación limpia** (`evaluar_solape_1207.py`). Florence-2 afinado solo sobre imágenes **no vistas**, en una muestra
aleatoria (semilla 42) estratificada por carpeta de las 773 (las 55 de `fiesta_noche` y 60–76 del resto: **371 imágenes**;
se paró ahí para acortar el cálculo en CPU, ≈ 4.4 s por imagen), y CLIP zero-shot sobre **esas mismas 371 imágenes**:

| Carpeta | n | CLIP zero-shot | Florence-2 afinado | Diferencia |
|---|---|---|---|---|
| casual | 76 | 14 = 18.4 % | 66 = **86.8 %** | +68.4 |
| streetwear | 60 | 33 = **55.0 %** | 30 = 50.0 % | −5.0 |
| de_vestir | 60 | 52 = **86.7 %** | 34 = 56.7 % | −30.0 |
| fiesta_noche | 55 | 0 = 0.0 % | 50 = **90.9 %** | +90.9 |
| deportivo | 60 | 16 = 26.7 % | 28 = **46.7 %** | +20.0 |
| playa_resort | 60 | 22 = 36.7 % | 29 = **48.3 %** | +11.6 |
| **Total (muestra)** | **371** | 137 = **36.9 %** (IC95 32.2–41.9) | 237 = **63.9 %** (IC95 58.9–68.6) | **+27.0** |
| Ponderado a la composición de las 773 no vistas | 773 | 33.8 % (medido: 261/773) | ≈ 62.5 % (estimado) | ≈ +28.7 |

Prueba pareada sobre las 371 (McNemar): solo acierta Florence en 140, solo CLIP en 40, ambos en 97, ninguno en 94
(χ² = 54.5, p < 0.001).

**Por qué 63.9 % y no el 90.8 % del test.** Las etiquetas de las carpetas coinciden con las del entrenamiento (433 de las 434
imágenes compartidas, 99.8 %), así que no es una regla distinta. La diferencia viene de **qué tipos de prenda contiene la
muestra**: las carpetas se construyeron cubriendo la cola larga de los 135 `articleType`, mientras que el test refleja la
distribución natural (el 59 % del test son tipos con ≥ 200 ejemplos de entrenamiento; en las 371 solo el 26 %). El nombre de
archivo de cada imagen de las carpetas indica su tipo, y con eso se puede medir el acierto según lo visto que sea:

| Ejemplos del tipo de prenda en train | Imágenes no vistas | Acierto de Florence |
|---|---|---|
| 0–9 (gafas de sol 19, sandalias deportivas 14, chándales 13, chalecos 10, bañadores 4) | 60 | **2 = 3 %** |
| 10–49 | 56 | 33 = 59 % |
| 50–199 | 160 | 122 = 76 % |
| ≥ 200 | 95 | 80 = 84 % |

| Subconjunto de las 371 | n | CLIP zero-shot | Florence-2 afinado |
|---|---|---|---|
| Todas | 371 | 36.9 % | 63.9 % |
| Tipos con ≥ 10 ejemplos en train | 311 | 41.8 % (IC95 36.5–47.3) | **75.6 %** (70.5–80.0) |
| Tipos con ≥ 50 ejemplos en train | 255 | 41.6 % (35.7–47.7) | **79.2 %** (73.8–83.7) |
| Tipos con < 10 ejemplos en train | 60 | 11.7 % (7/60) | 3.3 % (2/60) |

Las gafas de sol están en las carpetas pero el entrenamiento las excluyó (no textil). Lectura: el modelo **acierta el estilo
en los tipos de prenda que ha visto y no extrapola a los que no**, lo que refuerza que aprende la regla tipo → estilo (§6.4).

- **La ventaja sobre CLIP es real pero de unos 27–29 puntos, no de 40.6** (73.4 % frente a 32.8 % con la cifra
  contaminada).
- **`fiesta_noche` pasa de 0 % a 90.9 %** y `casual` de 18 % a 87 %: esas son las dos clases donde CLIP fallaba
  sistemáticamente.
- **CLIP sigue ganando en `de_vestir`** (86.7 % frente a 56.7 %; Florence lo manda a `casual` en 19 de 60) y empata en
  `streetwear` (55.0 % frente a 50.0 %; Florence lo manda a `casual` en 15 y a `deportivo` en 9). El afinado no es mejor en todo.
- Estimación **indirecta** de cuánto inflaba el solape: (886 aciertos en las 1207 − ≈ 483 esperados en las 773 no vistas) / 434
  vistas ≈ **93 %** de acierto en imágenes vistas frente a ≈ 62 % en no vistas.
- Aun limpia, esta prueba mide si el modelo reproduce **la misma regla de etiquetado** en imágenes de catálogo no vistas,
  no un criterio de estilo verificado por una persona (§6.4).

### 6.4 Cómo leer el 90.8 % de estilo

No hay motivo para pensar que el modelo ha aprendido «estilo» en abstracto: lo más probable es que reconstruya la regla
`articleType → grupo_estilo` (con `categoria` al 99.6 %). Es un buen resultado *para el catálogo*, pero el atajo
tipo-de-prenda → estilo es justo lo que no estará disponible en una foto de Instagram con el look completo. La revisión
humana (§7) y las fotos de calle (§8) lo confirman.

---

## 7. Revisión humana (app «Ficha de Prenda»)

**Protocolo.** App web («Ficha de Prenda», Artifact de Claude con base de datos compartida, acceso solo con sesión
iniciada) con **120 fichas del test set, 20 por categoría**. Cada ficha llega **pre-rellenada con la etiqueta de Kaggle** y
el revisor la confirma o edita; `color_primario`, `genero`, `temporada` y `grupo_estilo` admiten **selección múltiple**
(mínimo 1). El revisor **no ve la predicción del modelo**. Estado a 2026-09-20 ≈ 11:00: **100 de 120 fichas** revisadas.

Evolución del acuerdo medio del modelo con las etiquetas humanas: n = 33 → 81 %, n = 58 → 78 %, **n = 100 → 79 %**
(estable). Acuerdo humano-Kaggle en `temporada`: 48 % → 47 % → 45 %.

Convención de acierto con selección múltiple: la predicción del modelo (un valor por campo) es correcta si cae dentro del
conjunto que marcó el revisor. Es una regla **permisiva**.

### 7.1 Humano frente a Kaggle (100 fichas)

| Campo | Igual | Añade valores | Cambia | Acuerdo (Kaggle ∈ selección) |
|---|---|---|---|---|
| `categoria` | 99 | 0 | 1 | 99 % |
| `color_primario` | 77 | 20 | 3 | 97 % |
| `genero` | 94 | 0 | 6 | 94 % |
| `grupo_estilo` | 65 | 21 | 14 | 86 % |
| `temporada` | 44 | 1 | 55 | **45 %** |

Solo 16 de 100 fichas coinciden con Kaggle en los cinco campos. Uso de la selección múltiple: color 20 %, estilo 21 %,
temporada 1 %, género 0 %.

### 7.2 Modelo frente a Kaggle y frente al humano

| Campo | Modelo vs Kaggle | Modelo vs humano | IC95 (vs humano) |
|---|---|---|---|
| `categoria` | 99 % | 98 % | 93.0 – 99.4 |
| `color_primario` | 76 % | 81 % | 72.2 – 87.5 |
| `genero` | 96 % | 92 % | 85.0 – 95.9 |
| `grupo_estilo` | 93 % | 80 % | 71.1 – 86.7 |
| `temporada` | 63 % | 44 % | 34.7 – 53.8 |
| **Media** | **85 %** | **79 %** | |
| Media sin `temporada` | 91.0 % | 87.8 % | |

El modelo coincide más con Kaggle que con el humano justo donde Kaggle y el humano difieren (`temporada` 19 puntos, `estilo`
13): reproduce las etiquetas con las que se entrenó, defectos incluidos. En `color` ocurre lo contrario (81 frente a 76)
porque la selección múltiple del humano es permisiva.

### 7.3 `temporada`: el techo lo pone el vocabulario

| Kaggle → humano | Fichas |
|---|---|
| primavera_verano → primavera_verano | 35 |
| otono_invierno → **todo_el_ano** | 28 |
| primavera_verano → **todo_el_ano** | 15 |
| otono_invierno → otono_invierno | 9 |
| otono_invierno → primavera_verano | 9 |
| primavera_verano → otono_invierno | 3 |
| primavera_verano → primavera_verano + todo_el_ano | 1 |

`todo_el_ano` aparece en 44 de 100 fichas y **43 fichas lo tienen como único valor**. Con un vocabulario de 2 valores el
acuerdo máximo posible es 57/100. Sobre esas **57 fichas respondibles**, el modelo acierta 44 (**77 %**) y la etiqueta de
Kaggle 45 (**79 %**): el 44 % de acuerdo global no es fallo del modelo sino de la definición de la etiqueta.

Por tipo de prenda: `Tshirts` 10/10 `primavera_verano`; `Backpacks` 7/8 y `Clutches` 4/4 `todo_el_ano`; `Caps` 5/6
`primavera_verano`; `Casual Shoes` 4/5 `todo_el_ano`; `Jackets` (19) es lo ambiguo: 7 `otono_invierno`, 3 `primavera_verano`, 9
`todo_el_ano`; `Dresses` (16): 8 `primavera_verano`, 7 `todo_el_ano`, 1 `otono_invierno`.

### 7.4 `grupo_estilo`: multietiqueta, `deportivo` con `streetwear`, y los vestidos

- **21 fichas** llevan más de un estilo. La combinación dominante es `deportivo + streetwear` (**10 de 21**), casi siempre
  chaquetas, mochilas, gorras y zapatillas de marcas deportivas; después `casual + streetwear` (4) y `casual + fiesta_noche` (3).
- **Vestidos** (`Dresses`, 16 fichas; Kaggle los marca todos `fiesta_noche`): 11 de 16 incluyen `casual`; solo 4 son
  `fiesta_noche` puro. Los 4 puros son lisos y oscuros o de color liso (*Avirate Black*, *Femella Blue*, *Jealous 21 Black*,
  *Sepia Pink*); los `casual` son estampados, multicolor, en línea A o infantiles. Hay un contraejemplo (*Sepia Women Black
  Dress*, liso negro → `casual`), así que la regla no es limpia.
- De los 20 errores de estilo del modelo frente al humano, **8 son `fiesta_noche` → `casual`** (vestidos y tacones): el modelo
  reproduce fielmente la regla `Dresses → fiesta_noche`.
- **2 fichas son ropa infantil** (*Gini and Jony*): el humano las marca `casual`; Kaggle y el modelo, `fiesta_noche`.

### 7.5 `genero`, `color` y `categoria`

- **Género**: los 6 cambios del humano son todos a `neutro` (2 chaquetas deportivas, 2 zapatillas, unas chanclas y una
  gorra). El criterio parece visual («¿la llevaría cualquiera?»), no el mercado objetivo de la marca. Pero otras dos
  gorras «Men» se mantienen `masculino`, así que no es una regla por tipo de prenda. El modelo falla 8 fichas: en 5 el
  humano puso `neutro` y el modelo repitió el género de Kaggle; en 3 el modelo puso `neutro` donde el humano puso un
  género (2 gorras `masculino` y 1 mochila `femenino`).
- **Color**: 20 de 100 fichas llevan 2–3 colores (rayas, acentos deportivos, packs de 3 camisetas). De los 19 errores del
  modelo, 10 son confusiones dentro de la familia azul/navy/gris/verde/lavanda (p. ej. polo navy a rayas → `lavanda`, gorra
  azul → `lavanda`), 5 entre tonos cálidos o neutros (blanco↔amarillo, rosa↔naranja, camel↔beige/dorado, amarillo↔beige) y
  4 con negro, burdeos o fucsia (una camiseta negra → `verde`). `lavanda` absorbe el `Purple` de Kaggle (1612 filas) y eso
  lo contamina.
- **Categoría**: 1 cambio humano (una chaqueta de forro polar: ¿abrigo o ropa superior?, frontera real de la taxonomía),
  que es uno de los 2 desacuerdos del modelo; el otro es un vestido estampado predicho `ropa_inferior`.

---

## 8. Fotos reales de calle: de la foto entera a los looks

**Datos.** 19 fotos de *street fashion* de Wikimedia Commons (personas con el outfit puesto y fondo real; otras 11 se
descartaron). Atribuciones en `data/fotos_calle/ATRIBUCIONES.txt`. Las imágenes **no se suben al repo** (personas
identificables; se regeneran con `descargar_fotos_calle_wikimedia.py`).

### 8.1 Por qué se espera una caída

El clasificador solo ha visto **una prenda por foto, sin fondo, en encuadre de catálogo**. El estilo es una propiedad del
*look* completo. Una zapatilla sola no dice «streetwear»; zapatilla + vaquero ancho + sudadera, sí.

### 8.2 Diagnóstico: el clasificador sobre la foto entera

| Campo | Predicción sobre las 19 fotos enteras |
|---|---|
| `categoria` | `accesorio` **12** (63 %), `calzado` 4, `cuerpo_entero` 2, `ropa_superior` 1 |
| `temporada` | `primavera_verano` **19/19** (constante) |
| `color_primario` | `negro` 12 (63 %), gris 2, rosa 2, azul 1, blanco 1, amarillo 1 |
| `grupo_estilo` | `streetwear` 9, `fiesta_noche` 8, `casual` 2 |

`accesorio` es un atajo de *layout* («objeto pequeño en escena grande»), no de prenda. El único caso limpio (una persona,
una prenda, fondo neutro) sale bien en los cuatro campos.

### 8.3 Prototipo de looks (`analizar_outfit.py`)

> **Aviso de versión (añadido en §11.6):** el «v2» de esta sección es la versión del *script* de
> detección (las guardas heurísticas de más abajo), no la del adapter clasificador — nombre
> desafortunado, coincide por casualidad con `florence2_base_lora_v2/`. Esta sección se corrió
> con el adapter **v1** (el único que existía en ese momento de la sesión, antes de las
> decisiones de esquema de §11.1). Con el adapter **v3** (mejor acuerdo medio con el humano,
> §11.4) los recortes deberían clasificarse mejor sin tocar nada de la detección — no se ha
> vuelto a correr todavía, ver §11.6.

Mismo modelo con dos capacidades y sin entrenar nada nuevo:

1. **Detectar** (adapter *desactivado*, Florence-2 base nativo): `<OD>` para personas y las prendas que sabe nombrar
   (calzado, pantalón, falda, vestido, chaqueta, gorro, bolso); `<CAPTION_TO_PHRASE_GROUNDING>` con **una** frase
   («shirt», «pants») sobre el recorte de cada persona para la prenda superior y el pantalón que `<OD>` casi nunca da.
   Con varias palabras a la vez devuelve una caja por palabra aunque no esté la prenda, por eso se pide una cada vez.
2. **Clasificar** (adapter *activado*): cada recorte pasa por `<ATRIBUTOS_PRENDA>`, igual que en el entrenamiento.
3. **Agregar**: el estilo del look es el voto de los `grupo_estilo` de sus prendas, ponderado por la raíz del área relativa.
   La **categoría de cada prenda la da el detector**, no el clasificador (ver 8.4).

Versión 1 (primera pasada) → versión 2: tras ver los fallos de la v1 sobre estas mismas 19 fotos se añadieron cinco guardas:
(i) una caja de «prenda superior» que abarca a casi toda la persona se sustituye por el torso geométrico; (ii) se descartan
personas por debajo del 12 % del área de la principal (una figura desenfocada y una persona cortada por el borde);
(iii) el calzado solo se agrupa si el par está junto; (iv) el pantalón por *grounding* debe empezar en la mitad baja;
(v) en primeros planos (persona ≥ 85 % de la foto) no se busca pantalón ni torso geométrico. Según mi inspección visual la
v1 tenía ≈ 8 cajas erróneas de 90 (33 personas); la v2 tiene 2 de 86 (31 personas). **Esas guardas están ajustadas a estos
fallos concretos: las cifras siguientes son en muestra.**

### 8.4 Resultados (v2, 19 fotos, 31 personas)

**Detección.** 86 prendas (2.8 por persona): calzado 28, ropa inferior 24, ropa superior 18, abrigo 8, cuerpo entero 6,
accesorio 2. Origen de la caja: `<OD>` 61 (71 %), *grounding* 20 (23 %), torso geométrico 5 (6 %).

**Auditoría manual** (hecha **por Claude** mirando las fotos anotadas, no por el autor; ficheros
`data/revision_humana/auditoria_outfit_calle.json` y `outfits_fotos_calle_v2.json`; pendiente de que el autor la valide):

| Métrica | Resultado | IC95 |
|---|---|---|
| Cajas correctas / parciales / erróneas | **80 (93 %)** / 4 (5 %) / 2 (2 %) | 86 – 97 |
| Cajas correctas por origen | `<OD>` 57/61, *grounding* 18/20, geométrico 5/5 | |
| Color correcto en cajas correctas (familias cercanas admitidas) | **67/78 = 86 %** | 76 – 92 |
| Prendas básicas visibles sin ninguna caja | 2 de 84 → recall **98 %** | 92 – 99 |
| Personas visibles detectadas | 31 de 31 (por construcción, ver §9) | |

**Frente a la lectura de la foto entera** (el clasificador sobre los mismos píxeles):

| | Foto entera | Looks por prenda (v2) |
|---|---|---|
| Prendas consideradas | 1 (una `categoria`) | 86 (2.8 por persona) |
| `accesorio` como categoría del clasificador | 12/19 fotos (63 %) | 19/84 recortes (23 %) |
| Categoría del clasificador = categoría del detector | — | 59/84 = **70 %** (superior 39 %, abrigo 38 %, inferior 79 %, calzado 85 %, cuerpo entero 100 %) |
| `temporada` | 19/19 `primavera_verano` | 83/84 `primavera_verano` (abrigos de pelo incluidos) |
| `color_primario` `negro` | 63 % de las fotos | 56 % de los recortes (47/84) |
| Estilo dentro de lo aceptable, persona principal | **13/19 = 68 %** | **16/19 = 84 %** |
| Estilo dentro de lo aceptable, todas las personas | — | 23/31 = 74 % |

Los estilos aceptables (1–2 por persona, criterio de Claude) figuran en el fichero de auditoría. La diferencia de 3 fotos
sobre 19 (IC95 de 16/19: 62–94; de 13/19: 46–85) **no es estadísticamente significativa**. Lo que cambia es la
estructura: el baseline predecía `fiesta_noche` en 8 de 19 fotos (solo 4 lo son: vestidos de lentejuelas o de gala) y el
look por prendas lo corrige en 3 fotos casuales (calle_02, calle_05, calle_20); no empeora ninguna.

**Fallos que persisten**

- El clasificador llama `accesorio` a 11 de las 26 camisetas y abrigos puestos (recortes con piel, pelo y fondo, distintos de
  un producto sobre fondo blanco). Por eso la categoría se toma del detector.
- `temporada` es inservible (todo `primavera_verano`), incluidos abrigos de pelo.
- Color: 11 errores en las 78 cajas correctas: blazers negros leídos como `camel` (2), pantalones o shorts negros como
  `azul` (2), vaqueros azules como `negro` (1) y prendas estampadas o poco habituales (blusa multicolor, medias de rayas,
  botas beige, tacones metalizados, camiseta blanca → `beige`, abrigo marrón → `rojo`).
- Estilo ambiguo: minivestidos de tirantes en un centro comercial (`fiesta_noche` del modelo, `casual`/`playa_resort` mío),
  camiseta blanca + bolso beige (`fiesta_noche`), look editorial blanco con tacones rosas.
- Capas: una chaqueta abierta sobre una camiseta produce una sola caja (se descarta la camiseta por solape).
- Fondo: personas parcialmente visibles solapadas (calle_19) producen cajas ruidosas.

**Tiempo:** ≈ 41 s por foto en CPU sin caché (`<OD>` con 3 haces + *grounding* + clasificación de cada recorte).

---

## 9. Limitaciones y amenazas a la validez

1. **Etiquetas de catálogo = reglas, no anotaciones.** El 90.8 % de estilo y el 99.6 % de categoría miden cuánto reproduce
   el modelo el mapeo `articleType → etiqueta`, no un criterio de moda.
2. **Test de la misma distribución y con las mismas reglas** que el entrenamiento; no mide generalización a otros catálogos.
   Además refleja la distribución natural de tipos de prenda: **el estilo cae a 3 % en tipos con < 10 ejemplos de
   entrenamiento y a 59 % con 10–49** (§6.3), un dato que el 90.8 % del test esconde.
3. **Solape con la comparación de CLIP** (corregido en §6.3 y §10).
4. **Revisión humana** parcial (100/120), de un único revisor, **con etiquetas pre-rellenadas** (efecto de anclaje hacia
   Kaggle: el acuerdo con Kaggle es una cota superior) y regla de acierto permisiva con selección múltiple.
5. **Fotos de calle: 19 fotos, 31 personas.** Sin etiquetas humanas: auditoría de Claude con «estilos aceptables» subjetivos;
   guardas ajustadas mirando esas mismas fotos (en muestra); `personas visibles` se cuentan con el mismo criterio que la
   detección (recall de personas no informativo). Wikimedia no representa la diversidad de una cuenta real de moda.
6. **Una sola ejecución de entrenamiento** (semilla 42, un adapter): no hay varianza entre semillas.
7. **No se ha comparado con un LLM comercial** con el mismo esquema (la justificación empírica de «modelo propio»).
8. **Licencia**: el dataset de Kaggle no tiene licencia libre explícita; las fotos de calle son de Wikimedia (CC), citadas.

---

## 10. Correcciones a lo dicho antes

- **Comparación con CLIP (73.4 % frente a 32.8 %).** Se presentó como «prueba de generalización real porque el modelo nunca
  vio esas imágenes». **Era incorrecto**: comparten dataset y regla de etiquetado con el entrenamiento y el 36 % (434 de
  1207) son imágenes que el modelo afinado ya había visto (348 en train). El 73.4 % queda como cifra contaminada y se
  sustituye por la medida sobre las no vistas: **63.9 % frente a 36.9 % de CLIP** en 371 imágenes (§6.3).
- **«Alrededor de la mitad plausibles» en `grupo_estilo` de las fotos de calle** (README, primeros hallazgos): era una
  valoración a ojo. Con los estilos aceptables definidos en §8 la lectura de la foto entera da 13/19 (68 %).

---

## 11. Decisiones abiertas y próximos pasos

### 11.1 Decisiones tomadas e implementadas (2026-09-20, dataset v2)

El autor resolvió las cinco dudas de la primera versión de esta sección. Cambios ya
implementados en `herramientas/preparar_dataset_florence2.py` y documentados en
`esquema_atributos.md`; **`data/{train,val,test}.jsonl` ya está regenerado con las reglas
nuevas (v2)**. El adapter `modelos/florence2_base_lora_v1/` —y por tanto todos los
resultados de §6–§8 de este documento— sigue siendo el entrenado con las reglas **v1**
(anteriores a esta fecha); el adapter v2, ya entrenado sobre estas reglas nuevas, y su
comparación campo a campo con v1, están en §11.2.

| Tema | Decisión del autor | Qué se implementó |
|---|---|---|
| `genero` = `neutro` | «Así es» — es un criterio visual («¿lo llevaría cualquiera?»), no el mercado objetivo de la marca | **Sin cambio de código**: no hay tabla de reglas que traduzca ese criterio, así que la etiqueta de entrenamiento sigue siendo la de Kaggle (`Men/Women/Unisex`); la discrepancia queda documentada en `esquema_atributos.md` |
| `temporada` de chaquetas | «Vamos a suponerlas de todas las estaciones, independientemente de lo que pusiese yo [en la revisión]» | `articleType == Jackets` → `todo_el_ano` siempre, ignorando el `season` de Kaggle. El resto de tipos se queda con el mapeo de 2 valores — **sigue pendiente** (ver tabla de abajo) |
| `deportivo` + `streetwear` | «No quiero marcas, no» (rechaza reetiquetar por marca deportiva) | Sin cambio: `grupo_estilo` se queda de una sola etiqueta; el solape (10/21 fichas multietiqueta) queda como limitación documentada, no resuelta |
| Vestidos → `fiesta_noche` o `casual` | «De noche suelen ser de un único color, más planos y quizás brillantes en algunos casos» | Regla nueva por `productDisplayName`: palabra de patrón (`printed`, `striped`, `floral`, `polka/dot`, `checked`, `multi/colour`, `animal`, `a-line`, `tiered`, `ruffle`) → `casual`; sin ella (liso) → `fiesta_noche`. Validada contra la revisión humana: **13 de 14** vestidos no infantiles. La parte de «brillante» no se pudo afinar: no hay ninguna palabra de purpurina/lentejuelas/metalizado en los nombres de este catálogo |
| Paleta de color | «Intentaría no hacer modificaciones tan profundas en Estado_arte» | Sin cambio de vocabulario: `lavanda` sigue absorbiendo `Purple`, no se añade `morado`. `fucsia`/`plateado` (F1 0.00 en v1) solo se pueden atacar sobremuestreando |

**De propina, un defecto real encontrado al implementar esto** (no estaba en la lista de dudas):
al mirar por qué la regla de `Dresses` fallaba tanto, salió que **713 filas de las 44 072**
(108 de las 464 `Dresses`, 23 %) son ropa infantil con `gender = Women` o `Men` — el filtro
existente solo excluía `gender ∈ {Boys, Girls}` (3.3 %), y marcas como *Gini and Jony* o
*Doodle Kids* se etiquetan con `Women`/`Men` en Kaggle y se colaban. Se añadió un filtro por
`productDisplayName` (§`esquema_atributos.md`). Efecto: el pool de filas mapeables baja de
24 798 (56.3 %) a **24 215 (54.9 %)**.

**Dataset v2, splits regenerados (misma semilla 42, mismo tamaño 4000/500/500):**

| `grupo_estilo` | train v1 → v2 | | `temporada` | train v1 → v2 |
|---|---|---|---|---|
| casual | 1375 → **1442** | | primavera_verano | 2271 → 2176 |
| streetwear | 849 → 847 | | otono_invierno | 1729 → 1619 |
| fiesta_noche | 592 → **517** | | **todo_el_ano** | 0 → **205** |
| de_vestir | 505 → 520 | | | |
| deportivo | 417 → 420 | | `categoria` `abrigo` | 209 → 205 |
| playa_resort | 262 → 254 | | | |

`fiesta_noche` baja (parte de los vestidos pasan a `casual`) y `todo_el_ano` aparece con
exactamente 205 filas en train — el mismo número que `abrigo`/`Jackets`, lo que confirma que la
regla nueva solo toca esa categoría y no tiene fugas a otras.

**Lo que sigue sin decidir** (no se preguntó o no se resolvió del todo):

| Tema | Por qué sigue abierto |
|---|---|
| `temporada` del resto de tipos de prenda (`Dresses` incluido) | Solo se decidió `Jackets`; `Dresses` reparte 8 primavera-verano / 7 todo el año / 1 otoño-invierno en la revisión humana, sin criterio claro |
| `grupo_estilo` multietiqueta de verdad (JSON con lista) | Se rechazó la vía por marca, pero no se preguntó si se quiere multietiqueta por otra vía |
| Vestidos «brillantes» | Sin datos en este catálogo para validar esa parte de la regla |

### 11.2 Reentrenamiento v2: resultado real (2026-09-20)

Entrenado en Kaggle (GPU, ≈ 54 min con descarga de dataset incluida; 0.40–0.41 s/paso, igual de
rápido que la T4 de Colab en v1) en vez de Colab — ver §11.3 para el porqué y cómo. Mismo dataset
v2 de §11.1, mismos hiperparámetros que v1 (r=16, α=32, 3 épocas, batch efectivo 16). Época con
mejor accuracy media en validación: **época 2** (81.4 %; en v1 fue la época 3, también 81.4 %).

| Campo | Val, mejor época (v1 / v2) | Test 500 (v1 → **v2**) | Δ | IC95 (v2) |
|---|---|---|---|---|
| `categoria` | 98.4 / 98.2 | 99.6 % → **98.0 %** | −1.6 | 96.4–98.9 |
| `color_primario` | 72.6 / 73.0 | 76.2 % → **72.0 %** | −4.2 | 67.9–75.8 |
| `grupo_estilo` | 88.0 / 85.8 | 90.8 % → **86.8 %** | −4.0 | 83.6–89.5 |
| `genero` | 90.4 / 90.4 | 94.0 % → **94.2 %** | +0.2 | 91.8–95.9 |
| `temporada` | 57.8 / 59.6 | 60.2 % → **60.2 %** | 0.0 | 55.8–64.4 |
| JSON válido | 100 / 100 | 100 % → **100 %** | — | |
| Latencia (GPU Kaggle) | — | — → **1.00 s/imagen** | (v1: 6.5 s/imagen en CPU) | |

**v2 no es mejor que v1 en el test global — es ligeramente peor en tres campos, salvo en lo que se
pidió arreglar.** Con una sola repetición por versión (sin varias semillas) no se puede separar
del todo señal de ruido, pero hay una lectura razonable campo a campo:

- **`grupo_estilo` (−4.0 puntos) es la caída más esperable y la más fácil de explicar**: v1 podía
  acertar `Dresses` con el atajo `tipo de prenda → fiesta_noche` sin mirar la imagen (§6.4); v2 le
  quita ese atajo (necesita leer si el vestido está estampado) — es una tarea más difícil y más
  honesta, no un fallo del entrenamiento. Consistente con la caída: `fiesta_noche` mejora su
  recall (0.96) a costa de la precisión (0.80, era 0.95 en v1) — señal de que ahora hay que
  *distinguir* en vez de aplicar la regla siempre.
- **`color_primario` (−4.2 puntos) es la que más preocupa**: en v1 solo `fucsia` y `plateado`
  tenían F1 0.00; en v2 se les unen **`burdeos`, `dorado` y `naranja`** (antes 0.22–0.57 de F1).
  Estas cinco clases ya eran las de menos ejemplos en train (todas por debajo de 60 filas) —
  compatible con varianza de una sola repetición sobre clases con poquísimos datos, pero no
  descartable como regresión real hasta repetirlo. Sigue siendo el punto de la lista de §11.1
  ("sobremuestrear la cola larga") el que más urge.
- **`categoria` (−1.6) y `temporada` (0.0)** están dentro de lo esperable: `categoria` pierde 10
  aciertos de 500 (ruido plausible), y `temporada` no tenía por qué cambiar en el agregado — la
  única regla nueva es de `Jackets`, una fracción pequeña del test (aunque sí aparece por primera
  vez `todo_el_ano` con señal, 205 filas de train con esa etiqueta exacta; no se ha medido todavía
  el acierto específico en esa clase, `evaluar_modelo.py` no da F1 por clase de `temporada`).
- **`genero` (+0.2, sin cambio real)**: como se documentó en §11.1, la etiqueta de entrenamiento
  para `genero` no cambió en v2 (se mantiene la de Kaggle) — este número es la confirmación de que
  no cambió nada ahí, no una mejora.

**Conclusión honesta**: las tres reglas que pidió el autor están implementadas y el modelo entrena
igual de bien en conjunto (accuracy media en el mejor punto de validación: 81.4 % en ambas), pero
el test global de v2 no es un "v1 pero mejor" — es un modelo que ya no hace trampa en un campo
(`grupo_estilo`) a cambio de una tarea más difícil, con una caída en `color_primario` que necesita
más datos para las clases raras antes de poder decir si es ruido o un problema real. **v1, v2 y v3
se quedan los tres en el repositorio** (`modelos/florence2_base_lora_v1/`, `_v2/`, `_v3/`) para
poder comparar.

**Contraste pareado contra las 100 fichas revisadas a mano** (`herramientas/comparar_modelos.py`;
mismas 100 fotos para los tres modelos, así que la comparación no la contamina un test set distinto):

| Campo | v1 vs humano | v2 vs humano | Fichas que pierden / ganan (v1→v2) |
|---|---|---|---|
| `categoria` | 98 % | 97 % | 1 / 0 |
| `color_primario` | **81 %** | **81 %** | 3 / 3 |
| `genero` | 92 % | 91 % | 1 / 0 |
| `temporada` | 44 % | 38 % | 16 / 10 |
| `grupo_estilo` | 80 % | 79 % | 2 / 1 |
| **Media** | 79 % | 77 % | |

**Esto cambia la lectura de §11.2 arriba: la caída de `color_primario` del test de 500 (−4.2 puntos)
no se reproduce contra el humano en estas 100 fichas — se queda exactamente en 81 % los dos, con
tantas fichas que pierden como que ganan.** Es un indicio (n=100, no concluyente) de que la caída del
test grande es más ruido de qué imágenes concretas de las clases raras cayeron en el test que una
pérdida real de calidad — aunque el fallo aislado que sí aparece es justo de una clase débil (una
chaqueta naranja: v1 acierta `naranja`, v2 dice `amarillo`). `grupo_estilo` tampoco se mueve de
forma real (80 %→79 %, ruido de una ficha). **`temporada` sí cae de forma real (44 %→38 %), y es la
consecuencia esperada, no un fallo**: el autor pidió `todo_el_ano` fijo para `Jackets`
*"independientemente de lo que pusiese yo [en la revisión]"* — el modelo ahora ignora a propósito
el juicio caso a caso que él mismo dio por ficha, así que comparar contra esas mismas respuestas
antiguas tenía que bajar. Con las 20 fichas de `Jackets` pesando el 20 % de esta muestra reducida
(no de la distribución real del catálogo), el efecto se nota más aquí que en el test de 500.

### 11.3 Cómo se entrenó v2 (nota técnica, para la sección de método)

No se usó Colab para este run (el autor estaba sin acceso a su ordenador y Colab no se maneja
cómodamente desde el navegador móvil): se entrenó vía la **API de Kaggle** con un script propio
(`herramientas/kaggle_kernel/`, documentado en su propio `README.md`) que hace exactamente los
mismos pasos que `notebook_colab_entrenamiento.ipynb` (clonar el repo, instalar dependencias,
regenerar `data/*.jsonl`, `entrenar_lora.py`, `evaluar_modelo.py`) pero como un script no
interactivo lanzado por API, sin manejar ningún notebook a mano. Detalle porque no es solo una
curiosidad de esta sesión: es una vía de entrenamiento reproducible alternativa a Colab, ya
probada y documentada, disponible para el siguiente reentrenamiento.

### 11.4 `temporada` del resto de tipos: decisión y dataset v3 (2026-09-20, misma noche)

Pendiente desde §11.1: `Jackets` era el único tipo con regla de `temporada` decidida; el resto
se quedaba con el mapeo de 2 valores de Kaggle. Se construyó un artifact,
**"Reglas de temporada"** (`herramientas/generar_panel_temporada.py`), con una tarjeta por
`articleType` (1-2 fotos de ejemplo de las mismas fichas ya revisadas, la combinación de
respuestas que dio el autor para ese tipo, y una propuesta ya calculada — mayoría clara de
`todo_el_ano` o de una sola estación → esa regla; sin patrón, como `Dresses`, → se deja el
mapeo actual). Decidir es tocar una de 3 opciones; revertir es tocar otra vez, sin paso aparte
(pedido explícito: "que sea cómodo desde el móvil"). `herramientas/leer_reglas_temporada.py`
recoge las decisiones y genera el fragmento de código.

De las 22 propuestas (21 tipos + el valor por defecto), el autor **confirmó 21 y corrigió 1**
— `Caps`, de mi propuesta `estacional` (83 % de sus revisiones eran `primavera_verano`) a
`todo_el_ano`. `TIPOS_TODO_EL_ANO` pasa de 1 tipo
(`Jackets`) a **13**: `Jackets, Caps, Backpacks, Casual Shoes, Clutches, Formal Shoes, Heels,
Jeans, Shirts, Sports Shoes, Sweaters, Track Pants, Trousers`. El resto (`Dresses, Flip Flops,
Jumpsuit, Leggings, Sandals, Shorts, Skirts, Tops, Tshirts` y cualquier tipo no revisado) se
queda con el mapeo de 2 valores por `season` de Kaggle. Implementado en
`preparar_dataset_florence2.py`, detalle de cada tipo en `esquema_atributos.md`.

**Efecto en el dataset (v3): `temporada` cambia de clase minoritaria a clase mayoritaria.**
Esos 13 tipos cubren una parte grande del catálogo (casi todo `calzado` y `accesorio`, gran
parte de `ropa_superior`/`ropa_inferior`) — `todo_el_ano` pasa de 205/4000 (5.1 %, solo
`Jackets`) a **2422/4000 (60.6 %)** en train, con `primavera_verano` en 25.3 % y
`otono_invierno` en 14.1 %. La clase mayoritaria trivial de `temporada` en test sube de 56.8 %
(v1/v2) a **63.4 %** — el listón para que `temporada` "acierte algo" en vez de solo predecir la
mayoritaria es ahora más alto, hay que tenerlo en cuenta al leer la accuracy de v3.

**Resultado real del entrenamiento (Kaggle GPU, mismo día, ≈ 55 min).** Época con mejor
accuracy media en validación: **época 3** (87.3 %, la más alta de las tres versiones — v1 y v2
llegaron a 81.4 %).

| Campo | Test 500 (v1 → v2 → **v3**) | F1 `color_primario`/`grupo_estilo` peores/mejores clases (v3) |
|---|---|---|
| `categoria` | 99.6 % → 98.0 % → **97.8 %** | |
| `color_primario` | 76.2 % → 72.0 % → **73.4 %** | `fucsia`/`dorado`/`naranja`/`plateado` en 0.00; `negro` 0.83, `azul` 0.82 |
| `grupo_estilo` | 90.8 % → 86.8 % → **86.8 %** | `deportivo` 0.72 el más bajo; `streetwear` 0.92 el más alto |
| `genero` | 94.0 % → 94.2 % → **92.4 %** | |
| `temporada` | 60.2 % → 60.2 % → **85.6 %** | muy por encima del 63.4 % trivial (+22.2 puntos, frente a los +3.4 de v1/v2) |
| JSON válido | 100 % → 100 % → **100 %** | |

**Contraste pareado contra las 100 fichas revisadas a mano** (`herramientas/comparar_modelos.py`,
ahora con las tres versiones a la vez):

| Campo | v1 vs humano | v2 vs humano | **v3 vs humano** |
|---|---|---|---|
| `categoria` | 98 % | 97 % | 98 % |
| `color_primario` | 81 % | 81 % | **84 %** |
| `genero` | 92 % | 91 % | 92 % |
| `temporada` | 44 % | 38 % | **68 %** |
| `grupo_estilo` | 80 % | 79 % | 81 % |
| **Media** | 79 % | 77 % | **85 %** |

**v3 es la mejor de las tres versiones contra el humano en casi todos los campos, no solo en
`temporada`.** El salto de `temporada` es real y grande: de v2 a v3, **33 fichas pasan de fallo
a acierto y solo 3 al revés** (de v1 a v3, la comparación es igual de favorable). Tiene sentido
que compense tanto: antes solo `Jackets` tenía la regla, ahora 13 tipos — mucha más superficie
del catálogo donde el modelo deja de intentar adivinar una estación que ni Kaggle ni el humano
tienen claro y en su lugar aprende una relación mucho más fácil de aprender (tipo de prenda →
`todo_el_ano`), la misma clase de atajo que ya explica el buen resultado de `categoria` y
`grupo_estilo` (§6.4). **`temporada` vs Kaggle cae a la vez a 28 %** (v1: 63 %, v2: 49 %) — es
la otra cara del mismo cambio: para esos 13 tipos, v3 ignora a propósito la estación de Kaggle
que antes coincidía a veces por casualidad, así que el desacuerdo con Kaggle sube exactamente
donde baja el desacuerdo con el humano.

`color_primario` también mejora de verdad (81 %→84 %, 5 fichas ganan por 2 que pierden de v2 a
v3) — dato a favor de que la caída del test de 500 sigue siendo más ruido de clases raras que
una tendencia real. **`fucsia`/`dorado`/`naranja`/`plateado` siguen en F1 0.00 en las tres
versiones** — sobremuestreo real en §11.5.

### 11.5 Sobremuestreo de colores raros: dataset y adapter v4 (2026-09-20, más tarde)

`fucsia`, `dorado`, `naranja`, `plateado` (F1 0.00) y `burdeos` (F1 bajo) llevaban así las tres
versiones. La causa no es un mal reparto del muestreo estratificado: **el dataset entero tiene
pocas filas de esos colores** — `fucsia` solo 50 de las 24215 filas mapeables (0.2 %), frente a
5684 de `negro`. Ningún muestreo por `categoria` iba a darle a `fucsia` más de un puñado de
ejemplos porque no hay más que reservar.

**Cambio (solo de muestreo, ninguna regla nueva):** `preparar_dataset_florence2.py` reserva
aparte, antes del muestreo por `categoria`, hasta 200 filas de cada uno de esos 5 colores (todas
las que haya si hay menos — `fucsia` da sus 50) y las mezcla con el resto antes de repartir en
train/val/test. Resultado en train: `fucsia` 4→**39**, `dorado` ~46→**156**, `naranja` ~50→**186**,
`plateado` ~25→**153**, `burdeos` ~49→**184**. `categoria` se resiente un poco (`calzado` sube de
21.7 % a 25.8 % del train, porque esos colores no se reparten igual entre tipos de prenda) pero
sin romperse.

**Resultado del entrenamiento (Kaggle GPU, mismo día).** Mejor época en val: 3 (87.5 %, en línea
con v3). F1 de `color_primario` en el test de 500, antes → después del refuerzo:

| Clase | v1/v2/v3 | **v4** |
|---|---|---|
| `naranja` | 0.00 (las tres) | **0.87** — la mejor de las 17 clases |
| `dorado` | 0.00 (las tres) | **0.69** |
| `plateado` | 0.00 (las tres) | **0.56** |
| `burdeos` | 0.22–0.45 | 0.45 |
| `fucsia` | 0.00 (las tres) | **0.00** — sigue igual, esperable: son 50 imágenes en *todo* el dataset, no hay más que reservar por mucho que se reorganice el muestreo |

**Pero no es una victoria limpia: `color_primario` cae contra el humano (84 %→75 %, contraste
pareado en las 100 fichas) y con eso la media también (85 %→82 %).** No es ruido —10 fichas
pasan de acierto a fallo por solo 1 en sentido contrario, muy distinto del vaivén 5-vs-2 que se
vio de v2 a v3. Mirando las 10 que pierde, hay un patrón: 3 son `negro`→`gris`, 2 son
`navy`→`azul`, 2 son un color cualquiera→`dorado`. Reforzar 4 clases (de ~2-6 % del train cada
una a ~4-5 %) desplaza a ~700 filas de otros colores dentro del presupuesto fijo de 4000 —
mueve la frontera de decisión y arrastra clases visualmente próximas (`negro`/`gris`,
`navy`/`azul`, tonos cálidos/`dorado`) aunque no se tocara su muestreo. `temporada` (68 %→66 %)
y `grupo_estilo` (81 %→82 %) se mueven poco, dentro de ruido.

**Conclusión: es un trade-off real, no un v3-pero-mejor.** Arregla de verdad 3 de las 5 clases
que llevaban rotas desde v1 (F1 0.00→0.56-0.87), a costa de una pérdida medible en el resto de
`color_primario`. **v3 sigue siendo la versión con mejor acuerdo global con el humano (85 %)**;
v4 es la que mejor cubre la paleta completa pero con peor acuerdo medio (82 %). Los cuatro
adapters se quedan en el repositorio — cuál usar depende de si importa más acertar de media o
no fallar sistemáticamente en cuatro colores completos.

### 11.6 Trabajo técnico

1. ~~Reentrenar v2~~ — **hecho** (§11.2), vía Kaggle en vez de Colab (autor sin acceso a
   ordenador; Colab no es manejable cómodamente desde el navegador móvil). Detalle en §11.3.
2. ~~`temporada` del resto de tipos de prenda~~ — **decidido y reentrenado como v3** (§11.4).
3. ~~Sobremuestrear la cola larga de colores raros~~ — **hecho como v4** (§11.5): arregla
   `naranja`/`dorado`/`plateado` (F1 0.00→0.56-0.87) pero `color_primario` cae en conjunto
   (84 %→75 % contra el humano) — **v3 se queda como la versión de mejor acuerdo medio (85 %)**;
   v4 es la alternativa si lo que importa es no fallar sistemáticamente en esos colores.
   `fucsia` sigue en F1 0.00 (solo 50 imágenes en todo el dataset, no se arregla remuestreando).
4. **Terminar las 20 fichas** (autor) y reejecutar `analizar_revision_humana.py`.
5. Sobremuestrear también la cola larga de **tipos de prenda** (no solo colores): el estilo cae
   al 3 % en tipos con menos de 10 ejemplos de entrenamiento (§6.3).
6. **Repetir el prototipo de looks (§8) con el adapter v3**, ahora que existe y es mejor que el
   v1 con el que se midió §8.4 — mismo `analizar_outfit.py`, que ya apunta a v3 por defecto;
   no hace falta reentrenar nada, solo volver a correrlo sobre las 19 fotos de calle. Barato,
   pendiente de hacer.
7. **Looks, la pieza grande**: sustituir las heurísticas de detección por un **detector de
   prendas afinado** (DeepFashion2, el candidato de §12.2 de `Estado_arte.md`) y afinar el
   clasificador con **recortes reales**; para medirlo, una app v2 que muestre el recorte y pida
   validar la prenda (categoría, color, estilo) sobre fotos de calle. Es la pieza pendiente de
   verdad: todo lo de v1-v4 se mide sobre catálogo, no sobre fotos reales de redes sociales —
   el objetivo original de todo este componente (§1).
8. **Comparar con Claude/Gemini** en el mismo test y esquema (opcional, coste de API): es el
   dato que responde a «no vale usar Claude directamente».
9. Actualizar §6.3/§7 de `Estado_arte.md` **solo si el autor lo pide**.

---

## 12. Reproducibilidad

```bash
cd experimentos/vlm_atributos_prenda
pip install -r requirements.txt          # transformers==4.51.3 fijado a propósito
cd herramientas
python3 preparar_dataset_florence2.py    # train/val/test.jsonl v4 (reglas de §11.1 + §11.4, muestreo de §11.5), semilla 42
python3 estadisticas_dataset.py          # tablas de la sección 4 (v1) / 11.1, 11.4 y 11.5 (v4)
python3 baseline_zero_shot.py            # ≈ 65 min en CPU (500 imágenes) -- resultado v1, no se ha repetido en v2/v3/v4
#   entrenamiento v1 (documentado en §5-§10): notebook_colab_entrenamiento.ipynb -> florence2_base_lora_v1/
#   entrenamiento v2/v3/v4 (documentado en §11.2-§11.5): mismo notebook -> florence2_base_lora_v4/, o
#   herramientas/kaggle_kernel/ (API de Kaggle, sin notebook, VERSION="v4" en entrenar_en_kaggle.py) -- ver su README.md
python3 evaluar_modelo.py --adapter ../modelos/florence2_base_lora_v1   # resultados de §6 (por defecto usa v1)
python3 evaluar_modelo.py --adapter ../modelos/florence2_base_lora_v4 --sin-zero-shot --sin-1207  # resultados de §11.5
python3 evaluar_solape_1207.py           # solape con train/val/test y comparación con CLIP sin contaminación (v1)
python3 analizar_revision_humana.py --revisiones ../data/revision_humana/revisiones_app_n100_2026-09-20.json
python3 comparar_modelos.py --revisiones ../data/revision_humana/revisiones_app_n100_2026-09-20.json  # v1/v2/v3/v4 pareado, §11.2/§11.4/§11.5
python3 predecir_lote.py --carpeta ../data/fotos_calle --salida calle.json
python3 analizar_outfit.py --carpeta ../data/fotos_calle --salida-json outfits.json --salida-imagenes anotadas --cache cache.json
python3 resumen_outfit.py --outfits outfits.json --foto-entera ../data/revision_humana/predicciones_fotos_calle.json \
    --auditoria ../data/revision_humana/auditoria_outfit_calle.json
```

**Aviso de versión del dataset**: `preparar_dataset_florence2.py` regenera `data/*.jsonl` con las reglas **v4** (§11.1 +
§11.4, muestreo de §11.5) — es lo que hay en el repositorio ahora, y es lo que se usó para entrenar y evaluar
`florence2_base_lora_v4/`. Los adapters `modelos/florence2_base_lora_v1/`, `_v2/` y `_v3/` se entrenaron con reglas o
muestreo anteriores; sus resultados documentados en §6–§8, §11.2 y §11.4 no son reproducibles ejecutando
`evaluar_modelo.py`/`evaluar_solape_1207.py` tal cual ahora (test set con contenido distinto) — esas versiones exactas
de `data/*.jsonl` quedan recuperables del historial de git si hace falta.

Datos en el repositorio: `data/{train,val,test}.jsonl` (v4), `data/revision_humana/` (revisiones humanas, manifest de la
app, predicciones del modelo por versión `predicciones_app_120[_v2|_v3|_v4].json`, salida y auditoría de los looks),
`data/eval_1207_solape.json` (v1), `modelos/florence2_base_lora_v1/`, `_v2/`, `_v3/` y `_v4/` (los cuatro adapters, cada
uno con su `resultados_entrenamiento.json` y su `evaluacion_test_*.txt`), `herramientas/kaggle_kernel/` (entrenamiento
vía API de Kaggle, alternativa a Colab).

**¿Qué adapter usar?** No hay un sucesor único — **v3** tiene el mejor acuerdo medio con el humano (85 %, §11.4); **v4**
sacrifica algo de esa media (82 %) a cambio de dejar de fallar sistemáticamente en `naranja`/`dorado`/`plateado`
(§11.5). Para cualquier uso que no dependa mucho de esos tres colores, v3 es la opción por defecto más segura.
