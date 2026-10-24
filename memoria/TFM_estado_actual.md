# Estado Actual del Trabajo de Fin de Máster (TFM)

## 0. Cómo vamos y qué te toca (24 de octubre de 2026)

*Panel vivo: se actualiza al final de cada sesión de trabajo y en la pestaña «Hoy» de la página «Tendencias de prenda». No sigue el calendario del Gantt: Víctor lleva su propio orden.*

**Cómo vamos**
- **Tendencia por prenda (en curso).** La tarea semanal en la nube y la revista por correo funcionan; los siete estilos se separan en las cinco dimensiones con la muestra de referencia (§6.9 de `TFM_tendencias_de_prenda.md`).
- **Fuentes de mercado de los cinco estilos nuevos: hechas.** Medidas el 13 y 14 de octubre (§6.10); Víctor aceptó 46 y `tendencia_fuentes.json` tiene 73 fuentes. La primera tarea semanal con ellas es el lunes 19 de octubre, con un tope de 120 minutos de análisis para no pasarse de tiempo.
- **Acierto del modelo grande en los cinco estilos nuevos: medido el 15 de octubre** (ronda 2; 28 recortes reales con respuesta: tipo 93 %, estampado 96 %, tejido 89 %, forma 96 %; los 6 controles rechazados).
- **Pantalones y vaqueros: arreglado el 16 de octubre (§6.11).** El modelo grande nombraba la prenda de arriba en 146 de 291 recortes de ropa inferior; con una pista de la zona del cuerpo, «Pantalón» pasa de 68 a 202 y el denim de 7 a 53. La tarea semanal usa `semanal_pista` y los 916 recortes están reetiquetados.
- **Instagram: aparcado por Víctor** (muy importante, pero ahora no puede). `instagram_prueba.py` y su tarea de GitHub están preparados.
- **Texto de tendencia en lenguaje natural hecho con datos medidos: probado (Experimento C, 16 de octubre; `TFM_experimento_C_texto_con_datos.md`).** P@5 de 83 % frente a 37 % del texto corto de un LLM que solo conoce el nombre y 70 % del oráculo (6 tendencias, un juez, puntuación a ciegas); **repetida la puntuación (24 de octubre) la dirección se mantiene pero no se confirma la magnitud** (93 % frente a 73 %, +20 pp, IC [−7, +47]). Siguiente: Trend JSON de producción con fotos de mercado, brazo opcional con modelo abierto, puntuación de SKUs y página de aprobación.
- **Límites conocidos:** Reddit solo deja unas 1 petición por minuto desde GitHub; para old money no hay comunidad de Reddit activa medible; 29 candidatos de prensa tienen la foto sin comprobar; el color es el atributo más flojo (70 % a ojo).

**Qué te toca**
1. **Instagram,** cuando puedas (30 a 40 min en el portátil).
2. **El lunes 19 de octubre:** nada que hacer; si la revista no llega o llega con fotos pendientes, mira el último «Tendencia semanal (revista)» en GitHub Actions.

---

## 1. Evolución y Definición del Proyecto

### 1.1. Fase Descartada: Manipulación de Prendas en Bolsas de Plástico
El punto de partida exploró un sistema de visión cenital para guiar un brazo robótico en el desembalaje de prendas en bolsas de plástico transparentes.
- **Logros obtenidos:** Detección geométrica de zona de trabajo con OpenCV (segmentación HSV, transformadas de Hough). Integración inicial de YOLOv8.
- **Motivo del descarte:** El plástico transparente y deformable imponía una **limitación mecánica severa**. El diseño de garras (soft-grippers) habría consumido el esfuerzo investigador, alejando el foco de la arquitectura de software e IA, que es el objetivo profesional real.

### 1.2. Dirección Final: Sistema Robótico Bimanual con Arquitectura de Modos de Operación

El TFM está definitivamente centrado en el desarrollo de un **sistema de clasificación de prendas de moda** mediante robótica colaborativa bimanual, con una arquitectura de control progresiva de cinco modos de operación.

La solución, que trabaja sobre **cajas rígidas individuales** (cada caja contiene una prenda), evita la manipulación directa de tejidos y concentra toda la carga investigadora en la capa de software e inteligencia artificial. La progresión de modos es:

| Modo | Nombre | Tecnología Core |
| :--- | :--- | :--- |
| 1 | Vaciado Geométrico (*Singulation*) | PCL + YOLO-obb para detección de cajas |
| 2 | Clasificación Supervisada | YOLOv8/11 supervisado por tipo de prenda |
| 3 | Reposición por Demanda Geográfica | Integración con ERP simulado (JSON) |
| 4 | Tendencias de Mercado (*Trend-Driven*) | CLIP + Grounding DINO + análisis de redes sociales |
| 5 | Gestión Integral | Optimización multiobjetivo (Modos 3 + 4) |

**El aporte investigador** reside en los Modos 4 y 5: el sistema actúa como un **Agente de Inteligencia de Mercado** que traduce tendencias de influencers y redes sociales en vectores semánticos (CLIP), identifica las prendas del inventario que mejor encajan con esa tendencia y genera órdenes de trabajo para los robots. Esto cierra el bucle entre **IT (marketing/tendencias) ↔ Middleware (ROS 2) ↔ OT (robots GoFa)**.

## 2. Situación de Desarrollo (Core Tecnológico)

Los cimientos tecnológicos están validados por proyectos previos:

- **Infraestructura Robótica:** 2 robots ABB GoFa anclados a mesa de trabajo.
- **Middleware:** ROS 2 como bus de mensajería y orquestador.
- **Visión / IA:** Pipeline clásico OpenCV + YOLO validado. Se integrará CLIP para la capa de tendencias (Modo 4).
- **Control e Integración IT/OT:** Código C# funcional para comunicación EGM con controladores ABB. PLC Siemens para gestión de estados y HMI en RobotStudio.

## 3. Hoja de Ruta de Desarrollo

1. **Fase 1 — Infraestructura base:** Configuración ROS 2, nodo puente EGM (Python ↔ C#), integración PLC/HMI.
2. **Fase 2 — Modos 1 y 2:** Pipeline de visión cenital (Cámara Águila), detección YOLO de cajas y prendas, transformación XYZ, picking bimanual básico.
3. **Fase 3 — Visual Servoing:** Cámaras eye-in-hand, correcciones en bucle cerrado para el agarre preciso.
4. **Fase 4 — Modo 3:** Integración del ERP simulado (JSON con datos de stock por país), lógica de reposición geográfica.
5. **Fase 5 — Modos 4 y 5 (carga investigadora):** Pipeline de análisis de tendencias, vectorización semántica con CLIP, distancia coseno para matching prenda-tendencia, optimización multiobjetivo.
