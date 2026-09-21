# Reentrenar vía Kaggle (alternativa a Colab, sin manejar un notebook)

Mismos pasos que `notebook_colab_entrenamiento.ipynb` (clonar, instalar, preparar dataset, entrenar,
evaluar), pero lanzados y seguidos por API en vez de abrir un notebook a mano — pensado para cuando
no hay forma cómoda de manejar la interfaz de Colab (p. ej. desde el móvil). Kaggle da GPU gratis
(T4×2 o P100, ~30 h/semana) igual que Colab. Usado de verdad el 2026-09-20 para entrenar v2, v3 y
v4 seguidos (resultados en `memoria/TFM_clasificador_visual_atributos.md` §11.2, §11.4, §11.5).

## Qué hace falta (una vez, ~2 min desde cualquier navegador)

1. Cuenta de Kaggle (gratis, sin tarjeta): [kaggle.com](https://www.kaggle.com/).
2. **Verificar el teléfono de la cuenta**: `Settings` → pestaña **Account** → **Phone
   Verification**. Kaggle no da internet dentro de un kernel sin esto (aunque se pida
   `enable_internet=True` por API) — sin verificar, `git clone`/`pip install`/descargar el
   dataset fallan con `Could not resolve host` sin ningún aviso más claro. Comprobar con
   `diag_internet.py` (ver abajo) antes de lanzar el entrenamiento de verdad ahorra un ciclo
   entero de ~30 min si falla.
3. `Settings` → pestaña **API Tokens** → **Generate New Token** (la sección "(Recommended)",
   *no* la "Legacy API" de más abajo). Copiar el token, algo como `KGAT_...`.
4. Guardarlo en la máquina que va a lanzar el entrenamiento: `~/.config/kaggle/api_token`
   (`chmod 600`). El paquete `kaggle` de PyPI en uso (1.7.4.5) todavía **no** soporta este
   token nuevo en sus comandos de CLI (`kaggle kernels push` etc. siguen pidiendo el
   `kaggle.json` clásico de usuario+key) — por eso `push_and_run.py` no usa la CLI, usa
   directamente `kagglesdk` (que sí lo soporta vía la variable de entorno `KAGGLE_API_TOKEN`,
   que el script rellena solo desde ese fichero).

## Cómo se lanza

```bash
cd experimentos/vlm_atributos_prenda/herramientas/kaggle_kernel
pip install --user kaggle              # trae kagglesdk como dependencia
python3 push_and_run.py push           # sube entrenar_en_kaggle.py y lo lanza con GPU
python3 push_and_run.py estado         # status + ultimas lineas del log; repetir hasta COMPLETE
python3 push_and_run.py log            # log completo
python3 push_and_run.py bajar ./salida # descarga los ficheros de /kaggle/working/
```

**Antes de relanzar para una versión nueva (v5, v6...)**: cambiar `VERSION` al principio de
`entrenar_en_kaggle.py` (una sola línea — el nombre del adapter, del zip y del log de evaluación
se derivan de ahí solos) y `SLUG`/`req.new_title` en `push_and_run.py`; asegurarse de que
`data/*.jsonl` ya está regenerado con las reglas de esa versión y commiteado **antes** de subir,
porque `entrenar_en_kaggle.py` clona el repo de GitHub, no usa los ficheros locales.

`push_and_run.py push` usa el usuario y el slug fijados al principio del fichero (`USUARIO`,
`SLUG`) — **ajustarlos** si se relanza con otra cuenta o para otro experimento. Nota real de esta
sesión: Kaggle ignora el slug pedido en el *primer* push de un kernel **nuevo** y lo deriva del
título (con un límite duro de **50 caracteres** en el título); el slug real es el que devuelve
`push()` en la URL — hay que copiarlo a la constante `SLUG` antes de poder consultar `estado`. Un
push a un kernel que ya existe (misma versión, relanzar tras un fallo) sí respeta el slug.

`entrenar_en_kaggle.py` (lo que se sube y corre en Kaggle) clona el repo en una carpeta temporal
**fuera** de `/kaggle/working/` (si se clona dentro, Kaggle trata el repo entero — miles de
ficheros — como "salida del kernel"), instala `requirements.txt`, quita `torchao` (mismo
problema que en Colab, pero aquí no hace falta reiniciar nada porque cada paso corre en un
subproceso nuevo), regenera `data/*.jsonl` (determinista, misma semilla — reproduce lo que ya
está en el repo, para la versión que esté commiteada), entrena (`entrenar_lora.py`, ~20-25 min en
T4/P100) y evalúa en el test set (`evaluar_modelo.py --sin-zero-shot --sin-1207`). Al final copia
a `/kaggle/working/` (lo que `push_and_run.py bajar` descarga):

- `florence2_base_lora_<VERSION>.zip` — el adapter entrenado (con `resultados_entrenamiento.json`
  y `evaluacion_test_<VERSION>.txt` ya dentro), para descomprimir en
  `experimentos/vlm_atributos_prenda/modelos/florence2_base_lora_<VERSION>/`.
- `resultados_entrenamiento.json` y `evaluacion_test_<VERSION>.txt` sueltos también, por comodidad.

No corre la comparación con las 1207 imágenes de `clip_trend_matching/` (`--sin-1207`): usa
`open_clip`, que no está en `requirements.txt` de esta carpeta; se puede correr aparte después
con `evaluar_solape_1207.py` si hace falta.

`diag_internet.py` es un kernel mínimo (sin GPU) que solo comprueba conectividad a pypi.org,
github.com y huggingface.co — para aislar problemas de internet/verificación de cuenta sin
esperar a que falle el entrenamiento real.
