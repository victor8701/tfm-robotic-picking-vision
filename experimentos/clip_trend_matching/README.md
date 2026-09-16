# POC: matching semántico CLIP prenda ↔ tendencia

Prueba de concepto aislada del **matching semántico** descrito en
[`memoria/Estado_arte.md`](../../memoria/Estado_arte.md), sección 7
("Semantic matching: prenda ↔ tendencia"). No depende de los robots, de
la caja rígida real, ni de fotos nuevas de ropa — solo de CLIP y de un
puñado de imágenes que ya existían en el repo.

**No hay que tocar código ni registrar nada en un JSON**: el script lee
TODO el contenido de una carpeta de imágenes (por defecto `muestras/`,
o la que le indiques por terminal) y le pone cualquier nombre de
archivo vale — se usa solo para mostrarlo en pantalla.

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

1. **Lee todas las imágenes de la carpeta indicada** (`--muestras`,
   por defecto `muestras/`) — cualquier `.jpg`/`.jpeg`/`.png`/`.webp`
   que haya dentro, sin necesidad de registrarlas en ningún sitio.
2. **Carga CLIP** (`ViT-B/32`, los pesos originales de OpenAI) y
   convierte cada imagen en un vector (`v_prenda`).
3. **Detecta automáticamente el `grupo_estilo` de cada imagen**
   (Casual, Streetwear, De vestir, Fiesta/Noche, Deportivo o
   Playa/Resort — el vocabulario cerrado de §3.4.1): compara la imagen
   contra una frase descriptiva de cada uno de los 6 grupos y se queda
   con el de mayor similitud. **Importante**: en el sistema real ese
   campo lo fija marketing a mano en el ERP (§3.5) — aquí se infiere
   solo para no tener que etiquetar nada en este POC. Ver el aviso más
   abajo, porque esta parte no es perfecta.
4. **Por cada tendencia de `tendencias_ejemplo.json`**, convierte su
   campo `descripcion` (texto) en un vector (`v_tendencia`).
5. **Calcula el score de cada pareja (prenda, tendencia)** con la
   fórmula de §7.2:
   - `score_semantico` = similitud coseno entre `v_prenda` y
     `v_tendencia` — un número entre -1 y 1 (en la práctica, para CLIP,
     los valores relevantes suelen caer entre 0.15 y 0.30; no esperes
     ver números cerca de 1).
   - `boost` = +0.1 si el `grupo_estilo` detectado en el paso 3 coincide
     con el `grupo_estilo_detectado` de la tendencia. Si no, +0.0.
   - `score_total` = la suma de los dos.
6. **Ordena las imágenes de mayor a menor `score_total`** y las
   imprime, tendencia por tendencia.

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

Eso usa la carpeta `muestras/` que ya trae el repo. Para usar tus propias
imágenes sin tocar nada del código, tienes dos formas de indicar la
carpeta con `--muestras` (o `-m`):

- **Nombre corto** (sin ruta): se busca como subcarpeta de
  `clip_trend_matching/`. Por ejemplo, si creas
  `experimentos/clip_trend_matching/streetwear/` y la llenas de fotos,
  te vale con:

  ```bash
  python3 clip_matching_poc.py --muestras streetwear
  # o, exactamente igual:
  python3 clip_matching_poc.py --muestras /streetwear
  ```

  (la barra inicial es opcional, el script la ignora — ambas formas
  apuntan a `clip_trend_matching/streetwear`).

- **Ruta absoluta**: si la carpeta está fuera del proyecto (por ejemplo,
  en tu escritorio), pásala completa y se usa tal cual:

  ```bash
  python3 clip_matching_poc.py --muestras /home/ubuntu22/Desktop/mis_fotos
  ```

También puedes apuntar a otro fichero de tendencias con
`--tendencias otro_archivo.json` (`-t`), si no quieres usar
`tendencias_ejemplo.json`.

La primera ejecución tarda un poco más por la descarga del modelo; las
siguientes son casi instantáneas (los pesos quedan cacheados en
`~/.cache/huggingface`). Todo corre en CPU, no hace falta GPU.

### Qué nombres le pongo a las imágenes

El que quieras. El nombre de archivo solo se usa para mostrarlo en
pantalla (los guiones bajos y medios se convierten en espacios), así
que `zapatillas_urbanas.jpg` se verá como "Zapatillas urbanas". No hay
ninguna convención que seguir ni ningún sitio donde registrarlas aparte.

### Qué vas a ver

Primero, la lista de imágenes encontradas y el grupo de estilo que CLIP
le ha asignado a cada una. Luego, por cada tendencia, una tabla con las
imágenes ordenadas de más a menos afín:

```
Grupo de estilo detectado automaticamente por CLIP (zero-shot):
  - Caja zapatillas sudaderas gafas     -> Streetwear
  - Caja pamela falda top panuelo       -> Fiesta/Noche
  ...

TENDENCIA: El streetwear urbano domina esta semana: sudaderas oversized...
==============================================================================
1. * Caja zapatillas sudaderas gafas     (grupo=Streetwear   ) score_semantico=+0.2626  boost=0.10  total=+0.3626
2.   Caja chaqueta camisa vaqueros       (grupo=Casual       ) score_semantico=+0.2173  boost=0.00  total=+0.2173
...
```

Cómo leerlo:
- El **`*`** marca las imágenes cuyo `grupo_estilo` (detectado en el
  paso 3) coincide con la tendencia (las que reciben el boost de +0.1).
- Lo interesante no es solo qué queda en el puesto 1 — es fijarte en
  `score_semantico` **antes** de sumar el boost. En las 3 tendencias de
  este POC, la imagen "correcta" ya iba primera por similitud pura, sin
  necesidad del boost categórico.

### Aviso: la detección automática de grupo_estilo falla a veces (y eso es útil saberlo)

Con las 5 imágenes de `muestras/`, CLIP clasificó bien 3 de 5 grupos a
ojo humano, pero se equivocó en 2: una caja con pamela + falda + top +
pañuelo (que a ojo es más "Playa/Resort") salió como "Fiesta/Noche", y
una caja con vestido + sombrero + corbata (que a ojo es más
"Fiesta/Noche") salió como "De vestir". No es un bug del script — es el
propio modelo dudando entre categorías parecidas, que es exactamente el
riesgo de acoplamiento frágil que ya documentaste en `Estado_arte.md`
§14.1 (ahí hablabas del LLM devolviendo un grupo fuera de vocabulario;
aquí es CLIP dudando entre dos grupos válidos, pero el síntoma —el
boost categórico fallando en silencio— es el mismo).

Lo tranquilizador: en los 3 casos el ranking final seguía poniendo la
imagen "correcta" en primer lugar gracias solo al `score_semantico`,
boost o no boost. Es la prueba de que la señal semántica de CLIP es la
que de verdad sostiene el sistema, y el boost categórico es un refuerzo,
no una muleta — tal y como ya lo planteaba tu propio §7.2 ("el score
semántico sigue siendo la señal principal").

## Cómo experimentar por tu cuenta

- **Prueba tendencias nuevas**: añade un objeto más en
  `tendencias_ejemplo.json` con el mismo formato (usa siempre uno de los
  6 valores en `grupo_estilo_detectado`: Casual, Streetwear, De vestir,
  Fiesta/Noche, Deportivo, Playa/Resort).
- **Prueba imágenes nuevas**: copia cualquier `.jpg`/`.png` a `muestras/`
  (o a otra carpeta y usa `--muestras`) y vuelve a correr el script — no
  hay que editar ningún JSON de imágenes, ya no existe.
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
- El `grupo_estilo` que ve este script lo infiere CLIP por zero-shot,
  no viene fijado por marketing como en el diseño real (§3.5) — ver el
  aviso más arriba.

## Datos usados

Las 5 imágenes de `muestras/` **no son fotos nuevas**: son renders ya
generados para el proyecto de Visión por Computador (rama `proyecto_VC`
de este mismo repo, `images/02Dic/1.jpg`, `5.jpg`, `10.jpg`, `15.jpg` y
`20.jpg`, renombradas aquí sin pista del grupo de estilo para no viciar
la detección automática). Cada una agrupa varias prendas afines dentro
de una caja, así que aquí se tratan como un "set temático" completo, no
como una prenda aislada — es una simplificación deliberada para esta
prueba rápida.

No hay ninguna imagen "Deportivo" en el set de partida — limitación de
estas 5 imágenes, en la línea de lo que ya documenta `Estado_arte.md`
§14.3 sobre balance de catálogo entre Grupos de estilo. Añade una tú
mismo con `--muestras` si quieres comprobar ese grupo también.

## Próximo paso si el ranking tiene sentido

Si las tendencias de ejemplo rankean arriba la imagen "esperada", el
siguiente paso natural (fuera del alcance de este POC) es construir el
LLM Trend Agent real de §6 para dejar de escribir las tendencias a
mano, y separadamente crecer el catálogo de imágenes cuando haya acceso
físico a prendas — pero el núcleo de matching ya habría quedado validado
de forma barata y sin bloquear en el hardware.
