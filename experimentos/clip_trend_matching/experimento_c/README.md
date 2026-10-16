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
