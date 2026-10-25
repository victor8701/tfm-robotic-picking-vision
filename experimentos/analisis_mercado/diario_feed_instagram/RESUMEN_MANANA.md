# Borrador del resumen para Víctor (se afina y se manda a las 06:47 o cuando él vuelva)

**Buenos días. Resumen de la noche (todo en local, sin subir nada a GitHub, y Instagram solo en modo lectura):**

**Instagram**
- Estuve ~175 navegaciones leyendo hashtags y perfiles con tu sesión de `tendencias.moda_`: ningún aviso de Instagram, sin likes, seguir ni comentar.
- **71 de las 75 cuentas candidatas se leen en Windsor** y están medidas (publicaciones en 14 y en 90 días, carruseles frente a vídeos). Prueba real de punta a punta con 189 fotos bajadas sin fallos: pasan la puerta «persona con ropa» el 77 % (146); el 84 % en Inditex y el 100 % en `killstar` y `barbour`.
- Mi propuesta ★ (14 cuentas, ya puesta en Windsor): `gucci`, `loewe`, `ralphlauren`, `britishcountryheritage`, `barbour`, `massimodutti`, `zara`, `abercrombie`, `bershka`, `stussy`, `hottopic`, `killstar`, `thehippieshake`, `bimbaylola`. Cubre 12 de las 14 casillas, entre ellas **geek EEUU** (la más vacía: `hottopic` ≈ 13 fotos por semana, `killstar` 6, todas las de `killstar` probadas pasan la puerta) y «bohemio España» (`bimbaylola`). Las creadoras españolas de moda publican sobre todo reels (se aprovecha la miniatura). Siguen sin cobertura geek España y old money España.
- Radar cualitativo por estilo (qué se repite en los hashtags): `diario_feed_instagram/radar_cualitativo_2026-10-25.md`.
- Sobre «educar el feed»: `tendencias.moda_` sigue solo 2 cuentas (`palomo_vintage` y `gothboishop`, vintage/goth; las seguiste tú), por eso el inicio sale con eso. Yo no sigo ni doy «me gusta» (aunque me diste libertad, prefiero no automatizar acciones que pueden hacer que Instagram limite la cuenta). Si quieres que el feed se vaya hacia moda de España y EEUU, sigue tú desde el móvil las ★ (tocando el @ en la página); en unos días «Para ti» y «Explorar» se llenan de moda parecida, y entonces lo leo yo en modo lectura. Si prefieres que siga yo las 14 con pausas largas, dímelo.

**Demo del Modo 4 (nueva):** Trend JSON por estilo y mercado → puntuación de SKUs → aprobación del operario. 7 de las 14 casillas ya tienen datos para generar una tendencia; el umbral θ = 0,20 del documento deja pasar entre el 25 y el 57 % del inventario y el boost de grupo domina el top-5.

**Páginas para ti (móvil):**
- «Cuentas de Instagram»: https://claude.ai/artifact/XA1GspeMKPPmsXmeMZqK42 (75 candidatas; filtro «★ Mi propuesta»; marca ✓ Fuente / ✕ No, «Ya la sigo», cambia estilo y mercado).
- «Aprobar tendencias»: https://claude.ai/artifact/EGzojG5pvkWoeoMCgTxsir (simulación del HMI).

## Cómo vamos
- Instagram: lectura funcionando por la vía oficial (Windsor, prueba gratuita hasta ~23-nov); código de la fuente nueva listo en local con 10 pruebas (y ensayado el paso que aplica tus ✓ a las fuentes); falta tu ✓ en las cuentas y la clave en GitHub.
- La tarea semanal corre el lunes 26 a las 03:30 (hora de España). Sin Instagram, salvo que HOY domingo hagas los tres pasos (tus ✓, un sí a subir el código y la clave en GitHub); si no, Instagram entra el lunes 2 de noviembre (la prueba de Windsor llega hasta ~23-nov: cinco lunes en total).
- Todo lo de la noche está sin commitear: memoria nueva (`TFM_instagram_fuente.md`, `TFM_modo4_demo.md`), código nuevo y diarios.

## Qué necesito de ti
1. En «Cuentas de Instagram»: si te parece bien mi propuesta, filtro «★ Mi propuesta» y un toque en «✓ Aceptar las 14» (1 min); si no, ✓/✕ una a una (10 min). Sigue las que quieras tocando el @.
2. Un sí/no en el panel «Hoy»: ¿subo a GitHub el código de la fuente de Instagram?
3. Cuando quieras que la tarea lea Instagram: poner `WINDSOR_API_KEY` en los secretos de GitHub (te guío).
4. Opcional: si conoces 2-3 cuentas de Instagram españolas de estilo geek/gamer o cayetano/old money que publiquen fotos de outfits, pásame los @ y los pruebo en Windsor (son las dos casillas que no consigo llenar).
5. Opcional: probar «Aprobar tendencias»; decidir si apago «Write actions» en Windsor.
