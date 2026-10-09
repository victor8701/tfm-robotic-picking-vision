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

**Qué es distinguible.** El estampado del modelo grande (17 de 22, IC 57 a 90 %) deja fuera el 50 % de «siempre liso». El tipo (24 de 38, IC 47 a 77 %) incluye el 50 % del flujo anterior: la mejora de 50 a 63 % es una indicación, no una certeza. Forma (IC 41 a 78 %) y tejido (IC 36 a 80 %) incluyen su referencia.

Familia de prenda (arriba, abrigo, abajo, cuerpo entero, calzado, accesorio): flujo anterior 29 de 38 (76 %) → modelo grande 33 de 38 (87 %). Color: 21 de 30 (70 %) a ojo, con sesgo hacia «negro» (juez único). En datos públicos (308 prendas de Fashionpedia): tipo 76 % frente a 44 % de CLIP; estampado 74 % frente a 66 % de la capa entrenada; forma 48 % frente a 59 %.

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

### 3.4 Cuellos de botella

- **Datos, no modelo.** ~23 fotos útiles por temporada en urbano España (referentes por X y prensa por nombre) y 2 en geek España; Instagram y TikTok, donde publican, no se pueden leer. Con ese volumen una cifra por tipo apenas llega a las 5 fotos exigidas.
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

| Atributo | Método | Acierto (principal) | Referencia | Confianza máxima en el informe |
|---|---|---|---|---|
| Tipo de prenda | modelo grande | 24 de 38 (63 %) | 9 de 38 (24 %); método anterior 50 % | baja |
| Familia de prenda | modelo grande | 33 de 38 (87 %) | método anterior 76 % | alta (con 30 fotos o más) |
| Estampado | modelo grande | 16 de 22 (73 %) en el paso semanal | 11 de 22 (50 %) | media |
| Forma | modelo grande | 13 de 23 (57 %) | 11 de 23 (48 %) | baja |
| Tejido | modelo grande | 8 de 15 (53 %) | 10 de 15 (67 %) | baja |
| Color | adaptador Florence-2 v3 | 21 de 30 (70 %, a ojo) | — | baja |

La confianza de cada cifra del informe es el mínimo entre las fotos que la sostienen (≥ 30 alta, 15 a 29 media, 5 a 14 baja) y el techo que fija el acierto del atributo (≥ 85 % con 30 o más etiquetas alta, ≥ 65 % media, menos baja). Las cifras de esta tabla se sustituyen por las del **lote ciego** cuando exista (§5).

## 5. Qué falta medir

1. **Lote ciego** de 30 a 60 recortes nuevos que Víctor etiquete después de que el modelo grande los haya etiquetado, con las instrucciones congeladas (v3) y sin sugerencias del modelo en la página. Es la única medida limpia de lo que corre cada semana: las 40 fotos de la prueba se usaron para ajustar las instrucciones (sudadera = algodón, logos pequeños = liso).
2. **Más de una persona etiquetando** y más de 100 etiquetas por atributo si se quiere distinguir diferencias de 10 puntos.
3. **Validar las auditorías** de cajas, color y estilo de calle hechas por el asistente.
4. **Más volumen de fotos** para que una cifra por tipo y atributo llegue a 5 fotos: YouTube, comunidades de Reddit, fotos libres de Wikimedia Commons para la temporada pasada.
5. **Varias semillas** en los entrenamientos de Florence-2 (una sola por versión).

## 6. Resumen en cinco frases

El proyecto pasó de un CLIP que acertaba el 33 % del estilo de una prenda a un clasificador propio que acierta el 64 % sin haberla visto y el 85 % de media de cinco campos sobre catálogo. En la calle y con redes sociales el catálogo no sirve tal cual: hizo falta detectar y recortar, y las fotos útiles no salen de una búsqueda por texto (17 %) sino de elegir las fuentes. Entrenar más con modelos pequeños nunca mejoró lo que ya daba la referencia; lo que mejoró fue la especificidad (reglas y vocabulario propios) y, para estampado y tipo de prenda, un modelo general grande (estampado 50 → 77 %, tipo 50 → 63 %). Varias cifras iniciales eran demasiado buenas (contaminación, juez a ojo, «cualquiera») y se corrigieron al medir con referencias humanas; con 15 a 38 etiquetas el margen es de 8 a 13 puntos. Lo que limita hoy el análisis de tendencia es el volumen de fotos (decenas por temporada) y las definiciones de las etiquetas, no el modelo.

## 7. Fuentes

`memoria/TFM_clasificador_visual_atributos.md` (§0, §3, §6, §7, §8, §11, §13) · `memoria/TFM_experimento_B_vectores_visuales.md` · `memoria/TFM_ingesta_redes_sociales.md` · `memoria/TFM_tendencias_de_prenda.md` (§3, §6.1 a §6.4) · `experimentos/analisis_mercado/README.md` · `experimentos/vlm_atributos_prenda/resultados/` (`profesor_fashionpedia_2026-10-08/`, `profesor_victor_2026-10-09/`, `alumno_2026-10-08.json`, `fashionpedia_atributos_*.json`) · `experimentos/analisis_mercado/tendencia_datos/fiabilidad.json`.
