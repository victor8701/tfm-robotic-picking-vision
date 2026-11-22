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

**Primera vez con el socket de RAPID en el puente (una vez).** Desde el 21-nov, `T_COM` ya no se conecta a un servidor del PC: se conecta al **puente EGM**, que lo guarda y se lo pasa al PC por su conexión de control. RAPID no cambia (`ipPC` y `puertoPC` siguen en `127.0.0.1` y 5010); cambia quién escucha en ese puerto. Hay que actualizar el puente en Windows (copiar 4 ficheros y compilar) y añadir una línea a su configuración:

a. **Windows (PowerShell):** copiar el C# nuevo al clon y compilar.
```
foreach ($f in "RapidPuente","Config","Program","ServidorControl") { Copy-Item "\\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica\puente_egm\PuenteEgm\$f.cs" "C:\Users\Viktor\source\repos\TFM_Windows\robotica\puente_egm\PuenteEgm\" }
cd C:\Users\Viktor\source\repos\TFM_Windows\robotica\puente_egm\PuenteEgm
dotnet build -c Release
```
b. En `C:\Users\Viktor\Desktop\TFM_RAPID\config.celda.json`, dentro de la sesión `brazo1`, justo después de la línea `"puerto_control": 7001,`, añade:
```json
"rapid": {"ip": "127.0.0.1", "puerto": 5010},
```
c. Los `config_celda.json` y `config_celda_windows.json` del PC ya llevan `"via": "puente"` en `socket_rapid`. Para volver a como era antes (el PC de servidor del socket), pon `"via": "pc"` ahí y quita la línea `rapid` del puente: no pueden estar los dos escuchando en el 5010. Con el controlador **real**, `ipPC` en RAPID pasa a ser la IP del PC con el puente (la misma a la que ya manda el EGM) y `ip` en el puente, esa IP o `0.0.0.0`.

Orden de arranque:
1. **Puente EGM**, en una ventana de **PowerShell de Windows para él solo**. El `.exe` no está en la carpeta del PC (la de WSL del paso 2): si lo lanzas desde allí sale «`.\PuenteEgm.exe` no se reconoce como nombre de un cmdlet». Hay que ir antes a la carpeta donde está compilado:
   ```
   cd C:\Users\Viktor\source\repos\TFM_Windows\robotica\puente_egm\PuenteEgm\bin\Release\net8.0
   .\PuenteEgm.exe "C:\Users\Viktor\Desktop\TFM_RAPID\config.celda.json"
   ```
   Sin `--prueba`. La consola debe decir `semantica=absoluta`, `socket de RAPID TCP 127.0.0.1:5010 ...` y `Puente en marcha. Ctrl+C para parar.` (cuando RAPID se conecte, añadirá `RAPID conectado al socket desde 127.0.0.1:...`); no cierres esa ventana. Ese `.exe` es del clon `TFM_Windows` (compilado el 15-nov): el código de la carpeta de WSL no se compila solo. Si cambias el C#, cópialo a `TFM_Windows` y compila en `...\puente_egm\PuenteEgm` con `dotnet build -c Release`. Con `config.celda.json` no hay problema: ya pone `"semantica": "absoluta"`, y el clon aún tiene `desplazamiento` como valor por defecto.
2. **PC**, en **otra ventana de PowerShell de Windows**. El WSL está en modo NAT y no alcanza el puente, que escucha en el `127.0.0.1` de Windows:
   ```
   cd \\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica
   & "C:\Program Files\Python311\python.exe" -m celda.ciclo celda\config_celda_windows.json
   ```
   Es la misma configuración con la ruta de `caja.csv` en formato Windows. Queda esperando (`Esperando al socket de RAPID del puente...`) a que RAPID se conecte al puente. Conviene que esté en marcha antes del Play; ya no es obligatorio, porque el puente guarda la conexión de RAPID hasta que el PC aparezca. Si el puente es el viejo, sale `comando desconocido: rapid_estado`: recompílalo (punto a).
3. **RobotStudio**: espera unos 10 segundos, **Reset** y **Play** una sola vez.

**Variante con ROS 2** (el ciclo del PC como nodo, en vez de `python -m celda.ciclo`; el porqué y los topics, en `docs/ros2.md`). El orden es el mismo: puente, celda, Play. Solo cambia cómo se lanza la celda. El `python -m celda.ciclo` de arriba sigue valiendo. Probado el 21-nov con un `T_COM` falso: WSL2 llega al puente de Windows y las órdenes de ROS llegan a RAPID y vuelven. Sin probar con RobotStudio.

*Una sola vez (preparar la conexión WSL2 ↔ Windows):*

a. **Compilar** (y cada vez que cambies algo de `ros2/`). **Linux (terminal de Ubuntu en WSL2):**
```
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select robotica_bimanual
```
b. **Averiguar la IP de Windows vista desde WSL2.** **Linux (WSL2):**
```
ip route show default | awk '{print $3}'
```
Da algo como `172.27.48.1`. Esa IP puede cambiar al reiniciar el PC: si cambia, repite b, c y d (en la d, la subred de la regla).

c. **Decir al puente que escuche en esa IP.** No es un comando: es editar una línea del fichero. **Windows (PowerShell):**
```
gedit C:/Users/Viktor/Desktop/TFM_RAPID/config.celda.json
```
Busca con Ctrl+F `ip_control`, cambia solo la IP y guarda:
```
"ip_control": "172.27.48.1",
```
No pongas `0.0.0.0`: abriría el control del robot (que no pide contraseña) a la Wi-Fi. Con esa IP, `python -m celda.ciclo` desde Windows ya no conecta con el puente; para volver a esa prueba, pon `"127.0.0.1"`. Para comprobar el cambio: **Windows (PowerShell)**
```
Select-String -Path C:\Users\Viktor\Desktop\TFM_RAPID\config.celda.json -Pattern '"ip_control"'
```
d. **Cortafuegos de Windows.** Sin esto, WSL2 no llega al puente (`timed out`). Hace falta administrador: menú Inicio, escribe `PowerShell`, clic derecho en **Windows PowerShell**, **Ejecutar como administrador**, **Sí**. En esa ventana, uno a uno:

1. Ver las reglas del puente (no cambia nada). Las de la red `Public` con `Block` son las que sobran:
```
Get-NetFirewallRule -DisplayName "puenteegm.exe" | Select-Object DisplayName, Profile, Direction, Action | Format-Table -AutoSize
```
2. Quitar los bloqueos de entrada del puente (si no hay ninguno, no sale nada y no pasa nada):
```
Get-NetFirewallRule -DisplayName "puenteegm.exe" | Where-Object { $_.Action -eq 'Block' -and $_.Direction -eq 'Inbound' } | Remove-NetFirewallRule
```
3. Permitir solo el puerto de control, y solo desde la subred de WSL2 (cambia `172.27.48.1` por tu IP de b, y `172.27.48.0/20` por su subred, que es la IP con el último número a 0 y `/20` si la IP de WSL es `172.27.5x.x`):
```
New-NetFirewallRule -DisplayName "PuenteEgm control desde WSL" -Direction Inbound -Protocol TCP -LocalPort 7001 -LocalAddress 172.27.48.1 -RemoteAddress 172.27.48.0/20 -Profile Any -Action Allow
```
*Cada vez:*

e. **Puente EGM**, en una ventana de PowerShell de Windows para él solo (como en el punto 1; ya lleva el relé de RAPID). Si había uno en marcha, ciérralo antes con Ctrl+C: tiene que leer el `ip_control` nuevo. **Windows (PowerShell):**
```
cd C:\Users\Viktor\source\repos\TFM_Windows\robotica\puente_egm\PuenteEgm\bin\Release\net8.0
.\PuenteEgm.exe "C:\Users\Viktor\Desktop\TFM_RAPID\config.celda.json"
```
Debe decir `control TCP 172.27.48.1:7001`, `socket de RAPID TCP 127.0.0.1:5010` y `Puente en marcha`.

f. **Comprobar que WSL2 llega al puente.** **Linux (WSL2):**
```
HOST=$(ip route show default | awk '{print $3}'); timeout 5 bash -c "echo > /dev/tcp/$HOST/7001" && echo "conecta con $HOST" || echo "NO conecta con $HOST"
```
Tiene que decir `conecta`. Si no: o el puente no está en marcha (e), o falta el cortafuegos (d), o la IP del c no es la de b.

g. **Celda por ROS 2.** **Linux (WSL2)**, en una ventana distinta de la del puente:
```
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
export PYTHONPATH=$HOME/repos/tfm-robotica-bimanual/robotica:$PYTHONPATH
ros2 launch robotica_bimanual celda_real.launch.py config:=$HOME/repos/tfm-robotica-bimanual/robotica/celda/config_celda.json host:=$(ip route show default | awk '{print $3}')
```
`host` es la IP de Windows vista desde WSL2 (la saca el propio comando). Usa `celda/config_celda.json` (rutas de Linux, `caja.csv` en `/mnt/c/...`), no el `_windows`. Debe salir `Esperando a RAPID por /rapid/estado (socket del puente)...` y ningún aviso de `timed out`. Para parar, Ctrl+C.

h. **RobotStudio.** **Reset** y **Play** una sola vez. En la app: modo **Simulación**, y la primera vez `nCajas := 1` e `indiceFijo := 7`; luego **CAJA EN POSICIÓN** como siempre. El socket de RAPID no pasa por WSL2: `T_COM` se conecta al puente, en Windows, igual que con el ciclo de Python. El ciclo no pide nada a RAPID hasta que el robot arranca el EGM de la caja.

i. **Mirar qué hace** (opcional), en otra terminal. **Linux (WSL2):**
```
source /opt/ros/humble/setup.bash
ros2 topic echo /rapid/estado
```
Sale `conectado: false` hasta el Play y `conectado: true` cuando `T_COM` llega al puente. Y para los hechos del ciclo:
```
source /opt/ros/humble/setup.bash
ros2 topic echo /celda/estado
```
Saca una línea JSON por hecho: `inicio`, `caja`, `pinza`, `fin` o `error`. Con la cámara por ROS también `ros2 topic echo /celda/caja`.

*Si falla:*
- RAPID se para con `El PC no ha dirigido la caja N: paro. Revisa el PC.` y la app deja **Valores por defecto**, **Cargar de fichero** y los ajustes en gris: el aviso es la consecuencia; la causa está en la terminal del `ros2 launch` (línea `el ciclo de la celda se ha parado: ...`), y `nodo_celda` ya ha terminado (hay que relanzar la celda, g). La app bloquea los ajustes mientras RAPID está en error y **ABORTAR** no vale con el programa parado: en RobotStudio, **Reset** y **Play**; RAPID vuelve a esperar INICIAR y entonces los ajustes se pueden cambiar (pestaña Parámetros, **Valores por defecto**).
- El ciclo de **Python en Windows** (`python -m celda.ciclo celda\config_celda_windows.json`) se queda en `Esperando al socket de RAPID del puente...` con `timed out` (en Windows, un puerto sin nadie escuchando tarda ~2 s en rechazar y sale como `timed out`): ese ciclo busca el puente en `127.0.0.1`, y con `ip_control` puesto a la IP de WSL2 el puente ya no escucha ahí. Con esa IP, lanza la celda por ROS 2 (g); para el ciclo de Python de Windows, vuelve a poner `"127.0.0.1"` en `ip_control` (c) y reinicia el puente.
- `ros2 topic ...` da un traceback largo con `xmlrpc`: el demonio de ROS está colgado. **Linux (WSL2):**
```
source /opt/ros/humble/setup.bash
ros2 daemon stop
ros2 daemon start
```
- `no llega /brazo1/estado` o `sin estado del puente: timed out`: el puente no está en marcha, o falta el cortafuegos (d), o la IP (b y c) no es la buena.
- `Connection refused`: el puente no escucha en esa IP (revisa el `ip_control` y reinícialo).
- `no llega /rapid/estado`: `nodo_puente` sin conexión con el puente, o lanzado sin `rapid:=true`.
- `el puente no ofrece el socket de RAPID`: falta la sección `rapid` en `config.celda.json`.
- `comando desconocido: rapid_estado`: el puente es el viejo; recompílalo (bloque «Primera vez con el socket de RAPID en el puente», arriba).
- `RAPID no se ha conectado al socket del puente`: falta Play o `T_COM` no ha arrancado.

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
- **3 · Límite del EGM** (PERS `egmMaxPos`, 1500 por defecto; ahora en la pestaña **Parámetros → Movimiento y seguridad**): el controlador para el EGM (Motors Off) si la referencia se aleja más de esto de la posición de espera (600, −6,5, 543). Es lo que más limita cuántas cajas caben: con la mesa en su sitio de ahora, a 1000 llegan **4** cajas de 200 mm y a 1500 llegan **8** (y las 10 cajas de tamaños distintos de la prueba caben todas). Con la mesa donde estaba antes (x −1120, y 342) eran 2 y 5. Se cambia desde la app (pide confirmación) o en el editor de datos RAPID. **Está sin comprobar que el controlador acepte 1500**: si al arrancar el EGM da error, pon 1000. El PC lee el valor de RAPID y aplica el mismo límite. `alcanceMax` (790 mm) es el radio máximo de la pinza desde el eje del robot, comprobado con la cinemática del GoFa hasta TCP z = 585.

**Pestaña «Parámetros»** (ajustes de puesta en marcha). Son PERS de `MOD_CajaPinza.mod`; la app las lee y las escribe antes de `INICIAR TANDA` (durante la tanda están bloqueadas) y el PC las pide a RAPID al empezar con los mensajes `recogida`, `agarre` y `celda`: una sola fuente, ya no hay que tocar el JSON del PC para ellas. Cuatro secciones, una cada vez:

| Sección | Ajuste (PERS) | Uso | Por defecto |
|---|---|---|---|
| Recogida | `recogidaModo` | **Fija**: el centro de la caja es siempre (`recogidaX`, `recogidaY`). **Cámara**: el que mide la cámara en cada caja (más la corrección), dentro de la zona permitida. Solo en Real. | Fija |
| Recogida | `recogidaX`, `recogidaY` | Centro de la caja, mm desde la base. Con cámara, punto nominal. En simulación solo cuenta X (el sensor de la cinta da Y). | 700, 0 |
| Recogida | `recogidaTolX`, `recogidaTolY` | Con cámara: zona ± alrededor del nominal; fuera de ella el PC **no se mueve** y avisa. Protegido. | 50, 50 |
| Recogida | `camaraOffsetX/Y/Giro` | Corrección fina de la calibración, se suma a lo que mide la cámara. | 0 |
| Recogida | `zCinta` | Altura de la superficie de la cinta. Protegido. | 220 |
| Pinza y agarre | `giroPinza` | Giro extra de las mordazas (90 = el otro eje; sustituye al interruptor x/y). | 0 |
| Pinza y agarre | `agarreModo`, `agarrePorcentaje`, `agarreHundimiento` | Altura h del punto de agarre sobre la base de la caja: **Porcentaje** (h = alto × %, 50 = el centro, como antes) o **Desde la tapa** (h = alto − hundimiento: los dedos cierran siempre a esa distancia bajo la tapa). | Porcentaje, 50 %, 30 mm |
| Pinza y agarre | `agarreMinimo` | h no baja de esto (los dedos sobresalen bajo el TCP y no deben tocar la cinta). | 10 |
| Pinza y agarre | `solapeMinimo` | Alto mínimo agarrable: una caja más baja se rechaza. | 10 |
| Pinza y agarre | `aperturaPinza`, `grosorDedo` | El PC rechaza cajas cuyo ancho (el lado que cierra la pinza) no cabe en la apertura, y si el dedo no cabe en `mesaHueco`. 0 = sin comprobar (la apertura del CAD, ≈ 40 mm, no deja coger las cajas de 200 mm de la simulación). | 0, 0 |
| Pinza y agarre | `tcpZ`, `margenAproximacion` | Brida→punto de agarre (147 mm; protegido) y altura sobre la caja al acercarse y transportar. | 147, 65 |
| Tiempos | `tAntesAgarrar`, `tAgarre`, `tSuelta` | Pausas: tras CAJA EN POSICIÓN antes de moverse, tras confirmar el cierre antes de subir, tras confirmar la apertura antes de irse. | 0 s |
| Tiempos | `tMaxPinza`, `tMaxCaja`, `tMaxCamara` | Esperas máximas a `PinzaCerrada` (al cerrar y al abrir), a la caja (0 = sin límite) y a la cámara. | 3, 40, 5 s |
| Tiempos | `tiempoConv` | Segundos quieto en la salida antes de cerrar el EGM (lo que más alarga el ciclo). | 2,5 s |
| Movimiento y seguridad | `velocidad` | Velocidad máxima del TCP que manda el PC, 5 a 100 mm/s (100 = el tope del puente, `paso_mm 0.4`). Empezar lento. Protegido. | 100 |
| Movimiento y seguridad | `zMinima` | Suelo del TCP: el PC rechaza puntos por debajo (0 = el menor de `zCinta` y `mesaZ`). Protegido. | 0 |
| Movimiento y seguridad | `seguroX/Y/Z` | Punto de espera (TCP) donde empieza cada sesión EGM; RAPID recalcula `pSeguro`, `pSeguroBrida` y `pStart` con ellos y con `tcpZ` al empezar. Protegido. | 600, −6,5, 543 |
| Movimiento y seguridad | `egmMaxPos`, `alcanceMax` | Límite del EGM (protegido) y radio máximo de la pinza (solo se muestra). | 1500, 790 |

**Valores por defecto y ficheros.** Arriba de la pestaña hay tres botones y un campo de nombre:
- **Valores por defecto**: pone en todos los ajustes (esta pestaña, la zona de la mesa y la caja de referencia; no los de cada tanda) el valor que tiene el módulo al cargarlo. Pide confirmación, dice cuántos cambian y avisa si entre ellos hay protegidos; si ya están todos, no hace nada.
- **Guardar en fichero**: escribe todos los ajustes en `$HOME/parametros/<nombre>.csv` del controlador, con el nombre que teclees (letras, números, espacio, guion y guion bajo; el `.csv` lo pone la app). Si el fichero existe, pregunta antes de sustituirlo. Guardar vale también con la tanda en marcha.
- **Cargar de fichero**: lee `<nombre>.csv`, enseña cuántos ajustes cambian (con algunos ejemplos y los protegidos) y, si aceptas, los escribe en RAPID como si los cambiaras a mano. Las líneas que no valen (ajuste desconocido, valor no numérico, fuera de margen, modo inexistente) se ignoran y se dicen; no se carga nada que esté fuera de margen. Bajo los botones salen los `.csv` que hay en la carpeta: tocar uno rellena el nombre.
- Formato: `parametro;valor;unidad;descripcion`, una línea por ajuste y punto decimal. Se puede editar a mano (en Excel vale la coma decimal y los separadores `;`, `,` o tabulador; la cabecera, las líneas vacías y las que empiezan por `#` son opcionales) y solo hace falta que cada línea lleve el nombre del ajuste y su valor. En el controlador virtual, la carpeta es `...\Virtual Controllers\ControllerTFG_EGM\HOME\parametros`: desde Windows se copian los ficheros de ahí y hacia ahí. **Sin comprobar en el controlador:** que el usuario de la app tenga permiso de escritura en `$HOME` por RWS (si no, la app lo dice con el motivo).

Los ajustes **protegidos** piden confirmación y explican qué cambian. **Altura de agarre:** tras calcular h, el PC recalcula todas las alturas (agarre, aproximación, viaje, depósito, salida); en simulación se ve con las cajas de tamaños distintos. En real el alto de cada caja tiene que darlo la cámara (o, sin ella, no hay forma de saberlo: el PC no se mueve). **Cámara:** si no ve la caja o la ve fuera de la zona, el PC **se para**; nunca cae al punto fijo por su cuenta. **No hecho:** la detección de la cámara (`FuenteCamara`), los perfiles «Simulación»/«Laboratorio», la masa de la pinza (`herrPinza` solo se usa para el alcance: el EGM va con `tool0`) y seguir una caja en movimiento por la cinta.

El dibujo de la pestaña muestra la mesa desde arriba, la base del robot, el lado de entrada, los sitios (dejada, en curso, de esta tanda, libre) y en **rojo lo que el robot no alcanza** con la caja de referencia. Si la tanda no cabe y las cajas son iguales (simulación, tamaños fijos), INICIAR TANDA se bloquea y dice cuántas caben. Con tamaños distintos o en real la cuenta es solo una cota: el PC comprueba **antes de empezar** que caben todas las de `caja.csv` y, con cámara, cada caja antes de moverla; si una no cabe, se para con un mensaje.

Modo **Real**: RAPID no mueve la cinta ni escribe `caja.csv`, y la orientación la lee la cámara del PC (todavía pendiente: `FuenteCamara` no está hecha). El PC y RAPID tienen que estar en el mismo modo: el PC lo comprueba con `lote` y se niega a empezar si no coinciden.

### Paso 10. Cajas con su tamaño en el 3D (complemento CajasVariables)
Sin este paso, la simulación tiene **una sola pieza de 200 mm** (`CajaGrande`) que los `Positioner` recolocan en cada caja: no se ve el tamaño de cada caja ni el reparto en la mesa. El complemento (`robotica/rapid/estacion/CajasVariables`, ver su README) vigila `CajaGrande` y, cada vez que RAPID coloca una caja:
- la **redimensiona** con el largo, ancho y alto de su línea de `caja.csv` (misma caja, tamaño variable), con el mismo centro y la cara de abajo en la cinta, así que el sensor, el agarre y los `Positioner` siguen igual; la pinza agarra a la altura de cada caja (`alto / 2`) y se ve su trayectoria distinta;
- deja una **copia** de la caja anterior donde se quedó en la mesa: se ve el reparto en filas. Al terminar la tanda (RAPID escribe `fin_tanda.txt` en `HOME`) esperan 3 s y desaparecen todas, incluida la última, que se oculta; al empezar otra tanda (RAPID reescribe `caja.csv`) también se quitan las copias y la caja se vuelve a mostrar. Si abortas la tanda, no hay marca de fin y las cajas siguen hasta la siguiente.

**`caja.csv` no se toca nunca a mano.** RAPID lo escribe él solo en la carpeta HOME cada vez que pulsas `INICIAR TANDA` en simulación: una línea por caja con `largo;ancho;alto;giro` (en mm y grados), con las medidas que salen de la caja de referencia y de `Cajas de tamaños distintos`. Lo leen el PC y el complemento, y se reescribe en cada tanda. En Real no existe (la cámara da las medidas).

Cómo cargarlo (los pasos de ABB para RobotStudio 2026, «Creating a RobotStudio Add-In»; tu manual de 2023 queda desfasado: ahora el complemento es .NET 10 y la versión mínima es la 26.1):
1. Si instalaste antes el paquete `TFM.CajasVariables`, desinstálalo (Add-Ins → Installed Packages → RobotStudio Add-Ins, clic derecho) y cierra RobotStudio.
2. Copia `Desktop\TFM_RAPID\Addin\ParaBinAddins\CajasVariables.rsaddin` a `C:\Program Files (x86)\ABB\RobotStudio 2026\Bin\Addins\` (el Explorador pide permisos de administrador). Ese `.rsaddin` apunta con `<Path>` a la carpeta de la DLL, `Desktop\TFM_RAPID\Addin\CajasVariables`, que tiene que seguir ahí.
3. Abre RobotStudio 2026 y la estación.
4. Menú **Add-Ins**, panel de la izquierda: clic derecho en «Cajas variables» → **Load Add-In**.
5. En **Output** debe salir «Cajas variables: cargado…» y, con la estación abierta, «Cajas variables: 12 Positioner, caja de 200 x 200 x 200 mm, csv: …». Además se escribe `C:\Users\Viktor\AppData\Local\Temp\CajasVariables.log`.

**Actualizar el complemento y el módulo (fin de tanda, 21-nov).** Con RobotStudio abierto la DLL está bloqueada y no se puede sustituir. En este orden:
1. Cierra RobotStudio.
2. **Windows (PowerShell):** copia la DLL nueva al escritorio (la antigua queda como `CajasVariables.dll.antes_fin` si ya la copié yo; si no, copia la tuya antes):
```
Copy-Item "\\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica\rapid\estacion\CajasVariables\bin\Paquete\CajasVariables.dll" "C:\Users\Viktor\Desktop\TFM_RAPID\Addin\CajasVariables\CajasVariables.dll" -Force
```
3. Abre RobotStudio y la estación. En **Output** debe salir `Cajas variables: cargado...`; si no, **Add-Ins** → clic derecho en «Cajas variables» → **Load Add-In**.
4. Recarga `MOD_CajaPinza.mod` en `T_ROB1` y `T_COM` (paso 5). El del escritorio ya es el nuevo. Al recargar, los ajustes vuelven a los del módulo (recogida 700/0, altura de la cinta 220...).
5. Prueba una tanda: al terminar, en `Output` sale `Cajas variables: tanda terminada: N cajas quitadas de la mesa y la ultima, oculta.` y el 3D queda vacío a los 3 s.

El paquete `.rspak` (`Desktop\TFM_RAPID\Addin\TFM.CajasVariables-1.1.rspak`, Add-Ins → Install Package) es una vía que no está en el manual de ABB y con la que no llegó a cargar: un complemento instalado así no se carga solo, y no se ha comprobado que «Load Add-In» funcione con él.

Límites: está compilado contra las DLL de tu RobotStudio 2026, pero **no se ha ejecutado**; qué hace al correr (crear la caja con `Body.CreateSolidBox`, copiar la pieza, el sensor con la caja nueva) está por comprobar. Si algo falla, mándame lo que salga en Output. Para usar tamaños variables, en la app: pestaña Mesa → «Cajas de tamaños distintos» (o pon medidas distintas en la caja de referencia).

### Paso 11. Visión (la cámara)
La visión mide cada caja que ve una cámara fija y cenital sobre la recogida (largo, ancho, alto, giro y posición en la base del robot). Es lo que el PC lee en modo **Real**; en simulación sigue saliendo de `caja.csv`.

**Todas las pruebas** (con fotos de ejemplo, con las tuyas, la calibración de la cámara y el ciclo con cámara) están en **`docs/vision.md`**, un manual paso a paso con los comandos, lo que tienes que ver en cada prueba y qué hacer si no sale. Empieza por su Prueba 1. Aquí queda solo lo que toca a la celda.

**Conectarlo a la celda (modo Real).** Hace falta la calibración de la cámara (`camara.json`, Prueba 9 de `docs/vision.md`). **Windows:** edita `\\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica\celda\config_celda_windows.json`: `"modo_simulacion": false` y una sección `camara` (las rutas relativas se toman desde la carpeta de ese JSON, `robotica\celda\`; copia ahí `camara.json`):
```json
"camara": {
  "calibracion": "camara.json",
  "origen": {"tipo": "realsense", "tam": [1280, 720], "fps": 15},
  "alto_mm": null,
  "modo": "profundidad"
}
```
`origen` también puede ser `{"tipo": "carpeta", "ruta": "fotos"}` (imágenes guardadas, para ensayar: Prueba 10), `{"tipo": "opencv", "indice": 0}` (cámara USB, sin profundidad: entonces `alto_mm` con el alto de las cajas y `"modo": "color"`) o la RealSense, que necesita su librería:
```
# Windows (PowerShell)
cd \\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica
$py = "C:\Program Files\Python311\python.exe"
& $py -m pip install pyrealsense2
```
`modo` puede ser `color`, `fondo` (con `"fondo": "foto_sin_cajas.png"`) o `profundidad`; también valen `hsv_bajo`, `hsv_alto` y `umbral_fondo`.

En la app: **Real**, pestaña **Parámetros → Recogida → Posición de la caja = Cámara** (solo en Real), `recogidaX/Y` en el punto donde espera la pinza, la zona permitida ±X ±Y, la altura de la cinta igual que la `--z` de la calibración y, en **Tiempos**, el máximo esperando a la cámara. Con **Fija**, el PC usa siempre `recogidaX/Y` y de la cámara solo toma las medidas y el giro. El PC y la app tienen que estar en el mismo modo. Después se arranca como en el paso 8 (puente, PC, Play; el PC con `celda\config_celda_windows.json`). Si lanzas la celda por ROS 2 (variante del paso 8), la cámara también puede venir de un driver de ROS: en `celda/config_celda.json` pon `"origen": {"tipo": "ros"}` (topics por defecto `/camera/color/image_raw` y `/camera/aligned_depth_to_color/image_raw`; con la RealSense, `ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true` en otra terminal de Linux antes del `ros2 launch` de la celda). Si la cámara no ve una caja entera a tiempo o la ve fuera de la zona, el PC se para con un aviso: no se mueve.

**Primera prueba del modo Real en casa (sin cámara ni celda).** El PC lee fotos de ejemplo (`ejemplos_vision/celda`, una por caja) en vez de una cámara, y el robot virtual de RobotStudio va donde las ve. Hay una configuración hecha, `celda/config_celda_real_casa.json` (modo Real, 3 cajas, cámara de carpeta), para no tocar la de simulación. Con ROS 2, como en el paso 8:

1. **Fotos de ejemplo** (solo si no existe la carpeta `ejemplos_vision/celda`). **Linux (WSL2):**
```
cd ~/repos/tfm-robotica-bimanual/robotica && python3 -m vision.generar_ejemplos ejemplos_vision
```
2. **Puente** (Windows, PowerShell), igual que siempre (paso 8, punto e).
3. **Celda en modo Real.** **Linux (WSL2)**, el mismo `ros2 launch` del paso 8 (g) pero con otro `config`:
```
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export PYTHONPATH=$HOME/repos/tfm-robotica-bimanual/robotica:$PYTHONPATH && ros2 launch robotica_bimanual celda_real.launch.py config:=$HOME/repos/tfm-robotica-bimanual/robotica/celda/config_celda_real_casa.json host:=$(ip route show default | awk '{print $3}')
```
4. **RobotStudio:** Reset y Play. **En la app:** pestaña Parámetros → **Valores por defecto** (recogida **Fija** en 700 y 0, altura de la cinta 220; con **Cámara**, la misma X e Y y zona ±50). Pestaña Tanda: modo **Real**, **3** cajas, **INICIAR TANDA**, y **CAJA EN POSICIÓN** en cada caja.

**Elegir la carpeta de fotos desde la app y ver lo que ve el PC (22-nov).** Con `config_celda_real_casa.json` (lleva `"visor": true` y `"raiz_carpetas"`):
- **En el PC se abre la ventana «Vision de la celda»** (como la del trabajo de Robótica Industrial): la foto que ve la cámara, el **contorno** de lo que el programa considera la caja, un **punto verde en el centro** con sus coordenadas en mm y el **hilo**, una línea de extremo a extremo de un lado corto al otro por el centro (a lo largo del eje largo), más las medidas. Arriba, la carpeta, «foto i de N» y el estado: **VISTA PREVIA** (la foto que se usará para la siguiente caja, sin gastarla) y, 3 s después de medir cada caja, **CAJA k: MEDIDA**. Con la tecla `q` o cerrando la ventana, el ciclo sigue sin ella. En Ubuntu se abre con WSLg (si no hay pantalla lo avisa y sigue sin ventana).
- **En la app**, pestaña Parámetros → **Cámara** (solo en Real, antes de pulsar INICIAR): botones con **La del PC** y las carpetas que da el PC (hoy `celda` y `celda_zapatos`, las que tienen `camara.json`); al pulsar una, en 1–2 s la app dice **«N fotos»** y el estado, y la ventana del PC pasa a esa carpeta. **La del PC** es la cámara que tenga la configuración del PC: en `config_celda_real_casa.json` es la carpeta de ejemplo `celda` (por eso se ven fotos y no una cámara), y el estado lo dice («la de la configuración: carpeta celda»). Con una cámara de verdad (`origen` `opencv`, `realsense` o `ros`) sale «cámara en vivo». **Valores por defecto** vuelve a ella. `celda_zapatos` son tres fotos de cajas alargadas (330 × 190 × 120 y 300 × 180 × 100, giros 0°, 35° y −60°) para ver bien el hilo.
- Solo salen carpetas con su propio `camara.json` (la calibración de esa cámara). Tus fotos reales (`planta_real_prueba`) no salen hasta calibrarlas (Prueba 7 de `docs/vision.md`) y poner el `camara.json` en su carpeta.

**RobotStudio coge cajas por la webcam (23-nov).** WSL2 no abre cámaras USB, así que con la webcam la celda se lanza con el **ciclo de Python de Windows** (sin ROS 2). Antes comprueba la webcam sola (`docs/vision.md`, Prueba 11: `python -m vision.ver_camara --listar --ver`) y apunta su `indice`.

*Cómo funciona:* cada caja se coge **una a una**. Pones una caja delante de la webcam, pulsas **CAJA EN POSICIÓN** y el PC mira la cámara en ese momento, mide esa caja (largo, ancho, giro y dónde está) y el robot de RobotStudio va a ese punto, la coge y la deja en la mesa. Se repite tantas veces como pongas en **Tanda → Cajas** de la app (1 por defecto). La calibración de la webcam, `celda/camara_webcam.json`, es **aproximada** y centra la imagen en el punto de recogida (700, 0): una caja bajo el centro de la imagen es una caja en (700, 0); si la mueves a la derecha en la imagen, el robot va a +x, y si la subes en la imagen, a +y. Las medidas y la escala son aproximadas; para medir de verdad hay que calibrar (Prueba 7 de `docs/vision.md`).

*Calibración real (recomendada):* en vez de la aproximada de abajo, calibra tu webcam con el **asistente con ventana** (`docs/vision.md`, Prueba 12): tablero impreso, ~15 fotos, el tablero tendido con su centro en la recogida (700, 0), y «Guardar la calibración» en `celda\camara_webcam.json`. **Windows (PowerShell)**, en la carpeta `robotica`:
```
& "C:\Program Files\Python311\python.exe" -m calibracion.app_camara --indice 1 --tam 1280x720 --salida celda\camara_webcam.json
```
Con ella, las medidas y las posiciones son reales y puedes usar la recogida en modo **Cámara** con una zona permitida más pequeña. Si prefieres no calibrar, la aproximada:

*Preparación (una vez):*
1. **Ajusta la calibración a tu webcam** si no está a 600 mm de la mesa. Mide la distancia de la webcam a la superficie donde pones la caja y regenera el fichero. **Windows (PowerShell)**:
```
cd \\wsl.localhost\Ubuntu-22.04\home\ubuntu22\repos\tfm-robotica-bimanual\robotica
```
```
& "C:\Program Files\Python311\python.exe" -m vision.ver_camara --indice 0 --altura 700 --fov 62 --alto 120 --guardar-calibracion celda\camara_webcam.json --z 220 --centro 700,0
```
(`--indice` es el de tu webcam, `--altura` la distancia en mm, `--fov` su campo de visión horizontal (62 es normal en una webcam) y `--alto` el alto de tu caja. Se cierra con `q`.) Con la webcam a 600 mm ve unos 720 × 400 mm de superficie. Pon también `indice` y `alto_mm` en `celda/config_celda_real_webcam.json` (`origen` y `camara`).
2. **Puente** (Windows, PowerShell), como siempre. Si su `ip_control` no es `172.27.48.1`, pon esa IP en `puente.host` del JSON anterior.

*Cada vez:*
1. **RobotStudio:** Reset y Play (con el módulo ya recargado, paso 5).
2. **App:** pestaña Parámetros → **Valores por defecto**; luego **Recogida**: *Posición de la caja* = **Cámara**, recogida X = 700, Y = 0 y la **zona permitida ± X / ± Y** = lo que dejes moverse la caja (por ejemplo 150: el robot solo va si la caja está a menos de 150 mm del centro de la imagen; si no, se para con un aviso y no se mueve). Pestaña Tanda: modo **Real** y **Cajas** = las que vayas a coger (1).
3. **Celda con la webcam.** **Windows (PowerShell)**, en la carpeta `robotica` de arriba:
```
& "C:\Program Files\Python311\python.exe" -m celda.ciclo celda\config_celda_real_webcam.json
```
   **Qué cámara abre:** la del JSON (`indice` 1: la webcam externa). Para elegirla al lanzar, sin tocar el JSON, añade `--indice`: `--indice 0` es la del portátil y `--indice 1` la webcam (los números que salen en `vision.ver_camara --listar --ver`):
```
& "C:\Program Files\Python311\python.exe" -m celda.ciclo celda\config_celda_real_webcam.json --indice 0
```
   En la terminal sale `Cámara USB: índice N` y en la banda de la ventana «camara USB N». Se abre la ventana con la webcam en vivo y la caja que identifica (contorno, centro con sus coordenadas en el robot, hilo y medidas); `camara.cajas` del JSON (1) limita cuántas identifica a la vez.
4. **App:** **INICIAR TANDA**. Pon la caja delante de la webcam, **entera** en la imagen, y pulsa **CAJA EN POSICIÓN**. El PC dice en su terminal `Celda: caja 1 de N (...)` con las medidas y el robot va a donde está. Para la siguiente, cambia la caja de sitio y repite.

Si abre la cámara del portátil o la de infrarrojos y no tu webcam, lánzalo con `--indice <el que dio --listar --ver>` (o cambia `indice` en `origen` del JSON; añade `"api": "dshow"` si no abre). Si el PC se para con `fuera de la zona permitida`, la caja está lejos del centro de la imagen: acércala o sube la zona permitida. Si dice `no ve ninguna caja entera`, la caja está cortada por el borde de la imagen o su color no es el del cartón marrón (Prueba 5 de `docs/vision.md`). *Sin probar con RobotStudio.*

*Para actualizar (módulo, app y ejemplos):*
1. **Fotos de ejemplo** (crea `celda_zapatos`). **Linux (WSL2):**
```
cd ~/repos/tfm-robotica-bimanual/robotica && python3 -m vision.generar_ejemplos ejemplos_vision
```
2. **Módulo de RAPID:** el `MOD_CajaPinza.mod` del escritorio ya es el nuevo (copia anterior: `.antes_camara`). Recárgalo en `T_ROB1` y `T_COM` (paso 5): los ajustes vuelven a los del módulo.
3. **App:** ya están copiados `app.js`, `logica.js` y `demo-rws.js` nuevos en `Desktop\TFM_RAPID\WebApps\CajaPinza` y en la carpeta `HOME\WebApps\CajaPinza` del controlador virtual (copias: `.antes_camara`). Recarga la app en el navegador del controlador; si sigue la antigua, reinicia el controlador (Restart) y vuelve a abrirla.
4. Lanza la celda con el `ros2 launch` de arriba (con `config_celda_real_casa.json`).

**Qué debes ver:** en la terminal del launch, `Celda: caja 1 de 3 (199.995 x 139.561 x 120 mm, giro 0 grados)`, luego la 2 (200 × 140, giro −45°) y la 3 (160 × 100 × 90, giro 60°), con su `Pinza: cerrar -> cerrada`; el robot va al punto de la caja y la deja en la mesa. El 3D no muestra cajas (en Real no se mueve `CajaGrande`): la pinza agarra aire. Con una cuarta caja, el PC se para con `La cámara no ve ninguna caja entera` porque no quedan fotos. Ensayado el 22-nov sin RobotStudio (puente y RAPID falsos): las 3 cajas se miden, caben en la mesa y todos los puntos están dentro del espacio del puente. *Sin probar:* con RobotStudio.

*Sin probar:* la cámara y las cajas reales, la RealSense (`pyrealsense2`), `--interactivo` y el ciclo completo en Real con la cámara conectada. Solo se ha probado con imágenes sintéticas.

## 3. Cómo funciona

**Quién habla con quién.** RAPID habla con el puente por **dos canales distintos** (el EGM y el socket) y con la app por un tercero. Solo el puente EGM está en el otro extremo de los dos primeros:

| Canal | De → a | Qué lleva | Sin él |
|---|---|---|---|
| EGM (UDP 6511) | Controlador (el EGM de `T_ROB1`) ↔ `PuenteEgm.exe` | Solo posiciones: dónde está el robot y dónde debe ir, 25 veces por segundo | El robot no se mueve |
| Socket (TCP 5010) | `T_COM` (RAPID) ↔ **el propio puente** (relé de RAPID); el PC habla con él por la conexión de control (comandos `rapid_*`) | Órdenes de pinza (`cerrar`/`abrir`), `fin_caja`, y los ajustes (`lote`, `mesa`, `recogida`, `agarre`, `celda`, `giro`) | La pinza no se abre ni se cierra y el PC no sabe la mesa ni el lote |
| RWS (HTTP) | App del FlexPendant ↔ variables `PERS` de RAPID | Parámetros, botones, señales | La app no ajusta nada |

El puente no interpreta lo del socket (pinza, ajustes): lo pasa tal cual entre RAPID y el PC, y el EGM no lleva más que posiciones. El ciclo del PC (`celda.ciclo` o, con ROS 2, `nodo_celda`) solo habla con el puente: movimiento por `objetivo`/`estado` y RAPID por `rapid_*` (por la conexión de control o, con ROS 2, por `/brazo1/*` y `/rapid/*` a través de `nodo_puente`). Diagrama completo en `docs/ros2.md`.

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
- `recogida`, `agarre` y `celda` → contestan los ajustes de la pestaña Parámetros (`recogida:<modo>:<x>:<y>:<tolX>:<tolY>:<offX>:<offY>:<offGiro>:<tMaxCamara>`, `agarre:<modo>:<porcentaje>:<hundimiento>:<minimo>:<solape>:<apertura>:<grosor>:<giroPinza>`, `celda:<zCinta>:<margenAprox>:<tcpZ>:<seguroX>:<seguroY>:<seguroZ>:<velocidad>:<zMinima>`); el PC los pide justo después de `mesa` y rechaza los incoherentes antes de mover nada.
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
| `probar_en_casa`: «no veo el tablero de 9x6 esquinas» | El tablero no sale entero, está desenfocado o con brillos, o las esquinas contadas no son las interiores (un tablero de 10x7 cuadros tiene 9x6 esquinas) |
| `probar_en_casa`: «no encuentro ninguna caja» | El color no es el del cartón: `--interactivo` para ajustarlo o `--modo fondo`/`profundidad` |
| `calibracion.camara`: error con `--toca 0,0:600.0,-120.0` en PowerShell | Los valores con coma van entre comillas: `--toca "0,0:600.0,-120.0"` |
| `calibracion.camara extrinsecos`: criterio «repetir» o aviso de tablero reflejado | Un punto tocado mal o un índice cruzado: mira `tablero_detectado.png` (índices de las esquinas) y repite el toque |
| El PC se para: «la cámara no ve ninguna caja entera en N s (tMaxCamara)» | Caja fuera de la imagen, cortada por el borde o de otro color; el tiempo es el de la app (Parámetros → Tiempos) |
| El PC se para: «fuera de la zona permitida … no me muevo» | La caja está más lejos del punto de recogida que la zona ±X ±Y de la app: acércala o amplía la zona |
| «falta la seccion 'camara' en config_celda.json» | La app está en Real y la configuración del PC no tiene sección `camara` (Paso 11) |
| El PC dice «punto fuera del espacio del puente» | Se está usando `config.json` en vez de `config.celda.json` (el espacio llega a x = 800) |
| Al empezar el EGM el robot va a un sitio inalcanzable (errores 50375 y 50366) y el PC se rompe | `semantica` del puente en `desplazamiento`: tiene que ser `absoluta` (la consola del puente debe decir `semantica=absoluta`) |
