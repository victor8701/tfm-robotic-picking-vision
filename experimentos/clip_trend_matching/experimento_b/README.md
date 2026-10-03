# Experimento B — ¿aporta la evidencia visual al vector de tendencia de texto?

Compara, recuperando prendas de un inventario con CLIP (el del POC, `../clip_matching_poc.py`), seis
**métodos** por tendencia (los 7 sub-estilos de `Estado_arte.md` §3.4.2):

| Método | Qué es |
|---|---|
| `T_ciego_en` | descripción redactada por un LLM que solo conoce el *nombre* de la tendencia (Gemini gratuito, T=0), en inglés |
| `T_ciego_es` | la misma, en español (como la genera hoy el pipeline; CLIP-OpenAI es de inglés) |
| `T_oraculo_en` | prompt escrito conociendo la taxonomía — cota superior **optimista** del texto |
| `V` | centroide **recortado** (se descarta el 20 % más alejado) de 10 fotos reales confirmadas de esa tendencia |
| `F_ciego` / `F_oraculo` | fusión `0.5·texto + 0.5·V` con el texto ciego / oráculo |

## Cómo ejecutarlo (todo desde esta carpeta, sin editar código)

```bash
python3 generar_textos_ciegos.py     # ya hecho (textos_tendencia_b.json, versionado); repetirlo cambia los textos
python3 experimento_b.py preparar    # embeddings (con caché) + señal automática gruesa + pool para puntuar
python3 evaluar_b.py                 # abre http://localhost:8765 y puntúa 0/1/2 a ciegas (~15 min; se puede parar y reanudar)
python3 experimento_b.py analizar    # P@5 / NDCG@5 (y @10 si completas el tramo 2), diferencias emparejadas
```

El pool tiene dos **tramos**: el 1 (≈147 prendas) completa el top-5 de todos los métodos —lo mínimo—; el 2
(≈121) añade los puestos 6-10 para más precisión. Puedes parar al acabar el tramo 1.

## Diseño fijado ANTES de puntuar (2026-10-03)

- Métrica primaria: **P@5 estricto** (relevante = puntuación 2). Secundarias: P@5 laxo (≥1), NDCG@5, y lo mismo @10.
- α = 0.5; N = 10 fotos de evidencia (sorteo con semilla 0); recorte 20 %; textos congelados en `textos_tendencia_b.json`.
- Decisión: **MEJORA** solo si la diferencia media es ≥ +5 pp **y** el IC95 % (t, 6 gl) excluye 0; si no, **neutro**
  (el plan lo documenta como resultado neutro y cierra la vía visual). Se informa también victorias/empates/derrotas y el
  p exacto por permutación de signos. *No* se usa bootstrap percentil: con 7 tendencias da ≈13 % de falsos positivos
  (simulado con puntuaciones aleatorias; t ≈ 6 %, permutación ≈ 1 %).
- Quien puntúa ve el nombre de la tendencia y los rasgos de su taxonomía, **nunca** los textos ni qué método propuso cada prenda.

## Límites que hay que declarar en la memoria

1. **Potencia**: con 7 tendencias solo se detectan diferencias grandes (IC ≈ ±20 pp). «Neutro» ≠ «no hay efecto».
2. **Inventario**: 1 207 miniaturas de **60×80 px** de un catálogo de e-commerce (30 tipos de artículo, casi todo básico):
   no hay prendas «geek» ni «bohemias» de verdad. Es un sustituto; el resultado fiable llegará con el catálogo real de SKUs.
3. **Salto de dominio**: la evidencia visual son fotos de calle/redes (persona, fondo) y el inventario fotos de producto
   aisladas (problema *street-to-shop*). Un vector visual puede quedar penalizado por eso, no por falta de información de estilo.
4. **Texto**: el brazo ciego parte solo del nombre (límite inferior del agente real, que ve el contenido); el oráculo es
   un límite superior. Todos los textos largos se **truncan a 77 tokens** (CLIP): se pierde la última frase.
5. **Señal automática** de `preparar`: usa un mapeo orientativo sub-estilo → grupo del ERP muy grueso; sirve de prueba
   de humo, no como resultado.
6. Las 168 fotos de evidencia mezclan origen (X, Wikimedia, subidas) y las etiquetó una sola persona.

## v2 — inventario corregido y dos brazos nuevos (añadida DESPUÉS de ver la v1; exploratoria)

**Motivo.** En la v1, `alternativo_geek` y `lujo_ostentoso` tuvieron techo ≈ 0 con todos los métodos (2 y 5 prendas
aprobadas de 43 y 42): el catálogo de prueba no contenía ese tipo de prendas. Víctor lo confirmó y aportó sus
referencias de estilo: **lujo ostentoso = Dani Alves; geek = Orslok**.

- `anadir_inventario_extra.py`: **+60 prendas** de adulto con motivos de fandom (Batman, Marvel, Angry Birds, Mickey…) del
  *mismo* dataset de origen, elegidas por una **regla sobre metadatos** (no por CLIP ni por resultados), mismo tamaño 60×80 px.
- **`lujo_ostentoso` se excluye del análisis v2**: este dataset es de grandes superficies (tras quitar relojes, joyería y
  perfumes quedan ~4 prendas de diseñador reales; las 65 de «marcas premium» son sobre todo merchandising Puma-Ferrari) y
  Wikimedia Commons devuelve escaneos, pasarelas y fotos de personas. Hace falta un catálogo real. *(Observación de diseño:
  el catálogo real de segunda mano «por kilo» probablemente tenga el mismo problema; ver memoria §14.3 y §7.5.)*
- Brazos nuevos: `T_corto_ciego_en` (un prompt corto en inglés redactado por el MISMO LLM ciego, que solo conoce el nombre) y
  `F_corto` (su fusión con la evidencia visual). Separan el efecto del **formato** del texto del efecto del **conocimiento** de la
  taxonomía, que el oráculo de la v1 mezclaba.
- Oráculo de `alternativo_geek` corregido: el de la v1 decía «techwear, goth or punk», que no es la definición de la taxonomía
  (fandom: gaming, anime, cómic); se redacta a partir de esa definición escrita.
- Las 268 puntuaciones de la v1 se **reutilizan**; solo se puntúan las prendas nuevas del pool (≈ 41).

```bash
python3 generar_textos_ciegos.py --solo-v2   # añade, sin tocar lo existente, el prompt corto ciego y el oráculo corregido
python3 anadir_inventario_extra.py           # +60 prendas en inventario_extra/geek/
python3 experimento_b.py preparar-v2         # pool_b_v2.json = solo las prendas aún sin puntuar
python3 evaluar_b.py --pool pool_b_v2.json   # puntuar (se guarda en el mismo ratings_b.json)
python3 experimento_b.py analizar-v2
```

**Estatus estadístico.** Las decisiones de la v2 se tomaron *viendo* los resultados de la v1 (grados de libertad del
investigador), así que todo es **exploratorio** salvo dos comparaciones declaradas primarias antes de puntuar:
`F_corto − T_corto_ciego_en` (¿la imagen mejora a un texto corto sin conocimiento de la taxonomía?) y
`T_corto_ciego_en − T_ciego_en` (efecto del formato). Misma regla de decisión; 6 tendencias en lugar de 7.

**Resultados y conclusiones (v1 y v2):** ver `memoria/TFM_experimento_B_vectores_visuales.md`.
