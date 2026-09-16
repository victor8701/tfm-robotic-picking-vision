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

## Cómo funciona, paso a paso

CLIP es un modelo que sabe convertir **tanto imágenes como texto** en un
vector de 512 números (un "embedding"), y lo hace de forma que dos cosas
que significan lo mismo — una foto de unas zapatillas y la frase "unas
zapatillas deportivas" — caen en vectores parecidos, aunque una sea
imagen y la otra texto. Es la pieza que permite comparar "lo que dice una
tendencia de moda" con "lo que se ve en una foto de prenda", que es
justo el puente que necesita el TFM entre marketing (texto) y el robot
(imagen).

El script hace esto:

1. **Carga CLIP** (`ViT-B/32`, los pesos originales de OpenAI).
2. **Convierte las 5 imágenes de `muestras/` en 5 vectores** (`v_prenda`,
   uno por imagen) — esto se hace una sola vez al arrancar.
3. **Por cada tendencia de `tendencias_ejemplo.json`**, convierte su
   campo `descripcion` (texto) en un vector (`v_tendencia`).
4. **Calcula el score de cada pareja (prenda, tendencia)** con la
   fórmula de §7.2:
   - `score_semantico` = similitud coseno entre `v_prenda` y
     `v_tendencia` — un número entre -1 y 1 que mide "cuánto se parecen"
     (en la práctica, para CLIP, los valores relevantes suelen caer
     entre 0.15 y 0.30; no esperes ver números cerca de 1).
   - `boost` = +0.1 si el `grupo_estilo` de esa prenda (asignado a mano
     en `muestras_metadata.json`) coincide con el `grupo_estilo_detectado`
     de la tendencia. Si no coincide, +0.0.
   - `score_total` = la suma de los dos.
5. **Ordena las 5 muestras de mayor a menor `score_total`** y las
   imprime.

No hay entrenamiento ni ajuste de ningún tipo — CLIP se usa "tal cual"
(zero-shot), que es exactamente el escenario que quiere poner a prueba
`Estado_arte.md` §13.4.

## Cómo probarlo

Necesitas Python 3 y conexión a internet la primera vez (para descargar
los pesos de CLIP, ~350 MB).

```bash
cd experimentos/clip_trend_matching
pip install -r requirements.txt
python3 clip_matching_poc.py
```

La primera ejecución tarda un poco más por la descarga del modelo; las
siguientes son casi instantáneas (los pesos quedan cacheados en
`~/.cache/huggingface`). Todo corre en CPU, no hace falta GPU.

### Qué vas a ver

Por cada una de las 3 tendencias de ejemplo, una tabla con las 5
muestras ordenadas de más a menos afín, algo así:

```
TENDENCIA: El streetwear urbano domina esta semana: sudaderas oversized...
grupo_estilo_detectado: ['Streetwear']  (intensidad=0.8)
==============================================================================
1. * Sneakers + sudaderas + gafas de sol    (grupo=Streetwear   ) score_semantico=+0.2626  boost=0.10  total=+0.3626
2.   Chaqueta + camisa + vaqueros + zapatillas (grupo=Casual    ) score_semantico=+0.2173  boost=0.00  total=+0.2173
...
```

Cómo leerlo:
- El **`*`** marca las muestras cuyo `grupo_estilo` coincide con la
  tendencia (las que reciben el boost de +0.1).
- Lo interesante no es solo qué queda en el puesto 1 — es fijarte en
  `score_semantico` **antes** de sumar el boost. En las 3 tendencias de
  este POC, la muestra "correcta" ya iba primera por similitud pura, sin
  necesidad del boost categórico. Eso es la señal de que CLIP, sin
  entrenar nada, ya capta el vocabulario de estilo razonablemente bien.
- Si alguna vez ves que el orden "correcto" solo se consigue gracias al
  `*` (es decir, que sin el boost el ranking saldría distinto), es una
  señal de que la similitud semántica sola no basta y conviene
  investigar más — bajar el umbral, cambiar de modelo CLIP, etc.

## Cómo experimentar por tu cuenta

Todo lo editable son los dos JSON, no hace falta tocar el script:

- **Prueba tendencias nuevas**: añade un objeto más en
  `tendencias_ejemplo.json` con el mismo formato (usa siempre uno de los
  6 valores de `grupo_estilo_detectado`: Casual, Streetwear, De vestir,
  Fiesta/Noche, Deportivo, Playa/Resort) y vuelve a correr el script.
- **Prueba imágenes nuevas**: mete un `.jpg` en `muestras/`, añade su
  entrada en `muestras_metadata.json` (`archivo`, `nombre`,
  `grupo_estilo`) y listo.
- **Cambia el peso del boost**: la constante `BETA_BOOST_ESTILO` al
  principio de `clip_matching_poc.py` — súbela y verás cómo el orden
  empieza a depender más del grupo categórico y menos de la similitud
  fina.

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

## Próximo paso si el ranking tiene sentido

Si las 3 tendencias de ejemplo rankean arriba la muestra "esperada",
el siguiente paso natural (fuera del alcance de este POC) es construir
el LLM Trend Agent real de §6 para dejar de escribir las tendencias a
mano, y separadamente crecer el catálogo de imágenes cuando haya acceso
físico a prendas — pero el núcleo de matching ya habría quedado validado
de forma barata y sin bloquear en el hardware.
