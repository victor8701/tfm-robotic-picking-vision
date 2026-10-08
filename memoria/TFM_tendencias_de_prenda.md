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
