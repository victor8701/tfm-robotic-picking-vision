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
│  LLM (Claude Pro + web search)                                   │
│  → Análisis de tendencias por mercado/segmento                   │
│  → JSON de tendencias  →  Aprobación operario (HMI)             │
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
| 2 | Clasificación supervisada | YOLO (39 tipos) + Catalog matching | Identificación de tipo y SKU |
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
| Trend Intelligence | Claude API (Anthropic) con web search |
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
| **Este TFM** | 2026 | **39 tipos YOLO** (9+4+4+5+9+8) | **9 dimensiones ERP** | **Robótica + trend matching** |

La diferencia clave respecto a taxonomías académicas: en este sistema la clasificación visual (YOLO) no necesita distinguir slim de baggy porque esa información viene del ERP asociado al SKU. El robot no necesita "ver" si un pantalón es palazzo o cargo; necesita identificar el SKU y el ERP le dice el resto.

### 3.3 Taxonomía principal — Tipos detectados por YOLO

La clasificación opera en dos niveles: YOLO clasifica el **tipo** (39 clases: 9 superior + 4 inferior + 4 cuerpo entero + 5 abrigo + 9 calzado + 8 accesorios), y el catalog matching refina al **SKU exacto** dentro de ese tipo.

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

#### ROPA INFERIOR (4 tipos YOLO — el fit/material es atributo ERP)

| # | Tipo YOLO | Sub-tipos gestionados por ERP |
|---|---|---|
| 10 | Pantalón | Vaquero · Lino · Pana · Traje · Chándal/Jogger · Cuero · Cargo |
| 11 | Short / Bermuda | Vaquero corto · Tela · Deportivo |
| 12 | Falda | Mini · Midi · Maxi · Plisada · Lápiz · Vaquera |
| 13 | Legging / Malla | Básica · Cuero · Deportiva/técnica |

> **Justificación del colapso en 4 tipos**: cuando un pantalón está doblado en una caja, la diferencia visual entre un slim y un baggy es mínima y no fiable desde una cámara overhead. Sin embargo, denim vs. lino vs. chándal sí tiene señal visual (textura, color típico, grosor). Esta señal visual contribuye al catalog matching, no a la clasificación YOLO de primer nivel. El ERP es la fuente de verdad para fit, material y ocasión.

**Atributos de pantalón en ERP:**

| Atributo | Valores |
|---|---|
| Material | vaquero · lino · pana · tela de traje · chándal · cuero |
| Fit | skinny · slim · regular · baggy/oversize · palazzo/wide leg |
| Detalle | liso · con rotos · cargo (bolsillos laterales) |
| Ocasión | deportivo · casual · vestir |
| Género | femenino · masculino · neutro |
| Largo | largo · medium (bermuda/tobillero) · shorts (corto, principalmente femenino) |

#### PRENDAS DE CUERPO ENTERO (4 tipos)

| # | Tipo | Características visuales |
|---|---|---|
| 14 | Vestido corto | Prenda superior+inferior en una pieza; longitud hasta muslo |
| 15 | Vestido midi | Longitud entre rodilla y media pantorrilla |
| 16 | Vestido largo | Longitud hasta el tobillo o el suelo |
| 17 | Mono | Prenda completa con perneras; tirantes o cremallera frontal visibles |

> Los tres tipos de vestido son distinguibles incluso con la prenda doblada: la longitud total de tejido es una señal visual fiable. El mono se distingue del vestido por la presencia de perneras separadas.

#### ROPA DE ABRIGO (5 tipos)

| # | Tipo | Características visuales |
|---|---|---|
| 18 | Chaqueta | Prenda corta (hasta cadera); incluye vaquera, bomber, cuero, cortavientos |
| 19 | Americana | Estructura rígida con solapas; tela de traje; botonadura visible |
| 20 | Abrigo | Prenda larga (hasta rodilla o más); tejido grueso y pesado |
| 21 | Plumas | Compartimentos acolchados (baffle lines) visibles; relleno evidente |
| 22 | Chubasquero | Material impermeable (brillo característico); capucha frecuentemente visible |

> La diferencia entre chaqueta vaquera, bomber y de cuero es de material y color, ambos detectables visualmente. El catalog matching los distingue sin necesidad de tipos YOLO separados.

#### CALZADO (9 tipos)

| # | Tipo | Características visuales |
|---|---|---|
| 23 | Zapatillas deportivas | Suela gruesa con cámara de aire; perfil atletico |
| 24 | Zapatillas casual / lifestyle | Suela más fina; silueta más limpia; sin tecnología deportiva visible |
| 25 | Zapatos planos de vestir | Suela fina plana; punta cerrada; incluye bailarinas, mocasines, náuticos, oxford |
| 26 | Zapatos de tacón | Tacón visible (aguja, bloque o kitten heel) |
| 27 | Sandalias | Tira/correa; puntera o trasera abierta |
| 28 | Chanclas / Slides | Banda única o doble; suela plana; sin cierre trasero |
| 29 | Botines | Caña corta (hasta tobillo); cierre lateral o frontal |
| 30 | Botas | Caña media o alta; incluye cowboy, plataforma, lluvia y montaña/trekking |
| 31 | Plataformas / Cuñas | Suela muy gruesa y sólida; elevación uniforme |

#### ACCESORIOS (8 tipos)

| # | Tipo | Características visuales |
|---|---|---|
| 32 | Bolso | Cuerpo definido; asa/correa; varios tamaños y formas |
| 33 | Mochila | Correas traseras; forma trapezoidal; mayor volumen |
| 34 | Riñonera / Belt bag | Cuerpo pequeño; clip o hebilla frontal |
| 35 | Cinturón | Tira plana y larga; hebilla en un extremo. Subtipos: cuero clásico · cuero ancho/corset · tela/lona · cadena · elástico · cuerda/trenzado |
| 36 | Bufanda / Pañuelo | Pieza textil larga/cuadrada sin forma definida rígida |
| 37 | Gorra / Gorro / Sombrero | Silueta de cubierta para la cabeza; visera o copa visible |
| 38 | Gafas de sol | Montura con dos lentes; patillas laterales. Subtipos: aviador/piloto · cuadradas/oversized · redondas · cat-eye · rectangulares/finas · wrap/deportivas |
| 39 | Joyería | Piezas pequeñas metálicas/decorativas. Subtipos: cadena chunky oro · cadena chunky plata · cadena fina/delicada · collar statement · gargantilla (choker) · pulsera cadena · pulsera fina · pendientes aro grandes · pendientes pequeños/studs |

**Total: 39 tipos YOLO**

### 3.4 Atributos del ERP (dimensiones de metadato por SKU)

Estos atributos no son detectados por YOLO sino que vienen del catálogo, introducidos por el operario vía la app web de etiquetado.

| Dimensión | Valores posibles |
|---|---|
| **Color primario** | blanco · negro · gris · beige · camel · navy · azul · rojo · verde · burdeos · rosa · lavanda · menta · amarillo · naranja · fucsia · dorado · plateado |
| **Estampado** | liso · rayas · cuadros vichy · floral · leopardo/animal print · tie-dye · geométrico · logo/lettering |
| **Material** | algodón · lino · seda/satén · terciopelo/velvet · cuero/vinilo · punto · denim · neopreno/técnico · tul/encaje · pana · tweed/bouclé · impermeable |
| **Fit** | skinny · slim · regular · relaxed · oversized · wide leg/palazzo · cropped · maxi |
| **Ocasión** | deportivo · casual · vestir · fiesta/evento |
| **Temporada** | primavera-verano · otoño-invierno · todo el año |
| **Estética** | minimalista · streetwear/urbano · romántico · retro/vintage · grunge · preppy · bohemio · Y2K · coastal/resort |
| **Género** | femenino · masculino · neutro (nota: prendas masculinas pueden asignarse a cualquier género; prendas femeninas solo a femenino/neutro) |
| **Mercado destino** | Europa (mercado único por ahora) |

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
YOLO v8/v11 (entrenado en 39 tipos) → tipo + bounding box + confianza
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

CLIP, al haber sido entrenado con 400 millones de pares imagen-texto de Internet, tiene una representación semántica suficientemente rica para bridging este gap en modo zero-shot. La estrategia propuesta:

1. **Fase zero-shot (baseline)**: usar directamente las fotos de catálogo sin ningún entrenamiento adicional. Medir Recall@1 y Recall@5.
2. **Si Recall@5 < 80%**: añadir augmentation sobre las fotos de catálogo (simular pliegues, rotaciones, zooms, cambios de iluminación) y repetir.
3. **Si sigue insuficiente**: fine-tuning de CLIP con pares (imagen_robot, imagen_catálogo) del mismo SKU. Se necesitarían ~50-100 pares por tipo de prenda (no por SKU), captados con la cámara del robot.

**Alternativa de emergencia**: si el catalog matching no alcanza precisión operativa, se puede añadir una etiqueta QR/física en la caja. En ese caso, la visión solo valida y el QR da el SKU. Esta opción elimina la contribución investigadora del matching, por lo que se usa solo como fallback.

---

## 5. App web de etiquetado SKU

### 5.1 Propósito y rol en el sistema

La app web de etiquetado SKU es la herramienta con la que el operario (o el propio investigador durante la fase de desarrollo) **popula el ERP** con entradas de catálogo.

Su función específica:
- Asociar cada prenda del catálogo con su SKU + foto + atributos + embedding CLIP
- Generar el índice vectorial que usa el catalog matching en tiempo real

**No está relacionada con el entrenamiento de YOLO**. YOLO se entrena por separado con datasets públicos + imágenes propias etiquetadas por tipo, no por SKU.

### 5.2 Workflow del operario

```
1. Cargar foto de la prenda (foto de catálogo o foto del robot)
2. Seleccionar tipo YOLO (dropdown: los 39 tipos)
3. Introducir atributos:
   - Color primario (selector de color)
   - Estampado (dropdown)
   - Material (dropdown)
   - Fit (dropdown)
   - Ocasión (dropdown)
   - Estética (multiselect)
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
  "ocasion": "casual",
  "estetica": ["minimalista", "streetwear"],
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

---

## 6. Pipeline de tendencias de moda

### 6.1 Trend Intelligence Agent

El agente de inteligencia de tendencias es un LLM (Claude Pro, cuenta del investigador, con web search habilitado) que analiza las redes sociales y genera descripciones en lenguaje natural de las tendencias de moda activas por mercado y segmento.

**Características clave**:
- Corre **offline** (no en tiempo real durante el picking)
- Disparado por el operario desde el HMI o por un timer periódico (diario/semanal)
- Los resultados quedan en estado "pendiente" hasta que el operario los aprueba desde el HMI
- Solo tras la aprobación se actualizan los vectores de tendencia usados en picking

### 6.2 Parámetros de entrada (HMI)

El operario configura los siguientes parámetros antes de ejecutar el análisis:

| Parámetro | Opciones |
|---|---|
| Mercado geográfico | Europa (único mercado por ahora; ampliable a regiones en el futuro) |
| Género objetivo | Femenino · Masculino · Todo |
| Tipo de prenda | Ropa superior · Inferior · Calzado · Accesorios · Todo |
| Fuentes | Instagram · TikTok · Pinterest · X/Twitter · Vogue/prensa · Todas |

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
  "intensidad": 0.78,
  "estado": "pendiente"
}
```

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

---

## 7. Semantic matching: prenda ↔ tendencia

### 7.1 El espacio compartido de CLIP

CLIP (Contrastive Language-Image Pretraining, Radford et al., 2021) aprende una representación vectorial compartida para imágenes y texto. Tras el entrenamiento con 400M pares imagen-texto, objetos visualmente similares a una descripción textual tienen vectores cercanos en el espacio de embeddings.

En este sistema se explotan dos encoders de CLIP:
- **Image encoder**: transforma la foto de catálogo de un SKU en un vector `v_prenda ∈ ℝ^512`
- **Text encoder**: transforma la descripción de tendencia del LLM en un vector `v_tendencia ∈ ℝ^512`

Ambos vectores coexisten en el mismo espacio, lo que permite medir su similitud semántica directamente.

### 7.2 Cálculo del score de matching

```
score(SKU, tendencia) = cosine_similarity(v_prenda_SKU, v_tendencia)
                      = (v_prenda · v_tendencia) / (||v_prenda|| · ||v_tendencia||)
                      ∈ [-1, 1]
```

En la práctica, los scores relevantes suelen estar en el rango [0.1, 0.4] para CLIP. Se establecerá un umbral experimental `θ` (estimación inicial: 0.20) por debajo del cual un SKU se considera "no alineado" con la tendencia.

### 7.3 Pre-computación y caché

Para que el matching sea en tiempo real durante el picking, los embeddings se pre-computan:

- **v_prenda_SKU**: calculado al insertar cada SKU en el ERP (app de etiquetado). Se almacena en el campo `embedding_clip` del JSON y en el índice vectorial por tipo.
- **v_tendencia**: calculado cuando el operario aprueba una nueva tendencia. Se almacena en `trends/active/`.

En picking, solo se hace la operación de producto punto, que es O(N×D) con N = número de SKUs del tipo y D = 512. Muy rápido.

### 7.4 Manejo de múltiples tendencias simultáneas

En producción habrá varias tendencias activas (distintos mercados, distintos segmentos, distintas semanas). El score final agrega todas las tendencias relevantes para el pedido en curso:

```python
def score_multitrend(sku, pedido, tendencias_activas):
    relevantes = [t for t in tendencias_activas
                  if t.tipo_prenda in (pedido.tipo_prenda, "Todo")
                  and (t.genero_objetivo == sku.genero or t.genero_objetivo == "Todo")]
    
    if not relevantes:
        return 0.0
    
    numerador = sum(t.intensidad * cosine_sim(sku.embedding, t.vector)
                    for t in relevantes)
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

Cada SKU tiene un campo `mercado_destino` que indica en qué mercados está aprobado para venta. Este campo es introducido por el operario en la app de etiquetado y puede reflejar:
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
| YOLO clasificación | mAP@0.5 | Precisión media en los 39 tipos | > 0.85 |
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
| Dic 2026 | 4 | ~32h | Modo 2 + App | YOLO 39 tipos entrenado · App web etiquetado SKU v1 |
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
| Acceso a web limitado en LLM | Baja | Medio | Alternativa: Perplexity API; o dataset estático de tendencias |
| Tiempo insuficiente para Modo 5 | Media | Medio | Modo 5 como extensión del Modo 4; priorizar Modos 1-4 |

---

*Documento vivo — actualizar con cada decisión de diseño relevante durante el desarrollo.*
