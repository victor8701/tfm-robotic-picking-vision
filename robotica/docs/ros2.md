# La celda por ROS 2

`python -m celda.ciclo` habla con el robot por TCP directo con `PuenteEgm.exe`. Con ROS 2, el mismo ciclo corre como **nodo** (`nodo_celda`) y habla con el robot y con la cámara por *topics*. El código del ciclo es el mismo (`celda/ciclo.py`): solo cambia por dónde recibe el estado y manda los objetivos.

## Qué va por ROS 2 y qué no

RAPID habla por **dos canales** con el PC, y ROS 2 solo afecta al ciclo del PC, no a RAPID:

- **EGM** (UDP 6511): el controlador y `PuenteEgm.exe`. Solo posiciones. RAPID (`T_ROB1`) se limita a abrir y cerrar la sesión EGM.
- **Socket** (TCP 5010): `T_COM` y el ciclo del PC. Pinza (`cerrar`/`abrir`), `fin_caja` y ajustes. No pasa por el puente.

```
 CONTROLADOR GoFa (RAPID)                         PC con Windows                      Ubuntu (WSL2, ROS 2)
┌────────────────────────┐                  ┌───────────────────┐               ┌───────────────────────────────┐
│ T_ROB1  (movimiento)   │◄══ EGM UDP 6511 ═►│  PuenteEgm.exe    │◄─ TCP 7001 ──►│ nodo_puente                   │
│                        │   (posiciones)    │  (C#)             │    (JSON)     │   ▲ /brazo1/estado, /rechazo  │
│ T_COM   (pinza+socket) │◄══ socket TCP 5010 (pinza, ajustes) ════════════════════►│   │ ▼ /brazo1/objetivo        │
│                        │                                                        │ nodo_celda  (el ciclo)        │──► /celda/estado
│ PERS ◄── RWS (HTTP) ───┼──── App del FlexPendant                                │   ▲                           │──► /celda/caja
└────────────────────────┘                                                        │   │ /camera/color/image_raw   │
                                                                                  │ driver de la cámara           │
                                                                                  └───────────────────────────────┘
```

| Tramo | Cómo va | Por qué |
|---|---|---|
| Ciclo ↔ puente | **ROS 2** (`/brazo1/objetivo`, `/brazo1/estado`, `/brazo1/rechazo`) | Es lo que se ha cambiado |
| Cámara → ciclo | **ROS 2** si `camara.origen.tipo = "ros"` (cualquier driver: RealSense, USB...) | Se puede usar el driver que haya |
| `nodo_puente` ↔ `PuenteEgm.exe` | TCP 7001 (JSON) | El puente es C# en Windows y el EGM va por UDP, que WSL2 no reenvía. Sigue como estaba (decisión D27) |
| RAPID (`T_COM`) ↔ ciclo | TCP 5010, no pasa por el puente | RAPID no tiene ROS; es el canal de la pinza y los ajustes |
| Puente ↔ controlador | UDP 6511 (EGM) | Protocolo de ABB |

Es decir: el ciclo ya no sabe nada de TCP con el puente, pero **el puente EGM en sí sigue siendo un `.exe` de Windows** al que `nodo_puente` llega por TCP. Convertir el puente en un nodo ROS 2 nativo (fase 2) exigiría ROS 2 en Windows o reenviar el UDP del EGM hacia WSL2; no está hecho.

## Piezas nuevas (`ros2/robotica_bimanual/robotica_bimanual/`)

- `nodo_celda.py`: el nodo. Hilo propio para el ciclo y `spin` en el principal.
- `puente_ros.py`: `PuenteRos`, con los mismos métodos que `ClientePuente` (`estado()`, `objetivo(pose)`). El ciclo no distingue uno de otro.
- `proveedor_ros.py`: `ProveedorRos`, la cámara por topics (color bgr8 o rgb8, y profundidad 16UC1 en mm o 32FC1 en m).
- `nodo_puente.py`: ahora publica en `/brazo1/rechazo` lo que el puente rechaza (objetivo fuera del espacio, etc.).
- `launch/celda_real.launch.py`: lanza `nodo_puente` y `nodo_celda`.

## Topics del nodo

| Topic | Tipo | Sentido | Contenido |
|---|---|---|---|
| `/brazo1/objetivo` | `PoseStamped` | ciclo → puente | Pose de la brida en metros, cuaternión (x, y, z, w) (REP 103). El puente solo la reenvía si se renueva cada 0,2 s |
| `/brazo1/estado` | `String` (JSON) | puente → ciclo | Estado del EGM y pose real |
| `/brazo1/rechazo` | `String` (JSON) | puente → ciclo | Objetivo rechazado y motivo |
| `/celda/estado` | `String` (JSON) | salida | `inicio`, `caja`, `pinza`, `fin`, `error` |
| `/celda/caja` | `PoseStamped` | salida | Centro y giro de la caja que ve la cámara (metros, base del robot). No sale con `caja.csv`, que no tiene posición |

Se puede mirar todo con `ros2 topic echo /celda/estado`.

## Puesta en marcha

Una sola vez, compilar el paquete (Linux / WSL2):

```bash
cd ~/ros2_ws && colcon build --packages-select robotica_bimanual
```

Cada vez, en este orden:

1. **Windows:** `PuenteEgm.exe` con `config.celda.json`. Si ROS corre en WSL2, `ip_control` tiene que ser `0.0.0.0` (con `127.0.0.1` solo escucha a Windows). Si el cortafuegos pregunta, permitir TCP 7001.
2. **Cámara** (solo en real y con cámara por ROS), en otra terminal de Linux:
   ```bash
   ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true
   ```
   En `celda/config_celda.json`, sección `camara`: `"origen": {"tipo": "ros"}`. Los topics por defecto son `/camera/color/image_raw` y `/camera/aligned_depth_to_color/image_raw`; se cambian con `"color"` y `"profundidad"` dentro de `origen`. Con `modo` `color` o `fondo` no hace falta profundidad (si la caja no tiene `alto_mm` fijo, sí).
3. **Celda** (Linux / WSL2):
   ```bash
   source /opt/ros/humble/setup.bash
   source ~/ros2_ws/install/setup.bash
   export PYTHONPATH=/home/ubuntu22/repos/tfm-robotica-bimanual/robotica:$PYTHONPATH
   ros2 launch robotica_bimanual celda_real.launch.py config:=/home/ubuntu22/repos/tfm-robotica-bimanual/robotica/celda/config_celda.json host:=<IP de Windows>
   ```
   `host` es la IP de Windows vista desde WSL2 (`ip route show default | awk '{print $3}'`). Si ROS corre en Windows, `host:=127.0.0.1`.
4. En el FlexPendant, **CAJA EN POSICIÓN** como siempre. El nodo espera a RAPID en el puerto 5010 y el ciclo arranca cuando se conecta.

Alternativa sin ROS, la de siempre: `python -m celda.ciclo` (TCP directo con el puente). Sigue funcionando igual.

## Errores típicos

- `no llega /brazo1/estado: ¿están en marcha nodo_puente y el puente EGM?`: falta `nodo_puente` o `PuenteEgm.exe`, o `host` no es el bueno.
- `no llegan imágenes por /camera/color/image_raw`: el driver de la cámara no corre o publica con otro nombre (`ros2 topic list`).
- `no llega la profundidad ... align_depth`: la RealSense sin `align_depth.enable:=true`.
- `falta el parametro 'config'`: se ha lanzado el nodo sin la ruta de `config_celda.json`.

## Sin comprobar

- RAPID (controlador virtual o real) conectando al socket 5010 cuando el nodo corre en **WSL2**. Con el controlador virtual en Windows debería valer el reenvío de `localhost` de WSL2; con el controlador real hace falta que el PC con el nodo sea alcanzable por su IP (`netsh interface portproxy` o red en modo *mirrored* de WSL2) y poner esa IP en `ipPC` de RAPID y en `ip_escucha`.
- Una cámara USB real dentro de WSL2 (no se ve sin `usbipd`); una RealSense por USB-IP o la cámara en otra máquina con ROS 2 en la misma red.
- Todo lo anterior con el robot: las pruebas usan un puente y una cámara falsos que hablan por los mismos topics.

## Pruebas

`tests/test_ros_celda.py` (10 pruebas, con ROS 2 cargado):

```bash
source /opt/ros/humble/setup.bash
cd ~/repos/tfm-robotica-bimanual/robotica
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/test_ros_celda.py
```

Cubren `PuenteRos` (estado, objetivos, rechazos, error si falta el puente), `nodo_puente` (rechazos del puente TCP), el ciclo completo de dos cajas por topics con un RAPID falso, el error publicado si RAPID no contesta, y la cámara por ROS (color + profundidad) hasta el punto seguro sobre la caja detectada.
