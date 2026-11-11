# Robótica bimanual: código de la fase robótica

Código de la celda con **un** GoFa (decisión del tutor; el setup queda pendiente). Rama `robotica-un-robot`.
La versión con dos robots está en `robotica-bimanual`, basada en `analisis-mercado`
(mapa v5). El plan de unión de los proyectos está en `memoria/TFM_robotica_caja_bimanual.md`, §15.
Estado detallado, riesgos y suposiciones: [docs/ESTADO.md](docs/ESTADO.md).

## Qué hay y qué está comprobado

| Parte | Carpeta | Comprobado aquí | Falta |
|---|---|---|---|
| Geometría, consigna, control PBVS, seguridad, estados | `nucleo/` | Sí, con pruebas unitarias | Valores medidos en la celda |
| Coordinador bimanual | `nucleo/coordinador.py` | Sí: ciclo completo y fallos, en simulación | Driver de la mano y visibilidad real |
| Protocolo EGM | `egm/` | Sí: `egm.proto` validado con protoc, ida y vuelta de mensajes | — |
| Puente EGM en C# | `puente_egm/` | Compilado y probado con un controlador simulado (14 pruebas de extremo a extremo) | Controlador virtual de RobotStudio (Windows) |
| Controlador simulado | `mock/` | Sí (lo usan las pruebas del puente) | — |
| Visión: esquinas y pose | `vision/` | Sí, con imágenes sintéticas | Cámara real y datos del laboratorio |
| Calibración: homografía y mano-ojo | `calibracion/` (CLI en `calibracion/cli.py`) | Sí, con datos sintéticos | Datos medidos en el laboratorio |
| Nodos ROS 2 | `ros2/robotica_bimanual/` | Compilado con colcon, lanzado con su launch, nodos creados en pruebas | Sistema completo con robots |
| Módulos RAPID | `rapid/` | **No** | Controlador virtual |
| CSV a RAPID | `simulacion/csv_a_rapid.py` | Sí | — |

## Cómo se prueba

```bash
cd robotica
python3 -m pytest -q
```

- Requisitos: Python 3.10 o superior, numpy, opencv, protobuf y pytest (`requirements.txt`).
- Las pruebas del puente necesitan el ejecutable compilado: `dotnet build -c Release puente_egm/PuenteEgm`.
  Sin .NET 8 se saltan.
- Con ROS 2 Humble cargado (`source /opt/ros/humble/setup.bash`) se ejecutan también las pruebas de nodos.
- Resultado en la última ejecución: 98 pasan y 1 módulo se salta sin ROS; con ROS 2, 100 pasan.

## Convenciones

- Núcleo y puente: posiciones en **mm**, ángulos en **rad**, cuaterniones **(w, x, y, z)**.
- EGM: el cuaternión va en `(u0, u1, u2, u3)` = `(w, x, y, z)`.
- ROS 2: posiciones en **metros** y cuaterniones **(x, y, z, w)**, según REP 103. La conversión está en `ros2/robotica_bimanual/robotica_bimanual/convertir.py`.
- Un objetivo que no llega a tiempo no se ejecuta: el puente retiene el brazo (watchdog).
- Un fallo (desviación, pérdida de visión o de posición) detiene la sesión y exige rearme explícito.

## Antes de mover un robot

0. Configurar las IPs y los puertos. Lo que falta y dónde va cada valor está en [docs/configuracion.md](docs/configuracion.md).
1. Pasar el guion del controlador virtual: [docs/guion_virtual.md](docs/guion_virtual.md). Incluye la prueba que decide la semántica de `Planned` (D30).
2. Pasar la visita 1 en modo solo lectura: [docs/guion_V1.md](docs/guion_V1.md).
3. Paro físico al alcance. Ninguna trayectoria se ejecuta sin haberla visto antes en el controlador virtual.

## Qué no está hecho

- Los valores de `simulacion/celda.json` son de partida y no están medidos. Están marcados como placeholders.
- El driver de la mano: los eventos `AGARRE_HECHO`, `VERIFICADO` y `SOLTADO` llegan desde fuera.
- La caja en la pose de agarre puede no entrar en el campo de la cámara. Ver riesgos en docs/ESTADO.md.
- Los módulos RAPID no se han probado en un controlador.
- Calibración en el laboratorio: la captura de datos está en `docs/guion_V1.md` (sección D) y el procesado en `python3 -m calibracion.cli`. Faltan los datos reales.

## Estructura

```
nucleo/        lógica pura (sin ROS, sin cámara, sin robot)
egm/           protocolo EGM (egm.proto reconstruido del proyecto previo)
puente_egm/    puente EGM en C# (.NET 8), una sesión por controlador
mock/          controlador EGM simulado para probar sin robot
vision/        esquinas y pose de la caja
calibracion/   homografía con validación y mano-ojo
ros2/          paquete robotica_bimanual (nodos, launch)
rapid/         módulos RAPID (no probados)
simulacion/    celda.json (placeholders) y conversor CSV a RAPID
docs/          guiones de prueba y estado
tests/         pruebas (pytest)
```
