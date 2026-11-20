"""Ciclo de la celda: el PC lleva cada caja por EGM a traves del puente y coordina la pinza con
RAPID por socket.

Uso (con el puente en marcha, primero el PC y despues RAPID):
    cd robotica
    python -m celda.ciclo celda/config_celda.json

El avance entre puntos se decide por posicion (tolerancias), nunca por tiempo. El periodo solo
marca el ritmo de envio del objetivo, que el puente necesita al menos cada 0,1 s.
"""
from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

_RAIZ = Path(__file__).resolve().parents[1]  # robotica/
sys.path.insert(0, str(_RAIZ))  # paquete nucleo
sys.path.insert(0, str(_RAIZ / "ros2" / "robotica_bimanual"))  # ClientePuente, sin rclpy

from nucleo.geometria import error_pose  # noqa: E402
from robotica_bimanual.cliente_puente import ClientePuente  # noqa: E402
from robotica_bimanual.convertir import pose_desde_estado_puente  # noqa: E402

from .config import Config, cargar  # noqa: E402
from .percepcion import crear_fuente  # noqa: E402
from .planificacion import Mesa, Reparto, SinSitio, Tramo, a_brida, planificar, validar_puntos  # noqa: E402
from .socket_rapid import ServidorRapid  # noqa: E402


class Celda:
    # Espera maxima a las respuestas de RAPID a lote y giro. Contestan al instante: si no llega nada, el
    # modulo de RAPID es una version sin esos mensajes.
    ESPERA_PREGUNTA_S = 5.0
    # Sin datagramas del robot durante tanto tiempo, el EGM esta parado (ABORTAR de la app, Stop en RAPID...): se
    # deja de mandar objetivos en vez de esperar a que se agoten las iteraciones.
    ESPERA_EGM_PARADO_S = 3.0
    # Respuesta de RAPID a cerrar, abrir y fin_caja (la mas larga, fin_caja, tarda como mucho tiempoConv + 10 s).
    ESPERA_RESPUESTA_S = 40.0

    def __init__(self, cfg: Config, fuente, puente, rapid: ServidorRapid):
        self.cfg = cfg
        self.fuente = fuente
        self.puente = puente
        self.rapid = rapid
        self._n_rapid: int | None = None  # cajas de la tanda segun RAPID (la app del FlexPendant), tras 'lote'
        self._mesa: Mesa | None = None    # zona de deposito segun RAPID (la app), tras 'mesa'
        self._reparto: Reparto | None = None   # donde va cada caja en la mesa (cajas de medidas distintas)

    def ejecutar(self) -> None:
        i = 0
        while True:
            self._caja(i)
            i += 1
            if i >= self._total_cajas():
                break
        self.rapid.enviar("fin_programa")

    def _total_cajas(self) -> int:
        """Cajas de la tanda. La cuenta la lleva RAPID (la ajusta la app del FlexPendant): se pregunta con
        'lote' al empezar la primera caja. En simulacion, ademas, RAPID escribe caja.csv con una linea por
        caja y las dos cuentas deben coincidir. Hay que llamarlo despues de empezar la primera caja:
        antes, RAPID puede no haber escrito aun el fichero."""
        total = getattr(self.fuente, "total", lambda: None)()
        if self._n_rapid is None:
            return int(total) if total is not None else self.cfg.n_cajas
        if total is not None and int(total) != self._n_rapid:
            raise RuntimeError(f"caja.csv tiene {int(total)} cajas y RAPID va a hacer {self._n_rapid}: "
                               "el fichero no es de esta tanda")
        return self._n_rapid

    def _preguntar(self, mensaje: str) -> str:
        self.rapid.enviar(mensaje)
        try:
            return self.rapid.recibir(self.ESPERA_PREGUNTA_S)
        except TimeoutError as e:
            raise RuntimeError(f"RAPID no contesta a '{mensaje.split(':')[0]}': ¿es un MOD_CajaPinza antiguo, "
                               "sin ese mensaje? Carga el modulo actual en T_ROB1 y T_COM") from e

    def _sincronizar_lote(self) -> None:
        """Pregunta a RAPID cuantas cajas tiene la tanda y en que modo esta (los ajusta la app del
        FlexPendant): asi el PC no puede discrepar ni en la cuenta ni en el modo."""
        r = self._preguntar("lote")
        partes = r.split(":")
        if len(partes) != 3 or partes[0] != "lote" or partes[2] not in ("sim", "real") or not partes[1].isdigit():
            raise RuntimeError(f"RAPID respondio {r!r} a 'lote' (se esperaba lote:<n>:<sim|real>)")
        if (partes[2] == "sim") != self.cfg.modo_simulacion:
            raise RuntimeError(
                "RAPID esta en modo " + ("simulacion" if partes[2] == "sim" else "real") + " y el PC en "
                + ("simulacion" if self.cfg.modo_simulacion else "real")
                + " (modo_simulacion de la configuracion): cambia uno de los dos")
        self._n_rapid = int(partes[1])
        if self._n_rapid < 1:
            raise RuntimeError("RAPID dice que la tanda tiene 0 cajas")
        self._leer_mesa()

    def _leer_mesa(self) -> None:
        """Pide a RAPID la zona de la mesa donde se dejan las cajas y los limites del robot (los pone la app del
        FlexPendant; los limites son PERS de MOD_CajaPinza.mod). El limite del EGM y el alcance se aplican a todos
        los puntos que se manden; la ventana por eje se deriva del limite (100 mm menos, como en la configuracion)."""
        r = self._preguntar("mesa")
        partes = r.split(":")
        esperado = "mesa:<x0>:<y0>:<largo>:<ancho>:<z>:<hueco>:<egmMaxPos>:<alcanceMax>"
        if len(partes) != 9 or partes[0] != "mesa":
            raise RuntimeError(f"RAPID respondio {r!r} a 'mesa' (se esperaba {esperado})")
        try:
            x0, y0, largo, ancho, z, hueco, egm_max, alcance = (float(v) for v in partes[1:])
        except ValueError:
            raise RuntimeError(f"RAPID respondio {r!r} a 'mesa' (se esperaba {esperado})") from None
        if largo <= 0.0 or ancho <= 0.0 or hueco < 0.0 or egm_max <= 100.0 or alcance <= 0.0:
            raise RuntimeError(f"Medidas de la mesa no validas en RAPID: {r!r}")
        self._mesa = Mesa(x0, y0, largo, ancho, z, hueco)
        self.cfg = replace(self.cfg, desviacion_egm_max=egm_max, alcance_max=alcance, ventana_semiancho=egm_max - 100.0)

    def _preparar_mesa(self) -> None:
        """Empieza el reparto de la mesa. Si se conocen todas las cajas de antemano (caja.csv de la simulacion), se
        comprueba la tanda entera antes de mover nada: si alguna no cabe, se para aqui con el motivo. Con camara
        las medidas llegan caja a caja y se comprueba cada una antes de moverla."""
        self._reparto = Reparto(self._mesa)
        total_conocido = getattr(self.fuente, "total", lambda: None)()
        if total_conocido is None:
            return
        prueba = Reparto(self._mesa)
        for j in range(int(total_conocido)):
            try:
                prueba.colocar(self.fuente.leer(j), self.cfg)
            except SinSitio as e:
                raise RuntimeError(f"La caja {j + 1} de {int(total_conocido)} no cabe en la mesa: {e}. Agranda la zona, "
                                   "reduce el hueco, sube el limite del EGM o baja el numero de cajas.") from None

    def _avisar_giro(self, caja) -> None:
        """Cuenta a RAPID el giro de la caja que ha leido el PC; la app lo muestra junto al que puso RAPID."""
        r = self._preguntar(f"giro:{caja.giro_deg:.1f}")
        if r != "giro_ok":
            raise RuntimeError(f"RAPID respondio {r!r} al giro, se esperaba 'giro_ok'")

    def _caja(self, i: int) -> None:
        self._esperar_arranque_egm()
        if i == 0:
            self._sincronizar_lote()
        caja = self.fuente.leer(i)
        if i == 0:
            self._preparar_mesa()
        try:
            destino = self._reparto.colocar(caja, self.cfg)
        except SinSitio as e:
            raise RuntimeError(f"La caja {i + 1} no cabe en la mesa: {e}") from None
        print(f"Celda: caja {i + 1} de {self._total_cajas()} ({caja.largo:g} x {caja.ancho:g} x {caja.alto:g} mm, "
              f"giro {caja.giro_deg:g} grados) -> mesa ({destino.x:.0f}, {destino.y:.0f})")
        self._avisar_giro(caja)
        tramos = planificar(caja, self.cfg, destino)
        validar_puntos(tramos, self.cfg)
        for tramo in tramos:
            self._seguir(tramo)
            if tramo.accion_final == "cerrar":
                self._pedir("cerrar", "cerrada")
            elif tramo.accion_final == "abrir":
                self._pedir("abrir", "abierta")
            elif tramo.accion_final == "fin_caja":
                # RAPID espera a que el EGM termine (el robot queda convergido en la salida unos
                # segundos, sin que el PC haga nada) y contesta fin_ok: sin esa respuesta, la
                # siguiente orden podria llegar pegada a esta en el socket.
                self._pedir("fin_caja", "fin_ok")

    def _esperar_arranque_egm(self) -> dict:
        """Espera a que RAPID arranque la sesion EGM de la caja: los datagramas aumentan."""
        base = None
        while True:
            e = self.puente.estado()
            if e.get("estado") == "fallo":
                raise RuntimeError(f"puente en fallo antes de la caja: {e.get('codigo')}")
            ciclos = int(e.get("ciclos", 0))
            if base is None:
                base = ciclos
            elif ciclos > base + 5:
                return e
            time.sleep(self.cfg.periodo_s)

    def _seguir(self, tramo: Tramo) -> None:
        """Lleva el robot por cada punto del tramo. Avanza cuando la brida real esta dentro de tolerancia.

        Los puntos del planificador son del TCP de la pinza, pero EGM y el puente trabajan con la
        brida. Por eso el objetivo se convierte antes de enviarlo y de medir el error.
        """
        ciclos_vistos, desde = None, time.monotonic()
        for punto in tramo.puntos:
            objetivo = a_brida(punto, self.cfg.largo_herramienta_mm)
            for _ in range(self.cfg.max_iteraciones):
                e = self.puente.estado()
                if e.get("estado") == "fallo":
                    raise RuntimeError(f"{tramo.nombre}: puente en fallo: {e.get('codigo')}")
                ciclos = int(e.get("ciclos", 0))
                if ciclos != ciclos_vistos:
                    ciclos_vistos, desde = ciclos, time.monotonic()
                elif time.monotonic() - desde > self.ESPERA_EGM_PARADO_S:
                    raise RuntimeError(f"{tramo.nombre}: el robot ha dejado de enviar datagramas EGM hace "
                                       f"{time.monotonic() - desde:.0f} s: ¿tanda abortada o programa parado en RAPID?")
                real = pose_desde_estado_puente(e["real"])
                dt, dr = error_pose(real, objetivo)
                if np.linalg.norm(dt) <= self.cfg.tolerancia_pos and np.linalg.norm(dr) <= self.cfg.tolerancia_rot:
                    break
                r = self.puente.objetivo(objetivo)
                if not r.get("ok"):
                    raise RuntimeError(
                        f"{tramo.nombre}: el puente rechaza la brida {objetivo.t.round(1).tolist()}: {r}")
                time.sleep(self.cfg.periodo_s)
            else:
                raise RuntimeError(f"{tramo.nombre}: no llega al punto {punto.t.round(1).tolist()}")

    def _pedir(self, orden: str, esperada: str) -> None:
        t0 = time.monotonic()
        self.rapid.enviar(orden)
        try:
            r = self.rapid.recibir(self.ESPERA_RESPUESTA_S)
        except TimeoutError:
            raise RuntimeError(f"RAPID no ha contestado a '{orden}' en {self.ESPERA_RESPUESTA_S:g} s: "
                               "¿tanda abortada o programa parado?") from None
        if r in ("fallo_pinza", "fallo_egm"):
            if r == "fallo_egm":
                motivo = "T_ROB1 no paro el EGM"
            elif orden == "abrir":
                motivo = "la pinza no confirmo la apertura: PinzaCerrada no bajo a 0"
            else:
                motivo = "la pinza no confirmo el agarre: PinzaCerrada no subio a 1"
            raise RuntimeError(f"RAPID: {r} ({motivo}) al ejecutar '{orden}'")
        if r != esperada:
            raise RuntimeError(f"RAPID respondio '{r}' a '{orden}', se esperaba '{esperada}'")
        if orden in ("cerrar", "abrir"):
            # Asi se ve en la consola del PC que la orden salio y que RAPID la confirmo (la senal PinzaCerrada cambio).
            print(f"Pinza: {orden} -> {r} ({time.monotonic() - t0:.1f} s)")


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("uso: python -m celda.ciclo celda/config_celda.json")
        return
    cfg = cargar(argv[1])
    fuente = crear_fuente(cfg)
    puente = ClientePuente(cfg.puente_host, cfg.puente_puerto, timeout_s=2.0)
    rapid = ServidorRapid(cfg.rapid_ip, cfg.rapid_puerto, cfg.rapid_espera_s)
    print(f"Esperando a RAPID en {cfg.rapid_ip}:{cfg.rapid_puerto}...")
    try:
        rapid.esperar_cliente()
        Celda(cfg, fuente, puente, rapid).ejecutar()
        print("Celda: todas las cajas recogidas.")
    finally:
        rapid.cerrar()
        puente.cerrar()


if __name__ == "__main__":
    main(sys.argv)
