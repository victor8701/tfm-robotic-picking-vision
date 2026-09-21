# Ingesta y análisis visual de contenido de tendencia (`viral_clips` + visión)

**Autor:** Víctor Martín Parra
**Máster:** Robótica y Automatización — UC3M (2025/2027)
**Fecha del plan:** 21 de septiembre de 2026
**Estado: SOLO PLAN — nada de esto está implementado todavía.** Esta rama (`ingesta-viral-clips`) se creó
para tener un sitio propio donde trabajar esto sin mezclarlo con la rama ya cerrada del clasificador
(`clip-trend-semantic-matching-poc`). Pensado para retomarlo dentro de aproximadamente un mes —
este documento está escrito para que sea suficiente por sí solo, sin tener que reconstruir el
contexto de memoria.

---

## Resumen en tres frases

El clasificador visual de prendas (rama `clip-trend-semantic-matching-poc`, cerrada, ver su memoria
[`TFM_clasificador_visual_atributos.md`](TFM_clasificador_visual_atributos.md) §13) está terminado y funciona
bien, pero nunca se ha probado sobre una sola foto real de redes sociales — todo su entrenamiento y
evaluación es sobre catálogo de Kaggle. Por otro lado, `viral_clips` (repo propio, separado, ya
descarga clips de YouTube y está pendiente de ampliar a TikTok/X) ya ingiere contenido real de
tendencia, pero el Trend Intelligence Agent actual solo mira su **audio y texto** (Whisper → Qwen2.5
→ Claude) — nadie mira todavía el contenido **visual** de esos clips. Esta rama es la pieza que junta
las dos cosas: extraer fotogramas de lo que `viral_clips` ya descarga (o de otra fuente, ver §5) y
pasarlos por el clasificador+detector ya construidos.

---

## 1. Contexto: de dónde viene esto y qué ya existe

### 1.1 El clasificador visual (rama cerrada)

Todo el trabajo de `clip-trend-semantic-matching-poc` está descrito con detalle en su propia memoria.
Lo mínimo que hace falta saber para esta rama, sin ir a leerla entera:

- **Clasificador propio**: Florence-2-base + LoRA, cinco versiones (v1-v5), pesos abiertos,
  autoalojado — no es una API comercial envuelta. **v3 es el adapter recomendado por defecto**
  (mejor acuerdo medio con revisión humana, 85%); v4/v5 son alternativas para casos concretos
  (colores raros / tipos de prenda raros respectivamente). Ver la tabla "¿Qué adapter usar?" en
  §12 de esa memoria.
- **Detector real**: YOLOv8-seg afinado sobre DeepFashion2 (de terceros, no propio — integrado en
  `experimentos/vlm_atributos_prenda/herramientas/analizar_outfit.py`), sustituye casi toda la
  heurística de detección que había antes.
- **Comparado empíricamente contra Claude y Gemini sin afinar**: gana de media (85% vs 74-76%),
  pierde en color genérico, gana por goleada en los campos que dependen de reglas propias del
  esquema (`grupo_estilo`, `temporada`).
- **Todo entrenado y evaluado sobre fotos de catálogo de Kaggle** (producto sobre fondo blanco) más
  19 fotos de calle de Wikimedia como único contacto con algo parecido a una foto real — nunca
  sobre contenido genuino de redes sociales.
- El repositorio y las herramientas (`experimentos/vlm_atributos_prenda/`) están completos,
  documentados y commiteados en esa rama — reutilizables tal cual desde aquí sin reescribir nada,
  aunque conviene traerlos a esta rama (`git merge`/`git rebase` desde `clip-trend-semantic-matching-poc`,
  o simplemente trabajar sabiendo que ambas ramas comparten ese historial).

### 1.2 `viral_clips` (repo separado, ya existente)

**Esto es importante y fácil de olvidar en un mes: `viral_clips` no es parte de este repositorio.**
Es un repo propio distinto: **[`github.com/victor8701/viral_clips`](https://github.com/victor8701/viral_clips)**.
Según `Estado_arte.md` §6.1, ya está **"desarrollada para YouTube, ampliada a TikTok y X/Twitter"** —
es decir, a fecha de este documento ya descarga/recorta clips de YouTube, y ampliarlo a TikTok/X
**ya estaba planeado independientemente de todo lo visual**, como parte del propio diseño del
Trend Intelligence Agent.

**No se ha mirado ese repositorio durante esta sesión** — no está clonado en esta máquina y no se ha
inspeccionado su código ni su README. El primer paso real de esta rama (§6, Etapa 0) es literalmente
ir a verlo.

### 1.3 El hueco real: nadie mira el contenido visual todavía

Releyendo `Estado_arte.md` §6.1 con cuidado: el Trend Intelligence Agent tal como está diseñado
**solo analiza audio y texto** de los clips que `viral_clips` descarga (Whisper transcribe el audio,
Qwen2.5 y Claude clasifican el texto). No hay ningún paso que mire los fotogramas del vídeo. El
clasificador visual (§1.1) fue motivado exactamente por este hueco — pero se construyó y validó
entero sobre catálogo, nunca conectado de verdad a `viral_clips`. Esta rama es la conexión que falta:
**sacar fotogramas de lo que `viral_clips` descarga y pasarlos por el clasificador+detector**.

---

## 2. Objetivo de esta rama

Cerrar el hueco de §1.3: dado un vídeo/clip de tendencia (de `viral_clips`), extraer fotogramas
representativos, pasarlos por el pipeline de detección+clasificación ya construido, y obtener
atributos de prenda reales de contenido real de redes sociales — no de catálogo.

**No es el objetivo de esta rama**, salvo que se decida ampliarlo explícitamente al retomarla:
- Sustituir o rehacer el Trend Intelligence Agent existente (Whisper/Qwen2.5/Claude) — eso sigue
  igual, esta pieza le añade una señal visual nueva, no lo reemplaza.
- Entrenar un detector o clasificador propios desde cero necesariamente — puede que sí haga falta
  (ver §5), pero el primer objetivo es simplemente **evaluar** lo que ya existe sobre contenido real
  y ver cuánto se sostiene, antes de decidir si hace falta afinar nada más.

---

## 3. Dónde encaja esto en el plan general del TFM

Por si se te ha olvidado el Gantt de `Estado_arte.md` §13.2: a fecha de este documento (21 de
septiembre de 2026) el TFM sigue en **fase teórica** (agosto-septiembre 2026); la implementación
empieza en octubre 2026, y el **"Trend pipeline" (LLM agent, `viral_clips` ampliado, HMI de
tendencias) está oficialmente planeado para marzo 2027** — meses por delante de "dentro de un mes".

Esto no es un problema, es una ventaja: el propio diagrama de dependencias de §13.3 dice
explícitamente que el *Trend pipeline* **"puede desarrollarse en paralelo con Catalog matching"** —
no bloquea nada más. Retomar esto dentro de un mes (≈ octubre 2026, cuando arranca la fase de
implementación) es adelantar trabajo de un hito de marzo, no ir con retraso. Tenlo en cuenta para no
sentir presión de calendario que no existe todavía — el margen real está ahí.

También relevante, ya escrito por ti mismo en `Estado_arte.md` §13.4 (tabla de riesgos): **"`viral_clips`
no cubre suficiente volumen de contenido de moda al ampliarlo a TikTok/X"** (probabilidad media,
impacto medio) con mitigación ya decidida: **"Complementar con búsqueda web (Tavily/DuckDuckGo) como
fuente adicional"**. Si el volumen real de `viral_clips` resulta insuficiente para esta pieza visual
también, esa mitigación ya pensada aplica igual aquí.

---

## 4. Qué se puede reutilizar tal cual (inventario)

De la rama `clip-trend-semantic-matching-poc`, sin tocar:

| Pieza | Dónde | Qué hace |
|---|---|---|
| Clasificador (adapters v1-v5) | `experimentos/vlm_atributos_prenda/modelos/` | Foto de una prenda → JSON de 5 atributos. Usar v3 por defecto |
| Detector | Integrado en `analizar_outfit.py` (descarga YOLO de HuggingFace) | Localiza prendas en una foto con personas |
| Pipeline completo detectar→recortar→clasificar→agregar | `herramientas/analizar_outfit.py` | Foto de una persona con outfit puesto → atributos por prenda + estilo del look. **Esto es exactamente lo que hace falta correr sobre los fotogramas nuevos** |
| Metodología de evaluación pareada | `herramientas/comparar_modelos.py`, `comparar_llm_comercial.py` | Para medir el modelo sobre contenido real sin conclusiones engañadas por ruido de muestra |
| Patrón de app de revisión mobile-friendly | Artifacts "Ficha de Prenda" / "Reglas de temporada" (ver memoria de esa rama) | Si hace falta etiquetar a mano una muestra de fotogramas reales para tener referencia, reusar este mismo patrón (tap para decidir, revertir = tocar otra opción) |
| Pipeline de reentrenamiento por API de Kaggle | `herramientas/kaggle_kernel/` | Si al final hace falta afinar algo con los datos nuevos, esto ya funciona y está probado 5 veces |

De `Estado_arte.md` (sin tocar el fichero, solo como referencia):
- §6.1: diseño del Trend Intelligence Agent y dónde encaja `viral_clips`.
- §6.4: formato del Trend JSON — cualquier señal visual nueva que se añada debería encajar aquí,
  probablemente como un campo más (a decidir, ver §5).
- §13.4: riesgos ya identificados y su mitigación.

---

## 5. Decisiones pendientes — solo las puedes tomar tú

Esto es lo que hace falta decidir al retomar, antes de escribir código:

1. **¿Qué hace `viral_clips` exactamente hoy?** Sin mirar el repo no se sabe si ya extrae
   fotogramas de los clips (aunque no los use) o si solo guarda el vídeo/audio. Esto cambia mucho
   el punto de partida real.
2. **Fuente concreta para empezar.** El diseño apunta a YouTube/TikTok/X vía `viral_clips`, pero
   para una primera validación rápida podría ser más simple un lote pequeño curado a mano (mismo
   espíritu que las 19 fotos de calle de Wikimedia de la rama cerrada, pero de contenido de moda
   real de redes sociales) — más lento de escalar, pero sin depender de que `viral_clips` ya
   soporte la plataforma que haga falta.
3. **Volumen necesario.** ¿Cuántos fotogramas/clips hacen falta para una evaluación honesta? Un
   punto de partida razonable, por comparación con lo ya hecho: algo entre las 19 fotos de calle
   (insuficiente, ya se demostró que es solo para detectar el problema) y los cientos que se
   usaron para evaluar el clasificador sobre catálogo. Si más adelante hace falta *afinar* (no
   solo evaluar), el volumen necesario es mayor — a estimar cuando se sepa si hace falta ese paso.
4. **Privacidad y consentimiento.** A diferencia de las fotos de catálogo (producto, sin personas)
   y de las 19 de Wikimedia (licencia CC, atribuidas), contenido real de redes sociales son
   personas identificables sin haber dado consentimiento explícito para este uso. Para un TFM de
   investigación probablemente está bien (uso académico, no redistribución), pero merece una
   decisión consciente, no un descuido — y probablemente una nota honesta en la memoria, al
   estilo de cómo se documentó la falta de licencia libre del dataset de Kaggle (§4 de la otra
   memoria).
5. **Formato de salida: ¿nuevo campo en el Trend JSON, o pieza separada?** ¿La señal visual
   (atributos de prenda detectados en los fotogramas) se integra dentro del Trend JSON de §6.4 de
   `Estado_arte.md` (un campo nuevo, p.ej. `prendas_detectadas` junto a `grupo_estilo_detectado`),
   o se queda como una pieza de evaluación/apoyo separada, sin tocar ese formato? Cualquiera de
   las dos implica (si se elige la primera) plantear el cambio a `Estado_arte.md` — recuerda que
   ese fichero no se toca sin que tú lo pidas explícitamente.
6. **¿Hace falta afinar algo, o basta con evaluar?** Deliberadamente fuera de alcance decidirlo
   ahora — depende de lo que salga en la Etapa 3 del plan de abajo.

---

## 6. Plan de trabajo por etapas

Mismo espíritu que el plan original del clasificador (etapas concretas, verificables, sin bloquear
en tener todo perfecto antes de empezar).

### Etapa 0 — Reconocimiento (antes de escribir nada)

- Clonar y leer `viral_clips` (README, código): ¿qué descarga ya?, ¿de qué fuentes de verdad
  funciona hoy (solo YouTube, o ya algo de TikTok/X)?, ¿guarda el vídeo entero, o ya recorta
  clips?, ¿hay fotogramas extraídos en algún punto del pipeline actual?
- Con eso, resolver las decisiones de §5.1-§5.3 (qué hay, por dónde empezar, cuánto volumen).
- Verificar si sigue vigente el riesgo de §13.4 de `Estado_arte.md` (cron de GitHub Actions
  desactivado a los 60 días sin commits) si `viral_clips` lleva tiempo sin tocarse.

### Etapa 1 — Extracción de fotogramas (mínimo viable)

- Si `viral_clips` no extrae fotogramas todavía: añadir esa capacidad (algo tan simple como
  `ffmpeg` a intervalos, o más elaborado con detección de escena — empezar simple).
  Referencia práctica de coste: la extracción de fotogramas es barata comparada con cualquier
  paso de inferencia del clasificador, no es la parte que hay que optimizar primero.
- Sin entrenar ni afinar nada todavía: solo conseguir fotogramas reales guardados en disco,
  trazables a su clip/fuente original.

### Etapa 2 — Evaluación honesta de lo que ya existe (sin afinar nada)

- Correr `analizar_outfit.py` (adapter v3 por defecto, detector DeepFashion2 ya integrado) sobre
  un lote de fotogramas reales — mismo patrón que la Etapa de "fotos de calle" de la rama cerrada,
  pero con datos de la fuente real objetivo en vez de Wikimedia.
- Si hace falta comparar contra una referencia humana: reusar el patrón de "Ficha de Prenda"
  (tap-to-decide, mobile-friendly) sobre una muestra pequeña de los fotogramas.
- **Esta etapa por sí sola ya es un resultado real para la memoria**, aporte o no aporte más
  adelante: "el clasificador entrenado sobre catálogo, evaluado sobre contenido real de redes
  sociales, rinde X" — es el dato que toda la rama cerrada dejó como pendiente.

### Etapa 3 — Decidir si hace falta afinar, con datos reales delante

- Con el resultado de la Etapa 2: si el rendimiento se sostiene razonablemente, probablemente no
  haga falta afinar nada más de inmediato — documentar y seguir con el resto del TFM.
- Si el salto de dominio es grande (probable, dado lo ya visto con las 19 fotos de calle): decidir
  entre afinar el clasificador con recortes reales, afinar/entrenar un detector propio, o ambos —
  con el pipeline de Kaggle ya construido y probado, reutilizable para lo primero al menos.

### Etapa 4 — Conectar con el resto del sistema (si procede)

- Solo si se decide integrar esta señal en el Trend JSON de verdad (§5.5): coordinar con el resto
  del Trend Intelligence Agent (§6.1 de `Estado_arte.md`), probablemente como un paso más del
  pipeline de GitHub Actions ya diseñado en §6.6.

---

## 7. Riesgos conocidos

Heredados de `Estado_arte.md` §13.4 (ya pensados, no nuevos):
- Volumen insuficiente de `viral_clips` al ampliar a TikTok/X → mitigación ya decidida: búsqueda
  web (Tavily/DuckDuckGo) como fuente complementaria.
- Cron de GitHub Actions desactivado tras 60 días sin commits, si `viral_clips` lleva tiempo
  parado.

Nuevos, específicos de esta pieza:
- **Salto de dominio probablemente grande.** Ya se documentó con las 19 fotos de calle (rama
  cerrada, §8) que el clasificador entrenado sobre catálogo se degrada de forma real sobre fotos
  con fondo/personas/varias prendas. Contenido de vídeo de redes sociales (movimiento, compresión,
  iluminación variable, oclusión) es probablemente todavía más difícil — no dar por hecho que el
  84.2% de accuracy de catálogo se acerque siquiera de lejos sobre esto.
- **Extraer el fotograma "bueno" de un clip no es trivial.** Un vídeo tiene fotogramas borrosos,
  de transición, sin la prenda visible entera, etc. — la calidad de la extracción de fotogramas
  puede importar tanto como la calidad del clasificador.
- **Privacidad/consentimiento** (ver §5.4) — no es solo un riesgo técnico.
- **Dependencia de un repo externo que puede haber cambiado.** `viral_clips` es un proyecto propio
  pero separado — puede llevar tiempo sin tocarse, las plataformas (YouTube/TikTok/X) cambian sus
  APIs/ToS con cierta frecuencia, y algo que funcionaba hace un mes puede no funcionar al volver.
  Verificar esto en la Etapa 0, no asumir que sigue igual.

---

## 8. Qué NO cambia (restricciones que se mantienen de la rama cerrada)

- **No tocar `memoria/Estado_arte.md`** salvo que tú lo pidas explícitamente — sigue aplicando
  aquí igual que en la rama anterior, incluso si esta rama termina necesitando un campo nuevo en
  el Trend JSON (§5.5): proponerlo, no escribirlo sin más.
- **El clasificador debe seguir siendo propio** (pesos abiertos, afinado con datos propios) — si
  esta rama termina necesitando afinar algo, sigue sin valer envolver una API comercial como
  sustituto.
- **Cualquier herramienta interactiva nueva, pensada para poder usarse desde el móvil** — ha sido
  el patrón de todo lo construido hasta ahora (apps de revisión, paneles de decisión, entrenamiento
  por API de Kaggle en vez de Colab) y ha funcionado bien.

---

## 9. Checklist para el día que retomes esto

1. Lee este documento entero (ya lo estás haciendo).
2. Si necesitas el detalle de por qué el clasificador visual quedó como quedó: lee §13 de
   [`TFM_clasificador_visual_atributos.md`](TFM_clasificador_visual_atributos.md) (el cierre de esa
   rama) — no hace falta leer el documento entero de nuevo.
3. Clona (o revisa si ya está clonado) `viral_clips` y léelo — Etapa 0 de §6.
4. Decide las preguntas de §5 con lo que encuentres.
5. Empieza por la Etapa 1-2 de §6 — extracción de fotogramas + evaluación honesta del pipeline ya
   construido, antes de plantearte entrenar nada nuevo.
