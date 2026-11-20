# Probar el puente con un robot: diagonales y RViz

Un solo robot: el brazo 1. El puente, con `--prueba`, manda él solo la prueba de diagonales. ROS y RViz no mandan nada: solo leen el registro del puente y dibujan el recorrido.

## Antes, una vez

- RobotStudio: el controlador del brazo 1 (`ControllerTFG_EGM`) con el módulo `MOD_EGM` cargado (el que tiene `main`).
- WSL: el paquete ROS compilado en `~/ros2_ws` (ya lo está). Si no lo estuviera:

```bash
cd ~/ros2_ws && colcon build --symlink-install --packages-select robotica_bimanual
```

## Orden de la prueba

**1. Puente (Windows, PowerShell).** Siempre antes que el controlador:

```powershell
cd "$env:USERPROFILE\source\repos\TFM_Windows\robotica\puente_egm\PuenteEgm\bin\Release\net8.0"
.\PuenteEgm.exe "$env:USERPROFILE\source\repos\TFM_Windows\robotica\puente_egm\config.json" --prueba
```

Tiene que salir `Puente en marcha. Ctrl+C para parar.` No cierres esa ventana.

**2. RobotStudio, controlador del brazo 1:** Stop → PP a Main → Play. Si el puente no está en marcha, el controlador no tiene a quién enviar datos y habrá que repetir Play.

**3. RViz (terminal de WSL):**

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 launch robotica_bimanual seguimiento.launch.py
```

Se abre RViz con el recorrido. El nodo lee `registros\puente.csv`, dentro de la carpeta `net8.0`. Si el registro está en otra carpeta: `ros2 launch robotica_bimanual seguimiento.launch.py csv:=/ruta/a/puente.csv`.

## Qué deberías ver

- **Puente:** cada 5 s, una línea de estado por sesión. En el brazo 1, `estado=activo`, `ciclos` subiendo (unos 250 por segundo) y `desviacion_mm` por debajo de 20.
- **Brazo 1:** baja primero al centro (z = 390, unos 15 s) y después repite sin parar las diagonales xy, xz e yz, de ida y vuelta.
- **RViz:** una línea azul con el recorrido, una esfera roja en la posición actual y un texto con la fase (por ejemplo `xy_ida`).
- **Brazo 2:** aparece como `esperando`. Es normal: no tiene controlador.

## Parar

- Ctrl+C en la ventana del puente, y Ctrl+C en la terminal de ROS.
- Para repetir, vuelve al paso 1.

## Si algo falla

- **No sale `Puente en marcha`:** ya hay otro puente abierto. Cierra esa ventana y vuelve a lanzarlo.
- **`esperando` y `ciclos` en 0:** el controlador no envía. Revisa Stop → PP a Main → Play.
- **`fallo` con `desviacion_excesiva`:** el brazo no sigue la referencia. Para con Ctrl+C, revisa el controlador, relanza el puente y repite el paso 2.
- **`fallo` con `prueba_no_llega`:** un paso no llegó en 60 s. Relanza el puente.
- **RViz no abre:** en WSL, `echo $DISPLAY` tiene que dar `:0`.
- **RViz vacío:** comprueba que `puente.csv` esté creciendo. Si no crece, el puente no está escribiendo.

## Notas

- Si relanzas el puente, repite el paso 2.
- El coordinador bimanual no está en el launch de un robot, así que ROS no manda órdenes al brazo.
- El modo `--prueba` funciona sin ROS.
