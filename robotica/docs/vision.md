# Visión de la celda: calibración y pruebas en casa

La cámara da a la celda lo que en simulación sale de `caja.csv`: para cada caja, el **largo, el ancho, el alto, el giro y la posición (x, y) en la base del robot**. El PC lo lee con `FuenteCamara` (`celda/percepcion.py`) cuando la app está en **Real**. Todo el código está en `vision/` (modelo de cámara, tablero, detección) y `calibracion/camara.py` (programa de calibración).

**Montaje que se supone:** una cámara FIJA, mirando hacia abajo (cenital), encima del punto de recogida, con la caja entera en la imagen. Con la cámara justo sobre la caja, la medida es la mejor (ver «Límites»). La detección no vale para una cámara en la muñeca.

| Programa | Para qué | Cuándo |
|---|---|---|
| `python3 -m calibracion.camara` | Imprime el tablero, calibra la cámara (intrínsecos) y la coloca en la base del robot (`camara.json`). | Puesta en marcha, una vez por montaje. |
| `python3 -m vision.probar_en_casa` | Mide las cajas de fotos guardadas y dibuja el resultado. | En casa, sin robot; y en el laboratorio para comprobar la calibración. |
| `python3 -m vision.generar_ejemplos` | Crea fotos sintéticas con verdad conocida. | Para ver que los programas funcionan antes de tener fotos propias. |

Se ejecutan desde `robotica/` (en Windows, PowerShell, con `pip install -r requirements.txt`; `pip install pillow` solo para que el tablero salga con la escala en el PNG).

## 1. Probar en casa con imágenes

### Con los ejemplos
```
python3 -m vision.generar_ejemplos ejemplos_vision
python3 -m vision.probar_en_casa ejemplos_vision/casa --tablero 9x6 --cuadro 25 --fov 62 --modo profundidad
python3 -m vision.probar_en_casa ejemplos_vision/casa --tablero 9x6 --cuadro 25 --fov 62 --alto 120 --esperado 200,140
python3 -m vision.probar_en_casa ejemplos_vision/celda --calibracion ejemplos_vision/celda/camara.json --z 220
```
Cada comando escribe en `resultados_vision/` las fotos anotadas (`*_anotada.png`), `detecciones.csv` y `caja_vision.csv`. `ejemplos_vision/verdad.csv` dice lo que mide cada caja.

### Con tus fotos
1. Imprime el tablero: `python3 -m calibracion.camara tablero --columnas 9 --filas 6 --cuadro 25 --salida tablero.png`. Imprímelo **al 100 %** y mide un cuadro con una regla: ese lado es el `--cuadro`.
2. Pon el tablero **apoyado en la misma superficie que las cajas** (mesa, suelo, cartón) y entero en la foto, junto a la caja y sin tapar. Haz las fotos desde arriba, lo más cenital que puedas, con luz pareja y la caja separada del tablero (y de otras cajas, al menos 3 cm).
3. Mide a mano largo, ancho y alto de la caja (para comparar).
4. `python3 -m vision.probar_en_casa fotos/ --tablero 9x6 --cuadro 25 --fov 65 --alto 120 --esperado 300,200`

El tablero da la escala, el origen (su esquina (0, 0), arriba a la izquierda) y la altura cero: las posiciones salen en mm en su marco (x a la derecha, y hacia arriba). `--fov` es el campo de visión **horizontal** de la cámara (unos 65–70° en un móvil; si lo tienes, `--intrinsecos` de la calibración mejora el resultado). El `--alto` es el de la caja. Sin él, hace falta un mapa de profundidad junto a la foto (`foto.npy`, en mm, alineado) y entonces cada caja lleva su alto medido.

**Cómo separa la caja del resto** (`--modo`):
- `color` (por defecto): rango HSV de cartón marrón. Si tu caja es de otro color o no la encuentra, `--interactivo` abre una ventana con barras (Intro acepta; `--guardar-params ajuste.json` guarda el rango y `--params ajuste.json` lo reutiliza) o se dan `--hsv-bajo H S V --hsv-alto H S V` (H de 0 a 180).
- `fondo`: se da una foto de la misma escena sin cajas (`--fondo`). No depende del color.
- `profundidad`: con mapa de profundidad; cuenta lo que sobresale del plano, así mide solo la tapa (la más exacta).

Lo que escribe: por foto, la imagen con la tapa en verde (amarilla la elegida, roja si toca el borde), el centro, una flecha por el lado largo y las medidas; `detecciones.csv` con todas las cajas y `caja_vision.csv` con una caja por foto en el formato `largo;ancho;alto;giro` de `caja.csv` (sirve de entrada de simulación con medidas reales). Código de salida: 0 todas las fotos con caja; 1 alguna sin caja o sin tablero; 2 datos incorrectos.

**Giro:** el del lado largo, en grados, antihorario visto desde arriba desde el eje x, entre −90 y 90 (como `giro` de `caja.csv`); si largo y ancho difieren menos de un 5 %, entre −45 y 45.

## 2. Calibración para la puesta en marcha

Hace falta: la cámara montada y fija donde va a trabajar, el tablero impreso (cuadro medido), poder llevar el TCP de la pinza (o una punta) a las esquinas del tablero y leer su x, y en la base del robot (FlexPendant, Cartesiano, Base, sin herramienta).

**Paso 1 · Tablero.** `python3 -m calibracion.camara tablero --columnas 9 --filas 6 --cuadro 25`. Una de las dos cuentas par y la otra impar (9×6, 7×4…): si no, el origen sería ambiguo.

**Paso 2 · Intrínsecos** (la distancia focal y la distorsión del objetivo; una vez por cámara y resolución). 12 a 20 fotos del tablero en distintas posiciones e inclinaciones, ocupando en alguna casi toda la imagen, en una carpeta:
```
python3 -m calibracion.camara intrinsecos fotos_tablero/ --tablero 9x6 --cuadro 25 --salida intrinsecos.json
```
Bueno: error de reproyección por debajo de 0,5 px; por encima de 1, repetir (código de salida 1). Mira las «peores fotos» y quita las desenfocadas. Mientras no se hagan, `--fov` en el paso 3 vale para empezar (la RealSense D435 tiene unos 69° de campo horizontal en color), con menos precisión.

**Paso 3 · Cámara en la base.** Con la cámara en su sitio, el tablero **tendido boca arriba sobre la cinta**, entero en la imagen y sin movimiento, una foto. Con el TCP se tocan **dos o más esquinas** y se anotan sus x, y en la base. Cada esquina se nombra por su columna y su fila: la (0, 0) es la de arriba a la izquierda en la foto. Conviene tocar **3 para ajustar y 2 más para validar**. Si no sabes qué índice es cuál, ejecuta el comando una vez: guarda `tablero_detectado.png` con las cuatro esquinas de las puntas marcadas.
```
python3 -m calibracion.camara extrinsecos foto_cinta.png --intrinsecos intrinsecos.json --tablero 9x6 --cuadro 25 \
    --z 220 --toca 0,0:700,-100 --toca 8,0:700,100 --toca 0,5:550,-100 --valida 8,5:550,100 --valida 4,2:625,0 --salida camara.json
```
`--z` es la altura de la superficie donde apoya el tablero (la **zCinta** de la app). El programa dice dónde queda la cámara en la base, el error de reproyección y, con `--valida`, el **error real de la cámara** en puntos que no usó para ajustar. Criterio: **objetivo** por debajo de 2 mm, **aceptable** por debajo de 5, **repetir** por encima (código de salida 1). Avisa si los puntos tocados no encajan con un tablero rígido, si encajan mejor con el tablero reflejado (índices cruzados) o si la cámara no mira hacia abajo.

**Paso 4 · Comprobarlo con fotos de verdad.** Con `camara.json`, fotos de cajas reales sobre la cinta y su medida a mano:
```
python3 -m vision.probar_en_casa fotos_cinta/ --calibracion camara.json --z 220 --alto 120 --esperado 300,200
```
Las posiciones tienen que salir en la base del robot (compáralas con el TCP sobre la caja). Ajusta el color o usa `--modo fondo` / `profundidad` hasta que el error de las medidas sea pequeño.

**Paso 5 · Conectarlo a la celda.** En `celda/config_celda.json` (la ruta del PC en Windows es `config_celda_windows.json`), una sección `camara`; las rutas relativas se toman desde la carpeta de ese JSON:
```json
"camara": {
  "calibracion": "camara.json",
  "origen": {"tipo": "realsense", "tam": [1280, 720], "fps": 15},
  "alto_mm": null,
  "modo": "profundidad"
}
```
- `origen`: `{"tipo": "carpeta", "ruta": "fotos"}` (imágenes guardadas, para ensayar el ciclo en casa), `{"tipo": "opencv", "indice": 0}` (cámara USB, sin profundidad) o `{"tipo": "realsense"}` (necesita `pip install pyrealsense2`).
- `alto_mm`: alto de las cajas si no se mide con profundidad (el mismo para todas); `null` si hay profundidad.
- `modo`, `hsv_bajo`, `hsv_alto`, `umbral_fondo`, `fondo`, `params`: como en las pruebas en casa.

En la app, pestaña **Parámetros**: **Recogida → Posición de la caja = Cámara** (solo en Real), el punto nominal `recogidaX/Y` (donde espera la pinza) y la **zona permitida** ±X, ±Y; la **corrección de cámara** (`camaraOffsetX/Y/Giro`) suma un ajuste fino a lo medido; **Tiempos → máximo esperando a la cámara**. Con **Fija**, el PC usa siempre `recogidaX/Y` y de la cámara solo toma las medidas y el giro. **Altura de la cinta** (`zCinta`) tiene que ser la `--z` de la calibración.

## 3. Cómo se comporta en la celda
Para cada caja el PC pide imágenes hasta ver una **entera** (no cortada por el borde) o agotar el tiempo máximo de la app; si no la ve, **se para con un aviso** y no usa el punto fijo. Si hay varias cajas en la imagen, coge la más cercana al punto de recogida. Después comprueba que el centro cae en la zona permitida (si no, no se mueve), que la pinza puede agarrarla (apertura, alto mínimo) y que cabe en la mesa, como con `caja.csv`.

## 4. Límites y sin comprobar
- **Solo se ha probado con imágenes sintéticas** (`vision/escena.py`: tablero con perspectiva y cajas como prismas): error de 0,1 mm en la posición de la cámara, 1 mm con profundidad y hasta unos mm con color. **No hay datos de una cámara ni de una caja reales.**
- **Pared de la caja (color y fondo):** la silueta incluye la pared que mira a la cámara, y la medida crece hacia el pie de la cámara (unos 8 mm en el ejemplo, con la caja a 150 mm del eje y la cámara a 800 mm; 0 si está justo debajo). El programa lo estima en `pared_mm` y avisa. Con profundidad no ocurre. **Pon la cámara sobre el punto de recogida.**
- **Cajas pegadas:** dos cajas a menos de unos 3 cm en la imagen se funden en una (el cierre de la máscara las une). Con profundidad y cajas separadas no hay problema.
- **Luz y color:** el rango HSV por defecto es de cartón marrón; con brillos, sombras duras o cajas blancas, usa `--modo fondo` o `profundidad`.
- **RealSense:** `vision.proveedores.RealSense` está escrito y **sin probar** (no hay cámara ni `pyrealsense2` aquí): comprueba que la profundidad llega alineada con el color y en mm. Los intrínsecos de fábrica de la cámara no se leen: se calibran con el tablero.
- **`--interactivo`** abre una ventana de OpenCV: no se ha podido ejecutar (sin pantalla en el equipo de desarrollo).
- **Una caja por imagen:** `FuenteCamara` lee una caja cada vez; la cinta en movimiento (agarrar al vuelo) no está.
- El tablero se detecta con el detector de sectores de OpenCV (~0,6 s por foto), que es preciso pero lento: solo se usa al calibrar o en las pruebas, no en el ciclo.
