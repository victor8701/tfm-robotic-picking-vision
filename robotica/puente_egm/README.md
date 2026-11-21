# Puente EGM (C#, .NET 8)

Puente entre el controlador ABB (EGM por UDP, 250 Hz) y el resto del sistema (ROS 2 por TCP).
Una sesión por controlador: recibe `EgmRobot` en cada ciclo y responde con `EgmSensor` con una
consigna segura. Cuatro reglas de seguridad:

- La consigna nunca se aleja más de `desviacion` de la posición real. Si lo hace, la sesión entra en **fallo**.
- La referencia avanza como mucho `paso_mm` por ciclo (0,5 mm a 4 ms = 125 mm/s) y no sale del `espacio_mm`.
- Si no llega ningún objetivo en `watchdog_s` (0,1 s), la sesión **retiene** la posición real.
- Tras un fallo, la sesión no se mueve hasta recibir `reset`.

## Compilar y ejecutar

En Windows, con el SDK de .NET 8 instalado (la versión de desarrollo es 8.0.133):

```bash
cd puente_egm/PuenteEgm
dotnet build -c Release
dotnet run -c Release -- ..\config.ejemplo.json
```

El ejecutable queda en `PuenteEgm/bin/Release/net8.0/PuenteEgm.dll`. Para ejecutarlo sin compilar
de nuevo: `dotnet PuenteEgm.dll config.json`.

Al arrancar muestra cada sesión y, cada 5 segundos, su estado en JSON.

## Configuración (`config.ejemplo.json`)

| Clave | Significado |
|---|---|
| `registro_csv` | Ruta del registro por ciclo, o `null`. Se escribe en un hilo aparte. |
| `nombre` | Nombre de la sesión (aparece en el registro). |
| `puerto_egm` | Puerto UDP al que el controlador envía `EgmRobot` (6511 en el proyecto previo). |
| `ip_controlador` | IP del controlador de esta sesión. Si se indica, solo se aceptan datagramas de esa IP. `null` = sin filtro: la consola escribe `primer datagrama de X:Y` por cada IP nueva; copiar esa X aquí y reiniciar. **Recomendado ponerla en producción.** |
| `ip_control`, `puerto_control` | Servidor TCP de control. `127.0.0.1` si ROS corre en el mismo Windows; si corre en WSL2, la IP de Windows vista desde WSL2 (p. ej. `172.27.48.1`; evita `0.0.0.0`, que abre el control a toda la red) y una regla de firewall para ese puerto solo desde la subred de WSL2. |

Los valores de red (IPs de los controladores, del PC, de WSL2 y de los UdpUc) están reunidos en
[docs/configuracion.md](../docs/configuracion.md), con el orden de arranque y los errores típicos.
| `semantica` | `absoluta` (por defecto): `planned` es la pose objetivo en el marco base; es lo que hace el controlador del proyecto (resuelto el 15-nov-2026). `desplazamiento`: `planned` sería una corrección respecto a la pose de partida; con este controlador el robot va al origen de la base, no usar. |
| `watchdog_s` | Segundos sin objetivo antes de retener la posición. |
| `limites` | `paso_mm`, `giro_rad` por ciclo; `desviacion_mm`, `desviacion_rad` máximas respecto a la posición real. |
| `espacio_mm` | Caja de trabajo en la base del robot, por ejes `x`, `y`, `z`. |

Los valores del ejemplo son de partida y no están medidos.

## Protocolo de control (TCP, una línea JSON por comando)

```json
{"cmd": "objetivo", "t": [x, y, z], "q": [w, x, y, z]}   → {"ok": true}
{"cmd": "estado"}                                           → estado, código, real, referencia, desviación
{"cmd": "parar"}  {"cmd": "arrancar"}  {"cmd": "reset"}     → {"ok": true} o {"ok": false, "error": "..."}
```

Estados: `esperando` (sin objetivo todavía), `activo`, `retener` (objetivo vencido; se recupera solo),
`fallo` (desviación excesiva; exige `reset`), `parada` (exige `arrancar`).

Los objetivos deben llegar a 20–50 Hz: si no, el puente retiene el brazo.

### Socket de RAPID (opcional)

Con la sección `"rapid": {"ip": "127.0.0.1", "puerto": 5010}` en una sesión, el puente es además el servidor TCP al que se conecta la tarea
`T_COM` del controlador (`ipPC`/`puertoPC` en `MOD_CajaPinza.mod`) y pasa los mensajes tal cual entre RAPID y el programa de la celda
(`RapidPuente.cs`). Sin la sección, el puente no abre nada y esos comandos devuelven error. Cada conexión nueva de RAPID sustituye a la anterior.

```json
{"cmd": "rapid_estado"}                           → {"ok": true, "conectado": bool, "origen": "ip:puerto"}
{"cmd": "rapid_enviar", "msg": "cerrar"}          → {"ok": true}   (máx. 80 caracteres, el límite de las cadenas de RAPID)
{"cmd": "rapid_recibir", "timeout_s": 5}          → {"ok": true, "msg": "cerrada"} o {"ok": false, "codigo": "timeout|cerrado|desconectado", "error": "..."}
```

`rapid_recibir` bloquea su conexión hasta que RAPID contesta: se usa una conexión de control aparte de la del movimiento (lo hacen
`celda/rapid_puente.py` y `nodo_puente`). Más en `docs/ros2.md`.

## Registro

Con `registro_csv` activo, cada ciclo deja una línea: `t_s, sesion, seqno, estado, real_xyz, ref_xyz, desviacion_mm`.
La cola tiene un límite; si se llena, se descartan líneas y el programa informa al salir.

## Lo que no garantiza

- No hay garantía de tiempo real. El puente no hace E/S en el bucle, pero Windows no es un sistema de tiempo real.
  Medir `intervalo_max_ms` en el PC que se use de verdad, con la carga del día a día.
- No hay comprobación de colisiones ni de fuerza. La protección es la desviación y el espacio de trabajo.
- La semántica de `planned` es `absoluta` (resuelto el 15-nov-2026 con las pruebas de RobotStudio y el TFG). Con `desplazamiento` el robot va al origen de la base.

## Pruebas

Las pruebas de extremo a extremo (`tests/test_puente_e2e.py`) ejecutan este puente compilado con un
controlador simulado en Python (`mock/controlador_egm.py`). Comprueban seguimiento, watchdog, límite del
espacio, fallo por desviación con rearme, parada y rechazo de comandos incorrectos, en las dos semánticas.
