# Briefing para discusión: encontrar fotos de tendencia relevantes y probar vectores de tendencia visuales (Opción B)

**Proyecto:** TFM de Víctor Martín Parra — Máster en Robótica y Automatización, UC3M (2025/2027)
**Fecha:** sábado 3 de octubre de 2026 · **Redactado por:** Claude (Sonnet 5.5), a petición de Víctor
**Para:** otro agente de IA que no conoce el proyecto. Documento autocontenido. Repositorio (público): `github.com/victor8701/tfm-robotic-picking-vision`.

**Convención de honestidad.** *[medido]* = calculado con datos reales del proyecto (límites en §4.7). *[hipótesis]* = no probado. *[no verificado]* = afirmación sobre el mundo exterior que no he comprobado. Si algo de aquí te parece mal planteado, dilo: se pide expresamente que se cuestione.

---

## 0. Qué se le pide al otro agente

Devolver un **plan de implementación** (pasos ordenados, horas estimadas, criterios de éxito y de parada) para dos cosas encadenadas:

1. Que el programa **encuentre fotos relevantes de ropa/tendencias de forma automática o casi**. Ojo al objetivo: no hacen falta miles; hace falta **alta precisión sobre un conjunto pequeño por tendencia (≈10–20 fotos buenas)**.
2. Que con esas fotos se monte y evalúe el **experimento B**: ¿un vector de tendencia *visual* (a partir de fotos reales) mejora o complementa al vector de tendencia *textual* a la hora de recomendar prendas de un inventario?

Restricciones duras: **$0 de gasto**, solo CPU, ~8 h/semana de Víctor, modelos de pesos abiertos. Las preguntas concretas están en §9.

---

## 1. El TFM en un minuto

Sistema robótico **bimanual (2× ABB GoFa)** que clasifica y selecciona prendas de moda en cajas rígidas individuales, con cinco modos de operación progresivos (1 vaciado geométrico · 2 clasificación supervisada · 3 reposición por demanda geográfica · **4 guiado por tendencias** · **5 optimización multiobjetivo**). **La aportación investigadora está en los Modos 4 y 5.**

Hipótesis central (memoria §1.3): *un sistema robótico bimanual puede cerrar el bucle IT↔Middleware↔OT, desde el análisis de tendencias en redes sociales hasta la selección física de prendas, usando CLIP como puente semántico entre el lenguaje de la moda y la visión del robot.*

**Cómo funciona hoy el diseño de tendencias (memoria §6–7):**
- Un *Trend Intelligence Agent* ingiere clips virales (`viral_clips`, repo propio, hoy solo YouTube) → Whisper → Qwen2.5 → Claude → un **Trend JSON** cuya pieza clave es una `descripcion` en **texto libre** + `grupo_estilo_detectado` (uno de 6 valores).
- **El matching es: `score = cos(CLIP_img(SKU), CLIP_txt(descripcion)) + β·boost_estilo`**, con β≈0.1 y umbral θ≈0.20. Es decir, **la tendencia es solo texto**; nadie mira todavía el contenido visual de las tendencias (memoria de la rama, §1.3).
- Métricas objetivo (memoria §11): Precision@K > 0.70, NDCG@K > 0.75, y evaluación mixta con **juicio humano** (A/B contra un experto, coherencia interna, estabilidad temporal). No existe un ground truth objetivo de "prenda alineada con una tendencia".
- Inventario: catálogo fotografiado de **87–145 SKUs** (ropa de segunda mano) + "hero set" físico de 15–25 SKUs para la demo.

**Calendario (memoria §13):** ~8 h/semana desde octubre 2026; implementación oct-2026→jun-2027; **octubre = infraestructura ROS 2 / EGM / PLC (ruta crítica)**; catalog matching en enero; *Trend pipeline* en marzo 2027; Modo 4 en abril; evaluación en junio; defensa en julio 2027. Según una nota previa de Víctor, **los robots estarían disponibles hacia mediados de octubre** *[por confirmar]*.

---

## 2. Dónde encaja esta parte (y dónde no)

El trabajo de "ingesta de redes sociales" cierra un hueco: **el clasificador visual (Florence-2 + LoRA) y el POC de CLIP se entrenaron/evaluaron solo con fotos de catálogo de Kaggle**, nunca con fotos reales de redes. Es trabajo **adelantado respecto al Gantt** (el Trend pipeline es de marzo) y **no está en la ruta crítica** (octubre es robot). Por eso conviene acotarlo en tiempo.

Dos taxonomías que no hay que confundir:
- **6 Grupos de estilo del ERP** (los que usa el matching): Casual · Streetwear · De vestir · Fiesta/Noche · Deportivo · Playa/Resort.
- **7 sub-estilos de referencia** (capa opcional "no integrada todavía", memoria §3.4.2), con la que se han etiquetado las fotos reales: `old_money` (≈De vestir) · `lujo_ostentoso` (≈De vestir/Fiesta) · `clasico_tradicional` (≈Casual/De vestir) · `urbano` (≈Streetwear) · `bohemio` (≈Casual/Playa) · `alternativo_geek` (≈Casual) · `convencional` (≈Casual). El mapeo es orientativo; la mitad cae en "Casual".

---

## 3. Situación actual (qué existe)

**Datos etiquetados (475 entradas en la galería):** 173 fotos reales **confirmadas** por Víctor en los 7 sub-estilos (168 con fichero de imagen): old_money 33 · alternativo_geek 29 · convencional 28 · urbano 26 · bohemio 24 · lujo_ostentoso 17 · clasico_tradicional 16. Más 191 descartadas con imagen. 87 fotos nuevas sin revisar.

**Tubería de recogida automática (funciona sola):** GitHub Actions (repo público, gratis) → búsqueda **Tavily** (plan gratuito, 1000 créditos/mes, ~140 usados) acotada a x.com → filtro mecánico de palabras (≈50 términos) → descarga de fotos nativas por el endpoint público de sindicación de X (sin autenticar) o de vídeos con `yt-dlp` + fotogramas con `ffmpeg` (tope de 4 por vídeo) → importa a una **galería táctil** (Flask en Render gratis; el repo hace de base de datos) donde Víctor aprueba/corrige/elimina con toques. Textos de búsqueda actuales (fijos, un texto por estilo, se repiten cada día):

| Estilo | Texto de búsqueda |
|---|---|
| old_money | `old money aesthetic outfit quiet luxury real photos` |
| lujo_ostentoso | `logomania flashy designer brands outfit real photos` |
| clasico_tradicional | `cayetana style outfit spain classic preppy` |
| urbano | `moda trap español streetwear outfit real` |
| bohemio | `bohemian boho chic outfit real photos` |
| alternativo_geek | `techwear utilitarian gorpcore streetwear outfit real photos` |
| convencional | `normcore basic outfit real photos` |

**Modelos y herramientas locales:** CLIP **ViT-B/32** (pesos OpenAI, `open_clip`, 512-d); Florence-2-base + adaptadores LoRA v1–v5 (entrenados en catálogo; v3 = 85% de acuerdo medio con revisión humana, supera a Claude y Gemini sin afinar en `grupo_estilo`/`temporada`); detector de prendas YOLOv8s-seg de DeepFashion2 (terceros, Apache-2.0, preentrenado).

**POC de matching** (`experimentos/clip_trend_matching/`): ≈1,2 mil fotos de producto de Kaggle en 6 carpetas = los 6 grupos (casual 251 · streetwear 201 · deportivo 230 · de_vestir 176 · fiesta_noche 137 · playa_resort 218; 1.213 en las carpetas) + 3 tendencias de ejemplo en texto (`tendencias_ejemplo.json`: streetwear urbano, "quiet luxury", resort) + script que aplica la fórmula de la memoria. En una evaluación previa sobre 1.207 de esas fotos, CLIP zero-shot clasificando el grupo de estilo 1-de-6 dio **32,8%** (y `fiesta_noche` colapsaba a 0%). Aviso: hay una cuestión de licencia del dataset (ver README del POC).

**Hardware:** WSL2, 8 hilos de CPU, 7,7 GB RAM, **sin CUDA utilizable** (GTX 1050 Max-Q de 4 GB inaccesible para PyTorch). Embeber una foto con CLIP ViT-B/32 en CPU ≈ 0,13 s. Para entrenamientos mayores se ha usado Colab/Kaggle gratuitos.

---

## 4. Lo que hemos medido

### 4.1 Quién elige la foto importa más que cualquier filtro *[medido]*
Fotos aprobadas por Víctor, con sus mismos criterios, según cómo se obtuvo la foto:

| Método de obtención | Fotos | Aprobadas |
|---|---|---|
| Elegidas por Claude **mirando la imagen**, de webs/Wikimedia | 99 | 76% |
| Elegidas por Claude **mirando la imagen**, de X | 25 | 80% |
| Subidas por Víctor | 55 | 78% |
| **Búsqueda automática por texto + lista de palabras** | 209 decididas | **17%** (35 útiles) |

Es la misma plataforma y los mismos criterios: cambia quién elige. La automática nunca fue mejor: entre 17% y 33% por etapas desde el primer día. (Si se excluyen 24 fotos que un asistente borró en bloque sin que Víctor las evaluara: 35 útiles de 185 = 19%.)

### 4.2 Qué es la "basura" *[medido, cualitativo]*
Búsquedas por texto devuelven tuits cuyo *texto* encaja pero cuya *imagen* no: arte anime/OC y cómics, renders 3D y assets de videojuegos, capturas de TV/noticias, carteles e infografías, mapas del tiempo, memes, collages publicitarios de reventa, imágenes generadas por IA (fantasía), fotogramas de vídeos no relacionados, fotos de jugadores de esports. Cinco rondas de listas de palabras prohibidas no lo resolvieron: **un filtro de texto no ve la imagen**. La basura se concentra en pocas fuentes: **28 cuentas con ≥2 fotos decididas y 0 aprobadas suman 122 de las 174 eliminadas** (una sola, un showcase de vídeo/imagen generativa, 27). Cuentas con buen historial: `@dieworkwear` 7/12, `@TechwearClub` 4/4, `@Painthisice` 4/4, `@MissMixi` 4/4, `@YuShuXin_Global` 3/3.

### 4.3 Límites estructurales de la búsqueda *[medido/código]*
- Una consulta Tavily devuelve **≤20 resultados**. Con texto fijo repetido a diario, el conjunto relevante se agota rápido (se encontró y arregló un bug por el que los resultados ya descargados ocupaban el cupo; un estilo llegó a tener 55 URLs ya procesadas).
- Tras ese arreglo, las 87 fotos nuevas vienen de cuentas casi todas nuevas (84/87) pero en una muestra visual de 30 solo ~6 eran ropa/persona utilizable (~20%).
- El cron de GitHub Actions no es fiable a la hora: huecos reales de 2,5–6,5 h aunque esté configurado cada hora.

### 4.4 Filtros visuales contra las decisiones de Víctor *[medido]*
Conjunto: 185 fotos de X con decisión (35 útiles, 19%). CLIP ViT-B/32:

| Filtro | Útiles que conserva | Basura que descarta | % útil entre las que pasan |
|---|---|---|---|
| Zero-shot "persona con ropa real" (umbral 0,5) | 94% | 63% | 37% |
| Idem, umbral 0,7 | 91% | 69% | 41% |
| Idem, umbral 0,9 | 69% | 83% | 49% |
| Detector de prendas DF2 añadido | ≈ igual (+2 pp): también "detecta ropa" en dibujos |  |  |
| **Modelo de preferencia** (CLIP + regresión logística entrenada con las decisiones de Víctor; 5-fold, evaluado solo en fotos de X no vistas) | AUC **0,92**; al conservar 90% de las útiles → 54% |  |  |

**Lectura clave (cambio de punto de operación):** no necesitamos *recall*, necesitamos *precisión en un conjunto pequeño*. Ordenando por el modelo de preferencia, **entre las 10 mejor puntuadas el 69% son útiles, entre las 20 el 70%, entre las 30 el 64%, entre las 50 el 58%** (10 repeticiones de 5-fold, solo 185 fotos para entrenar; debería mejorar con más etiquetas y con otras señales).

### 4.5 Clasificación de los 7 sub-estilos en fotos reales *[medido]*
168 fotos confirmadas, 7 clases (azar ≈14%): CLIP zero-shot con un prompt por estilo **59%**; sonda lineal sobre CLIP congelado con **3 / 5 / 10 / 20 fotos por estilo: 59% / 68% / 78% / 77%** (20 repeticiones). **Meseta en ~10–20 fotos/estilo**: el límite parece ser la ambigüedad entre estilos vecinos, no el volumen. (Mezcla fotos curadas, subidas y de X con división aleatoria: cifra optimista para "foto real de X".)

### 4.6 Piloto: ¿cuánta basura tolera un vector de tendencia visual? *[medido, proxy]*
Proxy en el mismo dominio (foto real → foto real), relevancia = misma etiqueta de estilo, conjunto de prueba fijo, métrica Average Precision (azar ≈ 5%), 7 estilos × 100 sorteos. "Solo texto" = prompt escrito a mano por estilo (33%, **línea base optimista** porque conoce la taxonomía). n = nº de fotos de evidencia por tendencia:

| % de basura entre las fotos de evidencia | n=5 centroide imagen | n=5 texto+imagen | n=8 centroide imagen | n=8 texto+imagen |
|---|---|---|---|---|
| 0% | 34% | 37% | 35% | 36% |
| 25% | 29% | 33% | 29% | 32% |
| 50% | 23% | 30% | 20% | 29% |
| 75% | 12% | 22% | 12% | 23% |

Lecturas: (i) con evidencia **limpia**, el centroide de imagen iguala al texto (≈33–35%) y la fusión gana poco (+3–4 pp): **el beneficio esperado de la visión es pequeño en este proxy**; (ii) el centroide **solo-imagen se degrada rápido** con basura (a 50% pierde 10–15 pp y queda por debajo del texto); (iii) la **fusión es más robusta**; (iv) un filtro "quédate con el 60% más cercano al texto" no ayudó.

### 4.7 Límites de todo lo anterior
Umbrales y modelos de §4.4 elegidos/entrenados con las mismas 185 fotos (hay que validarlos con las 87 sin revisar); muestras pequeñas (35 útiles); "útil" = criterio subjetivo de una persona (sin acuerdo inter-anotador); el proxy de §4.6 no es el experimento B (no usa catálogo ni juicio humano de relevancia prenda↔tendencia) y su línea base de texto es optimista; en las fotos de la galería no se garantiza la licencia (ver §8).

---

## 5. El problema: encontrar fotos relevantes

**Definición de "relevante"** (criterios que aplica Víctor): foto *real* (no dibujo, render, captura, meme, anuncio ni imagen generada por IA); persona o prenda con el conjunto claramente visible; sin cosplay ni merchandising de personajes con copyright; sin desnudo parcial; coherente con la tendencia buscada; idealmente de contexto social/de tendencia.

**Reencuadre.** Para el experimento B hacen falta **~10–20 fotos limpias por tendencia** y el piloto sugiere que la evidencia debe estar **≥ ~75% limpia** si se usa sola (la fusión con texto tolera más). Eso permite **filtrar con mucha dureza** y descartar el 90% de los candidatos.

**Propuesta inicial de Claude (para criticar):**
```
Fuentes ──► puerta "foto real con persona vestida" (CLIP zero-shot)
        ──► quitar duplicados / fotogramas casi iguales (similitud CLIP o hash perceptual)
        ──► puntuación = f( relevancia al texto de la tendencia [CLIP],
                            modelo de preferencia [aprendido de las decisiones de Víctor],
                            prior de la cuenta de origen )
        ──► top-N por tendencia (N≈10–20)  ──► (opcional) Víctor valida en la galería
        ──► centroide CLIP = vector visual de la tendencia ──► experimento B
```

**Alternativas de *fuente* (la parte que falla hoy) — a evaluar:**

| Fuente | Pro | Contra / incógnita |
|---|---|---|
| X por consultas de texto (hoy) | ya montado, gratis | 17% de acierto; ≤20 resultados por consulta; el texto no ve la imagen |
| X **por cuentas de confianza** (`site:x.com/cuenta`) aprendidas de las decisiones de Víctor | prior alto (varias cuentas 100%) | cobertura limitada; Tavily devuelve ≤20 por llamada |
| **Consultas expandidas** (un LLM genera decenas de variantes: prendas, marcas, hashtags) | amplía el conjunto más allá de 20 | más créditos Tavily; más ruido |
| **Fotogramas de vídeos de YouTube** de `viral_clips` | ya está en el stack del TFM; el texto (Whisper) y la imagen salen del *mismo* clip → relato coherente | hay que detectar persona/conjunto en fotogramas; calidad variable |
| **Wikimedia Commons / Unsplash / Pexels** (APIs gratuitas) | fotografía real, etiquetada por humanos, licencia clara *[no verificado en detalle]* | no son "redes sociales/tendencia" (menos fiel al relato del TFM) |
| Datasets académicos de estilo (p. ej. FashionStyle14, Hipster Wars, Fashionpedia) | etiquetas y calidad | **[no verificado]** disponibilidad, licencia y correspondencia con nuestra taxonomía |
| Reddit (r/streetwear, r/malefashionadvice…), Pinterest | publicaciones con título descriptivo | **[no probado]**; posibles bloqueos/ToS |

**Alternativas de *filtrado/ranking*:** puerta CLIP zero-shot (medida: 41%); modelo de preferencia (medido: 54%/70% en top-N); juez VLM de pesos abiertos (p. ej. Qwen2.5-VL pequeño) para casos dudosos *[no probado: latencia en CPU y calidad desconocidas]*; aprendizaje activo (Víctor etiqueta solo lo más incierto); prior por cuenta.

---

## 6. Objetivo a corto plazo: Opción B

**Hipótesis** *[hipótesis]*: H1) un vector de tendencia construido con fotos reales (centroide de embeddings CLIP) recupera prendas relevantes del inventario igual o mejor que el vector de texto; H2) la **fusión** `α·texto + (1−α)·imagen` ≥ max(texto, imagen) en P@K y NDCG@K; H3) la calidad del vector visual es robusta (o no) a la contaminación de la evidencia.

**Diseño propuesto (a refinar):**
- *Tendencias*: los 7 sub-estilos y/o tendencias con nombre (quiet luxury, techwear, boho…); varias redacciones de texto (escritas a mano **y** generadas por un LLM, para no usar una línea base optimista).
- *Evidencia visual*: N ∈ {1, 3, 5, 10, 20} fotos por tendencia, del conjunto filtrado (y variantes con contaminación controlada).
- *Inventario*: fase 1 = las ~1.200 fotos de producto del POC (stand-in); fase 2 = el catálogo real de 87–145 SKUs cuando esté fotografiado.
- *Juicio humano*: Víctor puntúa a ciegas (0/1/2) el top-5 de cada método con *pooling* para acotar el esfuerzo (orden de 30–60 min).
- *Métricas*: P@5, P@10, NDCG@10 con intervalos bootstrap; ablaciones por N, α y contaminación. Línea base: solo texto (memoria §7), solo `boost_estilo`, azar.
- *Entregable*: tabla/figura para la memoria §11.2 + decisión de si el Modo 4 usa vectores visuales.

**Riesgos y criterio de parada.** El piloto sugiere ganancia pequeña. Si tras la fase 1 la fusión no supera al texto por un margen cuyo intervalo excluya 0 (p. ej. ≥ 5 pp en P@10 sobre ≥ 7 tendencias), se documenta como **resultado neutro/negativo** (también defendible: "el texto basta; lo visual aporta robustez como mucho") y se pasa a otra cosa. **Presupuesto de tiempo: ~12–16 h en total.**

---

## 7. Objetivo a largo plazo

- **Octubre**: priorizar la ruta crítica (ROS 2 / EGM / PLC) y, en cuanto haya robot, **capturar fotos de las prendas de Víctor con la cámara del robot** (vista cenital, luz industrial): es el dataset in-domain que necesitan YOLO (Modo 2, dic) y el catalog matching (Recall@K, ene). Valen más para la tesis que cualquier foto scrapeada.
- **Marzo 2027 (Trend pipeline)**: reutilizar lo que salga de B; p. ej. añadir un `vector_visual` al Trend JSON junto a `descripcion`. La ingesta debe correr **sin intervención humana** (memoria §6.6), así que el módulo de "encontrar fotos relevantes" debe diseñarse con puertas de calidad medibles, no con revisión manual permanente.
- **Abril–junio**: Modo 4/5 y evaluación completa (P@K, NDCG@K con juicio humano, tests E2E).
- **Otras vías a considerar**: curva de aprendizaje del clasificador con fotos reales (ya medida a pequeña escala, §4.5) como figura de memoria; aprendizaje activo como "motor de datos" para acotar el esfuerzo de etiquetado.

---

## 8. Restricciones y avisos

- **Dinero**: solo lo que ya paga Víctor. Tavily, Render y GitHub en plan gratuito. Las suscripciones a Claude Pro/Gemini Pro **no cubren facturación de API**. *Observación para la memoria §6.1*: allí se asume que `claude -p` con el plan Pro es "$0 marginal"; al usarlo desde GitHub Actions con el token OAuth de la suscripción se obtuvo dos veces `Credit balance is too low` (2026-09-26); causa no diagnosticada del todo *[puede no generalizar]*.
- **Modelo propio**: el clasificador de la tesis debe ser de **pesos abiertos con afinado propio**, no un envoltorio de una API comercial (Claude/Gemini solo como línea de comparación).
- **Tiempo**: ~8 h/semana; este fin de semana Víctor **no puede aportar fotos propias** (la recogida debe apoyarse en fuentes automáticas o ya existentes).
- **No tocar** `memoria/Estado_arte.md` (documento principal de Víctor); el material nuevo va en ficheros `memoria/TFM_*.md` separados.
- **Licencias / términos de uso (riesgo abierto, pregunta real)**: las imágenes de X se están guardando en un **repositorio público** de GitHub. Puede haber problemas de copyright/ToS *[no verificado]*; conviene decidir qué se guarda (¿solo IDs y embeddings?) y qué se cita en la memoria, y consultarlo con la universidad si procede.
- **Idioma**: Víctor trabaja en español.

---

## 9. Preguntas concretas para el otro agente

1. **Encuadre**: ¿es "vector de tendencia visual vs textual" el mejor uso de ~12–16 h para el valor del TFM, dado un piloto con ganancia pequeña? ¿Qué alternativa de mayor retorno propondrías?
2. **Arquitectura de búsqueda de fotos** (§5): propón la combinación fuente + filtro + ranking que alcance **≥ 75% de precisión en el top-N por tendencia** con $0, CPU y mínima intervención humana; ordena qué implementar primero y cómo validarlo antes de fiarse (¿qué conjunto de validación limpio, si los umbrales se eligieron en la misma muestra?).
3. **Experimento B**: cierra el diseño (conjunto de tendencias, redacción de textos sin sesgo optimista, inventario fase 1/2, protocolo de juicio humano con el mínimo esfuerzo, tamaños muestrales, estadística con n pequeño).
4. **Agregación robusta**: ¿centroide, media recortada, Rocchio, varios prototipos por clustering, kNN, un adaptador lineal ligero sobre CLIP, o CLIP/SigLIP alternativos de pesos abiertos? ¿Cuáles merecen probarse y cuáles no?
5. **Calendario**: qué puede correr **sin supervisión este fin de semana** (GitHub Actions / local) y cómo repartir las semanas siguientes en ~8 h/semana sin comerse octubre.
6. **Riesgos y puertas de decisión**, qué registrar para la memoria, y cómo tratar **licencias/ToS** de las imágenes.

**Formato de entrega que se espera:** supuestos explícitos · diagrama en texto · lista de pasos con horas, dependencias y criterio de aceptación · qué va a Actions y qué va en local · plan B si algo falla · lo que NO haría y por qué.

---

## Anexo A — Rutas útiles del repositorio

| Qué | Dónde |
|---|---|
| Memoria principal (solo lectura) | `memoria/Estado_arte.md` (§3.4, §6, §7, §11, §13, §14) |
| Plan de esta parte | `memoria/TFM_ingesta_redes_sociales.md` |
| POC CLIP de matching | `experimentos/clip_trend_matching/` (`clip_matching_poc.py`, `tendencias_ejemplo.json`) |
| Clasificador Florence-2 + LoRA | `experimentos/vlm_atributos_prenda/` (`predecir_lote.py`, `analizar_outfit.py`) |
| Tubería de recogida | `experimentos/ingesta_x/herramientas/` (`buscar_x.py`, `textos_busqueda.py`, `procesar_cola.py`, `importar_a_galeria.py`) |
| Datos etiquetados (decisiones de Víctor) | `experimentos/ingesta_x/panel/data/clasificaciones.json` |
| Historial de URLs ya descargadas | `experimentos/ingesta_x/cola/procesadas.txt` |
| Workflow programado | `.github/workflows/ingesta_x.yml`, `experimentos/ingesta_x/config.json` |

## Anexo B — Glosario mínimo
**SKU**: prenda concreta del catálogo. **Grupo de estilo / sub-estilo**: ver §2. **CLIP**: modelo que mapea imagen y texto al mismo espacio vectorial de 512 dimensiones; el "puente semántico" del TFM. **Centroide**: media normalizada de los embeddings de varias fotos. **P@K / NDCG@K**: precisión y calidad de ranking en los K primeros resultados. **AP**: precisión media (área bajo la curva precisión-recall). **Sonda lineal**: clasificador lineal entrenado sobre embeddings congelados. **LoRA**: afinado ligero de un modelo. **DF2**: DeepFashion2.
