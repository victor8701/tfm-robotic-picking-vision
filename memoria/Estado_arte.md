# Descripción Teórica del TFM
## Sistema Robótico Bimanual de Clasificación de Prendas con Arquitectura de Modos de Operación

**Autor:** Víctor Martín Parra  
**Máster:** Robótica y Automatización — UC3M (2025/2027)  
**Fecha:** agosto 2026  
**Versión:** 1.0 (documento vivo)

---

## Índice

1. [Introducción y motivación](#1-introducción-y-motivación)
2. [Descripción general del sistema](#2-descripción-general-del-sistema)
3. [Taxonomía de prendas](#3-taxonomía-de-prendas)
4. [Pipeline de visión por computador](#4-pipeline-de-visión-por-computador)
5. [App web de etiquetado SKU](#5-app-web-de-etiquetado-sku)
6. [Pipeline de tendencias de moda](#6-pipeline-de-tendencias-de-moda)
7. [Semantic matching: prenda ↔ tendencia](#7-semantic-matching-prenda--tendencia)
8. [Modo 3: Reposición geográfica](#8-modo-3-reposición-geográfica)
9. [Modo 5: Optimización multiobjetivo](#9-modo-5-optimización-multiobjetivo)
10. [Ejecución robótica](#10-ejecución-robótica)
11. [Métricas de evaluación](#11-métricas-de-evaluación)
12. [Estado del arte y bibliografía clave](#12-estado-del-arte-y-bibliografía-clave)
13. [Plan de trabajo](#13-plan-de-trabajo)
14. [Limitaciones y trabajo futuro](#14-limitaciones-y-trabajo-futuro)

---

## 1. Introducción y motivación

### 1.1 El reto de la logística en el fashion retail

La industria del fashion retail opera bajo una presión dual sin precedentes: por un lado, la aceleración de los ciclos de tendencia —impulsada por las redes sociales y la cultura del "outfit del día"— reduce la vida útil de un estilo de meses a semanas; por otro, la demanda de personalización geográfica exige que los mismos artículos de catálogo lleguen a mercados distintos con composiciones de pedido radicalmente diferentes.

Las plataformas como Inditex (Zara, Pull&Bear, Bershka, Massimo Dutti) gestionan almacenes con decenas de miles de referencias activas simultáneamente. El picking —la selección y extracción física de prendas para conformar pedidos— sigue siendo, en gran medida, una operación manual o semi-automatizada, dependiente de la habilidad del operario para interpretar órdenes de trabajo y localizar productos en el almacén.

Este trabajo propone cerrar dos brechas tecnológicas que coexisten en los centros de distribución modernos:

1. **La brecha IT ↔ OT**: Los departamentos de marketing monitorizan en tiempo real las tendencias en redes sociales y generan inteligencia de mercado (qué estilos están subiendo, qué mercados son más receptivos). Sin embargo, esa inteligencia no fluye de forma automática hacia las operaciones de almacén. El robot que hace picking no sabe —ni puede saber hoy— que esta semana en UK el urban minimalism en tonos pastel está siendo trending en TikTok.

2. **La brecha tipo-SKU en visión**: Los sistemas de clasificación de prendas actuales pueden identificar categorías generales (camiseta, pantalón, vestido), pero para tomar decisiones de picking basadas en tendencias se necesita conocer el SKU exacto y sus atributos (fit, material, estética, mercado destino). Identificar un SKU concreto a partir de una prenda doblada en una caja requiere un nivel de reconocimiento visual que va más allá de la clasificación por categoría.

### 1.2 Por qué robots colaborativos

La elección de cobots (robots colaborativos) frente a robots industriales clásicos responde a tres factores:

- **Flexibilidad en entornos desestructurados**: las prendas son objetos blandos, no rígidos, y su posición en la caja varía. Los cobots, combinados con visión y control de fuerza, se adaptan mejor a esta variabilidad que los robots industriales de trayectoria fija.
- **Coexistencia segura con humanos**: los almacenes de fashion retail son entornos mixtos; los cobots permiten que operarios y robots compartan espacio sin barreras físicas costosas.
- **Reconfigurabilidad**: cambiar la tarea de un cobot (por ejemplo, pasar de clasificar camisetas a clasificar calzado) implica únicamente una actualización software, no una re-ingeniería mecánica.

### 1.3 Hipótesis central del TFM

> **Un sistema robótico bimanual puede cerrar el bucle IT ↔ Middleware ↔ OT de forma completa: desde el análisis de tendencias de moda en redes sociales hasta la selección física de prendas en el almacén, usando modelos multimodales (CLIP) como puente semántico entre el lenguaje de la moda y la visión del robot.**

Esta hipótesis se valida mediante una arquitectura de cinco modos de operación progresivos, donde cada modo añade una capa de inteligencia sobre el anterior.

---

## 2. Descripción general del sistema

### 2.1 Arquitectura en tres capas

```
┌──────────────────────────────────────────────────────────────────┐
│                        IT  (Negocio)                             │
│  Marketing: clasifica el catálogo (ERP)                          │
│  LLM local (Qwen2.5) + Claude → tendencias reales                │
│  (YouTube/TikTok/X · GitHub Actions, sin intervención)           │
│  → JSON de tendencias  →  Aprobación operario (HMI)              │
└───────────────────────────────┬──────────────────────────────────┘
                                │ Trend DB (vectores CLIP)
┌───────────────────────────────▼──────────────────────────────────┐
│                  MIDDLEWARE  (ROS 2)                              │
│  ERP simulado (JSON de catálogo con embeddings CLIP)             │
│  YOLO → Catalog matching → SKU → CLIP cosine score → picking     │
└───────────────────────────────┬──────────────────────────────────┘
                                │ Coordenadas de picking
┌───────────────────────────────▼──────────────────────────────────┐
│                    OT  (Robots)                                   │
│  2× ABB GoFa (CRB 15000)  +  Cámara overhead RGB-D              │
│  2× Cámaras eye-in-hand   +  PLC Siemens (seguridad)            │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Los cinco modos de operación

| Modo | Nombre | Tecnología núcleo | Aportación |
|---|---|---|---|
| 1 | Vaciado geométrico | YOLO-obb + PCL | Singulación de cajas, depaletizado |
| 2 | Clasificación supervisada | YOLO (29 tipos) + Catalog matching | Identificación de tipo y SKU |
| 3 | Reposición geográfica | ERP JSON + filtrado por mercado | Picking orientado a demanda regional |
| 4 | Tendencias de mercado | LLM + CLIP + cosine similarity | Picking orientado a tendencias sociales |
| 5 | Gestión integral | Optimización multiobjetivo (M3+M4) | Cierre completo del bucle IT↔OT |

### 2.3 Hardware

| Componente | Modelo | Rol |
|---|---|---|
| Robot brazo 1 | ABB CRB 15000 GoFa (6-DOF) | Picking izquierdo |
| Robot brazo 2 | ABB CRB 15000 GoFa (6-DOF) | Picking derecho / asistencia bimanual |
| Cámara overhead | RGB-D (tipo Intel RealSense o similar) | Detección de cajas y prendas |
| Cámara eye-in-hand ×2 | RGB (montada en gripper) | Visual servoing para grasping preciso |
| PLC | Siemens S7 (TIA Portal) | Máquina de estados, seguridad, conteo |
| HMI | FlexPendant IRC5 (ABB) | Control de modos, tendencias, estado del operario |
| PC de procesamiento | GPU workstation (Linux) | Inferencia YOLO, CLIP, ROS 2 |

### 2.4 Software stack

| Capa | Tecnología |
|---|---|
| Middleware | ROS 2 (Humble o Iron) |
| Control robot | EGM (Externally Guided Motion, 250 Hz, C#) |
| Detección/clasificación | YOLOv8 / YOLOv11 (Python, PyTorch) |
| Catalog matching | CLIP (OpenAI, ViT-B/32 o ViT-L/14) |
| Nube de puntos | PCL (Point Cloud Library) |
| ERP simulado | JSON + Python/Node.js API |
| Trend Intelligence | Ollama (Qwen2.5, local) + Claude (`claude -p`, plan Pro/Max) — ver 6.1 |
| Orquestación autónoma | GitHub Actions (cron programado, sin intervención) — ver 6.6 |
| App etiquetado | HTML + JS + Node.js/Express |
| Dashboard HMI | FlexPendant IRC5 (ABB) con pantallas custom via ScreenMaker SDK |

---

## 3. Taxonomía de prendas

### 3.1 Criterios de diseño de la taxonomía

La taxonomía de prendas de este sistema debe satisfacer tres criterios simultáneamente:

1. **Distinguibilidad visual**: cada tipo debe ser reconocible desde una cámara overhead, incluso con la prenda parcialmente doblada. Los tipos que son visualmente indistinguibles en esa condición se colapsan en uno solo y la diferenciación se delega al catalog matching y al ERP.

2. **Relevancia para trend matching**: los tipos deben tener correspondencia con el vocabulario de tendencias (una tendencia "urban streetwear" hace referencia a tipos concretos de prenda; si esos tipos no existen en la taxonomía, el matching es imposible).

3. **Cobertura del portafolio Inditex**: la taxonomía cubre el rango de productos de las marcas principales del grupo (Zara, Pull&Bear, Bershka, Massimo Dutti, Stradivarius, Oysho en su vertiente de lifestyle).

### 3.2 Comparación con taxonomías del estado del arte

| Taxonomía | Año | Nº categorías | Atributos | Enfoque |
|---|---|---|---|---|
| DeepFashion | 2016 | 50 | 1.000+ | Clasificación + retrieval |
| iMaterialist | 2019 | 228 | Múltiples | Segmentación fine-grained |
| Fashionpedia | 2020 | 27 prendas + 294 atributos | Sí | Ontología completa |
| **Este TFM** | 2026 | **29 tipos YOLO** (9+3+2+4+6+5) | **10 dimensiones ERP** | **Robótica + trend matching** |

La diferencia clave respecto a taxonomías académicas: en este sistema la clasificación visual (YOLO) no necesita distinguir slim de baggy, chándal de traje, ni vestido de fiesta de vestido playero, porque esa información viene del ERP asociado al SKU. El robot no necesita "ver" el estilo de una prenda; necesita identificar el tipo genérico y el SKU exacto, y el ERP le dice el resto. Esta separación de responsabilidades se detalla en la sección 3.5.

### 3.3 Taxonomía principal — Tipos detectados por YOLO

La clasificación opera en dos niveles: YOLO clasifica el **tipo genérico** (29 clases: 9 superior + 3 inferior + 2 cuerpo entero + 4 abrigo + 6 calzado + 5 accesorios), y el catalog matching (CLIP) refina al **SKU exacto** dentro de ese tipo. El SKU exacto trae consigo, ya predefinidos en el ERP, todos los atributos de estilo, material y largo — YOLO nunca necesita clasificarlos directamente.

#### ROPA SUPERIOR (9 tipos)

| # | Tipo | Características visuales distinguibles |
|---|---|---|
| 1 | Camiseta manga corta | Manga corta visible; tela lisa/ligera |
| 2 | Camiseta de tirantes | Tiras finas; sin hombros cubiertos |
| 3 | Camiseta manga larga | Manga visible hasta la muñeca |
| 4 | Top | Prenda corta (hasta cintura); sin cuello definido |
| 5 | Camisa | Cuello con botones; tela más estructurada/rígida |
| 6 | Polo | Cuello tipo polo; tejido piqué texturizado |
| 7 | Sudadera | Volumen y grosor de tejido; con o sin capucha |
| 8 | Jersey | Tejido de punto visible; estructura entrelazada |
| 9 | Chaleco sin mangas | Sin mangas; puede ser de punto (textura) o acolchado (baffle lines) |

#### ROPA INFERIOR (3 tipos YOLO — largo, fit y material son atributos ERP)

| # | Tipo YOLO | Sub-tipos gestionados por ERP |
|---|---|---|
| 10 | Pantalón (incluye bermuda y short) | Vaquero · Lino · Pana · Traje · Chándal/Jogger · Cuero · Cargo · largo/bermuda/short |
| 11 | Falda | Mini · Midi · Maxi · Plisada · Lápiz · Vaquera |
| 12 | Legging / Malla | Básica · Cuero · Deportiva/técnica |

> **Justificación del colapso en 3 tipos**: cuando un pantalón está doblado en una caja, la diferencia visual entre un slim y un baggy es mínima y no fiable desde una cámara overhead, y lo mismo ocurre con el límite exacto entre un pantalón corto a la rodilla y uno un poco más largo. Denim vs. lino vs. chándal sí tiene señal visual clara (textura, color típico, grosor), pero esa señal se explota en el catalog matching (CLIP), no en la clasificación YOLO de primer nivel — YOLO solo necesita acotar el espacio de búsqueda a "es un pantalón". Por eso Short/Bermuda deja de ser un tipo YOLO independiente y pasa a ser, junto con el resto de sub-tipos, un atributo del SKU en el ERP. El ERP es la fuente de verdad para fit, material, largo y ocasión.

**Atributos de pantalón en ERP:**

| Atributo | Valores |
|---|---|
| Material | vaquero · lino · pana · tela de traje · chándal · cuero |
| Fit | skinny · slim · regular · baggy/oversize · palazzo/wide leg |
| Detalle | liso · con rotos · cargo (bolsillos laterales) |
| Género | femenino · masculino · neutro |
| **Largo** | **largo** (hasta el tobillo) · **bermuda** (a la rodilla; incluye variantes "capri"/"pescador") · **short** (muy corto, mayoritariamente femenino; incluye "hot pants") |
| Grupo de estilo | ver tabla unificada en 3.4 (Casual · Streetwear · De vestir · Fiesta/Noche · Deportivo · Playa/Resort) |

> El campo **Largo** sustituye la antigua distinción YOLO "Pantalón vs. Short/Bermuda": ahora es un único selector de 3 valores en el ERP, aplicable a cualquier pantalón con independencia de su material o estilo (un jogger puede ser largo o short; un vaquero puede ser largo, bermuda o short).

#### PRENDAS DE CUERPO ENTERO (2 tipos)

| # | Tipo | Características visuales |
|---|---|---|
| 13 | Vestido | Prenda superior+inferior en una pieza, sin perneras separadas |
| 14 | Mono | Prenda completa con perneras; tirantes o cremallera frontal visibles |

> El vestido y el mono se distinguen por un rasgo estructural fiable incluso doblados: la presencia o ausencia de perneras separadas. **El largo del vestido (antes Vestido corto/midi/largo) deja de ser una clase YOLO**: por decisión de diseño, ya no se usa el largo como criterio de taxonomía de vestidos. En su lugar, el vestido se caracteriza por su **Grupo de estilo** (atributo ERP, ver 3.4), que distingue por ejemplo un vestido de fiesta/noche (tejido con brillo, pedrería, silueta ajustada o de gala) de un vestido casual/playero tipo "sundress" (algodón o lino ligero, estampado floral, silueta suelta — pensado para playa, picnic o el día a día). Esta distinción de estilo tiene señal visual al menos tan fiable como el largo (tejido, brillo y estampado son perfectamente detectables con la prenda doblada), pero se modela como atributo ERP y no como clase YOLO porque el SKU exacto ya la fija de forma inequívoca: el catalog matching (CLIP) identifica el SKU concreto, y ese SKU trae consigo su grupo de estilo predefinido por marketing. Ver el flujo completo en 3.5.

#### ROPA DE ABRIGO (4 tipos)

| # | Tipo | Características visuales |
|---|---|---|
| 15 | Chaqueta | Prenda corta (hasta cadera); incluye vaquera, bomber, cuero, cortavientos |
| 16 | Americana | Estructura rígida con solapas; tela de traje; botonadura visible |
| 17 | Abrigo | Prenda larga (hasta rodilla o más); tejido grueso y pesado |
| 18 | Plumas | Compartimentos acolchados (baffle lines) visibles; relleno evidente |

> **Chubasquero eliminado como tipo YOLO** (catálogo físico reducido a 29 tipos, ver nota de alcance en 4.2): es un nicho poco relevante para el storytelling de tendencias del TFM y encarece desproporcionadamente el sourcing de SKUs de abrigo. Si aparece uno en el flujo real, cae dentro de "Chaqueta" (material impermeable como atributo ERP).

> La diferencia entre chaqueta vaquera, bomber y de cuero es de material y color, ambos detectables visualmente. El catalog matching los distingue sin necesidad de tipos YOLO separados; el material (y su Grupo de estilo asociado — p. ej. cuero → Streetwear, vaquera → Casual, cortavientos → Deportivo) es un atributo ERP, igual que en Pantalón. Ver mapeo completo en 3.4.

#### CALZADO (6 tipos)

| # | Tipo | Características visuales |
|---|---|---|
| 19 | Zapatillas deportivas | Suela gruesa con cámara de aire; perfil atletico |
| 20 | Zapatillas casual / lifestyle | Suela más fina; silueta más limpia; sin tecnología deportiva visible |
| 21 | Zapatos planos de vestir | Suela fina plana; punta cerrada; incluye bailarinas, mocasines, náuticos, oxford |
| 22 | Zapatos de tacón | Tacón visible (aguja, bloque o kitten heel) |
| 23 | Sandalias | Tira/correa; puntera o trasera abierta |
| 24 | Botas | Caña corta, media o alta (fusiona el antiguo tipo "Botines"); incluye cowboy, plataforma, lluvia y montaña/trekking |

> **Reducido de 9 a 6 tipos**: Chanclas/Slides y Plataformas/Cuñas eliminados (redundancia visual con Sandalias y Botas respectivamente), y Botines se fusiona dentro de Botas — la caña (corta/media/alta) pasa a ser matiz de catalog matching, no una distinción YOLO.

#### ACCESORIOS (5 tipos)

| # | Tipo | Características visuales |
|---|---|---|
| 25 | Bolso | Cuerpo definido; asa/correa; varios tamaños y formas |
| 26 | Riñonera / Belt bag | Cuerpo pequeño; clip o hebilla frontal |
| 27 | Cinturón | Tira plana y larga; hebilla en un extremo. Subtipos: cuero clásico · cuero ancho/corset · tela/lona · cadena · elástico · cuerda/trenzado |
| 28 | Bufanda / Pañuelo | Pieza textil larga/cuadrada sin forma definida rígida |
| 29 | Gorra / Gorro / Sombrero | Silueta de cubierta para la cabeza; visera o copa visible |

> **Reducido de 8 a 5 tipos**: Mochila eliminada (redundante con Bolso), Gafas de sol y Joyería eliminadas — no son prendas textiles y su enorme subvariedad interna (ver versión anterior de esta tabla) suponía mucho esfuerzo de etiquetado con poco retorno visual para el objetivo del TFM.

**Total: 29 tipos YOLO**

### 3.4 Atributos del ERP (dimensiones de metadato por SKU)

Estos atributos no son detectados por YOLO sino que vienen del catálogo, introducidos por **marketing** vía la app web de etiquetado (ver nota de roles en 3.5).

| Dimensión | Valores posibles |
|---|---|
| **Color primario** | blanco · negro · gris · beige · camel · navy · azul · rojo · verde · burdeos · rosa · lavanda · menta · amarillo · naranja · fucsia · dorado · plateado |
| **Estampado** | liso · rayas · cuadros vichy · floral · leopardo/animal print · tie-dye · geométrico · logo/lettering |
| **Material** | algodón · lino · seda/satén · terciopelo/velvet · cuero/vinilo · punto · denim · neopreno/técnico · tul/encaje · pana · tweed/bouclé · impermeable |
| **Fit** | skinny · slim · regular · relaxed · oversized · wide leg/palazzo · cropped · maxi |
| **Grupo de estilo** | Casual · Streetwear · De vestir · Fiesta/Noche · Deportivo · Playa/Resort *(sustituye a Ocasión + Estética, ver 3.4.1)* |
| **Temporada** | primavera-verano · otoño-invierno · todo el año |
| **Género** | femenino · masculino · neutro (nota: prendas masculinas pueden asignarse a cualquier género; prendas femeninas solo a femenino/neutro) |
| **Mercado destino** | Europa (mercado único por ahora) |

> Nota de pantalón: el atributo **Largo** (largo · bermuda · short, ver 3.3) es específico de las prendas de tipo Pantalón; el resto de dimensiones de esta tabla son transversales a todos los tipos.

#### 3.4.1 Grupo de estilo: campo unificado (sustituye a Ocasión + Estética)

Las versiones anteriores del ERP separaban **Ocasión** (deportivo/casual/vestir/fiesta) y **Estética** (minimalista/streetwear/romántico/retro/grunge/preppy/bohemio/Y2K/coastal), con solapamiento entre ambas y demasiado grano fino para ser útil en la práctica. Se sustituyen por un único campo, **Grupo de estilo**, con 6 valores mutuamente excluyentes pensados para ser lo bastante amplios como para agrupar de forma explícita los sub-tipos y materiales de cada categoría de prenda:

| Grupo de estilo | Descripción | Ejemplos de sub-tipo/material típico |
|---|---|---|
| **Casual** | Uso diario, sin connotación deportiva ni formal | Vaquero (denim) · pana · punto/tricot · camiseta lisa |
| **Streetwear** | Estética urbana, informal pero marcada | Chándal/jogger · cargo · sudadera oversize · chaqueta bomber/cuero · zapatillas lifestyle |
| **De vestir** | Formal, oficina, ceremonia no nocturna | Traje/tela de traje · americana · camisa estructurada · zapato de vestir |
| **Fiesta/Noche** | Eventos, salir de noche | Satén/seda con brillo · lentejuelas/pedrería · vestido de fiesta · tacón |
| **Deportivo** | Práctica deportiva o su estética | Tejido técnico/neopreno · legging deportivo · zapatilla deportiva |
| **Playa/Resort** | Playa, piscina, picnic, vacaciones | Lino · algodón ligero floral · vestido tipo "sundress" · sandalia/chancla |

**Mapeo orientativo material/sub-tipo → Grupo de estilo** (marketing puede sobreescribirlo por SKU si el corte concreto no sigue el patrón general):

| Sub-tipo / Material | Grupo de estilo por defecto | Tipos YOLO donde aplica |
|---|---|---|
| Chándal / jogger | Streetwear | Pantalón, Sudadera |
| Cargo | Streetwear | Pantalón |
| Cuero | Streetwear (salvo corte de vestir → De vestir) | Pantalón, Chaqueta, Falda, Legging, Cinturón |
| Vaquero / denim | Casual | Pantalón, Falda, Chaqueta |
| Pana | Casual | Pantalón |
| Lino | Playa/Resort | Pantalón, Camisa, Vestido |
| Tela de traje | De vestir | Pantalón, Americana |
| Satén/seda con brillo, pedrería | Fiesta/Noche | Vestido, Top |
| Algodón ligero + estampado floral | Playa/Resort | Vestido |
| Tejido técnico/neopreno | Deportivo | Legging, Chándal, Chubasquero deportivo |

Esta tabla es la respuesta operativa a "chándal → streetwear, traje → de vestir, vaquero → casual": el mapeo vive en el ERP (introducido o confirmado por marketing al etiquetar cada SKU), **no** se implementa como clases YOLO adicionales. YOLO solo necesita saber que la prenda es "un pantalón" o "una chaqueta"; qué tan formal, urbano o playero es ese pantalón concreto lo dice el ERP.

### 3.5 Flujo completo: qué ve YOLO, qué sabe el ERP, qué compara el LLM

Esta sección fija, sin ambigüedad, la responsabilidad de cada componente. Es la aclaración central de este apartado y responde directamente a la pregunta "¿cómo va a funcionar realmente el proceso del LLM y el YOLO?".

**Principio de diseño**: YOLO nunca necesita entender de moda. Su único trabajo es reducir el espacio de búsqueda para el catalog matching (CLIP), indicando el tipo genérico de prenda (uno de los 29). Toda la semántica de estilo, largo, material y ocasión vive en el ERP, fijada por marketing al dar de alta cada SKU. El LLM, a su vez, nunca ve una foto del robot ni del catálogo: solo analiza redes sociales y devuelve texto, que se traduce a las mismas categorías que ya existen en el ERP para que ambos lados sean comparables.

**Nota de roles — quién es quién en el bucle IT↔OT**: este TFM gira en torno a la conexión entre marketing y fábrica (ver 1.1), y esa conexión se concreta en dos personas distintas, no una sola. **Marketing** (oficina, IT) clasifica el catálogo por adelantado — da de alta cada SKU con su estilo, temporada, material — sin tocar nunca la planta. **El operario** (planta, OT) trabaja desde la pantalla del HMI y es quien dispara la operación en tiempo real: pide, por ejemplo, "ropa de verano de tal característica", y el robot busca físicamente entre los SKUs que marketing ya dejó clasificados. Las versiones anteriores de este documento atribuían el etiquetado del catálogo al "operario" — es una imprecisión ya corregida: etiquetar el catálogo es tarea de marketing; disparar/aprobar acciones desde el HMI de planta es tarea del operario (ver también 6.1 y 6.5).

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. YOLO (visión, sobre la prenda física en la caja)                  │
│    Entrada:  imagen overhead de la prenda doblada                    │
│    Salida:   tipo genérico (1 de 29) + bounding box + confianza      │
│    NO sabe:  ni largo, ni material, ni estilo, ni ocasión            │
│    Ejemplo:  "esto es un Pantalón" (no sabe si es vaquero o chándal) │
└───────────────────────────────┬────────────────────────────────────┘
                                │ acota la búsqueda a "Pantalones" del ERP
┌───────────────────────────────▼────────────────────────────────────┐
│ 2. Catalog matching — CLIP image encoder                             │
│    Entrada:  imagen overhead + tipo YOLO                             │
│    Salida:   SKU exacto (nearest neighbor en el subconjunto acotado) │
│    El SKU YA trae fijados en el ERP: color, material, largo,         │
│    fit, ocasión/temporada y Grupo de estilo — nada de esto se        │
│    "detecta"; se recupera de la ficha del SKU una vez identificado.  │
└───────────────────────────────┬────────────────────────────────────┘
                                │ SKU + atributos ERP completos
┌───────────────────────────────▼────────────────────────────────────┐
│ 3. LLM Trend Agent (offline, no ve prendas físicas)                  │
│    Entrada:  búsqueda web / redes sociales (Instagram, TikTok, ...)  │
│    Salida:   descripción en lenguaje natural + Grupo de estilo       │
│    inferido (usando el MISMO vocabulario de 6 valores que el ERP)    │
│    Ejemplo:  "el streetwear con pantalón cargo está en auge" →       │
│              grupo_estilo_detectado = ["Streetwear"]                 │
└───────────────────────────────┬────────────────────────────────────┘
                                │ vector CLIP-texto + grupo_estilo_detectado
┌───────────────────────────────▼────────────────────────────────────┐
│ 4. Semantic matching (sección 7)                                     │
│    Cruza cada SKU candidato con la tendencia activa en dos pasos:    │
│    a) filtro/boost categórico: ¿coincide el Grupo de estilo del SKU  │
│       con el grupo_estilo_detectado de la tendencia?                 │
│    b) score fino: similitud coseno CLIP entre v_prenda y v_tendencia │
│    El resultado combinado ordena los candidatos para el picking.     │
└─────────────────────────────────────────────────────────────────────┘
```

**Por qué esta separación y no otra**:
- YOLO con menos clases (29 en vez de intentar meter estilo/largo como clases) es más fácil de entrenar y más robusto: cada clase tiene una diferencia estructural clara (perneras sí/no, mangas sí/no, tacón sí/no), no una diferencia de "vibra" o corte que dependa del pliegue de la prenda en la caja.
- El ERP es la única fuente de verdad para todo lo que es decisión de catálogo (qué SKU es de qué estilo). Esto también es más mantenible: si una prenda se re-etiqueta de temporada, no hay que re-entrenar YOLO, solo editar el JSON del SKU en la app de etiquetado.
- El LLM y el ERP comparten vocabulario (el mismo listado de 6 grupos de estilo) precisamente para que el filtro categórico del paso 4a sea posible sin ambigüedad de sinónimos.

---

## 4. Pipeline de visión por computador

### 4.1 Modo 1 — Vaciado geométrico (Singulation)

**Objetivo**: detectar y separar cajas de cartón sobre una cinta transportadora o palé. Las cajas contienen prendas individuales y llegan en configuraciones variables (apiladas, giradas, superpuestas).

**Pipeline**:
```
Cámara RGB-D overhead
    │
    ▼
PCL: segmentación de plano + clustering euclidiano → nube de puntos por caja
    │
    ▼
YOLO-obb (oriented bounding boxes) → detección de cajas con orientación
    │
    ▼
Cálculo de pose 6D (posición XYZ + orientación) de cada caja
    │
    ▼
Publicación en ROS 2 → planificador de picking bimanual
```

**Salida**: lista de cajas con pose 6D y orden de extracción recomendado.

### 4.2 Modo 2 — Clasificación supervisada

**Objetivo**: identificar el tipo YOLO de la prenda dentro de cada caja (primer nivel de la jerarquía de la taxonomía).

**Condición de la prenda**: caja abierta, prenda doblada. Color y patrón son detectables. Fit y material solo parcialmente.

**Pipeline**:
```
Cámara overhead (imagen RGB del interior de la caja abierta)
    │
    ▼
YOLO v8/v11 (entrenado en 29 tipos genéricos) → tipo + bounding box + confianza
    │
    ▼
Si confianza < umbral → señal al operario para confirmación manual
    │
    ▼
Tipo YOLO confirmado → entrada al catalog matching
```

**Dataset de entrenamiento para YOLO**:
- Base: DeepFashion2, iMaterialist (imágenes de ropa en entornos variados)
- Dominio específico: fotos propias de prendas en caja con cámara overhead (capturadas durante el etiquetado con la app web)
- Augmentation: variaciones de iluminación, orientación, pliegue, oclusión parcial
- Etiquetado: la app web genera automáticamente los registros de tipo por SKU

### 4.3 Catalog matching — Identificación de SKU

**Objetivo**: dada la imagen overhead de una prenda y su tipo YOLO, identificar el SKU exacto dentro del catálogo.

**Motivación**: el tipo YOLO dice "esto es un Pantalón". El catalog matching dice "este pantalón específico es el SKU ZR-2025-PANT-BLK-S (Zara, pantalón vaquero slim negro talla S, para mercado ES/UK/FR)".

**Arquitectura de 2 niveles**:

```
Imagen overhead (prenda en caja)
    │
    ▼
YOLO → tipo = "Pantalón"  ← reduce el espacio de búsqueda a N_pantalones
    │
    ▼
ERP: recuperar todos los embeddings CLIP de "Pantalón" → índice vectorial parcial
    │
    ▼
CLIP image encoder (imagen overhead) → vector v_robot ∈ ℝ^512
    │
    ▼
Nearest neighbor: argmin cosine_distance(v_robot, v_catalogo_i) para i en Pantalones
    │
    ▼
SKU ganador + todos sus atributos del ERP
```

**Strategy de dataset — cómo reducir el esfuerzo de captura**:

La principal dificultad del catalog matching es el *domain gap*: las fotos de catálogo (prenda sobre modelo o maniquí, iluminación de estudio) tienen una distribución visual muy distinta a las imágenes del robot (prenda doblada en caja, iluminación industrial, cámara overhead).

CLIP, al haber sido entrenado con 400 millones de pares imagen-texto de Internet, tiene una representación semántica suficientemente rica para bridging este gap. La estrategia propuesta, en orden de coste creciente:

1. **Baseline elegido — prototipo few-shot por SKU (Opción C)**: en vez de comparar contra una única foto de catálogo tipo estudio, cada SKU se representa por el **promedio de los embeddings CLIP de sus 3-5 fotos propias** (capturadas con la cámara del robot, condición real de caja — ver 5.6), incluyendo variaciones de augmentation. Es una búsqueda por similitud (nearest neighbor), no una clasificación de N clases, así que escala de forma natural al tamaño real del catálogo (87-145 SKUs, ver 5.6) sin sufrir el problema estadístico de un clasificador entrenado con solo 3-5 ejemplos reales por clase. Añadir o quitar un SKU es solo editar el índice vectorial, no reentrenar nada — coherente con el principio de 3.5 ("no hay que re-entrenar YOLO, solo editar el JSON del SKU").
2. **Si Recall@5 < 80%**: entrenar una capa lineal ligera sobre los embeddings congelados de CLIP (no se reentrena CLIP entero, solo esta capa) usando las mismas fotos ya capturadas.
3. **Si sigue insuficiente**: fine-tuning completo de CLIP con pares (imagen_robot, imagen_catálogo) del mismo SKU. Se necesitarían ~50-100 pares por tipo de prenda (no por SKU), captados con la cámara del robot. Se descarta como baseline por ser el escalón más caro y menos escalable de los tres — se reserva como último recurso.

**Por qué no un clasificador dedicado por SKU (Opción B, descartada)**: con 87-145 SKUs y solo 3-5 fotos reales por SKU, entrenar un clasificador de 87-145 clases es un problema de *few-shot learning* frágil — con tan pocos ejemplos reales por clase (las copias aumentadas están correlacionadas entre sí, no son evidencia independiente), el riesgo de que el modelo memorice detalles incidentales de esas fotos concretas (pliegue exacto, luz del día de captura) en vez de la prenda es alto, y cada alta de SKU nuevo exigiría reentrenar el modelo completo. La búsqueda por similitud de la Opción C no tiene ninguna de las dos limitaciones.

**Alternativa de emergencia**: si el catalog matching no alcanza precisión operativa, se puede añadir una etiqueta QR/física en la caja. En ese caso, la visión solo valida y el QR da el SKU. Esta opción elimina la contribución investigadora del matching, por lo que se usa solo como fallback.

---

## 5. App web de etiquetado SKU

### 5.1 Propósito y rol en el sistema

La app web de etiquetado SKU es la herramienta con la que marketing (o el propio investigador durante la fase de desarrollo, asumiendo ese rol) **popula el ERP** con entradas de catálogo.

Su función específica:
- Asociar cada prenda del catálogo con su SKU + foto + atributos + embedding CLIP
- Generar el índice vectorial que usa el catalog matching en tiempo real

**No está relacionada con el entrenamiento de YOLO**. YOLO se entrena por separado con datasets públicos + imágenes propias etiquetadas por tipo, no por SKU.

### 5.2 Workflow de marketing

```
1. Cargar foto de la prenda (foto de catálogo o foto del robot)
2. Seleccionar tipo YOLO (dropdown: los 29 tipos genéricos)
3. Introducir atributos:
   - Color primario (selector de color)
   - Estampado (dropdown)
   - Material (dropdown)
   - Fit (dropdown)
   - Largo (dropdown: largo · bermuda · short — solo visible si tipo = Pantalón)
   - Grupo de estilo (dropdown: Casual · Streetwear · De vestir · Fiesta/Noche · Deportivo · Playa/Resort; preseleccionado según el mapeo de 3.4.1 a partir del Material, editable por marketing)
   - Temporada (multiselect)
   - Género (radio: femenino / masculino / neutro)
   - Mercado destino: Europa (fijo por ahora)
4. Introducir SKU (campo de texto libre)
5. Precio EUR (numérico)
6. Ubicación en almacén (pasillo + estante + posición)
7. Guardar → la app:
   a. Escribe la entrada en el ERP JSON
   b. Invoca el script Python de CLIP para calcular el embedding
   c. Actualiza el índice vectorial en memoria
```

### 5.3 Stack técnico

| Componente | Tecnología |
|---|---|
| Frontend | HTML + JavaScript (vanilla o React minimal) |
| Backend | Node.js + Express (ligero, local) |
| Base de datos | JSON plano (un archivo por tipo YOLO o uno global) |
| CLIP embeddings | Python script (invocado desde Express vía `child_process`) |
| Índice vectorial | JSON o formato `.npy` para los vectores |

### 5.4 Esquema del ERP JSON por SKU

```json
{
  "sku": "ZR-2025-PANT-BLK-S",
  "tipo_yolo": "Pantalón",
  "color_primario": "negro",
  "estampado": "liso",
  "material": "vaquero",
  "fit": "slim",
  "detalle": "liso",
  "largo": "largo",
  "grupo_estilo": "casual",
  "temporada": ["otoño", "invierno"],
  "genero": "neutro",
  "precio_eur": 39.99,
  "mercado_destino": "Europa",
  "stock": 87,
  "ubicacion_almacen": {
    "pasillo": "A",
    "estante": 2,
    "posicion": 5
  },
  "imagen_catalogo": "catalog/ZR-2025-PANT-BLK-S.jpg",
  "embedding_clip": [0.23, -0.11, 0.07, ...]
}
```

> El campo `largo` solo aplica a `tipo_yolo: "Pantalón"`; se omite (o queda `null`) en el resto de tipos. `grupo_estilo` es siempre uno de los 6 valores de 3.4.1.

### 5.5 Estructura de ficheros del ERP

```
erp/
├── catalog/              ← Fotos de producto (una por SKU)
│   ├── ZR-2025-PANT-BLK-S.jpg
│   └── ...
├── skus/
│   ├── pantalon.json     ← Todas las entradas de tipo "Pantalón"
│   ├── camiseta_mc.json
│   └── ...
├── index_vectorial/
│   ├── pantalon.npy      ← Matriz de embeddings CLIP por tipo
│   └── ...
└── erp_global.json       ← Consolidado de todos los SKUs
```

### 5.6 Estrategia de captura de catálogo

Con 29 tipos YOLO y un objetivo de 3-5 SKUs reales por tipo (ver 3.3), el catálogo necesario está en el rango **87-145 SKUs**. Comprar y montar en caja rígida esa cantidad de prendas para cada ciclo de picking robótico no es necesario ni realista para un TFM, así que se separan dos catálogos con requisitos distintos:

- **Catálogo fotografiado (87-145 SKUs)**: cubre todo el rango objetivo. De cada SKU solo se necesitan fotos — una en condición "catálogo" (fondo limpio) y 3-5 en condición "cámara del robot" (prenda doblada, luz industrial, vista cenital) — no hace falta que la prenda pase físicamente por el robot. Esto es lo que alimenta el catalog matching (Recall@K, sección 11.1) con volumen realista.
- **Hero set físico (~15-25 SKUs)**: subconjunto que sí se compra en firme, se mete en cajas rígidas de verdad y se usa en la demo robótica en vivo / vídeo del TFM.
- **Sourcing**: ropa de segunda mano "por kilo" (~10-12€/kg, bajo 1€/prenda de media) para abaratar el volumen del catálogo fotografiado; Vinted/Wallapop cuando se necesite cubrir un hueco concreto de la taxonomía; prendas prestadas (devueltas tras fotografiar) para tipos puntuales difíciles de encontrar de segunda mano (p. ej. Americana, Mono).
- **Balance entre Grupos de estilo**: al margen de cubrir los 29 tipos, conviene asegurar representación mínima en los 6 Grupos de estilo de 3.4.1 — un catálogo con muchas prendas "Casual" y casi ninguna "Fiesta/Noche" deja a ciertas tendencias detectadas sin apenas candidatos reales entre los que elegir (ver limitación en 14.3).

---

## 6. Pipeline de tendencias de moda

### 6.1 Trend Intelligence Agent

El agente de inteligencia de tendencias es un pipeline híbrido, no un único LLM, diseñado para que el análisis sea automatizado y basado en fuentes reales — no simulado ni ejecutado a mano:

| Pieza | Herramienta | Rol | Coste |
|---|---|---|---|
| Ingesta de contenido viral | Extensión propia de [`viral_clips`](https://github.com/victor8701/viral_clips) (ya desarrollada para YouTube, ampliada a TikTok y X/Twitter) | Descarga/recorta clips virales de moda desde las tres fuentes | $0 |
| Transcripción | Whisper (OpenAI, MIT License, local) | Convierte el audio de los clips a texto | $0 |
| Clasificación mecánica | Ollama + Qwen2.5 (Apache 2.0, local) | Tareas estructuradas: extraer *tags* de estilo, mapear a los 6 Grupos de estilo del ERP | $0 |
| Síntesis final de tendencia | Claude, vía `claude -p` (Claude Code CLI, plan Pro/Max ya contratado por el investigador) | Redacta la descripción en lenguaje natural y el Trend JSON final (tarea que exige más matiz que un modelo de 3-7B) | $0 marginal (uso incluido en la suscripción ya pagada) |

Se descartó Llama 3.1 como modelo local en favor de Qwen2.5 por licencia: Llama usa la [Community License de Meta](https://www.llama.com/llama3_1/license/) (uso comercial permitido pero con restricciones — no competir con productos de Meta, no usar sus salidas para entrenar otros modelos), mientras que Qwen2.5 es [Apache 2.0](https://huggingface.co/Qwen/Qwen2.5-7B/blob/main/LICENSE), sin restricciones, más acorde con el requisito de poder editar el pipeline libremente. Como alternativas de respaldo en la nube (gratuitas pero no locales, para picos de carga o si el hardware local no está disponible) se documentan Groq (free tier: 30 req/min, 6.000 tokens/min, 14.400 req/día, sin tarjeta) y Google AI Studio / Gemini (free tier: del orden de 1.000-1.500 req/día, sin tarjeta, con el matiz de que activar facturación en el proyecto elimina el nivel gratis).

**Características clave**:
- Corre **offline** (no en tiempo real durante el picking)
- Se ejecuta **de forma autónoma, sin intervención humana**, orquestado vía GitHub Actions — ver 6.6
- Los resultados quedan en estado "pendiente" hasta que el operario los aprueba desde el HMI de planta (ver nota de roles en 3.5: aprobar/disparar desde el HMI es tarea del operario, no de marketing)
- Solo tras la aprobación se actualizan los vectores de tendencia usados en picking

### 6.2 Parámetros de entrada (HMI)

El operario configura los siguientes parámetros antes de ejecutar el análisis:

| Parámetro | Opciones |
|---|---|
| Mercado geográfico | Europa (único mercado por ahora; ampliable a regiones en el futuro) |
| Género objetivo | Femenino · Masculino · Todo |
| Tipo de prenda | Ropa superior · Inferior · Calzado · Accesorios · Todo |
| Fuentes | YouTube · TikTok · X/Twitter (vía `viral_clips`, ver 6.1) · Todas |

### 6.3 Prompt generado dinámicamente

```
Analiza las tendencias de moda actuales en Europa, con foco en [TIPO_PRENDA] 
para el género [GÉNERO]. Fuentes principales: [FUENTES].
Fecha de análisis: [FECHA].

Describe en lenguaje natural (máximo 250 palabras) qué estilos, colores, 
siluetas, materiales y estéticas están dominando. Menciona eventos virales, 
lanzamientos de colecciones o figuras públicas que estén impulsando las 
tendencias detectadas. Usa vocabulario de moda preciso (ej: "coastal grandmother 
aesthetic", "mob wife", "quiet luxury", "Y2K revival", "gorpcore").

Clasifica además la tendencia dentro de uno o varios de estos 6 grupos de estilo 
(el mismo vocabulario usado en el catálogo — no uses otros valores): 
Casual · Streetwear · De vestir · Fiesta/Noche · Deportivo · Playa/Resort.

Asigna una puntuación de intensidad de 0.0 a 1.0 donde 1.0 indica tendencia 
masiva y viral, y 0.0 indica señal débil o residual.
```

### 6.4 Output del LLM — Trend JSON

```json
{
  "mercado": "Europa",
  "genero_objetivo": "femenino",
  "tipo_prenda": "Ropa superior",
  "fuentes": ["Instagram", "TikTok"],
  "fecha_analisis": "2026-10-12",
  "descripcion": "Este mes en Europa, el urban minimalism domina en moda femenina. 
    Las sudaderas oversized en tonos neutros (gris pizarra, beige, off-white) 
    están siendo impulsadas por cuentas de estética 'clean girl' y 'quiet luxury'. 
    El detalle de la semana es la sudadera con cuello alto integrado, vista en 
    varias figuras de reality shows. Las camisetas gráficas con tipografía 
    vintage (fuentes serifas lavadas) también están subiendo, posiblemente 
    vinculado al aniversario de lanzamientos de música indie de los 2000. 
    Colores secundarios en ascenso: azul slate y verde sage.",
  "grupo_estilo_detectado": ["Streetwear", "Casual"],
  "intensidad": 0.78,
  "estado": "pendiente"
}
```

> `grupo_estilo_detectado` usa el mismo vocabulario de 6 valores que el campo `grupo_estilo` del ERP (3.4.1). Es la pieza que permite al Modo 4 filtrar/potenciar candidatos por coincidencia categórica de estilo antes (o además) de aplicar el score semántico CLIP — ver 7.2.

### 6.5 Flujo de aprobación

```
LLM ejecuta análisis
    │
    ▼
Trend JSON guardado en trends/pending/{fecha}_{mercado}_{segmento}.json
    │
    ▼
HMI muestra alerta: "Nueva tendencia disponible para revisión"
    │
    ▼
Operario lee la descripción y evalúa si es coherente con el negocio
    │
    ├── RECHAZA → archivo se mueve a trends/rejected/ (sin efecto)
    │
    └── APRUEBA → 
            CLIP text encoder procesa el campo "descripcion"
            → vector almacenado en trends/active/{archivo}.json
            → índice vectorial de tendencias activas actualizado
            → picking comienza a usar el nuevo vector
```

### 6.6 Ejecución autónoma (GitHub Actions)

Un requisito explícito de diseño es que el pipeline de tendencias (6.1) corra **sin que el investigador tenga que dejar su portátil encendido ni intervenir manualmente** — de noche, en background, de forma repetible. La pieza que lo permite es un *workflow* de GitHub Actions programado con un trigger `cron`, en vez de depender de que el hardware local del investigador esté despierto:

- El *workflow* corre en los servidores de GitHub, no en el portátil del investigador — el ordenador puede estar apagado.
- El token de larga duración de Claude Code (`CLAUDE_CODE_OAUTH_TOKEN`, ya contemplado en el `README` de `viral_clips` para uso sin login repetido) se guarda como secreto cifrado del repositorio, permitiendo que `claude -p` se invoque de forma desatendida dentro del *workflow*.
- El *runner* gratuito de GitHub Actions no tiene GPU, así que Ollama + Qwen2.5 corren en CPU — asumible porque el análisis es un batch offline de una vez al día/semana, no una inferencia en tiempo real.
- Coste: minutos ilimitados en repositorios públicos; 2.000 minutos/mes gratis en repositorios privados — muy por encima de lo que consume una ejecución diaria corta.
- **Dos límites a vigilar**: el trigger `cron` tiene un intervalo mínimo de 5 minutos (irrelevante para una ejecución diaria) y, en repositorios públicos, GitHub **desactiva el schedule en silencio tras 60 días sin ningún commit** en el repo — un riesgo real si hay temporadas del TFM sin tocar el código, que conviene vigilar en la pestaña Actions del repositorio.

---

## 7. Semantic matching: prenda ↔ tendencia

### 7.1 El espacio compartido de CLIP

CLIP (Contrastive Language-Image Pretraining, Radford et al., 2021) aprende una representación vectorial compartida para imágenes y texto. Tras el entrenamiento con 400M pares imagen-texto, objetos visualmente similares a una descripción textual tienen vectores cercanos en el espacio de embeddings.

En este sistema se explotan dos encoders de CLIP:
- **Image encoder**: transforma la foto de catálogo de un SKU en un vector `v_prenda ∈ ℝ^512`
- **Text encoder**: transforma la descripción de tendencia del LLM en un vector `v_tendencia ∈ ℝ^512`

Ambos vectores coexisten en el mismo espacio, lo que permite medir su similitud semántica directamente.

### 7.2 Cálculo del score de matching

El score combina dos señales complementarias: una **categórica** (Grupo de estilo, sección 3.4.1) y una **semántica** (similitud CLIP):

```
score_semantico(SKU, tendencia) = cosine_similarity(v_prenda_SKU, v_tendencia)
                                = (v_prenda · v_tendencia) / (||v_prenda|| · ||v_tendencia||)
                                ∈ [-1, 1]

boost_estilo(SKU, tendencia) = 1.0  si SKU.grupo_estilo ∈ tendencia.grupo_estilo_detectado
                              = 0.0  en caso contrario

score(SKU, tendencia) = score_semantico(SKU, tendencia) + β · boost_estilo(SKU, tendencia)
```

`β` es un peso experimental (estimación inicial: 0.1) que favorece a los SKUs cuyo Grupo de estilo coincide explícitamente con el que el LLM detectó como tendencia, sin descartar el resto — el score semántico sigue siendo la señal principal y captura matices que el grupo categórico no distingue (p. ej. dos SKUs "Casual" con distinta afinidad a "minimalismo urbano"). En la práctica, los scores semánticos relevantes suelen estar en el rango [0.1, 0.4] para CLIP. Se establecerá un umbral experimental `θ` (estimación inicial: 0.20 sobre `score_semantico`) por debajo del cual un SKU se considera "no alineado" con la tendencia, independientemente del boost de estilo.

### 7.3 Pre-computación y caché

Para que el matching sea en tiempo real durante el picking, los embeddings se pre-computan:

- **v_prenda_SKU**: calculado al insertar cada SKU en el ERP (app de etiquetado). Se almacena en el campo `embedding_clip` del JSON y en el índice vectorial por tipo.
- **v_tendencia**: calculado cuando el operario aprueba una nueva tendencia. Se almacena en `trends/active/`.

En picking, solo se hace la operación de producto punto, que es O(N×D) con N = número de SKUs del tipo y D = 512. Muy rápido.

### 7.4 Manejo de múltiples tendencias simultáneas

En producción habrá varias tendencias activas (distintos mercados, distintos segmentos, distintas semanas). El score final agrega todas las tendencias relevantes para el pedido en curso:

```python
BETA_BOOST_ESTILO = 0.1

def score_multitrend(sku, pedido, tendencias_activas):
    relevantes = [t for t in tendencias_activas
                  if t.tipo_prenda in (pedido.tipo_prenda, "Todo")
                  and (t.genero_objetivo == sku.genero or t.genero_objetivo == "Todo")]
    
    if not relevantes:
        return 0.0
    
    def score_tendencia(t):
        score_semantico = cosine_sim(sku.embedding, t.vector)
        boost = BETA_BOOST_ESTILO if sku.grupo_estilo in t.grupo_estilo_detectado else 0.0
        return score_semantico + boost
    
    numerador = sum(t.intensidad * score_tendencia(t) for t in relevantes)
    denominador = sum(t.intensidad for t in relevantes)
    
    return numerador / denominador
```

### 7.5 Casos borde y limitaciones

| Caso | Comportamiento |
|---|---|
| Sin tendencias activas para el mercado del pedido | Fallback: clasificación por tipo + mayor stock |
| Score máximo por debajo de θ para todos los SKUs | Fallback: ordenar por proximidad en almacén (minimizar distancia de recorrido) |
| Dos tendencias contradictorias del mismo mercado | La de mayor intensidad × recencia pondera más |
| CLIP falla al encodear texto muy largo | Truncar a 77 tokens (límite de CLIP) → describir de forma más concisa |

---

## 8. Modo 3: Reposición geográfica

### 8.1 Descripción del modo

El Modo 3 introduce inteligencia de mercado basada en datos de demanda geográfica estructurada, en contraposición al Modo 4 (que usa señales no estructuradas de redes sociales).

**Escenario típico**: el sistema recibe un pedido de 50 unidades para el mercado UK. El pedido no especifica qué prendas, solo el mercado destino y la cantidad. El Modo 3 selecciona los SKUs cuyo campo `mercado_destino` incluye "UK" y que tienen stock disponible.

### 8.2 ERP como fuente de verdad geográfica

Cada SKU tiene un campo `mercado_destino` que indica en qué mercados está aprobado para venta. Este campo es introducido por marketing en la app de etiquetado y puede reflejar:
- Regulaciones locales (tallas, etiquetado)
- Adecuación cultural (estética, colores)
- Acuerdos comerciales (exclusividades)

### 8.3 Lógica de filtrado

```python
def filtrar_por_mercado(inventory, pedido):
    return [sku for sku in inventory
            if pedido.mercado in sku.mercado_destino
            and sku.stock >= 1]
```

La lista resultante es la entrada al Modo 4 (si está activo) o directamente al planificador de picking (si el sistema corre en Modo 3 puro).

---

## 9. Modo 5: Optimización multiobjetivo

### 9.1 Descripción del modo

El Modo 5 combina los Modos 3 y 4: primero filtra por mercado geográfico (Modo 3) y luego ordena los candidatos por score de alineamiento con tendencias (Modo 4). La demanda geográfica actúa como restricción dura; la tendencia actúa como función de ordenación blanda.

### 9.2 Pipeline completo

```python
def modo_5_picking(pedido, inventory, tendencias_activas, erp):
    
    # Restricción dura: mercado geográfico
    candidatos = filtrar_por_mercado(inventory, pedido)
    
    # Función de score: alineamiento con tendencias
    for sku in candidatos:
        sku.trend_score = score_multitrend(sku, pedido, tendencias_activas)
    
    # Ordenación por score descendente
    candidatos.sort(key=lambda s: s.trend_score, reverse=True)
    
    # Selección de los N SKUs del pedido
    picking_list = candidatos[:pedido.cantidad]
    
    # Generación de coordenadas de picking para el robot
    return [(sku, erp.get_coordenadas(sku)) for sku in picking_list]
```

### 9.3 Extensiones futuras del Modo 5

- **Balance de stock**: penalizar SKUs con stock muy bajo para evitar ruptura
- **Diversidad de selección**: si todos los top-N son del mismo tipo, diversificar
- **Urgencia temporal**: priorizar prendas de temporada cuya ventana de venta se cierra

---

## 10. Ejecución robótica

### 10.1 ROS 2 como middleware

ROS 2 (Robot Operating System 2) actúa como el sistema nervioso del sistema. Todos los módulos (visión, ERP, LLM, planificador, control de robot) se comunican a través del bus de mensajes de ROS 2 (DDS — Data Distribution Service).

**Nodos ROS 2 principales**:

| Nodo | Función |
|---|---|
| `camera_node` | Publica imágenes de la cámara overhead y eye-in-hand |
| `yolo_node` | Suscribe a imágenes, publica detecciones de tipo de prenda |
| `catalog_matcher_node` | Suscribe a detecciones, publica SKU identificado |
| `erp_node` | Servidor de la base de datos de catálogo; responde a queries por SKU |
| `trend_node` | Gestiona el índice de tendencias activas; calcula scores |
| `planner_node` | Recibe pedido → genera lista de picking ordenada → publica goals |
| `egm_node` | Traduce goals de picking en comandos EGM para los ABB GoFa |
| `hmi_node` | Interfaz con la pantalla HMI; gestiona comandos del operario |

### 10.2 Control de robot: EGM

EGM (Externally Guided Motion) es el protocolo de ABB para control de movimiento externo a 250 Hz vía UDP. Permite enviar consignas de posición/velocidad desde un nodo externo (en este caso, el PC de procesamiento con ROS 2) al controlador del robot en tiempo real.

**Flujo de control**:
```
Planner → coordenadas 6D (XYZ + RPY) del picking goal
    │
    ▼
EGM node (C# o Python) → envía consigna de posición vía UDP a IRC5
    │
    ▼
ABB GoFa ejecuta movimiento → feedback de posición actual a 250 Hz
    │
    ▼
Visual servoing node ajusta la consigna según la posición real de la prenda
```

### 10.3 Visual servoing (eye-in-hand)

Para el agarre preciso de la prenda, el gripper de cada robot lleva una cámara que permite ajustar la posición de agarre en tiempo real (Image-Based Visual Servoing, IBVS).

**Pipeline**:
```
Cámara eye-in-hand → imagen en tiempo real
    │
    ▼
Detección del punto de agarre óptimo (centroide de la prenda visible)
    │
    ▼
Error en imagen (píxeles) → controlador IBVS → corrección de velocidad del robot
    │
    ▼
Convergencia → señal de "listo para agarrar" → cierre del gripper
```

### 10.4 Planificación bimanual

El picking bimanual permite procesar dos prendas en paralelo (un robot por brazo) cuando la configuración del pedido lo permite. El planificador asigna prendas a cada brazo según:
- Proximidad física de las cajas en el almacén
- Evitación de colisiones entre brazos
- Balanceo de carga entre los dos GoFa

---

## 11. Métricas de evaluación

### 11.1 Métricas por componente

| Componente | Métrica | Descripción | Objetivo |
|---|---|---|---|
| YOLO clasificación | mAP@0.5 | Precisión media en los 29 tipos | > 0.85 |
| YOLO clasificación | Accuracy por clase | Por tipo YOLO por separado | Identificar clases débiles |
| Catalog matching | Recall@1 | SKU correcto es el top-1 | > 0.60 |
| Catalog matching | Recall@5 | SKU correcto está en el top-5 | > 0.85 |
| Trend matching | Precision@K | De K seleccionados, cuántos son tendencia | > 0.70 |
| Trend matching | NDCG@K | Calidad del ranking de K candidatos | > 0.75 |
| Picking robótica | Pick success rate | % picks sin fallo mecánico | > 0.90 |
| Picking robótica | Cycle time (s) | Tiempo detección → depósito | < 8 s/prenda |
| Sistema (M4) | E2E latency (picking) | Pedido → robot en movimiento | < 2 s |
| Sistema (M4) | E2E latency (tendencias) | Disparo LLM → vectores activos | < 60 s |

### 11.2 Evaluación cualitativa del pipeline de tendencias

La evaluación cuantitativa del trend matching es compleja porque no existe un ground truth objetivo (¿cuál es la prenda "correctamente" alineada con una tendencia?). Se propone una evaluación mixta:

1. **Test A/B con juicio humano**: dado un conjunto de prendas y una descripción de tendencia, ¿el sistema selecciona las mismas que seleccionaría un experto en moda?
2. **Coherencia interna**: si la tendencia es "quiet luxury en tonos neutros", ¿el sistema puntúa alto a jerséis beige slim y bajo a camisetas neón?
3. **Estabilidad temporal**: si la misma tendencia se ejecuta en dos semanas consecutivas, ¿los scores son estables?

---

## 12. Estado del arte y bibliografía clave

### 12.1 Robótica colaborativa en intralogística fashion

La automatización de almacenes en retail textil es un campo en expansión. Empresas como Ocado (UK) y AutoStore han desarrollado sistemas de almacenamiento y recuperación automáticos (AS/RS), pero orientados a cajas estándar rígidas, no a prendas en cajas variadas.

La manipulación de textiles (deformable object manipulation) es un problema abierto en robótica. Los robots industriales clásicos (KUKA, Fanuc) no están optimizados para la variabilidad geométrica de las prendas. Los cobots como el ABB GoFa, con control de fuerza integrado, se adaptan mejor.

**Referencias clave**:
- Sanchez et al. (2018). "Robotic manipulation and sensing of deformable objects in domestic and industrial applications". *International Journal of Robotics Research*.
- Lui et al. (2023). "A survey on textile manipulation for robotic systems". *IEEE Transactions on Automation Science*.

### 12.2 Clasificación de prendas con visión por computador

El campo tiene hitos bien establecidos:

- **DeepFashion** (Liu et al., 2016): dataset de 800K imágenes con 50 categorías y 1000+ atributos. Primer benchmark de referencia para retrieval y clasificación de moda.
- **DeepFashion2** (Ge et al., 2019): 491K pares de imágenes para retrieval comercial.
- **iMaterialist** (Guo et al., 2019): 228 categorías, orientado a segmentación fine-grained. Datset oficial del challenge de Kaggle.
- **Fashionpedia** (Jia et al., 2020): ontología de 27 categorías de prenda + 19 partes del cuerpo + 294 atributos. Anotación más completa disponible.

Para entornos industriales con prendas dobladas, no existe un dataset específico. Este TFM crea el primero de su tipo (prenda doblada en caja, cámara overhead industrial).

### 12.3 Modelos multimodales: CLIP y más allá

- **CLIP** (Radford et al., 2021): "Learning Transferable Visual Models From Natural Language Supervision". OpenAI. Entrenado con 400M pares imagen-texto de Internet. Zero-shot classification y retrieval de referencia.
- **Grounding DINO** (Liu et al., 2023): detection con lenguaje natural. Alternativa a YOLO para detección zero-shot. Útil si no hay datos suficientes para entrenar YOLO.
- **ALIGN** (Jia et al., 2021): modelo similar a CLIP de Google, entrenado con 1.8B pares.
- **FashionCLIP** (Chia et al., 2022): fine-tuning de CLIP específicamente en datos de e-commerce de moda. Potencialmente más preciso para este dominio.

### 12.4 Análisis de tendencias de moda mediante IA

La predicción de tendencias de moda (fashion trend forecasting) es un área emergente:

- **WGSN**: servicio comercial de predicción de tendencias basado en análisis de redes sociales, búsquedas, ventas y runway reports. Referencia del sector.
- **Fashion-MNIST** (Xiao et al., 2017): benchmark clásico de clasificación de prendas (10 clases, imágenes en escala de grises). Demasiado simple para los objetivos de este TFM.
- **Trend forecasting con NLP**: análisis de hashtags de Instagram y Pinterest para detectar tendencias emergentes. Trabajos de investigación de NYU Fashion Lab y MIT Media Lab.
- **LLM como oráculos de tendencia**: uso de modelos de lenguaje (GPT-4, Claude) con acceso a web para generar resúmenes de tendencias. Novedad de 2023-2024 sin publicaciones académicas formales aún.

### 12.5 Integración IT/OT en entornos industriales

- **OPC-UA**: estándar de comunicación IT/OT ampliamente usado en automatización industrial.
- **ROS 2 en industria**: ROS 2 está ganando tracción como capa middleware para integrar IT (Python, APIs, web) con OT (PLCs, cobots). ABB GoFa tiene soporte oficial de ROS 2.
- **Industry 4.0 / Cyber-Physical Systems (CPS)**: marco conceptual que describe exactamente el tipo de integración IT↔OT que este TFM implementa.
- **EGM en cobots ABB**: protocolo propietario ABB para control externo en tiempo real. Documentado en ABB Application Manual EGM.

---

## 13. Plan de trabajo

### 13.1 Condiciones

- **Período**: agosto 2026 — julio 2027
- **Horas disponibles**: ~8 horas/semana (promedio) a partir de octubre 2026
- **Fase teórica**: agosto — septiembre 2026 (redacción, estado del arte, definición de arquitectura)
- **Fase de implementación**: octubre 2026 — junio 2027
- **Defensa**: julio 2027

### 13.2 Gantt mensual

| Mes | Semanas | Horas est. | Fase | Entregables / Hitos |
|---|---|---|---|---|
| Ago 2026 | 4 | Teórica | Teórica | Este documento · Estado del arte literatura |
| Sep 2026 | 4 | Teórica | Teórica | Taxonomía definitiva · Diseño ERP JSON · Diseño app web |
| Oct 2026 | 4 | ~32h | Infraestructura | ROS 2 setup · Bridge EGM · Conexión PLC Siemens |
| Nov 2026 | 4 | ~32h | Modo 1 | YOLO-obb detección de cajas · PCL singulation funcional |
| Dic 2026 | 4 | ~32h | Modo 2 + App | YOLO 29 tipos entrenado · App web etiquetado SKU v1 |
| Ene 2027 | 4 | ~32h | Catalog matching | CLIP zero-shot baseline · Recall@K medido · Augmentation |
| Feb 2027 | 4 | ~32h | Modo 3 | ERP JSON completo · Filtrado geográfico funcional |
| Mar 2027 | 4 | ~32h | Trend pipeline | LLM agent · CLIP vectorización · HMI tendencias v1 |
| Abr 2027 | 4 | ~32h | Modo 4 | Trend matching → picking · Demo Modo 4 funcional |
| May 2027 | 4 | ~32h | Modo 5 + VS | Optimización M3+M4 · Visual servoing eye-in-hand |
| Jun 2027 | 4 | ~32h | Evaluación | Tests E2E · Métricas completas · Análisis de resultados |
| Jul 2027 | 4 | ~32h | Redacción | Memoria TFM final · Preparación defensa |

**Total horas de implementación estimadas**: ~320h (10 meses × ~32h/mes)

### 13.3 Dependencias críticas

```
Infraestructura (ROS 2 + EGM)
    │
    ├── Modo 1 (detección de cajas)
    │       │
    │       └── Modo 2 (clasificación de tipo)
    │               │
    │               └── Catalog matching (identificación de SKU)
    │                       │
    │                       ├── Modo 3 (reposición geográfica)
    │                       │
    │                       └── Modo 4 (tendencias)  ← requiere también Trend pipeline
    │                               │
    │                               └── Modo 5 (multiobjetivo)
    │
    App web (ERP) ──────────────────────────────────────────────┘
    (puede desarrollarse en paralelo con Modo 1)
    
    Trend pipeline ──────────────────────────────────────────────┐
    (puede desarrollarse en paralelo con Catalog matching)       │
                                                                 └── Modo 4
```

### 13.4 Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| CLIP zero-shot no alcanza Recall@5 > 80% | Media | Alto | Fine-tuning con augmentation; fallback a QR como emergencia |
| Integración EGM inestable | Baja | Alto | Comenzar con velocidades bajas; usar modo supervisor |
| Dataset YOLO insuficiente para tipos raros | Media | Medio | Combinar DeepFashion + sintético + oversampling |
| `viral_clips` no cubre suficiente volumen de contenido de moda al ampliarlo a TikTok/X | Media | Medio | Complementar con búsqueda web (Tavily/DuckDuckGo) como fuente adicional |
| GitHub Actions desactiva el cron tras 60 días sin commits (repos públicos) | Baja | Medio | Vigilar la pestaña Actions; commit trivial periódico si hay temporada sin tocar el repo |
| Tiempo insuficiente para Modo 5 | Media | Medio | Modo 5 como extensión del Modo 4; priorizar Modos 1-4 |

---

## 14. Limitaciones y trabajo futuro

Esta sección documenta, de forma honesta, tres puntos débiles del diseño identificados durante la propia definición de la arquitectura — no son fallos descubiertos a posteriori, sino límites conscientemente aceptados por tratarse de un TFM, con su implicación si el sistema se llevase a un entorno de producción real.

### 14.1 Vocabulario de estilo compartido: un acoplamiento frágil

El filtro categórico del matching (7.2) depende de que el LLM Trend Agent devuelva **siempre** uno exacto de los 6 valores de Grupo de estilo del ERP (3.4.1). Si el modelo devuelve un valor fuera de esa lista — más probable con un modelo local pequeño (Qwen2.5, 3-7B) que con Claude — el boost categórico del paso 4a de 3.5 se desactiva en silencio para esa tendencia, sin lanzar ningún error: el sistema sigue funcionando solo con el score semántico, degradado sin aviso. Mitigación propuesta: validar la salida del LLM contra la lista cerrada de 6 valores antes de aceptar el Trend JSON, con reintento si no coincide exactamente.

### 14.2 Etiquetado manual del catálogo: consistencia y escala

El Grupo de estilo de cada SKU lo asigna una persona a mano (marketing, ver 3.5) al dar de alta el producto. Etiquetando en solitario 87-145 SKUs (5.6), existe riesgo real de deriva de criterio entre los primeros y los últimos SKU etiquetados. Mitigación para el TFM: fijar una guía de etiquetado por escrito antes de empezar a etiquetar, no sobre la marcha.

**Trabajo futuro**: explorar etiquetado asistido por LLM — dado el SKU (o una foto de la prenda), el modelo busca el producto en internet y propone automáticamente Grupo de estilo, material y estampado, quedando marketing solo para confirmar/corregir. Se deja fuera del alcance de este TFM porque complicaría significativamente el proyecto (fiabilidad de la búsqueda, verificación de que el producto encontrado es el correcto, coste adicional de LLM por SKU) sin ser el foco de la contribución investigadora, que es el razonamiento semántico tendencia↔prenda, no la automatización del etiquetado en sí.

### 14.3 Balance del catálogo entre Grupos de estilo

El catálogo (grupo_estilo por SKU) es prácticamente estático una vez etiquetado, mientras que la tendencia detectada por el Modo 4 es dinámica. Si el catálogo queda desequilibrado entre los 6 Grupos de estilo de 3.4.1 (por ejemplo, mucha ropa "Casual" y poca "Fiesta/Noche", un riesgo real al comprar de segunda mano sin más criterio que el precio), una tendencia detectada en un grupo infrarrepresentado tendrá pocos candidatos reales entre los que el sistema pueda elegir. Para el alcance de este TFM se acepta esta limitación — el catálogo de 87-145 SKUs no pretende ser representativo de un inventario real de Inditex. En un despliegue de producción real, esto se resolvería con una estrategia activa de reposición de catálogo por Grupo de estilo (comprar/dar de alta deliberadamente donde el catálogo esté infrarrepresentado), que añadiría una capa de gestión de inventario fuera del alcance de este trabajo.

---

*Documento vivo — actualizar con cada decisión de diseño relevante durante el desarrollo.*
