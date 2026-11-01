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
| `ip_controlador` | Si se indica, solo se aceptan datagramas de esa IP. **Recomendado.** |
| `ip_control`, `puerto_control` | Servidor TCP de control. `127.0.0.1` para pruebas; desde WSL2 hace falta la IP de Windows. |
| `semantica` | `desplazamiento`: `planned` es una corrección respecto a la pose de partida. `absoluta`: `planned` es la posición objetivo. **Decidir con la prueba D30 del controlador virtual.** |
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

## Registro

Con `registro_csv` activo, cada ciclo deja una línea: `t_s, sesion, seqno, estado, real_xyz, ref_xyz, desviacion_mm`.
La cola tiene un límite; si se llena, se descartan líneas y el programa informa al salir.

## Lo que no garantiza

- No hay garantía de tiempo real. El puente no hace E/S en el bucle, pero Windows no es un sistema de tiempo real.
  Medir `intervalo_max_ms` en el PC que se use de verdad, con la carga del día a día.
- No hay comprobación de colisiones ni de fuerza. La protección es la desviación y el espacio de trabajo.
- La semántica de `planned` no está confirmada hasta la prueba D30 en el controlador virtual.

## Pruebas

Las pruebas de extremo a extremo (`tests/test_puente_e2e.py`) ejecutan este puente compilado con un
controlador simulado en Python (`mock/controlador_egm.py`). Comprueban seguimiento, watchdog, límite del
espacio, fallo por desviación con rearme, parada y rechazo de comandos incorrectos, en las dos semánticas.
