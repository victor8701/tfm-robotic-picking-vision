# Instagram como fuente de fotos de referentes: qué se probó, qué funciona y qué cuesta

**Autor:** Víctor Martín Parra, con el asistente · **Fecha:** 24-25 de octubre de 2026 · **Estado:** abierto (lectura montada y medida; 68 cuentas elegidas por Víctor el 25-oct, 14 leídas por Windsor durante la prueba; clave `WINDSOR_API_KEY` puesta por él el 25-oct por la tarde, pendiente de comprobar con la primera pasada del lunes 26)
**Código y datos:** `experimentos/analisis_mercado/tendencia_prenda.py` (fuente `instagram`), `test_instagram_fuente.py`, `NUBE.md` (sección «Instagram como fuente»), `diario_feed_instagram/` (lecturas del feed a mano asistida). **No toca** `Estado_arte.md`.
**Relacionados:** `TFM_tendencias_de_prenda.md` §6.11 («el cuello de botella es el acceso a los datos»), `TFM_estado_actual.md`.

## Resumen

Instagram es donde publican la mayoría de los referentes de cada estilo, pero Meta no deja leer sus fotos sin una API aprobada. Se montó la **vía oficial** (Business Discovery de Meta a través del conector `instagram_public` de Windsor, plan de prueba gratuito de 30 días): de 16 cuentas candidatas **se leen 10** (las otras 6 son cuentas personales o con el @ mal escrito); de cada publicación llegan la foto (con dirección de descarga que **caduca a los ~5 días**), el enlace, la fecha, los likes y los comentarios. El rendimiento depende mucho de la cuenta: en 90 días, **148 fotos de una marca (`gucci`) y 40 de un cantante muy activo (`kidcudi`), pero 0-9 de los demás famosos** (1-3 fotos al mes). Conclusión de diseño: elegir las cuentas por cuántos outfits publican, no por su fama, y contar con un cupo de cuentas de pago (75 cuentas = 23 US$/mes en Windsor) o con una app propia de Meta (gratis, sin tope, más pasos).

**Resultado de la primera noche completa (24-25 de octubre):** se midieron **75 cuentas candidatas** (71 se leen, 4 sin probar; otras 13 son personales, inactivas o con el @ mal escrito) y se eligió una propuesta de **14 cuentas** (el tope de la prueba) que cubre **12 de las 14 casillas** estilo × mercado y aportaría unas **74 fotos nuevas por semana, de las que la puerta «persona con ropa» acepta ≈ 60** (§3.3). La puerta deja pasar el 77 % de 189 fotos reales (146). Lo que no se consigue por esta vía: **geek España** (los streamers españoles publican casi solo vídeo y los hashtags en español solo traen tiendas pequeñas latinoamericanas) y **old money España**. La lectura del feed «Para ti» y de hashtags con el navegador (solo lectura, ~170 navegaciones, sin avisos de Instagram) sirvió para descubrir cuentas y para un radar cualitativo por estilo (§5.1), pero es estable solo en lo cualitativo (§5.2).

## 1. Vías evaluadas

| Vía | Qué da | Por qué sí / no |
|---|---|---|
| **Windsor, conector `instagram_public`** (Business Discovery de Meta) | Fotos, likes y comentarios de cuentas profesionales cuyo @ ya conocemos | **Elegida.** Oficial, sin scraping, un toque de autorización. No descubre cuentas ni hashtags; solo cuentas Creador/Empresa; cupo de pago |
| App propia de Meta con Business Discovery (`instagram_prueba.py`) | Lo mismo, gratis y sin tope de cuentas | Alternativa (más pasos: app de desarrollador, token de larga duración que hay que renovar) |
| Plugins con datos no oficiales (Manifold; skills con Apify o Xpoz) | Descubren cuentas y hashtags | Descartados como fuente de datos (no documentan de dónde sacan lo de Instagram; fotos de personas; estabilidad y normas). Valen, como mucho, para *proponer* @ que luego se comprueban por la vía oficial |
| Lectura del feed y de hashtags a mano asistida | Qué se ve y quién lo publica | Cualitativo y personalizado; sirve para descubrir cuentas y contrastar, no para medir cuotas (ver §5) |

## 2. Qué hizo falta para que funcionara (y lo que falló)

1. La cuenta del proyecto tiene que ser **profesional** (Creador/Empresa) y estar **enlazada a una página de Facebook**. Sin ese enlace, el paso «Grant Instagram Public Access» de Windsor decía «No Facebook Page was granted» y no registraba ninguna cuenta, aunque la cuenta de Instagram ya estuviera conectada para estadísticas propias (conector `instagram`, que **no** sirve: solo lee la cuenta propia).
2. En un portátil con sesión de Facebook de un usuario de la UE aparecía además una pantalla obligatoria de consentimiento («con anuncios o sin anuncios por suscripción») que bloquea los inicios de sesión con Facebook hasta que la contesta el usuario.
3. Al conectar, Windsor deja activado «Write actions» (permite a un asistente publicar y comentar). No se necesita ni se usa.
4. Las altas de cuentas a leer («Account to follow») se hacen en la página de Windsor, una por una. Esa página se atasca tras varias altas y bajas seguidas y deja de guardar sin avisar (basta recargarla); y Windsor descarta solas, sin mensaje, las cuentas que no puede leer, así que hay que comprobar la lista de cuentas después de cada tanda. Los @ escritos de memoria fallan a menudo (`ibai` es `ibaillanos`, `boxlunch` es `boxlunchgifts`): los de las «cuentas similares» de Instagram son exactos.

## 3. Lo medido (24 de octubre, plan de prueba)

- **Se leen:** `playboicarti`, `travisscott`, `gucci`, `tamara_falco`, `bycalitos`, `kidcudi`, `asaprocky`, `lilpeep`, `rojuu`, `shodamonkas`. **No se leen:** `quevedo`, `orslok`, `jacobelordi`, `dieworkwear`, `soyunapringada`, `casareal`.
- **Fotos (imagen + carrusel) en 90 días:** `gucci` 148, `kidcudi` 40, `tamara_falco` 9, `asaprocky` 5, `lilpeep` 5, `shodamonkas` 5, `bycalitos` 4, `rojuu` 3, `travisscott` 3, `playboicarti` 0 (≈ 74 al mes con las diez).
- **Descarga:** las direcciones `media_url` de imágenes y carruseles se bajan bien (comprobado con una petición de 1 KB); las de vídeo son .mp4 y para esos casos se usa la miniatura.
- **Orden de magnitud:** con ~60 cuentas elegidas por rendimiento y un tope de 8 fotos nuevas por cuenta y semana, la fuente aportaría del orden de varios cientos de fotos al mes, frente a las ~980 de la primera tanda grande de X, Reddit y prensa (que acumula varios meses).

### 3.1 Prueba de extremo a extremo con datos reales (25 de octubre de 2026)

Con 14 cuentas de la lista (marcas, modelos, creadoras y medios) se bajaron las fotos de los últimos 14 días con el propio código de la tarea semanal (`instagram_registros`, tope de 6 por cuenta) y se pasó la puerta «persona con ropa» (CLIP):
**76 fotos bajadas, 0 fallos de descarga (29 s), 57 aceptadas (75 %), 18 sin persona y 1 repetida** (16 s de puerta, un solo hilo). Aceptadas por cuenta: `gucci` 6/6, `budrys.jr` 6/6, `tim.conlin` 5/6, `rebecamomeg` 5/6, `irmastyle` 5/6, `mararuizj` 4/5, `kidcudi` 4/6, `britishcountryheritage` 4/6, `moritz_hau` 4/6, `fabric_ofthe_universe` 3/4, `florianmacek` 3/5, `raquelcanas` 3/6, `therake` 3/6, `tamara_falco` 2/2. Los descartes son sobre todo prendas sueltas, fotos de producto o capturas con texto.

**Marcas de Inditex (contexto del TFM), misma prueba:** `zara` 22 publicaciones en 14 días (13 carruseles), `bershka` 18 (10), `massimodutti` 16 (10), `pullandbear` 13 (10); de 32 fotos bajadas, **27 (84 %) pasan la puerta** (`zara` y `bershka` 8/8, `massimodutti` 6/8, `pullandbear` 5/8). Son las fuentes de Instagram con más fotos de colección con modelos y de mercado español.

**Ritmo en 90 días con 14 de las cuentas** (publicaciones por semana; entre paréntesis, carruseles+imágenes de las 90): `gucci` 13,5 (148 de 174), `ralphlauren` 12,7 (108 de 163), `zara` 10,2 (87 de 131), `raquelcanas` 9,5 (6 de 122: casi todo vídeo), `bershka` 7,9 (53 de 102), `britishcountryheritage` 7,0 (90 de 90), `massimodutti` 6,9 (64 de 89), `rebecamomeg` 5,8 (10 de 74), `pullandbear` 5,4 (58 de 70), `hm` 5,4 (30 de 70), `hackettlondon` 4,6 (40 de 59), `oxfordandchino` 2,8 (36 de 36), `georginagio` 2,8 (17 de 36), `therake` 2,5 (25 de 32). **En total, unas 60 fotos (carruseles e imágenes) y 37 miniaturas de vídeo por semana**; con el tope de 8 fotos nuevas por cuenta y semana y el 75-84 % que pasa la puerta, la tarea semanal sumaría del orden de **50-65 fotos útiles por semana con estas 14 cuentas** (unas 1 500 en una temporada de 6 meses), frente a las ~980 de la primera tanda grande de X, Reddit y prensa.

**Qué publica cada tipo de cuenta (14 días):** las creadoras españolas de moda publican sobre todo **reels** (`rebecamomeg` 14 vídeos de 17 publicaciones, `raquelcanas` 13 de 14, `vickymartinberrocal` 22 de 23; de los vídeos solo se aprovecha la miniatura); `britishcountryheritage` publica **14 carruseles en 14 días** (todos con foto); las marcas (`gucci`) mezclan carruseles e imágenes. El conector da una fila por publicación: del carrusel llega solo la portada, no sus fotos interiores.

**Descubrimiento de cuentas con las «cuentas similares» de Instagram** (un clic en el icono junto a «Seguir», solo lectura): desde `rebecamomeg` y `raquelcanas` salen otras 18 creadoras españolas de moda con categoría de cuenta profesional; desde `britishcountryheritage`, `oxfordandchino` y `budrys.jr`, medios y modelos de estilo clásico; desde `gucci`, otras marcas de lujo. La **categoría que aparece bajo el nombre** (Creador digital, Personaje público, Blog personal, Modelo, Estilista…) es un buen indicador de que la cuenta es profesional y, por tanto, legible por Business Discovery. Lista completa y medidas en `experimentos/analisis_mercado/diario_feed_instagram/candidatos_instagram.tsv`.

### 3.2 Segunda tanda de pruebas: cubrir las casillas sin datos (25 de octubre de 2026)

La primera propuesta de 14 cuentas no tenía ninguna del estilo **geek**, que es la casilla más corta de la tubería (2 fotos en España y 0 en EEUU), ni de «convencional EEUU» ni de «bohemio España». Se dieron de alta en Windsor otras 26 cuentas conocidas (tiendas, marcas y streamers de cada estilo, @ escritos de memoria) y se midió su ritmo en los últimos 14 días: **se leen 21 y no se leen 5** (`ibai` —el @ bueno es `ibaillanos`—, `koi`, `elganso`, `pedrodelhierro`, `xokas14`; Windsor las descarta sin avisar). `boxlunch` tampoco existe con ese @: el bueno es `boxlunchgifts`, que sí se lee.

| Cuenta | Casilla | Publicaciones en 14 días | Fotos por semana (carruseles + imágenes) | Seguidores | Pasan la puerta |
|---|---|---|---|---|---|
| `hottopic` | geek EEUU | 37 (18 carruseles, 8 imágenes, 11 vídeos) | 13 | 4,0 M | 8/12 |
| `killstar` | geek EEUU | 25 (12 carruseles, 13 vídeos) | 6 | 1,9 M | 11/11 |
| `dollskill` | geek EEUU | 20 (9 carruseles, 1 imagen, 10 vídeos) | 5 | 3,4 M | 4/6 |
| `g2esports` | geek (esports, en inglés) | 24 (9 carruseles, 15 vídeos) | 4,5 | 1,4 M | 5/8 |
| `barbour` | old money | 18 (9 carruseles, 2 imágenes, 7 vídeos) | 5,5 | 1,3 M | 5/5 |
| `bimbaylola` | bohemio España | 13 (9 carruseles, 3 imágenes, 1 vídeo) | 6 | 2,3 M | 5/9 |
| `desigual` | bohemio España | 7 (4 carruseles, 3 vídeos) | 2 | 1,9 M | 2/2 |
| `abercrombie` | convencional EEUU | 8 (7 carruseles, 1 vídeo) | 3,5 | 5,0 M | 4/5 |
| `loewe` | lujo España | 8 (6 carruseles, 1 imagen, 1 vídeo) | 3,5 | 6,9 M | 1/3 |
| `boxlunchgifts` | geek EEUU | 17 (9 carruseles, 3 imágenes, 5 vídeos) | 6 | 1,0 M | 5/8 |
| `stradivarius` | urbano España | 15 (8 carruseles, 7 vídeos) | 4 | 8,5 M | 6/6 |
| `mango` | convencional España | 6 (3 carruseles, 3 vídeos) | 1,5 | 15,7 M | 2/2 |
| `blackcraftcult` | geek EEUU | 6 (3 imágenes, 3 vídeos) | 1,5 | 1,3 M | 1/1 |
| `balenciaga` | lujo | 7 (6 carruseles, 1 vídeo; nada desde el 16-oct) | 3 | 15,0 M | – |
| `brooksbrothers` | clásico EEUU | 6 (5 carruseles, 1 vídeo) | 2,5 | 478 K | – |
| `stussy` | urbano EEUU | 4 (4 carruseles) | 2 | 6,1 M | 3/3 |
| `scalperscompany` | clásico España | 10 (4 carruseles, 6 vídeos) | 2 | 601 K | – |
| `thegrefg` | geek España | 8 (1 carrusel, 7 vídeos) | 0,5 | 7,7 M | – |

La puerta «persona con ropa» (CLIP, fotos reales de 6-9 días) deja pasar **62 de 81 fotos (77 %)**: muy bien las marcas con modelos (`killstar` 11/11, `barbour` 5/5, `stussy` 3/3, `abercrombie` 4/5), peor las que mezclan producto suelto (`hottopic` 8/12, `boxlunchgifts` 5/8, `dollskill` 4/6, `bimbaylola` 5/9) y mal `loewe` (1/3: portadas de producto); las marcas de Inditex y Mango pasan casi siempre (`stradivarius` 6/6, `mango` 2/2). Sorprende que `mango`, con 15,7 M de seguidores, publique solo 1,5 fotos por semana (el resto son vídeos). **Propuesta ★ v3** (14 cuentas públicas; con la de estadísticas suman las 15 que admite el plan de prueba): `gucci`, `loewe`, `ralphlauren`, `britishcountryheritage`, `barbour`, `massimodutti`, `zara`, `abercrombie`, `bershka`, `stussy`, `hottopic`, `killstar`, `thehippieshake`, `bimbaylola`; cubre 12 de las 14 casillas; **alternativas medidas que no entran por el tope de 14**: `boxlunchgifts` (geek EEUU, 6 fotos por semana), `dollskill` (geek EEUU), `stradivarius` (urbano/convencional España, 4 por semana y 6/6), `desigual` (bohemio España). Con el tope de 8 fotos nuevas por cuenta y semana, geek EEUU pasaría de 0 a unas 14 fotos por semana (unas 11 aceptadas). Siguen sin cobertura **geek España** y **old money España**: los streamers españoles que sí se leen publican casi solo vídeo (`ibaillanos` 9 publicaciones en 14 días y solo 2 carruseles, `auronplay` 3 vídeos, `knekro` ninguna) y el equipo de esports `g2esports` publica en inglés y casi sin ropa.

Detalle de manejo (no es un resultado, pero ahorra tiempo): la página de Windsor para dar de alta @ se atasca tras varias altas y bajas seguidas y deja de guardar sin avisar; basta recargarla y volver a pedir los elementos del formulario, y después las altas funcionan con 3 s de separación.

**Qué dicen los pies de foto (61 publicaciones de `hottopic`, `killstar` y `barbour`, 14 días):** son sobre todo promoción. En `hottopic` casi todo son eventos, sorteos, colaboraciones con grupos y franquicias (merchandising de My Chemical Romance, Pokémon, Hello Kitty, Elden Ring) y avisos de tienda, con poca mención de prendas; en `killstar` y `barbour` sí nombran la prenda («dungarees», «bodysuit», «mesh midi dress», «cardigan», «Thornproof Wax», «tartan», «denim»). Por eso los pies de foto no sirven para medir qué se lleva, solo como vocabulario de apoyo; y explican que `hottopic` deje pasar menos fotos por la puerta (8/12): muchas portadas son carteles de evento o de producto.

### 3.3 Cobertura esperada por casilla con la propuesta ★ v3

Con las cifras de 14 días de la tabla anterior (fotos = carruseles + imágenes; el carrusel aporta solo su portada), el tope de 8 fotos nuevas por cuenta y semana y la tasa de aceptación de la puerta «persona con ropa» medida en cada cuenta (75 % cuando no se midió o hay menos de 3 fotos):

| Estilo | Mercado | Cuentas ★ | Fotos nuevas por semana (tope de 8 por cuenta) | Aceptadas por la puerta |
|---|---|---|---|---|
| Geek | ES | — | 0 | 0 |
| Geek | US | `hottopic`, `killstar` | 14.0 | 11.3 |
| Urbano | ES | `bershka` | 5.0 | 5.0 |
| Urbano | US | `stussy` | 2.0 | 2.0 |
| Clásico | ES | `massimodutti` | 5.0 | 3.8 |
| Clásico | US | `ralphlauren` | 6.5 | 4.9 |
| Old money | ES | — | 0 | 0 |
| Old money | US | `britishcountryheritage`, `barbour` | 12.5 | 10.2 |
| Lujo | ES | `loewe` | 3.5 | 1.2 |
| Lujo | US | `gucci` | 7.0 | 7.0 |
| Bohemio | ES | `bimbaylola` | 6.0 | 3.3 |
| Bohemio | US | `thehippieshake` | 2.5 | 1.9 |
| Convencional | ES | `zara` | 6.5 | 6.5 |
| Convencional | US | `abercrombie` | 3.5 | 2.8 |

**Total: unas 74 fotos nuevas por semana, de las que la puerta acepta ≈ 60**, más ≈ 36 miniaturas de vídeo por semana que no se cuentan aquí. Dos casillas siguen vacías (geek España y old money España) y tres dependen de una sola cuenta con poca producción (urbano EEUU, lujo España, bohemio EEUU). Estas cifras son una estimación con dos semanas de ritmo y muestras pequeñas de la puerta; la primera tanda real de la tarea semanal las comprobará.

### 3.4 Fotos en la página de decisión (25 de octubre)

Para decidir ✓/✕ con criterio visual, la página «Cuentas de Instagram» enseña en cada tarjeta una **tira de 3 miniaturas con las publicaciones más recientes**: **72 de las 75 cuentas** (sin foto: `playboicarti`, que no tiene imágenes recientes, y `knekro` y `hannahdrapinski`, que Windsor no guarda por no ser cuentas profesionales). Las fotos salen de las direcciones `media_url` de Windsor (descargadas en el acto, recortadas a 3:4, JPEG de ~30 KB) y se publican como ficheros del propio Artifact privado (2,2 MB en total, carga diferida); **no se guardan en el repositorio** (herramientas: `tendencias_prenda/fotos_cuentas.py`; la página las pinta con `cuentas_instagram.py html --fotos`, que acepta la carpeta o la lista `diario_feed_instagram/cuentas_con_foto.txt`).

Cómo se hizo con tantas cuentas (Windsor solo admite 15 en la prueba): se rotaron las cuentas en rondas de 14 (quitando y dando de alta en la página de Windsor), pidiendo a Windsor ~45 días de publicaciones de cada ronda; el resultado era tan grande (0,3-1,5 MB de texto) que la herramienta lo guardó en un fichero y un script eligió las 3 últimas publicaciones con foto de cada cuenta (si no había 3, miniaturas de vídeo) sin copiar direcciones a mano. Al terminar se volvieron a dar de alta las 11 cuentas aceptadas (comprobado con `get_connectors`). La alternativa, capturar la rejilla del perfil con el navegador, resultó intermitente (el Chrome del portátil solo deja hacer capturas a ratos, cuando la pantalla y la ventana están activas) y solo sirvió para `pullandbear`. Dos detalles de manejo: a veces el alta de una cuenta no se guarda aunque el botón responda (reintentar tras recargar la página), y Windsor descarta sin avisar las cuentas personales.

### 3.5 Corrección de @ de marcas españolas (25 de octubre)

Las marcas españolas que «no se leían» (`elganso`, `pedrodelhierro`, `adolfodominguez`) **no eran ilegibles: el @ estaba mal escrito** (esas cuentas existen pero son ajenas, vacías o privadas). Buscando el nombre de la marca en la búsqueda de Instagram (la cuenta oficial sale primero, verificada y con su número de seguidores) se obtuvieron los @ buenos, y los cuatro se leen en Windsor: `elgansoinsta` (182 mil seguidores), `pedrodelhierro_official` (240 mil), `adolfodominguezofficial` (546 mil) y `cortefiel_official` (307 mil). Publicaciones en 14 días (carruseles / vídeos): Cortefiel 12 / 0, Pedro del Hierro 6 / 6, Adolfo Domínguez 5 / 8, El Ganso 3 / 3; las últimas fotos de Cortefiel y El Ganso enseñan camisas de cuadros, chinos, americanas, abrigos de paño, chaquetas acolchadas y punto de ochos (clásico / old money), las de Adolfo Domínguez sobre todo bolsos. Además `nudeproject` (urbano España, 1,6 M) da 3 carruseles y 2 vídeos en 14 días y mezcla campañas con fotos de artistas. Los cinco @ pasaron a la página de decisión (v16, 80 tarjetas) y la propuesta ★ sube a 17 (`elgansoinsta`, `cortefiel_official` y `pullandbear` para las casillas vacías de old money, clásico y urbano España). **Lección:** antes de dar una marca por «no legible», comprobar el @ con la búsqueda de Instagram. Con 14 cuentas de Instagram Public como máximo en la prueba de Windsor, caben las 11 aceptadas y tres más.

## 4. Integración en la tarea semanal

Fuente `{"tipo": "instagram", "valor": "usuario", ...}` en `tendencia_fuentes.json`. Una sola petición a Windsor con todas las cuentas; como mucho 8 fotos nuevas por cuenta y pasada (imágenes primero, más recientes antes); lo ya conocido solo actualiza likes, comentarios y seguidores; las fotos se bajan en el acto y pasan por la misma puerta («persona con ropa»), el mismo control de repetidas y el mismo análisis que las demás. La clave de Windsor llega por el secreto `WINDSOR_API_KEY`; sin él, la fuente da un aviso y la tarea sigue. Si alguna cuenta de las fuentes no está dada de alta en Windsor y la petición con filtro de cuentas falla, la tarea repite la petición sin filtro y se queda con las cuentas de las fuentes. 10 pruebas sin red (`test_instagram_fuente.py`), entre ellas que la clave no aparece en ningún mensaje de error y que un error de clave o de cupo no se reintenta.

## 5. Límites y cuestiones éticas

- Solo cuentas profesionales públicas que ya conocemos; no se descubren cuentas ni hashtags por esta vía; el cupo de la prueba es de 15 cuentas durante 30 días.
- Datos públicos de publicaciones; en el repositorio solo quedan identificadores, enlaces y cifras, ninguna foto. Mismo trato que el resto de fuentes (fotos de personas solo en Kaggle privado, borrado al terminar).
- La app de Windsor pide permisos de leer, estadísticas, comentar y publicar; se usa solo la lectura.
- La lectura del feed y de hashtags con el navegador del autor (sin likes ni comentarios; desde el 25 de octubre también se siguen cuentas, ver §5.3) es **cualitativa**: depende de la cuenta (feed personalizado) y de lo que Instagram enseña; el acceso automatizado contraviene las condiciones de Instagram aunque sea solo lectura, por lo que se limita a ritmo humano y se mantiene fuera de la tubería de medida.

## 5.1 Radar cualitativo de la primera noche de lectura

Una noche de lectura a mano asistida (24-25 de octubre; ~150 navegaciones, solo lectura) dejó un **radar por estilo** (`experimentos/analisis_mercado/diario_feed_instagram/radar_cualitativo_2026-10-25.md`): old money (abrigos de paño, punto grueso, chaquetas enceradas, lino claro), clásico (tweed, cazadora «varsity», gabardina), urbano (vaqueros muy anchos, chándal de nailon, camisetas de fútbol retro «blokecore»), geek (techwear, «gorpcore» de membrana y trail, anime), lujo (abrigos camel, bolsos de asa, relojes), bohemio («suzani», «kantha», croché, botines con flecos) y convencional (en inglés lo domina el streetwear asiático). Sirve para contrastar con lo que mide la tubería y proponer vocabulario nuevo; **no mide cuotas**.

## 5.2 Estabilidad de las rejillas de hashtag

Se repitió a las 04:20 la lectura visual de seis rejillas (#oldmoney, #preppystyle, #streetwear, #techwear, #bohostyle, #blokecore) leídas hacia la medianoche. En los hashtags de nicho la estética es la misma a horas de distancia (#blokecore repite sus tres primeros posts; #techwear y #bohostyle, mismos elementos con otros posts) y en los amplios se repiten las prendas aunque cambien los posts (#streetwear). Son resultados cualitativos de una cuenta nueva: sirven para vocabulario de prendas y estilos, no para medir frecuencias. Detalle en `diario_feed_instagram/pase_visual_2026-10-25.md`. Los hashtags en español de nicho «geek» (#modageek) devolvieron solo tiendas pequeñas de Colombia, Brasil, Paraguay, Chile y México (≤ 20 «me gusta»), ninguna cuenta española con fotos de outfits.

## 5.3 Seguir cuentas desde la cuenta del proyecto (25 de octubre)

La primera noche de lectura (§5.1) mostró que el feed de una cuenta nueva es casi genérico: hay que **sembrarlo** siguiendo cuentas de los siete estilos y los dos mercados. El 25 de octubre el autor dio permiso expreso para que el asistente siguiera cuentas con la cuenta del proyecto (`tendencias.moda_`, nueva: 0 publicaciones y 0 seguidores) y siguiera explorando. Se acotó así: (1) **solo seguir** (nada de «me gusta», comentarios, mensajes, guardar ni publicar); (2) solo cuentas públicas de moda de España o EEUU, con las aceptadas como fuente primero y después las alternativas de las casillas vacías; (3) **ritmo humano y bajo**: una cuenta cada varios minutos, con clic real sobre el botón de la página y comprobación de que pasa a «Siguiendo», como mucho 6 por hora y 15 al día por parte del asistente (el autor ya la había llevado a 16 seguidos a mano); (4) **parada inmediata** a la primera señal de Instagram (acción bloqueada, «inténtalo más tarde», confirmación de identidad, captcha o petición de inicio de sesión), sin reintentos ni saltos; (5) cada seguimiento queda anotado con hora y motivo en `diario_feed_instagram/SEGUIR_CUENTAS.md`, y en la página «Cuentas de Instagram» se marca «Ya la sigo». Es acceso automatizado de una cuenta real, que las condiciones de Instagram no permiten con esa generosidad; el riesgo (una restricción temporal de la cuenta, que afectaría a su uso con Windsor) lo asume el propietario y se reduce con el ritmo bajo.

**Primera tanda (08:50-08:57):** `gucci`, `loewe`, `zara`, `massimodutti`, `ralphlauren`, `britishcountryheritage` y `hottopic` (7 en ~8 min, uno más que el tope por hora; sin ningún aviso; la cuenta pasó de 16 a 23 seguidos). El «Explora» de la cuenta, a esa hora, estaba dominado por reventa de streetwear vintage (Supreme, camisetas de Dragon Ball, chaquetas de chándal Adidas, Ed Hardy, Carhartt): refleja lo que ya seguía el autor, no a las marcas que acababan de añadirse; habrá que repetir la lectura cuando el feed incorpore las nuevas.

## 6. Qué falta

**Hecho el 25-oct:** Víctor contestó las 83 tarjetas de la página de decisión: **68 ✓ y 15 ✕** (rechazó `adolfodominguezofficial`, `auronplay`, `barbour`, `bershka`, `bimbaylola`, `elgansoinsta`, `g2esports`, `hannahdrapinski`, `hm`, `ibaillanos`, `knekro`, `mango`, `pullandbear`, `stradivarius`, `thegrefg`). Las 68 están en `tendencia_fuentes.json` (141 fuentes en total) y se subieron con el código (§3.5, §5.3). Windsor solo lee 14 cuentas durante la prueba, así que se dieron de alta las que mejor cubren las casillas, una o dos por casilla: `abercrombie`, `britishcountryheritage`, `coldculture`, `cortefiel_official`, `desigual`, `gucci`, `killstar`, `loewe`, `nudeproject`, `ralphlauren`, `scuffers.co`, `stussy`, `thehippieshake` y `zara`; las otras 54 siguen siendo fuentes pero no se leen todavía. Con ellas, **urbano España y bohemio España ya tienen fuente** (antes quedaban vacías tras los rechazos). **Falta:** (1) comprobar con la pasada del lunes 26 a las 03:30 que la clave funciona; (2) decidir antes del 15 de noviembre entre Windsor Basic (23 US$/mes, 75 cuentas: caben las 68) y la app propia de Meta (gratis y sin tope de cuentas, más pasos: app de desarrollador y token de larga duración que hay que renovar), porque sin cambiar de plan al acabar la prueba (≈ 23 de noviembre) Windsor deja una sola cuenta; (3) para **geek España** y **old money España** no hay ninguna cuenta aceptada que publique fotos de eso (`teamheretics` solo vídeos y carteles; `elgansoinsta` fue rechazada): hacen falta @ que Víctor conozca; (4) medir con las primeras semanas cuánto sube la muestra en las casillas con pocas fotos (geek EEUU, urbano EEUU, lujo España, bohemio EEUU).
