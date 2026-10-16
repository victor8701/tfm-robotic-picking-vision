# Experimento C — un texto de tendencia hecho con datos medidos frente al de un LLM que solo conoce el nombre

**Autor:** Víctor Martín Parra, con el asistente · **Fecha:** 16 de octubre de 2026 · **Estado:** cerrado (primera vuelta)
**Código y datos:** `experimentos/clip_trend_matching/experimento_c/` (su README tiene el diseño fijado antes de puntuar y el resultado) y `experimentos/analisis_mercado/texto_tendencia.py` (el generador). Reutiliza el Experimento B (`TFM_experimento_B_vectores_visuales.md`).
**Relacionados:** `Estado_arte.md` §6–7 y §11 (solo lectura), `TFM_tendencias_de_prenda.md` §6.9 y §6.11.

## Resumen

En el Experimento B el emparejamiento prenda ↔ tendencia dependía del **texto** (un texto largo escrito por un LLM que solo conocía el nombre de la tendencia: P@5 de 23 a 34 %; un texto corto informado: 51 %) y la evidencia visual no aportaba. Aquí el texto se escribe con **plantillas, sin LLM**, a partir de lo que mide el análisis de prendas sobre la muestra de referencia de cada estilo (qué prendas, formas, estampados y tejidos lo distinguen de los demás). Con puntuación humana a ciegas y la regla de decisión fijada de antemano, ese texto recupera prendas que Víctor juzga acordes con la tendencia en el **83 %** de los cinco primeros puestos (P@5), frente al **37 %** del texto corto de un LLM que solo conoce el nombre (+47 pp, IC95 % [+30, +64], p exacto 0,031, gana en 6 de 6 tendencias) y al **70 %** de un texto escrito a mano conociendo la taxonomía (+13 pp, [+2, +24]; a K = 10, +3 pp, neutro).

## 1. Pregunta e hipótesis

¿Un texto corto escrito con plantillas a partir de las medidas del análisis recupera mejor las prendas de cada tendencia que el texto corto de un LLM que solo conoce el nombre? **H1 (primaria):** `T_datos_en` supera a `T_corto_ciego_en` en P@5. Secundarias: acercarse al oráculo, superar al texto largo ciego (el del pipeline actual) y a solo imagen.

## 2. Diseño (fijado el 16 de octubre, antes de puntuar; commit 8f99ff7)

- **Receta R1** (`texto_tendencia.py`, congelada): prendas = lo que distingue al estilo (cuota ≥ 5 % y ≥ +3 puntos sobre los demás estilos; mínimo 3 y máximo 5, completando con las más frecuentes si el estilo no tiene rasgo propio); modificadores = valores de forma, estampado y tejido con q < 0,10 y ≥ +8 puntos (≥ +15 para «liso»), como mucho 3, sin valores por defecto; plantilla `{nombre} style outfit, {modificadores}: {prendas}`. Evidencia: la muestra de referencia de Víctor (404 fotos, siete estilos) analizada por el pipeline (§6.11).
- **Brazos:** los de la v2 del B más `T_datos_en`. **Tendencias evaluadas:** 6 (todas menos lujo ostentoso: el inventario gratuito no tiene prendas de lujo; su texto se genera igualmente).
- **Inventario y método:** el del B (1 267 miniaturas de 60×80 px, CLIP ViT-B/32 OpenAI, misma evidencia visual con la misma semilla). Puntuación a ciegas (0/1/2) de Víctor solo para las prendas nuevas del top-10 (15 de 264; las otras 249 ya estaban puntuadas en B).
- **Decisión:** MEJORA si la diferencia media en P@5 estricto es ≥ +5 pp y el IC95 % (t, 5 gl) excluye 0; si no, neutro. Primaria: `T_datos_en − T_corto_ciego_en`.
- **Grado de libertad declarado:** la primera versión de la receta ordenaba las prendas por frecuencia («trousers» salía en casi todos los estilos); se cambió a ordenarlas por lo que distingue al estilo antes de recuperar ninguna prenda.

## 3. Resultados

| Brazo | P@5 estricto | NDCG@5 | P@10 | NDCG@10 |
|---|---|---|---|---|
| **`T_datos_en`** | **83 %** | **0,86** | **68 %** | **0,74** |
| `T_oraculo_en` | 70 % | 0,66 | 65 % | 0,64 |
| `F_oraculo` | 50 % | 0,50 | 53 % | 0,52 |
| `T_corto_ciego_en` | 37 % | 0,39 | 35 % | 0,38 |
| `T_ciego_es` | 37 % | 0,34 | 38 % | 0,36 |
| `V` (solo imagen) | 33 % | 0,36 | 42 % | 0,41 |
| `T_ciego_en` (texto largo ciego) | 30 % | 0,31 | 37 % | 0,35 |

Comparaciones emparejadas por tendencia (P@5 / P@10, diferencia en pp, IC95 %, victorias-empates-derrotas):
- **Primaria** `T_datos_en − T_corto_ciego_en`: **+47 [+30, +64]**, p = 0,031, 6-0-0 / +33 [+14, +53], p = 0,062, 5-1-0 → **MEJORA**.
- `T_datos_en − T_oraculo_en`: +13 [+2, +24], 4-2-0 / +3 [−25, +32], 3-1-2 (neutro).
- `T_datos_en − T_ciego_en`: +53 [+17, +90], 5-1-0 / +32 [−8, +71] (neutro).
- `T_datos_en − V`: +50 [+28, +72], 6-0-0 / +27 [−1, +55] (neutro).

Aciertos de 5 por tendencia (datos / oráculo / corto ciego / largo ciego / solo imagen): old money 3/2/1/1/2 · clásico 4/3/1/0/0 · urbano 5/5/4/3/3 · bohemio 5/4/3/5/2 · geek 3/3/0/0/0 · convencional 5/4/2/0/3.
**Sensibilidad:** 26 de las 30 prendas del top-5 de `T_datos_en` ya estaban puntuadas en B (sin saber de este método); contando las 4 nuevas como fallos, P@5 = 70 % y la diferencia primaria +33 pp [+22, +44] (p = 0,031).

## 4. Lectura

1. Con un inventario y un juez fijos, **lo que se mide del estilo aporta más al texto que lo que un LLM sabe del nombre**: el brazo de datos nunca pierde frente al corto ciego, y se queda al nivel de un texto escrito a mano conociendo la taxonomía (el oráculo del B).
2. Es coherente con B: la evidencia sigue sin entrar por la imagen (`V`, fusiones) sino por el texto. La contribución del análisis de prendas es **dar a ese texto contenido específico y verificable** (cada palabra tiene una cifra detrás), sin API comercial.
3. Para el sistema: el Trend JSON puede generar `descripcion_clip` con esta receta a partir de los datos de cada estilo y mercado, y dejar la descripción en español para que la apruebe el operario (`Estado_arte.md` §6.5).

## 5. Límites

(1) **Mismo juez:** Víctor eligió las fotos de referencia de las que salen los textos y puntúa si las prendas encajan; el resultado dice que el análisis recoge *su* criterio de cada estilo, no una verdad externa. Falta un segundo juez o repetir la puntuación pasado un tiempo. (2) **Seis tendencias:** solo se detectan diferencias grandes (semianchura típica del IC ≈ ±22 pp en K = 5); el p exacto mínimo con seis victorias es 0,031; las comparaciones secundarias son exploratorias y sin corregir por comparaciones múltiples. (3) **Inventario:** miniaturas de 60×80 px de un catálogo de e-commerce, casi todo básico; lujo ostentoso sin evaluar; el catálogo real de SKUs puede cambiar el resultado. (4) **El oráculo de esta tabla (70 %) no es el de la v1 de B (51 %):** son seis tendencias en lugar de siete y se corrigió el oráculo de geek. (5) **Indulgencia:** de las 15 prendas nuevas, 14 fueron «encaja» (en B, «encaja» fue el 36 % de lo puntuado); es lo esperable si el brazo recupera bien, pero no se descarta algo de indulgencia dos semanas después. (6) Las medidas de las que salen los textos las hizo un clasificador con errores conocidos (§6.11): sus errores forman parte de lo evaluado. (7) Un texto por tendencia y una sola evidencia: no se ha medido la variabilidad por cambiar de muestra de referencia.

## 6. Qué sigue

Brazo opcional con modelo abierto (Qwen, nunca API comercial) que reformule los mismos hechos, congelado antes de puntuar; Trend JSON de producción por estilo y mercado con las fotos de mercado (la primera tanda grande llega el 19 de octubre); puntuación de SKUs con el §7 de `Estado_arte.md` más coincidencia de atributos y los casos borde del §7.5; página de aprobación del operario (HMI simulado); un segundo juez o una repetición de la puntuación; catálogo con prendas de lujo.
