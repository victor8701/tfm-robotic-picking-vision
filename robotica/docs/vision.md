# Visión: manual paso a paso para probar

Este manual es para probar la visión **sin saber nada de visión**. Cada prueba dice qué necesitas, qué escribir, qué tienes que ver y qué hacer si no sale. Empieza por la Prueba 1 y sigue en orden: cada una es un poco más difícil y más cercana a la celda real.

## 0. Qué hace, en dos frases

Una cámara hace una foto de la caja y el programa calcula **dónde está** (x, y), **cuánto mide** (largo, ancho, alto) y **cuánto está girada**, en milímetros y con los ejes del robot. Para pasar de píxeles de la foto a milímetros del robot necesita saber dónde está la cámara: a eso se le llama **calibrar**.

Hay dos programas que usarás:

| Programa | Para qué |
|---|---|
| `vision.probar_en_casa` | Mide las cajas de unas fotos y dibuja el resultado. Es el que más vas a usar. |
| `vision.ver_camara` | Abre tu webcam y enseña en vivo lo que el programa identifica (contorno, centro e hilo de la caja), sin robot. Prueba 11. |
| `calibracion.app_camara` | **Asistente con ventana para calibrar la cámara** paso a paso (tablero, fotos, posición, prueba y guardar). Prueba 12. |
| `calibracion.camara` | Calibra la cámara (le dice al programa dónde está y cómo es su objetivo). |

Y uno de ayuda: `vision.generar_ejemplos`, que fabrica fotos falsas con respuesta conocida para comprobar que todo funciona.

## 1. Antes de empezar (2 minutos, una vez)

**Dónde se escribe.** En la terminal de **Ubuntu (WSL)**: la ventana negra cuyo texto empieza por `ubuntu22@DESKTOP-...`. Se abre buscando «Ubuntu» en el menú de Windows. Todos los comandos de este manual son para esa terminal. (Para una prueba, `--interactivo`, hace falta PowerShell: se avisa en su sitio.)

**Cada comando se escribe desde la carpeta `robotica`.** Por eso cada bloque de este manual empieza con un `cd`: así se puede copiar entero en una ventana nueva.

**Comprueba que está todo instalado:**
```bash
python3 -c "import cv2, numpy; print('OpenCV', cv2.__version__)"
```
Tiene que escribir algo como `OpenCV 4.13.0`. Si da «No module named cv2», instala con `pip install opencv-python numpy` y repite.

**Cómo ver las imágenes que salen.** Los programas guardan sus resultados en la carpeta `resultados_vision`. Para abrirla en el Explorador de Windows:
```bash
explorer.exe resultados_vision
```
(Sin la terminal, la ruta es `\\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica\resultados_vision`.) Cada vez que lances `probar_en_casa`, esa carpeta se rellena otra vez: lo anterior se sobrescribe, así que copia lo que quieras guardar.

## 2. Seis palabras que salen en todas partes

- **Tablero:** una hoja impresa con cuadros blancos y negros (un tablero de ajedrez) de tamaño conocido. Sirve de regla: como el programa sabe lo que mide cada cuadro, saca la escala de la foto.
- **Calibrar:** decirle al programa dónde está la cámara y cómo es su objetivo. Se hace una vez, al montar la cámara.
- **Modo `color`:** encuentra la caja por su color de cartón marrón. Es el que se usa si no dices otra cosa. **Depende del color**: si el fondo se parece a la caja, falla.
- **Modo `fondo`:** compara la foto con otra foto de la misma escena **sin caja**. No depende del color de la caja.
- **Modo `profundidad`:** usa un mapa de distancias (de una cámara de profundidad) y detecta lo que sobresale de la cinta. No depende del color ni de la luz. Necesita ese mapa.
- **Alto de la caja:** una foto cenital no ve cuánto de alta es la caja; hay que dársela (`--alto`) o sacarla de la profundidad.

## 3. Qué prueba hago

| Prueba | Para qué sirve | Necesitas | Tiempo |
|---|---|---|---|
| **1. Ver que funciona** | Comprobar que todo está instalado y entender la salida | Nada | 5 min |
| **2. Tus fotos, sin tablero** | Ver si el programa encuentra tus cajas | Tus fotos | 5 min |
| **3. Medir cajas de verdad** | Ver cuánto se equivoca midiendo | Tablero impreso, regla, móvil | 30 min |
| **4. Caja del color del fondo** | Que funcione aunque la caja se parezca al suelo | La prueba 3 + una foto sin caja | 15 min |
| **5. Ajustar el color a tu caja** | Cajas que no son de cartón marrón | Tus fotos, PowerShell | 10 min |
| **6. Ensayar la calibración** | Ver cómo se calibra y qué debe salir | Nada | 5 min |
| **7. Calibrar tu cámara en casa** | Calibrar con una regla en vez del robot y medir la precisión de todo | Tablero, regla, móvil fijo | 1 h |
| **8. Pruebas automáticas** | Comprobar que no se ha roto nada | Nada | 3 min |
| **9. En el laboratorio** | La calibración de verdad, con el robot | Cámara montada, robot | 1–2 h |
| **10. Ciclo completo con cámara** | El PC lee la cámara y mueve el robot | RobotStudio (avanzada) | 1 h |
| **11. Ver tu webcam en vivo** | Ver lo que ve la cámara y lo que identifica (contorno, centro, hilo), sin robot | Webcam, Windows | 5 min |
| **12. Calibrar tu cámara con el asistente** | Medidas y posiciones reales en el robot, con una ventana que te guía | Tablero impreso, regla, webcam fija, Windows | 20 min |

---

## Prueba 1. Ver que funciona

**Qué haces:** creas fotos falsas con respuesta conocida y compruebas que el programa acierta.

**Pasos:**

1. Crea las fotos de ejemplo (tarda unos 10 segundos):
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m vision.generar_ejemplos ejemplos_vision
```
Crea la carpeta `ejemplos_vision` con fotos de una mesa, un tablero y una caja (`casa/`), la misma mesa sin caja (`fondo.png`), fotos de una cámara de celda (`celda/`), fotos para calibrar (`calibracion/`) y `verdad.csv`, que dice lo que mide cada caja de verdad.

2. Mide las 5 fotos de `casa`:
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m vision.probar_en_casa ejemplos_vision/casa --tablero 9x6 --cuadro 25 --fov 62 --modo profundidad
```

3. Mira la respuesta correcta para comparar:
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
cat ejemplos_vision/verdad.csv
```

**Qué tienes que ver:** una tabla como esta, y debajo `5 de 5 fotos con caja`:
```
                    imagen    largo  ancho   alto   giro       x       y  conf  notas
              casa_01.png *   199.8  139.7  120.7   -0.0   400.3   -60.1  1.00
              casa_02.png *   200.0  140.0  120.7   25.0   410.2   -70.2  0.99
```
Cada fila es una foto. Compara con `verdad.csv`: el largo y el ancho tienen que coincidir en menos de 1 mm (200 × 140 la primera, 200 × 140 la segunda…). Si coincide, **todo funciona**. Cómo se lee la tabla está en el apartado 4.

**Si no sale:** si dice `No module named cv2`, mira el apartado 1. Si dice `no existe ejemplos_vision/casa`, falta el paso 1.

## Prueba 2. Tus fotos, sin tablero

**Qué haces:** pasas tus fotos por el programa para ver si encuentra la caja. Como tus fotos no tienen tablero, no hay escala exacta: los milímetros son **aproximados**, pero ves si la detecta y cómo está girada.

**Antes:** pon tus fotos en una carpeta, por ejemplo `ejemplos_vision/planta_real_prueba`. **Saca de ahí** las imágenes que no son fotos (capturas con la máscara o las detecciones del programa anterior): confunden.

**Pasos:**
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m vision.probar_en_casa ejemplos_vision/planta_real_prueba --altura-camara 1000 --fov 70 --alto 200
```
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
explorer.exe resultados_vision
```
Qué significan los números que puse:
- `--altura-camara 1000`: se supone que la cámara mira justo hacia abajo a 1000 mm (1 metro) de la superficie. **Pon la altura real**, medida con una cinta.
- `--fov 70`: el campo de visión horizontal de la cámara, en grados. Un móvil suele estar entre 65 y 80.

En esta prueba la altura y el campo de visión **mandan directamente en los milímetros**: si te equivocas un 10 % en la altura, los mm salen un 10 % mal. Por eso los números son orientativos; lo importante es ver si encuentra la caja. Con tablero (Prueba 3) no pasa.
- `--alto 200`: el alto de la caja, en milímetros.

**Qué tienes que ver:** en las imágenes `*_anotada.png`, un rectángulo alrededor de cada caja detectada, una cruz en el centro, una flecha por el lado largo y las medidas. En la tabla, la caja elegida lleva un `*`.

**Cómo saber si salió bien:**
- El rectángulo rodea la caja de verdad: **bien**.
- El rectángulo es casi toda la foto y la nota dice «ocupa el 50 % de la foto: el fondo se parece al color de la caja»: **mal**. El fondo (un suelo de madera, por ejemplo) tiene el color del cartón. Pasa a la Prueba 4.
- El rectángulo es rojo y pone `RECORTADA`: la caja toca el borde de la foto. Haz la foto con la caja entera.

## Prueba 3. Medir cajas de verdad

**Qué haces:** haces fotos de una caja con un tablero impreso al lado, y comparas lo que mide el programa con lo que mides tú con una regla. Es la prueba que dice cuánto se equivoca de verdad.

**Qué necesitas:** una impresora, una regla, un móvil, una caja que puedas medir y una superficie lisa de color distinto al de la caja (una mesa gris, una hoja blanca grande).

**Pasos:**

1. Crea el tablero para imprimir:
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m calibracion.camara tablero --columnas 9 --filas 6 --cuadro 25 --salida tablero.png
```
2. Imprime `tablero.png` **al 100 %** (en el cuadro de impresión de Windows, elige «tamaño real» o «100 %», **no** «ajustar a la página»). Pégalo sobre cartón o algo rígido: tiene que quedar **plano y sin arrugas**.
3. Con una regla, mide el lado de **un cuadro** del tablero impreso en milímetros. Debería estar muy cerca de 25. **Apunta tu valor medido**: es tu `--cuadro`.
4. Mide la caja con la regla: largo, ancho y alto en mm. Apúntalos.
5. Coloca el tablero y la caja **sobre la misma superficie**, a unos 5 cm el uno del otro (que no se toquen ni se tapen). Haz varias fotos **desde arriba, lo más vertical que puedas**, a 60–100 cm, con el tablero y la caja enteros en la foto, con luz pareja y sin brillos. Cambia la caja de sitio o de giro entre foto y foto.
6. Pasa las fotos al ordenador y ponlas en una carpeta, por ejemplo `ejemplos_vision/mis_fotos`.
7. Mídelas (cambia `25` por tu `--cuadro`, `120` por el alto de tu caja y `300,200` por su largo y ancho):
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m vision.probar_en_casa ejemplos_vision/mis_fotos --tablero 9x6 --cuadro 25 --fov 70 --alto 120 --esperado "300,200"
```

`--fov 70` es el campo de visión horizontal del móvil (65–80 °). Aquí no hace falta que sea exacto: en las pruebas con fotos de ejemplo, equivocarse 8–18 ° cambia las medidas unos pocos por ciento.

**Qué tienes que ver:** en la columna de notas, el error de cada foto (`error largo +3.1 ancho -1.2 mm`). Con la caja cerca del centro de la foto, un error de pocos milímetros es normal; si la caja está en una esquina de la foto, puede llegar a una decena porque la cámara ve la pared lateral (la nota `pared ~X mm` lo avisa).

**Si no sale:**
- «No veo el tablero»: el tablero tiene que salir **entero**, enfocado y sin brillos. Y las esquinas se cuentan por dentro: un tablero de 10×7 cuadros tiene 9×6 esquinas.
- Los errores son de 20 mm o más con la caja bien detectada: revisa que midas bien el `--cuadro` (con regla, no el valor que pone el programa) y que la foto sea cenital.

## Prueba 4. Caja del color del fondo

**Qué haces:** haces que el programa funcione aunque la caja se parezca al suelo, comparando la foto con otra igual **sin caja**.

**Pasos:**

1. Fija el móvil (apóyalo en una pila de libros o un trípode). **No lo muevas** mientras hagas las fotos.
2. Con el tablero en la mesa, haz una foto **sin caja** y llámala `fondo.jpg`.
3. Sin mover nada, haz las fotos **con la caja** (el tablero sigue ahí).
4. Pon `fondo.jpg` en una carpeta **distinta** de la de las fotos de cajas, por ejemplo `ejemplos_vision/fondo/`, y las fotos de cajas en `ejemplos_vision/mis_fotos_fondo/`.
5. Mide:
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m vision.probar_en_casa ejemplos_vision/mis_fotos_fondo --tablero 9x6 --cuadro 25 --fov 70 --alto 120 --modo fondo --fondo ejemplos_vision/fondo/fondo.jpg --esperado "300,200"
```
**Qué tienes que ver:** el rectángulo de cada foto sobre la caja, como en la Prueba 3. Para comprobar que el modo no depende del color, prueba también con una caja de otro color.

**Si no sale:** las fotos tienen que ser del **mismo tamaño** que el fondo y con la cámara en el mismo sitio; si no, dirá «la foto de fondo mide … y la imagen …». Un cambio grande de luz entre la foto del fondo y las demás también estropea el resultado.

Para probar con las fotos de ejemplo (que traen su propio fondo):
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m vision.probar_en_casa ejemplos_vision/casa --tablero 9x6 --cuadro 25 --fov 62 --alto 120 --modo fondo --fondo ejemplos_vision/fondo.png
```

## Prueba 5. Ajustar el color a tu caja

**Qué haces:** si tu caja no es de cartón marrón, o el modo `color` no la encuentra, ajustas el rango de color con unas barras deslizantes y lo guardas.

**Esta prueba se hace en PowerShell de Windows** (no en la terminal de Ubuntu), porque abre una ventana. **No he podido ejecutarla** (donde la preparé no hay pantalla): si falla, dime el mensaje.

**Pasos** (abre PowerShell y escribe, cambiando la ruta de la foto):
```
cd \\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica
& "C:\Program Files\Python311\python.exe" -m vision.probar_en_casa ejemplos_vision\mis_fotos --tablero 9x6 --cuadro 25 --fov 70 --alto 120 --interactivo --guardar-params ajuste.json
```
(La primera vez: `& "C:\Program Files\Python311\python.exe" -m pip install opencv-python numpy`.)

Se abre una ventana con la primera foto. La parte **verde** es lo que el programa cree que es caja. Mueve las barras (H, S, V, mínimo y máximo) hasta que el verde cubra solo la caja. Pulsa **Intro** para aceptar (Esc cancela). El rango queda en `ajuste.json`. Para usarlo otra vez sin abrir la ventana:
```
cd \\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica
& "C:\Program Files\Python311\python.exe" -m vision.probar_en_casa ejemplos_vision\mis_fotos --tablero 9x6 --cuadro 25 --fov 70 --alto 120 --params ajuste.json
```

## Prueba 6. Ensayar la calibración

**Qué haces:** haces la calibración completa con datos que ya tienen la respuesta, para ver cómo se usa y qué tiene que salir. Antes hay que haber hecho la Prueba 1.

**Pasos:** (son tres comandos, uno detrás de otro)
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m calibracion.camara intrinsecos ejemplos_vision/calibracion/fotos_tablero --tablero 9x6 --cuadro 25 --salida ejemplos_vision/intrinsecos.json
```
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m calibracion.camara extrinsecos ejemplos_vision/calibracion/cinta.png --intrinsecos ejemplos_vision/intrinsecos.json --tablero 9x6 --cuadro 25 --z 220 --toca "0,0:600.0,-120.0" --toca "8,0:793.2,-68.2" --toca "0,5:632.4,-240.7" --valida "8,5:825.5,-189.0" --valida "4,2:709.5,-142.4" --salida ejemplos_vision/camara_calibrada.json --anotada ejemplos_vision/tablero_detectado.png
```
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m vision.probar_en_casa ejemplos_vision/celda --calibracion ejemplos_vision/camara_calibrada.json --z 220
```

**Qué tienes que ver:**
- Del primero: `12 fotos usadas, error de reproyección 0.02 px` y `campo de visión horizontal 62°`.
- Del segundo: `cámara en la base: x 690, y 5, z 870 mm`, `VALIDACIÓN: error 0.08 mm` y `criterio: objetivo`.
- Del tercero: las tres cajas de `celda/` medidas y colocadas en la base del robot, con la posición a 1 mm de `verdad.csv`.

**Qué es cada cosa** (para entender la Prueba 7 y la 9): el primer comando averigua cómo es el objetivo de la cámara con 12 fotos del tablero. El segundo averigua **dónde está la cámara**: con el tablero sobre la cinta, se «tocan» esquinas con el robot y se dicen sus coordenadas (aquí ya vienen puestas en `--toca`); las dos de `--valida` no se usan para ajustar, solo para comprobar. Abre `ejemplos_vision/tablero_detectado.png`: marca las esquinas (0,0), (8,0), (0,5) y (8,5) con sus índices, que son los números que se escriben en `--toca`.

## Prueba 7. Calibrar tu cámara en casa con una regla

**Qué haces:** el mismo proceso de la Prueba 6, pero con **tu móvil** y una **regla** en vez del robot. Te dice cuánto se equivoca el conjunto cámara + calibración + medida, que es lo que importa. En la celda, la regla se sustituye por la punta de la pinza.

**Pasos:**

1. **Intrínsecos.** Haz 12 a 20 fotos del tablero impreso con el móvil, desde distintos sitios e inclinaciones (de cerca, de lejos, de lado), con el tablero entero en cada una. Que el móvil no cambie de zoom ni de resolución. Ponlas en una carpeta, por ejemplo `ejemplos_vision/intr_movil`, y ejecuta:
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m calibracion.camara intrinsecos ejemplos_vision/intr_movil --tablero 9x6 --cuadro 25 --salida intrinsecos_movil.json
```
Bueno: error de reproyección por debajo de 0,5 px. Por encima de 1, repite las fotos (más nítidas).

2. **Tu propio «sistema de coordenadas».** Elige un punto de la mesa como origen (0, 0) y pégale una cruz de cinta. Decide el eje **x hacia la derecha** y el **eje y hacia el fondo** (alejándote de ti), mirando la mesa de frente. Los milímetros que midas serán esas x e y. (Si inviertes un eje, el programa avisa de que el tablero sale «reflejado».)

3. **Fija el móvil** mirando hacia abajo desde unos 70 cm (en un trípode o en un soporte). **No lo muevas más.** Pon el tablero plano en la mesa, entero en la foto, y haz **una foto**: `cinta.jpg`.

4. Con la regla, mide x e y (desde tu cruz) de **cinco esquinas del tablero**: (0,0), (8,0), (0,5) como esquinas para ajustar y (8,5) y (4,2) para validar. La esquina (0,0) es la de arriba a la izquierda **en la foto**. Para estar seguro del índice, haz primero la orden con cualquier coordenada: guarda `tablero_detectado.png` con los índices marcados.

5. Calibra (cambia las rutas y los números por los tuyos; `--z 0` porque la mesa es tu nivel cero):
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m calibracion.camara extrinsecos ejemplos_vision/cinta.jpg --intrinsecos intrinsecos_movil.json --tablero 9x6 --cuadro 25 --z 0 --toca "0,0:X,Y" --toca "8,0:X,Y" --toca "0,5:X,Y" --valida "8,5:X,Y" --valida "4,2:X,Y" --salida camara_casa.json --anotada tablero_detectado.png
```

6. **Mide la precisión de todo el conjunto.** Pon una caja en la mesa, con el móvil fijo en el mismo sitio, y haz fotos. Con la regla mide dónde está el **centro de la caja** (x, y) en tu sistema de coordenadas. Pasa la foto por el programa:
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m vision.probar_en_casa ejemplos_vision/fotos_caja --calibracion camara_casa.json --z 0 --alto 120 --esperado "300,200"
```

**Qué tienes que ver:** en el paso 5, `criterio: objetivo` (error de validación menor de 2 mm) o `aceptable` (menor de 5). Con una regla, `aceptable` ya es un buen resultado. En el paso 6, los `x` e `y` de la tabla tienen que coincidir con lo que mediste a mano, con un error de pocos milímetros.

**Si no sale:** `criterio: repetir` o «tablero reflejado» significan que un punto está mal medido o que el índice de una esquina está cruzado; mira `tablero_detectado.png` y repite el toque.

## Prueba 8. Pruebas automáticas

**Qué haces:** compruebas que el código no se ha roto. No hace falta entender nada: o pasan todas o no.
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/test_vision_camara.py tests/test_calibracion_camara.py tests/test_vision_casa.py tests/test_celda_percepcion.py
```
**Qué tienes que ver:** una línea final como `NN passed in 120.00s` (tarda unos 2 minutos). Si pone `failed`, dime cuáles.

## Prueba 9. En el laboratorio: calibrar con el robot

**Qué haces:** la Prueba 7, pero con el robot: en vez de la regla, la punta de la pinza toca las esquinas. Es la calibración de verdad.

**Qué necesitas:** la cámara montada y fija donde va a trabajar (mirando hacia abajo, encima de la recogida), el tablero impreso y pegado plano, y el FlexPendant.

**Pasos:**
1. **Intrínsecos:** igual que el paso 1 de la Prueba 7, pero con la **cámara de la celda** (en una carpeta, `fotos_tablero`).
2. Pon el tablero **boca arriba sobre la cinta**, entero en la imagen, y haz **una foto** (`foto_cinta.png`).
3. Con la pinza (o una punta fina en la brida) toca la esquina (0,0), la (8,0) y la (0,5) del tablero, y en el FlexPendant (Cartesiano, Base, sin herramienta) apunta los x e y de cada una. Después toca (8,5) y (4,2) para validar. Mide también la altura `z` de la superficie de la cinta: es la `zCinta` de la app.
4. Calibra, con tus números:
```bash
cd /home/ubuntu22/repos/tfm-robotica-bimanual/robotica
python3 -m calibracion.camara extrinsecos foto_cinta.png --intrinsecos intrinsecos.json --tablero 9x6 --cuadro 25 --z 220 --toca "0,0:X,Y" --toca "8,0:X,Y" --toca "0,5:X,Y" --valida "8,5:X,Y" --valida "4,2:X,Y" --salida camara.json --anotada tablero_detectado.png
```
**Qué tienes que ver:** `criterio: objetivo` (menos de 2 mm). Si sale `aceptable` (2 a 5 mm), vale para empezar. Con `repetir`, vuelve a tocar los puntos.
5. Comprueba con cajas reales sobre la cinta (Prueba 7, paso 6, con `--calibracion camara.json --z 220`) y compara con la posición real del TCP sobre la caja.

## Prueba 10. Ciclo completo con cámara (avanzada)

**Esto no lo he probado en RobotStudio.** Es el PC leyendo la cámara y moviendo el robot en el modo **Real**. Antes de nada, el ciclo completo en simulación (Paso 8 del manual de RobotStudio) tiene que funcionar.

**Qué haces:** en vez de una cámara de verdad, el PC lee fotos de una carpeta (las de ejemplo de `celda/`), una por cada caja.

**Ya hay una configuración hecha:** `celda/config_celda_real_casa.json` (modo Real, 3 cajas y las fotos de ejemplo como cámara). Con ROS 2 se usa sin editar nada: los comandos, en el manual de RobotStudio, paso 11, «Primera prueba del modo Real en casa». Lo de abajo es la forma manual, con el ciclo de Python de Windows.

**Pasos:**
1. Abre `\\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica\celda\config_celda_windows.json` y pon `"modo_simulacion": false` y esta sección `camara` (las rutas son relativas a esa carpeta `celda\`):
```json
"camara": {
  "calibracion": "../ejemplos_vision/celda/camara.json",
  "origen": {"tipo": "carpeta", "ruta": "../ejemplos_vision/celda"},
  "modo": "profundidad"
}
```
2. En la app del FlexPendant: **Real**, 3 cajas, y en la pestaña **Parámetros → Recogida**: Posición de la caja = **Cámara**, `recogidaX` = 700, `recogidaY` = 0, zona permitida ±50 y ±50, y `zCinta` = 220.
3. Arranca como en el Paso 8 (puente, PC, Play) y pulsa **CAJA EN POSICIÓN** en cada caja.

**Ventana del PC y carpeta desde la app:** con `"visor": true` se abre una ventana en tiempo real con la foto, el contorno de la caja, el centro (punto verde con sus coordenadas) y el hilo de lado corto a lado corto por el centro; con `"raiz_carpetas"` la app deja elegir la carpeta de fotos (manual de RobotStudio, paso 11). La imagen anotada de `probar_en_casa` lleva ahora el mismo hilo y el mismo punto verde.

**Qué tienes que ver:** el PC escribe `Celda: caja 1 de 3 (` con las medidas de la caja (200 × 140 × 120 mm, con algún decimal de más) y su giro, y el robot va al punto de la caja; la 2 y la 3 con sus propias medidas (200 × 140 con giro de −45°, y 160 × 100 × 90 con giro de 60°).

**Si no sale:** el PC se para con un mensaje claro. «La cámara no ve ninguna caja entera» = no hay más fotos en la carpeta o la caja no se detecta; «fuera de la zona permitida» = la caja está lejos de `recogidaX/Y`. Más mensajes en el apartado 5. Con una cámara de verdad, el `origen` es `{"tipo": "realsense"}` (necesita `pip install pyrealsense2`) o `{"tipo": "opencv", "indice": 0}` (cámara USB, sin profundidad: entonces hay que dar el `alto_mm` de las cajas y usar `"modo": "color"`). **La RealSense está sin probar.**

---

## Prueba 11. Ver tu webcam en vivo
**Qué haces:** abres la webcam del PC y ves en una ventana, en tiempo real, lo que ve y lo que el programa considera la caja: el contorno, el centro (punto verde con sus coordenadas en mm), el **hilo** (una línea de un lado corto al otro, por el centro) y las medidas. No hace falta robot, RAPID ni la app. Es el paso previo a usar la cámara en la celda.

**Dónde:** en **Windows** (WSL2 no ve las cámaras USB). **Windows (PowerShell)**, desde la carpeta `robotica`:
```
cd \\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica
```
1. Mira qué cámaras hay y cuál es cuál. Dice las que ve Windows y los índices que abren, y con `--ver` abre una ventana con la imagen de cada una (se cierra con cualquier tecla). Una cámara con infrarrojos (Windows Hello) sale como dos índices: una en color y otra en blanco y negro:
```
& "C:\Program Files\Python311\python.exe" -m vision.ver_camara --listar --ver
```
**Portátil con webcam externa:** el índice 0 suele ser la cámara frontal del portátil (y el 1, su infrarroja). Si la webcam externa **no sale** (en «Windows tiene conectadas» solo aparece la del portátil, p. ej. `USB2.0 HD IR UVC WebCam (x2)`), Windows no la ve: conéctala por USB (mejor directa al PC, sin hub), espera unos segundos y repite; debe salir otro índice (2, 3...). Con ese número: `--indice <número>`.
2. Ábrela (pon el `--indice` de la webcam que quieras, el que salió en el paso 1; `--alto` es el alto de tu caja en mm, porque una webcam no mide profundidad):
```
& "C:\Program Files\Python311\python.exe" -m vision.ver_camara --indice 0 --alto 120
```
**Qué tienes que ver:** la imagen de la cámara con una banda arriba («camara USB | VISTA PREVIA | SIN CALIBRAR: mm aproximados»). Pon una caja de cartón marrón sobre una superficie lisa, mirando la cámara desde arriba: debe salir su contorno amarillo, el punto verde en el centro y el hilo de extremo a extremo por el centro. Se sale con la tecla `q` o cerrando la ventana.

**Cuántas cajas identifica:** `--cajas N` (1 por defecto) limita a las N mejores (la mayor o, en la celda, la más cercana al punto de recogida); lo demás de la imagen, que suele ser ruido, no se marca. Con `--cajas 3` salen hasta tres.

**Sin calibrar:** se supone una cámara mirando hacia abajo a `--altura` mm (600 por defecto) de la mesa y `--fov` grados de campo de visión (62). Contorno, centro e hilo valen; los **mm son aproximados** (ajusta `--altura` a la tuya). Para medir de verdad hay que calibrarla (Prueba 7) y darla con `--calibracion camara.json --z <altura de la superficie>`.

**Si no sale:**
- «no puedo abrir la cámara»: otro programa la usa (Teams, Zoom, la app Cámara), Windows no deja a las aplicaciones de escritorio usarla (Configuración → Privacidad → Cámara) o el índice no es el bueno (`--listar`). Con `--api dshow` o `--api msmf` se prueba el otro backend de Windows.
- «no veo ninguna caja entera» en rojo: la caja está cortada por el borde de la imagen o el color no es el del cartón marrón (el rango de color se ajusta como en la Prueba 5).

**Usarla en la celda (ciclo de Python de Windows, sin ROS 2):** `celda/config_celda_real_webcam.json` trae la webcam, el modo color, el alto de la caja (`alto_mm`) y el visor, con una calibración aproximada `celda/camara_webcam.json` (cámara a 600 mm de la cinta). La cámara se elige al lanzar la celda con `--indice N` (0 = la del portátil, 1 = la webcam externa; los números de `--listar --ver`). Para ajustarla a tu altura: `... -m vision.ver_camara --altura 700 --guardar-calibracion celda\camara_webcam.json --z 220 --centro 700,0`. Esa cámara aproximada centra la imagen en la recogida (700, 0) del robot: una caja bajo el centro de la imagen es una caja en la recogida y, al moverla en la imagen, el robot va a ese punto (con la escala aproximada). En la app, recogida en modo **Cámara** con una zona permitida que cubra lo que muevas la caja. Cada caja se coge una a una (la pones y pulsas CAJA EN POSICIÓN). Los pasos, en el manual de RobotStudio, paso 11.

---

## Prueba 12. Calibrar tu cámara con el asistente (ventana)
**Qué haces:** calibras la webcam con una ventana que te guía paso a paso y deja el `camara.json` que usa la celda: con él, las medidas y las posiciones salen **reales** (en mm del robot) y no aproximadas. Necesitas el tablero impreso, una regla y la webcam FIJA donde va a trabajar. No hace falta el robot: en casa decides qué punto del robot es el centro del tablero.

**Dónde:** en **Windows** (la ventana usa Tkinter, que ya trae tu Python). **Windows (PowerShell)**, desde la carpeta `robotica` (`--indice` es el número de tu webcam, el de `--listar --ver`; la ventana también tiene el botón «¿Cuál es cuál?»):
```
cd \\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica
```
```
& "C:\Program Files\Python311\python.exe" -m calibracion.app_camara --indice 1 --tam 1280x720 --salida celda\camara_webcam.json
```
Se abre una ventana con la cámara en vivo a la izquierda y cuatro pestañas a la derecha:
1. **Tablero:** pulsa «Guardar tablero para imprimir…», imprímelo **al 100 %** (sin «ajustar a la página») y pégalo en algo plano y rígido. **Mide con la regla el lado de un cuadro** de tu impresión y escríbelo (en mm) en «Cuadro»; pulsa «Aplicar el tablero».
2. **Cámara (intrínsecos):** con el tablero entero en la imagen, guarda **unas 15 fotos** (Espacio o el botón; o marca «Automático» y se guarda sola cada vez que el tablero se queda quieto), **moviéndolo e inclinándolo** (como una hoja medio levantada) y llevándolo a los bordes y a las esquinas. El contador te dice cuántas llevas, cuántas zonas de la imagen cubres y qué falta. Pulsa «Calcular los intrínsecos»: debe salir **«muy bien»** (error por debajo de 0,5 píxeles) o «aceptable»; si no, repite con más fotos y más variadas. (Atajos: «Usar los intrínsecos de un camara.json anterior…» si solo has movido la cámara, o el campo de visión si no quieres hacer fotos, menos preciso.)
3. **Posición:** **no muevas la cámara a partir de aquí.** Tiende el tablero **plano** sobre la superficie donde irán las cajas, entero en la imagen. En casa deja «En casa» con el **centro del tablero en 700, 0** (la recogida), giro 0 (derecho en la imagen) y altura z = 220 (la de la cinta en RobotStudio), y pulsa «Calcular la posición de la cámara». Sale dónde está la cámara y el error de validación: **OBJETIVO** (< 2 mm) o ACEPTABLE (< 5 mm); con REPETIR, revisa que el tablero esté bien tendido y entero. Con el robot, en vez de eso, se tocan esquinas con el TCP y se escriben («columna,fila:x,y», una por línea).
4. **Probar y guardar:** pon una caja en esa superficie: debe salir su contorno, el centro con sus coordenadas en el robot, el hilo y las medidas (pon su alto en «Alto de la caja»). Pincha en la imagen para ver las coordenadas de ese punto. Si es lo que esperas, **«Guardar la calibración»**: queda en `celda\camara_webcam.json`, que es el que usa `config_celda_real_webcam.json`.

**Después:** ya no es una cámara «aproximada»: la caja medida tiene tamaño y posición reales en el robot. En la app del FlexPendant, recogida en modo **Cámara** (zona permitida de 50 a 150 mm) y la celda con `... -m celda.ciclo celda\config_celda_real_webcam.json --indice 1`. Para verla antes: `... -m vision.ver_camara --indice 1 --calibracion celda\camara_webcam.json --z 220 --alto 120`.

**Si no sale:** «no puedo abrir la cámara» (otro programa la usa, índice equivocado: «¿Cuál es cuál?»); «no veo el tablero entero» (que salga completo, sin brillos ni reflejos, enfocado y con buena luz); la resolución de la ventana tiene que ser la de la celda (`origen.tam` del JSON).

---

## 4. Cómo leer los resultados

**La tabla** (una fila por caja detectada, la elegida lleva un `*`):

| Columna | Qué es |
|---|---|
| `largo`, `ancho`, `alto` | Medidas de la caja en mm. El largo es siempre el lado mayor. |
| `giro` | Cuánto está girada, en grados, entre −90 y 90. Mide el lado largo, desde el eje x, hacia la izquierda visto desde arriba. 0 = el lado largo va a lo largo de x. |
| `x`, `y` | Dónde está el centro de la tapa, en mm. En casa son respecto a la esquina (0,0) del tablero; con la calibración de la celda, respecto a la base del robot. |
| `conf` | De 0 a 1: lo rectangular que es la mancha y si se ve entera. Por debajo de 0,5, desconfía. |
| `notas` | Avisos: `RECORTADA` (toca el borde de la foto), `pared ~X mm` (la pared lateral puede inflar la medida), `ocupa el X %` (el fondo se parece a la caja). |

**La foto anotada** (`*_anotada.png`, en `resultados_vision`): contorno de la tapa, en **amarillo** la caja elegida, en **verde** las demás y en **rojo** las recortadas; una cruz en el centro, una flecha por el lado largo y las medidas escritas.

**Los ficheros CSV** (en `resultados_vision`): `detecciones.csv` tiene todas las cajas con todos sus datos, y `caja_vision.csv` una caja por foto en el formato `largo;ancho;alto;giro` de `caja.csv`, para alimentar la simulación con medidas reales.

**El código de salida:** 0 si todas las fotos tienen caja, 1 si alguna no, 2 si falta algún dato.

## 5. Problemas típicos

| Pasa esto | Qué hacer |
|---|---|
| `No module named cv2` | `pip install opencv-python numpy` |
| El programa solo muestra ayuda y «Falta la orden» o «Falta la foto o la carpeta» | Te falta la orden o la carpeta de fotos: copia el comando de la prueba |
| «no veo el tablero de 9x6 esquinas» | El tablero debe salir entero, enfocado, sin brillos. Las esquinas son las de dentro: 10×7 cuadros = 9×6 esquinas |
| «no encuentro ninguna caja» | El color no es el del cartón: Prueba 5 (`--interactivo`) o Prueba 4 (`--modo fondo`) |
| «ocupa el 50 % de la foto» | El fondo se parece a la caja: `--modo fondo`, otro fondo o profundidad |
| `RECORTADA` | La caja toca el borde de la foto: encuádrala entera |
| Con `--modo profundidad` no encuentra la caja | El `--fov` (o los intrínsecos) tiene que ser el de la cámara que hizo el mapa de profundidad: con uno equivocado, las alturas salen mal y no ve nada sobresalir |
| Dos cajas salen como una | Están a menos de 3 cm: sepáralas |
| La foto no se lee | Formatos válidos: png, jpg, jpeg, bmp, tif. Si es `.heic` o `.webp`, conviértela |
| Con tablero, mide mal | Mide a mano el cuadro impreso y usa ese valor en `--cuadro`; haz la foto más vertical |
| `calibracion.camara`: «criterio: repetir» | Un punto tocado mal: mira `tablero_detectado.png` y repite el toque |
| «el tablero reflejado» | Los ejes que has usado son un espejo (x a la derecha e y hacia ti): usa x a la derecha e y al fondo |
| PowerShell: error con `--toca 0,0:...` | Los valores con coma van **entre comillas**: `--toca "0,0:600,-120"` |
| El PC se para: «la cámara no ve ninguna caja entera en N s» | La caja no se ve entera o es de otro color; el tiempo es el de la app (Parámetros → Tiempos) |
| El PC se para: «fuera de la zona permitida» | La caja está más lejos del punto de recogida que la zona de la app: acércala o amplía la zona |

## 6. Qué NO está probado

- **Solo se ha probado con imágenes sintéticas** (dibujadas por el propio programa): la cámara se coloca con 0,1 mm de error y la caja se mide a 1 mm con profundidad. **No hay medidas con una cámara ni con cajas reales.** La Prueba 3 y la Prueba 7 son las que lo miden de verdad.
- La **RealSense** (`pyrealsense2`) está escrita pero sin probar, igual que `--interactivo` y la Prueba 10.
- Con **color o fondo**, si la caja está lejos del centro de la foto o la cámara no es cenital, la pared lateral infla la medida unos mm (con profundidad no). Monta la cámara justo encima de la recogida.
- Una caja con las **solapas abiertas** da un rectángulo que incluye las solapas; con la caja cerrada mide el cuerpo.
- Una cinta que **se mueve** o tiene dibujo estropea el modo `fondo`; el modo `profundidad` lo evita.
- Para las pruebas del PC con la cámara, **una caja por imagen**; agarrar al vuelo una caja en movimiento no está hecho.

## 7. Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Programa de pruebas | `vision/probar_en_casa.py` |
| Programa de calibración | `calibracion/camara.py` |
| Fotos de ejemplo | `vision/generar_ejemplos.py` (crea `ejemplos_vision/`) |
| Detección de la caja | `vision/deteccion.py` |
| Modelo de cámara | `vision/camara.py` |
| La cámara dentro del ciclo del PC | `celda/percepcion.py` (`FuenteCamara`) |
| Conectarla a la celda | Paso 11 del manual de RobotStudio y Prueba 10 de este manual |
