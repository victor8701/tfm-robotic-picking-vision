# Análisis de resultados por etapas: qué acertó cada parte del proyecto, contra qué y con cuántos datos

**Autor:** Víctor Martín Parra, con el asistente · **Fecha:** 9 de octubre de 2026 · **Estado:** vivo (se actualiza al repetir las mediciones; la versión visual está en el Artifact «Resultados por etapas»)
**Qué es:** un repaso transversal de todas las cifras de acierto que ha dado el proyecto desde el clasificador de catálogo hasta la tendencia por prenda, ordenadas por etapa, con su **referencia**, su **muestra** y su **margen**, y lo que enseñan en conjunto.
**Qué no es:** un resumen para quitar matices. Cada cifra remite al documento donde está medida (§7); si dos números parecen contradecirse, es porque se midieron de forma distinta y eso se explica aquí (§3.3).

## 0. Cómo leer las cifras

- **Referencia.** Un acierto solo dice algo frente a lo que se obtendría sin el modelo: el **azar** (1 de 6 = 17 %), **«decir siempre la clase más frecuente»** (50 % en estampado si la mitad son lisas) o **el método anterior**. Casi todas las lecturas de este documento son «cuánto mejora sobre la referencia».
- **Margen.** Con n pequeña el acierto tiene mucho ruido. Intervalo de Wilson al 95 % para un 60 % de acierto: n = 15 → 36 a 80 %; n = 22 → 40 a 77 %; n = 38 → 44 a 74 %; n = 100 → 50 a 69 %; n = 308 → 54 a 65 %; n = 500 → 56 a 64 %. **Con 15 a 38 etiquetas (lo que hay para estampado, forma, tejido y tipo de prenda de Víctor) solo se distinguen diferencias de 20 puntos o más.**
- **Prenda principal frente a «cualquiera».** Un recorte puede llevar varias prendas. «Principal» = la que Víctor eligió primero (la que llena el recorte); «cualquiera» = coincide con alguna de las que etiquetó. «Cualquiera» es más indulgente: sube el tipo del 50 % al 63 %. Salvo que se diga otra cosa, aquí se usa **principal**.
- **Quién juzga.** Etiquetas de Víctor (referencia humana), etiquetas de catálogo (Kaggle, con ruido conocido), o revisión a ojo del asistente (la más débil: un solo juez, sin ciego). Cada fila indica cuál.

## 1. Mapa de etapas

| # | Etapa | Pregunta | Qué se construyó | Resultado principal | Veredicto |
|---|---|---|---|---|---|
| 0 | Descartada: prendas en bolsas | ¿se pueden desembalar prendas en bolsas de plástico? | OpenCV (HSV, Hough) + YOLOv8 | sin cifras; el plástico impone una limitación mecánica | descartada |
| 1 | CLIP sin entrenar | ¿CLIP puede clasificar el estilo de una prenda por texto? | emparejado tendencia ↔ prenda (`clip_trend_matching`) | 32,8 % en 1 de 6 (1 207 imágenes); `fiesta_noche` 0 % | no basta |
| 2 | Clasificador propio (Florence-2 + LoRA) | ¿un modelo abierto afinado supera a CLIP y a los LLM generales? | cinco adapters v1 a v5 sobre catálogo | media de 5 campos 50,3 → 84,2 %; estilo no visto 36,9 → 63,9 %; 85 % frente a 74-76 % de Claude y Gemini | funciona en catálogo |
| 3 | Fotos de calle | ¿sirve en fotos reales con personas? | detector DeepFashion2 + recorte + clasificación por prenda | foto entera: «accesorio» en 12 de 19; por looks 13 → 16 de 19 | parcial |
| 4 | Ingesta de fotos de X | ¿se pueden traer fotos útiles automáticamente? | búsqueda por texto (Tavily), filtros, panel | 17 % útiles con búsqueda automática; 54 % con filtro aprendido | parcial |
| 5 | Experimento B | ¿aporta evidencia visual al vector de tendencia? | texto frente a visual frente a fusión, puntuado a ciegas | texto bien especificado 70 %, visual 33 %, fusión 50 % (P@5) | negativo para lo visual |
| 6 | 7 estilos y «Analizar mercado» | ¿qué estilo domina por mercado? | clasificador de 7 estilos, Biblioteca, informe por mercado | CV 78 %; con fotos nuevas de medios 2 de 10 | útil como herramienta, flojo fuera de su fuente |
| 7 | Tendencia por prenda | ¿qué prendas, con qué forma, estampado y tejido, se llevan en cada estilo? | flujo semanal, etiquetado a toques, pestaña «Prendas» | tipo 50 → 63 %, estampado 50 → 77 % con el modelo grande; forma 61 %; tejido sin mejora | en curso |
| 8 | Texto de tendencia con datos medidos | ¿un texto hecho con lo que mide el análisis recupera mejor las prendas de una tendencia que el de un LLM que solo conoce el nombre? | `texto_tendencia.py` + Experimento C (puntuación humana a ciegas, diseño fijado antes) | P@5 83 % frente a 37 % (corto ciego) y 70 % (oráculo); +47 pp, IC95 % [+30, +64], 6 de 6 tendencias | positivo, con un solo juez y 6 tendencias |

## 2. Cifras por etapa

Intervalos de Wilson al 95 %. «k de n» cuando hay recuento; «≈» cuando solo se dispone del porcentaje.

### Etapa 1: CLIP sin entrenar

| Medida | Referencia | Resultado | n | Nota |
|---|---|---|---|---|
| Estilo de una prenda de catálogo (1 de 6) | azar 16,7 % | **32,8 %** (≈ 396 de 1 207; IC 30 a 36 %) | 1 207 | `fiesta_noche` 0 %, `casual` 18 %; CLIP **gana** en `de_vestir` (87 % frente a 57 %) |

### Etapa 2: Florence-2 + LoRA (catálogo)

| Medida | Referencia | Resultado | n | Nota |
|---|---|---|---|---|
| Media de 5 campos en test (categoría, color, estilo, género, temporada) | sin afinar 50,3 % (mayoritaria 39,0 %) | **84,2 %** | 500 imágenes × 5 | JSON válido 100 %; `temporada` 58,2 → 60,2 %: el ajuste no aporta nada ahí |
| Estilo en imágenes que el modelo no había visto | CLIP 36,9 % | **63,9 %** (237 de 371; IC 59 a 69 %) | 371 | la primera cifra (73,4 %) estaba **contaminada** por imágenes vistas en entrenamiento |
| Acuerdo con etiquetas humanas | Kaggle frente al humano: 86 % en estilo, 45 % en `temporada` | v1 **79 %**; v3 **85 %** (mejor); v4 y v5 83 % | 100 fichas (120 en v5) | `temporada`: el techo lo pone la definición de la etiqueta |
| Frente a LLM comerciales sin afinar | Claude 74 %, Gemini Flash-Lite 76 % | **85 %** (v3) | 50 fichas × 5 campos | gana en estilo (+24-28 puntos) y temporada (+20-24), pierde en color (64 % frente a 70-74 %) |

### Etapa 3: fotos de calle

| Medida | Referencia | Resultado | n | Nota |
|---|---|---|---|---|
| Estilo del look, persona principal | foto entera 13 de 19 (68 %) | **16 de 19 (84 %)** con detectar → recortar → clasificar | 19 fotos | `accesorio` en 12 de 19 fotos enteras: síntoma del salto de dominio |
| Cajas de prenda correctas | heurísticas sobre Florence 80 de 86 (93 %) | **84 de 89 (94 %)** con DeepFashion2 | 19 fotos | lo que cambia es de dónde vienen: heurísticas 29 → 5 % de las cajas; auditoría hecha por el asistente |

### Etapa 4: ingesta de fotos de X

| Medida | Referencia | Resultado | n | Nota |
|---|---|---|---|---|
| Fotos útiles entre las que revisa Víctor | búsqueda automática por texto **17 %** (35 de 209) | filtro aprendido de sus decisiones **54 %** al conservar el 90 % de las útiles (AUC 0,92) | 359 decisiones | estimado en validación cruzada; **no está integrado** en la búsqueda. CLIP «persona con ropa» sin entrenar: 41 %; curadas a ojo por el asistente 76-80 %; subidas por Víctor 78 % |
| Origen del problema | — | la búsqueda mira el texto, nunca la imagen: ≤ 20 resultados por búsqueda, ~1 de cada 5 útil | — | una causa estructural (lista de ya procesadas ignorada) se encontró el 28 de septiembre |

### Etapa 5: Experimento B (vector de tendencia)

| Medida | Referencia | Resultado | n | Nota |
|---|---|---|---|---|
| Prendas buenas en el top 5 de cada tendencia (v2) | evidencia visual (10 fotos): **33 %** | texto bien especificado **70 %**; fusión 50 %; texto sin conocer la taxonomía 30-37 % | 6 tendencias × 5 | v1 (pre-registrada) neutra; **domina conocer qué significa cada estilo**, no la longitud ni lo visual |

### Etapa 6: 7 estilos y «Analizar mercado»

| Medida | Referencia | Resultado | n | Nota |
|---|---|---|---|---|
| Estilo (7 clases), validación cruzada | CLIP sin entrenar **59 %** | sonda lineal **78 %** con 10 fotos por estilo (meseta hasta 20) | 168 fotos confirmadas | el límite es la ambigüedad entre estilos vecinos, no el volumen; el sesgo de fuente es real (41 de 44 «lujo» son bolsos) |
| Estilo con fotos nuevas de medios españoles | azar 14 % | **2 de 10 (20 %)** | 10 (de 18; 8 no eran un outfit) | el 44 % de las fotos de medios no eran una persona con ropa visible |
| Fotos que Víctor da por buenas, por fuente | — | r/LouisVuitton 32 de 33, Barbour 22 de 29, Preppy 14 de 18; hola y semana 3 de 13; cuentas oficiales de marcas 0 de 5 | 135 | la fuente decide más que el modelo |

### Etapa 7: tendencia por prenda

Etiquetas de Víctor (prenda principal): tipo n = 38, estampado 22, forma 23, tejido 15 (14 donde «no se distingue» queda fuera). Referencia = «decir siempre lo más frecuente».

| Método | Tipo (29) | Estampado | Forma | Tejido |
|---|---|---|---|---|
| Siempre lo más frecuente | 9 de 38 (24 %) | 11 de 22 (50 %) | 11 de 23 (48 %) | 10 de 15 (67 %) |
| CLIP B/32 sin entrenar (flujo semanal anterior) | 19 de 38 (50 %) | 9 de 22 (41 %) | 11 de 23 (48 %) | 4 de 14 (29 %) |
| Capa sobre CLIP B/32 entrenada con 22 000 prendas de Fashionpedia | | 12 de 22 (55 %) | 4 de 23 (17 %) | |
| Igual con CLIP L/14 (2 800 prendas) | | 13 de 22 (59 %) | 4 de 23 (17 %) | |
| Florence-2 describe el recorte (palabras clave) | | 13 de 22 (59 %) | 10 de 23 (43 %) | 9 de 14 (64 %) |
| Alumno: capa sobre CLIP entrenada con las etiquetas del modelo grande (5 252 prendas) | 20 de 38 (53 %) | 11 de 22 (50 %) | 11 de 23 (48 %) | 7 de 15 (47 %) |
| **Modelo grande directo** (Qwen3-VL-8B, sin entrenar) | **24 de 38 (63 %)** | **17 de 22 (77 %)** | **14 de 23 (61 %)** | 9 de 15 (60 %) |
| Modelo grande como en el paso semanal (instrucciones v1, con su propio tipo) | 22 de 38 (58 %) | 16 de 22 (73 %) | 13 de 23 (57 %) | 8 de 15 (53 %) |
| **Lote ciego**: modelo grande en el paso semanal (instrucciones v3), 32 recortes al azar etiquetados después | 17 de 32 (53 %) | 23 de 27 (85 %) | 15 de 27 (56 %) | 14 de 26 (54 %) |
| Lote ciego: referencia «siempre lo más frecuente» (esa muestra) | 8 de 32 (25 %, «Chaqueta») | 21 de 27 (78 %, «liso») | 13 de 27 (48 %, «regular») | 7 de 26 (27 %, «algodón») |
| Lote ciego: CLIP (el tipo que había) en los mismos recortes | 17 de 32 (53 %) | | | |

**Lote ciego (9 de octubre).** 60 recortes al azar, uno por foto, con la etiqueta del modelo grande ya puesta y sin sugerencias en la página; Víctor contestó 53: **32 con etiquetas, 21 «inservibles» y 7 sin contestar**. Con la prenda principal: tipo 17 de 32 (53 %, IC 36 a 69 %), **igual que CLIP en los mismos recortes (17 de 32)**, y por familia 27 de 32 (84 %) frente a 28 de 32 (88 %) de CLIP;
estampado 23 de 27 (85 %, IC 68 a 94 %) frente a 21 de 27 (78 %) de «siempre liso» (liso 19 de 21; con estampado 4 de 6); forma 15 de 27 (56 %, IC 37 a 72 %) frente a 13 de 27 (48 %) de «regular» («oversized» 4 de 9, con 5 de las 9 dichas «regular»; «ajustada» 1 de 5);
tejido 14 de 26 (54 %, IC 35 a 71 %) frente a 7 de 26 (27 %) de «algodón»: **la única medida que se distingue de su referencia** (cuero 4 de 4, técnico 2 de 2, algodón 5 de 7; vaquero 2 de 5, lino 0 de 2, «no se distingue» 1 de 5).

**Qué es distinguible.** El estampado del modelo grande (17 de 22, IC 57 a 90 %) deja fuera el 50 % de «siempre liso». El tipo (24 de 38, IC 47 a 77 %) incluye el 50 % del flujo anterior: la mejora de 50 a 63 % es una indicación, no una certeza. Forma (IC 41 a 78 %) y tejido (IC 36 a 80 %) incluyen su referencia.

Familia de prenda (arriba, abrigo, abajo, cuerpo entero, calzado, accesorio): flujo anterior 29 de 38 (76 %) → modelo grande 33 de 38 (87 %). Color: 21 de 30 (70 %) a ojo, con sesgo hacia «negro» (juez único). En datos públicos (308 prendas de Fashionpedia): tipo 76 % frente a 44 % de CLIP; estampado 74 % frente a 66 % de la capa entrenada; forma 48 % frente a 59 %.

**Revisión «OK / más o menos / No» (10 de octubre).** Otra vara de medir: Víctor ve la valoración del modelo en cada recorte y contesta OK, «más o menos» (con las alternativas que también valen) o No (con lo que es). 54 recortes (24 donde a ciegas no coincidían, 30 nuevos, 6 de control con la valoración de otro recorte); quedan 46 reales con respuesta. **Aceptable (OK + «más o menos»): tipo 41 de 46 (89 %, IC 77 a 95 %), estampado 43 de 46 (93 %), tejido 38 de 45 (84 %), forma 45 de 46 (98 %); solo con OK, 87, 93, 73 y 89 %.** Es más generosa que el lote ciego (tipo 53 %, estampado 85 %, tejido 54 %, forma 56 %) porque ve la respuesta y lo dudoso vale; el acierto real queda entre las dos. Los 6 controles no fueron concluyentes (4 marcados «no sirve»; en los otros 2 la valoración equivocada valía para otra prenda del recorte), así que no se sabe cuánto sube el OK por ver la respuesta. El tipo falla casi solo en «Camisa» (4 de 8 aceptadas; las demás etiquetas, 37 de 38). Criterio de Víctor tras verla: con ~70 % basta; lo importante es separar por estilo. Detalle en `TFM_tendencias_de_prenda.md` §6.6.

**Separación por estilo (10 de octubre).** Con las fotos aprobadas de Víctor (geek 91 prendas en 42 fotos, urbano 78 en 39), el geek y el urbano **se separan en forma (p = 0,005), tejido (0,011) y tipo de prenda (0,013)** y no en estampado (0,47) ni en familia (0,14): urbano más oversized (40 % frente a 15 %); geek más corta/cropped (19 % frente a 3 %), ajustada (14 % frente a 1 %), punto (19 % frente a 4 %) y top (15 % frente a 1 %). Con todas las fuentes (261 prendas) el tipo se separa todavía más (p = 0,001). Un acierto del ~70 % encoge las diferencias, no las inventa. Cuello de botella: en el mercado real casi no hay geek (2 fotos en España, ninguna en EEUU). Detalle en §6.7.

**Los siete estilos (12 de octubre).** Con las 404 fotos aprobadas de la Biblioteca (794 prendas etiquetadas por el modelo grande, el 99 al 100 % de cada estilo), cada estilo frente a los demás: **los siete se separan en las cinco dimensiones (familia, tipo, estampado, tejido y forma) con una probabilidad de azar menor del 0,1 %**. Rasgos más marcados: clásico, abrigo y chaqueta (47 % frente a 14 %); old money, americana y liso (84 %); lujo, texto o logo (51 % frente a 4 %) y bolsos; bohemio, estampado «otro», tops y vestidos; convencional, liso (90 %); urbano, oversized (40 % frente a 9 %); geek, gráfico o dibujo (22 % frente a 5 %). Falta medir el acierto del modelo en los cinco estilos nuevos y conseguir fotos de mercado para ellos. Detalle en §6.9. La tarea que lo hace cada lunes en la nube, sin el ordenador de Víctor, y la revista por correo están en §6.8.

### Etapa 8: texto de tendencia con datos medidos (Experimento C)

| Medida | Referencia | Resultado | n | Nota |
|---|---|---|---|---|
| P@5 estricto de `T_datos_en` (texto con plantillas a partir de los datos medidos) | texto corto ciego 37 %; texto largo ciego 30 %; oráculo 70 %; solo imagen 33 % | **83 %** (NDCG@5 0,86) | 6 tendencias × 5 prendas | primaria declarada antes de puntuar: +47 pp, IC95 % [+30, +64], p exacto 0,031, 6 de 6 |
| P@10 | corto ciego 35 %; oráculo 65 % | **68 %** | 6 × 10 | primaria a K = 10: +33 pp [+14, +53] |
| Sensibilidad | las 4 prendas nuevas del top-5 contadas como fallos | 70 %, +33 pp [+22, +44] | 30 prendas | la conclusión no depende de ellas |

Límites: un solo juez (el que eligió las fotos de referencia), 6 tendencias, miniaturas de 60×80 px, lujo sin evaluar. Detalle en `TFM_experimento_C_texto_con_datos.md`.

## 3. Lectura transversal

### 3.1 Qué hizo subir el acierto de verdad

1. **Especificidad, no volumen.** Afinar con las reglas propias del esquema dio +34 puntos de media en catálogo (+24-28 en estilo sobre los LLM generales, que no conocen esas reglas); conocer lo que significa cada estilo dio +33 a +40 puntos de P@5 en el Experimento B (texto informado 70 % frente a ciego 30-37 %); alinear el vocabulario (sudadera = algodón) corrige errores que ningún entrenamiento arregla.
2. **Pasar de un modelo pequeño a uno grande general en tareas de percepción.** En prendas, el modelo grande sube el tipo del 50 al 63 %, el estampado del 50 al 77 % y la forma del 48 al 61 %, donde CLIP, una capa entrenada con 22 000 prendas y un CLIP mayor se quedaban en la referencia. La diferencia se ve en datos públicos (tipo 76 % frente a 44 %) y en los de Víctor.
3. **Curar las fuentes.** La búsqueda automática por texto da un 17 % de fotos útiles; las fuentes elegidas mirando las imágenes, un 76-80 %; un filtro aprendido de las decisiones de Víctor, un 54 % (al conservar el 90 % de las útiles). La fuente pesa más que el modelo.

### 3.2 Lo que no sirvió (y se documentó)

- **Más datos de lo mismo con un modelo pequeño.** La capa sobre CLIP con el 10 % de las 22 000 prendas de Fashionpedia sale igual que con el 100 % (estampado 78,9 → 79,3 %, forma 59,5 → 60,8 % en validación). Un CLIP casi tres veces mayor (L/14) tampoco.
- **Destilar el modelo grande en CLIP.** Con las etiquetas del modelo grande sobre 5 252 prendas el alumno queda en la referencia con las etiquetas de Víctor: reproduce solo el 51-71 % de lo que dice el profesor, y es el alumno el que falla, no el profesor (que acierta 77 % en estampado).
- **Evidencia visual para tendencias ya bien descritas** (Experimento B): la fusión empeora un buen texto (70 → 50 %).
- **Filtros de palabras para las fotos de X:** cada ronda abre una categoría nueva de ruido; el problema no tiene lista finita.
- **`temporada` como atributo:** Kaggle da la estación de la colección, no la de la prenda; el modelo aprende la etiqueta, no la estacionalidad.

### 3.3 Correcciones que se hicieron a lo ya medido

| Lo que se creyó | Lo que salió al medir bien | Por qué cambió |
|---|---|---|
| Estilo 73,4 % frente a CLIP en las 1 207 imágenes | 63,9 % frente a 36,9 % en 371 no vistas | el 36 % de las imágenes se habían visto en entrenamiento |
| Tipo de prenda 85 % (36 recortes) | 50 % con la prenda principal (38 etiquetas de Víctor) | el primer juez era el asistente a ojo, la lista juntaba arriba y abrigo y contaba «cualquiera» de las prendas del recorte |
| «Tipo fiable: 18 de 27» (8 de octubre) | 19 de 38 (50 %) principal; 24 de 38 (63 %) cualquiera | la cifra indulgente y solo del primer lote |
| `grupo_estilo` 90,8 % en test | no dice lo que parece fuera del catálogo | aprende el atajo `articleType → etiqueta` (cae al 3 % con tipos de prenda no vistos) |
| Alumno entrenado con 2 626 prendas: tipo 22 de 38 (58 %) | con las 5 252 prendas, 19-20 de 38 (50-53 %) | más datos no lo mejoraron: la diferencia era ruido de n = 38 |
| Ajuste de instrucciones del modelo grande («profesor_v2», tejido 8 → 9 de 15) | no cuenta como mejora | se hizo mirando las mismas etiquetas; solo la medida del lote ciego vale |
| Tipo de prenda del modelo grande 63 % (prueba con las 40 fotos) | 53 % en el lote ciego, igual que CLIP en esos mismos recortes (53 %) | otra muestra y otro reparto de prendas; los márgenes (±15 a ±17 puntos) cubren los dos valores: no hay evidencia de que mejore a CLIP en el tipo |
| Estampado 77 % frente a 50 % de «siempre liso» | 85 % frente a 78 % en el lote ciego | la referencia cambia con la muestra (la mitad de lisas en la prueba, el 78 % en el lote ciego); el estampado de lo no liso acierta 4 de 6 |

### 3.4 Cuellos de botella

- **Datos, no modelo.** ~23 fotos útiles por temporada en urbano España (referentes por X y prensa por nombre) y 2 en geek España; Instagram y TikTok, donde publican, no se pueden leer. Con ese volumen una cifra por tipo apenas llega a las 5 fotos exigidas.
- **Recortes inservibles.** Al etiquetar el lote ciego, Víctor marcó como inservibles **21 de los 53 recortes contestados (40 %)**: 4 de 4 del «torso geométrico» (red de seguridad del detector, que no se estaba filtrando por un fallo de comparación de texto, corregido el 9 de octubre), 2 de 4 de las detecciones por *grounding* y 14 de 44 (32 %) de las de DeepFashion2. Los informes cuentan prendas que no lo son. Un filtro del modelo grande («¿se ve una prenda con claridad?») descarta con seguridad pero poco: el estricto quita 6 de las 21 inservibles y ninguna de las 72 utilizables (IC 0 a 5 %); el criterio de Víctor es más amplio (caras, torsos sin prenda, fragmentos y detalles ampliados, carteles, comida, revistas, blanco y negro) y el modelo da por buenas 15 de las 21.
- **Definiciones.** Cada etiqueta lleva un criterio: `temporada` (colección frente a estacionalidad), «oversized» (13 % en Fashionpedia, la mitad en el streetwear de Víctor), sudadera (felpa para el modelo, algodón para Víctor), «ajustada» frente a «corta». Una parte del error es de lenguaje, no de visión.
- **Muestras de evaluación pequeñas.** 15 a 38 etiquetas por atributo; un solo etiquetador; las auditorías de cajas, color y estilo de calle las hizo el asistente y siguen sin validar.
- **Dominio.** Catálogo ≠ calle: el clasificador de prenda suelta colapsa sobre la foto entera (`accesorio`, 12 de 19) y solo se arregla detectando antes.

### 3.5 Coste

| Pieza | Coste |
|---|---|
| Florence-2 + LoRA (por versión) | ~21 min de T4 en Kaggle (hasta 58 min por la cola); adapter de 7,7 MB; 6,5 s por imagen en CPU |
| Detector de prendas + Florence sobre una foto (CPU) | ~20 s por foto; 82 fotos ≈ 30 min |
| Embeddings CLIP en CPU | B/32 13 prendas por segundo; L/14 1 por segundo (suena el ventilador) |
| Modelo grande (Qwen3-VL-8B, 2 × T4 en Kaggle) | carga 100-146 s; 0,9 s por prenda y pregunta con el recorte, 1,5 s con la foto; **2,5 s por prenda** en el paso semanal (unos 25 minutos por 600 prendas) |
| Etiquetado por el modelo grande de 5 252 prendas | 2 tareas en paralelo, 103 y 105 minutos |
| Esfuerzo humano de Víctor | 120 fichas (revisión humana), 309 juicios del Experimento B, 135 fotos por chat, 61 prendas en la página de etiquetado (2 lotes) |

## 4. Fiabilidad actual por atributo (lo que usa el informe de «Prendas»)

| Atributo | Método | A ciegas (principal, lote ciego) | Revisión (aceptable) | Referencia a ciegas | Confianza máxima en el informe |
|---|---|---|---|---|---|
| Tipo de prenda | modelo grande | 17 de 32 (53 %) | 41 de 46 (89 %) | CLIP 17 de 32; «siempre Chaqueta» 8 de 32 | media (antes baja) |
| Familia de prenda | modelo grande | 27 de 32 (84 %) | | CLIP 28 de 32 (88 %) | media |
| Estampado | modelo grande | 23 de 27 (85 %) | 43 de 46 (93 %) | «siempre liso» 21 de 27 (78 %) | media |
| Forma | modelo grande | 15 de 27 (56 %) | 45 de 46 (98 %) | «siempre regular» 13 de 27 (48 %) | media (antes baja) |
| Tejido | modelo grande | 14 de 26 (54 %) | 38 de 45 (84 %) | «siempre algodón» 7 de 26 (27 %) | media (antes baja) |
| Color | adaptador Florence-2 v3 | 21 de 30 (70 %, a ojo) | | | baja |

La confianza de cada cifra del informe es el mínimo entre las fotos que la sostienen (≥ 30 alta, 15 a 29 media, 5 a 14 baja) y el techo que fija el acierto del atributo. El techo sale del mejor de dos criterios: a ciegas (≥ 85 % con 30 o más etiquetas alta, ≥ 65 % media, menos baja) y la revisión (límite inferior del intervalo de «aceptable» ≥ 65 % → media; «alta» solo se alcanza a ciegas, porque la revisión ve la respuesta del modelo). Desde el 10 de octubre se aplica la revisión; los tipos con 6 o más revisados y menos del 65 % aceptado («Camisa», 4 de 8) salen con confianza baja y un aviso.

**Desde el 16 de octubre (método `semanal_pista`, §6.11 de `TFM_tendencias_de_prenda.md`).** La tabla de arriba es del método anterior. Con el nuevo, sobre el mismo lote ciego: tipo 20 de 32 (62 %), familia 32 de 32, estampado 25 de 27 (93 %), tejido 15 de 26 (58 %), forma 14 de 27 (52 %). Revisión de Víctor en dos rondas (74 recortes reales, aceptable; los 28 de la ronda 2 son de los cinco estilos nuevos): tipo 91 %, estampado 96 %, tejido 86 %, forma 99 %; los 6 controles de la ronda 2 se rechazaron todos. Techo de confianza en el informe: sin cambios (media en los cuatro).

## 5. Qué falta medir

0. **Fotos geek del mercado** (2 en España, ninguna en EEUU): hoy solo se puede separar por estilo con las fotos aprobadas de Víctor. Es lo que más limita.
0b. **Cuánto sube el OK por ver la respuesta**: los 6 controles no lo midieron; haría falta repetirlo con controles más limpios (valoración de otro recorte de una sola prenda).
1. **Un segundo lote ciego**, solo si se ajustan las instrucciones: el primero (9 de octubre) ya no es ciego para cualquier cambio hecho viendo sus fallos («oversized» dicho «regular» 5 de 9 veces, «ajustada» dicha «corta», tejido «no se distingue» dicho «algodón»). Con las instrucciones v3 congeladas, esas son las cifras del paso semanal.
1b. **Filtrar mejor los recortes inservibles** (40 % de los contestados). Probado un filtro del modelo grande sobre 93 recortes: seguro (0 de 72 utilizables perdidos) pero flojo (6 de 21 inservibles). Falta probar la fracción visible («más de la mitad», la regla de Víctor) y un filtro por foto, con un lote nuevo.
2. **Más de una persona etiquetando** y más de 100 etiquetas por atributo si se quiere distinguir diferencias de 10 puntos.
3. **Validar las auditorías** de cajas, color y estilo de calle hechas por el asistente.
4. **Más volumen de fotos** para que una cifra por tipo y atributo llegue a 5 fotos: YouTube, comunidades de Reddit, fotos libres de Wikimedia Commons para la temporada pasada.
5. **Varias semillas** en los entrenamientos de Florence-2 (una sola por versión).

## 6. Resumen en cinco frases

El proyecto pasó de un CLIP que acertaba el 33 % del estilo de una prenda a un clasificador propio que acierta el 64 % sin haberla visto y el 85 % de media de cinco campos sobre catálogo. En la calle y con redes sociales el catálogo no sirve tal cual: hizo falta detectar y recortar, y las fotos útiles no salen de una búsqueda por texto (17 %) sino de elegir las fuentes. Entrenar más con modelos pequeños nunca mejoró lo que ya daba la referencia; lo que mejoró fue la especificidad (reglas y vocabulario propios) y, para estampado y tipo de prenda, un modelo general grande (estampado 50 → 77 %, tipo 50 → 63 %). Varias cifras iniciales eran demasiado buenas (contaminación, juez a ojo, «cualquiera») y se corrigieron al medir con referencias humanas; con 15 a 38 etiquetas el margen es de 8 a 13 puntos. Medido a ciegas con 32 recortes de producción, el modelo grande iguala a CLIP en el tipo (53 %) y solo se distingue de su referencia en el tejido (54 % frente a 27 %); además, el 40 % de los recortes que se revisaron eran inservibles. Lo que limita hoy el análisis de tendencia es el volumen de fotos (decenas por temporada), la calidad de los recortes y las definiciones de las etiquetas, más que el modelo. Cuando Víctor revisó lo que había valorado el modelo (OK, «más o menos» o No) dio por buena su valoración en el 84 a 98 % de los atributos y fijó el criterio del proyecto: con un 70 % basta, lo importante es separar por estilo; con sus fotos, la forma, el tejido y el tipo de prenda sí distinguen el geek del urbano, aunque en el mercado real casi no hay geek para comparar.

## 7. Fuentes

`memoria/TFM_clasificador_visual_atributos.md` (§0, §3, §6, §7, §8, §11, §13) · `memoria/TFM_experimento_B_vectores_visuales.md` · `memoria/TFM_ingesta_redes_sociales.md` · `memoria/TFM_tendencias_de_prenda.md` (§3, §6.1 a §6.7) · `experimentos/analisis_mercado/README.md` · `experimentos/vlm_atributos_prenda/resultados/` (`profesor_fashionpedia_2026-10-08/`, `profesor_victor_2026-10-09/`, `alumno_2026-10-08.json`, `fashionpedia_atributos_*.json`) · `experimentos/analisis_mercado/tendencia_datos/fiabilidad.json` · `valoraciones.json` y `valoraciones_resumen.json` (revisión) · `separacion_estilos.json`.
