# Experimento C — ¿un texto de tendencia hecho con datos medidos supera al de un LLM que solo conoce el nombre?

**Estado:** diseño **fijado el 16 de octubre de 2026, antes de puntuar nada y antes de recuperar ninguna prenda con estos textos** (el commit que contiene este fichero es anterior a cualquier puntuación).
**Código:** este directorio + `../../analisis_mercado/texto_tendencia.py` (el generador, que también servirá para el Trend JSON de producción) y `../experimento_b/` (inventario, CLIP, puntuaciones y estadística, que se reutilizan tal cual).

## 1. Pregunta

En el Experimento B (3 de octubre) el factor que decidió el acierto del emparejamiento prenda ↔ tendencia fue **el texto**, no la imagen: un texto largo escrito por un LLM que solo conocía el *nombre* de la tendencia (el brazo realista del pipeline de `Estado_arte.md` §6) dio P@5 de 23 a 34 %; un texto corto escrito por una persona que conocía la taxonomía (el oráculo), 51 %; añadir fotos de evidencia no ayudó. El análisis semanal de este proyecto mide, para cada estilo, qué prendas, formas, estampados y tejidos lo caracterizan. **¿Un texto corto escrito con plantillas a partir de esas medidas, sin LLM, recupera mejor las prendas de cada tendencia que el texto corto de un LLM que solo conoce el nombre?**

- **H1 (primaria):** `T_datos_en` supera a `T_corto_ciego_en` en P@5.
- **H2 (secundaria):** `T_datos_en` se acerca al oráculo `T_oraculo_en` (cota optimista, escrita conociendo la taxonomía).
- Secundarias: contra `T_ciego_en` (texto largo ciego, el del pipeline actual) y contra `V` (solo imagen).

## 2. Brazos

Los de la v2 del Experimento B (ya puntuados): `T_ciego_en`, `T_ciego_es`, `T_oraculo_en` (corregido en la v2), `T_corto_ciego_en`, `V`, `F_ciego`, `F_oraculo`, `F_corto`. **Nuevo: `T_datos_en`** = el texto en inglés de `textos_datos_c.json` (`descripcion_clip`), generado por la receta R1 de `texto_tendencia.py` a partir de `separacion_estilos.json` (bloque «solo_biblioteca»): la muestra de referencia que aprobó Víctor (404 fotos, siete estilos) analizada por el pipeline (detector DeepFashion2 + Qwen3-VL-8B con la configuración `semanal_pista`).

**Receta R1** (ver el docstring de `texto_tendencia.py`): prendas = lo que *distingue* al estilo (cuota ≥ 5 % y ≥ +3 puntos sobre el resto; mínimo 3, completadas con las más frecuentes; máximo 5); modificadores = valores de forma, estampado y tejido con q < 0,10 y ≥ +8 puntos (≥ +15 para «liso»), como mucho 3, sin valores por defecto; plantilla `{nombre} style outfit, {modificadores}: {prendas}`. El nombre del estilo es el mismo dato que ven los textos ciegos; lo único nuevo es la evidencia medida.
**Textos congelados:** `textos_datos_c.json` (SHA-256 del fichero en el commit; no se regeneran).

| Tendencia | `T_datos_en` |
|---|---|
| urbano | urban style outfit, oversized baggy: sweatshirt, shorts, jacket, hoodie, t-shirt |
| alternativo-geek | alternative geek style outfit, graphic print, knit, technical: skirt, hoodie, crop top, sneakers, long-sleeve t-shirt |
| clásico-tradicional | classic traditional style outfit: jacket, sleeveless vest, trousers |
| old money | old money style outfit, plain solid-color, slim-fit, linen: blazer, trousers, dress shoes, button-up shirt |
| lujo ostentoso | ostentatious luxury style outfit, logo print, leather, graphic print: handbag, t-shirt, jacket |
| bohemio | bohemian style outfit, patterned, oversized baggy, cropped: skirt, dress, tank top, sandals, boots |
| convencional | conventional style outfit, plain solid-color: dress, sneakers, high heels, t-shirt, button-up shirt |

**Tendencias que se evalúan: 6** (todas menos lujo ostentoso, como en la v2 de B: el inventario gratuito no contiene prendas de lujo, techo ≈ 0 con juicio humano). El texto de lujo se genera igualmente (Víctor pidió los siete); se evaluará cuando exista un inventario con prendas de ese tipo.

## 3. Procedimiento

1. `experimento_c.py preparar`: codifica `T_datos_en` con el mismo CLIP que B (ViT-B/32 OpenAI), recupera el top-10 del inventario de la v2 (1 267 prendas de 60×80 px) por tendencia y construye el *pool* de prendas **nuevas** (las que aún no tienen puntuación en `ratings_b.json`, que se reutiliza).
2. Puntuación humana **a ciegas** (0 / 1 / 2: no encaja / dudoso / encaja) de Víctor en una página de toques: ve el nombre y los rasgos de la taxonomía (`RASGOS` de B), **nunca** los textos ni qué método propuso cada prenda; orden barajado y tramo 1 (prendas que algún método pone en su top-5) antes que el tramo 2 (puestos 6 a 10).
3. `experimento_c.py analizar`: la estadística de B (`analizar_generico`).

## 4. Métricas y regla de decisión (como en B)

P@5 estricto (relevante = 2) primaria; P@5 laxo (≥ 1), NDCG@5 y lo mismo @10 secundarias. Diferencias emparejadas por tendencia: IC95 % t (5 gl con 6 tendencias) y p exacto por permutación de signos, victorias / empates / derrotas. **MEJORA** solo si la diferencia media es ≥ +5 pp **y** el IC95 % excluye 0; en otro caso, **neutro** (no concluyente). Comparación primaria: **`T_datos_en − T_corto_ciego_en`**. Las demás son secundarias y exploratorias.

## 5. Grados de libertad que se declaran

- La receta R1 se escribió y se ajustó **mirando los textos que producía y las cifras de la muestra de referencia, pero sin haber recuperado ninguna prenda con ellos**. La primera versión ordenaba las prendas por frecuencia (salía «trousers» en casi todos los estilos, sin distinguirlos); se cambió a ordenar por lo que distingue al estilo porque quien puntúa juzga si la prenda encaja con *ese* estilo. Es una decisión de diseño razonada, no ajustada a resultados, y queda fijada aquí.
- Las medidas de la muestra de referencia salen de un clasificador con errores conocidos (a ciegas: tipo 62 %, estampado 93 %, tejido 58 %, forma 52 %; en la revisión de Víctor, 86 a 99 % aceptable). El texto hereda esos errores: es parte de lo que se evalúa.
- Quien puntúa es la misma persona que eligió las fotos de referencia de las que salen los textos (un solo juez, sin independencia total).

## 6. Límites

(1) Con 6 tendencias solo se detectan diferencias grandes (semianchura típica del IC ≈ ±20 pp): «neutro» no es «no hay efecto». (2) Inventario de e-commerce con miniaturas de 60×80 px (casi todo básico; sin lujo, pocas prendas «geek» y «bohemias» de verdad). (3) Un solo juez. (4) Texto en inglés para CLIP-OpenAI; el español es solo para la aprobación humana. (5) El brazo ciego es un límite inferior del agente real (que vería contenido) y el oráculo un límite superior optimista.

## 7. Brazo opcional con modelo abierto (no forma parte del análisis registrado)

Un modelo abierto (Qwen, en Kaggle, nunca una API comercial) reformula los mismos hechos en una frase más natural, con la orden de no añadir prendas ni atributos que no estén en la evidencia. Se congelará aparte (modelo, instrucciones, temperatura 0, fecha) **antes** de puntuar sus prendas y se analizará como exploratorio (`T_datos_abierto_en − T_datos_en`).

## 8. Ficheros

`textos_datos_c.json` (textos y evidencia, congelados) · `experimento_c.py` (preparar / analizar) · `pool_c.json` y `pool_c_clave.json` (prendas por puntuar y qué rango da cada método; se generan) · las puntuaciones se añaden a `../experimento_b/ratings_b.json`.

## 9. Resultado (16 de octubre de 2026; añadido DESPUÉS de puntuar, lo anterior no se ha tocado)

Víctor puntuó a ciegas las 15 prendas nuevas (14 «encaja», 1 «no encaja»); el resto de puntuaciones son las del B. Salida completa del análisis en `resultados_c.txt`.

| Brazo | P@5 estricto | NDCG@5 | P@10 | NDCG@10 |
|---|---|---|---|---|
| **`T_datos_en`** | **83 %** | **0,86** | **68 %** | **0,74** |
| `T_oraculo_en` (escrito conociendo la taxonomía) | 70 % | 0,66 | 65 % | 0,64 |
| `F_oraculo` | 50 % | 0,50 | 53 % | 0,52 |
| `T_corto_ciego_en` | 37 % | 0,39 | 35 % | 0,38 |
| `T_ciego_es` | 37 % | 0,34 | 38 % | 0,36 |
| `V` (solo imagen) | 33 % | 0,36 | 42 % | 0,41 |
| `T_ciego_en` (texto largo, el del pipeline actual) | 30 % | 0,31 | 37 % | 0,35 |

**Comparación primaria declarada (`T_datos_en − T_corto_ciego_en`, P@5):** +47 pp, IC95 % [+30, +64], p exacto 0,031, gana en 6 de 6 tendencias → **MEJORA** según la regla fijada (≥ +5 pp e IC sin el 0). A K = 10: +33 pp [+14, +53], p = 0,062, 5/1/0 → MEJORA.
**Secundarias (exploratorias):** frente al oráculo +13 pp [+2, +24] a K = 5 (4/2/0) y +3 pp [−25, +32] a K = 10 (neutro): al nivel del oráculo, no claramente por encima. Frente al texto largo ciego +53 pp [+17, +90] (K = 5) y +32 pp [−8, +71] (K = 10, neutro). Frente a solo imagen +50 pp [+28, +72] (K = 5) y +27 pp [−1, +55] (K = 10, neutro).

Aciertos de 5 por tendencia en el top-5 (`T_datos_en` / oráculo / corto ciego / largo ciego / solo imagen): old money 3/2/1/1/2 · clásico 4/3/1/0/0 · urbano 5/5/4/3/3 · bohemio 5/4/3/5/2 · geek 3/3/0/0/0 · convencional 5/4/2/0/3. `T_datos_en` nunca pierde frente al corto ciego.

**Sensibilidad.** 26 de las 30 prendas del top-5 de `T_datos_en` ya tenían puntuación del B, dada sin saber nada de este método; solo 4 son nuevas. Contando esas 4 como fallos (el peor caso), `T_datos_en` queda en P@5 = 70 % y la diferencia primaria en +33 pp [+22, +44], p = 0,031: la conclusión no depende de ellas.

**Lectura y límites que hay que declarar.** (1) La misma persona eligió las fotos de referencia de las que salen los textos y puntúa si las prendas encajan: el resultado dice que el análisis recoge *su* criterio de cada estilo, no una verdad externa; haría falta un segundo juez o repetir la puntuación pasado un tiempo. (2) Seis tendencias: solo se detectan diferencias grandes (semianchura típica del IC ≈ ±22 pp en K = 5); el p exacto mínimo con seis victorias es 0,031. (3) El oráculo de esta tabla (70 %) no es el de la v1 de B (51 %): son seis tendencias en vez de siete (sin lujo, que dio techo ≈ 0) y el oráculo de geek se corrigió en la v2. (4) De las 15 prendas nuevas, 14 fueron «encaja» (en B, «encaja» fue el 36 % de lo puntuado): es lo esperable si el brazo recupera bien, pero no se descarta algo de indulgencia dos semanas después. (5) Inventario de miniaturas de 60×80 px de un catálogo de e-commerce; lujo ostentoso sin evaluar. (6) Un solo análisis primario; el resto son exploratorios y no se corrigen por comparaciones múltiples.

## 10. Repetición de la puntuación por la misma persona (test–retest) — diseño fijado el 24 de octubre de 2026, ANTES de puntuarla

**Motivo.** El principal límite del resultado de §9 es que Víctor eligió las fotos de referencia de las que salen los textos y también puntúa si las prendas encajan. No hay un segundo juez a mano; Víctor propuso puntuar él mismo otra vez. Eso no resuelve la falta de independencia, pero sí responde a una pregunta distinta y necesaria: **¿cuánto se mantiene el resultado con otra puntuación de la misma persona, ocho días a tres semanas después y sin ver la primera?**

**Qué se repite.** Las 67 prendas distintas que están en el top-5 de `T_datos_en`, `T_corto_ciego_en` o `T_oraculo_en` (30 de cada uno, con solapes): con ellas se recalcula por completo el P@5 de la comparación primaria y la del oráculo. Orden barajado con semilla 24 (distinta del de B y C); la página no enseña la puntuación anterior, ni los textos, ni el método que propuso cada prenda (`pool_c2.json`, `puntuar_c.py html --pool pool_c2.json --ids pool_c2_ids.json`). Las nuevas puntuaciones van a `ratings_c_retest.json`; **`ratings_b.json` no se toca**.

**Qué se calcula** (`experimento_c.py retest-analizar`): (1) acuerdo con la primera puntuación (% y kappa de Cohen, con tres categorías y con «encaja / no encaja»); (2) la comparación primaria `T_datos_en − T_corto_ciego_en` en P@5 estricto con **la segunda puntuación sola**, con la **conservadora** (encaja solo si lo fue las dos veces) y con la **indulgente** (encaja si lo fue alguna), y lo mismo frente al oráculo.
**Regla fijada antes de puntuar:** la conclusión de §9 se considera **robusta** si la comparación primaria con la segunda puntuación sola sigue siendo MEJORA (≥ +5 pp e IC95 % t sin el 0). Si no lo es, se informa tal cual y se matiza la conclusión; no se elige la variante que mejor salga. Un kappa bajo se informa como límite de la medida, no se corrige.

**Lo que NO responde:** la dependencia del criterio de una sola persona (hace falta otra persona) ni la de las seis tendencias.

