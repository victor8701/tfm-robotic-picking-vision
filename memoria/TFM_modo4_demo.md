# Demo del Modo 4: del análisis de tendencias al SKU, con aprobación del operario

**Autor:** Víctor Martín Parra, con el asistente · **Fecha:** 25 de octubre de 2026 · **Estado:** demo funcionando con datos reales; sin commitear
**Código:** `experimentos/clip_trend_matching/demo_modo4/` (README con el detalle y los comandos). **Relacionados:** `Estado_arte.md` §6.4–§7 (solo lectura), `TFM_experimento_C_texto_con_datos.md`, `TFM_instagram_fuente.md`.

## Resumen

Hasta ahora el flujo «tendencia → SKU» estaba descrito (§6.4–§7) y medido por trozos (Experimentos B y C). La demo lo une con código y pruebas: la tarea semanal mide qué prendas pesan en cada estilo y mercado; con eso se escribe un **Trend JSON** por casilla (sin LLM); el texto corto en inglés se codifica con CLIP; se puntúan los SKUs del inventario de prueba (`coseno + 0,1` si el grupo del ERP coincide); y el operario aprueba o rechaza desde una página que simula el HMI (aprobado → se guarda el vector en `trends/active/`; rechazado → `trends/rejected/`).

## Lo que enseña con los datos de la semana del 19 de octubre

1. **Siete de las catorce casillas (estilo × España/EEUU) de otoño-invierno 2026/27 ya pueden generar una tendencia** (al menos 3 prendas con ≥ 5 fotos): clásico EEUU, convencional España, lujo EEUU, old money España y EEUU, urbano España y EEUU. Las otras siete no, y el índice dice por qué (0-2 prendas con ≥ 5 fotos; geek EEUU, ninguna foto). Es una medida directa del cuello de botella de datos y de lo que le pedimos a Instagram.
2. **El umbral de alineación θ = 0,20 de §7.2 no sirve con estos textos:** la similitud con los 1 267 SKUs tiene mediana 0,18-0,21 y máximo 0,28-0,30, así que θ = 0,20 deja pasar entre el 25 % y el 57 % del inventario. Hace falta un umbral relativo (p. ej. el percentil 95 de cada tendencia) o validarlo con datos.
3. **El boost de grupo (β = 0,1) domina el orden:** el mejor SKU y el percentil 90 de la similitud están a solo 0,03-0,075, menos que β. Los 5 primeros SKUs de las 7 tendencias son todos de los grupos de la tendencia (y los 10 primeros, en convencional España y urbano España/EEUU): el texto apenas decide dentro de un grupo. Hay que validar β con puntuación humana.
4. **La intensidad (viralidad) no se mide todavía:** el campo queda vacío en vez de inventar una cifra.

## Límites

El inventario son miniaturas de una tienda en línea, no el catálogo real; muchas casillas tienen confianza baja; cada fuente tiene un único mercado; el HMI es una página (Artifact «Aprobar tendencias»), no el FlexPendant. Sin evaluación humana de los SKUs elegidos con esta variante de texto por casilla (el Experimento C evaluó el texto por estilo, no por mercado).

## Qué sigue

Umbral relativo y β validados con puntuación humana; medida de intensidad (viralidad por casilla); Trend JSON en los dos formatos (español para la persona, inglés para CLIP) generados cada semana por la tarea; conectar la aprobación con la carpeta `trends/active/` real; y repetir con el catálogo real de SKUs.
