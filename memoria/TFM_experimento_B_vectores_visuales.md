# Experimento B — ¿aporta la evidencia visual al vector de tendencia? (resultado: no se detecta mejora)

**Autor:** Víctor Martín Parra · **Fecha:** 3 de octubre de 2026
**Estado:** **cerrado**. v1 (pre-registrada): neutro. v2 (exploratoria, corrige la falta de prendas «geek»): lo confirma.
**Código y datos:** `experimentos/clip_trend_matching/experimento_b/` (su README recoge el diseño y cómo reproducirlo).
**Relacionados:** `TFM_briefing_opcion_B.md`, `plan_de_implementacion_pipeline_visual_en_la_nube.md`; `Estado_arte.md` §6–7 y §11 (solo lectura).

## Resumen

Se compararon, con CLIP y puntuación humana a ciegas, un vector de tendencia **de texto**, uno **visual** (centroide de 10 fotos reales confirmadas) y una **fusión**. Con la regla fijada de antemano (v1: 7 tendencias, 268 prendas puntuadas) **no se detecta mejora** de la evidencia visual, y la v2 lo confirma: la evidencia visual iguala a un texto pobre pero **nunca supera a un texto bien especificado**, y añadida a éste tiende a empeorarlo. Lo que domina el resultado no es lo visual sino **lo bien especificada que esté la tendencia en el texto**: el prompt escrito conociendo la definición del estilo obtiene un 70 % de P@5 frente a un 30-37 % de los textos generados solo a partir del *nombre* de la tendencia. Con 6-7 tendencias el IC es de ±25 pp: «neutro» significa «no se detecta un efecto grande», no «no hay efecto».

## 1. Pregunta e hipótesis

El *Trend Intelligence Agent* (§6) describe cada tendencia solo con texto y el matching (§7) es el coseno CLIP entre ese texto y la foto de cada SKU. ¿Añadir evidencia visual de la tendencia (fotos reales) mejora la recuperación de prendas?
**H1** el vector visual iguala o supera al de texto · **H2** la fusión `α·texto + (1−α)·visual` iguala o supera al mejor de los dos.

## 2. Diseño

**v1 (fijada el 3-oct-2026 antes de puntuar).** 7 tendencias (los sub-estilos de §3.4.2) · inventario de 1 207 miniaturas de **60×80 px** de un catálogo de e-commerce (Kaggle) · CLIP ViT-B/32 (`open_clip`, pesos OpenAI, `quickgelu`) · evidencia visual: 10 fotos reales confirmadas por tendencia (semilla 0), **centroide recortado** (se descarta el 20 % más alejado) · fusión con α = 0,5.
Seis métodos: `T_ciego_en` / `T_ciego_es` (descripción redactada por Gemini `gemini-3.5-flash-lite`, T = 0, que solo conoce el *nombre* de la tendencia; en inglés y en español), `T_oraculo_en` (prompt corto escrito conociendo la taxonomía: cota superior optimista), `V` (centroide visual), `F_ciego` y `F_oraculo` (fusiones).
Puntuación humana a ciegas (0/1/2) de las 268 prendas del *pool* (unión de los top-10), sin ver qué método propuso cada una; Víctor usó **solo 0 y 2**, por lo que P@K estricto = laxo. Métricas: P@5 (primaria), NDCG, P@10; diferencias emparejadas por tendencia con IC95 % t y *p* exacto por permutación de signos (el bootstrap percentil dio un 12,8 % de falsos positivos con 7 tendencias en una simulación con puntuaciones aleatorias; t: 6,4 %; permutación: 1,3 %). Regla: **mejora** = ≥ +5 pp con IC95 % que excluye 0.

**v2 (exploratoria, diseñada *viendo* la v1).** En la v1, `alternativo_geek` y `lujo_ostentoso` tuvieron techo ≈ 0 con todos los métodos (2 y 5 prendas aprobadas de 43 y 42 propuestas): el catálogo no tenía ese tipo de prendas (Víctor lo confirmó; sus referencias: Dani Alves para lujo ostentoso, Orslok para geek). Cambios:
- **+60 prendas «geek»** de adulto con motivos de fandom (Batman, Marvel, Angry Birds…) del mismo dataset de origen, elegidas por regla sobre metadatos y no por CLIP ni por resultados.
- **`lujo_ostentoso` excluido**: no es evaluable con inventario gratuito (≈ 4 prendas de diseñador reales en el dataset; Wikimedia devuelve escaneos, pasarelas y fotos de personas).
- **Dos brazos nuevos**: `T_corto_ciego_en` (prompt corto redactado por el mismo LLM ciego) y `F_corto` (su fusión con `V`); y el oráculo de `alternativo_geek` corregido según la definición de la taxonomía (el de la v1 decía «techwear, goth or punk»).
- Se reutilizan las 268 puntuaciones; se puntuaron 41 prendas nuevas. Primarias declaradas antes de puntuar: `F_corto − T_corto_ciego_en` y `T_corto_ciego_en − T_ciego_en`; todo lo demás es exploratorio.

## 3. Resultados

**v1 (7 tendencias; la pre-registrada).**

| Método | P@5 | NDCG@5 | P@10 | NDCG@10 |
|---|---|---|---|---|
| `T_ciego_en` (texto largo, inglés) | 23 % | 0,24 | 31 % | 0,31 |
| `T_ciego_es` (texto largo, español) | 34 % | 0,34 | 37 % | 0,40 |
| `T_oraculo_en` (prompt corto, informado) | **51 %** | 0,47 | **46 %** | 0,47 |
| `V` (solo evidencia visual) | 29 % | 0,31 | 40 % | 0,40 |
| `F_ciego` | 34 % | 0,32 | 39 % | 0,37 |
| `F_oraculo` | 37 % | 0,35 | 41 % | 0,39 |

Comparaciones (P@5, pp; victorias/empates/derrotas por tendencia): `F_ciego − T_ciego_en` +11 [−12, +35] (3/3/1) · `F_oraculo − T_oraculo_en` −14 [−37, +9] (1/2/4) · `V − T_oraculo_en` −23 [−45, −0,4], *p* perm. 0,125 (0/3/4) · español − inglés +11 [−17, +39]. **Veredicto de la regla: neutro.**

**v2 (6 tendencias, sin lujo; inventario de 1 267 prendas).**

| Método | P@5 | NDCG@5 | P@10 | NDCG@10 |
|---|---|---|---|---|
| `T_ciego_en` | 30 % | 0,31 | 37 % | 0,35 |
| `T_ciego_es` | 37 % | 0,34 | 38 % | 0,36 |
| `T_corto_ciego_en` (corto, **sin** conocer la taxonomía) | 37 % | 0,39 | 35 % | 0,39 |
| `T_oraculo_en` (corto, **informado**) | **70 %** | 0,66 | **65 %** | 0,66 |
| `V` | 33 % | 0,36 | 42 % | 0,41 |
| `F_ciego` | 40 % | 0,37 | 45 % | 0,42 |
| `F_corto` | 40 % | 0,41 | 42 % | 0,43 |
| `F_oraculo` | 50 % | 0,50 | 53 % | 0,52 |

| Comparación (P@5) | Diferencia [IC95 %] | V/E/D | *p* perm. | Nota |
|---|---|---|---|---|
| `F_corto − T_corto_ciego_en` | +3 pp [−5, +12] | 1/5/0 | 1,00 | **primaria** → neutro (P@10: +7 [−8, +21]) |
| `T_corto_ciego_en − T_ciego_en` | +7 pp [−22, +35] | 3/2/1 | 0,75 | **primaria** → neutro (P@10: −2) |
| `T_corto_ciego_en − T_oraculo_en` | −33 pp [−50, −16] | 0/0/6 | 0,031 | exploratoria; 6 de 6 tendencias |
| `V − T_oraculo_en` | −37 pp [−61, −12] | 0/1/5 | 0,062 | exploratoria |
| `F_oraculo − T_oraculo_en` | −20 pp [−47, +7] | 1/0/5 | 0,19 | exploratoria |
| `V − T_corto_ciego_en` | −3 pp [−24, +17] | 2/1/3 | 1,00 | exploratoria |

**Por tendencia (P@5, v2).**

| Tendencia | T ciego | T corto ciego | T oráculo | V | F ciego | F corto | F oráculo | Aprobadas / pool |
|---|---|---|---|---|---|---|---|---|
| old_money | 20 % | 20 % | 40 % | 40 % | 40 % | 20 % | 60 % | 19/35 |
| clasico_tradicional | 0 % | 20 % | 60 % | 0 % | 0 % | 20 % | 0 % | 6/46 |
| urbano | 60 % | 80 % | 100 % | 60 % | 60 % | 100 % | 80 % | 23/41 |
| bohemio | 100 % | 60 % | 80 % | 40 % | 80 % | 60 % | 60 % | 19/35 |
| alternativo_geek | 0 % | 0 % | 60 % | 0 % | 0 % | 0 % | 40 % | **14/47** (era 5/42) |
| convencional | 0 % | 40 % | 80 % | 60 % | 60 % | 40 % | 60 % | 24/44 |

**Geek tras la ampliación.** El techo ya no es cero: 14 de 47 prendas del *pool* aprobadas, y 10 de las 12 añadidas que llegaron al *pool*. Pero **ningún método sin conocimiento de la taxonomía recuperó una sola prenda añadida en su top-5** (texto ciego largo, texto ciego corto, `V`, `F_ciego`, `F_corto`: 0/5), mientras que el prompt informado recuperó 4 (3 aprobadas) y `F_oraculo` 2 (2 aprobadas). El texto ciego entendió «geek» como *nerd* preppy («oversized graphic sweater, pleated plaid mini skirt, thick-rimmed glasses»), no como ropa de fandom.

## 4. Interpretación

**Se puede afirmar (con las cautelas de §5)**
1. **No hay evidencia de que la evidencia visual mejore el matching.** Regla pre-registrada: neutro (v1); las dos comparaciones primarias de la v2: neutras.
2. **La evidencia visual no supera a un texto bien especificado y, sumada a él, tiende a empeorarlo**: `V − T_oráculo` = −23 pp (v1) y −37 pp (v2); `F_oráculo − T_oráculo` = −14 pp (v1) y −20 pp (v2), con más derrotas que victorias en ambos. Con evidencia validada por una persona (el mejor caso posible para `V`) y en un inventario con prendas relevantes.
3. **La especificación del texto domina el resultado.** El prompt informado supera al corto ciego en las 6 tendencias (−33 pp, *p* = 0,031; exploratoria, 8 comparaciones sin corregir). El **formato corto, por sí solo, no lo explica**: corto ciego − largo ciego = +7 pp en P@5 (IC [−22, +35]) y −2 pp en P@10. *(Esto corrige la lectura provisional tras la v1, que atribuía la ventaja del oráculo al formato; la v2 la separa: pesa el conocimiento de qué significa cada estilo, no la longitud.)*
4. No se observa penalización por escribir la descripción en español con un CLIP de inglés (+7 pp a favor del español, IC amplio).

**Sugerido, no afirmable**
- La evidencia visual puede **reparar un texto mal interpretado** (v1, «convencional»: el texto ciego, interpretado como traje corporativo, 0 % → su fusión 60 %); en la v2 `F_ciego − T_ciego` = +10 pp (2/3/1), no significativo. Si lo visual aporta algo, sería como mecanismo de robustez ante textos pobres, no como mejora media.
- El centroide de fotos de calle **no recuperó prendas con estampado de fandom** (geek, 0/5), coherente con el salto de dominio *street-to-shop*: el embedding de un look completo codifica persona y escena, no el motivo de una camiseta.

## 5. Amenazas a la validez

- **Potencia:** 6-7 tendencias; IC de ±25 pp en P@5. Solo detecta diferencias grandes.
- **Oráculo circular:** lo redactó el investigador conociendo la definición que luego usa el evaluador para puntuar (alineación casi por construcción). El oráculo de `alternativo_geek` se corrigió *después* de ver la v1 y las prendas añadidas se eligieron por motivos de fandom que ese prompt nombra: su acierto en geek demuestra que ya hay prendas relevantes, no que CLIP-texto generalice.
- **Texto ciego** parte solo del nombre: cota inferior del agente real, que ve el contenido de los vídeos. La mejora de «dar definiciones» (punto 3) es plausible pero **no se ha probado con un agente real**.
- **Inventario:** miniaturas de 60×80 px de básicos de e-commerce, no el catálogo de SKUs; `lujo_ostentoso` no evaluable.
- **Salto de dominio** (*street-to-shop*) entre la evidencia (looks completos con persona y fondo) y el inventario (prendas aisladas).
- Un solo evaluador, puntuación de facto binaria, evidencia de una galería mezclada (X, Wikimedia, subidas) etiquetada por la misma persona que puntúa.
- **Grados de libertad del investigador** en la v2 (decidida viendo la v1) y comparaciones múltiples sin corregir: por eso es exploratoria salvo las dos primarias.
- Todos los textos largos (ES/EN del LLM ciego) se truncan a los 77 tokens de CLIP.

## 6. Implicaciones para el diseño del TFM

1. **Regla del plan aplicada:** resultado neutro → **no se prioriza el vector de tendencia visual**; los Pasos 1-2 del plan (recogida y filtrado de fotos en la nube) quedan en pausa. Se revisita solo con el **catálogo real de SKUs en alta resolución**, ≥ 15 tendencias, más de un evaluador y evidencia más cercana al dominio del inventario (fotos de prenda, no de look).
2. **Qué sí cambiar en el Modo 4 (barato):** el *Trend Intelligence Agent* (§6.3) debería recibir en su prompt las **definiciones de los grupos de estilo (§3.4.1) y un vocabulario de prendas**, y producir un texto que **nombre prendas concretas** coherentes con el ERP; el oráculo hizo en esencia eso y fue el único método claramente mejor. Mantener el texto por debajo de 77 tokens (el efecto del formato es pequeño, pero el truncado descarta contenido en silencio). Debe validarse con el agente real y juicio humano (§11.2): «prompt genérico» frente a «prompt con definiciones».
3. **Tendencias sin candidatos** (lujo, y probablemente más en un catálogo de segunda mano «por kilo», §5.6): tratarlo como caso normal con el *fallback* de §7.5 (todos los SKU por debajo de θ) y la limitación de §14.3, no como error.
4. Para la memoria final: presentar el experimento como **resultado neutro con diseño pre-registrado, extensión exploratoria declarada y límites explícitos**, junto con el hallazgo sobre la especificación del texto.

## 7. Reproducibilidad

```bash
cd experimentos/clip_trend_matching/experimento_b
# v1
python3 generar_textos_ciegos.py     # textos ciegos (Gemini gratuito, T = 0) → textos_tendencia_b.json (versionado)
python3 experimento_b.py preparar    # embeddings (caché), vectores, pool_b.json y pool_b_clave.json
python3 evaluar_b.py                 # puntuación a ciegas en http://localhost:8765 → ratings_b.json
python3 experimento_b.py analizar
# v2
python3 generar_textos_ciegos.py --solo-v2   # añade el prompt corto ciego y el oráculo corregido sin tocar lo existente
python3 anadir_inventario_extra.py           # +60 prendas en inventario_extra/geek/
python3 experimento_b.py preparar-v2         # pool_b_v2.json = solo las prendas aún sin puntuar
python3 evaluar_b.py --pool pool_b_v2.json
python3 experimento_b.py analizar-v2
```

Parámetros fijados: α = 0,5; N = 10 fotos; recorte 20 %; semilla de evidencia 0; CLIP `ViT-B-32-quickgelu` (OpenAI); K = 5 (primaria) y 10. Los 309 juicios de Víctor (268 + 41) están en `ratings_b.json`.
