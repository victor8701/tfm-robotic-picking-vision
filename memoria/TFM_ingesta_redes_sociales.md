# Ingesta y análisis visual de contenido de tendencia (`viral_clips` + visión)

**Autor:** Víctor Martín Parra
**Máster:** Robótica y Automatización — UC3M (2025/2027)
**Fecha del plan:** 21 de septiembre de 2026
**Estado a 2026-09-25: en implementación activa** (se retomó antes de lo previsto). Esta rama
(`ingesta-viral-clips`) se creó para tener un sitio propio donde trabajar esto sin mezclarlo con
la rama ya cerrada del clasificador (`clip-trend-semantic-matching-poc`). Este documento está
escrito para que sea suficiente por sí solo, sin tener que reconstruir el contexto de memoria.
Ya hechos: taxonomía de sub-estilos + herramienta de revisión táctil (Anexo A), Etapa 0 del plan
de abajo (`viral_clips` leído de verdad, corrige una suposición equivocada — ver §1.2), y arranque
de la Etapa 1 (`experimentos/ingesta_x/`, descarga+extracción de fotogramas desde X probada de
principio a fin).

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

### 1.2 `viral_clips` (repo separado, ya existente) — **Etapa 0 hecha, 2026-09-25: corrige una suposición equivocada**

**`viral_clips` no es parte de este repositorio.** Es un repo propio distinto, público:
**[`github.com/victor8701/viral_clips`](https://github.com/victor8701/viral_clips)**.

`Estado_arte.md` §6.1 dice que está **"desarrollada para YouTube, ampliada a TikTok y
X/Twitter"** — esta frase se había interpretado hasta ahora (incluida la primera versión de
este documento) como que **descarga/scrapea contenido DESDE esas tres plataformas**. Al clonar
el repo y leer el código de verdad (Etapa 0, por fin hecha), **eso es incorrecto**:

- **Descarga (fuente): solo YouTube**, vía `yt-dlp` (`src/viral_clips/pipeline/download.py`).
  No hay ningún código de descarga de TikTok o X/Twitter en todo el repo.
- **TikTok/Instagram/YouTube en `src/viral_clips/uploaders/`: son destinos de PUBLICACIÓN**,
  no fuentes — el pipeline genera clips verticales editados (subtítulos, gancho) a partir de un
  vídeo de YouTube y los **sube** a esas plataformas como contenido propio. "Ampliada a TikTok y
  X/Twitter" se refería a publicar ahí el resultado, no a ingerir contenido de tendencia desde
  ahí. Interpretación anterior equivocada, no solo incompleta.
- **No extrae fotogramas en ningún punto** (`grep` de "frame/fotograma/screenshot/keyframe" en
  todo `src/` no encuentra nada) — el pipeline es descarga → transcripción (Whisper) → selección
  de momentos con Claude → renderizado de vídeo. Nunca produce una imagen fija suelta.

**Consecuencia real para esta rama**: `viral_clips`, tal como está hoy, **no es un atajo** para
conseguir muchas fotos de tendencia real. Haría falta construir dos cosas que no existen: (a) una
vía de descarga desde TikTok/X (`yt-dlp` sí soporta TikTok como fuente en general, pero no hay
nada de eso conectado aquí, y TikTok tiene protecciones anti-scraping fuertes — no se sabe si
funcionaría sin probarlo), y (b) extracción de fotogramas (más simple, `ffmpeg` a intervalos,
tal como ya anticipaba la Etapa 1 de este plan). Esto es una construcción nueva, no conectar dos
piezas ya hechas — bastante más trabajo del que sugería la redacción anterior de este documento.

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

1. ~~**¿Qué hace `viral_clips` exactamente hoy?**~~ **Resuelto 2026-09-25** — ver §1.2: solo
   descarga de YouTube, no extrae fotogramas en ningún punto. Ambas cosas habría que construirlas.
2. **Fuente concreta para empezar.** El diseño apunta a YouTube/TikTok/X, pero como `viral_clips`
   no descarga de TikTok/X hoy (ver §1.2), esto ahora es una decisión real de por dónde empezar a
   construir, no de configuración. **Prueba empírica hecha 2026-09-25** con `yt-dlp` (la misma
   librería que ya usa `viral_clips` para YouTube) contra un post público real de cada red —
   [@VogueRunway en X](https://x.com/VogueRunway/status/2053500729072247254),
   [@zaralarssonscloset en Instagram](https://www.instagram.com/p/DX4KrINiDn-/), y un vídeo de
   moda en TikTok — sin usar ninguna cuenta ni cookies, solo para medir la fricción de cada una:
   - **X/Twitter: la más accesible.** Token de invitado anónimo + una llamada GraphQL limpia,
     sin avisos, igual en los 3 posts distintos probados (dos sin vídeo real, uno con — en los
     tres yt-dlp identificó el contenido sin fricción).
   - **Instagram: intermedia.** Accesible sin login, pero con más peso — sesión propia, aviso de
     "no CSRF token" (modo degradado sin autenticar), y estructura de carrusel más compleja que
     una sola pieza de contenido. Además, la extracción de **fotos** (no vídeo) de Instagram no
     es el punto fuerte de `yt-dlp` — puede hacer falta `gallery-dl` u otra herramienta para eso.
   - **TikTok: la más protegida, con diferencia.** Bloqueada de raíz: la petición inicial de
     página devolvió un reto anti-bot (challenge) de 537 bytes que `yt-dlp` no pudo resolver sin
     herramientas de "impersonation" (suplantar la huella TLS de un navegador real,
     `curl_cffi`) — ni siquiera llegó a ver el contenido.

   **Conclusión operativa**: si hay que elegir una plataforma nueva para construir la descarga,
   **X/Twitter es la más barata de implementar**; Instagram es factible pero más frágil y
   necesita más pieza extra para fotos; TikTok necesita herramientas de evasión de bot-detection
   más serias antes de plantearse nada más. Esto no decide *cuál tiene el contenido de moda que
   de verdad interesa* (ese es un criterio aparte, y probablemente Instagram/TikTok ganen ahí)
   — es solo la dificultad técnica de construirlo, que es lo que se pidió medir.
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

### Etapa 1 — Extracción de fotogramas (mínimo viable) — **en marcha, 2026-09-25**

- ~~Si `viral_clips` no extrae fotogramas todavía: añadir esa capacidad~~ — resuelto: no se toca
  `viral_clips` (decisión explícita del autor), se construyó aparte en
  **`experimentos/ingesta_x/`** (ver su README). `descargar_x.py` descarga vídeo de un post de X
  con `yt-dlp` y extrae fotogramas con `ffmpeg` a intervalos (fps=1/N), tal como se anticipaba
  aquí — "algo tan simple como ffmpeg a intervalos" resultó ser suficiente para la v1.
- **Probado de principio a fin** con contenido real de X (no de moda, solo para probar el
  mecanismo, por lote): un vídeo (7 fotogramas de 1080×1920) y un post de foto nativa (2 fotos a
  resolución original) — todo guardado con su metadata (URL, cuenta, descripción, fecha), así que
  sí queda "trazable a su fuente original", como pedía este punto.
- ~~Decidir si hace falta resolver la descarga de posts de solo foto~~ **resuelto (2026-09-25)**:
  ahora `descargar_x.py` también descarga fotos nativas (vía el endpoint público de sindicación
  de X, sin sesión), no solo vídeo.
- **Descubrimiento automático, investigado y descartado por ahora** (2026-09-25): se probaron 3
  vías (extractores de timeline/búsqueda de `yt-dlp` -- no existen para X; endpoint de timeline
  de sindicación -- 429/vacío; token de invitado de la API pública usado por herramientas de
  scraping conocidas -- **X lo invalidó**, "Invalid or expired token"). Sin autenticar con una
  cuenta real no hay búsqueda/listado fiable. `descargar_x.py --urls-file` acepta un lote de URLs
  ya identificadas en su lugar (a mano, o por búsqueda web) -- quita la fricción de invocarlo uno
  a uno, aunque identificar las URLs siga siendo un paso externo al script.
- ~~Un lote real de URLs de contenido de moda/tendencia~~ **primer lote real hecho (2026-09-25)**:
  13 fotos de estilo Old Money desde X (@dieworkwear, crítico de sastrería clásica, y
  @suitsupply), ya integradas en el artefacto de taxonomía — ver más abajo.
- Sin entrenar ni afinar nada todavía: solo conseguir fotogramas/fotos reales guardados en disco.

### Pestaña "Buscar en X" en el artefacto de taxonomía (2026-09-25)

A petición del autor, el artefacto **[Taxonomía de estilos](https://claude.ai/artifact/T4vJ4qbbiCuJGMKaZ8cgLL)**
tiene ahora una segunda pestaña para pedir búsquedas de contenido en X por estilo/ocasión, sin
salir de la app que ya usa desde el móvil.

**Cómo funciona de verdad (importante, no es búsqueda en vivo)**: la CSP del artefacto no deja
llamar a hosts externos desde su JS — no puede llamar a X directamente. La pestaña escribe una
**solicitud** en la colección `solicitudes_x` de la base de datos del artefacto (estilo, ocasión
opcional, y el texto de búsqueda ya resuelto: predeterminado, "automático" combinando estilo +
ocasión, o el que escriba el autor) y la deja en estado `pendiente`. Claude revisa esa cola y la
completa la próxima vez que se trabaje en esto — busca URLs reales por web, las pasa por
`descargar_x.py`, y añade las fotos resultantes al artefacto. El autor ve el estado
(pendiente/en proceso/completado/error) en la misma pestaña. Esto se explica también dentro de la
propia UI, no solo aquí.

**Demo real hecha para probar el ciclo completo** (no solo el mecanismo, con contenido de moda de
verdad): solicitud "Old Money", modo predeterminado (texto: *"old money aesthetic outfit quiet
luxury real photos"*). Encontradas 7 URLs candidatas por búsqueda web, pasadas por
`descargar_x.py`: 5 tenían foto/vídeo nativo descargable (15 fotos), 2 fallaron limpiamente (sin
media nativa). De las 15, se descartaron 2 tras revisión visual antes de integrarlas — **criterio
de curación, no solo mecánico**:
- Una foto de un tuit de @dieworkwear mostraba a personas reales en un contexto político concreto
  (photo-op con marca de un expresidente de EE.UU. de fondo) — la prenda en sí encajaba
  (americana/abrigo), pero meter ese contexto en un dataset académico de estilos no aporta nada y
  sí introduce un tema ajeno al TFM. Descartada aunque el mecanismo la hubiera descargado bien.
- Una era la portada ilustrada de un folleto antiguo ("The Tale of an Old Tweed Jacket"), no una
  foto real de una persona vistiendo la prenda — mismo criterio que ya se aplicó antes (las 3
  fotos originales de Old Money incluían una ilustración de 1902 que el autor acabó marcando como
  "Ninguna"; se prefiere foto real a ilustración salvo que se pida lo contrario).

Las 13 restantes, integradas en el artefacto (prefijo `omz`, Old Money pasa de 23 a 36 fotos):
look de calle con americana marino, jersey de cuello vuelto + americana (editorial), abrigo
cruzado de lana/cachemira sobre cuello alto (@suitsupply, marcadas con ocasión "Arreglado" por
tratarse de un look claramente cuidado/de evento), y una foto vintage en B/N de americana de
tweed espiga estilo Ivy.

**Dos mejoras a la pestaña, a petición del autor tras ver la primera versión (mismo día)**:
- **Registro de pasos en vivo, tipo terminal**: cada solicitud guarda un array `pasos` (texto +
  hora) que Claude va ampliando con `write_db` mientras la procesa — el autor lo ve aparecer en
  la propia pestaña casi en directo si tiene la página abierta, en vez de solo un estado final.
  Va también con expectativa de tiempo explícita en la UI: **~10-20 min una vez que Claude se
  pone con una solicitud, pero solo si hay sesión activa** — no hay ningún proceso corriendo en
  segundo plano 24/7; si nadie está trabajando en esto, se queda en "Pendiente" sin más.
- **Botón cancelar/reactivar**: por solicitud, mientras esté pendiente o en proceso. No borra el
  documento, solo cambia su estado a `cancelado` (mismo patrón de reversibilidad por toggle que
  ✕/↺ en las fotos — nunca una eliminación dura sin poder deshacerla).

**Segunda demo real, con las dos mejoras ya puestas** (solicitud "Convencional", modo
predeterminado, texto *"normcore basic outfit real photos"*): 6 URLs candidatas, 5 con
foto/vídeo nativo (@OldNavy, @Gap, @UniqloIn, @UniqloUSA, @UniqloThailand — estas dos últimas de
un vídeo, del que solo se cogió el mejor fotograma de cada uno, no todos: los demás fotogramas
salían mal encuadrados o repetían el mismo plano). 5 fotos añadidas, Convencional pasa de 23 a 28.

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

---

## Anexo A: Taxonomía de estilos observada en contenido real (2026-09-24)

**Fuente**: serie de 7 vídeos de [@almucarrion](https://www.tiktok.com/@almucarrion) en TikTok
("Tipos de Cayetanas" → "tipos de modernas" → "chicas pijas" → "chicas básicas" → "mis hippies" →
"tipos de frikis, último episodio"), identificados por título vía búsqueda (no se ha podido ver el
contenido de los vídeos en sí — ver §7, limitación técnica de acceso a TikTok ya documentada).
**El contenido de cada categoría lo aportó el autor de primera mano** (él sí vio los vídeos), no es
una interpretación mía ni está verificado más allá de eso — incluye correcciones suyas sobre lo que
yo había podido reconstruir solo con los títulos (distingue "modernos" de "modernos pijos", dos
categorías que yo no había separado).

Esta es exactamente el tipo de vocabulario más rico que quedó como pregunta abierta hace unos días
(§5 de la memoria del clasificador visual, y la conversación de esa fecha): 7 categorías con
reconocimiento real de audiencia (decenas/cientos de miles de "me gusta" por vídeo, ver búsquedas
de §7), no inventadas por diseño académico. Se documentan aquí **formalizadas para poder citarse en
el TFM** — nombre neutro y descriptivo en vez del término coloquial/de argot, quitando la carga de
juicio de clase social que llevan varios de los nombres originales, y quedándonos con el rasgo de
estilo que sí es información útil.

| # | Nombre coloquial (vídeo) | Nombre formal propuesto | Rasgos distintivos | Referencias citadas |
|---|---|---|---|---|
| 1a | Pijos (parte 1) | **Old Money** | Lujo discreto y clásico — americana/chaleco, camisa de corte náutico, punto fino, sin logos visibles | Separado de 1b el 2026-09-24 a petición del autor |
| 1b | Pijos (parte 2) | **Lujo ostentoso** (*New Money*) | Marca de lujo muy visible (p. ej. Gucci, Philipp Plein), el contraste deliberado de Old Money | Referencia del autor: estética "futbolista" |
| 2 | Cayetanos | **Clásico-tradicional** | Silueta clásica, tonos tierra/neutros, prendas atemporales; contraste con maquillaje más atrevido de lo que sugiere la ropa | Prenda icónica citada en prensa: chaqueta Barbour, manoletinas |
| 3 | Modernos + Modernos pijos (fusionados el 2026-09-24 a petición del autor — antes eran dos filas separadas) | **Urbano** | Escena trap/rap española, de la versión más cruda a la más pulida (bronceado, gimnasio, marca deportiva/lifestyle de gama alta, estética de reality/redes) — un único espectro | Cruz Cafuné y otros nombrados por el autor; en la versión pulida, "bycalitos" y perfiles de *La Isla de las Tentaciones* |
| 4 | Hippies | **Bohemio** | Telas fluidas, tonos tierra, capas, accesorios artesanales | Coincide con "Boho/Bohemian", ya documentado como categoría internacional establecida (ver más abajo) |
| 5 | Frikis | **Alternativo-geek** | Ropa ligada a fandom/cultura pop (gaming, anime, cómic), prioriza el motivo/estampado sobre la silueta | — |
| 6 | Básicos | **Convencional** | Sigue la tendencia dominante del momento sin rasgo diferenciador propio | Coincide con "Normcore", ya documentado como categoría internacional establecida |

**Estado a 2026-09-24: ya aplicado a `Estado_arte.md` §3.4.2**, con permiso explícito del autor
("modificando lo menos posible") — capa de referencia nueva, sin tocar los 6 valores de `grupo_estilo`
de §3.4.1 de los que depende el matching (§7.2), el Trend JSON (§6.4) y el prompt (§6.3). Sigue en pie
el aviso de solape: **"Urbano" se parece mucho a `streetwear`**, que ya existe en esos 6 valores —
integrarlo de verdad en el matching, si se decide, es trabajo pendiente, no hecho todavía.

**Cómo seguir con esto, opciones (no excluyentes):**

- **A. Dejarlo aquí como referencia**, sin decidir nada más todavía — vocabulario documentado y
  con fuente, listo para cuando se retome la rama de verdad.
- **B. Proponer formalmente ampliar/revisar `grupo_estilo`** con esta taxonomía (o una versión
  afinada de ella) — requiere decisión explícita del autor y, si se acepta, tocar
  `Estado_arte.md` §3.4.1 (y todo lo que depende de esos 6 valores exactos, ver la nota de
  acoplamiento frágil de su propio §14.1).
- **C. Usarla como punto de partida para etiquetar contenido real** cuando se retome la Etapa 2
  del plan (§6) — en vez de inventar categorías de cero al construir la herramienta de revisión
  de looks reales, partir de estas 7 (formalizadas) y ajustar con lo que se vea de verdad.
- **D. Buscar más series del mismo tipo** (de esta creadora u otras) para ver si estas 7 categorías
  se repiten como consenso informal o si cada creadora corta el pastel de forma distinta — antes de
  tratarlas como una taxonomía "consensuada".

### Herramienta de revisión táctil (2026-09-24, dos pasadas)

Artefacto: **[Taxonomía de estilos](https://claude.ai/artifact/T4vJ4qbbiCuJGMKaZ8cgLL)** — primer
paso concreto de la opción C de arriba (punto de partida para etiquetar, no espera a la Etapa 2).

**99 fotos reales** (21 en la primera pasada, 13 en la segunda, 65 en la tercera — ver más abajo),
buscadas y atribuidas una a una (fuente y enlace visibles bajo cada foto; sin enlace cuando solo se
pudo confirmar el medio, no la URL exacta del artículo), agrupadas por las 7 categorías con una
propuesta mía inicial ya marcada. Se corrige tocando otra etiqueta, sin paso de guardado aparte;
las correcciones quedan guardadas para leerlas de vuelta más adelante. Reparto tras la tercera
pasada: Old Money 13, Lujo ostentoso 14, Clásico-tradicional 17, Urbano 16, Bohemio 14,
Alternativo-geek 8, Convencional 17 (más las que el propio autor haya subido, que se cuentan
aparte).

La primera pasada (21 fotos, todas de archivo/blog de moda, sin personas identificables con
nombre) se quedó floja en dos categorías — Urbano con 1 sola foto y Alternativo-geek en 0 — por
evitar deliberadamente a las personas reales que el autor ya había citado, para no meterme en
derechos de imagen sin que él lo pidiera explícitamente. El autor corrigió esto: pidió dedicar más
tiempo a buscar exactamente a esas personas (él no quería tener que buscarlas), y además dio un
nuevo nombre para Alternativo-geek (**orslok**) que no había citado antes.

**Segunda pasada — personas reales, una por una:**

| Categoría | Persona buscada | Quién es | Fuente de la(s) foto(s) |
|---|---|---|---|
| Urbano | Cruz Cafuné | Rapero (Tenerife, PXXR GVNG) | Wikimedia Commons, CC BY-SA 4.0 (2 fotos) |
| Urbano | Hoke | Rapero (Valencia), nunca da la cara en entrevistas | informaUVA.com |
| Urbano | Israel B | Rapero (Madrid, ex-Corredores del Bloque) | MondoSonoro |
| Urbano | Shoda / Monkas | **Es una sola persona** (Shoda Monkas, Albacete) — el autor los citó como si fueran dos | MondoSonoro + Urban Life (2 fotos) |
| Urbano | bycalitos | Influencer streetwear/lujo — **es hombre** (Carlos Martín), no la mujer que se había asumido | Neo2 (2 fotos) |
| Urbano | *La Isla de las Tentaciones* | Reality Mediaset — no hay una persona concreta citada, se usó el propio programa | Notas de prensa oficiales de Mediaset (2 fotos) |
| Alternativo-geek | orslok | Germán García Carro — youtuber/streamer gaming, luego música (hyperpop/rap) | La Gaceta de Salamanca + Marca (fuente sólida, 2 fotos); labiode.com (fuente menos verificada, 1 foto) |

Todo verificado como imagen real antes de incluirla (no HTML de error ni avatar/ilustración
haciéndose pasar por la persona — se descartaron 2 avatares de orslok por ser justo eso: un troll
dibujado y un personaje de videojuego). Prioridad de fuente, de mejor a peor: Wikimedia Commons >
nota de prensa oficial > prensa musical/medio editorial > blog de biografías. Instagram/TikTok no
dieron ninguna foto descargable directo (bloquean el acceso sin sesión) — cuando la única fuente
habría sido eso, se dejó sin foto en vez de forzarlo.

**Eje nuevo: ocasión de uso, complementario al estilo (ver Anexo B más abajo).** Cada foto admite
ahora, además del estilo, una etiqueta opcional de ocasión (Fiesta/Noche, Deportivo, Playa/Resort)
— los 3 valores que ya existían en `Estado_arte.md` §3.4.1 y que, según observó el autor, no son
un estilo en sí sino un uso que cruza con cualquiera de los 7. No es una galería nueva, es una
etiqueta más sobre las mismas fotos.

**Cuarto valor de ocasión, "Arreglado" (2026-09-24, más tarde)**: a petición del autor. A
diferencia de los 3 anteriores, **este no existe como valor de `grupo_estilo` en
`Estado_arte.md` §3.4.1** — es vocabulario nuevo, no una reutilización. Si más adelante se plantea
la opción B del Anexo A (proponer formalmente esta taxonomía para `Estado_arte.md`), "Arreglado"
es el único valor del eje de ocasión que habría que decidir desde cero, no solo trasladar.

**"Ninguna" en ambos ejes, y eliminar como acción aparte (2026-09-24, más tarde el mismo día)**: a
petición del autor, cada foto tiene una opción "Ninguna" explícita en los dos ejes. En estilo,
"Ninguna" dice que la foto no encaja en ninguno de los 7 — baja a una sección "Sin estilo" al
final, pero **no la quita de la herramienta**; en ocasión, "Ninguna" solo dice "no aplica ninguna
en concreto", sin mover la foto de sitio. El autor corrigió una primera versión en la que "Ninguna"
sí implicaba quitar la foto: pidió que eliminar fuera una **acción aparte y explícita**, no un
efecto secundario de clasificar. Ahora cada foto tiene su propio botón ✕ en la esquina (independiente
de las etiquetas), que la manda a una sección "Eliminadas" — con el mismo botón, ya como ↺, para
recuperarla; nada se borra de verdad. De paso, se quitó `capture="environment"` del campo de subir
foto propia (forzaba la cámara en el móvil) para que abra la galería, como pidió.

**Fix de compatibilidad móvil, causa real (mismo día, un rato después)**: el `<label for="...">`
no arregló nada por sí solo — el problema no era el mecanismo de disparo, sino que el autor abría
el artefacto **dentro de la app de Claude**, cuyo visor embebido (WebView) no implementa selector
de archivos nativo (ni con `<label>` ni con nada — no es arreglable desde el código del artefacto).
**Solución real: abrir el enlace del artefacto en el navegador normal del móvil** (Chrome/Samsung
Internet) en vez de dentro de la app — confirmado por el autor que así sí funciona. Se planteó
construir una web totalmente aparte (fuera de claude.ai) para evitar este problema de raíz, pero
se descartó: para guardar fotos de verdad hace falta backend o una clave de acceso embebida en una
página pública (riesgo de seguridad), y el navegador ya resuelve el problema sin nada de eso — el
autor confirmó quedarse así.

**Selección múltiple (mismo día, más tarde)**: a petición del autor, "Añadir fotos propias" ahora
acepta elegir varias imágenes de golpe (`<input multiple>`), subiéndolas una a una con progreso
("Subiendo 2/5…") y un aviso final con cuántas se añadieron y cuántas fallaron, si acaso.

## Anexo B: Estilo vs. ocasión de uso — dos ejes complementarios (2026-09-24)

Observación del autor, textual: **"Playa, deporte o fiesta no tiene estilo propio"**. De los 6
valores ya existentes de `grupo_estilo` (`Estado_arte.md` §3.4.1), tres son realmente una
estética/identidad personal — **Casual, Streetwear, De vestir** — que es exactamente donde caen
los 7 sub-estilos del Anexo A (columna "Grupo de estilo más cercano" de §3.4.2 de
`Estado_arte.md`). Los otros tres — **Fiesta/Noche, Deportivo, Playa/Resort** — no son un estilo
propio sino una **ocasión/uso**: cualquiera de los 7 sub-estilos puede vestirse "de fiesta", "de
deporte" o "de playa" sin dejar de ser ese estilo. Son dos ejes ortogonales (estilo × ocasión), no
valores hermanos de un mismo campo.

Esto no invalida el diseño de §3.4.1 (que funciona bien para el ERP de catálogo, donde cada SKU
tiene un uso predominante claro y no necesita describir a una persona) — es una distinción que se
vuelve visible al construir la capa de sub-estilo, pensada para describir a una **persona** a
partir de una foto de tendencia, no una prenda suelta de catálogo. Alguien de estilo Old Money
puede llevar ropa de playa en vacaciones sin dejar de proyectar Old Money; ese matiz se pierde si
"Playa/Resort" compite como si fuera un estilo más.

**Aplicado en la herramienta de revisión táctil**: cada foto admite ahora, además del estilo, una
ocasión opcional — reutilizando tal cual los 3 valores que ya existen en `Estado_arte.md` §3.4.1
(Fiesta/Noche, Deportivo, Playa/Resort), sin inventar vocabulario nuevo. No es una segunda galería
de fotos propia (coherente con que "no tienen estilo propio"): es una etiqueta adicional sobre las
mismas fotos de estilo.

**No se ha tocado `Estado_arte.md`.** Si en algún momento se decide que esta distinción de dos ejes
debería reflejarse también allí (por ejemplo, separar de nuevo `grupo_estilo` en dos campos,
deshaciendo parcialmente la fusión "Ocasión + Estética → Grupo de estilo" que motivó el propio
§3.4.1), es una decisión pendiente y explícita del autor — no asumida aquí.

(La segunda pasada de fotos con personas reales, pedida el mismo día, está documentada con detalle
dentro de "Herramienta de revisión táctil", más arriba, junto con el resto de esa herramienta.)

## Tercera pasada: ampliación masiva + filtros (2026-09-24, más tarde)

El autor ya había subido muchas fotos propias desde el móvil (función de subida múltiple) y pidió
ampliar mucho más el lado de fotos buscadas por mí — "muchísimas más", probando sitios con
galerías enteras en vez de personas una a una — y añadir dos filtros a la herramienta: por origen
(subidas por el autor / por Claude) y por si ya las revisó o siguen solo con mi propuesta.

**Filtros**: dos `<select>` en la cabecera. Origen usa el propio `id` de la foto como marca —
todo lo subido por el autor lleva prefijo `u_` (ver la función de subida), no hace falta guardar
un campo aparte. Revisión comprueba si el `id` está en las correcciones guardadas en `db`. Ambos
filtran las tres secciones (grupos de estilo, "Sin estilo", "Eliminadas") a la vez, y el mensaje de
"sin fotos" distingue entre categoría vacía de verdad y categoría vaciada solo por el filtro.

**Búsqueda ampliada**: 7 sub-tareas en paralelo, una por categoría, con instrucción explícita de
priorizar páginas con galerías (varias fotos de una vez) en vez de buscar persona a persona.
Resultado: **65 fotos nuevas** (tabla de reparto final más arriba). Fuentes nuevas de peso:
Wikimedia Commons (Quevedo, Yung Beef, Bad Gyal, La Zowi, Morad, Central Cee, Maluma, Ufo361,
jugadores de esports G2 — todas con licencia CC verificable), ¡HOLA! (Cayetana Rivera, Tamara
Falcó y varias influencers con nombre), Who What Wear y tenshi-streetwear.com (artículos con
galería completa), Unsplash (Bohemio, fotógrafo con nombre en cada una).

**Incidente y fix — Urbano, rate-limit de Wikimedia**: la sub-tarea de Urbano se cortó a mitad de
las descargas por un bloqueo 429 de `upload.wikimedia.org` y devolvió 5 archivos `.jpg` que en
realidad eran páginas HTML de error (detectado al comprobar con `file`, no solo por la extensión).
Se retomó esa misma sub-tarea (en vez de relanzarla desde cero) pidiéndole que borrara esos 5 y
diera la atribución de las 5 fotos válidas que sí había guardado — así se recuperó el trabajo ya
hecho sin perderlo. Lección para la próxima vez que se lance una búsqueda así: verificar siempre
con `file`, nunca fiarse de la extensión ni del resumen final de la sub-tarea sin contrastarlo.

**Alternativo-geek, la más difícil, cubierta con criterio**: la sub-tarea descartó activamente una
foto (DJ con camiseta con estampado de Superman/Wonder Woman de DC) por depender de personajes con
copyright, y avisó de un caso límite (bolso con forma de consola retro genérica, sin logo) para que
el autor lo revise él mismo si quiere máxima seguridad — el mismo criterio de cautela que ya se
aplicó en la primera pasada, esta vez aplicado por la propia sub-tarea sin que hiciera falta
repetirle la instrucción.

**Compresión antes de publicar**: las 65 fotos nuevas pesaban 37MB en total (una, de Wikimedia,
13MB ella sola). Se redujeron con Pillow a máximo 1200px de lado más largo y calidad JPEG 85% antes
de publicar — quedaron en 9MB, más razonable para cargar desde el móvil (que es como el autor usa
esto). Los PNG de origen (3 de las 65) se convirtieron a JPEG en el mismo paso, mismo criterio que
ya se había aplicado antes con `om2.png`.

Estado a 2026-09-24: **99 fotos** entre las 7 categorías, más las que el autor haya
subido él mismo (no contadas aquí porque cambian constantemente). Sigue sin tocarse
`Estado_arte.md`.
