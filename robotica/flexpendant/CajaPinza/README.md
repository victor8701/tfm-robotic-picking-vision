# App `Celda de cajas` (FlexPendant del GoFa)

App web de OmniCore (App SDK 1.6.0, copiado de la práctica de Robótica Industrial) para llevar la celda de cajas desde el FlexPendant. Habla con `MOD_CajaPinza` por RWS: lee sus PERS `hmi*` y las de la tanda y escribe las órdenes y los ajustes.

## Qué hace
| Zona | Contenido |
|---|---|
| Cabecera | Estado del programa, PC y modo, y **ABORTAR** (Stop + PP a Main por RWS, con confirmación; no es un paro de emergencia). |
| Momento | En qué fase está la celda (tabla `FASE_*` de `MOD_CajaPinza.mod`), caja en curso, progreso y los pasos de una caja. **INICIAR TANDA** y **CAJA EN POSICIÓN**. |
| Pinza | Tarjeta con el estado de la pinza según las señales: **ABIERTA**, **CERRADA**, CERRANDO…/ABRIENDO… y SIN CONFIRMACIÓN (más de 3 s sin que `PinzaCerrada` siga a la orden, lo mismo que espera RAPID). Dos luces, `PinzaCerrar` (orden) y `PinzaCerrada` (confirmación), y cuántas órdenes de cerrar y abrir se han visto en la tanda, con la última y la caja. Si no lee las señales dice SIN LECTURA (suelen faltar `Access Level = All`). |
| Ajustes de la tanda | Cajas (1–100), Simulación o Real, giro al azar (con «Nueva secuencia») o fijo, si se espera el botón en cada caja y si los avisos de RAPID salen también en el FlexPendant (interruptor de mensajes). Solo se editan antes de iniciar o al terminar; el interruptor del botón vale también durante la tanda (desde la caja siguiente). |
| Pestaña Mesa de depósito | Zona de la mesa (esquina, largo, ancho, altura, hueco), caja de referencia (la mayor caja, y si en simulación las cajas miden distinto), y un dibujo de la mesa con los sitios y, en rojo, lo que el robot no alcanza. Estima cuántas caben y bloquea INICIAR si la tanda no cabe (cajas iguales). Por defecto, la mesa de la simulación. |
| Pestaña Parámetros | Ajustes de puesta en marcha en cuatro secciones: **Recogida** (posición fija o de cámara y zona permitida, corrección de la cámara, altura de la cinta), **Pinza y agarre** (giro, altura de agarre por porcentaje o desde la tapa, mínimo, alto mínimo, apertura y grosor del dedo, largo de la pinza, margen), **Tiempos** (pausas y esperas máximas) y **Movimiento y seguridad** (velocidad, suelo, punto de espera, límite del EGM). Los protegidos piden confirmación; durante la tanda, todo bloqueado. El PC los lee de RAPID: no hay que tocar el JSON. Botones **Valores por defecto** (con confirmación), **Guardar en fichero** y **Cargar de fichero**: CSV `parametro;valor;unidad;descripcion` en `$HOME/parametros/<nombre>.csv` del controlador, con el nombre que se teclea; al cargar se ve qué cambia y se ignoran las líneas que no valen. |
| Orientación de la caja | Dibujo desde arriba (giro antihorario, x a la derecha, y hacia arriba, la cinta avanza en +y), el giro que puso RAPID, el que lee el PC y si coinciden, la lista de giros de la tanda y las señales (sensor, cinta, orden de cerrar y pinza cerrada). |

## Valores por defecto y qué se guarda
La app no guarda nada: todos los ajustes son PERS de `MOD_CajaPinza`, así que siguen ahí al cerrar y volver a abrir la app (que no escribe nada al abrirse). Solo vuelven a los valores del módulo al recargar `MOD_CajaPinza.mod`.

| Ajuste | Por defecto |
|---|---|
| Modo | Simulación |
| Giro (simulación) | Al azar |
| Cajas de tamaños distintos (simulación) | Activado |
| Esperar CAJA EN POSICIÓN | Activado |
| Mostrar mensajes de RAPID en el FlexPendant | Apagado |

Al pulsar **Real** se activa esperar CAJA EN POSICIÓN; al pulsar **Simulación**, giro al azar y cajas distintas (`ajustesDeModo` de `logica.js`). Pulsar el modo ya activo no cambia nada, y todo se puede modificar a mano después. `caja.csv` (largo;ancho;alto;giro) lo escribe RAPID en cada tanda en simulación: no se edita a mano.

Con `CAJA EN POSICIÓN` activado, T_ROB1 no arranca el EGM de cada caja hasta recibirla. Sin él, en simulación arranca al llegar la caja al sensor y en real al activarse `CajaEnRecogida`.

## Ficheros
- `index.html`, `app.css`, `app.js`: la pantalla. `app.js` solo pinta y escribe.
- `logica.js`: toda la lógica (qué botón vale, qué texto, la lista de giros, que es el mismo generador que `MOD_CajaPinza.mod`). Sin DOM ni RWS: se prueba con Node.
- `demo-rws.js`: RWS simulado para ver la pantalla sin controlador (`index.html?demo`) y para las pruebas.
- `fp-components/` y `rws-api/`: librerías de ABB (App SDK 1.6.0, licencia MIT), solo lo que usa la app.
- `appinfo.xml`: nombre, icono y página de inicio que lee el controlador.

## Instalación
1. Carpeta `CajaPinza` entera en `$HOME/WebApps/` del controlador (virtual: `...\Virtual Controllers\ControllerTFG_EGM\HOME\WebApps\CajaPinza`).
2. Reiniciar el controlador: OmniCore solo detecta las apps al arrancar.
3. Las señales que muestra la app (`CajaEnRecogida`, `CintaMover`, `PinzaCerrar`, `PinzaCerrada`) tienen `Access Level = All` en `rapid/cfg/EIO/EIO.cfg`; con otro nivel, la app no las lee.
4. `MOD_CajaPinza.mod` actual en `T_ROB1` y `T_COM`. Sin las PERS `hmi*`, la app avisa de cuáles faltan.

Sin la app, `usarHmi := FALSE` en RAPID.

## Pruebas
```
cd robotica
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/test_flexpendant.py
```
- Coherencia con RAPID y EIO.cfg (fases, PERS y su tipo, constantes, señales, generador de giros) y sintaxis básica del módulo: solo Python.
- `tests/js/logica.test.js` y `tests/js/app.test.js` los lanza Node (en WSL se usa el de Windows). La segunda abre la pantalla entera en jsdom contra el RAPID simulado: `npm install` en `tests/js`, o `CAJAPINZA_JSDOM` con una carpeta que tenga `node_modules/jsdom`. Sin jsdom se salta.

## Sin probar
Solo se ha probado contra el RAPID simulado (`demo-rws.js`) y con las librerías de ABB reales dentro de jsdom. **No** contra el controlador virtual: que la suscripción por RWS a las PERS funciona, que `setValue` obtiene la mastership y que RAPID consume las órdenes como espera la app está por comprobar. La app relee todo cada 2 s por si una suscripción no avisa.
