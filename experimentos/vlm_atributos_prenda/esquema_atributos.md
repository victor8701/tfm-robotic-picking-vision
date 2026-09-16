# Esquema de atributos v1 — clasificador de prendas desde foto

Fuente de verdad de las tablas de mapeo `dataset Kaggle → esquema de esta tesis`, usadas por
`herramientas/preparar_dataset_florence2.py`. Reutiliza y colapsa campos que ya existen en
`memoria/Estado_arte.md` §3.3/§3.4 — no es un esquema inventado desde cero (mismo espíritu que
el paper "Fashion Florence", que colapsa las 228 etiquetas de iMaterialist a un puñado de
campos compactos).

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

## `grupo_estilo` (§3.4.1, los 6 valores)

Reutiliza tal cual la lógica ya validada en `poblar_muestras_dataset.py` (`CATEGORIAS` dict),
generalizada de "filtro con tope por carpeta" a "función de clasificación por fila". Limitación
ya conocida y documentada: `usage == "Party"` solo tiene 18 filas en las 44k — insuficiente
para aprender `fiesta_noche` de esa señal sola, así que se mantiene la heurística ya usada
(`Dresses + Heels + Clutches + Jumpsuit → fiesta_noche`). Es la misma clase que ya salió peor
parada en la evaluación de CLIP zero-shot (0% de acierto); es razonable esperar que siga
siendo la más débil también aquí.

## `genero` (§3.4)

| Kaggle `gender` | → `genero` |
|---|---|
| Men | masculino |
| Women | femenino |
| Unisex | neutro |
| Boys, Girls | *excluido* (ropa infantil, fuera de alcance) |

## `temporada` (§3.4, versión de 3 valores)

| Kaggle `season` | → `temporada` |
|---|---|
| Summer, Spring | primavera_verano |
| Fall, Winter | otono_invierno |

El tercer valor de §3.4 (`todo_el_año`) no es aprendible de una foto individual — se deja en
el vocabulario de salida por si en el futuro hace falta, pero no se genera como etiqueta de
entrenamiento.

## Campos descartados para v1

`material`, `estampado` y `fit` (§3.4): el parquet de Kaggle no tiene columnas para ninguno de
los tres, y el texto de `productDisplayName` no da señal fiable para inferirlos sin
heurísticas frágiles. Quedan fuera del esquema v1 por completo.
