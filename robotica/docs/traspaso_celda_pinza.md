# Traspaso: celda GoFa + pinza (simulación en RobotStudio)

Estado a 2026-11-16. Todo está en la rama `robotica-un-robot` del repo `tfm-robotica-bimanual`, **sin commitear ni subir** (carpetas `robotica/celda/`, `robotica/rapid/`, `robotica/flexpendant/`, `robotica/docs/`, `robotica/puente_egm/config.celda.json`, `robotica/tests/test_celda_*.py`, `test_flexpendant.py` y `tests/js/`). El clon de Windows (`TFM_Windows`) no tiene la carpeta `celda`.

## Objetivo
Un GoFa (CRB 15000-5/0.95, OmniCore, RobotWare 7.12) con pinza coge cajas de una cinta y las deja ordenadas en una cuadricula de la mesa (todas sin girar), con medidas ajustables desde la app del FlexPendant. El movimiento lo hace EGM (una sesión por caja) mandado por un PC a través del puente C# (Windows). RAPID solo coordina. Primero simulación; en el laboratorio solo cambian la percepción (cámara en vez de `caja.csv`) y la señal de llegada (forzada a mano).

## Piezas
| Pieza | Dónde | Qué hace |
|---|---|---|
| Módulo RAPID | `robotica/rapid/MOD_CajaPinza.mod` (copia en `Desktop\TFM_RAPID\RAPID\`) | Cargado en `T_ROB1` y `T_COM`; `main` reparte con `TaskRunRob()`. `T_ROB1`: caja, cinta, sesión EGM. `T_COM`: socket con el PC, pinza, fin de sesión. |
| PC (planificador) | `robotica/celda/` (`ciclo.py`, `planificacion.py`, `percepcion.py`, `socket_rapid.py`, `config.py`) | Lee la caja, planifica 3 tramos (aproximación y agarre, transporte y depósito, salida), los manda al puente y coordina la pinza por socket. El PC es servidor del socket (127.0.0.1:5010); RAPID es cliente. |
| Puente EGM | `robotica/puente_egm/` + `config.celda.json` (solo `brazo1`, espacio ampliado a x/y −600…800 mm) | Sin cambios de código. |
| Estación | `Documents\RobotStudio\Projects\TFM_3\Station\Proyecto_1mayo.rsstnx` | Editada con `robotica/rapid/estacion/aplicar_estacion.py` y luego `actualizar_estacion.py`. Copias `.bak*` en la misma carpeta. |
| Señales | `robotica/rapid/cfg/EIO/EIO.cfg` (17 señales, `-Access "All"`), `cfg/SYS/SYS.cfg` (tarea `T_COM`) | Se cargan en RobotStudio con Load Parameters. |
| Manual | `robotica/docs/manual_robotstudio_cajapinza.md` | Pasos de RobotStudio, conexiones del Station Logic, límites y fallos. |
| App del FlexPendant | `robotica/flexpendant/CajaPinza/` (copias en `Desktop\TFM_RAPID\WebApps` y en el `HOME\WebApps` del controlador virtual) | Espera **CAJA EN POSICIÓN** para arrancar cada EGM; ajusta nº de cajas, simulación/real, giros y botón; muestra el momento, la orientación de la caja y las señales. Habla con las PERS `hmi*` de `MOD_CajaPinza` por RWS (16-nov). Ver su README y el paso 9 del manual. |

## Ciclo de una caja
1. `T_ROB1` pone la caja al inicio de la cinta (`CajaPosKK`, 12 giros de −90° a 75°), mueve la cinta (`CintaMover` → `LinearMover`) y espera `CajaEnRecogida` (la activa el sensor `FinCinta_2`). En el laboratorio esa DI se fuerza a mano.
2. Arranca la sesión EGM en `pSeguroBrida` = (600, -6.5, 690) en la brida, que es `pSeguro` = (600, -6.5, 543) en el TCP (punto de espera sobre la cinta, 300 mm más alto que el 390 de la prueba de EGM: a 243 la pinza quedaba dentro de la caja que llega) (`EGMActPose`, `EGMRunPose … \CondTime:=tiempoConv`), y espera. Las ventanas `egm_minmax` no limitan el movimiento: son el criterio de convergencia (±3 mm; ver `MOD_CajaPinza.mod`).
3. El PC detecta el inicio por los datagramas (`ciclos` del puente), planifica y sigue cada punto. En el punto de agarre manda `cerrar`; en la mesa, `abrir`; al final, `fin_caja`.
4. `fin_caja`: el PC ha dejado la pinza quieta en la salida. El robot queda convergido `tiempoConv` s (2,5), `EGMRunPose` termina, `T_ROB1` hace `EGMReset` y pone `egmParado`, y `T_COM` contesta `fin_ok`. Tras la última caja, `T_ROB1` vuelve a `pSeguroBrida` y se detiene con `Stop` (sin él, en modo continuo arrancaría otra tanda).
5. Protocolo por socket sin separadores, una orden por turno: `cerrar/abrir/fin_caja/fin_programa` ↔ `cerrada/abierta/fin_ok/fallo_pinza/fallo_egm`. Desde el 16-nov también `lote` ↔ `lote:<n>:<sim|real>` y `giro:<grados>` ↔ `giro_ok`: el PC se niega a empezar si su modo o la cuenta de `caja.csv` no son los de RAPID, y la app compara el giro que colocó RAPID con el que lee el PC.
6. Con la app (`usarHmi := TRUE`), `T_ROB1` espera `INICIAR` antes de generar `caja.csv` y moverse, y `CAJA EN POSICIÓN` antes de cada EGM (si `hmiConfirmar`). Con `usarHmi := FALSE`, como antes.

## Datos de la celda (mm, respecto a la base del GoFa, que está en (0,2; 0,2; 0,2) m)
- Recogida (caja parada): x = 700; y = 100 − medio lado delantero (el PC lo calcula con `centro_parada`: una caja girada toca el sensor antes). Giro 0 → (700, 0). `z_cinta` 220; `z_mesa` 320; mesa (−220, 542).
- Caja de simulación: cubo de 200 mm. `herrPinza`: TCP (0, 0, 147), masa 0,5 kg (provisional).
- Giro en `caja.csv`: `largo;ancho;alto;giro`, giro en [−90, 90).

## Comprobado en RobotStudio
- Los 12 `Positioner` colocan la caja con su giro; `CintaMover` la mueve; el sensor la para y activa `CajaEnRecogida`; con Play, RAPID recorre solo hasta esperar al EGM (`caja.csv` correcto, primera caja −75°).
- Tests del repo: 142 pasan, 1 se salta (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest robotica/tests`).

## Sin comprobar (por orden de riesgo)
0c. **Parametros de puesta en marcha** (20-nov). Pestana Parametros de la app: recogida (fija o camara, zona permitida, correccion), agarre (altura por porcentaje o desde la tapa, minimo, alto minimo, apertura, grosor del dedo, giro de la pinza, TCP, margen), tiempos (pausas y esperas maximas, tiempoConv) y movimiento (velocidad, suelo, punto de espera). Son PERS de `MOD_CajaPinza.mod`; el PC las pide con `recogida`, `agarre` y `celda`, asi que el JSON queda solo como valores de arranque. Probado con el RAPID falso y la cinematica del PC; **sin ejecutar en RobotStudio**: `pSeguro/pSeguroBrida/pStart` pasan de CONST a VAR y se recalculan al empezar (`AplicarSeguro`), y `tiempoConv` pasa de CONST a PERS. Pendiente: camara (`FuenteCamara`), perfiles Simulacion/Laboratorio, masa de la pinza (el EGM va con `tool0`).
0b. **Deposito ordenado en la mesa, con cajas de medidas distintas** (18-nov). Las cajas se reparten en filas segun llegan (`Reparto` en `celda/planificacion.py`, con espejo en `logica.js`), sin girar. Probado con el PC contra un RAPID falso y con la cinematica del GoFa (alcance); sin ejecutar en RobotStudio. Desde el 18-nov los valores por defecto son `egmMaxPos` = 1500 mm desde el punto de espera y la `mesa_marron` colocada en (-700, 350, 500) mm del mundo (zona x -900..300, y 150..1150 respecto a la base): caben 8 cajas de 200 mm (con 1000 serian 4; con la mesa antigua, 2 y 5). No se sabe si el controlador acepta 1500: si no, ponerlo a 1000. Faltaba mover `mesa_marron` en RobotStudio (Set Position); queda a 20 mm del inicio de la cinta. Las mordazas tienen que caber en `mesaHueco`. `ABORTAR` (RWS Stop + PP a Main) y el interruptor de mensajes (`hmiMensajes`) tampoco se han probado en el controlador.
0. **La app del FlexPendant contra el controlador virtual** (16-nov). Probada solo con un RAPID simulado y las librerías de ABB dentro de jsdom. Por comprobar: que `T_ROB1` y `T_COM` compilan el módulo nuevo (`WaitUntil` sobre las PERS `hmi*`, `StrPart`/`StrToVal` en `T_COM`), que RWS suscribe esas PERS, que `setValue` consigue la mastership con RobotStudio abierto y que el controlador detecta la app tras reiniciar.
1. **Todo el ciclo con puente + PC + RAPID.** Todavía no se ha ejecutado.
2. **Cerrar el EGM por convergencia** (`\CondTime:=tiempoConv` con ventana ±3 mm). Sustituye a la interrupción con `EGMStop`, que el 15-nov no cerraba la sesión: el programa seguía en `EGMRunPose`, sin movimiento y con el EGM abierto. Sin comprobar en el controlador.
3. **Arranque de la siguiente caja.** Un [foro de ABB](https://forums.robotstudio.com/discussion/13134/problems-with-restarting-egm-communication) cuenta que el robot sigue enviando unos 1,7 s tras `EGMStop`. `_esperar_arranque_egm` (en `ciclo.py`) detecta el inicio porque `ciclos` sube más de 5, así que podría confundir esos restos con un arranque.
4. **`T_COM`:** que `TaskRunRob()` compile en esa tarea (en `T_ROB1` sí), que conecte al socket y que `SocketReceive … \Time:=WAIT_MAX` funcione.
5. **Alcance con pinza** de `pSeguro` y los puntos de recogida y mesa: la rutina `prueba_alcance` existe, pero no se ha comunicado su resultado.
6. **Agarre forzado en simulación:** `Attacher` y `Detacher` de `VacuumPen_SComp` tienen la caja grande como `Child` fijo, sin sensor. La apertura de la pinza (≈40 mm según el CAD) es menor que la caja (200 mm).
7. `eje_pinzado` = "y" (eje local de cierre de la pinza) es una suposición pendiente del CAD.

## Trampas encontradas (para no repetirlas)
- RobotStudio guarda los ángulos de las propiedades en **radianes** aunque los muestre en grados.
- El estado «Idle» embebido en `.rsstnx` restaura los valores de las propiedades al abrir o hacer Reset: hay que editarlo a la vez que las propiedades.
- No editar `.rsstnx` con RobotStudio abierto; el título de la ventana tarda unos segundos en cambiar al cerrar la estación.
- La configuración del controlador está en `image.bin`: solo se cambia con Load Parameters (el fichero debe llamarse `EIO.cfg` / `SYS.cfg`).
- `\NoWaitCond` no lo acepta RW 7.12; `Rand` no consta (se usa un generador propio).
- El WSL está en modo NAT y no alcanza el `127.0.0.1` de Windows: el PC se lanza desde Windows con `python -m celda.ciclo celda\config_celda_windows.json` (Python 3.11 de Windows, con `numpy`).
- Orden de arranque: puente → PC → RobotStudio (espera ~10 s, Reset, un solo Play).
- Velocidad: el puente limita la referencia a `paso_mm` por ciclo de 4 ms (0,4 mm = 100 mm/s). El robot la sigue con ~0,2 s de retraso (205 ms medidos el 11-nov en dos pruebas), así que en marcha queda a v × 0,2 s de ella: 20 mm a 100 mm/s. `desviacion_mm` tiene que ser al menos 1,5 veces eso o el puente entra en fallo (`desviacion_excesiva`). Con cajas giradas, el mismo retraso en giro (0,0025 rad por ciclo ≈ 0,13 rad) obliga a `desviacion_rad` ≥ 0,2; el retraso en giro es una estimación, no está medido.
- Vuelta entre cajas: va por articulaciones (`MoveAbsJ` a las que tenía el robot al llegar a `pSeguroBrida`, tomadas con `CJointT()`). Con `MoveJ` y `ConfJ \Off` el controlador elegía la configuración del brazo y el 15-nov acabó con «Joint Out of Range» (50027). Además, la salida del PC sube por encima del techo de la caja ya depositada (TCP a 585 mm, brida a 732): antes subía solo a 485 mm, 35 mm por debajo del techo, y la vuelta barría la pinza a través de la caja. Comprobado con la cinemática del GoFa (DH de `CRB15000_5_95__01.rslib`): la salida es alcanzable (J5 = 92°) y el barrido articular pasa a más de 48 mm sobre la caja.
- `semantica` del puente = `absoluta`: el controlador lee `planned` como pose absoluta en la base. Con `desplazamiento` el puente manda (0, 0, 0) al empezar el EGM y el robot va al origen de la base (errores 50375 y 50366, el PC se rompe). Visto el 15-nov-2026; la consola del puente debe decir `semantica=absoluta`.

## Preferencias del usuario
Trabaja en español. Commit y push solo si lo pide. No quiere ficheros `.ps1` en el proyecto. No pedir que repita Stop/Play. Cada respuesta de trabajo termina con el estado y lo concreto que necesito de él.

## Siguiente paso
Ejecutar el ciclo con una caja (`nCajas := 1`, `indiceFijo := 7`) con el puente en marcha, ver dónde se queda y diagnosticarlo con los registros del puente (`registros/puente.csv`), la salida del PC y el Event Log del controlador.
