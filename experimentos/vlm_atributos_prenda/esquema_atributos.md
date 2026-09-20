# Esquema de atributos v3 — clasificador de prendas desde foto

Fuente de verdad de las tablas de mapeo `dataset Kaggle → esquema de esta tesis`, usadas por
`herramientas/preparar_dataset_florence2.py`. Reutiliza y colapsa campos que ya existen en
`memoria/Estado_arte.md` §3.3/§3.4 — no es un esquema inventado desde cero (mismo espíritu que
el paper "Fashion Florence", que colapsa las 228 etiquetas de iMaterialist a un puñado de
campos compactos).

**v2 (2026-09-20):** tras revisar 100 fichas a mano en la app "Ficha de Prenda", se decidieron
tres cambios de regla (`temporada` de `Jackets`, `grupo_estilo` de `Dresses`, filtro de ropa
infantil por nombre) — marcados como tal en cada sección, con la fecha y el motivo. El adapter
`modelos/florence2_base_lora_v1/` está entrenado con las reglas **v1** (anteriores a esta
fecha); `florence2_base_lora_v2/` con las reglas v2.

**v3 (2026-09-20, mismo día):** `temporada` se decide para el resto de tipos de prenda (13 más,
además de `Jackets`) en el artifact *"Reglas de temporada"* — marcado como tal en su sección.
Nada más cambia respecto a v2. `florence2_base_lora_v3/` es el adapter con estas reglas.
Detalle completo de las decisiones en `memoria/TFM_clasificador_visual_atributos.md` §11.1/§11.5.

## JSON objetivo

```json
{"categoria":"ropa_superior","color_primario":"negro","grupo_estilo":"streetwear","genero":"masculino","temporada":"otono_invierno"}
```

## `categoria` (§3.3, las 6 cabeceras, no los 29 tipos finos)

| categoria | `articleType` de Kaggle que caen aquí |
|---|---|
| `ropa_superior` | Tshirts, Shirts, Tops, Sweatshirts, Sweaters, Waistcoat |
| `ropa_inferior` | Jeans, Shorts, Trousers, Track Pants, Leggings, Capris, Skirts |
| `cuerpo_entero` | Dresses, Jumpsuit |
| `abrigo` | Jackets, Blazers, Rain Jacket, Nehru Jackets |
| `calzado` | Casual Shoes, Sports Shoes, Heels, Formal Shoes, Flats, Sandals, Flip Flops, Sports Sandals |
| `accesorio` | Handbags, Backpacks, Belts, Caps, Scarves, Stoles, Mufflers, Ties, Clutches |

**Excluido siempre** (mismo criterio ya usado en `poblar_muestras_dataset.py`): ropa étnica
india (Kurtas, Sarees, Salwar, Churidar, Dupatta, Patiala, Kurtis, Kurta Sets, Lehenga Choli,
Nehru Jackets *como prenda étnica* — aquí se cuela en `abrigo` por nombre pero es un caso
raro, 4 filas), ropa interior/estar por casa (Bra, Briefs, Boxers, Camisoles, Nightdress,
Shapewear, Bath Robe...), artículos no textiles (relojes, perfume, maquillaje, joyería,
gafas de sol, agua/balones/paraguas...), y filas `gender ∈ {Boys, Girls}` (~3.3% del dataset,
ropa infantil fuera de alcance). `Boots` tiene **0 filas** en las 44k del dataset — hueco
conocido, no hay nada que mapear.

## `color_primario` (§3.4, los 18 valores tal cual)

Los 46 valores distintos de `baseColour` en Kaggle, mapeados por familia de color más cercana.
Casos exactos o casi exactos primero, luego aproximaciones documentadas:

| `baseColour` (Kaggle) | → `color_primario` | Nota |
|---|---|---|
| Black | negro | exacto |
| White, Off White | blanco | exacto |
| Blue, Turquoise Blue | azul | |
| Navy Blue | navy | exacto |
| Grey, Grey Melange, Charcoal | gris | |
| Red | rojo | exacto |
| Green, Olive, Sea Green, Lime Green, Fluorescent Green | verde | |
| Pink, Rose | rosa | |
| Purple | lavanda | **aproximación** — sin valor "morado" en la paleta de la tesis |
| Lavender | lavanda | exacto |
| Mauve | rosa | aproximación (podría ir a lavanda, 28 filas) |
| Silver, Steel, Metallic | plateado | |
| Yellow, Mustard | amarillo | |
| Beige, Cream, Skin, Nude, Taupe | beige | |
| Brown, Khaki, Tan, Coffee Brown, Mushroom Brown | camel | la paleta no tiene "marrón" genérico, camel es el más cercano |
| Gold, Bronze, Copper | dorado | |
| Maroon, Burgundy | burdeos | |
| Orange, Peach, Rust | naranja | |
| Magenta | fucsia | |
| Teal | azul | aproximación (verde-azulado sin casa exacta) |
| **Multi** | *excluido* | patrón multicolor, no un color primario — se descartan esas filas del entrenamiento de este campo |

**Decisión (2026-09-20, tras la revisión humana de 100 fichas — ver `memoria/TFM_clasificador_visual_atributos.md`
§11.1): la paleta se queda como está.** `lavanda` sigue absorbiendo `Purple` y `fucsia`/`plateado` siguen con pocos
ejemplos (F1 0.00 en el test v1); se decidió no ampliar el vocabulario de §3.4 con un valor `morado` nuevo para no
tocar en profundidad ese documento. El único remedio disponible es sobremuestrear esas dos clases.

## `grupo_estilo` (§3.4.1, los 6 valores)

Reutiliza tal cual la lógica ya validada en `poblar_muestras_dataset.py` (`CATEGORIAS` dict),
generalizada de "filtro con tope por carpeta" a "función de clasificación por fila".

**`Dresses` — regla v2 (2026-09-20), reemplaza la heurística anterior.** La heurística v1
(`Dresses → fiesta_noche` sin condición) estaba mal: `usage == "Party"` solo tiene 18 de 464
filas de `Dresses`, y la revisión humana la corrigió a `casual` en 11 de 16 vestidos. Regla
nueva, por `productDisplayName` (validada contra la revisión humana: 13 de 14 vestidos no
infantiles, único contraejemplo de fábrica `Sepia Women Black Dress`):

| `productDisplayName` de `Dresses` contiene una palabra de patrón (`printed`, `striped`, `floral`, `polka`/`dot`, `checked`, `multi`/`colour`, `animal`, `a-line`, `tiered`, `ruffle`) | → `grupo_estilo` |
|---|---|
| sí | casual |
| no (liso) | fiesta_noche |

Criterio del autor: *"de noche suelen ser de un único color, más planos y quizás brillantes en
algunos casos"*. La parte de "brillante" (lentejuelas, purpurina, metalizado) no se ha podido
afinar: no hay ninguna fila de `Dresses` en este dataset con esas palabras en el nombre (catálogo
de fotos de producto de 60×80 px, no moda de pasarela).

`Heels`, `Clutches` y `Jumpsuit` **se quedan igual** (`→ fiesta_noche` sin condición): la
revisión humana los confirma para `Heels` (2/3) y `Clutches` (4/4); `Jumpsuit` tiene un único
dato revisado y no encaja (`French Connection Women Blue Playsuit` → el revisor puso
`playa_resort`), pero es una sola fila, insuficiente para cambiar la regla.

**`deportivo` + `streetwear` (sin resolver, aceptado como límite conocido).** La revisión
humana marca ambos estilos a la vez en 10 de 21 fichas multietiqueta (casi siempre ropa
deportiva de marca: mochilas, gorras, chaquetas y zapatillas de Nike/Adidas/Puma/Reebok). Se
valoró resolverlo con una regla por marca y **se descartó explícitamente** ("no quiero
marcas"). `grupo_estilo` se queda de una sola etiqueta en v1/v2; este solape es una limitación
documentada, no una regla.

## Ropa infantil colada (filtro adicional, 2026-09-20)

`gender ∈ {Boys, Girls}` ya se excluye (ver tabla de `genero` abajo), pero **713 filas del
dataset completo** (108 de las 464 de `Dresses`) son ropa infantil con `gender = Women` o
`Men` — marcas y nombres como *Gini and Jony*, *Doodle Kids*, *"Girl's"*, *"Kids"* que ese
campo no detecta. Se añade un filtro por `productDisplayName` (regex sobre `kids/girl's/boy's/
infant/baby/toddler/junior` + las dos marcas) que descarta también esas filas.

## `genero` (§3.4)

| Kaggle `gender` | → `genero` |
|---|---|
| Men | masculino |
| Women | femenino |
| Unisex | neutro |
| Boys, Girls | *excluido* (ropa infantil, fuera de alcance) |

**Sobre el criterio de `neutro` (2026-09-20):** la revisión humana cambia 6 fichas a `neutro`
que Kaggle marcaba `Men`/`Women` — siempre ropa deportiva (chaquetas, zapatillas, gorra,
chanclas). Confirmado por el autor: el criterio es visual ("¿lo llevaría cualquiera?"), no el
mercado objetivo de la marca. **La etiqueta de entrenamiento sigue siendo la de Kaggle** (no
hay una tabla de reglas por tipo de prenda que traduzca ese criterio visual, y no se ha pedido
una): esto queda documentado como una discrepancia conocida entre la etiqueta de entrenamiento
y el criterio humano, no como algo corregido en v2.

## `temporada` (§3.4, versión de 3 valores)

| Kaggle `season` / `articleType` | → `temporada` |
|---|---|
| `articleType` ∈ `TIPOS_TODO_EL_ANO` (13 tipos, tabla abajo) | **todo_el_ano** |
| resto, `season` = Summer, Spring | primavera_verano |
| resto, `season` = Fall, Winter | otono_invierno |

**Decisión v2 (2026-09-20).** El vocabulario de 3 valores de §3.4 ya no se deja "por si acaso"
(v1) — se genera de verdad para `Jackets`, con la estación de Kaggle ignorada del todo: *"vamos
a suponerlas de todas las estaciones, independientemente de lo que pusiese yo [en la
revisión]"*. Es una decisión deliberada, no derivada de los datos de revisión (que para
`Jackets` estaban repartidos: 7 otoño-invierno, 3 primavera-verano, 9 todo el año).

**Decisión v3 (2026-09-20, mismo día).** El resto de tipos de prenda ya está decidido, tipo a
tipo, en el artifact *"Reglas de temporada"* (`herramientas/generar_panel_temporada.py` /
`leer_reglas_temporada.py`): una propuesta por tipo calculada de las 100 fichas de la revisión
humana (mayoría clara de `todo_el_ano`, o de una sola estación → esa propuesta; sin patrón
claro, como `Dresses` — 8 primavera-verano / 7 todo el año / 1 otoño-invierno — o como el
propio `Jackets` antes de decidirlo a mano → se deja el mapeo por `season` de Kaggle). El autor
confirmó casi todas las propuestas; solo corrigió `Caps` (de `estacional`, pese al 83% de sus
revisiones en `primavera_verano`, a `todo_el_ano`).

| `TIPOS_TODO_EL_ANO` (13) | `estacional` — mapeo por `season` (9 con datos de revisión + el resto sin revisar) |
|---|---|
| Jackets, Caps, Backpacks, Casual Shoes, Clutches, Formal Shoes, Heels, Jeans, Shirts, Sports Shoes, Sweaters, Track Pants, Trousers | Dresses, Flip Flops, Jumpsuit, Leggings, Sandals, Shorts, Skirts, Tops, Tshirts, y cualquier tipo no revisado |

## Campos descartados para v1

`material`, `estampado` y `fit` (§3.4): el parquet de Kaggle no tiene columnas para ninguno de
los tres, y el texto de `productDisplayName` no da señal fiable para inferirlos sin
heurísticas frágiles. Quedan fuera del esquema v1 por completo.
