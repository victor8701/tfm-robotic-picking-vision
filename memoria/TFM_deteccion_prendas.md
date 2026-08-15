# Overview: Sistema Robótico Bimanual de Clasificación de Prendas

> Este documento es el overview inicial del sistema. La arquitectura de modos de operación completa está en `TFM_deteccion_prendas_modos`. La arquitectura de software detallada está en `TFM_deteccion_prendas_ampliado.md`.

## Escenario

Planta ficticia donde llegan cajas con prendas de ropa por una cinta transportadora. Las cajas grandes contienen varias **cajas individuales rígidas** (una prenda por caja pequeña: 1 camiseta, 1 pantalón, 1 par de zapatos, etc.). Los dos brazos robóticos GoFa son los encargados de manipular estas cajas individuales.

El PLC gestiona la cinta transportadora, seta de emergencia, modo de trabajo activo, alarmas y warnings. Algunas de estas señales se comunican con RobotStudio para el HMI.

## Pipeline de Visión

Al llegar la caja a la zona de trabajo, la **Cámara Águila** (cenital, RGB-D) detecta:
- Las esquinas de la caja grande.
- Las cajas individuales interiores, su tipo de prenda y su pose.

Con esta información, el sistema selecciona la caja con mayor confianza (en coordenadas y clasificación) y calcula puntos de aproximación para cada brazo sin colisión entre ellos.

Cada robot dispone de su propia **cámara eye-in-hand** (RGB-D) que, mediante **visual servoing**, decide cómo ejecutar el agarre preciso. La coordinación bimanual es necesaria para el transporte de las cajas.

## Modos de Operación

Desde el HMI el operario selecciona el **modo de operación activo**. Los cinco modos, de menor a mayor complejidad de IA, son:

1. **Vaciado Geométrico:** Despaletizado y separación de cajas (singulation).
2. **Clasificación Supervisada:** Sorteo por tipo de prenda (camiseta, pantalón, zapatos...).
3. **Reposición por Demanda Geográfica:** El sistema consulta el stock de un mercado específico (ERP simulado via JSON) y repone según necesidad.
4. **Tendencias de Mercado:** El sistema consulta qué es tendencia para un país/mercado, analiza fuentes de influencia (influencers, hashtags, eventos virales) y usa **CLIP** para hacer matching semántico entre las tendencias detectadas y las prendas del inventario.
5. **Gestión Integral:** Combinación de Modos 3 y 4. Optimización multiobjetivo: reponer el stock de un mercado priorizando las prendas que mejor encajan con la moda detectada allí.

## Capa de Investigación

El aporte investigador del TFM reside en los Modos 4 y 5:

- **Pipeline de análisis de tendencias:** Ingesta de menciones de influencers/eventos → extracción de *tags* de moda (ej. "oversize", "urbano", "retro") → vectorización con CLIP.
- **Matching semántico:** Texto de tendencia y imagen de prenda coexisten en el espacio vectorial de CLIP. La **distancia coseno** entre ambos vectores determina la probabilidad de que la prenda encaje con la tendencia del mercado objetivo.
- **Ejecución robótica:** El resultado del matching se traduce en coordenadas (X, Y, Z) para que los GoFa ejecuten el picking bimanual.

Esta arquitectura justifica el TFM como investigación porque cierra el bucle IT ↔ Middleware ↔ OT.
