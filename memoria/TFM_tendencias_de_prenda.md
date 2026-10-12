# Tendencia por prenda: de «qué estilo domina» a «qué prendas, con qué forma»

Rama `analisis-mercado`, 2026-10-06. Documento nuevo: no toca `Estado_arte.md`. Código y página en `experimentos/analisis_mercado/tendencias_prenda/`.

## 1. Qué se redefine

Hasta ahora el informe de «Analizar mercado» daba la **cuota de cada estilo** en las fotos de un mercado (p. ej. España: convencional 37 %, lujo 18 %, bohemio 16 %…).
Víctor lo corrigió: cada persona tiene su estilo, así que ver qué estilo domina no dice nada. Lo útil es, **dentro de un estilo**, qué prenda se lleva, con qué forma y estampado,
y si sube o baja. Decisiones suyas (2026-10-06): el estilo lo da la **persona** (sus referentes), la unidad es **prenda + forma + estampado + color**, y se empieza por **geek y urbano**.

## 2. Propuesta

1. **Referente.** Cada estilo tiene sus personas (geek: orslok, Painthisice; urbano: Cruz Cafuné, Hoke, Israel B, Shoda Monkas, bycalitos, La Isla de las Tentaciones). Sin reconocimiento facial:
   una foto se atribuye por la cuenta que la publica o porque el titular/pie nombra a la persona.
2. **Foto.** Se leen las fotos públicas (X, RSS, prensa) en una ventana de tiempo.
3. **Prendas.** Detector por foto (YOLOv8-seg de DeepFashion2 + Florence-2 `<OD>` para calzado y accesorios, `analizar_outfit.py`).
4. **Forma, estampado, color.** Vocabulario del ERP (Estado_arte §3.4): 18 colores, 8 estampados, 8 formas (fit), 29 tipos de prenda; ampliado con extras marcados como míos.
5. **Tendencia.** Cuota de fotos por celda (prenda · forma · estampado · color), ponderada por popularidad y frescura (vida media 10 días, como el informe actual), comparada con la ventana anterior.
   Si una celda tiene pocas fotos se enseña un nivel más general (prenda + forma, o solo prenda); sin datos suficientes se dice «pocos datos».

La propuesta (referentes, prendas con sus formas y estampados, subestilos, 10 preguntas) está en un Artifact privado de claude.ai que Víctor corrige desde el móvil; sus respuestas quedan en su base (`tendencias/general|geek|urbano`).

### 2b. Decisiones de Víctor sobre la propuesta (2026-10-06, leídas en la base del Artifact)

| Pregunta | Respuesta | ¿Como proponía el asistente? |
|---|---|---|
| ¿El streetwear entra en urbano? | Sí (skate, baggy, marcas americanas); enciende «Streetwear baggy / skate» y «Drill / calle» | no |
| ¿Qué hacer primero? | Las dos cosas a la vez (más fuentes de fotos y método), más despacio | no |
| ¿Geek incluye alternativo / techwear / e-girl? | Sí; enciende también «Informática / dev» | sí |
| ¿Calzado y accesorios? | Ropa y calzado; accesorios fuera. En la lista de urbano enciende gorra/gorro y riñonera y apaga camisa (se toma lo específico) | sí (con excepción) |
| ¿Prendas cortadas o tapadas? | Cuentan si se ve más de la mitad | no |
| ¿Ventana de comparación? | Por temporada (6 meses) | no |
| ¿Mínimo de fotos por celda? | 5 | sí |
| ¿Fotos de prensa que nombran al referente? | Sí | sí |
| ¿Mercado? | España y EEUU por separado | no |

Referentes: descarta Rubius, TheGrefg, AuronPlay y La Isla de las Tentaciones; acepta TechwearClub, Quevedo, Morad y Beny Jr; no contesta quién más. Consecuencias: (1) con ventana de temporada no hay dos ventanas que comparar hasta ~abril de 2027
(la colección empezó en octubre de 2026), así que el informe enseñaría la cuota de la temporada actual sin flechas y se guardarían instantáneas semanales; (2) geek en España se queda con un solo referente con X (orslok, parado), hay que pedirle nombres;
(3) el detector debe estimar cuánta prenda se ve; (4) para EEUU faltan referentes (se proponen cuatro para urbano; para geek, cuentas y comunidades, no streamers).

## 3. Primeras pruebas (pequeñas; sirven para decidir, no para concluir)

**a) Volumen.** En el último informe de España (45 días, 116 fotos) urbano pesa un 6 % y geek un 0 %. De los referentes con X activo solo @byCaLiTosYT publica con regularidad (12 fotos descargadas, 4 pasaron los filtros);
@shodamonkas 1 foto en 14 días; @orslok lleva unos 600 días sin publicar. Con estas fuentes una celda de cuatro atributos queda casi siempre vacía: hace falta más volumen o agregar a un nivel más general.
Quevedo, Morad, Beny Jr e Israel B no tienen una cuenta de X que se pueda encontrar (adivinar el @ devuelve a otras personas), así que solo quedan fotos de prensa que nombren a la persona. Sonda sobre Bing Noticias (RSS público, 180 días, ~10 noticias por consulta;
`experimentos/analisis_mercado/sonda_prensa.py` y `resultados_sonda_prensa_2026-10-06.json`): Quevedo 12 fotos con persona y ropa (8 útiles a ojo), Morad 12 (4 útiles distintas), Israel B 1, Hoke 0, Beny Jr 0, Cruz Cafuné 0, orslok 0, Shoda Monkas 0.
Se cuelan otras personas, portadas, detenciones y la misma foto recortada de distinta forma. En total unas 26 fotos útiles por temporada en urbano España (con las 12 de bycalitos en X y 1 de Shoda Monkas) y ninguna en geek España. Wikimedia Commons tiene fotos
con licencia libre y fecha de Quevedo, Morad y Cruz Cafuné (y de Travis Scott, Playboi Carti y A$AP Rocky), aún sin revisar: servirían para la temporada pasada.

**b) Detector de prendas en 28 fotos de la Biblioteca (14 geek + 14 urbano, al azar).** Las 28 tienen persona; 3,0 prendas por foto en geek y 2,4 en urbano; a ojo falla en 6 de 28 (capturas, primeros planos de cara, una infografía, una persona diminuta).
El detector solo tiene 13 clases: casi todo lo de arriba sale «camisa de manga larga» (8 de 11 en geek, 8 de 10 en urbano), sudaderas incluidas. La categoría de Florence sobre el recorte coincide con la del detector en el 64 % (geek) y el 56 % (urbano) de las prendas:
se entrenó con fotos de catálogo y degrada en foto de calle. El color domina en negro (62 % geek, 41 % urbano). Forma y estampado no existen en el modelo (se descartaron en v1).
Observación sobre la muestra geek (a ojo): de 14 fotos, 6 alternativo/e-girl, 3 techwear, 2 kawaii/Harajuku, 1 fandom explícito y 2 sin clasificar; no coincide con la definición «fandom y cultura pop».

**c) CLIP ViT-B/32 zero-shot sobre el recorte de cada prenda** (`vlm_atributos_prenda/herramientas/prueba_recortes_clip.py`; 66 recortes, 36 revisados a ojo por mí, no por Víctor; resultados por recorte en `vlm_atributos_prenda/resultados/prueba_recortes_clip_2026-10-06.json`):

| Atributo | Acierto | Referencia | Comentario |
|---|---|---|---|
| Tipo fino (lista del ERP; **arriba y abrigo juntos**) | 29 de 34 (85 %) | listas separadas: 26 de 35 (74 %) | arriba 12/15, abajo 12/13, calzado 3/4, vestidos 2/2; el detector llama «camisa» a casi todo lo de arriba, no hay que fiarse de su categoría |
| Estampado (10 opciones) | 10 de 31 (32 %) | siempre «liso» = 65 % | acierta tartán (4/4) y gráficos grandes (2/2); dice «liso» en 1 de 20 prendas lisas; con un sesgo hacia «liso» sube a 77 % en validación cruzada pero pierde logos y camuflaje |
| Forma (4 opciones) | 13 de 18 (72 %) | siempre «oversized» = 72 % | no aporta; no aplica a faldas, vestidos, shorts ni calzado |

Límites: n pequeño, juez único (yo, a ojo; la verdad admite respuestas alternativas razonables), prompts en inglés sin afinar, sin intervalo de confianza; el 77 % del estampado sesgado se eligió con una validación cruzada de un parámetro sobre las mismas 31 prendas.
Los modelos mayores de open_clip (ViT-L-14 OpenAI/DFN, SigLIP SO400M) no se pudieron probar el 6 de octubre: la descarga desde Hugging Face iba a ~0,2 MB/s y se cortó (`prueba_recortes_clip.py --modelo … --pesos …` y `evaluar_recortes.py` están listos).

## 4. Lectura y siguiente paso

- El **tipo de prenda** es alcanzable con modelos abiertos sin entrenar (85 % en una muestra pequeña); el **estampado y la forma** no salen de CLIP zero-shot con estos prompts. Habrá que entrenar con correcciones de Víctor (hojas de recortes numeradas desde el móvil) una capa pequeña sobre CLIP, o probar un CLIP/SigLIP mayor (pesos abiertos) con los mismos 36 recortes.
- El **cuello de botella es el volumen de fotos**, no el clasificador: con X y prensa por nombre salen ~26 fotos útiles por temporada en urbano España y ninguna en geek España. Opciones abiertas (pregunta «volumen» del Artifact): medir solo a nivel prenda y acumular cada semana,
  y/o añadir fuentes con más fotos aunque no sean personas (miniaturas de YouTube de los referentes, comunidades de Reddit en EEUU) y fotos libres de Commons para la temporada pasada.
- Con el estilo dado por la persona, el clasificador de estilo (acierto real 2 de 10 en prensa, 8 de 18 fotos sin look) deja de ser el cuello de botella del método; queda para fotos sin referente.
- Pendiente de Víctor (preguntas del Artifact): cómo hacer el «sube/baja» con ventana de temporada, quién da el estilo geek en EEUU, qué hacer con el volumen, más referentes de geek en España, y confirmar las sugerencias de EEUU para urbano (Travis Scott, Playboi Carti, Kid Cudi, A$AP Rocky).

## 5. Flujo v0 (`experimentos/analisis_mercado/tendencia_prenda.py`, 2026-10-06 noche)

Víctor eligió «las dos cosas a la vez»: aceptar un volumen pequeño (medir solo prenda, y prenda + forma si hay 5 fotos) acumulando cada semana, y añadir fuentes con más fotos. Se midieron las fuentes nuevas antes de integrarlas:

| Fuente | Resultado (6 de octubre de 2026) |
|---|---|
| Miniaturas de vídeos de YouTube (feeds RSS por canal) | 34 miniaturas de 12 canales: sobre todo portadas de disco, memes y caras; ~1 de cada 5 enseña ropa. Los fotogramas `hq1-3.jpg` de cada vídeo no se probaron. |
| X de famosos de EEUU (Travis Scott, Playboi Carti, Kid Cudi) | 1 foto en 60 días y 0 con persona y ropa; TechwearClub, última foto hace 1949 días; Painthisice, 9 fotos y 0 con persona y ropa según el filtro |
| Reddit por RSS (top del mes) | r/streetwear: 12 posts con imagen; r/techwearclothing: 0; el RSS limita a ~1 petición por minuto |
| Prensa por nombre (Bing Noticias) | ver §3a: ~13 fotos útiles por temporada para todos los referentes de urbano España |

Conclusión: **el cuello de botella es el acceso a los datos, no el modelo**. Instagram y TikTok (donde publican los referentes) no se pueden leer sin API de pago o aprobada; con las fuentes abiertas salen decenas de fotos por temporada.
El flujo (`cosechar → biblioteca → analizar → informe`, datos aparte en `tendencia_datos/`) está pensado para acumular: cada semana añade las fotos nuevas de cada fuente, las analiza (detector DeepFashion2 + Florence, tipo fino con CLIP sobre el recorte) y recalcula la cuota de fotos por prenda para cada estilo × mercado × temporada de 6 meses (PV marzo-agosto, OI septiembre-febrero), con mínimo de 5 fotos por cifra.
Mientras no haya dos temporadas no hay «sube / baja»; las fotos antiguas que devuelven las cuentas con pocos posts (p. ej. 566 días) se conservan con su fecha y servirán de temporada pasada.
La muestra de referencia son las 82 fotos que Víctor aprobó en la app como urbano (40) y geek (42): no tienen fecha ni mercado, así que se informan aparte.

## 6. Qué se puede estimar de una prenda: etiquetas de Víctor y cuatro intentos (6 a 8 de octubre de 2026)

**Examen.** Víctor etiquetó con la página «Etiquetar prendas» (toques en el móvil) dos lotes de recortes: 61 prendas en total, 18 completas (tipo, estampado, tejido y forma). La primera prenda que elige es la principal; las demás son opcionales.
Ninguna de esas etiquetas se usa para entrenar: solo miden. Se cuenta acierto si la predicción coincide con alguna de las etiquetas puestas a ese recorte (Hoodie ≡ Sudadera) y se compara siempre con «decir siempre la clase más frecuente».
Con 22 o 23 etiquetas por atributo el error típico es de unos 10 puntos (intervalo del 95 %, ±20): no se distingue un 50 % de un 60 %, y como se probaron varias variantes sobre los mismos recortes la mejor sale algo inflada.

| Atributo | CLIP B/32 sin entrenar (lote 1) | Capa sobre CLIP B/32 con 22 000 prendas de Fashionpedia | Capa sobre CLIP L/14 con 2 800 prendas | Florence-2 describe el recorte (palabras clave) | Siempre la más frecuente |
|---|---|---|---|---|---|
| Tipo de prenda | 18 de 27 (top-1), 23 de 27 (top-3) | — | — | — | — |
| Estampado | 12 de 24 | 10 a 13 de 22 | 10 a 13 de 22 | 13 de 22 | 11 de 22 («liso»; 9 de 24 en el lote 1) |
| Tejido | 6 de 17 | — (Fashionpedia no tiene tejido) | — | 9 de 14 | 10 de 14 o 10 de 17 («algodón») |
| Forma | 12 de 22 | 4 a 9 de 23 | 4 a 6 de 23 | 10 de 23 | 11 de 23 («oversized / baggy»; 13 de 22 en el lote 1) |

**Fashionpedia** (`vlm_atributos_prenda/herramientas/entrenar_atributos_fashionpedia.py`; anotaciones CC BY 4.0). Atributos mapeados al vocabulario de Víctor: estampado desde «textile pattern» (liso, rayas, cuadros, gráfico, texto / logo, camuflaje, otro) y forma desde «silhouette», «length» y los «nickname» crop
(oversized / baggy, regular, ajustada, corta / cropped). Entrenamiento con 22 300 prendas de `train`, validación con 1 980 de `val`. Curva de aprendizaje (regresión logística sobre los embeddings congelados, sin pesos de clase):

| Datos | Estampado: validación | Estampado: Víctor | Forma: validación | Forma: Víctor |
|---|---|---|---|---|
| 10 % | 78,9 % | 13 de 22 | 59,5 % | 4 de 23 |
| 25 % | 79,0 % | 12 de 22 | 59,1 % | 4 de 23 |
| 50 % | 79,1 % | 13 de 22 | 60,3 % | 4 de 23 |
| 100 % | 79,3 % | 12 de 22 | 60,8 % | 4 de 23 |
| Siempre la más frecuente | 76,3 % («liso») | 11 de 22 | 36,0 % («regular») | 11 de 23 |

Con ViT-L/14 (OpenAI, 428 M de parámetros frente a 151 M; 2 800 prendas porque es mucho más lento) la curva es igual de plana: estampado 77,4 → 78,7 % en validación y 11 → 13 de 22 con Víctor; forma 49,4 → 57,9 % y 1 → 4 de 23.
Resultados en `resultados/fashionpedia_atributos_{completo,vit_l14}_2026-10-07.json`.

**Lectura.** (1) Con 22 000 prendas la capa aprende en su terreno (forma pasa del 36 % al 61 % en Fashionpedia), pero esa mejora no llega a las fotos de streetwear de Víctor, y diez veces más datos o un codificador casi tres veces mayor no cambian el resultado:
la limitación no es la cantidad de datos de este tipo ni la capacidad del codificador. (2) Hay un desajuste de dominio (moda de revista y de calle frente a streetwear) y de definición: «oversized» en Fashionpedia no es exactamente el «oversized» de Víctor.
(3) La forma y el tejido dependen de cómo cae la prenda sobre el cuerpo y de la textura, y un recorte suelto a 224 píxeles no lo contiene; la descripción de Florence-2 menciona la forma en 7 de 23 recortes. (4) Con unas 30 fotos útiles por temporada en urbano España, aunque se acertara todo, los porcentajes por forma o tejido tendrían muy poco soporte.

**Decisión de Víctor y mía (8 de octubre).** No se hace ahora un «entrenamiento muy grande» repitiendo lo mismo con más fotos. Orden de trabajo: (1) cerrar lo fiable, es decir, el botón «Analizar mercado» y el informe por prenda con tipo, color y estampado grueso (liso, dibujo o texto), cada cifra con su nivel de confianza;
(2) probar un modelo abierto grande de lenguaje y visión (7 000 a 8 000 millones de parámetros, tipo Qwen-VL) en una GPU de Kaggle sobre la foto entera y medirlo con las etiquetas de Víctor; si supera el 70 % y la clase más frecuente, se usa de profesor para etiquetar miles de fotos de las fuentes y se afina nuestro modelo con LoRA (ese sería el entrenamiento grande, con una aportación propia);
si no, forma y tejido quedan como límite documentado; (3) titulares y pies de foto como pista barata cuando existan. Subir las fotos de las etiquetas (personas reales) a Kaggle requiere el permiso expreso de Víctor, en un dataset privado que se borra al terminar. Su única tarea futura: unos 60 recortes nuevos etiquetados a ciegas, y solo si el profesor funciona.

### 6.1 Corrección sobre el tipo de prenda y revisión del color (8 de octubre, tarde)

**El tipo fino acierta la mitad, no dos tercios.** La cifra «18 de 27 a la primera» del apartado 6 cuenta como acierto que el modelo coincida con *cualquiera* de las prendas que Víctor etiquetó en ese recorte (indulgente) y solo con el lote 1. Contra la **prenda principal** (la primera que eligió, la que llena el recorte) y con los dos lotes (38 recortes con tipo),
el tipo que da el flujo semanal acierta **19 de 38 (50 %)**; con «cualquiera de las prendas», 24 de 38 (63 %); **por familia** (arriba, abrigo, abajo, cuerpo entero, calzado, accesorio) 29 de 38 (76 %) y 36 de 38 con «cualquiera». Probé alternativas sobre esos mismos 38:

| Método | Principal | Cualquiera |
|---|---|---|
| Flujo semanal (CLIP B/32 dentro de la lista de la categoría del detector) | 19 de 38 | 24 de 38 |
| CLIP B/32 sin restringir (29 tipos), «a photo of …» | 19 de 38 | 25 de 38 |
| CLIP B/32, conjunto de 4 plantillas | 16 de 38 | 22 de 38 |
| CLIP B/32, sonda lineal con tus etiquetas (dejando uno fuera) | 11 de 38 | 13 de 38 |
| CLIP L/14, «a photo of …» | 17 de 38 | 25 de 38 |
| CLIP L/14, conjunto de 4 plantillas | 18 de 38 | 26 de 38 |
| CLIP L/14, sonda lineal (dejando uno fuera) | 8 de 38 | 11 de 38 |

Ninguna alternativa mejora al flujo: con 38 etiquetas y 14 clases, la sonda lineal no aprende y un CLIP mayor no ayuda. Lo que dije a Víctor el 8 de octubre («el tipo de prenda es fiable») era demasiado optimista para el tipo fino; para la familia, 76 %, es aceptable pero no alto.

**Color.** No hay etiquetas de Víctor de color. Revisé a ojo 30 prendas al azar del flujo (recortes con el `color_primario` del adaptador Florence-2 v3): 21 de 30 bien, 5 claramente mal y 4 dudosas (juez único, el asistente; intervalo muy ancho). Los fallos son sistemáticos: prendas rojas, moradas, doradas, marrones o de camuflaje salen negras, grises o «camel»;
por eso «negro» (55 % de las prendas con color) está inflado.

**Qué hace el informe con esto** (pestaña «Prendas» de la app, `fiabilidad_prenda.py`, `tendencia_prenda.py informe`): cada cifra lleva un margen (intervalo de Wilson con las fotos efectivas) y una confianza = mínimo entre lo que sostienen las fotos (≥ 30 alta, 15 a 29 media, 5 a 14 baja) y el techo que fija lo que acierta el atributo (≥ 85 % alta, ≥ 65 % media, menos baja).
Hoy el tipo fino y el color tienen techo «baja» y la familia «media»: la herramienta es **orientativa** hasta que el clasificador mejore. Para probar si un modelo de lenguaje y visión grande lo mejora, ver `vlm_atributos_prenda/herramientas/vlm_profesor/`.

### 6.2 El «profesor»: un modelo grande de lenguaje y visión, sin entrenar (8 de octubre, tarde)

**Pregunta.** CLIP, una capa entrenada con Fashionpedia y Florence-2 no mejoran a «decir siempre lo más frecuente» con las etiquetas de Víctor. ¿Lo hace un modelo abierto grande de lenguaje y visión que mira la foto entera? Si sí, puede hacer de profesor (etiquetar muchas fotos) y destilarse en nuestro modelo.

**Método** (`vlm_atributos_prenda/herramientas/vlm_profesor/`). Kaggle con dos GPU T4; Qwen2.5-VL-7B-Instruct y Qwen3-VL-8B-Instruct en fp16 repartidos entre las dos GPU (carga de 100 a 146 s, unos 0,7 s por prenda y pregunta con lotes de 6); sin entrenar nada.
A cada modelo se le da la foto con la prenda marcada en una caja roja y su recorte («foto») o solo el recorte («recorte») y se le pide un JSON con valores cerrados que se traducen al vocabulario de Víctor; para el tipo, una lista numerada. Examen: 308 prendas de Fashionpedia val (30 por clase de estampado y 40 por clase de forma),
con las etiquetas que salen de los atributos del conjunto; sus fotos son públicas, así que no hay datos de personas de las fuentes de Víctor en Kaggle. Comparación: la capa de regresión logística sobre CLIP B/32 entrenada con 22 000 prendas de Fashionpedia (para estampado y forma) y CLIP B/32 sin entrenar (para el tipo).

| 308 prendas de Fashionpedia val | CLIP B/32 | Qwen2.5-VL-7B | Qwen3-VL-8B |
|---|---|---|---|
| Tipo (13 categorías; el modelo no sabe cuál es la prenda) | 137 de 308 (44 %), sin entrenar | recorte 199 (65 %) · foto 187 (61 %) | recorte 226 (73 %) · **foto 233 (76 %)** |
| Estampado (7 clases) | 202 de 307 (66 %), recall medio 0,59, capa entrenada | recorte 192 (63 %) · foto 188 (61 %) | **recorte 226 (74 %), recall medio 0,65** · foto 215 (70 %) |
| Forma (4 clases) | **150 de 255 (59 %), recall medio 0,61**, capa entrenada | recorte 109 (43 %) · foto 106 (42 %) | recorte 122 (48 %) · foto 118 (46 %) |

Pedirles que describan antes de contestar («foto_razona», 80 prendas) no mejora: Qwen3-VL estampado 50 de 79 (63 %) y forma 35 de 71 (49 %). Con el recorte o con la foto entera sale parecido en estampado y forma; la foto ayuda algo en el tipo (76 frente a 73 %).

**Lectura.** (1) El tipo y el estampado mejoran con claridad: el profesor acierta 30 puntos más que CLIP sin entrenar en tipo y 8 más que la capa entrenada en estampado, aun siendo esa capa un modelo entrenado con las propias etiquetas del conjunto. Los errores de tipo son de ambigüedad entre categorías vecinas
(abrigo ↔ chaqueta 7, camisa ↔ chaqueta 6, top ↔ camisa 4, falda ↔ vestido 4), no de gruesos. (2) La forma no: 48 % frente a 59 % de la capa entrenada. La capa aprende cómo etiqueta Fashionpedia «oversized», «ajustada» o «corta»; el modelo grande tiene su propio criterio. Lo que decide si sirve es medirlo con las etiquetas de Víctor,
que dicen otra cosa de «oversized» que Fashionpedia (la capa sacaba 4 de 23). (3) Qwen2.5-VL-7B queda por debajo de la capa sobre CLIP en todo salvo el tipo; Qwen3-VL-8B es el que se usa de aquí en adelante. (4) No se midió contra Víctor directamente: subir sus 40 fotos a Kaggle se bloqueó por permisos (son personas reales);
en su lugar se usa el profesor sobre fotos públicas y se mide al alumno con las etiquetas de Víctor, que no salen del ordenador (§6.3).

### 6.3 El alumno: nuestro modelo entrenado con las etiquetas del profesor, medido con las de Víctor (8 de octubre, noche)

**Qué se hizo.** Qwen3-VL-8B etiquetó en Kaggle 5 252 prendas públicas de Fashionpedia train (13 categorías de ropa más calzado, bolsos y sombreros; tope de 350 por categoría y 300 por accesorio): primero el tipo entre los 29 de Víctor con la foto entera y luego, sabiendo ese tipo, estampado, tejido y forma sobre el recorte
(dos tareas en paralelo, 103 y 105 minutos en dos GPU T4; ~2,5 s por prenda). Con esas etiquetas se entrenó una regresión logística por atributo sobre los embeddings de CLIP B/32 del recorte (`vlm_profesor/entrenar_alumno.py`), y se midió con las etiquetas de Víctor, que no salieron del ordenador y no se usaron para entrenar.
En el tipo se descartaron 406 etiquetas del profesor que contradecían la categoría de Fashionpedia (p. ej. un «pantalón» etiquetado como falda).

| Atributo | Alumno (prenda principal) | Alumno («cualquiera») | Siempre la más frecuente (principal · cualquiera) | Acuerdo del alumno con el profesor (validación cruzada) |
|---|---|---|---|---|
| Tipo de 29 | 19 de 38 (20 de 38 si el detector pesa 0,5 a 0) | 25 de 38 | 9 de 38 («Sudadera») · flujo actual 19 de 38 (principal) y 24 de 38 | 66 % |
| Estampado | 11 de 22 | 16 de 32 | 11 de 22 · 15 de 32 («liso») | 71 % |
| Tejido | 7 de 15 | 12 de 23 | 10 de 15 · 13 de 23 («algodón») | 51 % |
| Forma | 11 de 23 | 18 de 31 | 11 de 23 · 17 de 31 («oversized / baggy») | 63 % |

**Lectura.** (1) El alumno no mejora lo que había: el tipo queda en 19 o 20 de 38 (50 a 53 %) frente a los 19 del flujo actual, y estampado, tejido y forma empatan con «decir siempre lo más frecuente» (tejido, peor). Con 22 o 23 etiquetas el error típico es de unos 10 puntos: no se distingue de lo anterior.
Con la mitad de las prendas (2 626) el tipo salió 22 de 38, lo que da idea del ruido. (2) CLIP B/32 solo reproduce entre el 51 y el 71 % de lo que dice el profesor (validación cruzada): el recorte a 224 píxeles tiene pocos datos de tejido y de cómo cae la prenda; destilar en esa capa pierde buena parte de lo que el profesor veía.
(3) Hay además una diferencia de criterio entre el profesor y Víctor, que se ve en los fallos: 7 de los 8 fallos de tejido son «algodón» (Víctor) frente a «felpa / polar» (alumno), porque el profesor etiqueta como felpa las sudaderas y capuchas (así lo pedía la guía de mi propio prompt) y Víctor las etiqueta como algodón;
5 de los 12 fallos de forma son «oversized» (Víctor) frente a «regular» (alumno), porque en Fashionpedia «oversized» es mucho más raro (13 %) que en el streetwear de Víctor (la mitad de sus prendas); y en estampado el alumno dice «texto / logo» en prendas que Víctor llama «liso» o «gráfico» (7 fallos). Es decir, parte del problema es de **definiciones**, no solo de capacidad.
(4) Lo que no se sabe es cuánto acierta el propio profesor contra Víctor, porque subir sus fotos a Kaggle se bloqueó por permisos. Esa es la prueba que separa «el modelo grande coincide con Víctor y falla la destilación» de «el modelo grande tiene otro criterio». Sin ella, la conclusión sólida es que la destilación sobre CLIP no basta.

### 6.4 El profesor medido directamente con las etiquetas de Víctor (9 de octubre)

**Método.** Con permiso expreso de Víctor, sus 40 recortes etiquetados (40 fotos de personas reales: 33 de su Biblioteca, 3 de prensa, 2 de Reddit, 2 de X) se subieron a un dataset privado de Kaggle (5,8 MB: foto, caja de la prenda y su tipo; ninguna etiqueta de estampado, tejido ni forma),
se corrió Qwen3-VL-8B-Instruct sin entrenar (9 minutos, 131 s de carga, dos GPU T4) y el dataset se borró al bajar los resultados. Configuraciones: `recorte` y `foto` (estampado, tejido y forma dándole el tipo que puso Víctor); `tipo_recorte` y `tipo_foto` (elegir el tipo entre los 29);
`profesor` (el flujo en dos pasos que etiquetó Fashionpedia: tipo con la foto, y atributos con el recorte y el tipo que eligió él) y `profesor_v2` (igual, con la guía de tejido ajustada tras ver los fallos del alumno: sudadera y capucha de jersey cuentan como algodón; **ajuste hecho mirando las mismas etiquetas, no es una medida limpia**).
Resultados por prenda en `vlm_atributos_prenda/resultados/profesor_victor_2026-10-09/`.

| Prenda principal de Víctor | Flujo / CLIP hasta ahora | Alumno sobre CLIP (§6.3) | Qwen3-VL-8B directo | Siempre la más frecuente |
|---|---|---|---|---|
| Tipo de 29 | 19 de 38 (50 %) | 19-20 de 38 | recorte 24 de 38 (63 %); foto 22; profesor 22 | 9 de 38 |
| Tipo, «cualquiera» | 24 de 38 | 25 de 38 | 27-28 de 38 (71-74 %) | |
| Familia de prenda | 29 de 38 (76 %) | 28 de 38 | 30-33 de 38 (79-87 %) | |
| **Estampado** | 12-13 de 22 | 11 de 22 | **17 de 22 (77 %)** con foto o recorte; profesor 16 | 11 de 22 («liso») |
| Estampado, «cualquiera» | | 16 de 32 | 25-27 de 32 (78-84 %) | 15 de 32 |
| Tejido | 6 de 17 | 7 de 15 | 9 de 15; profesor 8; v2 9 | 10 de 15 («algodón») |
| Forma | 4-9 de 23 | 11 de 23 | foto 14 de 23 (61 %); profesor 13; recorte 11 | 11 de 23 («oversized») |
| Forma, «cualquiera» | | 18 de 31 | foto 22 de 31 (71 %); profesor 17 | 17 de 31 |

**Lectura.** (1) **Estampado: el modelo grande supera el 70 % y casi dobla a «decir liso»** (50 %): liso 9 de 11, gráfico 6 de 7, texto o logo 2 de 3; los fallos son «liso» → «texto / logo» (2, logos pequeños), gráfico ↔ texto (2) y «otro» → camuflaje (1). Con 22 etiquetas el error típico es de unos 9 puntos: la diferencia con la referencia es de tres errores típicos.
(2) **Tejido: no supera a «algodón»** (9 de 15 frente a 10), pero acierta los materiales que se distinguen a simple vista (vaquero, cuero y técnico, 3 de 3) y falla donde hay que separar algodón, punto y felpa (4 de 10 algodones) y en el tul; con 15 etiquetas, 10 de ellas «algodón», la prueba no puede decir más.
(3) **Forma: mejora con la foto entera** (14 de 23, 61 %) frente al recorte (11 de 23): el modelo necesita ver cómo cae la prenda sobre el cuerpo. «Regular» 5 de 5, «oversized» 8 de 11 y «ajustada» solo 1 de 5 (3 veces «corta / cropped»: tops ajustados y cortos a la vez, una ambigüedad del propio vocabulario). No llega al 70 % con la prenda principal.
(4) **Tipo: mejora modesta** (63 frente a 50 %, dentro del margen con 38 prendas); por familia 87 % con el recorte. Los fallos son entre vecinos: camiseta ↔ polo, camisa ↔ chaqueta.
(5) **Conclusión.** El modelo grande sí coincide con Víctor en estampado y en los materiales evidentes, y la destilación sobre CLIP (§6.3) pierde esa ventaja: lo que falla es el alumno (51-71 % de acuerdo con el profesor), no el profesor. Es un argumento para usar el modelo grande dentro del flujo y no destilarlo.
Su coste: una GPU (Kaggle gratuita: ~2,5 s por prenda con dos preguntas, 25 minutos por cada 600 prendas) y que las fotos de cada semana salgan del ordenador a un servicio externo (privado y borrado después). (6) Límites: 15 a 38 etiquetas por atributo (error típico de 8 a 13 puntos), una sola persona etiquetó, fotos de sus propias fuentes;
el umbral del 70 % lo fijé antes de ver el resultado.

### 6.5 El paso semanal con el modelo grande y el lote ciego (9 de octubre)

**Decisión de Víctor (9 de octubre): sí.** A la vista de §6.4, el análisis semanal usa Qwen3-VL-8B en Kaggle en lugar de destilarlo. Coste que asume: las fotos nuevas de personas reales de sus fuentes salen cada semana del ordenador a un dataset privado de Kaggle (borrado en la misma pasada) y el sistema depende de una GPU externa (~25 minutos por cada 600 prendas).
**Diseño** (`analisis_mercado/tendencia_prenda.py vlm`, `vlm_profesor/kernel_profesor.py`): configuración «semanal» = tipo entre los 29 con el recorte (24 de 38 con el recorte, 22 con la foto) y, con ese tipo, estampado, tejido y forma con la foto entera y el recorte (la forma sube de 11 a 14 de 23 con la foto); instrucciones v3 (v2 + «liso» admite logos pequeños). Tolerante a fallos: un lote que falla se repite prenda a prenda.
**Primera pasada real (9 de octubre):** 275 de 276 prendas visibles de 131 fotos; el tipo cambió respecto a CLIP en 169 (61 %); reparto: estampado liso 158, dibujo 38, texto o logo 34, cuadros 19; forma regular 153, oversized 62, corta 23, ajustada 17; tejido algodón 190, cuero 25, punto 23, técnico 18.
**Lote ciego:** 60 recortes al azar (uno por foto, de fotos sin ninguna etiqueta de Víctor, con la etiqueta del modelo grande ya puesta y sin sugerencias en la página; 38 urbano y 22 geek; 18 de España, 8 de EEUU y 34 de la Biblioteca) en la página «Etiquetar prendas» (lote `b3-`, mapa en `tendencia_datos/etiquetado_lote3_estado.json`, claves en `lote_ciego.json`). Las instrucciones del modelo están **congeladas** hasta medirlo (las 40 fotos de la prueba ya se usaron para ajustarlas); al importar las etiquetas, `fiabilidad_prenda.py` sustituye las cifras de la prueba por las del lote ciego.

**Resultado del lote ciego (9 de octubre, tarde).** Víctor contestó 53 de los 60 recortes: 32 con etiquetas, 21 «inservibles», 7 sin contestar. Con la prenda principal: tipo 17 de 32 (53 %), **igual que CLIP en los mismos recortes (17 de 32)**; familia 27 de 32 (84 %); estampado 23 de 27 (85 %) frente a 21 de 27 (78 %) de «siempre liso»; forma 15 de 27 (56 %) frente a 13 de 27 (48 %); tejido 14 de 26 (54 %) frente a 7 de 26 (27 %) de «siempre algodón».
Solo el tejido se distingue de su referencia; el tipo no mejora a CLIP (la mejora de 50 a 63 % de la prueba con las 40 fotos no se confirma: otra muestra, márgenes de ±15 a ±17 puntos). Errores sistemáticos: «oversized» dicho «regular» (5 de 9), «ajustada» dicha «corta» o «regular» (4 de 5), «no se distingue» dicho «algodón» (4 de 5), vaquero dicho algodón (2 de 5).
**El 40 % de los recortes contestados eran inservibles** (en los lotes 1 y 2, elegidos por variedad, solo 3 % y 8 %): torso geométrico 4 de 4, grounding 2 de 4, DeepFashion2 14 de 44 (32 %). El filtro que debía excluir el torso comparaba con «torso» y la detección se llama «torso (geometrico)»: corregido (`valida()`), y el informe ya no cuenta esas detecciones.
`fiabilidad.json` toma desde ahora las cifras del lote ciego (tipo baja, familia media, estampado media, forma baja, tejido baja); las instrucciones v3 siguen congeladas y el lote ya no es ciego para cualquier ajuste.

**Filtro de recortes inservibles con el modelo grande (9 de octubre, noche).** Se probó a preguntarle al modelo grande, con la foto marcada y el recorte, si el recuadro es «una prenda bien visible puesta en una persona» (y no piel, manos, fondo, un trozo cortado o borroso, o un recuadro que mezcla prendas), con un criterio normal (`usable_a`) y otro más estricto (`usable_b`), sobre los 93 recortes que Víctor etiquetó o marcó como inservibles (72 utilizables, 21 inservibles; sus marcas no se subieron).
Resultado: `usable_a` descarta 2 de 21 inservibles y 0 de 72 utilizables; **`usable_b` descarta 6 de 21 (29 %, IC 14 a 50 %) y 0 de 72 utilizables (IC 0 a 5 %)**; cuando descarta, acierta 6 de 6; todos los descartes son «no es una prenda». Es un filtro **seguro pero flojo**: deja pasar 15 de los 21 inservibles.
Mirando los 21 recortes, el criterio de Víctor es más amplio que el del modelo: caras y torsos sin prenda, fragmentos y detalles ampliados (una cintura, un zapato cortado, un estampado de cómic), cosas que no son prendas (un cartel de neón, un plato de comida, la portada de una revista), fotos en blanco y negro y recuadros que mezclan prendas. Por eso no se ha integrado en el paso semanal (cuesta un 36 % más de tiempo y quita 1 de cada 3,5 inservibles); el arreglo del torso geométrico (4 de 21) sí.
Siguiente prueba posible, derivada de su regla ya documentada («cuenta si se ve más de la mitad de la prenda»): pedir al modelo la fracción visible y un filtro por foto («¿es un outfit con las prendas a la vista?»). Las 21 marcas ya no son un examen limpio para ajustar un filtro; haría falta otro lote.

### 6.6 Revisión «OK / más o menos / No» y comparación entre estilos (10 de octubre)

**Qué pidió Víctor.** Al ver los resultados a ciegas dijo que «no está tan mal, a veces no es blanco o negro»: quería, en la siguiente revisión, ver lo que había valorado el modelo de cada recorte y contestar OK, «más o menos» (y qué más podría ser) o No (y qué es). Después de hacerla fijó el criterio del proyecto: **con un acierto de en torno al 70 % basta; lo importante es separar por estilo**.
**Diseño** (`analisis_mercado/revisar_valoraciones.py`, Artifact «Revisar valoraciones»): 54 recortes mezclados al azar; 24 de la «parte A» (recortes del lote ciego en los que el modelo y su etiqueta principal discrepaban en algún atributo), 30 de la «parte B» (recortes nuevos, uno por foto, con valoración del modelo) y, dentro de la B, **6 de control** con la valoración de otro recorte de otra familia de prenda (para medir si el OK sale demasiado fácil; se avisó de que había «unos pocos» sin decir cuáles). Respuestas por fila (tipo, estampado, tejido, forma): OK, «más o menos» con las alternativas que también valen, o No con lo que es. Marcó 6 recortes «no sirve» (4 eran controles): quedan 48 con respuesta, 46 reales y 2 de control. La primera versión de la página tenía un fallo (la base de datos entrega los datos como solo lectura y la página intentaba modificarlos tras el primer guardado, así que no dejaba cambiar lo marcado); se corrigió y no se perdió ninguna respuesta.

| Atributo | OK | Más o menos | No | Aceptable (OK + más o menos) | Solo OK | A ciegas (lote ciego) |
|---|---|---|---|---|---|---|
| Tipo (46) | 40 | 1 | 5 | **41 (89 %, IC 77 a 95 %)** | 40 (87 %) | 17 de 32 (53 %) |
| Estampado (46) | 43 | 0 | 3 | **43 (93 %, IC 82 a 98 %)** | 43 (93 %) | 23 de 27 (85 %) |
| Tejido (45) | 33 | 5 | 7 | **38 (84 %, IC 71 a 92 %)** | 33 (73 %) | 14 de 26 (54 %) |
| Forma (46) | 41 | 4 | 1 | **45 (98 %, IC 89 a 100 %)** | 41 (89 %) | 15 de 27 (56 %) |

En los 24 recortes nuevos (parte B, la muestra que mejor representa lo que hace cada semana el paso semanal): tipo 21 de 24, estampado 22 de 24, tejido 20 de 23, forma 23 de 24. En la parte A (22 recortes con respuesta): tipo 20 de 22, estampado 21 de 22, tejido 18 de 22 y forma 22 de 22 aceptables; cuando Víctor discrepa de lo que puso a ciegas, sus alternativas incluyen su etiqueta anterior en 12 de 14 casos, es decir, que no se limita a aceptar lo que ve (en el tejido mantiene su etiqueta anterior: 9 de las 10 discrepancias previas siguen siendo «más o menos» o «No»).
**Dónde falla el tipo.** Las etiquetas del modelo se dieron por buenas 37 de 38 veces salvo «Camisa»: **4 de 8**. De los 5 «No», 4 fueron «Camisa» (para una chaqueta, una falda, un pantalón o una camiseta) y 1 «Top» (un pantalón): casi siempre hay otra prenda en el recorte, o el modelo contesta por la prenda más visible y no por la detectada. El informe baja la confianza de «Camisa» a baja y lo avisa en la fila. Errores de otros atributos: estampado «texto o logo» o «dibujo» en prendas lisas (3), tejido «algodón» donde Víctor ve vaquero, técnico o lino (2 cada uno), forma «regular» frente a «oversized» o «ajustada» (4 «más o menos»).
**Una regla con el detector no ayuda.** En 4 de los 5 «No» del tipo el detector de prendas tenía la categoría correcta (falda, pantalón, abrigo), así que se probó mandar el tipo del detector cuando el modelo grande contradice su familia en prendas de abajo o calzado: en el lote ciego 18 frente a 17 de 32, en los lotes 1 y 2 21 frente a 24 de 38, y en la revisión corrige la familia en 3 recortes y estropea 4 en los que Víctor había dicho OK. No se aplica: el recorte suele contener varias prendas y las dos respuestas pueden valer.

**Cómo leerlo.** Es una vara **más generosa** que etiquetar a ciegas: se ve la respuesta del modelo (posible sesgo de anclaje) y lo dudoso vale. El acierto real queda entre las dos columnas. **Los 6 controles no resultaron concluyentes:** 4 los marcó «no sirve» (no se sabe si por la valoración absurda o por el recorte; entre los otros 48 recortes solo 2 se marcaron así) y en los otros 2 la valoración «equivocada» valía para otra prenda del recorte (un pantalón y una chaqueta en recortes con varias prendas). Con su criterio del 70 %, los cuatro atributos lo cumplen en esta muestra, con márgenes de ±6 a ±10 puntos.
**Efecto en el sistema** (`fiabilidad_prenda.py`): la revisión se añade a cada `vlm_*` y sube el techo de confianza a **media** en tipo, estampado, tejido y forma (límite inferior del intervalo de «aceptable» ≥ 65 %, el mismo umbral que a ciegas); «alta» solo se alcanza a ciegas. Los tipos con 6 o más revisados y menos del 65 % aceptado (hoy «Camisa») salen con confianza baja y un aviso.

### 6.7 ¿Se separan el geek y el urbano? (10 de octubre)

**Pregunta.** Si lo importante es separar por estilo y el modelo acierta en torno al 70 %, ¿se distinguen los dos estilos a nivel de prenda con lo que ya mide el modelo grande? (`analisis_mercado/separacion_estilos.py`; lo recalcula `tendencia_prenda.py informe`; `tendencia_datos/separacion_estilos.json`; en la app, pestaña «Prendas», «Qué distingue al geek del urbano».)
**Método.** Prendas visibles y válidas con valoración del modelo grande, comparadas por estilo (el estilo lo da la persona de referencia, no la foto). Para cada categoría, diferencia de cuota geek − urbano con intervalo del 95 % por **bootstrap por foto** (las prendas de una foto no son independientes) y p de **permutación por foto**; q de Benjamini-Hochberg dentro de cada dimensión (comparar muchas categorías a la vez fabrica falsos positivos); prueba global por dimensión con la distancia de variación total. Dos alcances: **solo las fotos aprobadas de Víctor** (la Biblioteca: 169 prendas; geek 91 en 42 fotos, urbano 78 en 39, mismo origen en los dos estilos) y **todas las fuentes** (261 prendas; geek 94 en 44 fotos, urbano 167 en 85).

**Solo la Biblioteca (la comparación limpia).**
- **familia**: prueba global p = 0,136 (distancia 0.14). Abrigo geek 8 % frente a urbano 20 % (dif. -13 puntos, IC -25 a -1, p = 0,034, q = 0,136)
- **tipo**: prueba global p = 0,013 (distancia 0.31). Top geek 15 % frente a urbano 1 % (dif. +14 puntos, IC +6 a +24, p = 0,005, q = 0,060)
- **estampado**: prueba global p = 0,473 (distancia 0.14). ninguna categoría destaca por sí sola.
- **tejido**: prueba global p = 0,011 (distancia 0.21). punto geek 19 % frente a urbano 4 % (dif. +15 puntos, IC +5 a +25, p = 0,007, q = 0,035); denim (vaquero) geek 1 % frente a urbano 8 % (dif. -7 puntos, IC -14 a +0, p = 0,040, q = 0,100)
- **forma**: prueba global p = 0,005 (distancia 0.29). oversized / baggy geek 15 % frente a urbano 40 % (dif. -24 puntos, IC -39 a -9, p = 0,003, q = 0,013); corta / cropped geek 19 % frente a urbano 3 % (dif. +16 puntos, IC +5 a +27, p = 0,013, q = 0,022); ajustada geek 14 % frente a urbano 1 % (dif. +13 puntos, IC +4 a +23, p = 0,011, q = 0,022)

**Todas las fuentes.**
- **familia**: prueba global p = 0,111 (distancia 0.13). Abrigo geek 7 % frente a urbano 20 % (dif. -13 puntos, IC -22 a -3, p = 0,021, q = 0,086)
- **tipo**: prueba global p = 0,001 (distancia 0.44). Top geek 15 % frente a urbano 2 % (dif. +13 puntos, IC +5 a +22, p = 0,002, q = 0,022); Camiseta manga corta geek 5 % frente a urbano 16 % (dif. -11 puntos, IC -19 a -2, p = 0,026, q = 0,078); Polo geek 0 % frente a urbano 7 % (dif. -7 puntos, IC -11 a -2, p = 0,022, q = 0,078); Pantalón geek 3 % frente a urbano 10 % (dif. -6 puntos, IC -12 a -1, p = 0,042, q = 0,090); Falda geek 6 % frente a urbano 1 % (dif. +6 puntos, IC +1 a +11, p = 0,004, q = 0,034); Botas geek 6 % frente a urbano 1 % (dif. +5 puntos, IC +1 a +10, p = 0,018, q = 0,078); Jersey geek 5 % frente a urbano 1 % (dif. +5 puntos, IC +0 a +11, p = 0,034, q = 0,085)
- **estampado**: prueba global p = 0,072 (distancia 0.19). liso geek 48 % frente a urbano 63 % (dif. -15 puntos, IC -29 a +0, p = 0,044, q = 0,156); gráfico / dibujo geek 21 % frente a urbano 9 % (dif. +12 puntos, IC +1 a +24, p = 0,023, q = 0,156)
- **tejido**: prueba global p = 0,019 (distancia 0.17). punto geek 19 % frente a urbano 3 % (dif. +16 puntos, IC +7 a +26, p = 0,001, q = 0,003)
- **forma**: prueba global p = 0,002 (distancia 0.27). regular geek 46 % frente a urbano 62 % (dif. -16 puntos, IC -31 a -1, p = 0,043, q = 0,072); corta / cropped geek 18 % frente a urbano 2 % (dif. +16 puntos, IC +6 a +26, p = 0,001, q = 0,005); ajustada geek 14 % frente a urbano 2 % (dif. +11 puntos, IC +3 a +21, p = 0,004, q = 0,010)

**Lectura.** Con las fotos de Víctor los estilos **se separan en forma, tejido y tipo de prenda** (p entre 0,005 y 0,013) y **no en estampado ni en familia**: el urbano es mucho más oversized (40 % frente a 15 %), el geek más corta/cropped y ajustada, con más punto y más tops, faldas y botas; el urbano, más abrigos, camisetas de manga corta y pantalones. Con todas las fuentes se mantienen el top, el punto y las formas ajustada y cropped, y el tipo se separa todavía más (p = 0,001) pero aparece el confundido de origen: el geek es casi todo de la galería de Víctor y el urbano mezcla galería y mercado (por ejemplo, el «oversized» se diluye en el mercado).
**Robustez al acierto del 70 %.** Si el modelo falla al azar con probabilidad 1 − a, la diferencia observada es aproximadamente a veces la real: se encoge, no se inventa (columna «real≈» del JSON). Podría inventarse si el modelo fallase distinto en un estilo que en otro; en la revisión lo dio por bueno casi igual en geek (89 a 95 % según el atributo) que en urbano (81 a 100 %), con 19 y 27 recortes: no hay indicio, pero la muestra es pequeña.
**Cuello de botella.** En el mercado real casi no hay geek para comparar: la temporada otoño-invierno 2026/27 en España tiene 2 fotos geek y EEUU ninguna; todo el geek sólido es de la galería. La separación por estilo funciona hoy con las fotos aprobadas de Víctor, no con lo que se lee de X, prensa y Reddit.

### 6.8 La tarea semanal en la nube y la revista por correo (11 y 12 de octubre)

**Petición de Víctor (11 de octubre, sin acceso a los robots por estar fuera de Madrid):** que el análisis corra todos los lunes **sin encender su ordenador** y recibir por correo «algo como una revista semanal» con los cambios del mercado, el porcentaje de acierto y lo que ha considerado.
**Diseño.** `.github/workflows/tendencia_semanal.yml` (en `main`, que es de donde GitHub programa: lunes 02:30 y 05:30 UTC y disparo manual), con el código de la rama `analisis-mercado` y los datos generados en la rama `datos-tendencia` (`fotos.json`, `prendas.json`, `estado.json`, `informe.json`, `separacion_estilos.json`, `embeddings.npz`, `registro_semanal.txt`), para que los commits de la tarea no choquen con los de código. Pasos: cosechar (X por FxTwitter, prensa por Bing News con tres intentos, Reddit) → fotos nuevas con persona y ropa y sin repetidas (el embedding CLIP de cada foto se guarda por identificador: no hace falta la caché de imágenes) → analizar en CPU (DeepFashion2 + Florence-2 + CLIP; unos 18 s por foto, como en el portátil) → modelo grande en Kaggle (dataset privado que se borra) → informe y comparación entre estilos → guardar datos → correo por SMTP (secretos de GitHub) → marca de edición enviada.
**Revista** (`revista_semanal.py`, HTML de correo de unos 55 a 70 KB, por debajo del recorte de Gmail): 01 lo que se lleva (por estilo y mercado, con margen y confianza de cada cifra y miniaturas), 02 qué ha cambiado (últimas 4 semanas frente a las 4 anteriores, con p de la diferencia, y novedades de la semana), 03 qué distingue a cada estilo, 04 cuánto fiarte (acierto a ciegas y en la revisión de Víctor, techo de confianza, señales internas, punto débil «Camisa»), 05 qué ha considerado (fuentes con su estado, filtros y método), 06 para la próxima. Si el modelo grande falla, el grupo lo avisa (usa el tipo de CLIP, menos fiable); si la tarea falla, llega un aviso corto con el enlace al registro.
**Qué pasó el primer día.** Prueba manual (11 de octubre, 12 min): la cosecha, el análisis y el correo funcionaron desde GitHub (X y Reddit responden; Bing News falla a ratos con respuestas que no son XML, de ahí los reintentos) y falló solo el paso de Kaggle, porque la CLI exige un `kaggle.json` aunque se autentique con el token nuevo (corregido y probado en un entorno limpio). **GitHub retrasa mucho las tareas programadas de este repositorio:** la del lunes 12 salió 7 horas tarde (los huecos medidos de la ingesta horaria ya eran de 3 a 7 h), por eso hay un segundo horario y una marca (`ultima_revista.txt`) para que una ejecución programada no repita la revista que ya se lanzó a mano; ese día llegaron dos correos iguales.
**Fotos que solo están en el portátil.** Para analizar en la nube la Biblioteca de los cinco estilos nuevos (316 fotos, 44 MB) sin que el portátil haga el trabajo pesado (el ventilador sonaba), se suben a un dataset **privado** de Kaggle como **un solo fichero**: Kaggle abre los `.zip` y los `.tar` y reparte su contenido en cientos de ficheros (el dataset entero daba 404 y bajarlos uno a uno, 429), así que se sube un tar con extensión `.bin`, que se baja de una vez (44 MB en 11 s). La tarea lo baja, analiza, etiqueta y borra el dataset solo si todo ha ido bien.
**Privacidad.** El repositorio es público: solo hay identificadores, direcciones públicas, cajas y etiquetas, nunca fotos; los registros de la tarea no imprimen secretos ni correos; las fotos nuevas van a un dataset privado de Kaggle que se borra en la misma pasada. La revista lleva miniaturas de prendas (recortes de fotos públicas) por el servicio de correo de Google.
**Resultado.** Ejecución manual completa del 12 de octubre: 2 h 49 min (224 fotos nuevas analizadas en CPU a unos 18 s cada una y 655 prendas etiquetadas en un kernel de Kaggle de unos 32 min); Víctor recibió la revista y se veía bien en el móvil.

### 6.9 Los siete estilos (12 de octubre)

**Por qué solo había dos.** El 6 de octubre Víctor decidió «empezar por geek y urbano» y el análisis por prenda, el artefacto y la revista se montaron solo para ellos; el 11 de octubre pidió los demás («separar por estilo» era entre los siete de la app). El clasificador de estilos de la app tiene siete clases y 404 fotos aprobadas por Víctor: old money 80, clásico 72, lujo ostentoso 72, convencional 60, geek 42, urbano 40 y bohemio 38.
**Método.** Las 404 fotos pasan por el mismo flujo (detector DeepFashion2 + Florence-2 + CLIP y, después, el modelo grande Qwen3-VL-8B en Kaggle). `separacion_estilos.py` (`por_estilo`) compara **cada estilo con la suma de los demás**: diferencia de cuota por categoría con intervalo del 95 % por bootstrap por foto, p de permutación por foto y q de Benjamini-Hochberg dentro de cada estilo y dimensión, más una prueba global entre los siete estilos por dimensión (distancia de variación total media frente al reparto general, ponderada por prendas).
**Resultado (solo Biblioteca: 794 prendas con etiqueta del modelo grande, el 99 al 100 % de cada estilo).** Los siete estilos se distinguen en **las cinco dimensiones** (familia, tipo, estampado, tejido y forma) con una probabilidad de azar menor del 0,1 % en cada una (1 entre 1 001 permutaciones). Lo que más distingue a cada estilo frente al resto:
- **Clásico** (153 prendas, 71 fotos): abrigo (47 % frente a 14 %), chaqueta (31 % frente a 5 %), chaleco sin mangas (7 % frente a 1 %), forma regular (85 % frente a 54 %); casi nada oversized (4 % frente a 14 %) ni con logo.
- **Old money** (184, 80): americana (23 % frente a 4 %), camisa (25 % frente a 12 %), zapatos de vestir (16 % frente a 4 %), liso (84 % frente a 64 %), abrigo; casi nada oversized (3 % frente a 15 %).
- **Lujo ostentoso** (76, 55): texto o logo (51 % frente a 4 %), bolsos (32 % frente a 0 %), cuero o vinilo (34 % frente a 13 %); poco liso (21 % frente a 74 %).
- **Bohemio** (76, 38): estampado «otro» (28 % frente a 4 %), tops (21 % frente a 4 %), forma cropped (20 % frente a 4 %), vestidos y cuerpo entero (13 % frente a 2 %); sin abrigos (1 % frente a 22 %).
- **Convencional** (136, 60): liso (90 % frente a 64 %), punto (18 % frente a 8 %), forma ajustada (15 % frente a 8 %).
- **Urbano** (78, 39): oversized (40 % frente a 9 %), hoodie (10 % frente a 2 %), algodón (73 % frente a 57 %).
- **Geek** (91, 42): gráfico o dibujo (22 % frente a 5 %), tops (15 % frente a 4 %), cropped (19 % frente a 4 %), hoodie; poco liso (47 % frente a 71 %).
Los rasgos coinciden con las descripciones que Víctor escribió de cada estilo (el cayetano de Barbour y chalecos, el lujo de logos grandes, el bohemio de telas fluidas…), lo que respalda tanto el método como las etiquetas del modelo grande.
**Límites.** (1) Es una **muestra de referencia** (fotos que Víctor aprobó para cada estilo, sin fecha ni mercado): describe el estilo, no lo que se lleva ahora; para eso hacen falta personas de referencia y fuentes de mercado de los cinco estilos nuevos (propuestas en la pestaña «Estilos» del artefacto, pendientes de su revisión). (2) El **acierto del modelo grande solo está medido en geek y urbano** con sus etiquetas; en los cinco estilos nuevos (bolsos, vestidos, americanas, zapatos de vestir…) puede ser distinto: pendiente una revisión corta («OK / más o menos / No»). (3) Las fotos de cada estilo las eligió Víctor, así que parte de lo que distingue a un estilo viene de su criterio de selección, no solo de la moda.

