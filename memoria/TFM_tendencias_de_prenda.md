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

## 3. Primeras pruebas (pequeñas; sirven para decidir, no para concluir)

**a) Volumen.** En el último informe de España (45 días, 116 fotos) urbano pesa un 6 % y geek un 0 %. De los referentes con X activo solo @byCaLiTosYT publica con regularidad (12 fotos descargadas, 4 pasaron los filtros);
@shodamonkas 1 foto en 14 días; @orslok lleva unos 600 días sin publicar. Con estas fuentes una celda de cuatro atributos queda casi siempre vacía: hace falta más volumen o agregar a un nivel más general.

**b) Detector de prendas en 28 fotos de la Biblioteca (14 geek + 14 urbano, al azar).** Las 28 tienen persona; 3,0 prendas por foto en geek y 2,4 en urbano; a ojo falla en 6 de 28 (capturas, primeros planos de cara, una infografía, una persona diminuta).
El detector solo tiene 13 clases: casi todo lo de arriba sale «camisa de manga larga» (8 de 11 en geek, 8 de 10 en urbano), sudaderas incluidas. La categoría de Florence sobre el recorte coincide con la del detector en el 64 % (geek) y el 56 % (urbano) de las prendas:
se entrenó con fotos de catálogo y degrada en foto de calle. El color domina en negro (62 % geek, 41 % urbano). Forma y estampado no existen en el modelo (se descartaron en v1).
Observación sobre la muestra geek (a ojo): de 14 fotos, 6 alternativo/e-girl, 3 techwear, 2 kawaii/Harajuku, 1 fandom explícito y 2 sin clasificar; no coincide con la definición «fandom y cultura pop».

**c) CLIP ViT-B/32 zero-shot sobre el recorte de cada prenda** (`vlm_atributos_prenda/herramientas/prueba_recortes_clip.py`; 66 recortes, 36 revisados a ojo por mí, no por Víctor; resultados por recorte en `vlm_atributos_prenda/resultados/prueba_recortes_clip_2026-10-06.json`):

| Atributo | Acierto | Referencia | Comentario |
|---|---|---|---|
| Tipo fino (lista del ERP, dentro de la categoría detectada) | 26 de 35 (74 %) | — | abajo 12/13, calzado 3/4, arriba 9/15: confunde sudadera, chaqueta y camisa |
| Estampado (10 opciones) | 10 de 31 (32 %) | siempre «liso» = 65 % | acierta tartán (4/4) y gráficos grandes (2/2); dice «liso» en 1 de 20 prendas lisas; con un sesgo hacia «liso» sube a 77 % en validación cruzada pero pierde logos y camuflaje |
| Forma (4 opciones) | 13 de 18 (72 %) | siempre «oversized» = 72 % | no aporta; no aplica a faldas, vestidos, shorts ni calzado |

Límites: n pequeño, juez único (yo, a ojo), prompts en inglés sin afinar, sin intervalo de confianza; el 77 % del estampado sesgado se eligió con una validación cruzada de un parámetro sobre las mismas 31 prendas.

## 4. Lectura y siguiente paso

- El **tipo de prenda** es alcanzable con modelos abiertos; el **estampado y la forma** no salen de CLIP zero-shot con estos prompts. Habrá que entrenar con correcciones de Víctor (hojas de recortes numeradas desde el móvil) una capa pequeña sobre CLIP, o probar un CLIP/SigLIP mayor (pesos abiertos) con los mismos 36 recortes.
- Con el estilo dado por la persona, el clasificador de estilo (acierto real 2 de 10 en prensa, 8 de 18 fotos sin look) deja de ser el cuello de botella; queda para fotos sin referente.
- Pendiente de Víctor (preguntas del Artifact): si el streetwear entra en urbano (leí su «sin street wear» como U01–U09 urbano y U10–U11 descartadas), si geek incluye lo alternativo/techwear, calzado y accesorios, prendas cortadas, ventana (30 vs 90 días), mínimo de fotos por celda, mercado y más referentes.
