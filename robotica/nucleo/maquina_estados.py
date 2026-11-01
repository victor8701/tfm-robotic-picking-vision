"""Máquina de estados del ciclo de agarre de la caja.

Reglas de seguridad:
- Un evento inesperado durante un paso activo lleva a FALLO.
- PARADA puede llegar desde cualquier estado y lleva a PARADA_SEGURA.
- FALLO y PARADA_SEGURA no se mueven hasta recibir RESET, que vuelve a REPOSO.
- Los eventos que no tienen sentido en reposo (o en FIN) se ignoran y se cuentan.
"""
from __future__ import annotations

from enum import Enum


class Estado(Enum):
    REPOSO = "reposo"
    BUSCAR_CAJA = "buscar_caja"
    APROXIMAR = "aproximar"
    SERVOING = "servoing"
    AGARRAR = "agarrar"
    VERIFICAR_AGARRE = "verificar_agarre"
    LEVANTAR = "levantar"
    TRANSPORTAR = "transportar"
    DEPOSITAR = "depositar"
    RETIRAR = "retirar"
    FIN = "fin"
    FALLO = "fallo"
    PARADA_SEGURA = "parada_segura"


class Evento(Enum):
    INICIAR = "iniciar"
    CAJA_VISTA = "caja_vista"
    LLEGADA_APROX = "llegada_aprox"
    CONVERGE = "converge"
    AGARRE_HECHO = "agarre_hecho"
    VERIFICADO = "verificado"
    LEVANTADO = "levantado"
    LLEGADA_B = "llegada_b"
    SOLTADO = "soltado"
    RETIRADO = "retirado"
    ERROR = "error"
    PARADA = "parada"
    RESET = "reset"


_TRANSICIONES = {
    (Estado.REPOSO, Evento.INICIAR): Estado.BUSCAR_CAJA,
    (Estado.BUSCAR_CAJA, Evento.CAJA_VISTA): Estado.APROXIMAR,
    (Estado.APROXIMAR, Evento.LLEGADA_APROX): Estado.SERVOING,
    (Estado.SERVOING, Evento.CONVERGE): Estado.AGARRAR,
    (Estado.AGARRAR, Evento.AGARRE_HECHO): Estado.VERIFICAR_AGARRE,
    (Estado.VERIFICAR_AGARRE, Evento.VERIFICADO): Estado.LEVANTAR,
    (Estado.LEVANTAR, Evento.LEVANTADO): Estado.TRANSPORTAR,
    (Estado.TRANSPORTAR, Evento.LLEGADA_B): Estado.DEPOSITAR,
    (Estado.DEPOSITAR, Evento.SOLTADO): Estado.RETIRAR,
    (Estado.RETIRAR, Evento.RETIRADO): Estado.FIN,
}

_ACTIVOS = {
    Estado.BUSCAR_CAJA, Estado.APROXIMAR, Estado.SERVOING, Estado.AGARRAR,
    Estado.VERIFICAR_AGARRE, Estado.LEVANTAR, Estado.TRANSPORTAR, Estado.DEPOSITAR,
    Estado.RETIRAR,
}
_SUMIDEROS = {Estado.FALLO, Estado.PARADA_SEGURA}
_REARMABLES = {Estado.FALLO, Estado.PARADA_SEGURA, Estado.FIN}


class MaquinaEstados:
    def __init__(self):
        self.estado = Estado.REPOSO
        self.historial: list[Estado] = [Estado.REPOSO]
        self.ignorados = 0

    def enviar(self, evento: Evento) -> Estado:
        previo = self.estado
        if evento is Evento.PARADA and previo is not Estado.PARADA_SEGURA:
            nuevo = Estado.PARADA_SEGURA
        elif evento is Evento.RESET:
            nuevo = Estado.REPOSO if previo in _REARMABLES else previo
        elif previo in _SUMIDEROS:
            nuevo = previo
            self.ignorados += 1
        elif evento is Evento.ERROR and previo in _ACTIVOS:
            nuevo = Estado.FALLO
        else:
            nuevo = _TRANSICIONES.get((previo, evento))
            if nuevo is None:
                if previo in _ACTIVOS:
                    nuevo = Estado.FALLO
                else:
                    nuevo = previo
                    self.ignorados += 1
        self.estado = nuevo
        if nuevo is not previo:
            self.historial.append(nuevo)
        return nuevo
