# Celda de cajas: PC y RAPID

Una caja cada vez. El EGM lleva todo el movimiento de cada caja (una sesión EGM por caja). RAPID hace la posición segura, la cinta y la pinza, y en simulación genera las cajas.

## Piezas

- `robotica/rapid/MOD_CajaPinza.mod`: RAPID con dos tareas. T_ROB1 hace el movimiento y T_COM la pinza y el socket. Cargar el módulo como SYSMODULE en ambas.
- `celda/ciclo.py`: el PC. Lee la caja, planifica los tramos, los manda por el puente y coordina con RAPID.
- `celda/planificacion.py`: pinza hacia abajo, giro según la caja, alturas, tramos y límites.
- `celda/percepcion.py`: `caja.csv` en simulación y la cámara (`FuenteCamara`, con `vision/`) en real. Ver `docs/vision.md`.
- `celda/socket_rapid.py`: servidor de socket del PC.
- `celda/config_celda.json`: parámetros. Los valores `_pendiente` se rellenan con la estación y el CAD.

## Arranque

1. Puente EGM en marcha con `puente_egm/config.celda.json` (copia en `TFM_RAPID\config.celda.json`), sin `--prueba`: ese modo es solo para la prueba de diagonales de un robot (`docs/prueba_un_robot.md`).
2. PC, desde `robotica/`: `python -m celda.ciclo celda/config_celda.json`. Queda esperando a RAPID.
3. RobotStudio: arrancar RAPID. T_COM conecta con el PC. Cuando T_ROB1 espera la caja y se activa `CajaEnRecogida`, empieza la primera caja.

## Prueba de alcance (sin EGM)

Antes de la primera caja, comprobar que la pinza llega a la recogida y a la mesa, sin EGM ni PC:

1. Quitar `MOD_CajaPinza` de T_ROB1 y de T_COM. Cargar `rapid/MOD_PruebaAlcance.mod` en T_ROB1 y en T_COM (en T_COM no hace nada).
2. Robot cerca de pSeguro y sin caja parada en el sensor de la cinta. PP a Main → Play.
3. La ventana Output muestra los mensajes `Alcance: ...`. El último dice hasta dónde llegó.
4. Volver a cargar `MOD_CajaPinza` en T_ROB1 y en T_COM antes de la prueba con EGM.

Play arranca `main` (no el puntero), por eso la prueba va en su propio módulo.

## Brida y TCP

EGM controla la brida (tool0): `EGMActPose` recibe `pose_cero` como herramienta. Los puntos del planificador son del TCP de `herrPinza`, 147 mm por delante de la brida. `planificacion.a_brida` manda a EGM la brida = TCP + 147 mm en z (con la pinza hacia abajo). `largo_herramienta_mm` (JSON) debe coincidir con el TCP z de `herrPinza`, y `tests/test_celda_configuracion.py` lo comprueba. Si `EGMActPose` pasara a usar el TCP, habría que quitar `a_brida`.

En RobotStudio, TCP y tool0 difieren 147 mm (comprobado). Pendiente: ver que el TCP llega a su punto en la primera caja.

## Protocolo por socket

El PC es servidor y T_COM de RAPID es cliente. Sin separadores: cada orden espera su respuesta antes de la siguiente.

| PC → RAPID | RAPID → PC |
|---|---|
| `cerrar` | `cerrada` (o `fallo_pinza`) |
| `abrir` | `abierta` |
| `fin_caja` | `fin_ok` |
| `fin_programa` | (ninguna) |
| `lote` | `lote:<n>:<sim\|real>` (cajas de la tanda y modo, los de la app del FlexPendant) |
| `mesa` | `mesa:<x0>:<y0>:<largo>:<ancho>:<z>:<hueco>:<egmMaxPos>:<alcanceMax>` (zona de deposito y limites; el PC deja las cajas ordenadas en una cuadricula, sin girar) |
| `recogida` / `agarre` / `celda` | `recogida:<modo>:<x>:<y>:<tolX>:<tolY>:<offX>:<offY>:<offGiro>:<tMaxCamara>` / `agarre:<modo>:<porc>:<hund>:<min>:<solape>:<apertura>:<grosor>:<giroPinza>` / `celda:<zCinta>:<margenAprox>:<tcpZ>:<seguroX>:<seguroY>:<seguroZ>:<velocidad>:<zMinima>` (ajustes de puesta en marcha de la app; el PC los pide tras `mesa`) |
| `giro:<grados>` | `giro_ok` (o `giro_mal`) |

## Pendiente de verificar en el controlador virtual

- Opciones de RobotWare: multitarea (MultiTasking) y mensajería por socket (Socket Messaging).
- Que `EGMRunPose` con `\CondTime:=tiempoConv` y ventana ±3 mm termina al quedar el robot convergido en la salida. El `EGMStop` desde una interrupción no cerraba la sesión (15-nov).
- Que ninguna parada con la pinza quieta, en mitad de la caja, dura más de `tiempoConv`.
- Formato de `SocketReceive`: si deja algún carácter de más en el texto.
- Carpeta HOME del controlador virtual, para `caja.csv`.
- Señales, `pSeguro` y `herrPinza` con los valores de la estación.
- Dimensiones de la pinza (CAD) y `eje_pinzado`.

## Límites del puente

La velocidad de traslación la fija `paso_mm` (0,4 mm por ciclo de 4 ms = 100 mm/s) y la de giro `giro_rad` en `puente_egm/config.celda.json`. El robot sigue la referencia con ~0,2 s de retraso, así que `desviacion_mm` debe ser al menos 1,5 × v × 0,2 s (ver `docs/traspaso_celda_pinza.md`). Si el giro de la pinza no sigue al objetivo, bajar `giro_rad` o subir `desviacion_rad`.
