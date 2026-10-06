# Analizar mercado (prototipo) — «¿qué está de moda ahora mismo?»

**Objetivo final** (Víctor): que el operario pulse un botón **«Analizar mercado»** y vea qué está de moda ahora mismo
(`Estado_arte.md` §6, HMI de tendencias). Esta carpeta es el primer tramo de ese botón: una **app local con botones** (sin terminal) que
también sirve de **herramienta para clasificar fotos** y de **Biblioteca** donde le enseñas tú al clasificador y al buscador.

```
        ┌──────────── Biblioteca: descripciones · fotos · cuentas · enlaces (tú) ────────────┐
        ▼                                                                                   │
cosechar  →  clasificar (modelo de 7 estilos)  →  informe (qué está de moda, con ejemplos)   │
   ▲                         │                                                              │
   └── tus etiquetas (pestaña «Clasificar») y tus fotos/frases reentrenan el modelo ────────┘
```

## Uso — sin terminal

**Doble clic en «Analizar mercado»** (el `.bat` del escritorio; es copia de `Iniciar_Mercado.bat` de esta carpeta). Se abre una ventana negra
(el servidor: no la cierres mientras uses la app) y el navegador en `http://localhost:8766`. **Tras actualizar el código, cierra la ventana negra y
vuelve a abrirla** (el servidor lee `mercado.py` solo al arrancar). Pestañas:

| Pestaña | Para qué |
|---|---|
| **Inicio** | botón grande **Analizar mercado** (reentrena el modelo si has cambiado la Biblioteca o confirmado ≥ 10 fotos → descarga fotos nuevas de Reddit y de tu Biblioteca → las clasifica → prepara el informe; tarda varios minutos), contadores, consejo del siguiente paso y el registro de la tarea en curso |
| **Clasificar** | una foto cada vez con la sugerencia del modelo: clic o teclado (1-7 estilo · Enter acepta · 0 no sirve · ← volver · S saltar). Las fotos que **propones desde la Biblioteca** salen primero, con el estilo que indicaste (Enter lo confirma). Calcula en vivo **en qué % coincide el modelo contigo** (la medida honesta con fotos nuevas; lo que propones tú no cuenta) |
| **Biblioteca** | por estilo: **1** descripción con tus palabras + frases en inglés para el clasificador, **2** fotos de ejemplo (arrastrar, Ctrl+V o elegir archivos), **3** cuentas y enlaces para el buscador. Cada estilo muestra cuántas fotos tiene (meta 60) y cuánto acierta el modelo |
| **Informe** | el «qué está de moda ahora mismo» (barras ordenadas, tabla, fotos de ejemplo) |
| **Ajustes** | comunidades de Reddit, periodo del «top», y **Reentrenar** el modelo |

Para automatizar o depurar, lo mismo existe por línea de comandos: `python3 mercado.py app | entrenar | cosechar --biblioteca [--solo-x | --solo-enlaces] | cosechar --reddit a,b | informe | reentrenar | analizar --cosechar --biblioteca | hojas --estilo … | resolver …`.

## Revisar desde el móvil (por el chat, sin la app)

Cuando no hay ordenador a mano, las propuestas de la Biblioteca se revisan por el chat con Claude: `python3 mercado.py hojas --estilo clasico_tradicional --max 18` crea hojas de
contactos 3×3 con cada foto numerada (C01…, L01… = clásico, lujo; O, U, B, G, V para los demás) y su fuente abajo, en `cache/hojas/`; el estado va a `cache/revision_movil.json`.
Claude las envía al chat, tú contestas **solo con los números que SÍ valen** (p. ej. `C 1 2 6 · L 3 4`) y se aplica con
`python3 mercado.py resolver --revisadas C01-C18 --buenas C01,C02,C06` (lo revisado y no nombrado se descarta; lo bueno se confirma con el estilo propuesto, con origen «biblioteca»).
Cada tanda se ordena con la tasa de aciertos de la fuente y con un filtro «sirve / no sirve» aprendido de tus decisiones (CLIP + regresión logística), y reserva un tercio para
fuentes aún poco probadas. Entre el 2026-10-03 y el 2026-10-04 se juzgaron así 135 fotos (69 % buenas); el filtro preveía 59-67 % y el real fue 61-94 %.

## La Biblioteca (qué hace cada cosa)

| Lo que metes | Lo usa… | Cómo |
|---|---|---|
| **Fotos** de un estilo | el clasificador | son ejemplos de entrenamiento, guardadas reducidas en `cache/biblioteca/<estilo>/`. **No pasan por «Clasificar»** (ya son tuyas con su estilo). Al subirlas se compara su huella (dHash) con las del entrenamiento: si ya estaba con ese estilo no se repite, y si estaba con otro se avisa y manda tu elección. En el entrenamiento, las casi idénticas (CLIP ≥ 0,97) se usan una sola vez para no inflar la validación cruzada |
| **Frases en inglés** de un estilo | el clasificador | CLIP las convierte en un «prototipo de texto» por estilo. Si marcas «usar estas frases» (por defecto solo en *clásico-tradicional* y *lujo ostentoso*), el modelo parte de ese texto y las fotos lo **corrigen** (ver abajo) |
| **Descripción con tus palabras** y personas de referencia | la memoria del TFM y, más adelante, el LLM que redacte la `descripcion` del Trend JSON | solo se guardan |
| **`r/comunidad`**, **`u/usuario`** de Reddit | el buscador | se descargan sus fotos (top de la comunidad / publicaciones recientes del usuario) y se te proponen con ese estilo |
| **Tuits con fotos**, **páginas web / artículos**, **imágenes sueltas** | el buscador | se descargan al añadirlos (las fotos de las páginas e imágenes sueltas solo entrenan y nunca cuentan como «moda de ahora»; lo que propones desde la Biblioteca solo cuenta en el informe cuando lo confirmas tú). De una página se toman las fotos grandes (≥400 px, proporción de foto), sin logos ni iconos, y se queda un máximo de 12 que CLIP reconoce como «persona con ropa». Se proponen con ese estilo |
| **`@cuenta` de X** | el buscador, y la búsqueda híbrida de X (GitHub Actions, hoy pausada) | al añadirla se comprueba que existe (y se guarda su nombre real). Al buscar se bajan las fotos de sus últimos ~20 posts propios (sin reposts) a través del servicio público de terceros **FxTwitter** (`api.fxtwitter.com`: X no deja listar cuentas, ellos sí; sin clave ni coste). Es un servicio que a veces contesta 404 la primera vez que se pide una cuenta (se reintenta solo) y puede cambiar o caerse. Además se copia a `ingesta_x/cuentas_confiables.json` (clave `_desde_biblioteca`). Rinde según la cuenta: una de moda masculina dio 7 posts con foto de 19; una cuenta política, 1 de 20. Las cuentas que añade el asistente (p. ej. marcas oficiales) llevan `origen: asistente` y **no** se copian a `cuentas_confiables.json`, que es solo para lo que elige Víctor |
| **Instagram / TikTok** | nada automático | X, Instagram y TikTok no dejan listar perfiles solos: se guardan con su enlace para que abras el perfil y pegues aquí los enlaces de las fotos buenas |

**Qué NO se hace:** buscar por texto (las frases) en Reddit u otra web. Se midió: una búsqueda de Reddit con frases de «cayetano» devolvió 47 resultados,
8 con imagen directa y casi todos fuera de tema; con eso volveríamos al problema de «las fotos que encuentra son cada vez peores».

### Cómo entra el texto en el modelo (y lo que se midió)

`z = X·Wᵀ + b + λ·texto(X)`: la regresión logística (C=5, pesos de clase balanceados, como siempre) se entrena **con la puntuación del texto como base
fija**, así que solo aprende la *corrección* que piden las fotos: con pocas fotos manda el texto, con muchas mandan las fotos. El texto de un estilo
suma puntos cuando la foto se parece a sus frases (coseno CLIP × 100 menos la media de los 7 estilos) y **nunca resta** (una cayetana no pierde puntos por
no ser el cayetano de la frase). El peso λ ∈ {0, 0,25, 0,5, 1, 2} se elige al reentrenar por validación cruzada (2×5 pliegues) y solo se usa si mejora ≥ 1
punto el recall medio sin costar más de 2 puntos de acierto global; si no, λ = 0.

Con los datos del 2026-10-03 (276 fotos, tras quitar 3 casi repetidas; 15 de clásico y 17 de lujo), λ = 0,5:

| Estilo | Solo fotos | Con frases | Fotos |
|---|---|---|---|
| Clásico-tradicional | 53 % | **67 %** | 15 |
| Lujo ostentoso | 65 % | **85 %** | 17 |
| Convencional | 74 % | 68 % | 58 (pierde fotos a favor de clásico) |
| Recall medio de los 7 | 74 % | **79 %** | |
| Acierto global | 80 % | 81 % | |

Contrastes que llevaron a este diseño (mismo conjunto, 15 pliegues): mezclar el texto **después** de entrenar (sumar λ·texto a un modelo ya entrenado) hunde el
acierto global (79 → 52 % con λ = 0,5 solo en clásico+lujo) porque la clase impulsada roba fotos a las demás; usar el texto en los 7 estilos empeora
*Old Money* (95 → 78-92 %) porque sus frases no están afinadas. **Limitaciones:** con 15-20 fotos por estilo el margen es de ±10 puntos; las frases se escribieron
sabiendo qué estilos fallaban (cifra optimista); y las fotos de clásico que hay en la galería son sobre todo de *cayetanas* (mujeres), mientras que la
descripción de Víctor es del cayetano «paleto» masculino: la validación cruzada **no puede** medir si el texto ayuda con esa variante porque no hay fotos
de ella. La medida de verdad es «coincide contigo» al clasificar fotos nuevas, y las fotos que subas a la Biblioteca.

## Qué hay (y qué no) de «mercado» todavía

- **Sí**: ranking de estilos ponderado por posición en el «top» y por recencia (vida media configurable), con fotos de ejemplo,
  tabla equivalente, y un JSON con la forma del Trend JSON de `Estado_arte.md` §6.4 (`grupo_estilo_detectado`, `intensidad`, `fuentes`,
  `fecha_analisis`), salvo la `descripcion`, que debe redactarla el LLM **con las definiciones de los estilos** (hallazgo del
  Experimento B: pesa más lo bien especificado que sea el texto que añadir imágenes). Las páginas e imágenes sueltas de la Biblioteca **no** cuentan
  como «moda de ahora» (solo entrenan); las comunidades/usuarios de Reddit y los tuits sí.
- **No**: la fuente actual es **Reddit (EEUU)** y la taxonomía de 7 estilos es de la cultura española (vídeos de @almucarrion): el
  informe sirve para probar la herramienta, **no** como análisis del mercado europeo. Tampoco hay aún popularidad real (el RSS no da
  votos; se usa el puesto en el «top»), ni comparación de ventanas (esta semana frente a las últimas semanas = «subiendo»).
- **El botón final** necesita fuentes fiables y legales y pensadas para Europa: la **API oficial de Reddit** (gratis con OAuth, da votos),
  **YouTube** vía `viral_clips` (fotogramas de vídeos de moda en ES), y cuentas de referencia. X: su timeline oficial público da 429; hoy se lee con FxTwitter (tercero, frágil, zona gris de los términos de X): vale para probar, no como pieza de producción.
  Cada fuente es un adaptador que devuelve candidatas con los mismos campos, así que añadir una no toca el resto.
- **Filtro de fotos pendiente de mejorar**: la «puerta» actual (CLIP zero-shot: ¿es una persona con ropa?) solo quita lo que no es una foto de gente
  (anime, memes, paisajes); frente a tus decisiones «sirve / no sirve» en Reddit acierta apenas por encima del azar (AUC 0,55), y en las páginas deja pasar
  publicidad, fotos de producto y belleza (en las dos páginas probadas, menos de la mitad de las fotos que pasaban eran fotos útiles de ropa en uso). Un filtro aprendido de tus propias decisiones
  (136 hasta hoy: 111 sirven, 25 no) llegó a AUC 0,78 en validación cruzada; no está integrado. Hoy el último filtro eres tú con el 0 de «Clasificar».

## Estado (2026-10-04) y lo que falta para el botón final

Meta de 60 fotos distintas por estilo cumplida en 4 de 7 (Old Money 77, clásico 65, lujo 63, convencional 58; geek 41, bohemio 37, urbano 31) con 78 % de acierto en validación cruzada (clásico 63 %, lujo 87 %).
Sesgo conocido: 41 de las 44 fotos de lujo confirmadas en la app son bolsos de Louis Vuitton/Gucci y el 44 % del clásico es Barbour (comunidades de Reddit de EEUU), y Old Money y clásico se confunden entre sí.
Objetivo final: un botón que analice las tendencias, saque fotos de X y diga de dónde son. Falta: **modo mercado** (cuentas de X con etiqueta de mercado, p. ej. España; idioma, ubicación y likes/vistas de cada post, que FxTwitter da;
informe que cuente las fotos sin confirmar con la predicción del modelo; instantáneas semanales para «sube / baja»), una **medida real** con fotos nuevas de esas cuentas (la del 78 % es validación cruzada) y más datos de urbano, bohemio y geek.

## Privacidad y licencias

Las fotos son de **personas reales** que las subieron a Reddit/X o salen en prensa. Se guardan **solo en `cache/`** (fuera de git); al repositorio van el
código, el modelo (`modelo_estilos.npz`: 7×512 números de pesos y 7×512 de texto), las etiquetas (`etiquetas_mercado.json`: id, estilo y enlace, sin imágenes)
y los textos de la Biblioteca (`biblioteca.json`: descripciones, frases, cuentas y enlaces). No publiques las imágenes ni el informe con miniaturas; consulta a la
universidad antes de difundir un dataset con fotos de terceros (RGPD). Las páginas se piden con un identificador honesto (`tfm-uc3m-research/0.1`) y sin datos personales.

## Ficheros

| Fichero | Qué es | ¿En git? |
|---|---|---|
| `mercado.py` · `app.html` | la herramienta (servidor local + página) | sí |
| `Iniciar_Mercado.bat` | lanzador de doble clic para Windows (arranca la app en WSL y abre el navegador) | sí |
| `modelo_estilos.npz` | pesos del clasificador (CLIP + regresión logística) y prototipos de texto | sí |
| `etiquetas_mercado.json` | tus clasificaciones de la pestaña «Clasificar» (datos de la tesis) | sí |
| `biblioteca.json` | descripciones, frases, personas de referencia, cuentas y enlaces por estilo | sí |
| `cache/` (`img/`, `biblioteca/`) · `candidatos.json` · `informe_mercado.*` | imágenes y trabajo local | no |

Pruebas sin tocar tus datos: `MERCADO_DATOS=/ruta/copia python3 mercado.py app --puerto 8777` (y `MERCADO_CUENTAS_X=/ruta/cuentas.json` para no escribir en `ingesta_x`).
