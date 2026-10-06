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
