# Guion: visita 1 al laboratorio

Primero solo lectura y medidas. Ningún movimiento del robot hasta haber pasado el guion del controlador virtual
([guion_virtual.md](guion_virtual.md)) y con el paro físico al alcance. Anotar todo en `memoria/` o en `docs/ESTADO.md`.

## A. Controlador y licencias (solo lectura)

- [ ] Versión de RobotWare del OmniCore del laboratorio. Debe coincidir con la del controlador virtual (§9 del mapa).
- [ ] Opción EGM 689-1 instalada (ver la lista de opciones del controlador).
- [ ] Opción de MultiMove, solo si los dos brazos van en un controlador (D11).
- [ ] Modelo exacto del GoFa (placa o ficha): carga y **alcance**.
- [ ] Dirección IP del OmniCore. Prueba de alcance desde el PC del puente (ping), sin mover nada.
- [ ] Puerto UDP que se va a usar, libre en el PC y permitido por el firewall de Windows.

## B. Mesa y celda (medidas)

- [ ] Dimensiones de la mesa de chapa y posición de las dos bases (para el alcance conjunto, §6 del mapa).
- [ ] Zona de recogida (marcas rojas) y palet de depósito: posición en la mesa.
- [ ] Planitud de la chapa: medir la altura en varios puntos, porque la homografía solo vale para un plano.
- [ ] Caja grande: dimensiones interiores y altura de pared (propuesta 70 × 65 cm y 20 cm). Medir la caja real.
- [ ] Cajas de zapatos: medir 3 cajas reales (dimensiones y peso vacía y llena).
- [ ] Mano: si no hay CAD, medir apertura, grosor de dedos y distancia de la palma (§7 del mapa).

## C. Cámara (RealSense)

- [ ] Montar la RealSense en el soporte de la webcam, al mismo punto y altura (D17).
- [ ] Modelo y número de serie. Resolución de color y de profundidad (D15).
- [ ] Error de profundidad sobre tabla plana a 0,5, 1 y 1,5 m. Anotar la media y la desviación.
- [ ] Campo de visión real: con un tablero de referencia, medir qué parte de la caja cabe en la imagen desde la altura de trabajo.
      **Clave:** comprobar si la caja entra en la imagen en la pose de agarre (ver riesgos en docs/ESTADO.md).
- [ ] Capturas con la caja vacía y llena, con distintas luces (dataset propio, F3).

## D. Calibración

- [ ] Homografía de la mesa: al menos 6 puntos marcados (4 para ajustar y 2 para validar), a la altura del borde de la caja. La homografía del curso (4 puntos) no sirve.
- [ ] Mano-ojo de la cámara de muñeca: al menos 10 poses con un tablero visible en cada una. Guardar poses del robot y del tablero para `calibracion.calibrar_mano_ojo`.
- [ ] Prueba de consistencia: dos TCP sobre el mismo punto (§8 del mapa).
- [ ] Procesar los datos con la línea de comandos (desde `robotica/`):
      `python3 -m calibracion.cli homografia datos_mesa.json resultado_mesa.json`
      `python3 -m calibracion.cli mano_ojo datos_mano.json resultado_mano.json`
      Formato de los JSON en la cabecera de `calibracion/cli.py`. Código de salida 1 = repetir la homografía.

## E. Lo que se anota al final

| Punto | Valor medido | Fecha | Quién |
|---|---|---|---|
| Versión RobotWare | | | |
| EGM 689-1 | sí / no | | |
| Alcance del GoFa | | | |
| Mesa (largo × ancho) | | | |
| Caja grande interior | | | |
| Error de profundidad a 1 m | | | |
| La caja entra en la imagen en el agarre | sí / no | | |
| Homografía: RMS de validación | | | |
