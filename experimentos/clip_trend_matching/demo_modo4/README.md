# Demo del Modo 4: del análisis de tendencias al SKU, con aprobación del operario

**Fecha:** 25 de octubre de 2026 · **Estado:** demo funcionando con datos reales de la tarea semanal y el inventario de prueba del Experimento B (no es el catálogo real de SKUs).
Une, con código y pruebas, lo que `Estado_arte.md` §6.4–§7 solo describía: **Trend JSON por estilo × mercado → vector de texto de CLIP → puntuación de SKUs → aprobación del operario (HMI simulado)**. No toca `Estado_arte.md`.

## Piezas

| Fichero | Qué hace |
|---|---|
| `trend_json_mercado.py` | Lee `informe.json` (cuota de cada prenda por estilo × mercado × temporada) y `separacion_estilos.json` (rasgos del estilo, receta R1) y escribe `trends/pending/{fecha}_{mercado}_{estilo}.json` con los campos de §6.4 (`mercado`, `genero_objetivo`, `tipo_prenda`, `fuentes`, `fecha_analisis`, `descripcion`, `grupo_estilo_detectado`, `intensidad`, `estado: pendiente`) más `descripcion_clip` y la evidencia. Sin LLM: cada palabra tiene una cifra detrás. `trends/indice.json` cuenta TODAS las casillas y por qué no se generan las que no tienen datos |
| `puntuar_skus.py` | `score = coseno(v_prenda, v_tendencia) + β·[grupo del SKU ∈ grupo_estilo_detectado]` con β = 0,1 y θ = 0,20 (§7.2), usando los embeddings ya calculados del inventario (`experimento_b/cache/catalogo_v2.npz`); el vector de la tendencia sale del texto `descripcion_clip` |
| `hmi_aprobacion.py` + `hmi_aprobacion.html` | Página de toques (Artifact con base de datos) para el operario: cada tendencia con su texto, las prendas que la sostienen, los 5 SKUs que elegiría el sistema y los botones Aprobar / Rechazar. `aplicar` mueve lo aprobado a `trends/active/` con su vector de texto (§6.5) y lo rechazado a `trends/rejected/` |
| `test_demo_modo4.py` | 8 pruebas sin red ni CLIP (esquema de §6.4, casillas con pocos datos, índice de 14 casillas, puntuación con boost y umbral, aprobar/rechazar) |

## Cómo se ejecuta

```
python3 trend_json_mercado.py generar            # → trends/pending/ + trends/indice.json
python3 puntuar_skus.py puntuar                  # → trends/scored/ (carga CLIP; unos 20 s)
python3 hmi_aprobacion.py html --salida PAGINA.html     # página para publicar como Artifact
python3 hmi_aprobacion.py aplicar --dir DECISIONES      # tras aprobar/rechazar en la página
```

## Lo que muestra con los datos del 24-25 de octubre

- **7 de las 14 casillas (7 estilos × España/EEUU) de la temporada otoño-invierno 2026/27 tienen datos suficientes** (al menos 3 prendas con ≥ 5 fotos): clásico EEUU, convencional ES, lujo EEUU, old money ES y EEUU, urbano ES y EEUU. Las otras 7 no se generan y el índice dice por qué (bohemio ES y EEUU, clásico ES, convencional EEUU, geek ES, lujo ES: 0-2 prendas con ≥ 5 fotos; geek EEUU: ninguna foto). **Son justo las casillas que la fuente de Instagram intenta llenar** (ver `memoria/TFM_instagram_fuente.md`).
- **El umbral θ = 0,20 de §7.2 no discrimina con estos textos cortos en inglés:** la similitud semántica de los 1 267 SKUs con una tendencia tiene mediana 0,18-0,21, percentil 90 de 0,22-0,25 y máximo 0,28-0,30, así que θ = 0,20 «alinea» entre el 25 % y el 57 % del inventario. Conviene un umbral relativo (por ejemplo, el percentil 95 de cada tendencia, ≈ 0,25-0,27) o fijarlo con un conjunto de validación.
- **El boost de grupo (β = 0,1) domina el orden:** la distancia entre el mejor SKU y el percentil 90 de la similitud es de solo 0,03-0,075, menos que β. Resultado: **los 5 primeros SKUs de las 7 tendencias son todos de los grupos de la tendencia** (los 10 primeros, también en convencional ES y urbano ES/EEUU). Es coherente con §7.2 como filtro categórico, pero contradice «la semántica es la señal principal»: con β = 0,1 y este inventario, el texto apenas decide dentro de un grupo. Hay que validar β (¿0,02-0,05?) con puntuación humana.
- **Intensidad:** sin medida de viralidad no hay cifra; el campo queda `null` en vez de inventarla.
- **Diferencia con §6.5:** el codificador procesa `descripcion_clip` (texto corto en inglés), no `descripcion` (español, para la persona), porque es lo que dieron mejor los Experimentos B y C.

## Límites

Inventario de prueba (miniaturas de 60×80 px de una tienda en línea, 60 «extra» sin grupo), datos con confianza baja en muchas casillas, un solo mercado asignado por fuente, sin viralidad, y un HMI que es una página: no hay FlexPendant ni robot.
