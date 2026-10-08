# «Profesor»: un modelo abierto grande de lenguaje y visión para estampado, tejido y forma

**Pregunta.** CLIP sin entrenar, una capa entrenada con 22 000 prendas de Fashionpedia y Florence-2 no superan a «decir siempre lo más frecuente» con las etiquetas de Víctor (`memoria/TFM_tendencias_de_prenda.md` §6).
¿Lo hace un modelo grande abierto (Qwen2.5-VL de 7 000 millones de parámetros, Qwen3-VL de 8 000 millones) **sin entrenar**, mirando la foto entera y no solo el recorte? Si sí (y supera el 70 %), puede hacer de profesor: etiquetar miles de fotos de las fuentes
y destilarse en nuestro modelo con LoRA (el «entrenamiento grande» con sentido). Si no, forma y tejido quedan como límite documentado.

**Cómo se mide.** Dos exámenes, en un kernel de Kaggle con GPU (T4 ×2):
1. **Fashionpedia** (público): 308 prendas de `val`, una muestra por clase de estampado y de forma, con las etiquetas derivadas de los atributos del conjunto. Compara con la capa sobre CLIP B/32 en las mismas prendas.
2. **Las etiquetas de Víctor** (40 fotos, 61 prendas): su paquete va aparte (`--origen victor`) porque son fotos de personas reales. Sus etiquetas no se suben: se miden en local con `evaluar_profesor.py`.

Tres configuraciones (`kernel_profesor.py`): `recorte`, `foto` (foto entera con la prenda en una caja roja + el recorte) y `foto_razona` (describe en pocas frases y luego contesta, en una submuestra de 80).
Las respuestas se piden como JSON con valores cerrados (`plain|striped|plaid|graphic|text_logo|camouflage|other`, etc.) y se traducen al vocabulario de Víctor.

## Pasos

```bash
cd experimentos/vlm_atributos_prenda/herramientas/vlm_profesor
python3 preparar_dataset.py --origen fashionpedia --salida /ruta/dataset_fp        # paquete público (fotos.zip + manifiesto.json)
python3 kaggle_ops.py dataset-crear /ruta/dataset_fp                               # dataset PRIVADO en Kaggle
python3 kaggle_ops.py kernel-push kernel_profesor.py "TFM profesor VLM prendas" tfm-prendas-fashionpedia-vlm
python3 kaggle_ops.py estado                                                       # hasta COMPLETE
python3 kaggle_ops.py bajar /ruta/salida                                           # pred_*.jsonl + resumen.json
python3 evaluar_profesor.py --pred /ruta/salida --manifiesto /ruta/dataset_fp/manifiesto.json --salida ../../resultados/profesor_….json
python3 kaggle_ops.py dataset-borrar tfm-prendas-fashionpedia-vlm                  # al terminar
```

Para el paquete de Víctor: `--origen victor`, otro `dataset-crear` y se añade su slug (`tfm-prendas-victor-vlm`) a la lista de datasets del `kernel-push` (separados por comas). **Esas fotos son personas reales: solo se suben con permiso expreso de Víctor, en un dataset privado, y se borran al terminar.**

`kernel_profesor.py` se puede probar sin GPU: `PROFESOR_FALSO=1 PROFESOR_ENTRADA=<carpeta con los paquetes> PROFESOR_SALIDA=<carpeta> python3 kernel_profesor.py` (un generador falso comprueba la lógica de datos, prompts, lectura y resumen).
`MODO = "humo"` (primera línea del script) corre 8 prendas con un solo modelo para depurar en ~3 minutos.

## Notas de Kaggle

- Autenticación con el «API Token» nuevo (`~/.config/kaggle/api_token`), por el SDK; el `kaggle.json` clásico de esta máquina ya no autentica y la CLI 1.7.4.5 no soporta el token. `kaggle_ops.py` envuelve las dos cosas.
- Un dataset subido con `dir_mode="skip"` ignora las carpetas, por eso las fotos van en un único `fotos.zip` que el kernel extrae.
- Qwen2.5-VL-7B en fp16 repartido entre las dos T4 cargó en 103 s y dio JSON válido a la primera; ~0,7 s por prenda con lotes de 6.
