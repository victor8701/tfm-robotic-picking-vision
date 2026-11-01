# Fase robótica: caja grande con dos manos (mapa de trabajo)

**Estado:** borrador v3, 1 de noviembre de 2026 (tarde). Rama `robotica-caja-bimanual`, publicada en GitHub por petición de Víctor. El repositorio es público: no incluye material del tutor. Pendiente de completar con los proyectos a aprovechar (§12).

## 1. Objetivo

Entrada: una caja grande abierta, con cajas pequeñas (de zapatos) dentro, en la zona de trabajo.

Secuencia:
1. El águila (RGB-D, cenital) localiza la caja grande y las cajas pequeñas.
2. Los dos brazos van a un punto de aproximación calculado a partir de la caja.
3. El brazo **maestro** cierra el visual servoing con su cámara de muñeca sobre la caja.
4. El brazo **seguidor** coloca su mano en la transformación fija que dicta la geometría de agarre.
5. Las dos manos cierran con fuerza limitada, verifican el agarre y levantan a la vez.
6. Transporte a velocidad baja hasta el punto B, depósito y retirada.

**Alcance ahora:** caja grande y cajas pequeñas (identificación). **Fuera por ahora:** prendas, relevo entre brazos, PLC (se deja para el final), cinta transportadora.

## 2. Escenario de partida

| Elemento | Valor | Estado |
|---|---|---|
| Robots | 2× ABB CRB 15000 GoFa, 6 ejes, 5 kg incluida la herramienta | Según memoria. Carga y alcance a confirmar en la ficha |
| Manos | 2 manos tipo mano | Modelo CAD pendiente |
| Águila | RealSense RGB-D, cenital sobre la zona de trabajo | Modelo por confirmar. Error real por medir |
| Cámaras de muñeca | RGB-D, una por brazo | Decidido. Modelo por confirmar |
| Caja grande | Abierta, interior ~70 × 65 cm (6 cajas en 2 × 3), pared de **20 cm o más**, **cartón natural** | Decidido por Víctor ("por ahora") |
| Cajas pequeñas | Cajas de zapatos **sin tapa**, medida orientativa 32–35 × 21–23 × 12–13 cm, **blancas mates** | Color decidido por Víctor. Medir las reales |
| Peso | 2–4 kg con las 6 cajas llenas | Estimación. Medir |
| Mesa | Superficie y color por definir. Oscura o neutra, para contrastar con el cartón | Pendiente (D16) |
| Puntos A, aproximación y B | Por definir en RobotStudio | Pendiente |

**Color dominante de las prendas del inventario de prueba** (1 267 miniaturas, estimado con CLIP): negro 26 %, azul 17 %, gris 11 %, marrón 10 %, blanco 6 %, rojo 6 %, rosa 6 %, verde 5 %, morado 4 %, beige 4 %, amarillo 3 %, naranja 2 %.
- **Caja grande de cartón natural** (decidido por Víctor, "por ahora"). Consecuencia a vigilar: las cajas pequeñas no tienen tapa, así que la ropa se ve desde arriba. El marrón del cartón comparte tono con la ropa marrón y beige (14 % del inventario juntas). El color no separa la caja de la prenda: la separación tiene que venir de la geometría (borde, altura, rectángulo mayor que las cajas pequeñas).
- **Mesa oscura o neutra**, para que el borde de cartón se vea (D16).
- **Blanco** para las cajas pequeñas: contrasta con el cartón y separa bien las prendas oscuras.
- **Respaldo si la detección falla:** forrar la caja grande de naranja mate. Es el color que menos aparece en la ropa (2 %).

Las cifras son orientativas: son colores estimados con CLIP sobre miniaturas, no mediciones de prendas reales.

**Medida de la caja de zapatos.** No hay medida estándar. Una caja postal de cartón mide 32,5 × 21 × 12,5 cm por dentro ([Telecajas](https://telecajas.com/products/caja-postal-automontable-34-5x21x12-5-cm)). Usamos ese orden de magnitud y medimos las reales.

## 3. Arquitectura

- **RobotStudio** (Windows): celda, controladores virtuales, pruebas de alcance y colisiones.
- **ROS 2 Humble** sobre Ubuntu 22.04 (WSL2 para desarrollo): visión del águila y de las muñecas, planificación, estados, visualización. ROS 2 es el bus entre procesos.
- **Puente EGM**: un único proceso con dos sesiones (una por controlador, 250 Hz). Solo habla con los controladores. Recibe objetivos de ROS 2 a 20–50 Hz y los interpola. No lleva lógica de visión.
- **PLC Siemens**: al final. Hasta entonces, paro de emergencia de los controladores y paro físico en las pruebas reales.

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
| D9 | Caja grande de cartón natural ("por ahora", decidido por Víctor). Cajas pequeñas blancas mates. Respaldo si el cartón no separa: forrar de naranja mate | Decidida (Víctor) |
| D10 | Caja grande interior ~70 × 65 cm, pared de 20 cm o más | Propuesta. Depende de la mano |
| D11 | Dos controladores con puente EGM. MultiMove solo si la licencia lo justifica | Propuesta |
| D12 | Dónde agarra cada mano | Abierta. Depende del CAD de la mano |
| D13 | Ubuntu 22.04 en WSL2 para desarrollar. Puente en Linux nativo si el jitter no basta | Abierta. Medir |
| D14 | Cajas pequeñas sin tapa | Cerrada (confirmado por Víctor) |
| D15 | Modelo de RealSense del águila y de las muñecas | Abierta |
| D16 | Color y material de la mesa de trabajo: oscura o neutra, para contrastar con el cartón | Abierta |

## 5. Visual servoing (solo caja)

- **PBVS** sobre la pose de la caja, estimada desde la cámara del maestro. Las features son bordes y trozos de pared, no las cuatro esquinas: a 15 cm de la caja, una cámara de 60–70° ve unos 20 cm.
- **Rango de captura** (distancia y ángulo desde los que el servo converge): se mide en simulación y en la visita 3. El error del águila tiene que ser menor que ese rango.
- **Bucle:** cámara a 30 fps y latencia de ~100 ms. El puente interpola a 250 Hz. Velocidad baja cerca de la caja. Compensar la latencia con marcas de tiempo.
- **Vigilar:** oclusión por la propia mano; singularidades con la herramienta vertical; si se pierde la visión más de un tiempo límite, parar.

## 6. Alcance conjunto

1. Muestrear la pose de la caja (x, y, giro) dentro de la zona prevista.
2. Para cada pose, resolver la cinemática inversa de las dos manos a la vez, con la orientación de agarre.
3. Comprobar límites articulares con margen y singularidades.
4. Dibujar el mapa de alcance conjunto en RobotStudio.
5. Colocar A, aproximación y B dentro, con margen.
6. Si no cabe: mover las bases, limitar el giro de la caja o reducir su tamaño.

## 7. Manos y GraspIt

- **Sin el CAD de la mano no hay colisiones fiables en RobotStudio ni modelo para GraspIt.** Pedir el CAD (STEP/STL) y, si existe, el URDF, al fabricante o al laboratorio. Es la primera tarea de F1.
- **Si no hay CAD:** medir la mano en la visita 1 (apertura, grosor de dedos, distancia de la palma) y hacer un modelo simplificado con cajas y cilindros para colisiones en RobotStudio. Sirve para alcance y colisiones; GraspIt necesita la geometría real.
- **GraspIt:** sí, pero después del CAD. Sirve para elegir y comprobar los contactos de cada mano en las paredes. No coordina los dos brazos ni modela el cartón.
- **Estado del CAD:** Víctor lo pedirá; no sabe si será posible (1-nov). Si no llega, aplicar el modelo simplificado de arriba.
- **Confirmación del agarre** por la posición de los dedos, no por vacío.
- **Almohadillas:** fricción alta, porque el cartón resbala. Altura mínima de pared: dato de la mano.

## 8. Calibración (puesta en marcha)

1. TCP de cada mano (centro entre dedos).
2. Águila con mundo: tablero de geometría conocida sobre la mesa.
3. Bases con mundo: utillaje rígido con puntos conocidos, tocados con el TCP de cada brazo.
4. Hand-eye de cada cámara de muñeca, con tablero en la mano y varias poses.
5. Prueba de consistencia (los dos TCP tocan el mismo punto) y prueba de sujeción (caja vacía, fuerzas internas).

Presupuesto de error objetivo: ~2 mm. En RobotStudio la calibración sale exacta: hay que inyectar error para probar la sensibilidad.

## 9. Licencias a preguntar

1. RobotStudio con Virtual Controller.
2. RobotWare: movimiento guiado externo (EGM). Sin esta opción no hay control a 250 Hz.
3. RobotWare: MultiMove, solo si los dos brazos van en un único controlador.
4. Control de fuerza o compliance para el GoFa, si existe en la versión del laboratorio.
5. Versión de RobotWare del laboratorio y del virtual: deben coincidir.
6. PC SDK o Robot Web Services: uso y coste.
7. Driver y licencia de las manos.
8. Licencia académica de la universidad.

Libres: ROS 2, MoveIt 2, OpenCV, librealsense.

## 10. Fases

Horas estimadas (no medidas). El Gantt (§13.2) asignaba ~32 h a octubre y ~32 h a noviembre. Este alcance son ~150 h.

| Fase | Qué sale | Horas | Dónde | Estado |
|---|---|---|---|---|
| F0 Especificación y reutilización | Este documento y revisión de repos | 7 | Casa | En curso |
| F1 Celda en RobotStudio | Dos GoFa, mesa, caja CAD, A/aprox./B, alcance conjunto, colisiones | 17 | Casa (Windows) | Pide CAD de la mano |
| F2 Control externo | Puente EGM con dos sesiones, latencia y jitter medidos, paro y watchdog | 17 | Casa + V1 | Pide licencias |
| F3 Percepción del águila | Caja grande y cajas pequeñas, dataset RGB-D propio, error medido | 22 | Casa + V1–V2 | Medir la cámara |
| F4 Calibración | Águila↔mundo, bases, hand-eye, consistencia | 13 | Laboratorio (V2) | Puesta en marcha |
| F5 Planificación bimanual | Aproximación, colisiones entre brazos, máquina de estados sin PLC | 17 | Casa | Depende de F1 |
| F6 Visual servoing | PBVS maestro-seguidor sobre la caja, rango de captura | 22 | Casa + V3 | Depende de F3 |
| F7 Agarre y transporte | Caja vacía, luego llena, velocidad baja, liberación en B | 17 | Laboratorio (V4–V5) | Depende de F4–F6 |
| F8 Integración | 100 ciclos simulados y 20–30 reales | 17 | Mixto | Al final |
| F9 Memoria y vídeos | Capítulo de TFM, diagramas, vídeos para el tutor | 9 | Casa | Continuo |

**Ruta crítica:** F1 (con el CAD de la mano) → F3 (con las capturas de V1) → F4 → F6 y F7.

## 11. Visitas al laboratorio

Fecha por acordar con el tutor. Cada visita con guion escrito y grabación (vídeo, rosbag2, logs del controlador, imágenes RGB-D).

- **V1:** medir cajas y mano. Capturas RGB-D (vacía, llena, distintas luces). Error de la RealSense a 0,5, 1 y 1,5 m sobre tabla plana. EGM en seco con el controlador real (consigna igual a la posición actual).
- **V2:** calibración (F4).
- **V3:** servoing en seco, sin agarre. Primeros movimientos conjuntos a velocidad baja.
- **V4:** agarre con caja vacía.
- **V5:** caja llena, transporte y liberación en B.
- **V6:** ciclos completos y grabación para la memoria.

## 12. Reutilización de otros proyectos (pendiente de los links)

| Qué buscar | Proyecto | Fase | Estado |
|---|---|---|---|
| Puente EGM en C# (dos sesiones) | Pendiente | F2 | Pendiente |
| Calibración hand-eye y extrínseca | Pendiente | F4 | Pendiente |
| Captura y drivers de RealSense | Pendiente | F3 | Pendiente |
| Visual servoing (PBVS/IBVS) | Pendiente | F6 | Pendiente |
| Estación RobotStudio y RAPID | Pendiente | F1 | Pendiente |
| Modelo de la mano (URDF/CAD) | Pendiente | F1, F7 | Pendiente |

## 13. Riesgos

1. **Sin CAD de la mano**, no hay colisiones ni agarre fiables. Pedirlo ya.
2. **Error del águila mayor que el rango de captura del servo.** Medir en V1. Si no basta, marcadores ArUco en el borde de la caja.
3. **Desfase entre dos sesiones EGM** → fuerzas internas. Un proceso, jitter medido, velocidad baja al transportar.
4. **Cartón deformable:** la caja se abomba al agarrar. Agarre por el borde, fuerza limitada, pruebas con caja vacía antes.
5. **Acceso al laboratorio.** F1–F3 en casa y visitas agrupadas.
6. **Redes WSL2 ↔ RobotStudio y USB de la cámara.** Prueba temprana en casa (F2).
7. **Licencias no disponibles** (EGM, control de fuerza). Preguntar ya (§9).
8. **Ropa que sobresale** de las cajas pequeñas (van sin tapa): puede tapar la vista y chocar con la mano. Mitigación: pared de la caja grande de 20 cm o más y pruebas con ropa real en la visita 1.
9. **El cartón no separa la caja de la ropa marrón y beige** (14 % del inventario), y la mesa puede confundirse con el cartón. Mitigación: separar por geometría (borde, altura), mesa oscura o neutra, y si falla, forrar de naranja (D9).

## 14. Preguntas abiertas

- ¿De qué color es la mesa de trabajo? Debe contrastar con el cartón (D16).
- Respuesta del fabricante o del laboratorio sobre el CAD de la mano (lo pide Víctor).
- Modelo exacto de la RealSense del águila y de las muñecas.
- ¿Dónde corre el driver de la cámara: laboratorio o portátil?
- Fecha de acceso al laboratorio (tutor).
- Respuesta sobre Ubuntu y licencias.
- Dimensiones reales de las cajas de zapatos y peso con ropa.
