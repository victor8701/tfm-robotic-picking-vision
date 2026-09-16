# POC: matching semántico CLIP prenda ↔ tendencia

Prueba de concepto aislada del **matching semántico** descrito en
[`memoria/Estado_arte.md`](../../memoria/Estado_arte.md), sección 7
("Semantic matching: prenda ↔ tendencia"). No depende de los robots, de
la caja rígida real, ni de fotos nuevas de ropa — solo de CLIP y de un
puñado de imágenes que ya existían en el repo.

## Qué valida

La hipótesis a comprobar: dado un texto de tendencia (el tipo de salida
que generará el LLM Trend Agent de la sección 6) y una imagen de prenda,
¿la similitud coseno de CLIP + el boost categórico de Grupo de estilo
(fórmula exacta de 7.2, `score = score_semantico + β·boost_estilo`, con
`β = 0.1`) produce un ranking que tiene sentido de moda?

Es el riesgo #1 que ya está anotado en `Estado_arte.md` §13.4 ("CLIP
zero-shot no alcanza Recall@5 > 80%") — esto es la forma más barata de
empezar a tantear ese riesgo, antes de construir el ERP, la app de
etiquetado o el catalog matching real.

## Qué NO es

- No es el catalog matching final de §4.3 (eso necesita SKUs reales,
  fotos en condición "cámara del robot", e índice vectorial por tipo).
- No es el LLM Trend Agent de §6 — las 3 tendencias de
  `tendencias_ejemplo.json` están escritas a mano, con el mismo schema
  que generaría el LLM (§6.4), pero no vienen de redes sociales reales.
- No pretende medir Recall@K con rigor estadístico — son 5 imágenes,
  suficientes para una inspección cualitativa, no para una métrica.

## Datos usados

Las 5 imágenes de `muestras/` **no son fotos nuevas**: son renders ya
generados para el proyecto de Visión por Computador (rama `proyecto_VC`
de este mismo repo, `images/02Dic/1.jpg`, `5.jpg`, `10.jpg`, `15.jpg` y
`20.jpg`). Cada una agrupa varias prendas afines dentro de una caja, así
que aquí se tratan como un "set temático" completo, no como una prenda
aislada — es una simplificación deliberada para esta prueba rápida.

Cada muestra tiene asignado a mano un `grupo_estilo` (uno de los 6
valores cerrados de §3.4.1) en `muestras_metadata.json`:

| Muestra | Grupo de estilo |
|---|---|
| 1 — sneakers + sudaderas + gafas | Streetwear |
| 2 — chaqueta + camisa + vaqueros | Casual |
| 3 — vestido + tacones + camisa + botas | De vestir |
| 4 — vestido + sombrero + corbata + cinturón | Fiesta/Noche |
| 5 — pamela + falda + top + pañuelo | Playa/Resort |

No hay ninguna muestra "Deportivo" — limitación de este set de 5 imágenes,
en la línea de lo que ya documenta `Estado_arte.md` §14.3 sobre balance
de catálogo entre Grupos de estilo.

## Uso

```bash
pip install -r requirements.txt
python3 clip_matching_poc.py
```

La primera ejecución descarga los pesos de CLIP ViT-B/32 (~350 MB).

## Próximo paso si el ranking tiene sentido

Si las 3 tendencias de ejemplo rankean arriba la muestra "esperada",
el siguiente paso natural (fuera del alcance de este POC) es construir
el LLM Trend Agent real de §6 para dejar de escribir las tendencias a
mano, y separadamente crecer el catálogo de imágenes cuando haya acceso
físico a prendas — pero el núcleo de matching ya habría quedado validado
de forma barata y sin bloquear en el hardware.
