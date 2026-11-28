"""Detección de las cajas en una imagen cenital y medida de cada una en la base del robot.

Para cada caja da el centro (x, y), el giro del lado largo, el largo, el ancho y el alto: lo que lee el PC de la celda
(`celda.percepcion.Caja`). La imagen sola no basta: hace falta el modelo de la cámara (`vision.camara.ModeloCamara`, de
`calibracion.camara`) y el alto de la caja, que sale de la profundidad (RealSense) o se da a mano.

Tres formas de separar la caja del resto, según `params["modo"]`:
- "color": rango HSV del cartón (se ajusta con `vision.probar_en_casa --interactivo`).
- "fondo": diferencia con una foto de la misma escena sin cajas. No depende del color de la caja.
- "profundidad": píxeles que están a más de `altura_min_mm` sobre el plano de la cinta. No depende del color ni de la luz y
  mide el alto de cada caja; necesita un mapa de profundidad alineado con la imagen.

Con la máscara, el contorno se pasa al plano horizontal de la tapa (z = plano + alto) y allí se ajusta el rectángulo de menor
área: así la perspectiva queda corregida y el largo, el ancho y el giro salen en mm. Limitación: la silueta incluye la pared de la
caja que ve la cámara (hasta unos mm si la caja no está justo bajo ella); con profundidad se evita porque solo cuenta la tapa.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

import cv2
import numpy as np

from vision.camara import ModeloCamara

PARAMS_POR_DEFECTO = {
    "modo": "color",                      # "color" | "fondo" | "profundidad"
    "hsv_bajo": (10, 65, 60),             # HSV de OpenCV (H 0..180): cartón marrón o beige
    "hsv_alto": (30, 255, 255),
    "umbral_fondo": 30,                   # modo fondo: diferencia mínima (0..255) con la foto sin cajas
    "altura_min_mm": 15.0,                # modo profundidad: por encima del plano de la cinta...
    "altura_max_mm": 600.0,               # ...y por debajo de esta altura
    "area_min_px": 1500.0,                # contornos más pequeños son ruido
    "lado_min_mm": 20.0,                  # rectángulos con un lado menor que esto no son cajas
    "cuadrada_tol": 0.05,                 # si largo y ancho difieren menos de esta fracción, el giro va en [-45, 45)
    "apertura_px": 5,                     # limpieza de la máscara
    "cierre_px": 15,
}


def _params(params) -> dict:
    return {**PARAMS_POR_DEFECTO, **(params or {})}


@dataclass(frozen=True)
class Deteccion:
    centro: tuple[float, float]        # x, y de la tapa en la base (mm)
    giro_deg: float                    # del lado largo, antihorario visto desde arriba, en [-90, 90)
    largo: float                       # mm, el mayor
    ancho: float                       # mm
    alto: float                        # mm
    z_tapa: float                      # altura de la tapa en la base (mm)
    esquinas_px: np.ndarray            # (4, 2) de la tapa
    esquinas_base: np.ndarray          # (4, 2)
    area_px: float                     # de la máscara
    confianza: float                   # 0..1: lo rectangular que es la silueta y si se ve entera
    recortada: bool                    # toca el borde de la imagen: puede faltarle parte
    pared_mm: float = 0.0              # orden de magnitud de lo que infla la medida la pared que ve la cámara (0 con profundidad)

    def a_caja(self):
        from celda.percepcion import Caja
        return Caja(self.largo, self.ancho, self.alto, self.giro_deg, self.centro)


# ---------------------------------------------------------------- máscaras
def mascara_color(bgr: np.ndarray, params=None) -> np.ndarray:
    p = _params(params)
    suave = cv2.GaussianBlur(bgr, (5, 5), 0)
    hsv = cv2.cvtColor(suave, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array(p["hsv_bajo"]), np.array(p["hsv_alto"]))
    return _limpiar(m, p)


def mascara_fondo(bgr: np.ndarray, fondo: np.ndarray, params=None) -> np.ndarray:
    p = _params(params)
    if fondo.shape != bgr.shape:
        raise ValueError(f"la foto de fondo mide {fondo.shape[1]}x{fondo.shape[0]} y la imagen {bgr.shape[1]}x{bgr.shape[0]}")
    dif = cv2.absdiff(cv2.GaussianBlur(bgr, (5, 5), 0), cv2.GaussianBlur(fondo, (5, 5), 0)).max(axis=2)
    return _limpiar((dif > p["umbral_fondo"]).astype(np.uint8) * 255, p)


def _limpiar(m: np.ndarray, p: dict) -> np.ndarray:
    a = max(1, int(p["apertura_px"]))
    c = max(1, int(p["cierre_px"]))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((a, a), np.uint8))
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((c, c), np.uint8), iterations=2)


_cache_rayos: dict = {}
_cerrojo_rayos = threading.Lock()


def alturas_de_profundidad(profundidad_mm: np.ndarray, modelo: ModeloCamara) -> np.ndarray:
    """Altura z en la base (mm) de cada píxel a partir del mapa de profundidad (mm a lo largo del eje óptico, 0 = sin dato).
    NaN donde no hay medida."""
    alto, ancho = profundidad_mm.shape[:2]
    if (ancho, alto) != tuple(modelo.tam):
        raise ValueError(f"la profundidad mide {ancho}x{alto} y la calibración es de {modelo.tam[0]}x{modelo.tam[1]}: "
                         "tiene que estar alineada con la imagen de color")
    clave = (modelo.K.tobytes(), modelo.dist.tobytes(), ancho, alto, modelo.T_base_cam.matriz()[2].tobytes())
    with _cerrojo_rayos:   # el ciclo y el visor miden desde hilos distintos: la cache no se toca a la vez
        rayos = _cache_rayos.get(clave)
        if rayos is None:
            u, v = np.meshgrid(np.arange(ancho), np.arange(alto))
            px = np.stack([u.ravel(), v.ravel()], axis=1).astype(np.float64).reshape(-1, 1, 2)
            n = cv2.undistortPoints(px, modelo.K, modelo.dist).reshape(-1, 2)
            fila_z = modelo.T_base_cam.matriz()[2, :3]
            rayos = (n @ fila_z[:2] + fila_z[2]).reshape(alto, ancho)
            _cache_rayos.clear()
            _cache_rayos[clave] = rayos
    d = profundidad_mm.astype(np.float64)
    z = d * rayos + modelo.posicion[2]
    z[d <= 0] = np.nan
    return z


def mascara_altura(alturas: np.ndarray, z_plano: float, params=None) -> np.ndarray:
    p = _params(params)
    valido = np.isfinite(alturas)
    dentro = valido & (np.where(valido, alturas, 0.0) > z_plano + p["altura_min_mm"]) \
        & (np.where(valido, alturas, 0.0) < z_plano + p["altura_max_mm"])
    return _limpiar(dentro.astype(np.uint8) * 255, p)


# ---------------------------------------------------------------- detección
def _envolver(g: float) -> float:
    return ((g + 90.0) % 180.0) - 90.0


def detectar_cajas(bgr: np.ndarray, modelo: ModeloCamara, z_plano: float, alto_mm: float | None = None, params=None,
                   fondo: np.ndarray | None = None, profundidad: np.ndarray | None = None) -> list[Deteccion]:
    """Todas las cajas que ve la cámara, de mayor a menor área. z_plano: altura de la cinta (o de la mesa) en la base.

    alto_mm: alto de la caja si no se mide con profundidad (se usa para todas). Con profundidad y alto_mm = None, cada caja
    lleva su alto medido. Sin ninguno de los dos no se puede pasar la tapa a la base y es un error."""
    p = _params(params)
    alturas = None
    if profundidad is not None:
        alturas = alturas_de_profundidad(profundidad, modelo)
    if p["modo"] == "profundidad":
        if alturas is None:
            raise ValueError("el modo profundidad necesita el mapa de profundidad de la cámara")
        mascara = mascara_altura(alturas, z_plano, p)
    elif p["modo"] == "fondo":
        if fondo is None:
            raise ValueError("el modo fondo necesita una foto de la escena sin cajas")
        mascara = mascara_fondo(bgr, fondo, p)
    elif p["modo"] == "color":
        mascara = mascara_color(bgr, p)
    else:
        raise ValueError(f"modo de detección desconocido: {p['modo']!r} (color, fondo o profundidad)")
    if alto_mm is None and alturas is None:
        raise ValueError("sin mapa de profundidad hay que dar el alto de la caja (alto_mm)")

    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    alto_img, ancho_img = mascara.shape
    resultado = []
    for c in sorted(contornos, key=cv2.contourArea, reverse=True):
        area_px = float(cv2.contourArea(c))
        if area_px < p["area_min_px"]:
            break
        alto = alto_mm
        if alturas is not None and alto_mm is None:
            alto = _alto_medido(c, alturas, z_plano, mascara.shape)
            if alto is None:
                continue
        d = _rectangulo(c, modelo, z_plano, float(alto), p, area_px, (ancho_img, alto_img))
        if d is not None:
            resultado.append(d)
    return resultado


def _alto_medido(contorno, alturas: np.ndarray, z_plano: float, forma) -> float | None:
    relleno = np.zeros(forma, np.uint8)
    cv2.drawContours(relleno, [contorno], -1, 255, cv2.FILLED)
    relleno = cv2.erode(relleno, np.ones((7, 7), np.uint8))
    z = alturas[relleno > 0]
    z = z[np.isfinite(z)]
    if len(z) < 50:
        return None
    return float(np.median(z) - z_plano)


def _rectangulo(contorno, modelo: ModeloCamara, z_plano: float, alto: float, p: dict, area_px: float, tam_img) -> Deteccion | None:
    z_tapa = z_plano + alto
    puntos_px = contorno.reshape(-1, 2).astype(np.float64)
    try:
        en_plano = modelo.pixel_a_plano(puntos_px, z_tapa)
    except ValueError:
        return None
    (cx, cy), (w, h), _ = cv2.minAreaRect(en_plano.astype(np.float32))
    caja_mm = cv2.boxPoints(cv2.minAreaRect(en_plano.astype(np.float32))).astype(np.float64)
    largo, ancho = max(w, h), min(w, h)
    if ancho < p["lado_min_mm"]:
        return None
    # giro del lado largo en la base
    e0, e1 = caja_mm[1] - caja_mm[0], caja_mm[2] - caja_mm[1]
    lado = e0 if np.linalg.norm(e0) >= np.linalg.norm(e1) else e1
    giro = _envolver(float(np.degrees(np.arctan2(lado[1], lado[0]))))
    if (largo - ancho) / largo < p["cuadrada_tol"]:
        giro = ((giro + 45.0) % 90.0) - 45.0
    esquinas_px = modelo.base_a_pixel(np.hstack([caja_mm, np.full((4, 1), z_tapa)]))
    area_mm = float(cv2.contourArea(en_plano.astype(np.float32)))
    confianza = float(np.clip(area_mm / max(w * h, 1e-9), 0.0, 1.0))
    ancho_img, alto_img = tam_img
    margen = 2
    recortada = bool(np.any(puntos_px[:, 0] < margen) or np.any(puntos_px[:, 1] < margen)
                     or np.any(puntos_px[:, 0] > ancho_img - 1 - margen) or np.any(puntos_px[:, 1] > alto_img - 1 - margen))
    if recortada:
        confianza *= 0.3
    # Con la máscara de color o de fondo la silueta incluye la pared que mira a la cámara: es la envolvente de la tapa y del fondo de la
    # caja, y el fondo, visto desde la cámara y pasado al plano de la tapa, queda reducido hacia el pie de la cámara por
    # k = (altura de la cámara - alto) / altura de la cámara. Se estima cuánto infla eso el rectángulo medido, para avisar (la caja
    # justo bajo la cámara casi no crece; con profundidad no hay pared y es 0).
    altura_camara = modelo.posicion[2] - z_plano
    pared = 0.0
    if p["modo"] != "profundidad" and altura_camara > alto > 0:
        k = (altura_camara - alto) / altura_camara
        pie = modelo.posicion[:2]
        envolvente = np.vstack([caja_mm, pie + k * (caja_mm - pie)]).astype(np.float32)
        (_, _), (wi, hi), _ = cv2.minAreaRect(envolvente)
        pared = float(max(max(wi, hi) - largo, min(wi, hi) - ancho, 0.0))
    return Deteccion((float(cx), float(cy)), giro, float(largo), float(ancho), float(alto), float(z_tapa), esquinas_px, caja_mm,
                     area_px, confianza, recortada, pared)


def elegir(detecciones: list[Deteccion], centro_nominal=None) -> Deteccion | None:
    """La caja que se va a coger: la más cercana al punto de recogida si se conoce, y si no la mayor."""
    if not detecciones:
        return None
    if centro_nominal is None:
        return max(detecciones, key=lambda d: d.area_px)
    n = np.asarray(centro_nominal, dtype=float)
    return min(detecciones, key=lambda d: float(np.linalg.norm(np.asarray(d.centro) - n)))


def extremos_hilo(d: Deteccion) -> np.ndarray:
    """Píxeles (2 x 2) de los extremos del «hilo» de la caja: la recta que va del punto medio de un lado corto al del otro lado corto,
    pasando por el centro, es decir, a lo largo del eje largo (el del giro) y de extremo a extremo. Se calcula en la tapa, en la base,
    y se pasa a la imagen con la misma homografía que las esquinas."""
    a = np.radians(d.giro_deg)
    eje = np.array([np.cos(a), np.sin(a)]) * d.largo / 2.0
    c = np.asarray(d.centro, dtype=float)
    extremos = [np.array([c[0] - eje[0], c[1] - eje[1], d.z_tapa]), np.array([c[0] + eje[0], c[1] + eje[1], d.z_tapa])]
    return np.vstack([_pix(d, e) for e in extremos])


def centro_px(d: Deteccion) -> np.ndarray:
    """Píxel donde se ve el centro de la tapa de la caja."""
    return _pix(d, np.array([d.centro[0], d.centro[1], d.z_tapa]))


def ordenar(detecciones: list[Deteccion], centro_nominal=None) -> list[Deteccion]:
    """Las cajas de la mejor a la peor, con el mismo criterio que `elegir` (la más cercana al punto de recogida o, sin punto, la mayor); las
    cortadas por el borde de la imagen, al final."""
    if centro_nominal is None:
        return sorted(detecciones, key=lambda d: (d.recortada, -d.area_px))
    n = np.asarray(centro_nominal, dtype=float)
    return sorted(detecciones, key=lambda d: (d.recortada, float(np.linalg.norm(np.asarray(d.centro) - n))))


def dibujar(bgr: np.ndarray, detecciones: list[Deteccion], elegida: Deteccion | None = None) -> np.ndarray:
    """Copia de la imagen con cada caja marcada, como la ve el programa: el contorno (amarillo la elegida, verde las demás, rojo si está
    cortada por el borde), el hilo de extremo a extremo por el centro, el centro (punto verde con sus coordenadas en mm, como en el trabajo
    de Robótica Industrial) y las medidas."""
    img = bgr.copy()
    for d in detecciones:
        color = (0, 0, 255) if d.recortada else ((0, 255, 255) if d is elegida else (0, 220, 0))
        pts = np.round(d.esquinas_px).astype(np.int32)
        cv2.polylines(img, [pts], True, color, 2, cv2.LINE_AA)
        a, b = (tuple(int(round(v)) for v in p) for p in extremos_hilo(d))
        cv2.line(img, a, b, color, 2, cv2.LINE_AA)
        for extremo in (a, b):
            cv2.circle(img, extremo, 5, color, -1, cv2.LINE_AA)
        centro = tuple(int(round(v)) for v in centro_px(d))
        cv2.circle(img, centro, 8, (0, 0, 0), -1, cv2.LINE_AA)
        cv2.circle(img, centro, 6, (0, 255, 0), -1, cv2.LINE_AA)
        medidas = f"{d.largo:.0f}x{d.ancho:.0f}x{d.alto:.0f} giro {d.giro_deg:.0f}"
        coordenadas = f"{d.centro[0]:.0f},{d.centro[1]:.0f} mm"
        for k, texto in enumerate((medidas, coordenadas)):
            pos = (centro[0] + 14, centro[1] - 12 + 24 * k)
            cv2.putText(img, texto, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(img, texto, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.6, color if k == 0 else (0, 255, 0), 1, cv2.LINE_AA)
    return img


def _pix(d: Deteccion, punto3) -> np.ndarray:
    """Píxel de un punto 3D de la tapa usando la homografía local entre las esquinas en la base y en la imagen."""
    H, _ = cv2.findHomography(d.esquinas_base.astype(np.float32), d.esquinas_px.astype(np.float32))
    p = H @ np.array([punto3[0], punto3[1], 1.0])
    return p[:2] / p[2]
