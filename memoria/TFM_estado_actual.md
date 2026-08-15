# Estado Actual del Trabajo de Fin de Máster (TFM)

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
