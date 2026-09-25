# Ingesta de X (Twitter) — Etapa 1 del plan de ingesta de redes sociales

Primer paso de construcción real de `memoria/TFM_ingesta_redes_sociales.md`: conseguir
fotogramas reales de contenido de redes sociales, guardados en disco y trazables a su fuente
original. Ver esa memoria (Anexo de decisión de plataforma, 2026-09-25) para por qué se eligió
**X/Twitter** como primera plataforma: no es la que más contenido de moda tiene, es la más barata
de construir de las tres probadas (X más accesible que Instagram, que a su vez es más accesible
que TikTok, bloqueada con un reto anti-bot que no se pudo resolver sin herramientas adicionales).

Vive como script aparte en este repo del TFM, no dentro de `viral_clips` (decisión explícita del
autor, 2026-09-25) — más simple y aislado, a costa de no ser reutilizable en ese otro proyecto.

## Qué hace

`herramientas/descargar_x.py` recibe una o varias URLs de posts de X (por argumento, o por lote
con `--urls-file`). Para cada una, primero consulta el endpoint público de sindicación de X
(`cdn.syndication.twimg.com` — el mismo que usan los widgets de "insertar tuit" de cualquier web,
sin sesión ni clave de API) para saber qué tiene el post:

- **Si tiene vídeo**: lo descarga con `yt-dlp` y extrae un fotograma cada N segundos con `ffmpeg`
  (binario portable vía `imageio-ffmpeg`, no hace falta instalarlo aparte). El vídeo se borra
  tras extraer los fotogramas.
- **Si tiene foto(s) nativas**: las descarga directamente en su resolución original.
- **Si no tiene ninguna de las dos** (solo texto, o solo una tarjeta de vista previa de un
  enlace externo): falla con un error claro, no en silencio.

Cada imagen se guarda junto a una metadata JSON con su procedencia (URL, cuenta, descripción,
fecha de publicación, tipo de contenido).

## Alcance de esta v1

- ~~Solo tuits con vídeo~~ **resuelto (2026-09-25)**: ahora también descarga fotos nativas (ver
  arriba). Sigue habiendo un caso sin cubrir: posts que solo tienen una tarjeta de vista previa
  de un enlace externo (p. ej. un tuit que solo enlaza a un artículo) no se descargan — no es
  contenido nativo del post, tiene menos valor como dato de moda real.
- ~~Sin descubrimiento automático~~ **investigado a fondo (2026-09-25) y descartado por ahora,
  no solo pospuesto**: se probó (a) los extractores de timeline/búsqueda de `yt-dlp` (no
  existen para X), (b) el endpoint de timeline de sindicación (da 429 / vacío), y (c) el token
  de invitado de la API pública que usan herramientas de scraping conocidas —
  **X lo ha invalidado** ("Invalid or expired token"). Sin autenticarse con una cuenta real de X
  no hay forma fiable de buscar/listar contenido automáticamente ahora mismo, y autenticarse es
  una decisión aparte (¿cuenta de quién?, ¿riesgo de que X la banee?) que no se ha tomado. La
  vía que sí funciona: `--urls-file` acepta un lote de URLs ya identificadas (a mano, o por
  búsqueda web hecha por Claude, como se ha hecho durante todo este proyecto) — quita la
  fricción de invocar el script uno a uno, aunque la identificación de URLs siga siendo externa
  al script.
- **Sin filtro de contenido de moda.** No distingue si el post tiene ropa o gente o nada de
  interés — eso lo decide quien elija las URLs de entrada, o un paso posterior de clasificación.

## Cómo probarlo

```bash
pip install -r requirements.txt
cd herramientas
python descargar_x.py "https://x.com/usuario/status/1234567890" --out ../data/mi_lote

# o por lote:
python descargar_x.py --urls-file lista_urls.txt --out ../data/mi_lote --intervalo 2.0
```

`data/prueba_lote/` es la prueba end-to-end ya hecha (2026-09-25), por lote y mezclando los dos
tipos de contenido: una foto nativa real (`x.com/PopCrave/status/2025945514370310293`, 2 fotos a
resolución original) y un vídeo real (`x.com/teganandsara/status/2102191354956693835`, 7
fotogramas) — ninguno de moda, elegidos solo para probar el mecanismo, con su `_metadata.json`
al lado de cada uno. Sirve como prueba de que funciona de principio a fin, no como dataset.

## Aviso de privacidad (pendiente de decisión consciente)

Esto descarga contenido con personas identificables reales, sin su consentimiento explícito para
este uso concreto — a diferencia del catálogo de Kaggle (producto sin personas) o de las fotos de
Wikimedia Commons ya usadas en el taxonomía de estilos (con licencia y atribución claras). La
memoria (`TFM_ingesta_redes_sociales.md` §5.4) ya lo señalaba como decisión pendiente antes de
escalar esto — sigue pendiente. Uso aceptado por ahora: investigación académica interna, sin
redistribuir los fotogramas fuera de este proyecto.

## Qué falta para que esto sea útil de verdad

1. Un lote real de URLs de fotos/vídeos de moda/tendencia en X (curado a mano, o encontrado por
   búsqueda) — esta v1 solo prueba el mecanismo con contenido cualquiera, no de moda.
2. Pasar esas imágenes por el clasificador ya entrenado (`experimentos/vlm_atributos_prenda/`)
   para tener el primer número real de "cómo rinde el modelo entrenado en catálogo sobre
   contenido real" — Etapa 2 del plan.
