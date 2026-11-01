from nucleo.maquina_estados import Estado, Evento, MaquinaEstados

CAMINO_FELIZ = [
    Evento.INICIAR, Evento.CAJA_VISTA, Evento.LLEGADA_APROX, Evento.CONVERGE,
    Evento.AGARRE_HECHO, Evento.VERIFICADO, Evento.LEVANTADO, Evento.LLEGADA_B,
    Evento.SOLTADO, Evento.RETIRADO,
]


def _en_servoing():
    m = MaquinaEstados()
    for e in (Evento.INICIAR, Evento.CAJA_VISTA, Evento.LLEGADA_APROX):
        m.enviar(e)
    assert m.estado is Estado.SERVOING
    return m


def test_camino_feliz_llega_a_fin_y_se_rearma():
    m = MaquinaEstados()
    for e in CAMINO_FELIZ:
        m.enviar(e)
    assert m.estado is Estado.FIN
    m.enviar(Evento.RESET)
    assert m.estado is Estado.REPOSO


def test_evento_inesperado_en_marcha_es_fallo():
    m = _en_servoing()
    assert m.enviar(Evento.SOLTADO) is Estado.FALLO


def test_parada_desde_cualquier_estado_activo():
    m = _en_servoing()
    assert m.enviar(Evento.PARADA) is Estado.PARADA_SEGURA


def test_fallo_no_se_mueve_sin_rearme():
    m = _en_servoing()
    m.enviar(Evento.ERROR)
    assert m.estado is Estado.FALLO
    assert m.enviar(Evento.INICIAR) is Estado.FALLO
    assert m.ignorados == 1


def test_reset_desde_fallo_y_desde_parada():
    m = _en_servoing()
    m.enviar(Evento.ERROR)
    assert m.enviar(Evento.RESET) is Estado.REPOSO
    m.enviar(Evento.INICIAR)
    m.enviar(Evento.PARADA)
    assert m.enviar(Evento.RESET) is Estado.REPOSO


def test_error_en_reposo_se_ignora():
    m = MaquinaEstados()
    assert m.enviar(Evento.ERROR) is Estado.REPOSO
    assert m.ignorados == 1


def test_historial_registra_solo_los_cambios():
    m = MaquinaEstados()
    m.enviar(Evento.INICIAR)
    m.enviar(Evento.ERROR)
    assert m.historial == [Estado.REPOSO, Estado.BUSCAR_CAJA, Estado.FALLO]
