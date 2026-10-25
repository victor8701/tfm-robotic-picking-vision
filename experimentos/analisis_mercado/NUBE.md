# La tarea semanal en la nube (sin encender el ordenador)

Cada lunes, GitHub Actions ejecuta `tendencia_prenda.py todo --sin-biblioteca` y después manda por correo **la revista semanal** (`revista_semanal.py`).
El ordenador de Víctor no interviene. Fichero de la tarea: `.github/workflows/tendencia_semanal.yml` (tiene que estar en la rama `main`, porque GitHub solo programa tareas desde ahí).

```
lunes ~04:30 (GitHub puede retrasarlo 2-7 h)
   │  código: rama analisis-mercado        datos de la semana pasada: rama datos-tendencia
   ▼
cosechar (X, prensa, Reddit)  →  fotos nuevas con persona y ropa (sin repetidas)
analizar (CPU)                →  detector DeepFashion2 + Florence-2 + CLIP: prendas y tipo
modelo grande (Kaggle, GPU)   →  Qwen3-VL-8B: tipo, estampado, tejido y forma (dataset PRIVADO que se borra siempre)
informe + comparación entre estilos
   ▼
guarda los datos en `datos-tendencia`  →  manda la revista a tu correo  (si algo falla, manda un aviso corto)
```

## Qué hay que hacer una vez (desde el móvil, ~10 minutos)

Hacen falta cuatro «secretos» en GitHub (repositorio → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*). Los secretos no aparecen en los registros ni en el código.

| Secreto | Qué poner | Cómo conseguirlo |
|---|---|---|
| `SMTP_USER` | tu dirección de Gmail desde la que se envía | la tuya |
| `SMTP_PASSWORD` | contraseña **de aplicación** de Google (16 letras) | cuenta de Google → *Seguridad* → *Verificación en 2 pasos* (tiene que estar activa) → *Contraseñas de aplicaciones* → nombre «Tendencias» → copiar |
| `MAIL_TO` | dónde quieres recibir la revista | el correo que prefieras (puede ser el mismo) |
| `KAGGLE_API_TOKEN` | un token **nuevo** de Kaggle | kaggle.com → *Settings* → *API* → *Generate New Token* → copiar el texto entero (el del portátil se queda aparte) |

Después, en GitHub: *Actions* → **Tendencia semanal (revista)** → *Run workflow*. La primera vez tarda más (descarga de modelos, ~1-2 h). Si todo va bien llega la revista al correo; si falla, llega un aviso con el enlace al registro.
Desde entonces corre sola cada lunes. Cuando se vea que funciona, se quita la tarea local de `crontab` (hoy hay una, que solo corre con el portátil y WSL encendidos).

## Cómo se guardan los datos

- **Código**: rama `analisis-mercado` (la tarea la lee tal cual: lo que se sube ahí es lo que corre el lunes).
- **Datos generados** (`fotos.json`, `prendas.json`, `estado.json`, `informe.json`, `separacion_estilos.json`, `embeddings.npz`, `registro_semanal.txt`): rama `datos-tendencia`, para que los commits del lunes no choquen con los de código. Para traerlos al portátil: `python3 sincronizar_nube.py bajar`.
- **Datos curados a mano** (etiquetas de Víctor, valoraciones, `fiabilidad.json`, lotes): van con el código.
- **Fotos**: no se guardan en ningún sitio. Cada lunes se vuelven a bajar solo las que hacen falta (nuevas, y las de los ejemplos de la revista) desde su dirección pública.

## Privacidad (el repositorio es público)

- En el repositorio solo hay identificadores, direcciones públicas de las fotos, cajas y etiquetas; ninguna foto.
- Los registros de la tarea son públicos: no imprimen secretos ni correos.
- Las fotos nuevas salen del runner de GitHub a un dataset **privado** de Kaggle, que se borra en la misma pasada (como en la tarea de antes).
- La revista pasa por el servicio de correo de Google. Las miniaturas de prendas son recortes de fotos públicas de personas; se pueden quitar con la opción `--sin-fotos` del paso «Revista por correo».

## El modelo grande: qué configuración usa la tarea (16 de octubre)

La tarea etiqueta los recortes nuevos con Qwen3-VL-8B en Kaggle usando la configuración `semanal_pista` (`CONFIG_VLM` en `tendencia_prenda.py`). Antes usaba `semanal`, que en los recortes de pantalón nombraba a menudo la prenda de arriba que asoma por el borde (camisa, chaqueta, americana) y daba el tejido de esa otra prenda: los vaqueros salían «camisa de algodón». `semanal_pista` le dice qué zona del cuerpo marcó el detector y le pide la prenda que ocupa casi toda la caja (memoria §6.11; `evaluar_zona.py`).
- Probar otra configuración sobre recortes elegidos, sin tocar los datos: `python3 tendencia_prenda.py vlm-prueba --claves CLAVES.json --configs semanal_pista --salida CARPETA` (sube un dataset PRIVADO de Kaggle y lo borra siempre).
- Pasar esas respuestas a `prendas.json` (el etiquetado anterior queda en `vlm_anterior`): `python3 tendencia_prenda.py vlm-aplicar --dir CARPETA --config semanal_pista`.

## Instagram como fuente (24 de octubre): lectura oficial de Meta a través de Windsor

Las fuentes de tipo `instagram` de `tendencia_fuentes.json` (`{"tipo": "instagram", "valor": "usuario", "referente": "...", "estilo": "...", "mercado": "ES|US"}`) se leen con el conector `instagram_public` de Windsor (Business Discovery de Meta): solo cuentas **profesionales** (Creador o Empresa) que ya conocemos por su @; no descubre cuentas ni hashtags. La cuenta `tendencias.moda_` (profesional, enlazada a la página de Facebook «Tendencias Moda») hace de «llamante».

- **Secreto de GitHub `WINDSOR_API_KEY`**: la clave de la API de Windsor (la clave es de toda la cuenta; se ve en `onboard.windsor.ai/app/data-preview`). La mete Víctor en *Settings → Secrets and variables → Actions*; nunca por el chat ni en ningún fichero. Sin ella, las fuentes de Instagram dan un aviso («falta el secreto WINDSOR_API_KEY») y el resto de la tarea sigue.
- **Cupo de Windsor**: la prueba gratuita (30 días desde el registro) admite 15 cuentas en total; después, plan Free = 1 cuenta o Basic = 75 cuentas (23 US$/mes). Las cuentas que se leen tienen que estar dadas de alta en Windsor (página `onboard.windsor.ai/app/instagram_public`, campo «Account to follow»); Windsor descarta solo las que no puede leer.
- **Qué baja**: por cuenta, como mucho 8 fotos nuevas por pasada (imágenes y carruseles primero, más recientes antes; los vídeos, su miniatura), ventana de 35 días con solapamiento; lo ya conocido solo actualiza likes/comentarios/seguidores. Las direcciones de las fotos caducan a los ~5 días: se bajan en el acto (la caché de la nube empieza vacía cada semana) y no se pueden recuperar después.
- **Privacidad y normas**: lectura por la API oficial (no hay scraping ni uso de la sesión de nadie). En el repositorio solo quedan identificadores, el enlace público de cada publicación y cifras; ninguna foto.
- **Petición REST** (parámetros comprobados en la documentación oficial de Windsor, 25-oct): `https://connectors.windsor.ai/instagram_public?api_key=…&fields=…&date_from=…&date_to=…&select_accounts=@1,@2,…&_renderer=json`; `select_accounts` lleva los @ separados por comas sin espacios (el identificador de cada cuenta es su @, como lo da `get_connectors`); límites de Windsor: 600 peticiones por minuto y 10 000 al día (la tarea hace una a la semana). Si alguna cuenta de las fuentes no está dada de alta en Windsor y la petición con `select_accounts` falla (HTTP 400/404/422), la tarea repite la petición sin ese filtro y se queda solo con las cuentas de las fuentes; un error de clave o de cupo (401/403/429) no se reintenta. Las altas en Windsor y las ✓ de la página deben coincidir (máximo 14 cuentas Public durante la prueba).
- Código: `cosechar_instagram`, `windsor_filas` e `instagram_registros` en `tendencia_prenda.py`; pruebas en `test_instagram_fuente.py` (sin red).

## App propia de Meta (25 de octubre): lectura gratis y sin tope de cuentas

Alternativa a pagar Windsor. `instagram_meta.py` lee las cuentas de las fuentes con Business Discovery (`graph.facebook.com`, API v25.0) usando una app de Meta en modo desarrollo y un token de la cuenta profesional `tendencias.moda_`. Devuelve las filas con los mismos nombres de campo que Windsor, así que el resto de la tarea no distingue el origen.

- **Secretos de GitHub** (los pone Víctor; nunca por el chat): `META_IG_TOKEN` (token de página, que no caduca, o token largo de persona, ~60 días) y, opcional, `META_IG_USER_ID` (identificador de la cuenta de Instagram; si falta se busca solo). Cómo conseguirlos, paso a paso: `GUIA_APP_META.md` (con casillas, en el Artifact «Guía app de Meta»).
- **Orden en la tarea semanal** (`instagram_filas`): primero Meta si hay `META_IG_TOKEN`; Windsor (`WINDSOR_API_KEY`) para las cuentas que Meta no lea o si Meta falla (incluido un fallo imprevisto del lector). Si faltan las dos, las fuentes de Instagram se saltan con un aviso. El token de persona se prueba antes que el de su página.
- **Avisos**: si el token falla o le quedan menos de 15 días, la tarea escribe `avisos.json` y la revista lo muestra en «Para la próxima». Las cuentas sin lectura (personales, privadas, mal escritas) se cuentan aparte en una frase, no como error.
- **Prueba de un clic**: *Actions → «Prueba de Instagram» → Run workflow* (`prueba_instagram.py`, el fichero del workflow tiene que estar en `main`). Comprueba Meta y Windsor con las mismas funciones que la tarea y escribe el resultado en español en el resumen de la ejecución; la casilla «Probar con Meta las 68 cuentas…» gasta entre 70 y 150 de las ~200 peticiones por hora. Nunca imprime una clave.
- **Pendiente de comprobar** (solo con el token de Víctor): que Meta deje leer cuentas ajenas con una app en desarrollo sin pasar la revisión de la app. La documentación de Business Discovery no dice nada del modo desarrollo.
- Pruebas sin red: `test_instagram_meta.py` (24) y `test_instagram_fuente.py` (11).

## Prueba de Instagram (opcional, 16 de octubre) — sustituida por la anterior

`instagram_prueba.py` + `.github/workflows/instagram_prueba.yml` comprueban si Meta deja leer fotos de OTRAS cuentas profesionales (Business Discovery) con una app en modo desarrollo. Necesita un secreto de GitHub `META_IG_TOKEN` (token de usuario de Facebook de larga duración con `instagram_basic`, `pages_show_list`, `pages_read_engagement` e `instagram_manage_insights`, de un usuario que administre una Página de Facebook enlazada a una cuenta de Instagram Creador o Empresa). Se lanza creando `experimentos/analisis_mercado/lanzar_instagram.txt` y subiéndolo a la rama `analisis-mercado`; no guarda ninguna foto ni imprime el token. Si funciona, se integra como un tipo de fuente más (`instagram`) en `tendencia_fuentes.json`; si no, se descarta.

## Si algo falla

- *Revista de la semana anterior no llegó*: mirar en *Actions* el último «Tendencia semanal (revista)»; el paso en rojo dice dónde. Los datos de la semana pasada siguen intactos en `datos-tendencia`.
- *Reddit o X no devuelven nada desde GitHub*: algunas fuentes bloquean las direcciones de los servidores de GitHub. La revista lo cuenta («fuentes con error») y el resto sigue.
- *Kaggle falla*: el informe sale igual con el tipo de CLIP y las prendas quedan pendientes para la semana siguiente.
- *La tarea tarda más o dice que quedan fotos pendientes*: desde el 14 de octubre hay 73 fuentes (46 nuevas de old money, clásico, lujo, bohemio y convencional). El análisis en CPU tiene un tope de 120 minutos (`--max-minutos`), con las fuentes por turnos y lo más reciente primero; lo que no da tiempo se analiza la semana siguiente. La tarea guarda los datos solo al final, así que sin tope una tanda grande se podía perder entera.
- Para repetir a mano: *Actions* → *Run workflow*.
