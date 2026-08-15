# Arquitectura de Software Detallada: Sistema Robótico Bimanual de Clasificación de Prendas

> Este documento detalla la arquitectura de software del sistema. Los cinco **modos de operación** (desde vaciado geométrico hasta tendencias de mercado con CLIP) están descritos en `TFM_deteccion_prendas_modos`. El overview del sistema está en `TFM_deteccion_prendas.md`.

---

## 1. Visión General del Sistema

El escenario simula el final de una línea de logística inversa (devoluciones) o preparación de pedidos e-commerce. Los robots manipulan **cajas rígidas individuales** (una prenda por caja), no las prendas directamente. La célula física consta de:

| Hardware              | Función                                           |
|-----------------------|---------------------------------------------------|
| 2× ABB GoFa (OmniCore)| Manipulación bimanual de las cajas unitarias      |
| Cámara Águila RGB-D   | Visión cenital global (identificación y pose)     |
| 2× Cámaras Eye-in-Hand| Visión fina en la muñeca (visual servoing)        |
| PLC Siemens           | Maestro de la célula: seguridad y estados         |
| PC Orquestador        | Procesamiento IA y control cinemático             |
| HMI RobotStudio       | Interfaz del operario (selección de modo y receta)|

---

## 2. Decisión Arquitectónica: ROS 2 + C# EGM (TFG reutilizado)

Tienes dos tecnologías que quieres combinar:
- **ROS 2**: Como bus de mensajería y orquestador (y para poder ponerlo en el CV).
- **C# EGM (del TFG)**: Tu código de control en tiempo real que habla con los controladores ABB. No quieres reescribirlo.

La buena noticia es que son **perfectamente compatibles**. La solución es un **Nodo Puente** (Bridge Node): un nodo ROS 2 en Python de apenas 20 líneas que recoge los targets del topic ROS 2 y los reenvía por TCP al servidor C# del TFG. El C# permanece **sin tocar**: sigue siendo el único módulo que habla con los robots vía EGM.

```
[ROS 2 Bus] ──────► [Bridge Node] ──TCP──► [C# EGM Server (TFG)] ──UDP EGM──► [Robots]
```

Esto te da lo mejor de los dos mundos:
- ROS 2 en el CV (orquestación, pub/sub, MoveIt 2 para colisiones si se quiere).
- Tu TFG en el CV (C# + ABB EGM, control en tiempo real a 250Hz).

---

## 3. Arquitectura Completa (Diagrama)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  HMI (RobotStudio ScreenMaker / FlexPendant)                                  │
│  → Escribe variables PERS en OmniCore R1 (recipe, mode)                       │
│  → Lee DB del PLC vía OPC-UA para mostrar KPIs y alarmas                      │
└────────────────────────┬─────────────────────────────────────────────────────┘
                         │ I/O Digitales + OPC-UA
┌────────────────────────▼─────────────────────────────────────────────────────┐
│  PLC SIEMENS (TIA Portal)                                                     │
│  FC_StateMachine │ FB_CintaVirtual │ FB_SafetyMonitor │ FB_TcpComm │ DB_Global│
└────────────────────────┬─────────────────────────────────────────────────────┘
                         │ TCP/IP  →  "CMD:START_VISION;RECIPE:X;CYCLE:N"
┌────────────────────────▼─────────────────────────────────────────────────────┐
│  PC — ROS 2 Humble                                                            │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  /plc_bridge_node  (Python)                                           │    │
│  │  Recibe TCP del PLC → publica /plc/cell_state (String)               │    │
│  │  Suscribe /cycle_result → responde ACK al PLC                        │    │
│  └──────────────────────────┬───────────────────────────────────────────┘    │
│                             │ ROS 2 Topic: /plc/cell_state                    │
│  ┌──────────────────────────▼───────────────────────────────────────────┐    │
│  │  /vision_node  (Python)                                               │    │
│  │  Suscribe: /plc/cell_state                                            │    │
│  │  Captura cámara Águila → YOLO/PyTorch → Transformación XYZ           │    │
│  │  Publica: /robot_targets (PoseArray con R1 y R2)                     │    │
│  │  Publica: /detections (BoundingBox2DArray para debug/HMI)            │    │
│  │  Durante Grasp: captura EiH → calcula correcciones de servoing       │    │
│  │  Publica: /servoing_corrections (TwistStamped)                       │    │
│  └──────────────────────────┬───────────────────────────────────────────┘    │
│                             │ ROS 2 Topics: /robot_targets, /servoing_corr.   │
│  ┌──────────────────────────▼───────────────────────────────────────────┐    │
│  │  /egm_bridge_node  (Python — EL PUENTE)                              │    │
│  │                                                                       │    │
│  │  Suscribe: /robot_targets  →  serializa a JSON                       │    │
│  │  Suscribe: /servoing_corrections  →  serializa correcciones          │    │
│  │  Abre TCP a localhost:9090  →  envía JSON al C# EGM Server           │    │
│  │  Recibe ACK del C# ("GRASP_DONE", "PLACE_DONE", "ERROR")            │    │
│  │  Publica: /robot_status (String) en ROS 2                            │    │
│  └──────────────────────────┬───────────────────────────────────────────┘    │
│                             │ TCP local (localhost:9090)                       │
│  ┌──────────────────────────▼───────────────────────────────────────────┐    │
│  │  C# EGM SERVER  ← REUTILIZADO DEL TFG (adaptado para 2 robots)       │    │
│  │                                                                       │    │
│  │  TcpCommandReceiver    ← recibe JSON con targets de /egm_bridge_node │    │
│  │  BimanualPathPlanner   ← calcula Pre-Grasp R1 y R2, evita colisión   │    │
│  │  EgmProtobufPacker     ← serializa posición en egm.proto (Protobuf)  │    │
│  │  EgmCommunicatorR1     ← UDP 250Hz ↔ OmniCore Robot 1               │    │
│  │  EgmCommunicatorR2     ← UDP 250Hz ↔ OmniCore Robot 2               │    │
│  │  StatusReporter        ← envía "GRASP_DONE" de vuelta al Bridge      │    │
│  └──────────────────────────┬─────────────────────────────────────────┬─┘    │
└─────────────────────────────┼─────────────────────────────────────────┼──────┘
                              │ UDP 4ms EGM                              │ UDP 4ms EGM
                              ▼                                          ▼
              ┌───────────────────────┐              ┌───────────────────────┐
              │  ABB OmniCore R1      │              │  ABB OmniCore R2      │
              │  RAPID: main.mod      │              │  RAPID: main.mod      │
              │  → EGMSetupUC         │              │  → EGMSetupUC         │
              │  → EGMRunPose (cede   │              │  → EGMRunPose (cede   │
              │    control al C#)     │              │    control al C#)     │
              └───────────────────────┘              └───────────────────────┘
```

---

## 4. El Puente ROS 2 ↔ C# (egm_bridge_node.py)

Este es el módulo clave que une los dos mundos. Es simple a propósito:

```python
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseArray
from std_msgs.msg import String
import socket, json

class EgmBridgeNode(Node):
    def __init__(self):
        super().__init__('egm_bridge_node')
        # Conexión TCP al C# EGM Server (localhost)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(('127.0.0.1', 9090))
        # Suscripciones ROS 2
        self.create_subscription(PoseArray, '/robot_targets', self.on_targets, 10)
        # Publicaciones ROS 2
        self.status_pub = self.create_publisher(String, '/robot_status', 10)

    def on_targets(self, msg: PoseArray):
        # Serializa los dos targets a JSON y los manda al C#
        payload = {
            "r1": pose_to_dict(msg.poses[0]),
            "r2": pose_to_dict(msg.poses[1])
        }
        self.sock.sendall(json.dumps(payload).encode())
        # Espera ACK del C#
        ack = self.sock.recv(256).decode()
        self.status_pub.publish(String(data=ack))  # publica en ROS 2
```

El C# del TFG solo necesita dos adaptaciones mínimas:
1. Recibir JSON con dos targets en vez de comandos del SpaceMouse.
2. Arrancar dos `EgmCommunicator` en paralelo (uno por robot) en vez de uno.

---

## 5. Mapa Completo de Comunicaciones

| # | Origen                  | Destino                   | Protocolo           | Mensaje / Payload                                              |
|---|-------------------------|---------------------------|---------------------|----------------------------------------------------------------|
| 1 | HMI RobotStudio         | OmniCore R1               | PERS / RWS          | `recipe:="DEPORTIVA"`, `mode:=AUTO`                           |
| 2 | OmniCore R1             | PLC Siemens               | I/O Digital         | `DO_ROBOT1_READY = 1`                                         |
| 3 | PLC Siemens             | /plc_bridge_node (ROS 2)  | TCP/IP              | `"CMD:START_VISION;RECIPE:DEPORTIVA;CYCLE:0042"`              |
| 4 | /plc_bridge_node        | ROS 2 Bus                 | DDS Topic           | `/plc/cell_state` → `String("RECIPE:DEPORTIVA")`             |
| 5 | /vision_node            | Cámaras (Eagle + EiH)     | SDK / USB / GigE    | Solicitud de captura de frame                                  |
| 6 | /vision_node            | ROS 2 Bus                 | DDS Topic           | `/robot_targets` → `PoseArray` (pose R1 y R2 en XYZ+quat)    |
| 7 | /vision_node            | ROS 2 Bus                 | DDS Topic           | `/servoing_corrections` → `TwistStamped` (ΔX,ΔY,Δθ)          |
| 8 | /egm_bridge_node        | C# EGM Server             | TCP local           | JSON: `{"r1":{x,y,z,qx,qy,qz,qw}, "r2":{...}}`              |
| 9 | C# EGM Server           | OmniCore R1               | **UDP 4ms (EGM)**   | Protobuf `EgmRobot` → `planned_pose.cartesian`               |
|10 | OmniCore R1             | C# EGM Server             | **UDP 4ms (EGM)**   | Protobuf `EgmSensor` → `feedback.cartesian` (pos. actual)    |
|11 | C# EGM Server           | OmniCore R2               | **UDP 4ms (EGM)**   | Igual que #9 (canal UDP independiente)                        |
|12 | OmniCore R2             | C# EGM Server             | **UDP 4ms (EGM)**   | Igual que #10 (canal UDP independiente)                       |
|13 | C# EGM Server           | /egm_bridge_node          | TCP local           | `"STATUS:GRASP_DONE"` / `"STATUS:ERROR:TIMEOUT"`             |
|14 | /egm_bridge_node        | ROS 2 Bus                 | DDS Topic           | `/robot_status` → `String("GRASP_DONE")`                     |
|15 | /plc_bridge_node        | PLC Siemens               | TCP/IP              | `"ACK:CYCLE_DONE;PICKED:DEPORTIVA"`                           |
|16 | PLC Siemens             | HMI RobotStudio           | OPC-UA / DB        | `DB_Global.cycle_count++`, `alarm_active := FALSE`            |

---

## 6. Módulos por Componente

### 6.1. PC — Nodos ROS 2 (Python)

| Nodo / Fichero             | Responsabilidad                                                                  |
|----------------------------|----------------------------------------------------------------------------------|
| `plc_bridge_node.py`       | TCP listener del PLC. Convierte CMD a topics ROS 2. Envía ACK de vuelta al PLC. |
| `vision_node.py`           | Captura Águila, YOLO/PyTorch, calibración, transformación XYZ. Publica targets. |
| `yolo_inference.py`        | Módulo de inferencia YOLO/PyTorch (importado por vision_node).                   |
| `coord_transform.py`       | Calibración intrínseca + extrínseca. Función `pixel_to_robot_xyz()`.             |
| `visual_servoing_node.py`  | Captura cámaras EiH, calcula error Δ y publica correcciones en bucle cerrado.   |
| `egm_bridge_node.py`       | **El puente**. Suscribe topics de ROS 2 → TCP al C# EGM Server.                 |
| `ai_classifier.py`         | Módulo IA avanzada (Multi-label / CLIP). Llamado por vision_node.                |
| `config.py`                | IPs, puertos, umbrales de confianza, nombres de topics.                          |

### 6.2. PC — C# EGM Server (del TFG, adaptado)

| Clase / Fichero             | Responsabilidad                                                                  |
|-----------------------------|----------------------------------------------------------------------------------|
| `Program.cs`                | Punto de entrada. Arranca TcpCommandReceiver y los dos EgmCommunicators.         |
| `TcpCommandReceiver.cs`     | Servidor TCP local. Recibe JSON del Bridge. Parsea targets R1 y R2.              |
| `BimanualPathPlanner.cs`    | (**NUEVO**) Calcula Pre-Grasp de ambos robots. Gestiona Maestro/Esclavo.         |
| `EgmProtobufPacker.cs`      | Serializa posición Cartesiana a `EgmRobot` Protobuf (igual que TFG).            |
| `EgmCommunicatorR1.cs`      | Loop UDP 250Hz con OmniCore R1 (igual que TFG, pero apuntando a R1).            |
| `EgmCommunicatorR2.cs`      | (**NUEVO**) Loop UDP 250Hz con OmniCore R2 (copia del TFG para R2).             |
| `StatusReporter.cs`         | Envía ACKs ("GRASP_DONE", "ERROR") de vuelta al Bridge por TCP.                 |

> ✅ **Reutilización del TFG:** `EgmProtobufPacker.cs` y `EgmCommunicatorR1.cs` son prácticamente iguales al TFG. `TcpCommandReceiver.cs` cambia la fuente de datos (antes SpaceMouse, ahora JSON del Bridge). `BimanualPathPlanner.cs` y `EgmCommunicatorR2.cs` son los únicos módulos realmente nuevos.

### 6.3. PLC Siemens (TIA Portal)

| Bloque               | Tipo   | Responsabilidad                                                        |
|----------------------|--------|------------------------------------------------------------------------|
| `FC_StateMachine`    | FC     | Máquina de estados: INIT→WAIT→VISION→ROBOT→DONE→ERR.                  |
| `FB_CintaVirtual`    | FB     | Simula avance de cinta con temporizadores. Genera trigger al llegar.   |
| `FB_SafetyMonitor`   | FB     | E-Stop, puertas de seguridad. Corta potencia a los GoFa.              |
| `FB_TcpComm`         | FB     | Conexión TCP con `plc_bridge_node`. Envía CMD, recibe ACK.            |
| `FB_HmiInterface`    | FB     | Escribe KPIs en DB para lectura desde HMI (contadores, alarmas).      |
| `DB_Global`          | DB     | Variables globales: `recipe`, `cycle_count`, `alarm_code`, `mode`.    |
| `OB_Main`            | OB 1   | Ciclo de scan principal (llama a FCs y FBs).                          |

### 6.4. ABB OmniCore — RAPID (idéntico en R1 y R2)

| Fichero RAPID          | Responsabilidad                                                                |
|------------------------|--------------------------------------------------------------------------------|
| `main.mod`             | Bucle principal: espera señal PLC → inicia EGM → espera fin → vuelve a Home.  |
| `egm_routines.mod`     | Rutinas: `EGMSetupUC`, `EGMActPose`, `EGMRunPose`, `EGMStop`.                 |
| `io_signals.mod`       | Definición de I/O con el PLC (`DI_PLC_PERMISSION`, `DO_ROBOT_READY`).         |
| `tooldata.mod`         | Datos de la herramienta (garra): TCP, masa, inercia.                           |
| `workobj.mod`          | Sistema de coordenadas de la mesa de trabajo.                                  |
| `safety_routines.mod`  | Home position, límites de velocidad en modo manual, zonas de trabajo.          |

---

## 7. Flujo Completo de un Ciclo (Paso a Paso)

```
1.  Operario selecciona "DEPORTIVA" en el HMI → PERS recipe:="DEPORTIVA" en OmniCore R1
2.  OmniCore R1 → señal DO_RECIPE_SET=1 → PLC
3.  PLC: FC_StateMachine pasa a WAIT_BOX
4.  Operario coloca la caja en la mesa (cinta ficticia completada)
5.  PLC: FB_CintaVirtual → temporizador completo → TCP a /plc_bridge_node:
        "CMD:START_VISION;RECIPE:DEPORTIVA;CYCLE:0042"
6.  /plc_bridge_node publica en ROS 2: /plc/cell_state → "RECIPE:DEPORTIVA"
7.  /vision_node recibe el topic → captura imagen Cámara Águila
8.  /vision_node → YOLO detecta prendas → mejor candidata (conf=0.94, DEPORTIVA)
9.  /vision_node → coord_transform → [X1,Y1,Z1,q1] para R1, [X2,Y2,Z2,q2] para R2
10. /vision_node publica: /robot_targets → PoseArray con 2 poses
11. /egm_bridge_node recibe /robot_targets → serializa a JSON → TCP al C#:
        {"r1": {x,y,z,qx,qy,qz,qw}, "r2": {...}}
12. /plc_bridge_node envía ACK al PLC: "STATUS:OK;CONFIDENCE:0.94"
13. PLC: avanza a ROBOT_MOVING → activa DO_ROBOT_PERM=1 → RAPID R1 y R2
14. RAPID R1 y R2: detectan DI_PLC_PERMISSION=1 → llaman EGMRunPose (ceden control)
15. C# EgmCommunicatorR1 y R2: arrancan loops UDP 250Hz
16. C# BimanualPathPlanner: envía Pre-Grasp a R1 y R2 simultáneamente
17. Cuando ambos llegan a Pre-Grasp → fase de descenso Maestro/Esclavo
18. /visual_servoing_node: captura cámaras EiH → calcula Δ → publica /servoing_corrections
19. /egm_bridge_node: reenvía correcciones al C# → C# ajusta posición en tiempo real
20. Robots agarran la caja → C# → TCP → "STATUS:GRASP_DONE" → /egm_bridge_node
21. /egm_bridge_node publica /robot_status → "GRASP_DONE"
22. Robots transportan al destino → C# → "STATUS:PLACE_DONE"
23. RAPID: EGMStop → recuperan control propio → vuelven a Home
24. /plc_bridge_node → PLC TCP: "ACK:CYCLE_DONE;PICKED:DEPORTIVA"
25. PLC: FB_HmiInterface actualiza DB_Global.cycle_count++
26. PLC: FC_StateMachine → WAIT_BOX (nuevo ciclo)
27. HMI muestra contadores actualizados vía OPC-UA
```

---

## 8. Extensión: Arquitectura de Modos de Operación

El flujo descrito en las secciones anteriores corresponde al **Modo 2 (Clasificación Supervisada)**. El sistema completo implementa cinco modos de operación progresivos. La receta seleccionada en el HMI (`DB_Global.recipe`) determina el modo activo:

| `recipe` (HMI) | Modo | Qué cambia en el pipeline |
| :--- | :--- | :--- |
| `SINGULATION` | 1 — Vaciado Geométrico | `vision_node` usa PCL + YOLO-obb. Sin clasificación de prenda. |
| `SORTING:<tipo>` | 2 — Clasificación Supervisada | Pipeline estándar de esta arquitectura. |
| `STOCK:<país>` | 3 — Reposición Geográfica | `ai_classifier.py` consulta JSON de ERP simulado para determinar qué tipo de prenda se necesita en ese país. |
| `TREND:<país>` | 4 — Tendencias de Mercado | `ai_classifier.py` ejecuta el pipeline de análisis de tendencias (redes sociales → CLIP → distancia coseno). |
| `FULL:<país>` | 5 — Gestión Integral | Combina Modos 3 y 4: reposición de stock priorizando prendas alineadas con la tendencia del mercado. |

El módulo `ai_classifier.py` es el único que varía entre modos. El resto de la arquitectura (PLC, ROS 2, EGM bridge, RAPID) permanece idéntico independientemente del modo activo.

Para el detalle completo de cada modo, véase `TFM_deteccion_prendas_modos`.
