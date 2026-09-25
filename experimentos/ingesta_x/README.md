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

`herramientas/descargar_x.py` recibe una o varias URLs de posts de X **con vídeo**, descarga el
vídeo con `yt-dlp`, extrae un fotograma cada N segundos con `ffmpeg` (binario portable vía
`imageio-ffmpeg`, no hace falta tenerlo instalado en el sistema), y guarda los fotogramas +
una metadata JSON con la procedencia (URL, cuenta, descripción, fecha de publicación). El vídeo
descargado se borra tras extraer los fotogramas — solo se conservan las imágenes fijas.

## Alcance de esta v1, a propósito reducido

- **Solo tuits con vídeo.** Los de solo foto no funcionan aquí: `yt-dlp` no expone la URL de la
  imagen para Twitter (solo formatos de vídeo) — un tuit de solo foto falla con un error claro,
  no en silencio. Resolverlo (con otra librería, o llamando a la API/oEmbed de X directamente)
  queda para cuando haga falta de verdad.
- **Sin descubrimiento automático.** Hay que darle URLs de posts concretos, uno a uno — no busca
  por hashtag ni sigue una cuenta. `yt-dlp` tampoco soporta URLs de perfil/timeline de X
  directamente (probado, da `Unsupported URL`).
- **Sin filtro de contenido de moda.** No distingue si el vídeo tiene ropa o gente o nada de
  interés — eso lo decide quien elija las URLs de entrada, o un paso posterior de clasificación.

## Cómo probarlo

```bash
pip install -r requirements.txt
cd herramientas
python descargar_x.py "https://x.com/usuario/status/1234567890" --out ../data/mi_lote --intervalo 2.0
```

`data/prueba_mecanismo/` es la prueba end-to-end ya hecha (2026-09-25) con un vídeo real
(`x.com/teganandsara/status/2102191354956693835`, sin relación con moda, elegido solo para
probar el mecanismo) — 7 fotogramas reales de 1080×1920, con su `_metadata.json` al lado. Sirve
como prueba de que la descarga + extracción funciona de principio a fin, no como dataset.

## Aviso de privacidad (pendiente de decisión consciente)

Esto descarga contenido con personas identificables reales, sin su consentimiento explícito para
este uso concreto — a diferencia del catálogo de Kaggle (producto sin personas) o de las fotos de
Wikimedia Commons ya usadas en el taxonomía de estilos (con licencia y atribución claras). La
memoria (`TFM_ingesta_redes_sociales.md` §5.4) ya lo señalaba como decisión pendiente antes de
escalar esto — sigue pendiente. Uso aceptado por ahora: investigación académica interna, sin
redistribuir los fotogramas fuera de este proyecto.

## Qué falta para que esto sea útil de verdad

1. Un lote real de URLs de vídeos de moda/tendencia en X (curado a mano, o encontrado por
   búsqueda) — esta v1 solo prueba el mecanismo con un vídeo cualquiera.
2. Pasar esos fotogramas por el clasificador ya entrenado (`experimentos/vlm_atributos_prenda/`)
   para tener el primer número real de "cómo rinde el modelo entrenado en catálogo sobre
   contenido real" — Etapa 2 del plan.
3. Decidir si merece la pena resolver la descarga de posts de solo foto (probablemente sí, mucho
   contenido de moda en X es foto, no vídeo).
