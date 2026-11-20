# Manual de RobotStudio para `MOD_CajaPinza.mod` (versión 3, para no expertos)

## Qué hace la celda en simulación

Cada caja sigue este recorrido:
1. RAPID elige un giro (uno de 12: −90°…75°, de 15 en 15) y lo escribe en `caja.csv`.
2. Un `Positioner` pone la caja **al inicio de la cinta**, ya con ese giro.
3. RAPID activa `CintaMover`, la cinta (`LinearMover`) lleva la caja y el sensor de final de cinta (`FinCinta_2`) la detiene al tocarla. Ese contacto activa `CajaEnRecogida`.
4. Arranca el EGM y el PC lleva el robot: baja, cierra la pinza, transporta, abre y sube.
5. RAPID vuelve a poner la misma caja al inicio de la cinta con otro giro. La caja del 3D se recicla.

En el laboratorio no hay cinta ni `Positioner`: `CajaEnRecogida` se fuerza a mano. Es la única diferencia entre simulación y laboratorio.

## 1. Lo que ya está hecho (no lo toques)

**Estación `Proyecto_1mayo.rsstnx`** (copia anterior: `Proyecto_1mayo.rsstnx.bak3_antes_v3`, misma carpeta):
- 12 componentes `PosCaja01`…`PosCaja12` que ponen la caja grande al inicio de la cinta con cada giro. **Los ángulos van en radianes**: la interfaz los muestra en grados, pero el fichero los guarda en radianes. La versión anterior los tenía en grados y por eso la caja aparecía en otro sitio.
- El plano del sensor `FinCinta_2` es más ancho en x (de 0,7 a 1,1 m), para que detecte la caja con cualquier giro.
- En `VacuumPen_SComp`, `Attacher` y `Detacher` tienen la caja grande como `Child` fijo. El agarre queda forzado (ver «Límites»).
- 16 conexiones en el Station Logic (apartado 4). `LinearMover` y `FinCinta_2` ya se usan.

**Ficheros en `C:\Users\Viktor\Desktop\TFM_RAPID\`:**
- `EIO_cajapinza\EIO.cfg`: las 17 señales que usa la celda.
- `SYS_tcom\SYS.cfg`: la tarea `T_COM` (si ya la tienes creada, no hace falta).
- `RAPID\MOD_CajaPinza.mod`: el módulo v3.
- `config.celda.json`: configuración del puente.

## 2. Lo que tienes que hacer tú, en orden

### Paso 1. Abrir la estación
Abre `Proyecto_1mayo.rsstnx`. Si RobotStudio no la abre o da error, dime y restauro la copia `.bak3_antes_v3`.

### Paso 2. Cargar las señales y quitar las que ya no se usan
1. Haz una copia de seguridad: **Controller → Backup → Create Backup**.
2. **Controller → Configuration → I/O System** → clic derecho → **Load Parameters…**
3. Elige `Desktop\TFM_RAPID\EIO_cajapinza\EIO.cfg` (el fichero tiene que llamarse `EIO.cfg`).
4. En el modo de carga, elige **Delete existing parameters before loading**. Borra todas las señales actuales y carga solo las 17 del fichero, que ya incluye `PinzaCerrar` y `PinzaCerrada`. Así desaparecen las 12 señales que ya no se usan: `Salida`, `Entrada`, `PosicionadorOutput`, `CajaGrande`, `MoverCajaGrande`, `MoverCajaPeq`, `PosicionadorPeq`, `ShowGrande`, `HideGrande`, `ShowPeq`, `HidePeq` y `CajaLlegada`.
5. **Reinicia el controlador** y comprueba en **Signal** que quedan 17: `PinzaCerrar`, `PinzaCerrada`, `CintaMover`, `CajaEnRecogida`, `FinCajaEGM` y `CajaPos01`…`CajaPos12`.

Si prefieres no borrar nada, elige **Load parameters if no duplicates**: añade `CintaMover` y deja las demás.

Las señales llevan `-Access "All"`: así el simulador de E/S puede escribirlas (con el nivel por defecto, el paso 6 da «Failed to set value for signal…, check access rights»). Si ya cargaste una versión sin ese permiso, vuelve a cargar el fichero con **Load parameters and replace duplicates**.

### Paso 3. Mirar el Station Logic
**Simulación → Station Logic → Signals and Connections.** Deben salir las 16 conexiones del apartado 4, y `LinearMover` y `FinCinta_2` deben tener líneas. Si falta alguna, créala a mano o dímelo: son dos las que importan, `CintaMover` → `LinearMover.Execute` y `FinCinta_2.SensorOut` → `CajaEnRecogida`.

### Paso 4. La tarea T_COM
Debe existir. Si no: **Controller → Configuration → Controller** → clic derecho → **Load Parameters…** → `Desktop\TFM_RAPID\SYS_tcom\SYS.cfg`, y reinicia. Si no te deja, crea la tarea a mano: tipo **Task** → **New Task** → nombre `T_COM`, tipo `NORMAL`, **sin** «Motion Task».

### Paso 5. Cargar el módulo en las dos tareas
El módulo ha cambiado: **sustituye** el que tengas cargado.
1. En `T_ROB1` y en `T_COM`: borra `MOD_CajaPinza` (clic derecho → **Delete Module**) y cualquier módulo antiguo con `main`.
2. Clic derecho en `T_ROB1` → **Load Module…** → `Desktop\TFM_RAPID\RAPID\MOD_CajaPinza.mod`.
3. Lo mismo en `T_COM`: **el mismo fichero**.
4. **Check Program** en las dos tareas.

### Paso 6. Prueba de la cinta sin RAPID (con el simulador de E/S)
1. **Reset**. Abre **Simulación → I/O Simulator → `ControllerTFG_EGM`**.
2. Pon `CajaPos07` a 1: la caja salta al inicio de la cinta, sin giro. Prueba también `CajaPos03` (−60°) y `CajaPos10` (45°): la caja debe aparecer al inicio de la cinta con ese giro.
3. **La cinta solo se mueve con la simulación en marcha** (Play): el `LinearMover` avanza con el tiempo de simulación. Los `Positioner` sí actúan al instante, sin Play.
4. Con la simulación en marcha, pon `CintaMover` a 1 y mira el Station Logic: `LinearMover` debe mostrar `Execute (1)` y la caja debe avanzar hacia el sensor. Al tocarlo, `CajaEnRecogida` pasa a 1. Pon `CintaMover` a 0 y la caja se queda parada.
5. Si el módulo ya está cargado en `T_ROB1`, Play también arranca RAPID, y RAPID pone `CintaMover` a 0 al empezar y la maneja él solo. En ese caso salta este apartado: la comprobación de la cinta es el paso 8. Tras llegar a la posición segura, la caja aparece al inicio de la cinta y avanza sola.

### Paso 7. Alcance del robot
En `T_ROB1`: **PP to Routine** → `prueba_alcance` → **Play**. Recorre la posición segura, la recogida (arriba y abajo) y la mesa. Termina con el mensaje `prueba_alcance: todos los puntos alcanzados`. Si un `MoveJ` da error de alcance, dime cuál.

### Paso 8. Ciclo completo
Para empezar, una caja y sin giro: en el editor de datos RAPID, módulo `MOD_CajaPinza`, `nCajas := 1` e `indiceFijo := 7` (0 grados; `0` = giros al azar, del 1 al 12 = ese giro).

El PC toma el número de cajas de `caja.csv` (una línea por caja, la escribe RAPID): no hay que tocar `n_cajas` del JSON. Antes, con `n_cajas = 1` en el PC y `nCajas = 5` en RAPID, el PC solo agarraba la primera caja y RAPID recorría las otras cuatro sin PC: las cajas aparecían y desaparecían en la cinta (16-nov). Si el EGM termina sin que el PC haya pedido `fin_caja`, RAPID se para con el mensaje «El PC no ha dirigido la caja N».

Orden de arranque:
1. **Puente EGM**, en una ventana de **PowerShell de Windows para él solo**. El `.exe` no está en la carpeta del PC (la de WSL del paso 2): si lo lanzas desde allí sale «`.\PuenteEgm.exe` no se reconoce como nombre de un cmdlet». Hay que ir antes a la carpeta donde está compilado:
   ```
   cd C:\Users\Viktor\source\repos\TFM_Windows\robotica\puente_egm\PuenteEgm\bin\Release\net8.0
   .\PuenteEgm.exe "C:\Users\Viktor\Desktop\TFM_RAPID\config.celda.json"
   ```
   Sin `--prueba`. La consola debe decir `semantica=absoluta` y `Puente en marcha. Ctrl+C para parar.`; no cierres esa ventana. Ese `.exe` es del clon `TFM_Windows` (compilado el 15-nov): el código de la carpeta de WSL no se compila solo. Si cambias el C#, cópialo a `TFM_Windows` y compila en `...\puente_egm\PuenteEgm` con `dotnet build -c Release`. Con `config.celda.json` no hay problema: ya pone `"semantica": "absoluta"`, y el clon aún tiene `desplazamiento` como valor por defecto.
2. **PC**, en **otra ventana de PowerShell de Windows**. El WSL está en modo NAT y no alcanza el puente, que escucha en el `127.0.0.1` de Windows:
   ```
   cd \\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica
   & "C:\Program Files\Python311\python.exe" -m celda.ciclo celda\config_celda_windows.json
   ```
   Es la misma configuración con la ruta de `caja.csv` en formato Windows. Queda esperando a RAPID. Tiene que estar en marcha antes del Play.
3. **RobotStudio**: espera unos 10 segundos, **Reset** y **Play** una sola vez.

### Paso 9. App del FlexPendant (INICIAR y CAJA EN POSICIÓN)
La app `Celda de cajas` (carpeta `robotica/flexpendant/CajaPinza`, ver su README) sustituye a editar `nCajas`, `modoSimulacion` e `indiceFijo` a mano y a forzar `CajaEnRecogida`. Desde ella:
- **Se espera a `CAJA EN POSICIÓN`** para arrancar el EGM de cada caja. En simulación el botón se espera después de que el sensor de la cinta haya visto llegar la caja; en real, después de colocarla.
- Se ajusta la tanda **antes de `INICIAR TANDA`**: número de cajas (1 a 100), **Simulación o Real**, giro de las cajas (al azar con una secuencia que se puede cambiar, o fijo a uno de los 12 giros) y si se espera el botón en cada caja.
- La tarjeta **Pinza** (columna «Momento») muestra si está **ABIERTA** o **CERRADA** según las señales `PinzaCerrar` (orden) y `PinzaCerrada` (confirmación), con sus dos luces, cuántas órdenes de cerrar y abrir ha visto en la tanda y cuándo fue la última. «SIN CONFIRMACIÓN» = la orden salió y `PinzaCerrada` no la siguió en 3 s; «SIN LECTURA» = la app no lee las señales (mira `Access Level = All`).
- Se ve **en qué momento está** la celda (esperando INICIAR, poniendo la caja, cinta, esperando la caja, EGM, agarrada, soltada, cerrando el EGM, vuelta, tanda terminada o error), la caja en curso, **la orientación de la caja** (dibujo desde arriba, lo que puso RAPID y lo que lee el PC) y el estado de PC, programa, sensor, cinta y pinza.

**Qué se guarda y valores por defecto.** La app no guarda nada: los ajustes (cajas, modo, giro, mesa, mensajes, etc.) son PERS de `MOD_CajaPinza`, así que **se conservan al cerrar y abrir la app** y no los toca al abrirse. Solo se reponen a los valores del módulo al **volver a cargar `MOD_CajaPinza.mod`** (si tras reiniciar el controlador siguen, no está comprobado). Por defecto: **Simulación** con **giro al azar** y **cajas de tamaños distintos**, `CAJA EN POSICIÓN` activado y **mostrar mensajes desactivado**. Al pulsar **Real** se activa esperar `CAJA EN POSICIÓN`; al pulsar **Simulación** se vuelve a giro al azar y cajas distintas (pulsar el modo que ya está activo no cambia nada). Todo se puede modificar después a mano.

Instalación (ya copiada): la app está en `Desktop\TFM_RAPID\WebApps\CajaPinza` y en `...\Virtual Controllers\ControllerTFG_EGM\HOME\WebApps\CajaPinza`.
1. **Carga el `MOD_CajaPinza.mod` nuevo** (`Desktop\TFM_RAPID\RAPID`) en `T_ROB1` y en `T_COM`, como las otras veces. Sin él, la app dice «No encuentro en RAPID: …».
2. **Reinicia el controlador virtual** (Controlador → Reiniciar → Reinicio normal). OmniCore solo detecta las apps de `HOME\WebApps` al arrancar.
3. Abre el **FlexPendant virtual** (pestaña Controlador → FlexPendant) y busca la app `Celda de cajas` en el menú de aplicaciones.
4. Orden de arranque: puente → PC → RobotStudio (**Reset** y **Play**). T_ROB1 se queda esperando INICIAR: la app dice «Listo para empezar». Ajusta y pulsa **INICIAR TANDA**. Con el botón activado, en cada caja la app dice «Esperando CAJA EN POSICIÓN»: púlsalo para arrancar el EGM.

Sin la app: `usarHmi := FALSE` en `MOD_CajaPinza` (editor de datos RAPID) y el módulo hace lo de antes (en simulación, caja tras caja con el sensor; en real, espera `CajaEnRecogida`). Con `usarHmi := TRUE` y sin app, el programa espera INICIAR para siempre.

Otra tanda: el PC termina al acabar la tanda y `T_COM` cierra el socket, así que hay que **relanzar el PC y volver a dar Play**.

Para ver la pantalla sin controlador, abre `index.html?demo` en un navegador: usa un RAPID simulado y tiene sus propios Play, Stop y «Forzar CajaEnRecogida».

**Botones de la ventana principal.** `ABORTAR` (rojo, arriba a la derecha) pide confirmación, para RAPID y lo deja al principio, como Stop y PP a Main desde la app; no es un paro de emergencia (ese es el del FlexPendant). Después hay que **relanzar el PC y dar Play**. Si el robot llevaba una caja, la pinza sigue cerrada. El PC detecta que el EGM se ha parado (3 s sin datagramas) y termina con un mensaje en vez de quedarse esperando. El interruptor `Mostrar mensajes de RAPID en el FlexPendant` (apagado por defecto) controla los `TPWrite` del módulo (PERS `hmiMensajes`): apagado, no salta la ventana de mensajes del operador y los avisos salen solo en la app. No afecta a los mensajes del propio controlador (errores y eventos del sistema).

**Mesa de depósito** (pestaña «Mesa de depósito»). Las cajas se dejan **ordenadas y sin girar**, sea cual sea el giro con el que llegaron: la pinza gira en el aire durante el transporte. Pueden medir **distinto** (largo, ancho y alto): el PC las reparte en **filas** según llegan, cada una con su medida real y el hueco indicado, desde la esquina de la mesa cercana al robot, de x menor a mayor. La fila mide lo que la caja más ancha que lleva y la siguiente va pegada tras ella; cada caja entra deslizándose por el lado +x sobre sitios aún vacíos (sin subir más) y baja en vertical. La salida sube por encima de la caja más alta ya dejada. Lo que el robot no alcanza se salta.
- **1 · Zona de la mesa** (mm desde la base del robot): esquina de x e y mínimas, largo (en x), ancho (en y), altura de la superficie y hueco entre cajas (también al borde; mayor que el grosor de las mordazas). Son PERS `mesa*`; por defecto, la `mesa_marron` de la simulación **colocada más cerca del robot**: x de −900 a 300, y de 150 a 1150, superficie a 320. Para que el 3D coincida, en RobotStudio selecciona `mesa_marron` → **Modify → Set Position** y pon, respecto al mundo, **x −700, y 350, z 500 mm** sin tocar la orientación (antes estaba en −919,88; 542,29; 500). La mesa acaba a 20 mm del principio de la cinta (x 520 mm en el mundo): compruébalo en el 3D. Si prefieres no moverla, pon en la pestaña la esquina antigua (x −1120, y 342); si no, el robot dejará las cajas donde ya no hay mesa.
- **2 · Caja de referencia** (PERS `cajaLargo`, `cajaAncho`, `cajaAlto`): la mayor caja que esperas. Solo sirve para estimar cuántas caben (el dibujo y el bloqueo de INICIAR); el reparto real usa la medida de cada caja. En la simulación son además las medidas de las cajas que genera RAPID; con `Cajas de tamaños distintos` (PERS `cajasVariables`, activado por defecto) cada una mide entre el 60 y el 100 % del largo y del ancho y entre el 50 y el 100 % del alto (el 3D las toma con el complemento del paso 10; sin él sigue siendo un cubo de 200 mm). La app muestra las medidas de la caja en curso.
- **3 · Límite del EGM** (PERS `egmMaxPos`, 1500 por defecto): el controlador para el EGM (Motors Off) si la referencia se aleja más de esto de la posición de espera (600, −6,5, 543). Es lo que más limita cuántas cajas caben: con la mesa en su sitio de ahora, a 1000 llegan **4** cajas de 200 mm y a 1500 llegan **8** (y las 10 cajas de tamaños distintos de la prueba caben todas). Con la mesa donde estaba antes (x −1120, y 342) eran 2 y 5. Se cambia desde la app (pide confirmación) o en el editor de datos RAPID. **Está sin comprobar que el controlador acepte 1500**: si al arrancar el EGM da error, pon 1000. El PC lee el valor de RAPID y aplica el mismo límite. `alcanceMax` (790 mm) es el radio máximo de la pinza desde el eje del robot, comprobado con la cinemática del GoFa hasta TCP z = 585.

El dibujo de la pestaña muestra la mesa desde arriba, la base del robot, el lado de entrada, los sitios (dejada, en curso, de esta tanda, libre) y en **rojo lo que el robot no alcanza** con la caja de referencia. Si la tanda no cabe y las cajas son iguales (simulación, tamaños fijos), INICIAR TANDA se bloquea y dice cuántas caben. Con tamaños distintos o en real la cuenta es solo una cota: el PC comprueba **antes de empezar** que caben todas las de `caja.csv` y, con cámara, cada caja antes de moverla; si una no cabe, se para con un mensaje.

Modo **Real**: RAPID no mueve la cinta ni escribe `caja.csv`, y la orientación la lee la cámara del PC (todavía pendiente: `FuenteCamara` no está hecha). El PC y RAPID tienen que estar en el mismo modo: el PC lo comprueba con `lote` y se niega a empezar si no coinciden.

### Paso 10. Cajas con su tamaño en el 3D (complemento CajasVariables)
Sin este paso, la simulación tiene **una sola pieza de 200 mm** (`CajaGrande`) que los `Positioner` recolocan en cada caja: no se ve el tamaño de cada caja ni el reparto en la mesa. El complemento (`robotica/rapid/estacion/CajasVariables`, ver su README) vigila `CajaGrande` y, cada vez que RAPID coloca una caja:
- la **redimensiona** con el largo, ancho y alto de su línea de `caja.csv` (misma caja, tamaño variable), con el mismo centro y la cara de abajo en la cinta, así que el sensor, el agarre y los `Positioner` siguen igual; la pinza agarra a la altura de cada caja (`alto / 2`) y se ve su trayectoria distinta;
- deja una **copia** de la caja anterior donde se quedó en la mesa: se ve el reparto en filas. Al empezar otra tanda (RAPID reescribe `caja.csv`) se quitan las copias.

**`caja.csv` no se toca nunca a mano.** RAPID lo escribe él solo en la carpeta HOME cada vez que pulsas `INICIAR TANDA` en simulación: una línea por caja con `largo;ancho;alto;giro` (en mm y grados), con las medidas que salen de la caja de referencia y de `Cajas de tamaños distintos`. Lo leen el PC y el complemento, y se reescribe en cada tanda. En Real no existe (la cámara da las medidas).

Cómo cargarlo (los pasos de ABB para RobotStudio 2026, «Creating a RobotStudio Add-In»; tu manual de 2023 queda desfasado: ahora el complemento es .NET 10 y la versión mínima es la 26.1):
1. Si instalaste antes el paquete `TFM.CajasVariables`, desinstálalo (Add-Ins → Installed Packages → RobotStudio Add-Ins, clic derecho) y cierra RobotStudio.
2. Copia `Desktop\TFM_RAPID\Addin\ParaBinAddins\CajasVariables.rsaddin` a `C:\Program Files (x86)\ABB\RobotStudio 2026\Bin\Addins\` (el Explorador pide permisos de administrador). Ese `.rsaddin` apunta con `<Path>` a la carpeta de la DLL, `Desktop\TFM_RAPID\Addin\CajasVariables`, que tiene que seguir ahí.
3. Abre RobotStudio 2026 y la estación.
4. Menú **Add-Ins**, panel de la izquierda: clic derecho en «Cajas variables» → **Load Add-In**.
5. En **Output** debe salir «Cajas variables: cargado…» y, con la estación abierta, «Cajas variables: 12 Positioner, caja de 200 x 200 x 200 mm, csv: …». Además se escribe `C:\Users\Viktor\AppData\Local\Temp\CajasVariables.log`.

El paquete `.rspak` (`Desktop\TFM_RAPID\Addin\TFM.CajasVariables-1.1.rspak`, Add-Ins → Install Package) es una vía que no está en el manual de ABB y con la que no llegó a cargar: un complemento instalado así no se carga solo, y no se ha comprobado que «Load Add-In» funcione con él.

Límites: está compilado contra las DLL de tu RobotStudio 2026, pero **no se ha ejecutado**; qué hace al correr (crear la caja con `Body.CreateSolidBox`, copiar la pieza, el sensor con la caja nueva) está por comprobar. Si algo falla, mándame lo que salga en Output. Para usar tamaños variables, en la app: pestaña Mesa → «Cajas de tamaños distintos» (o pon medidas distintas en la caja de referencia).

## 3. Cómo funciona

`T_ROB1`, por cada caja:
1. Pulsa `CajaPosKK`: el `Positioner` KK pone la caja al inicio de la cinta con el giro KK.
2. Activa `CintaMover`: la caja avanza hasta el sensor. `FinCinta_2.SensorOut` activa `CajaEnRecogida`. Si en 40 s no llega, RAPID para con un mensaje.
3. Para la cinta, arranca la sesión EGM y espera. Desde aquí el PC lleva el robot por el puente.
4. Al acabar la caja, el PC deja la pinza quieta en la salida y pide `fin_caja`: el robot queda convergido unos 2,5 s y el EGM se cierra solo. `T_ROB1` vuelve a la posición segura y pasa a la caja siguiente. Tras la última se detiene con `Stop` (sin él, en modo continuo empezaría otra tanda).

`T_COM` habla con el PC por socket:
- `cerrar` → activa `PinzaCerrar`, espera `PinzaCerrada` = 1 (máximo 3 s; si no llega, contesta `fallo_pinza`) y contesta `cerrada`.
- `abrir` → desactiva `PinzaCerrar`, espera `PinzaCerrada` = 0 (máximo 3 s; si no baja, `fallo_pinza`) y contesta `abierta`. El PC escribe en su consola `Pinza: cerrar -> cerrada (0.1 s)` y `Pinza: abrir -> abierta (0.1 s)`.
- `abrir` → desactiva `PinzaCerrar` y contesta `abierta`.
- `fin_caja` → espera a que `T_ROB1` cierre el EGM (el robot queda convergido en la salida 2,5 s) y contesta `fin_ok` (o `fallo_egm` si en 12,5 s no se cerró).
- `lote` → contesta `lote:<nCajas>:<sim|real>`: el PC lo pregunta al empezar la primera caja y se niega a seguir si su modo o la cuenta de `caja.csv` no son los de RAPID (los ajusta la app).
- `mesa` → contesta `mesa:<x0>:<y0>:<largo>:<ancho>:<z>:<hueco>:<egmMaxPos>:<alcanceMax>`: el PC reparte la tanda en la mesa (cajas de medidas distintas, en filas) y, si conoce todas las cajas (`caja.csv`), se niega a empezar antes de mover nada si alguna no cabe.
- `giro:<grados>` → guarda en `hmiGiroPc` el giro que ha leído el PC y contesta `giro_ok`. La app lo pone junto al giro que colocó RAPID.

**Dónde recoge el robot.** Una caja girada toca el sensor antes que una recta, así que se para antes del centro de recogida teórico (hasta 41 mm para un cubo de 200 mm a 45°). El PC lo calcula en simulación (`centro_parada`, con `sensor_cinta_y` de `config_celda.json`) y lleva la pinza al centro real de la caja, como haría una cámara.

## 4. Conexiones del Station Logic (las 16)

| Origen | Destino |
|---|---|
| `ControllerTFG_EGM.PinzaCerrar` | `VacuumPen_SComp.diAttacher_2` |
| `VacuumPen_SComp.doAtacher_2` | `ControllerTFG_EGM.PinzaCerrada` |
| `FinCinta_2.SensorOut` | `ControllerTFG_EGM.CajaEnRecogida` |
| `ControllerTFG_EGM.CintaMover` | `LinearMover.Execute` |
| `ControllerTFG_EGM.CajaPos01` … `CajaPos12` | `PosCaja01.Execute` … `PosCaja12.Execute` |

Los 12 giros: `PosCaja01` = −90°, `02` = −75°, … `07` = 0°, … `12` = 75°. Con la semilla por defecto, las 5 primeras cajas salen con −75°, 30°, 60°, −75° y −30°.

## 5. Límites y cosas sin comprobar

Las he escrito sin poder probarlas en RobotStudio. Si fallan, dime el mensaje exacto:

1. **El sensor con la caja girada.** Es lo que más puede fallar: que el plano ancho detecte la caja o que algo más lo active. Si la caja pasa de largo, la cinta se para por el tiempo máximo (40 s) y RAPID avisa.
2. **Sobrepaso del sensor.** La caja puede avanzar unos milímetros más allá del punto teórico antes de que RAPID pare la cinta. Se mide en la primera prueba (clic derecho sobre `CajaGrande` → Modify → Set Position) y, si importa, se corrige en `sensor_cinta_y`.
3. **`TaskRunRob()`** (reparto entre tareas). Si Check Program lo rechaza, pon `main_movimiento` y `main_pinza` como «Main Entry» de cada tarea y borra el `main` del módulo.
4. **Cerrar el EGM por convergencia** (`\CondTime:=tiempoConv`, ventana ±3 mm). Sustituye a la interrupción con `EGMStop`, que el 15-nov dejaba el EGM abierto. Si una parada con la pinza quieta dura más de `tiempoConv` (2,5 s), la sesión terminaría antes de tiempo: súbelo en el módulo.
5. **El agarre en simulación está forzado**: la caja se une a la herramienta aunque la pinza no la rodee. Compruébalo a ojo. Para que detecte de verdad hay que poner el `LineSensor` entre los dedos.
6. **La pinza del 3D no se mueve.** El mecanismo `PincGripper_tool` de la estación no tiene articulaciones (`NumJoints = 0`): es un solo bloque de CAD, así que no hay dedos que se abran ni se cierren en pantalla aunque la orden llegue. Lo único que `PinzaCerrar` hace en la simulación es activar `VacuumPen_SComp`: al ponerla a 1, `Attacher` une `CajaGrande` a la herramienta y `LogicSRLatch` sube `PinzaCerrada`; al ponerla a 0, `Detacher` suelta la caja donde está y `PinzaCerrada` baja. Cómo comprobarlo, sin Play de más: en **Simulación → Señales** (o el I/O Simulator) mira `PinzaCerrar` y `PinzaCerrada` mientras corre la tanda, o en la app la tarjeta «Pinza»; la caja debe empezar a moverse con la herramienta al cerrar y quedarse en la mesa al abrir. Para ver los dedos moverse hay que partir el CAD en cuerpo y dos dedos y crear un mecanismo de herramienta con dos articulaciones lineales movidas por un `JointMover` que cuelgue de `PinzaCerrar`.
7. **Apertura de la pinza.** Según mis notas del CAD, la apertura es de unos 40 mm y la caja del 3D mide 200 mm: en pantalla los dedos atravesarán la caja.
8. **Alcance y ruta de HOME.** `pSeguro` = (600, -6.5, 543) TCP es el punto de espera sobre la cinta y la pose de arranque del EGM (en la brida, `pSeguroBrida` = (600, -6.5, 690)). Está 300 mm más alto que el punto donde las diagonales siguieron bien (390 en la brida): a esa altura la pinza quedaba dentro de la caja que llega. Comprobado con la cinemática del GoFa: es alcanzable y el barrido de vuelta desde la salida pasa a más de 59 mm sobre la caja de la mesa. El target `pSeguro` de la estación sigue en (240, 270, 600): actualízalo o bórralo antes de sincronizar, o puede volver a escribirse el valor viejo en el módulo. `caja.csv` se busca en la carpeta HOME de `ControllerTFG_EGM`.
9. **Datagramas tras `EGMStop`.** Un [foro de ABB](https://forums.robotstudio.com/discussion/13134/problems-with-restarting-egm-communication) cuenta que el robot sigue enviando unos 1,7 s después. El PC podría tomarlos por el arranque de la siguiente caja.
10. **La masa de la pinza** (`herrPinza`, 0,5 kg) es provisional. En simulación no importa.

## 6. Si algo falla

| Síntoma | Causa probable |
|---|---|
| RobotStudio no abre la estación | El fichero editado a mano. Restaurar `.bak3_antes_v3` |
| `T_COM` se para al arrancar | El PC no estaba escuchando en 127.0.0.1:5010 |
| `.\PuenteEgm.exe` no se reconoce como nombre de un cmdlet | Estás en la carpeta del PC (la de WSL). El puente se lanza en otra ventana, desde `C:\Users\Viktor\source\repos\TFM_Windows\robotica\puente_egm\PuenteEgm\bin\Release\net8.0` (paso 8) |
| `RAPID symbol 'main' was not found` en una tarea | El módulo no está cargado en esa tarea |
| La caja no aparece al inicio de la cinta | Falta la conexión `CajaPosKK` → `PosCajaKK`, o la señal no existe |
| La caja aparece pero no avanza | Falta la conexión `CintaMover` → `LinearMover.Execute` |
| La caja pasa de largo del sensor | `FinCinta_2` sin conexión a `CajaEnRecogida`, o el plano no la detecta |
| «La caja no ha llegado al sensor de la cinta» | Lo mismo: el sensor no se activó en 40 s |
| `fallo_pinza` | `PinzaCerrada` no cambió en 3 s (al cerrar no subió a 1; al abrir no bajó a 0): revisa `PinzaCerrar` → `diAttacher_2` y `doAtacher_2` → `PinzaCerrada` |
| `fallo_egm` | El EGM no se cerró a tiempo tras `fin_caja`: el robot no llegó a quedar convergido (ventana ±3 mm) en la salida (punto 4 de los límites) |
| La app dice «Sin conexión con RAPID» | El módulo nuevo no está cargado en `T_ROB1`, o el controlador no se reinició tras copiar la app |
| La app dice «No encuentro en RAPID: …» | `MOD_CajaPinza.mod` es el antiguo (sin las PERS `hmi*`): cárgalo en `T_ROB1` y `T_COM` |
| INICIAR o un ajuste da «Failed to get Mastership» | Otro cliente tiene el acceso de escritura a RAPID (RobotStudio con Request Write Access): suéltalo |
| El programa no se mueve y la app dice «Listo para empezar» | Falta pulsar INICIAR TANDA (o `usarHmi := FALSE` si no usas la app) |
| La app bloquea INICIAR TANDA: «caben N cajas» | Lo mismo, visto antes de empezar (pestaña Mesa) |
| El PC dice «La caja N no cabe en la mesa» | No queda sitio para esa caja con la zona, el hueco y los límites actuales: agranda la zona, baja `mesaHueco`, sube `egmMaxPos` o baja las cajas |
| El PC dice «el robot ha dejado de enviar datagramas EGM» | La tanda se abortó o el programa se paró en RAPID: relanza el PC y da Play |
| El PC dice «RAPID no contesta a 'lote'» o a 'mesa' | `T_ROB1` y `T_COM` tienen el módulo antiguo |
| El PC dice «RAPID está en modo real y el PC en simulación» | La app puso Real y el PC lee `caja.csv` (o al revés): `modo_simulacion` de su configuración y la app deben coincidir |
| La app avisa «El PC lee X° y RAPID puso la caja a Y°» | El PC usa un `caja.csv` que no es de esta tanda (ruta de `csv_caja`) |
| `50027 Joint Out of Range` al volver a `pSeguroBrida` tras soltar la caja | Ya no debería pasar: la vuelta es por articulaciones (`MoveAbsJ`) y la salida sube por encima de la caja. Tras un error de ejecución hay que mover el PP a Main antes del Play |
| Al acabar, el programa sigue corriendo sin movimiento y el puente sigue recibiendo ciclos | El EGM no termina: lo mismo que `fallo_egm`. Con la versión anterior (interrupción + `EGMStop`) pasaba siempre |
| Error de alcance en el `MoveJ` | Punto inalcanzable con la pinza: bajar `pSeguro` |
| `caja.csv` no aparece | RAPID no lo ha generado, o la carpeta HOME es otra |
| El PC dice «punto fuera del espacio del puente» | Se está usando `config.json` en vez de `config.celda.json` (el espacio llega a x = 800) |
| Al empezar el EGM el robot va a un sitio inalcanzable (errores 50375 y 50366) y el PC se rompe | `semantica` del puente en `desplazamiento`: tiene que ser `absoluta` (la consola del puente debe decir `semantica=absoluta`) |
