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

## Si algo falla

- *Revista de la semana anterior no llegó*: mirar en *Actions* el último «Tendencia semanal (revista)»; el paso en rojo dice dónde. Los datos de la semana pasada siguen intactos en `datos-tendencia`.
- *Reddit o X no devuelven nada desde GitHub*: algunas fuentes bloquean las direcciones de los servidores de GitHub. La revista lo cuenta («fuentes con error») y el resto sigue.
- *Kaggle falla*: el informe sale igual con el tipo de CLIP y las prendas quedan pendientes para la semana siguiente.
- Para repetir a mano: *Actions* → *Run workflow*.
