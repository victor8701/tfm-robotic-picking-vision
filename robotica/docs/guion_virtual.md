# Guion: puesta a punto en el controlador virtual (RobotStudio, Windows)

Objetivo: comprobar el puente EGM y los módulos RAPID en un controlador virtual antes de tocar el robot real.
Todo lo de este guion se hace en simulación. No se conecta ningún robot real.

Anotar cada resultado en la tabla del final (y en `docs/ESTADO.md`).

## 0. Requisitos

- RobotStudio con licencia Premium, con Virtual Controller y la opción EGM (689-1) en RobotWare.
  Según Víctor (1 de noviembre), el entorno es el mismo que el del TFG; confirmarlo en el controlador.
- SDK de .NET 8 (o runtime para ejecutar el puente compilado).
- Este repositorio en el PC de Windows (la carpeta `robotica/`).

## 1. Controlador virtual

1. Crear la estación con un GoFa y su controlador virtual. Anotar la versión de RobotWare.
2. Comprobar que la opción **Externally Guided Motion (EGM), 689-1** está instalada.
3. En la configuración de comunicaciones del controlador virtual, crear un dispositivo **UdpUc**:
   - nombre `default` (es el que usa `EGMSetupUC` en `MOD_EGM`);
   - dirección remota: la IP del PC donde corre el puente;
   - puerto: el de `puerto_egm` en la configuración del puente (6511 por defecto).
   - El nombre `EGMsensor` del RAPID debe coincidir con la configuración EGM del controlador. Si no coincide, la sesión no arranca. Comprobarlo en el paso 3.
4. Cargar `rapid/MOD_EGM.mod`, `rapid/MOD_Seguridad.mod` y `rapid/MOD_Prueba_V1.mod`.
5. Compilar el puente: `dotnet build -c Release` dentro de `puente_egm/PuenteEgm`.

## 2. Arranque del puente

```bat
cd puente_egm\PuenteEgm
dotnet bin\Release\net8.0\PuenteEgm.dll ..\config.ejemplo.json
```

Con `semantica` = `desplazamiento` al principio (ver paso 4). El puente debe mostrar la sesión en marcha.

## 3. Arranque de EGM en el controlador virtual

1. Poner el robot en `pInicio` con `MoveJ` (es la postura de partida del TFG; no la cambies).
2. Ejecutar `EGM_Iniciar`. El estado de la sesión debe pasar a "running".
3. Consultar el estado del puente: `{"cmd": "estado"}` por TCP (por ejemplo, con `netcat` o un script).
   Debe aparecer `"estado": "esperando"` y `"ciclos"` creciendo.

## 4. Prueba D30: ¿la consigna es corrección o posición absoluta?

Objetivo: saber qué significa `planned` en el controlador. Es la prueba que decide `semantica`.

1. Anotar la posición del TCP en RobotStudio (o con `CRobT` en RAPID).
2. Enviar un objetivo `t = pose_partida + (10, 0, 0)` mm, con `q` igual a la de partida, y mantenerlo a unos 25 Hz durante 2 s.
3. Medir el desplazamiento real del TCP:
   - si se mueve ~10 mm en X desde la partida: la semántica es **desplazamiento** (`semantica = desplazamiento`);
   - si va a una posición fija distinta de la partida: la semántica es **absoluta** (`semantica = absoluta`).
4. Repetir con `semantica = absoluta` (reiniciar el puente) para confirmar.
5. Si el movimiento sale muy distinto de 10 mm, o no sale: parar (`{"cmd":"parar"}`) y anotar. No seguir hasta entenderlo.

Riesgo a vigilar: el proyecto previo usaba `EGMActPose ... \x:=[-1, 1]`. Si el controlador limita la corrección a
±1 mm, el movimiento de 10 mm se quedará en 1 mm. Eso es el límite de `EGMActPose`, no un fallo del puente.
Anotarlo, porque cambia `rango_pos` en `MOD_EGM.mod`.

## 5. Límites y watchdog

1. **Límite del espacio**: enviar un objetivo fuera de `espacio_mm`. La referencia debe quedarse en el borde.
2. **Watchdog**: mandar objetivos 1 s, luego parar de mandarlos 0,5 s. El estado debe ser `retener` y el robot quieto.
   Al reanudar, debe volver a `activo`.
3. **Desviación**: con el robot parado en el controlador (por ejemplo, con el programa detenido), mandar un objetivo lejano.
   La sesión debe pasar a `fallo` con `codigo: desviacion_excesiva`. Solo después, `reset` y de nuevo `objetivo`.
4. **Parada**: `{"cmd":"parar"}` durante un movimiento. El robot debe quedarse en la posición. `arrancar` lo reactiva.

## 6. Latencia y registro

- Revisar `intervalo_max_ms` en el estado tras un minuto de funcionamiento.
- Revisar el CSV de `registro_csv`: una línea por ciclo, sin huecos grandes.
- Anotar el resultado: en el controlador virtual no es el dato del robot real, pero da una idea de la carga del PC.

## 7. Trayectoria (solo si los pasos 1 a 6 están bien)

1. Generar el módulo: `python3 simulacion/csv_a_rapid.py simulacion/trayectoria_ejemplo.csv MOD_Trayectoria.mod --velocidad v20`.
2. Cargarlo en el controlador virtual y ejecutar `Ejecutar_Trayectoria` a velocidad baja.
3. No subir la velocidad hasta haber visto el recorrido completo.

## Resultados

| Paso | Resultado | Anotaciones |
|---|---|---|
| 1. UdpUc y 689-1 | | |
| 3. EGM en marcha | | |
| 4. D30: semántica | | `desplazamiento` / `absoluta` / otro |
| 4. Límite de corrección (±1 mm?) | | |
| 5. Límite del espacio | | |
| 5. Watchdog (retener) | | |
| 5. Desviación (fallo) | | |
| 5. Parada y arranque | | |
| 6. intervalo_max_ms | | |
| 7. Trayectoria a v20 | | |
