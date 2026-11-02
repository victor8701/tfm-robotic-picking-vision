# Configuración de red y de la celda: qué valores poner y dónde

Este documento reúne todas las IPs, puertos y medidas que hay que poner en la instalación.
Los valores entre `<...>` son los que **no conozco**: hay que obtenerlos en el laboratorio o en el PC.
No he puesto ninguna IP inventada.

## 1. Esquema de red

```
 OmniCore 1 (IP <IP_OMNICORE_1>)  ──UDP EGM──►  PC Windows con el puente (IP <IP_PC_WINDOWS>)  puerto 6511
 OmniCore 2 (IP <IP_OMNICORE_2>)  ──UDP EGM──►  PC Windows con el puente (IP <IP_PC_WINDOWS>)  puerto 6512

 ROS 2 (en WSL2, en el mismo PC)  ──TCP JSON──► puente en Windows  puertos 7001 (brazo1) y 7002 (brazo2)
 RealSense (USB)                  ──────────►   driver ROS 2 (Windows o WSL2, según cómo se conecte)
```

- El controlador **envía** datos al PC: el PC no necesita conocer la IP del controlador para recibirlos,
  pero el puente puede filtrar por ella (`ip_controlador`).
- El puente **escucha**: el PC es el servidor de EGM y de control.

## 2. Tabla de valores

| Qué | Dónde se pone | Valor | De dónde sale |
|---|---|---|---|
| IP del OmniCore 1 | `puente_egm/config.json` → `ip_controlador` de la sesión `brazo1` | `<IP_OMNICORE_1>` | FlexPendant (Ajustes → Comunicación) o RobotStudio. Si no la sabes: ver §3 |
| IP del OmniCore 2 | `ip_controlador` de la sesión `brazo2` | `<IP_OMNICORE_2>` | Igual que la anterior |
| IP del PC del puente | En cada **UdpUc** del controlador: dirección remota | `<IP_PC_WINDOWS>` | `ipconfig` en el PC (adaptador de la red del laboratorio) |
| Puerto EGM del brazo 1 | UdpUc del OmniCore 1: puerto remoto. Y `puerto_egm` de la sesión `brazo1` | `6511` | Decisión nuestra (6511 del proyecto previo) |
| Puerto EGM del brazo 2 | UdpUc del OmniCore 2: puerto remoto. Y `puerto_egm` de la sesión `brazo2` | `6512` | Decisión nuestra |
| Nombre del dispositivo UdpUc | En el controlador | `default` | Lo usa `EGMSetupUC` en `rapid/MOD_EGM.mod` |
| Nombre del sensor EGM | En RAPID, `MOD_EGM.mod` | `"EGMsensor"` | Debe coincidir con la configuración EGM del controlador |
| Nombre del robot en RAPID | En RAPID, `MOD_EGM.mod` (`ROB_1`) | `ROB_1` | Nombre del robot en el controlador; cambia si hay varios robots |
| IP del servidor de control | `puente_egm/config.json` → `ip_control` | `127.0.0.1` o `0.0.0.0` | `127.0.0.1` si ROS corre en el mismo Windows. `0.0.0.0` si ROS corre en WSL2 |
| Puerto de control | `puerto_control` del puente y `brazo1.puerto` / `brazo2.puerto` del launch | `7001` / `7002` | Decisión nuestra |
| IP del puente vista desde WSL2 | `ros2/.../launch/celda.launch.py` → `brazo1.host`, `brazo2.host` | `<IP_PC_VISTA_DESDE_WSL>` | Ver §4. Si ROS corre en Windows: `127.0.0.1` |
| Semántica de `planned` | `puente_egm/config.json` → `semantica` | `desplazamiento` (provisional) | Se decide con la prueba D30 del controlador virtual |
| Tópicos de la cámara | launch → `topic_imagen`, `topic_info` | `<TOPICO_IMAGEN>`, `<TOPICO_INFO>` | `ros2 topic list` con el driver de la RealSense en marcha |
| Caja interior | launch → `ancho_mm`, `largo_mm`; `celda.json` → `caja_interior_mm` | `700`, `650`, `200` | Medir la caja real (guion de la visita 1) |
| Bases, puntos de agarre, cámara, punto B, espacio | `simulacion/celda.json` | ver §5 | Medir, o salir de la calibración |

## 3. Cómo averiguar la IP de cada controlador

No hace falta saberla de antemano:

1. En el FlexPendant (o en RobotStudio con el controlador virtual), mirar la IP de comunicación del controlador.
   En los controladores ABB, la IP del puerto de servicio suele ser `192.168.125.1`, pero es un dato general de ABB,
   no de este laboratorio. Confirmarla en el propio controlador o con el laboratorio.
2. Si la IP de origen del tráfico EGM no coincide con la anterior (por ejemplo, con el controlador virtual en el mismo PC),
   usar el aviso del puente:
   - Dejar `ip_controlador` en `null` la primera vez.
   - Arrancar el puente y después EGM en el controlador.
   - La consola del puente escribe una línea por cada IP nueva, por ejemplo:
     `[brazo1] primer datagrama de 192.168.10.23:6511 (aceptado; ip_controlador = sin filtro)`.
   - Copiar esa IP en `ip_controlador` y reiniciar el puente.
   - El puerto que aparece en la línea es el puerto de **origen** del controlador, puede ser distinto de 6511. Lo que importa es la IP.

## 4. ROS 2 en WSL2 y el puente en Windows

Si ROS 2 corre en WSL2 (Ubuntu 22.04) y el puente en Windows, WSL2 no ve `127.0.0.1` de Windows.

1. **IP de Windows vista desde WSL2.** Dentro de WSL2:
   ```bash
   ip route show default | awk '{print $3}'
   ```
   Ese valor es `<IP_PC_VISTA_DESDE_WSL>`. Va en `brazo1.host` y `brazo2.host` del launch.
2. **El puente debe escuchar fuera de `127.0.0.1`.** En `config.json`: `"ip_control": "0.0.0.0"`.
3. **Firewall de Windows.** Crear una regla de entrada que permita TCP `7001` y `7002` desde la red del adaptador
   `vEthernet (WSL)` (o desde la subred de WSL2). Sin esa regla, ROS verá "Connection refused" o un tiempo de espera.
4. **Alternativa.** Con WSL2 en modo espejo (`networkingMode=mirrored` en `.wslconfig`, Windows 11 22H2 o posterior),
   WSL2 puede usar `127.0.0.1`. **No lo he probado.** Comprobarlo antes de depender de ello.

Las conexiones de EGM (UDP desde los controladores) **no** pasan por WSL2: llegan al puente en Windows directamente.

## 5. Valores de la celda (`simulacion/celda.json`)

Todos son de partida y deben medirse (guion de la visita 1). Las coordenadas están en mm.

| Clave | Qué es | Valor de partida | Cómo se obtiene |
|---|---|---|---|
| `bimanual.base_1` | Pose de la base del brazo 1 (origen del mundo) | `[0, 0, 0]` | Definición; no hace falta medirla |
| `bimanual.base_2` | Pose de la base del brazo 2 respecto al mundo | `[1200, 0, 0]` | Medir la distancia entre bases (RobotStudio o cinta) |
| `bimanual.tcp_caja_1` / `tcp_caja_2` | Punto de agarre de cada mano en el marco de la caja | `[-400, 0, 100]` / `[400, 0, 100]` | Diseño de la pinza y de la caja real |
| `camara_en_mano1` | Pose de la cámara en el marco del TCP de la mano maestra | `[60, 0, -80]` | Salida de `calibracion/cli.py mano_ojo` |
| `punto_b_mm` | Pose de la caja en el punto de depósito | `[600, 500, 100]` | Medir el punto de depósito |
| `espacio_trabajo_mm` | Caja de trabajo en la base de cada robot | `x ±600`, `y ±600`, `z 0..800` | Alcance del GoFa (ficha o RobotStudio) |
| `caja_interior_mm` | Caja grande interior | `[700, 650, 200]` | Medir la caja real |
| `limites_ciclo`, `control`, `coordinacion` | Límites y ganancias | placeholders | Ajustar en el controlador virtual y en V1 |

Y en el puente: `limites` y `espacio_mm` de cada sesión (ver `puente_egm/README.md`).

## 6. Orden de arranque (la primera vez)

1. En el PC: `ipconfig`. Anotar la IP de la red del laboratorio → `<IP_PC_WINDOWS>`.
2. En cada controlador: anotar su IP → `<IP_OMNICORE_1>`, `<IP_OMNICORE_2>`.
3. En cada controlador: crear el UdpUc `default` con remoto `<IP_PC_WINDOWS>` y puerto `6511` (brazo 1) o `6512` (brazo 2).
4. Copiar `puente_egm/config.ejemplo.json` a `config.json`. Poner `ip_control` (`127.0.0.1` o `0.0.0.0`, §4) y dejar `ip_controlador` en `null`.
5. Arrancar el puente: `dotnet PuenteEgm.dll config.json` (ver `puente_egm/README.md`).
6. Arrancar EGM en el controlador (`EGM_Iniciar`).
7. Leer la consola del puente: aparecerá `primer datagrama de X:Y`. Poner X en `ip_controlador` de esa sesión y reiniciar el puente.
8. Comprobar el estado por TCP: `{"cmd": "estado"}` debe responder con `"estado": "esperando"` y `ciclos` creciendo.
9. Solo entonces, lanzar ROS 2 con `brazo1.host` y `brazo2.host` del §4.

## 7. Errores típicos y su síntoma

| Síntoma | Causa probable | Qué mirar |
|---|---|---|
| La consola no muestra `primer datagrama` | Puerto distinto, IP de Windows errónea o firewall | El puerto remoto del UdpUc, la IP remota y la regla de entrada UDP |
| Aparece `ignorado` | `ip_controlador` no coincide con la IP de origen | Copiar la IP que indica la línea y reiniciar el puente |
| ROS: `Connection refused` | `ip_control` en `127.0.0.1` con ROS en WSL2, o firewall | §4, puntos 2 y 3 |
| ROS: `sin estado del puente` con timeout | Firewall o IP de Windows errónea en el launch | §4, punto 1 |
| El controlador da error de EGM | Nombre de sensor o de dispositivo no coincide | `default`, `EGMsensor` y `ROB_1` en RAPID y en la configuración |

## 8. Lo que no sé todavía

- Las IPs reales de los dos controladores y del PC del laboratorio.
- Si el controlador virtual de RobotStudio envía desde `127.0.0.1` o desde una IP de adaptador virtual.
- En el repositorio del curso aparece `192.168.1.89`, en el cliente Python que se conecta a un servidor RAPID en el puerto
  1025. Es de otra instalación y de otro uso. No la uses aquí sin confirmarla.
