# Estado de la fase robótica (1 de noviembre de 2026)

Rama `robotica-bimanual` (desde `analisis-mercado`, mapa v6). Código en `robotica/`.

## 1. Qué se ha construido

| Paso | Contenido |
|---|---|
| 1 | Núcleo de control y seguridad. Protocolo EGM. Puente en C# (.NET 8) con controlador simulado y 14 pruebas de extremo a extremo. |
| 2 | Visión (esquinas y pose). Calibración (homografía validada y mano-ojo). Coordinador bimanual. Paquete ROS 2 (tres nodos, launch). Módulos RAPID. Conversor CSV a RAPID. |

Resultado: 98 pruebas pasan sin ROS y 100 con ROS 2 cargado. El puente C# compila sin avisos con .NET 8.0.133.
El paquete ROS 2 compila con colcon y el launch arranca los tres nodos.

Rama publicada: `origin/robotica-bimanual` (último commit 801833e). Partiendo de `analisis-mercado` (a8e5ec1), tiene siete
commits de código, documentación y mapa (v6). El commit del tutor (`02b44c2`) no está en la rama remota.

## 2. Qué se ha comprobado y qué no

Comprobado en este equipo:
- Lógica de control y seguridad, con pruebas de comportamiento.
- Puente C# real contra un controlador EGM simulado en Python, en las dos semánticas.
- Mensajes EGM: `egm.proto` reconstruido del proyecto previo y validado con protoc.
- Visión y calibración con datos sintéticos (el método de contorno aguanta ruido hasta σ = 15 con error ≤ 2 px).
- Ciclo completo del coordinador en simulación, con fallos inyectados.

**No comprobado todavía:**
- Ningún módulo RAPID en un controlador.
- El puente con el controlador virtual de RobotStudio.
- La cámara real, la RealSense ni datos del laboratorio.
- El sistema completo con robots.
- Latencia y jitter en el PC real. Las pruebas del puente solo dan una cota de cordura.

## 3. Decisiones tomadas sin consultar

Víctor pidió que no hubiera más preguntas por hoy. Estas son las decisiones que he tomado y que puede cambiar:

1. **Rama:** `robotica-bimanual`, creada desde `origin/analisis-mercado` (a8e5ec1). El commit del tutor (`02b44c2`) queda fuera de esta rama.
2. **Licencias:** interpreto «tengo lo mismo que en el TFG y en el trabajo de automatización» como RobotStudio Premium con la opción EGM. Se asume para el controlador virtual. **Falta confirmar la opción 689-1 en el OmniCore del laboratorio.**
3. **Puente:** en Windows, en C#, como decidió Víctor (D27). ROS 2 en WSL2 le habla por TCP.
4. **Teleoperación:** fuera de V1, porque no hay SpaceMouse (D28).
5. **Semántica de `planned`:** por defecto `desplazamiento` en la configuración de ejemplo. No está confirmada (D30). La prueba está en `docs/guion_virtual.md`.
6. **Valores sin medir:** `simulacion/celda.json`, los límites de EGM en `MOD_EGM.mod` y las ganancias del PBVS son de partida. Están marcados como placeholders.
7. **Visión por defecto:** método de contorno. El de líneas (port del proyecto previo) está disponible con `metodo: lineas`.
8. **TFG o TFM:** Víctor respondió que el repositorio de EGM es su **TFG**. Ya está reflejado en el mapa v6 (§14) y en la memoria.

## 4. Riesgos y hallazgos nuevos

1. **La caja puede no verse en la pose de agarre.** Con la cámara de partida (60 mm de offset lateral, 80 mm arriba del TCP) y el agarre en la pared de la caja (400 mm del centro), el centro de la caja queda a unos 62° del eje óptico. Un campo de cámara típico (media apertura de 30° a 35°) no lo ve. Las pruebas usan un campo de 80° para validar la lógica de control, y lo dicen explícitamente. Hay que decidir el montaje de la cámara y el método de aproximación final **en la visita 1**. Opciones: cámara inclinada hacia el centro, o servoing final sobre bordes visibles.
2. **`EGMActPose ... \x:=[-1, 1]` en el proyecto previo.** Si la tolerancia se interpreta en mm, limita la corrección a ±1 mm. Con el acumulado que envía el código, eso sería muy restrictivo. No he podido verificar los vídeos de `ExperimentoEGM`, así que no sé qué ocurrió en aquella prueba. Hay que comprobarlo en el controlador virtual (paso 4 de `guion_virtual.md`).
3. **El README del proyecto previo habla de incrementos, pero el código envía el acumulado.** Eso es el origen de D30.
4. **WSL2 y UDP.** El reenvío de puertos de Windows solo sirve para TCP. Por eso el puente va en Windows (D27). El control TCP desde WSL2 necesita la IP de Windows y una regla de firewall.
5. **Cliente del curso.** `ClienteGoFa.py` construye la cadena con un solo cero delante, así que no tiene anchura fija. El mapa dice «XXXYYYY». El puente nuevo usa JSON y no depende de ese formato, pero conviene corregir el mapa.
6. **Calibración del curso.** `calibrar_homografia.py` y `mock_robot.py`, citados en el mapa, no están en la copia local de `robotica_industrial` (solo está `lab3_pick_place_VC/client-tcpip-gofa`) ni en el historial del repositorio principal. Se han escrito de nuevo desde cero (`calibracion/`, `mock/`). Si existen en GitHub, habría que compararlos.

## 5. Qué falta para acabar

En orden:
1. **Controlador virtual (Víctor, en Windows):** pasar `docs/guion_virtual.md`. Decide `semantica` y el rango de `MOD_EGM`.
2. **Visita 1 (Víctor, con el tutor):** pasar `docs/guion_V1.md`. Medidas de mesa, caja y cámara, y el campo de visión en la pose de agarre.
3. **Driver de la mano:** definir cómo llegan `AGARRE_HECHO`, `VERIFICADO` y `SOLTADO` al coordinador.
4. **Calibración en el laboratorio:** la línea de comandos `calibracion/cli.py` procesa los datos de la visita 1 (homografía y mano-ojo). Faltan los datos reales.
5. **Mapa:** actualizar §9, §10, §13 y §14 con estos resultados (hecho en la versión 6 del mapa).

## 6. Cómo se reproduce

```bash
cd robotica
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q       # 98 pasan; 1 módulo se salta sin ROS
source /opt/ros/humble/setup.bash && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q   # 100 pasan
dotnet build -c Release puente_egm/PuenteEgm  # previo a las pruebas del puente
```
