# La celda por ROS 2

`python -m celda.ciclo` habla con el puente EGM por TCP directo. Con ROS 2, el mismo ciclo corre como **nodo** (`nodo_celda`) y habla con el robot, con RAPID y con la cámara por *topics*. El código del ciclo es el mismo (`celda/ciclo.py`): solo cambia por dónde recibe el estado y manda las órdenes.

## Quién habla con quién

RAPID habla con **un solo programa del PC: el puente EGM** (`PuenteEgm.exe`, en Windows), por dos canales:

- **EGM** (UDP 6511): `T_ROB1` y el puente. Solo posiciones. RAPID se limita a abrir y cerrar la sesión EGM.
- **Socket** (TCP 5010): `T_COM` y el puente. Pinza (`cerrar`/`abrir`), `fin_caja` y ajustes. **Desde el 21-nov el puente es el servidor de este socket** (antes lo era el programa del PC): `T_COM` se conecta a él y el puente pasa los mensajes tal cual, sin interpretarlos. El programa de la celda habla con RAPID por la conexión de control del puente (comandos `rapid_*`).

El ciclo de la celda solo habla con el puente: movimiento por `objetivo` y `estado`, RAPID por `rapid_enviar` y `rapid_recibir`. Con ROS 2, ese hablar es por topics y lo traduce `nodo_puente`.

```
 CONTROLADOR GoFa (RAPID)              PC con Windows                     Ubuntu (WSL2, ROS 2)
┌──────────────────────┐             ┌─────────────────┐   TCP 7001     ┌──────────────────────────────┐
│ T_ROB1  movimiento   │◄══ EGM ════►│                 │◄═ (JSON) ═════►│ nodo_puente                  │
│                      │  UDP 6511   │  PuenteEgm.exe  │  2 conexiones  │   ▲ /brazo1/estado           │
│ T_COM   pinza,       │◄═ socket ══►│  (C#)           │  de control    │   │ ▼ /brazo1/objetivo       │
│         ajustes      │  TCP 5010   │  + relé RAPID   │                │   │ ▲▼ /rapid/orden,respuesta│
│                      │             └─────────────────┘                │ nodo_celda  (el ciclo)       │──► /celda/estado
│ PERS ◄─ RWS (HTTP) ──┼── App del FlexPendant                          │   ▲                          │──► /celda/caja
└──────────────────────┘                                                │   │ /camera/color/image_raw  │
                                                                        │ driver de la cámara          │
                                                                        └──────────────────────────────┘
```

| Tramo | Cómo va | Por qué |
|---|---|---|
| Ciclo ↔ `nodo_puente` | **ROS 2** (`/brazo1/objetivo`, `/brazo1/estado`, `/brazo1/rechazo`, `/rapid/orden`, `/rapid/respuesta`, `/rapid/estado`) | Es lo que se ha pasado a ROS 2 |
| Cámara → ciclo | **ROS 2** si `camara.origen.tipo = "ros"` (cualquier driver: RealSense, USB...) | Se puede usar el driver que haya |
| `nodo_puente` ↔ `PuenteEgm.exe` | TCP 7001 (JSON por línea), **dos conexiones**: una para el movimiento, el estado y enviar a RAPID; otra que espera lo que contesta RAPID | El puente es C# en Windows y el EGM va por UDP, que WSL2 no reenvía (decisión D27). `rapid_recibir` bloquea su conexión hasta que RAPID contesta, y el movimiento no puede parar |
| RAPID (`T_COM`) ↔ puente | TCP 5010 (`ipPC`/`puertoPC` en RAPID) | RAPID no tiene ROS. Al ser el puente el servidor, el controlador (virtual o real) solo tiene que llegar a Windows, que es adonde ya llega el EGM: no hace falta que llegue a WSL2 |
| Puente ↔ controlador | UDP 6511 (EGM) | Protocolo de ABB |

Sigue siendo cierto que **el puente EGM es un `.exe` de Windows** al que `nodo_puente` llega por TCP. Convertirlo en un nodo ROS 2 nativo exigiría ROS 2 en Windows o reenviar el UDP del EGM hacia WSL2; no está hecho.

## Comandos del puente para RAPID

Si la sesión del puente tiene la sección `rapid` (`"rapid": {"ip": "127.0.0.1", "puerto": 5010}` en `config.celda.json`), el control entiende además de `objetivo`/`estado`:

| Comando | Respuesta |
|---|---|
| `{"cmd":"rapid_estado"}` | `{"ok":true,"conectado":bool,"origen":"ip:puerto"}` |
| `{"cmd":"rapid_enviar","msg":"cerrar"}` | `{"ok":true}`, o error si RAPID no está conectado o el mensaje pasa de 80 caracteres (el límite de las cadenas de RAPID) |
| `{"cmd":"rapid_recibir","timeout_s":5}` | `{"ok":true,"msg":"cerrada"}`, o `{"ok":false,"codigo":"timeout"\|"cerrado"\|"desconectado","error":...}`. Sin `timeout_s`, espera sin límite |

Cada Play abre un socket nuevo desde `T_COM`: la conexión nueva sustituye a la anterior. Un socket cerrado por RAPID se detecta (`conectado: false`, `codigo: cerrado`).

## Piezas (`robotica/` y `ros2/robotica_bimanual/robotica_bimanual/`)

- `puente_egm/PuenteEgm/RapidPuente.cs`: el relé (servidor del socket de RAPID) y, en `ServidorControl.cs`, los comandos `rapid_*`.
- `celda/rapid_puente.py`: `RapidPorPuente`, para `python -m celda.ciclo` con `socket_rapid.via = "puente"` (los mismos métodos que `ServidorRapid`).
- `nodo_celda.py`: el nodo del ciclo. Hilo propio para el ciclo y `spin` en el principal.
- `puente_ros.py`: `PuenteRos`, con los mismos métodos que `ClientePuente` (`estado()`, `objetivo(pose)`).
- `rapid_ros.py`: `RapidRos`, con los mismos métodos que `ServidorRapid` (`esperar_cliente`, `enviar`, `recibir`).
- `proveedor_ros.py`: `ProveedorRos`, la cámara por topics (color bgr8 o rgb8, y profundidad 16UC1 en mm o 32FC1 en m).
- `nodo_puente.py`: con `rapid:=true` lleva el socket de RAPID a `/rapid/*` y publica en `/brazo1/rechazo` lo que rechaza el puente.
- `launch/celda_real.launch.py`: lanza `nodo_puente` y `nodo_celda`.

`socket_rapid.via` en `celda/config_celda.json` (y `_windows`): `"puente"` (lo de arriba, el valor de los ficheros del repo) o `"pc"` (como antes: el programa de la celda es el servidor del socket en `ip_escucha:puerto`). No pueden estar los dos escuchando en el 5010: con `"pc"`, quita la sección `rapid` del puente y lanza el launch con `rapid:=false`.

## Topics

| Topic | Tipo | Sentido | Contenido |
|---|---|---|---|
| `/brazo1/objetivo` | `PoseStamped` | ciclo → puente | Pose de la brida en metros, cuaternión (x, y, z, w) (REP 103). El puente solo la reenvía si se renueva cada 0,2 s |
| `/brazo1/estado` | `String` (JSON) | puente → ciclo | Estado del EGM y pose real |
| `/brazo1/rechazo` | `String` (JSON) | puente → ciclo | Objetivo rechazado y motivo |
| `/rapid/orden` | `String` | ciclo → puente | Texto para RAPID: `cerrar`, `lote`, `giro:30.0`... |
| `/rapid/respuesta` | `String` | puente → ciclo | Lo que contesta RAPID: `cerrada`, `lote:2:sim`... |
| `/rapid/estado` | `String` (JSON) | puente → ciclo | `{"conectado":bool,"origen":...}` cada 0,5 s, o `{"error":...}` si el puente no tiene socket de RAPID |
| `/celda/estado` | `String` (JSON) | salida | `inicio`, `caja`, `pinza`, `fin`, `error` |
| `/celda/caja` | `PoseStamped` | salida | Centro y giro de la caja que ve la cámara (metros, base del robot). No sale con `caja.csv`, que no tiene posición |

Se puede mirar todo con `ros2 topic echo /celda/estado`.

## Puesta en marcha

Una sola vez, compilar el paquete (Linux / WSL2):

```bash
cd ~/ros2_ws && colcon build --symlink-install --packages-select robotica_bimanual
```

Cada vez, en este orden:

1. **Windows:** `PuenteEgm.exe` con `config.celda.json`, que lleva la sección `rapid` (ver el manual de RobotStudio, paso 8, para actualizar el puente la primera vez). Si ROS corre en WSL2, `ip_control` tiene que ser `0.0.0.0` (con `127.0.0.1` solo escucha a Windows). Si el cortafuegos pregunta, permitir TCP 7001. La consola debe decir `socket de RAPID TCP 127.0.0.1:5010`.
2. **Cámara** (solo en real y con cámara por ROS), en otra terminal de Linux:
   ```bash
   ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true
   ```
   En `celda/config_celda.json`, sección `camara`: `"origen": {"tipo": "ros"}`. Los topics por defecto son `/camera/color/image_raw` y `/camera/aligned_depth_to_color/image_raw`; se cambian con `"color"` y `"profundidad"` dentro de `origen`. Con `modo` `color` o `fondo` no hace falta profundidad (si la caja no tiene `alto_mm` fijo, sí).
3. **Celda** (Linux / WSL2):
   ```bash
   source /opt/ros/humble/setup.bash
   source ~/ros2_ws/install/setup.bash
   export PYTHONPATH=$HOME/repos/tfm-robotica-bimanual/robotica:$PYTHONPATH
   ros2 launch robotica_bimanual celda_real.launch.py config:=$HOME/repos/tfm-robotica-bimanual/robotica/celda/config_celda.json host:=$(ip route show default | awk '{print $3}')
   ```
   `host` es la IP de Windows vista desde WSL2 (la saca el propio comando). Si ROS corre en Windows, `host:=127.0.0.1`.
4. En RobotStudio, **Reset** y **Play** una vez; en el FlexPendant, **CAJA EN POSICIÓN** como siempre. `T_COM` se conecta al puente y el ciclo arranca cuando `/rapid/estado` dice `conectado`.

Alternativa sin ROS, la de siempre: `python -m celda.ciclo` (TCP directo con el puente; con `via = "puente"` también habla con RAPID a través de él). Sigue funcionando igual.

## Errores típicos

- `no llega /brazo1/estado: ¿están en marcha nodo_puente y el puente EGM?`: falta `nodo_puente` o `PuenteEgm.exe`, o `host` no es el bueno.
- `no llega /rapid/estado ...`: `nodo_puente` sin `rapid:=true` o sin conexión con el puente.
- `el puente no ofrece el socket de RAPID: ... sección 'rapid'`: falta la sección `rapid` en la sesión de `config.celda.json`.
- `comando desconocido: rapid_estado`: el puente es de antes del relé; recompilarlo.
- `RAPID no se ha conectado al socket del puente en N s`: falta Play o `T_COM`, o `ipPC`/`puertoPC` de RAPID no son los de la sección `rapid`.
- `no llegan imágenes por /camera/color/image_raw`: el driver de la cámara no corre o publica con otro nombre (`ros2 topic list`).
- `no llega la profundidad ... align_depth`: la RealSense sin `align_depth.enable:=true`.
- `falta el parametro 'config'`: se ha lanzado el nodo sin la ruta de `config_celda.json`.

## Sin comprobar

- Todo con el controlador (virtual o real): las pruebas usan un `T_COM` falso, un puente real (C#) y, para el movimiento, un puente y una cámara falsos.
- Con el controlador real, `ipPC` en RAPID tiene que ser la IP del PC con el puente (la misma a la que ya manda el EGM) y `ip` de `rapid` en el puente, esa IP o `0.0.0.0`; cortafuegos de Windows con TCP 5010 y 7001 permitidos.
- Una cámara USB real dentro de WSL2 (no se ve sin `usbipd`); una RealSense por USB-IP o la cámara en otra máquina con ROS 2 en la misma red.

## Pruebas

```bash
source /opt/ros/humble/setup.bash
cd ~/repos/tfm-robotica-bimanual/robotica
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/test_ros_celda.py tests/test_puente_e2e.py tests/test_celda_rapid_puente.py
```

- `tests/test_puente_e2e.py` (con el puente C# compilado): el relé contra el puente real: ida y vuelta, mensajes de 80 caracteres, timeout, cierre y reconexión de `T_COM`, y que esperar a RAPID no para el movimiento. Incluye `RapidPorPuente`.
- `tests/test_celda_rapid_puente.py`: el ciclo de dos cajas con RAPID a través del puente real.
- `tests/test_ros_celda.py` (con ROS 2): `PuenteRos`, `RapidRos`, `nodo_puente` (rechazos y socket de RAPID), el ciclo completo por topics con el socket en el puente y con el socket en el PC, el error si RAPID no contesta, la cámara por ROS, y una prueba con todos los saltos de verdad (topics → `nodo_puente` → puente C# → `T_COM` falso).
