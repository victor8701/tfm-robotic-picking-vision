"""Planificacion de una caja: tramos de la trayectoria que manda el PC por el puente.

Convencion: la herramienta mira hacia abajo cuando la orientacion es Q_BASE (igual que pStart en
RAPID). El giro de la caja (alrededor de z) gira la pinza; las mordazas cierran sobre el lado corto
(perpendicular al hilo, que va por el lado largo).

Deposito en la mesa: las cajas se dejan ordenadas en filas, todas sin girar (lado largo en x),
sea cual sea el giro con el que llegaron: la pinza gira en el aire durante el transporte. Las cajas pueden
medir distinto: se reparten en filas segun llegan (Reparto), desde la esquina de la mesa mas cercana al robot,
y cada caja entra deslizandose por el lado +x sobre sitios aun vacios, asi no pasa por encima de las ya dejadas
ni hace falta subir mas.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from nucleo.geometria import Pose, a_matriz, multiplicar, normalizar

from .config import LIMITE_X_MM, LIMITE_Y_MM, LIMITE_Z_MM
from .percepcion import Caja

Q_BASE = np.array([0.0, 0.0, 1.0, 0.0])  # herramienta hacia abajo (w, x, y, z)


def envolver_giro(grados: float) -> float:
    """Lleva un angulo a [-90, 90). La caja y la pinza son simetricas cada 180 grados."""
    return ((grados + 90.0) % 180.0) - 90.0


def orientacion_pinza(giro_caja_deg: float, eje_pinzado: str, giro_pinza_deg: float = 0.0) -> np.ndarray:
    """Orientacion de la herramienta con las mordazas perpendiculares al lado largo de la caja.

    eje_pinzado: eje local de la herramienta en el que cierran las mordazas ('x' o 'y'). Se
    confirma con el CAD de la pinza. giro_pinza_deg: giro extra de las mordazas (montaje de la pinza), que la
    app del FlexPendant ajusta como giroPinza; con eje 'y', 90 equivale a eje 'x'.
    """
    psi = (giro_caja_deg if eje_pinzado == "y" else giro_caja_deg + 90.0) + giro_pinza_deg
    psi = math.radians(envolver_giro(psi))
    q_giro = np.array([math.cos(psi / 2.0), 0.0, 0.0, math.sin(psi / 2.0)])
    return normalizar(multiplicar(q_giro, Q_BASE))


class NoAgarrable(ValueError):
    """La pinza no puede agarrar esta caja (muy baja o demasiado ancha para la apertura)."""


def altura_agarre(caja: Caja, cfg) -> float:
    """Altura h (mm) del punto de agarre sobre la base de la caja, y comprobacion de que la pinza puede cogerla.

    Modo 'porcentaje': h = alto * agarre_porcentaje / 100 (50 = el centro). Modo 'tapa': h = alto - agarre_hundimiento
    (los dedos cierran siempre a esa distancia bajo la tapa, que es lo que mejor mide una camara). Despues h no baja
    de agarre_minimo (los dedos sobresalen por debajo del TCP y no deben tocar la cinta ni la mesa) ni sube de alto.
    NoAgarrable si la caja es mas baja que solape_minimo, si agarre_minimo deja el punto por encima de la tapa o si
    el lado que cierran las mordazas (el ancho) no cabe en la apertura (apertura_pinza = 0: sin comprobar).
    """
    if caja.alto < cfg.solape_minimo:
        raise NoAgarrable(f"la caja mide {caja.alto:g} mm de alto y el dedo necesita tocar al menos "
                          f"{cfg.solape_minimo:g} mm de pared (solapeMinimo)")
    if cfg.apertura_pinza > 0.0 and caja.ancho > cfg.apertura_pinza:
        raise NoAgarrable(f"el lado que agarra la pinza mide {caja.ancho:g} mm y la pinza abre {cfg.apertura_pinza:g} mm "
                          "(aperturaPinza)")
    if cfg.agarre_modo == "tapa":
        h = caja.alto - cfg.agarre_hundimiento
    else:
        h = caja.alto * cfg.agarre_porcentaje / 100.0
    h = max(h, cfg.agarre_minimo)
    if h > caja.alto:
        raise NoAgarrable(f"el agarre mas bajo posible ({cfg.agarre_minimo:g} mm, agarreMinimo) queda por encima de la "
                          f"tapa de la caja ({caja.alto:g} mm)")
    return h


@dataclass(frozen=True)
class Tramo:
    nombre: str
    puntos: tuple[Pose, ...]
    accion_final: str | None  # 'cerrar' | 'abrir' | 'fin_caja' | None


def _pose(x: float, y: float, z: float, q: np.ndarray) -> Pose:
    return Pose.crear(t=(x, y, z), q=q)


@dataclass(frozen=True)
class Mesa:
    """Zona de la mesa donde se depositan las cajas (mm, en la base del robot).

    (x0, y0) es la esquina de x e y minimas; la zona se extiende largo en x y ancho en y. z es la
    superficie. hueco separa las cajas entre si y del borde de la zona (tiene que ser mayor que el grosor de
    las mordazas: la pinza entra entre dos cajas). Las pone la app del FlexPendant (PERS mesa* de RAPID)."""
    x0: float
    y0: float
    largo: float
    ancho: float
    z: float
    hueco: float


@dataclass(frozen=True)
class Destino:
    """Donde se deja una caja: centro, superficie de la mesa, x por la que se entra deslizando y altura de la
    caja mas alta ya dejada en la mesa (incluida esta), que fija hasta donde hay que subir al salir."""
    x: float
    y: float
    z_mesa: float
    x_entrada: float
    alto_libre: float = 0.0


class SinSitio(ValueError):
    """La caja no cabe en lo que queda de la zona de la mesa (o no queda nada a lo que el robot llegue)."""


# Paso (mm) con el que se busca el primer sitio utilizable cuando el sitio ideal queda fuera de alcance.
PASO_BUSQUEDA_MM = 10.0


class Reparto:
    """Reparte las cajas por la mesa segun llegan, con medidas distintas, en filas a lo largo de x.

    Cada fila va pegada a la anterior (mas lejos del robot, hacia +y) y se llena de x menor a mayor, es decir, de la
    x mas lejana a la entrada hacia la mas cercana, dejando `hueco` entre cajas y con el borde de la zona. Una fila
    mide lo que la caja mas ancha que lleva; cada caja va pegada al borde cercano de su fila. Si un sitio queda fuera
    del espacio del puente, del limite del EGM o del alcance, se salta y se busca el primero utilizable. Una caja se
    coloca antes de moverla (con sus medidas ya conocidas); si no cabe, SinSitio y el reparto no cambia."""

    def __init__(self, mesa: Mesa):
        self.mesa = mesa
        self._fila_y = mesa.y0 + mesa.hueco   # borde cercano de la fila en curso
        self._fondo = 0.0                     # lo ancha (en y) que es ya la fila en curso
        self._cursor = mesa.x0 + mesa.hueco   # donde empieza la siguiente caja de la fila
        self._alto_max = 0.0
        self.colocadas = 0

    def copia(self) -> "Reparto":
        otro = Reparto(self.mesa)
        otro._fila_y, otro._fondo, otro._cursor = self._fila_y, self._fondo, self._cursor
        otro._alto_max, otro.colocadas = self._alto_max, self.colocadas
        return otro

    def colocar(self, caja: Caja, cfg) -> Destino:
        m = self.mesa
        x_borde = m.x0 + m.largo - m.hueco
        y_borde = m.y0 + m.ancho - m.hueco
        entrada = m.x0 + m.largo + caja.largo / 2.0 + m.hueco   # la caja entera fuera de la zona, por +x
        alto_libre = max(self._alto_max, caja.alto)
        fila_y, fondo, cursor = self._fila_y, self._fondo, self._cursor
        while fila_y + caja.ancho <= y_borde + 1e-6:
            x = cursor
            while x + caja.largo <= x_borde + 1e-6:
                xc = x + caja.largo / 2.0
                d = Destino(x=xc, y=fila_y + caja.ancho / 2.0, z_mesa=m.z, x_entrada=max(entrada, xc), alto_libre=alto_libre)
                if _alcanzable(caja, cfg, d):
                    self._fila_y, self._fondo = fila_y, max(fondo, caja.ancho)
                    self._cursor = x + caja.largo + m.hueco
                    self._alto_max = alto_libre
                    self.colocadas += 1
                    return d
                x += PASO_BUSQUEDA_MM
            if fondo > 0.0:
                fila_y += fondo + m.hueco   # fila siguiente, pegada a la anterior
                fondo = 0.0
            else:
                fila_y += PASO_BUSQUEDA_MM  # nada utilizable en esta fila: se prueba un poco mas lejos
            cursor = m.x0 + m.hueco
        raise SinSitio(f"no hay sitio en la mesa para una caja de {caja.largo:g} x {caja.ancho:g} x {caja.alto:g} mm "
                       f"(llevan {self.colocadas} cajas; zona de {m.largo:g} x {m.ancho:g} mm, hueco {m.hueco:g} mm)")


def _poses_destino(caja: Caja, cfg, d: Destino) -> dict:
    """Puntos de un destino: entrada (deslizando desde +x), sobre el hueco, deposito y salida."""
    q = orientacion_pinza(0.0, cfg.eje_pinzado, cfg.giro_pinza)   # caja alineada con la mesa, venga como venga
    h = altura_agarre(caja, cfg)
    z_deposito = d.z_mesa + h
    z_viaje = max(cfg.z_cinta + caja.alto + cfg.margen_aproximacion, z_deposito + cfg.margen_aproximacion)
    z_salida = max(cfg.z_seguro, d.z_mesa + max(caja.alto, d.alto_libre) + cfg.margen_aproximacion)
    return {
        "q": q, "z_viaje": z_viaje,
        "entrada": _pose(d.x_entrada, d.y, z_viaje, q),
        "sobre": _pose(d.x, d.y, z_viaje, q),
        "deposito": _pose(d.x, d.y, z_deposito, q),
        "salida": _pose(d.x, d.y, z_salida, q),
    }


def _alcanzable(caja: Caja, cfg, d: Destino) -> bool:
    """El robot puede ir al destino: espacio del puente, limite del EGM y alcance en sus cuatro puntos."""
    p = _poses_destino(caja, cfg, d)
    try:
        validar_puntos([Tramo("destino", (p["entrada"], p["sobre"], p["deposito"], p["salida"]), None)], cfg)
    except ValueError:
        return False
    return True


def planificar(caja: Caja, cfg, destino: Destino | None = None) -> list[Tramo]:
    """Tres tramos por caja: aproximacion y agarre, transporte y deposito, salida.

    Alturas: la caja descansa en la cinta a z_cinta. El agarre es a la altura h sobre su base (altura_agarre: el
    centro con la configuracion por defecto). Sobre la caja hay un margen de aproximacion.

    La salida sube hasta dejar la pinza por encima de la caja ya depositada (techo de la caja mas el
    margen), no solo hasta z_seguro: el TCP agarra a media altura, y con la mesa mas alta que la cinta
    z_seguro quedaba por debajo del techo de la caja (65 mm sobre el centro, techo a 100 mm).
    """
    xc, yc = caja.centro if caja.centro is not None else cfg.centro_recogida
    xm, ym = cfg.mesa
    q = orientacion_pinza(caja.giro_deg, cfg.eje_pinzado, cfg.giro_pinza)
    h = altura_agarre(caja, cfg)
    z_agarre = cfg.z_cinta + h
    z_aprox = cfg.z_cinta + caja.alto + cfg.margen_aproximacion
    z_deposito = cfg.z_mesa + h
    z_seg = cfg.z_seguro
    z_salida = max(z_seg, cfg.z_mesa + caja.alto + cfg.margen_aproximacion)
    if destino is not None:
        return _planificar_en_mesa(caja, cfg, destino, (xc, yc), q, z_agarre, z_aprox)
    return [
        Tramo("aproximacion",
              (_pose(xc, yc, z_seg, q), _pose(xc, yc, z_aprox, q), _pose(xc, yc, z_agarre, q)),
              "cerrar"),
        Tramo("transporte",
              tuple([_pose(xc, yc, z_aprox, q)]
                    + ([_pose(cfg.via_transporte[0], cfg.via_transporte[1], z_aprox, q)]
                       if cfg.via_transporte is not None else [])
                    + [_pose(xm, ym, z_aprox, q), _pose(xm, ym, z_deposito, q)]),
              "abrir"),
        Tramo("salida", (_pose(xm, ym, z_salida, q),), "fin_caja"),
    ]


def _planificar_en_mesa(caja, cfg, destino, centro, q, z_agarre, z_aprox) -> list[Tramo]:
    """Los tres tramos con el deposito en un sitio de la mesa (ver el principio del modulo).

    Transporte: sube sobre la recogida, va a la via y a la entrada del hueco ya con la pinza girada para dejar la
    caja alineada con la mesa, se desliza por -x hasta quedar sobre el hueco y baja. Todo el viaje va a la altura
    de aproximacion (sin subir mas, que a mas altura el brazo no llega al fondo de la mesa). Salida: sube
    en vertical hasta dejar la pinza por encima de las cajas ya dejadas y avisa del fin de la caja."""
    xc, yc = centro
    p = _poses_destino(caja, cfg, destino)
    camino = [_pose(xc, yc, z_aprox, q)]
    if p["z_viaje"] > z_aprox:
        camino.append(_pose(xc, yc, p["z_viaje"], q))
    if cfg.via_transporte is not None:
        camino.append(_pose(cfg.via_transporte[0], cfg.via_transporte[1], p["z_viaje"], p["q"]))
    camino += [p["entrada"], p["sobre"], p["deposito"]]
    unicos = [camino[0]]
    for punto in camino[1:]:   # sin puntos repetidos (la entrada puede coincidir con el hueco)
        if not np.allclose(punto.t, unicos[-1].t, atol=1e-6):
            unicos.append(punto)
    return [
        Tramo("aproximacion",
              (_pose(xc, yc, cfg.z_seguro, q), _pose(xc, yc, z_aprox, q), _pose(xc, yc, z_agarre, q)),
              "cerrar"),
        Tramo("transporte", tuple(unicos), "abrir"),
        Tramo("salida", (p["salida"],), "fin_caja"),
    ]


def a_brida(punto: Pose, largo_herramienta_mm: float) -> Pose:
    """Pose de la brida (tool0) que pone el TCP de la pinza en 'punto'.

    EGM controla la brida, no el TCP: EGMActPose recibe pose_cero como herramienta. El TCP de
    herrPinza esta largo_herramienta_mm por delante de la brida, en el eje z de la herramienta. Con
    la pinza hacia abajo, la brida queda largo_herramienta_mm por encima del TCP.
    """
    eje = a_matriz(punto.q) @ np.array([0.0, 0.0, largo_herramienta_mm])
    return Pose(punto.t - eje, punto.q)


def validar_puntos(tramos: list[Tramo], cfg) -> None:
    """Comprueba los puntos antes de mover nada: espacio del puente y ventana EGM.

    El espacio del puente se mide en brida, que es lo que recibe. La ventana EGM se mide en TCP: la
    pinza mira siempre hacia abajo y pSeguro tiene el mismo desfase, asi que las distancias coinciden.
    """
    x0, y0, z0 = cfg.ventana_inicio
    # Suelo del TCP: ningun punto legitimo baja de la menor de las dos superficies (el agarre y el deposito estan a h > 0
    # sobre ellas). Protege si una altura esta mal medida.
    suelo = max(cfg.z_minima, min(cfg.z_cinta, cfg.z_mesa))
    for tramo in tramos:
        for p in tramo.puntos:
            x, y, z = (float(v) for v in p.t)
            if z < suelo - 1e-6:
                raise ValueError(f"{tramo.nombre}: punto {p.t.round(1).tolist()} por debajo del suelo del TCP "
                                 f"({suelo:g} mm: zMinima, zCinta o mesaZ)")
            xb, yb, zb = (float(v) for v in a_brida(p, cfg.largo_herramienta_mm).t)
            if not (LIMITE_X_MM[0] <= xb <= LIMITE_X_MM[1] and LIMITE_Y_MM[0] <= yb <= LIMITE_Y_MM[1]
                    and LIMITE_Z_MM[0] <= zb <= LIMITE_Z_MM[1]):
                raise ValueError(f"{tramo.nombre}: la brida {np.round([xb, yb, zb], 1).tolist()} "
                                 f"(TCP {p.t.round(1).tolist()}) queda fuera del espacio del puente")
            if (abs(x - x0) > cfg.ventana_semiancho or abs(y - y0) > cfg.ventana_semiancho
                    or abs(z - z0) > cfg.ventana_semiancho):
                raise ValueError(f"{tramo.nombre}: punto {p.t.round(1).tolist()} fuera de la ventana EGM")
            # El controlador para el EGM (Motors Off) si la referencia se aleja mas de MaxPosDeviation de la pose
            # con la que empezo la sesion: se comprueba aqui, antes de mover nada.
            lejos = math.dist((x, y, z), (x0, y0, z0))
            if lejos > cfg.desviacion_egm_max - 1.0:
                raise ValueError(f"{tramo.nombre}: punto {p.t.round(1).tolist()} a {lejos:.0f} mm del inicio del EGM "
                                 f"(maximo {cfg.desviacion_egm_max:.0f}, egmMaxPos de MOD_CajaPinza)")
            if math.hypot(x, y) > cfg.alcance_max:
                raise ValueError(f"{tramo.nombre}: punto {p.t.round(1).tolist()} a {math.hypot(x, y):.0f} mm del eje "
                                 f"del robot (alcance maximo {cfg.alcance_max:.0f}, alcanceMax de MOD_CajaPinza)")
