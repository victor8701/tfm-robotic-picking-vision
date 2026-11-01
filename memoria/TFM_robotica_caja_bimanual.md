# Fase robótica: caja grande con dos manos (mapa de trabajo)

**Estado:** borrador v5, 1 de noviembre de 2026 (noche). Vive en la rama `analisis-mercado`, carpeta `memoria/`. Cambios respecto a la v4: revisión del repo EGM del proyecto previo (§12.4), decisiones sobre el puente EGM (D26 a D30), ausencia de estación de RobotStudio en el laboratorio (§2) y plan para unir los proyectos (§15). Pendiente: medidas de la mesa y licencias (§9 y §14).

## 1. Objetivo y alcance

Entrada: una caja grande de cartón, abierta, con cajas de zapatos independientes dentro. Las cajas pequeñas se pueden sacar de la grande.

Secuencia:
1. La RealSense (cenital, RGB-D) localiza la caja grande y las cajas pequeñas.
2. Los dos brazos van a un punto de aproximación calculado a partir de la caja.
3. El brazo **maestro** cierra el visual servoing con su cámara de muñeca sobre la caja.
4. El brazo **seguidor** coloca su mano en la transformación fija que dicta la geometría de agarre.
5. Las dos manos cierran con fuerza limitada, verifican el agarre y levantan a la vez.
6. Transporte a velocidad baja hasta el punto B, depósito y retirada.

**Alcance ahora:** transporte bimanual de la caja grande. Identificar las cajas pequeñas sigue dentro del objetivo (la cámara las ve), pero el transporte no depende de ellas. **Fuera por ahora:** prendas, relevo entre brazos, PLC (se deja para el final), cinta transportadora.

## 2. Celda de partida

Datos confirmados por Víctor (1 de noviembre) y datos de los repositorios del curso.

| Elemento | Valor | Estado |
|---|---|---|
| Robots | 2× ABB GoFa. El primero es el mismo del proyecto de Robótica Industrial; el segundo se instala cerca, en posición a definir | Confirmado. Modelo exacto por leer en la placa |
| Carga | No es limitante: cajas de zapatos, 2–4 kg en total con las seis llenas | Confirmado por Víctor |
| Alcance | Lo que sí importa para ubicar las bases | Pendiente. Leer en la placa o la ficha |
| Controlador | OmniCore (RobotWare 7), no IRC5 como decía la memoria | Corregido. Licencias en §9 |
| Manos | 2 manos tipo mano (no ventosas) | CAD pedido por Víctor. Peso pendiente |
| Cámara del águila | RealSense RGB-D fija en el mismo soporte y a la misma altura que la webcam del curso | Modelo y resolución por confirmar. La homografía del curso no sirve (§8) |
| Cámaras de muñeca | RGB-D, una por brazo | Decidido. Modelo por confirmar |
| Mesa | Mismo tamaño que la de Robótica Industrial | Dimensiones por medir en V1 (§14). No hay estación de RobotStudio del laboratorio con la mesa modelada (1 de noviembre) |
| Caja grande | Abierta, cartón natural, interior ~70 × 65 cm (6 cajas en 2 × 3), pared de 20 cm o más | Color decidido por Víctor ("por ahora"). Medida: propuesta |
| Cajas pequeñas | Cajas de zapatos independientes, sin tapa, extraíbles de la caja grande, blancas mates. Medida orientativa 32–35 × 21–23 × 12–13 cm | Decidido. Medir las reales |
| Puntos A, aproximación y B | Por definir en RobotStudio | Pendiente |

**Entorno del laboratorio** (fotos de `robotica_industrial`, en `doc/` y en `lab3_pick_place_VC/client-tcpip-gofa/images/`): mesa de chapa ondulada plateada sobre un bastidor de perfil de aluminio; la cámara cuelga de un poste sobre la mesa; la zona de recogida está marcada con líneas rojas; hay un palet negro de depósito; la pantalla del FlexPendant queda a la derecha; de fondo, pared de ladrillo y una ventana. Repositorio: https://github.com/victor8701/robotica_industrial

**Colores.** Color dominante de las prendas del inventario de prueba (1 267 miniaturas, estimado con CLIP): negro 26 %, azul 17 %, gris 11 %, marrón 10 %, blanco 6 %, rojo 6 %, rosa 6 %, verde 5 %, morado 4 %, beige 4 %, amarillo 3 %, naranja 2 %.
- **Caja grande de cartón natural** (decidido por Víctor, "por ahora"). Como las cajas pequeñas no tienen tapa, la ropa se ve desde arriba. El marrón del cartón comparte tono con la ropa marrón y beige (14 % del inventario juntas): el color no separa la caja de la prenda. La separación tiene que venir de la geometría (borde, altura, rectángulo mayor que las cajas pequeñas).
- **Cajas pequeñas blancas:** contrastan con el cartón y separan bien las prendas oscuras.
- **Mesa:** la chapa plateada del laboratorio es neutra, así que el cartón se separa por saturación. Hay que vigilar las franjas de la chapa (§12.2).
- **Respaldo si la detección falla:** forrar la caja grande de naranja mate. Es el color que menos aparece en la ropa (2 %).

Las cifras son orientativas: colores estimados con CLIP sobre miniaturas, no medidos en prendas reales.

**Medida de la caja de zapatos.** No hay medida estándar. Una caja postal de cartón mide 32,5 × 21 × 12,5 cm por dentro ([Telecajas](https://telecajas.com/products/caja-postal-automontable-34-5x21x12-5-cm)). Usamos ese orden de magnitud y medimos las reales.

## 3. Arquitectura

- **RobotStudio** (Windows): celda, controladores virtuales, pruebas de alcance y colisiones. No hay estación del laboratorio (1 de noviembre), así que la celda se modela con las medidas de V1 (§14).
- **ROS 2 Humble** sobre Ubuntu 22.04 (WSL2 para desarrollar): visión de la RealSense y de las muñecas, planificación, estados, visualización. ROS 2 es el bus entre procesos.
- **Puente EGM** (Windows, C#; decidido por Víctor el 1 de noviembre): un único proceso con dos sesiones (una por controlador, 250 Hz). Solo habla con los controladores. Parte del código EGM del proyecto previo (§12.4). Recibe objetivos de ROS 2 por TCP desde WSL2, a 20–50 Hz, y los interpola. No lleva lógica de visión.
- **Comunicación del curso:** el proyecto de Robótica Industrial usaba un socket TCP con RAPID como servidor. Sirve para ir a puntos con una cámara fija, no para servoing. Lo rescatamos para pruebas de conexión y como plan B si no hay licencia EGM (§9).
- **PLC Siemens:** al final. Hasta entonces, paro de emergencia de los controladores y paro físico en las pruebas reales.

## 4. Decisiones

| # | Decisión | Estado |
|---|---|---|
| D1 | Coordinación maestro-seguidor en la primera versión. Pose común de caja en la versión final | Cerrada |
| D2 | Visual servoing solo sobre la caja. El seguidor sigue la transformación fija de agarre | Cerrada |
| D3 | EGM: un proceso, dos sesiones, un empaquetador por robot | Cerrada |
| D4 | ROS 2 entre procesos. El puente EGM solo habla con los controladores | Cerrada |
| D5 | Cámaras de muñeca RGB-D | Cerrada |
| D6 | Calibración en la puesta en marcha, no antes | Cerrada |
| D7 | PLC al final | Cerrada |
| D8 | Caja grande abierta (sin tapa) | Cerrada |
| D9 | Caja grande de cartón natural ("por ahora"). Cajas pequeñas blancas. Respaldo: naranja mate | Decidida por Víctor (1 de noviembre) |
| D14 | Cajas pequeñas sin tapa | Cerrada (Víctor) |
| D17 | Cámara del águila: RealSense RGB-D fija en el soporte de la webcam del curso, mismo punto y altura | Cerrada (Víctor, 1 de noviembre) |
| D18 | Cajas pequeñas independientes y extraíbles, no celdas con separadores | Cerrada (Víctor, 1 de noviembre) |
| D19 | Segunda base cerca de la primera; posición a decidir con el alcance conjunto | Cerrada (Víctor, 1 de noviembre). Posición pendiente |
| D20 | La carga no limita: el GoFa del curso sirve | Cerrada (Víctor, 1 de noviembre). Alcance pendiente |
| D21 | GraspIt con el flujo de la asignatura: planificar, filtrar, YAML, verificar | Cerrada en el método. Depende del modelo de la mano |
| D10 | Caja grande interior ~70 × 65 cm, pared de 20 cm o más | Propuesta. Depende de la mano y de la mesa |
| D11 | Dos controladores con puente EGM (cada GoFa suele llevar su propio OmniCore). MultiMove solo si los dos van en un único controlador | Propuesta, probable. Confirmar en el laboratorio |
| D12 | Dónde agarra cada mano | Abierta. Depende del CAD de la mano |
| D13 | Ubuntu 22.04 en WSL2 para desarrollar ROS 2 y visión. El puente EGM no va en WSL2 (D27) | Decidida en lo esencial (1 de noviembre). Medir el jitter del puente en Windows |
| D15 | Modelo exacto de la RealSense y su resolución | Abierta |
| D16 | Mesa: la chapa plateada del laboratorio, neutra y válida para el cartón. Vigilar las franjas | Propuesta (fotos del laboratorio) |
| D22 | GraspIt: entorno ROS 1 aparte, o GraspIt sin ROS | Abierta. Decidir con el modelo de la mano |
| D23 | La homografía del curso no sirve para la RealSense: recalibrar a la altura del borde o usar PnP | Propuesta |
| D24 | La calibración cubre toda la zona de la caja (el curso calibró unos 21 × 32 cm) | Propuesta |
| D25 | Si no hay licencia EGM en el OmniCore del laboratorio: plan B por definir (sockets o RWS) | Abierta. Confirmar la licencia |
| D26 | Reutilizar el protocolo EGM y el módulo RAPID `MOD_EGM` del proyecto previo (§12.4) como punto de partida, sin su estado global ni su escritura dentro del bucle de 250 Hz | Propuesta |
| D27 | Puente EGM en Windows, en C#. ROS 2 en WSL2 le envía objetivos por TCP | Decidida por Víctor (1 de noviembre) |
| D28 | Sin SpaceMouse en el laboratorio: la teleoperación queda fuera de V1 y los movimientos de prueba salen de RAPID, a velocidad baja | Hecho: no hay SpaceMouse (Víctor, 1 de noviembre) |
| D29 | `MaxPosDeviation` y `MaxSpeedDeviation` de EGM se fijan según el espacio de trabajo, no con el 1000 del proyecto previo | Propuesta. Medir en el controlador virtual |
| D30 | Semántica de `Planned` en EGM: ¿desplazamiento respecto a la trayectoria o posición absoluta? El README del proyecto previo dice incrementos y el código envía el acumulado | Abierta. Comprobar con desplazamientos pequeños en el controlador virtual |

## 5. Visual servoing (solo caja)

- **PBVS** sobre la pose de la caja, estimada desde la cámara del maestro. Las features son bordes y trozos de pared, no las cuatro esquinas: a 15 cm de la caja, una cámara de 60–70° ve unos 20 cm.
- **Rango de captura** (distancia y ángulo desde los que el servo converge): se mide en simulación y en la visita 3. El error del águila tiene que ser menor que ese rango.
- **Profundidad de la RealSense:** a 1 m, el error de profundidad es del orden de 1–2 cm (depende del modelo). Sirve para ver el borde y el fondo, no para la altura de agarre. La altura sale de la geometría de la caja y se comprueba tocando (lección del curso).
- **Bucle:** cámara a 30 fps y latencia de ~100 ms. El puente interpola a 250 Hz. Velocidad baja cerca de la caja. Compensar la latencia con marcas de tiempo.
- **Vigilar:** oclusión por la propia mano; singularidades con la herramienta vertical; si se pierde la visión más de un tiempo límite, parar.

## 6. Alcance conjunto

1. Muestrear la pose de la caja (x, y, giro) dentro de la zona prevista.
2. Para cada pose, resolver la cinemática inversa de las dos manos a la vez, con la orientación de agarre.
3. Comprobar límites articulares con margen y singularidades.
4. Dibujar el mapa de alcance conjunto en RobotStudio.
5. Colocar A, aproximación y B dentro, con margen.
6. Si no cabe: mover la segunda base (D19), limitar el giro de la caja o reducir su tamaño.

Sin las medidas de la mesa y el alcance del GoFa, el mapa no se puede hacer, porque ellas fijan dónde puede ir la segunda base.

## 7. Manos y GraspIt

- **Sin el CAD de la mano no hay colisiones fiables en RobotStudio ni modelo para GraspIt.** Víctor lo pedirá al fabricante o al laboratorio; no sabe si será posible. Si no llega, medir la mano en la visita 1 (apertura, grosor de dedos, distancia de la palma) y hacer un modelo simplificado con cajas y cilindros.
- **El flujo de GraspIt ya existe en la asignatura de Manipulación** (`GUIA_IMPLEMENTACION.md`, §12.3): planificar agarres con GraspIt, quedarse con los de `epsilon_quality > 0`, guardar los 10 mejores en YAML, elegir uno por calidad, comprobarlo levantando en Z y corregir el offset antes de depositar. Lo reutilizamos tal cual para las manos cuando tengamos su modelo.
- **Entorno:** el flujo usa `graspit_interface`, que se lanza con `roslaunch`, es decir, ROS 1. Nuestro WSL es Ubuntu 22.04 con ROS 2. Opciones: un entorno ROS 1 aparte solo para GraspIt, o GraspIt sin ROS (D22).
- **Confirmación del agarre** por la posición de los dedos, no por vacío.
- **Almohadillas:** fricción alta, porque el cartón resbala. Altura mínima de pared: dato de la mano.

## 8. Calibración (puesta en marcha)

Lecciones de la puesta en marcha del curso (`PUESTA_EN_MARCHA_28abril.md` y `PUESTA_EN_MARCHA_05mayo.md`, §12.1):
- **Un solo marco de trabajo**, escrito en la documentación. El curso confundió `wobj0` con `Workobject_1` (desfase de 329 y 70 mm) y el robot fue a sitios erróneos. Antes de medir nada, comprobar el marco activo en RobotStudio.
- **La homografía del curso tenía 4 puntos.** Con 4 puntos el error siempre sale cero y no valida nada. Nosotros usaremos al menos 6 puntos y validación con puntos no usados.
- **Criterio del curso:** RMS menor de 5 mm como objetivo; entre 5 y 15 mm, aceptable; más de 15 mm, repetir.
- **Altura de calibración:** una homografía solo vale para un plano. La del curso era el plano de la mesa. La nuestra tiene que ser a la altura del borde de la caja, o usar PnP con el tamaño conocido de la caja.
- **Zona:** el curso calibró unos 21 × 32 cm en `wobj0` (X entre 756 y 969 mm, Y entre 67 y 385 mm). La caja de 70 × 65 cm necesita calibrar toda su zona de trabajo (D24).
- Recalibrar si la cámara se mueve.

Pasos:
1. TCP de cada mano (centro entre dedos).
2. Águila con mundo: al menos 6 marcas en la mesa, validación con marcas no usadas, RMS menor de 5 mm como objetivo.
3. Bases con mundo y entre ellas: utillaje rígido con puntos conocidos, tocados con el TCP de cada brazo.
4. Hand-eye de cada cámara de muñeca, con tablero en la mano y varias poses.
5. Prueba de consistencia (los dos TCP tocan el mismo punto) y prueba de sujeción (caja vacía, fuerzas internas).

Presupuesto de error objetivo: ~2 mm. En RobotStudio la calibración sale exacta: hay que inyectar error para probar la sensibilidad.

## 9. Licencias a preguntar

1. RobotStudio con Virtual Controller y licencia Premium para EGM (la exige el README del proyecto previo, §12.4).
2. RobotWare: movimiento guiado externo (EGM) en el OmniCore del laboratorio y en el segundo. **Sin esta opción no hay control a 250 Hz.** Ningún proyecto del curso la usó, así que hay que comprobarla pronto (D25).
3. RobotWare: MultiMove, solo si los dos brazos van en un único controlador (D11).
4. Control de fuerza o compliance para el GoFa, si existe en la versión del laboratorio.
5. Versión de RobotWare del laboratorio y del virtual: deben coincidir.
6. PC SDK o Robot Web Services: uso y coste.
7. Driver y licencia de las manos.
8. Licencia académica de la universidad.

Libres: ROS 2, MoveIt 2, OpenCV, librealsense.

## 10. Fases

Horas estimadas (no medidas). El Gantt (§13.2 de `Estado_arte.md`) asignaba ~32 h a octubre y ~32 h a noviembre. Este alcance son ~150 h. F1 queda en 17 h: no hay estación del laboratorio. F2 baja a 14 h si el puente en C# reutiliza el código del proyecto previo (si se escribe en Python, 17 h). F3 baja a 18 h y F4 a 11 h si reutilizamos el código del curso (si no, 22 h y 13 h).

| Fase | Qué sale | Horas | Dónde | Rescate (§12) | Estado |
|---|---|---|---|---|---|
| F0 Especificación y reutilización | Este documento | 7 | Casa | Revisión de los tres proyectos | En curso |
| F1 Celda en RobotStudio | Dos GoFa, mesa, caja CAD, A/aprox./B, alcance conjunto, colisiones | 17 | Casa (Windows) | Add-in del proyecto previo para cargar trayectorias desde CSV (§12.4); medidas de la mesa | Pide CAD y medidas |
| F2 Control externo | Puente EGM en Windows (C#) con dos sesiones, latencia y jitter, paro y watchdog | 14 | Casa + V1 | Proyecto previo (§12.4): protocolo, bucle y `MOD_EGM`; `mock_robot.py` para probar sin robot; reconexión y patrón de RAPID | Pide licencias (EGM en virtual y en el laboratorio) |
| F3 Percepción del águila | Caja grande y cajas pequeñas, dataset RGB-D propio, error medido | 18 | Casa + V1–V2 | `deteccion_esquinas.py` (HSV, Hough, 4 esquinas); `ajuste_parametros_*` | Recalibrar sobre la RealSense |
| F4 Calibración | Águila↔mundo, bases, hand-eye, consistencia | 11 | Laboratorio (V2) | `calibrar_homografia.py`; checklist de puesta en marcha | Puesta en marcha |
| F5 Planificación bimanual | Aproximación, colisiones entre brazos, máquina de estados sin PLC | 17 | Casa | Idea del detector de colisiones; BiRRT* del curso (librería externa) | Depende de F1 |
| F6 Visual servoing | PBVS maestro-seguidor sobre la caja, rango de captura | 22 | Casa + V3 | Nada directo. `TFM_PROPUESTA.md` sugiere ViSP | Depende de F3 |
| F7 Agarre y transporte | Caja vacía, luego llena, velocidad baja, liberación en B | 17 | Laboratorio (V4–V5) | Flujo GraspIt, verificación en Z, compensación de offset | Depende de F4–F6 y de la mano |
| F8 Integración | 100 ciclos simulados y 20–30 reales | 17 | Mixto | — | Al final |
| F9 Memoria y vídeos | Capítulo de TFM, diagramas, vídeos para el tutor | 9 | Casa | — | Continuo |

Total: 149 h (152 h si F2 se escribe en Python).

**Ruta crítica:** F1 (CAD de la mano y medidas de la mesa) → F3 (capturas de V1 con la RealSense) → F4 → F6 y F7.

## 11. Visitas al laboratorio

Fecha por acordar con el tutor. Cada visita con guion escrito y grabación (vídeo, rosbag2, logs del controlador, imágenes RGB-D).

- **V1:** medir la mesa, la zona de recogida y el sitio de la segunda base. Medir las cajas de zapatos y la caja grande. Montar la RealSense en el soporte de la webcam y medir su error a 0,5, 1 y 1,5 m sobre tabla plana. Comprobar la opción EGM 689-1 y la configuración UDP del controlador (puerto 6511, y los nombres «default» y «EGMsensor» que usa el RAPID), sin mover el robot. Prueba de comunicación en solo lectura, con el controlador real y con `mock_robot.py` en el portátil. Capturas RGB-D con cajas (vacía, llena, distintas luces). Medir la mano si no hay CAD.
- **V2:** calibración (F4).
- **V3:** servoing en seco, sin agarre. Primeros movimientos conjuntos a velocidad baja.
- **V4:** agarre con caja vacía.
- **V5:** caja llena, transporte y liberación en B.
- **V6:** ciclos completos y grabación para la memoria.

## 12. Proyectos de referencia

Revisión hecha el 1 de noviembre. Para cada proyecto: qué hacía, qué rescatamos para el TFM y qué descartamos.

### 12.1 robotica_industrial: proyecto de equipo de la asignatura (la misma celda)

https://github.com/victor8701/robotica_industrial (equipo UC3M; Víctor figura como Viktor).

- **Qué hacía:** un GoFa recogía cubos de cuatro colores (amarillo, azul, rojo y verde) con un electroimán. El operario elegía color y cantidad en la pantalla del FlexPendant (WebApp HTML/JS con OmniCore SDK) y los apilaba en una rejilla 3×3 con 160 mm de separación. La visión usaba una webcam USB de 640×480, segmentación HSV por color, centroide, homografía píxel→mm en `wobj0` y envío de la cadena «XXXYYYY» por socket TCP a RAPID (servidor en el puerto 1025). Había un modo PLC con entradas DI1/DI2 en lugar de la pantalla.
- **Qué rescatamos:**
  - **Checklist y lecciones de puesta en marcha** (`PUESTA_EN_MARCHA_28abril.md`, `PUESTA_EN_MARCHA_05mayo.md`): marco de trabajo, comprobación de ejes, Z de recogida, velocidades de arranque. Va al guion de V1 y V2 (F4).
  - **`calibrar_homografia.py`:** marcas físicas en la mesa, RANSAC y verificación con clic. Va a F4, con los cambios de §8.
  - **`mock_robot.py`:** simulador del servidor TCP. Va a F2, para probar el cliente de visión en casa.
  - **`ajuste_parametros_colores.py`:** ajuste HSV con deslizadores y guardado en JSON. Va a F3 (cartón y blanco).
  - **HMI del FlexPendant** (`lab_HMI/webapp/` y `RAPID/HMIData.mod`): estado libre u ocupado, cantidad y contador. Va al HMI de la celda, más adelante.
  - **Patrón de RAPID:** servidor, reconexión tras `ERR_SOCK_TIMEOUT` y `ERR_SOCK_CLOSED`, aproximación con `MoveJ` y descenso con `MoveL` en modo fine. Referencia para F2 y F7.
  - **Modo PLC** (DI1/DI2). Va a la integración del PLC, al final.
- **Qué no copiamos:** el protocolo de cadena fija (solo positivos, 0–999 mm, sin confirmación ni marca de tiempo); las Z fijas (100 mm, 56 mm y 33,14 mm); `ConfJ\Off` y `ConfL\Off` en las rutinas de agarre (hay que revisarlos); la pausa de 1 s entre envíos; la homografía de 4 puntos; `cv2.CAP_DSHOW` (solo Windows).
- **Dato útil:** el área calibrada fue de unos 21 × 32 cm en `wobj0`. Nuestra caja de 70 × 65 cm necesita otra escala de calibración (D24).

### 12.2 plastico_transparente: rama de este mismo repositorio (fase descartada)

https://github.com/victor8701/tfm-robotic-picking-vision/tree/plastico_transparente

- **Qué hacía:** la fase 1 del TFM con bolsas de plástico transparente. `src/deteccion_esquinas.py` segmenta la caja de cartón por color (HSV), toma el contorno mayor como zona de interés, busca los bordes con `HoughLinesP` y saca hasta 4 esquinas a partir de sus intersecciones. Después intentó localizar las bolsas con visión clásica (Canny y morfología) y luego con YOLO. Eso se descartó porque en esta fase no hay prendas sueltas. Sus pruebas usan las fotos de `images/02Dic/` (real1 a real6). No todas son del laboratorio: real5 sí lo parece, y box_real1 es de casa.
- **Qué rescatamos:**
  - **`deteccion_esquinas.py` y `ajuste_parametros_esquinas.py`:** van a F3. Es el «4 esquinas por color» del objetivo original, ya escrito.
  - **`images/02Dic/real5.jpg`** (chapa ondulada): caso de prueba del laboratorio.
  - **La idea de usar la visión para la aproximación gruesa** y dejar la precisión final a la muñeca.
- **Qué no copiamos:** los parámetros (salen de esas fotos y hay que recalibrarlos en el laboratorio), la parte de bolsas y de YOLO, y el supuesto de que no hace falta la pose 6D (nuestras manos sí la necesitan).
- **Riesgo que ya conocen:** la chapa ondulada produce muchas rectas. El código aplica primero la máscara de color y solo busca rectas dentro de la zona de la caja. Hay que mantener ese orden en el laboratorio.

### 12.3 manipulacion_pick-place: asignatura de Manipulación (simulación)

https://github.com/victor8701/manipulacion_pick-place

- **Qué hacía:** simulación en Gazebo con ROS 1 (Noetic). En la Tarea 1, un gripper flotante recogía una banana con las poses de agarre que genera GraspIt (planificación por recocido simulado; se guardan los 10 mejores con `epsilon_quality > 0` en un YAML). Elegía el de mayor calidad, comprobaba levantando en Z y compensaba el offset al depositar en la mesa. En la Tarea 2, un UR10 con gripper Jaco se planificaba en espacio articular con BiRRT*, con cinemática inversa en KDL y un detector de colisiones (brazo, pinza y obstáculos). No usa MoveIt.
- **Qué rescatamos:**
  - **El flujo de GraspIt** (`GUIA_IMPLEMENTACION.md`): va a F1 y F7, cuando tengamos el modelo de la mano.
  - **La elección por calidad, la comprobación elevando en Z y la compensación del offset en el depósito:** van a F7 y al punto B.
  - **La idea del detector de colisiones** (brazo, pinza y obstáculos): va a F5.
  - **`TFM_PROPUESTA.md`:** la arquitectura global + local (águila + cámara en la mano) encaja con la nuestra. Propone empezar sin GraspIt y usar ViSP para el visual servoing.
- **Qué no copiamos:** Gazebo, ROS 1, el gripper flotante y el UR10, porque no son nuestra celda. La librería `manipulacion_lib` (BiRRT*, detector de colisiones, GazeboRobot) no está en el repo, así que el código no se puede reutilizar sin pedirla.
- **Lo que falta en el repo:** el cuaderno `guia_graspit.ipynb` y el YAML de agarres. Están en el paquete de la asignatura.

### 12.4 RobotStudio_AddIn_EGM_trajectories: proyecto previo de teleoperación EGM (C#)

https://github.com/victor8701/RobotStudio_AddIn_EGM_trajectories. Su README dice TFG; Víctor lo llama TFM (§14).

- **Qué hacía:** tres partes. (1) Teleoperación en vivo: SpaceMouse → aplicación WinForms (.NET 4.8) → `EgmCommunicator` (UDP 6511) → controlador por EGM a 250 Hz, con el módulo RAPID `MOD_EGM`. (2) Add-in offline de RobotStudio (SDK 2024): CSV → `RsRobTarget` en la estación activa. (3) `EGM_VS`: consola .NET 8 que reproduce por EGM una trayectoria CSV. Los dos vídeos de `ExperimentoEGM` muestran la misma trayectoria por las dos vías (no los hemos podido verificar aquí).
- **Qué rescatamos:**
  - **Protocolo EGM** con Google.Protobuf y `egm.proto` (espacio de nombres `Abb.Egm`), y el bucle que responde a cada paquete del controlador con `Planned.Cartesian`: base del puente de F2 en Windows (D26, D27).
  - **`MOD_EGM`:** arranque, `EGMActPose` y `PararEGM` (estado → `EGMStop` → `EGMReset`), igual que su diagrama de flujo. Va a F2 y a la parada segura.
  - **CSV → targets** del add-in: va a F1 para cargar las trayectorias A y B en la celda.
- **Qué no copiamos:** el estado estático `MyTarget`, sin bloqueo entre hilos; la escritura del CSV y `Console.WriteLine` dentro del bucle de 250 Hz; las rutas fijas (`.rsaddin` y `C:\AAAA\Path_EGM_10.csv`); los valores `MaxPosDeviation:=1000` y `MaxSpeedDeviation:=1000` sin justificar; el nombre de robot fijado en el código (IRB140, comentado). La teleoperación con SpaceMouse queda fuera de V1 (D28).
- **Por verificar:** si `Planned` es corrección o posición absoluta (D30), y las licencias (§9).
- **Plantilla `RobotStudioEmptyAddin1_16nov`:** add-in vacío, sin código propio (solo referencias al SDK 2024). Su README la presenta como base del add-in online, pero hoy no hace nada.
- **Otros repositorios:** pendientes de que Víctor los aporte.

## 13. Riesgos

1. **Sin CAD de la mano**, no hay colisiones ni agarre fiables. Pedirlo ya.
2. **Error del águila mayor que el rango de captura del servo.** Medir en V1. Si no basta, marcadores ArUco en el borde de la caja.
3. **Desfase entre dos sesiones EGM** → fuerzas internas. Un proceso, jitter medido, velocidad baja al transportar.
4. **Cartón deformable:** la caja se abomba al agarrar. Agarre por el borde, fuerza limitada y pruebas con caja vacía antes.
5. **Acceso al laboratorio.** F1–F3 en casa y visitas agrupadas.
6. **Redes WSL2 ↔ RobotStudio y USB de la cámara.** Prueba temprana en casa (F2).
7. **Licencias no disponibles** (EGM, control de fuerza). Preguntar ya (§9). Es el riesgo más grave si falta EGM.
8. **Ropa que sobresale** de las cajas pequeñas: puede tapar la vista y chocar con la mano. Mitigación: pared de la caja grande de 20 cm o más y pruebas con ropa real en V1.
9. **El cartón no separa la caja de la ropa marrón y beige** (14 % del inventario). Mitigación: separar por geometría, mesa de chapa neutra y, si falla, forrar de naranja (D9).
10. **Cajas pequeñas sueltas:** pueden desplazarse al levantar la caja grande. Transporte lento y pruebas con caja llena antes de subir la velocidad.
11. **La homografía del curso no sirve para la RealSense** (intrínsecos distintos). Recalibrar en F4 (D23).
12. **Chapa ondulada:** las franjas producen rectas falsas. Máscara de color antes de buscar bordes (§12.2).
13. **Mesa de dimensiones desconocidas:** el alcance conjunto no se puede cerrar hasta medirla (§14).
14. **GraspIt en ROS 1 frente a nuestro ROS 2:** entorno aparte o GraspIt sin ROS (D22).
15. **Semántica de `Planned` en EGM** (D30). Si el controlador la interpreta de forma distinta a como la envía el código, el movimiento será otro. Comprobar en el controlador virtual con desplazamientos pequeños, antes de cualquier movimiento real.
16. **Límites de EGM sin justificar** en el proyecto previo (`MaxPosDeviation` y `MaxSpeedDeviation` a 1000). Los fijamos nosotros y los medimos (D29).
17. **E/S dentro del bucle de 250 Hz** (CSV y consola, en el proyecto previo). Puede causar jitter. Nada de E/S en el bucle del puente; medir el jitter con y sin ella.
18. **Red del puente:** el UDP del controlador debe llegar al PC del puente. El reenvío de puertos de Windows solo sirve para TCP, y en WSL2 con NAT el UDP que llega desde fuera no entra en la VM sin configuración extra. Por eso el puente va en Windows (D27). Queda revisar el firewall.

## 14. Preguntas abiertas

- **Medidas de la mesa.** No hay estación de RobotStudio del laboratorio (1 de noviembre). Se miden en V1 o se piden al laboratorio.
- **Modelo exacto de la RealSense** y resolución de color y profundidad.
- **Alcance del GoFa** (placa o ficha del modelo) para ubicar la segunda base.
- **Licencias de EGM y MultiMove** en el OmniCore del laboratorio y en el segundo robot. También la licencia Premium de RobotStudio para EGM en el controlador virtual (la exige el README del proyecto previo).
- **CAD de la mano.** Respuesta del fabricante o del laboratorio (lo pide Víctor).
- **Peso real de las manos**, cuando haya modelo.
- **Dimensiones reales** de las cajas de zapatos y de la caja grande.
- **Dónde corre el driver de la RealSense:** en el portátil o en el PC del laboratorio.
- **Fecha de acceso al laboratorio** (tutor).
- **Respuesta sobre Ubuntu y licencias.**
- **¿Es el repositorio de EGM tu TFG de grado (su README) o lo usaste en el TFM?** Se cita como TFG hasta que lo confirmes.
- **¿Dónde va el código de robótica?** ¿En `analisis-mercado`, junto al mapa, o en una rama nueva?

## 15. Cómo unimos los proyectos

Pasamos de cuatro repositorios sueltos a un único proyecto de robótica dentro de este repositorio. Cada pieza se copia con su origen (repositorio y commit) anotado en el encabezado del archivo. No usamos submódulos.

Carpetas propuestas, dentro de `robotica/`:

| Carpeta | Qué va dentro | Origen | Fase |
|---|---|---|---|
| `robotica/puente_egm/` | Puente EGM en C# (Windows): dos sesiones y servidor TCP para ROS 2 | `EGM_VS` y `TFG_Proyecto_Solucion/VMP` del proyecto previo (§12.4) | F2 |
| `robotica/rapid/` | Módulos RAPID: `MOD_EGM` propio, servidor y patrón de reconexión | `MOD_EGM` (§12.4) y `RAPID/` de robotica_industrial (§12.1) | F2, F7 |
| `robotica/ros2/` | Cliente del puente, estados y planificación | Nuevo | F2, F5 |
| `robotica/vision/` | Detección de la caja y de las cajas pequeñas con la RealSense | `deteccion_esquinas.py` y `ajuste_parametros_*` (§12.1 y §12.2) | F3 |
| `robotica/calibracion/` | Calibración águila↔mundo y de las bases | `calibrar_homografia.py` (§12.1), con 6 puntos o más y validación (§8) | F4 |
| `robotica/simulacion/` | Add-in CSV → targets y la celda en RobotStudio | `TFG_offline` (§12.4) y las medidas de V1 | F1 |
| `robotica/mock/` | Simulador del controlador para probar en casa | `mock_robot.py` (§12.1) | F2 |
| `robotica/grasp/` | Flujo de GraspIt y elección del agarre | `GUIA_IMPLEMENTACION.md` (§12.3) | F7 |

Orden de trabajo:

1. **F1, en casa:** la celda en RobotStudio con las medidas que tengamos. Cargar las trayectorias desde CSV con el add-in.
2. **F2, en casa:** puente EGM contra el controlador virtual de RobotStudio, con el protocolo y `MOD_EGM` del proyecto previo. Antes, comprobar D30 con desplazamientos pequeños. La conexión se prueba primero con `mock/`.
3. **F3, en casa:** detección con la RealSense y dataset propio, sin robot.
4. **F4 en adelante, en el laboratorio:** calibración y primeras pruebas reales (V2 y siguientes).

Reglas:

- Nada se mueve en el robot real sin antes pasar por el controlador virtual.
- Antes de reutilizar un módulo RAPID se revisan sus límites (D29) y sus nombres de dispositivo (§11, V1).
- Lo que se copia lleva el repositorio y el commit de origen en el encabezado.
