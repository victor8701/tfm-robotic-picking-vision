"""Escenas sintéticas: una cámara de verdad (ModeloCamara) mira una mesa con un tablero de ajedrez y cajas de cartón.

Las usan las pruebas y `python -m vision.generar_ejemplos` (para probar los programas de visión sin cámara ni robot) porque
se conoce la verdad: dónde están el tablero y cada caja y qué mide cada una. Las imágenes son parecidas a una foto cenital, no
fotorrealistas: fondo gris liso, tablero con perspectiva, cajas como prismas con las paredes más oscuras que la tapa.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from nucleo.geometria import Pose, desde_matriz
from vision.camara import ModeloCamara
from vision.tablero import Tablero

FONDO_BGR = (120, 120, 120)
TAPA_BGR = (70, 110, 150)       # cartón (RGB 150, 110, 70)
PARED_BGR = (48, 78, 108)       # cartón en sombra
PIXELES_POR_CUADRO = 40


@dataclass(frozen=True)
class CajaSintetica:
    """Una caja apoyada en z_plano, con el largo en la dirección `giro_deg` (antihorario visto desde arriba, desde +x)."""
    largo: float
    ancho: float
    alto: float
    giro_deg: float
    centro: tuple[float, float]

    def esquinas_base(self, z: float) -> np.ndarray:
        """Las cuatro esquinas (4, 3) del rectángulo a la altura z."""
        a = np.radians(self.giro_deg)
        e_l = np.array([np.cos(a), np.sin(a)])
        e_a = np.array([-np.sin(a), np.cos(a)])
        c = np.asarray(self.centro, dtype=float)
        puntos = [c + sl * self.largo / 2 * e_l + sa * self.ancho / 2 * e_a for sl, sa in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        return np.array([[p[0], p[1], z] for p in puntos])


def camara_cenital(tam=(1280, 960), altura_mm=800.0, centro_xy=(0.0, 0.0), fov_horizontal_deg=62.0, inclinacion_deg=0.0,
                   z_plano=0.0, distorsion=None) -> ModeloCamara:
    """Cámara sobre la mesa mirando hacia abajo, con la imagen orientada como se ve la mesa desde arriba (x a la derecha,
    y hacia arriba), y una inclinación opcional alrededor del eje x de la imagen."""
    from vision.camara import intrinsecos_por_campo_de_vision
    K = intrinsecos_por_campo_de_vision(tam, fov_horizontal_deg)
    R_base_cam = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]])
    a = np.radians(inclinacion_deg)
    giro_x = np.array([[1.0, 0.0, 0.0], [0.0, np.cos(a), -np.sin(a)], [0.0, np.sin(a), np.cos(a)]])
    R = R_base_cam @ giro_x
    pose = Pose.crear(t=[centro_xy[0], centro_xy[1], z_plano + altura_mm], q=desde_matriz(R))
    return ModeloCamara(K, np.zeros(5) if distorsion is None else np.asarray(distorsion, dtype=float), pose, tam,
                        {"origen": "sintetica"})


def _patron_tablero(tablero: Tablero) -> np.ndarray:
    """Imagen del tablero con un cuadro blanco de margen: (columnas+3) x (filas+3) cuadros, el primero negro."""
    p = PIXELES_POR_CUADRO
    nc, nf = tablero.columnas + 1, tablero.filas + 1
    img = np.full(((nf + 2) * p, (nc + 2) * p), 255, np.uint8)
    for f in range(nf):
        for c in range(nc):
            if (f + c) % 2 == 0:
                img[(f + 1) * p:(f + 2) * p, (c + 1) * p:(c + 2) * p] = 0
    return img


def dibujar_tablero(img: np.ndarray, modelo: ModeloCamara, tablero: Tablero, T_base_tablero: Pose) -> None:
    """Pinta el tablero con la perspectiva de la cámara. T_base_tablero: pose del marco del tablero (esquina interior (0, 0),
    u a la derecha, v hacia arriba, z hacia arriba) en la base."""
    patron = _patron_tablero(tablero)
    p, s = PIXELES_POR_CUADRO, tablero.cuadro_mm
    alto_p, ancho_p = patron.shape
    esquinas_patron = np.array([[0, 0], [ancho_p, 0], [ancho_p, alto_p], [0, alto_p]], dtype=np.float32)
    # píxel del patrón -> (u, v) del marco del tablero: la esquina interior (0, 0) está en ((2) p, (2) p)
    uv = np.array([[(x / p - 2.0) * s, -(y / p - 2.0) * s, 0.0] for x, y in esquinas_patron])
    destino = modelo.base_a_pixel(T_base_tablero.aplicar(uv)).astype(np.float32)
    H = cv2.getPerspectiveTransform(esquinas_patron, destino)
    tam = (img.shape[1], img.shape[0])
    warp = cv2.warpPerspective(patron, H, tam, flags=cv2.INTER_LINEAR)
    mascara = cv2.warpPerspective(np.full_like(patron, 255), H, tam, flags=cv2.INTER_NEAREST)
    img[mascara > 0] = cv2.cvtColor(warp, cv2.COLOR_GRAY2BGR)[mascara > 0]


def dibujar_caja(img: np.ndarray, modelo: ModeloCamara, caja: CajaSintetica, z_plano: float = 0.0) -> None:
    """Pinta la caja como prisma: paredes en sombra y tapa encima."""
    base = caja.esquinas_base(z_plano)
    tapa = caja.esquinas_base(z_plano + caja.alto)
    pb = np.round(modelo.base_a_pixel(base)).astype(np.int32)
    pt = np.round(modelo.base_a_pixel(tapa)).astype(np.int32)
    for i in range(4):
        j = (i + 1) % 4
        cv2.fillConvexPoly(img, np.array([pb[i], pb[j], pt[j], pt[i]]), PARED_BGR)
    cv2.fillConvexPoly(img, pt, TAPA_BGR)


def escena(modelo: ModeloCamara, cajas=(), tablero: Tablero | None = None, T_base_tablero: Pose | None = None,
           z_plano: float = 0.0, ruido: float = 0.0, semilla: int = 0) -> np.ndarray:
    """Imagen BGR de la mesa (plano z_plano) vista por la cámara, con el tablero y las cajas indicados."""
    ancho, alto = modelo.tam
    img = np.full((alto, ancho, 3), FONDO_BGR, np.uint8)
    if tablero is not None:
        dibujar_tablero(img, modelo, tablero, T_base_tablero or Pose.crear(t=[0.0, 0.0, z_plano]))
    for c in cajas:
        dibujar_caja(img, modelo, c, z_plano)
    if ruido > 0:
        rng = np.random.default_rng(semilla)
        img = np.clip(img + rng.normal(0, ruido, img.shape), 0, 255).astype(np.uint8)
    return img


def profundidad(modelo: ModeloCamara, cajas=(), z_plano: float = 0.0) -> np.ndarray:
    """Mapa de profundidad (mm, a lo largo del eje óptico) de la mesa y las tapas de las cajas; 0 donde no hay medida."""
    ancho, alto = modelo.tam
    u, v = np.meshgrid(np.arange(ancho), np.arange(alto))
    px = np.stack([u.ravel(), v.ravel()], axis=1).astype(np.float64)
    n = cv2.undistortPoints(px.reshape(-1, 1, 2), modelo.K, modelo.dist).reshape(-1, 2)
    d_cam = np.hstack([n, np.ones((len(n), 1))])
    R = modelo.T_base_cam.matriz()[:3, :3]
    d_base = d_cam @ R.T
    o = modelo.posicion

    def a_profundidad(z_superficie: float, dentro: np.ndarray | None = None) -> np.ndarray:
        s = (z_superficie - o[2]) / d_base[:, 2]          # por unidad de d_cam (que tiene z = 1): s es la profundidad
        z = np.where(s > 0, s, 0.0)
        return z if dentro is None else np.where(dentro, z, np.inf)

    mapa = a_profundidad(z_plano)
    for c in cajas:
        alto_caja = z_plano + c.alto
        punto = o + (alto_caja - o[2]) / d_base[:, 2:3] * d_base
        a = np.radians(c.giro_deg)
        e_l = np.array([np.cos(a), np.sin(a)])
        e_a = np.array([-np.sin(a), np.cos(a)])
        rel = punto[:, :2] - np.asarray(c.centro)
        dentro = (np.abs(rel @ e_l) <= c.largo / 2) & (np.abs(rel @ e_a) <= c.ancho / 2)
        prof_tapa = a_profundidad(alto_caja)
        mapa = np.where(dentro & (prof_tapa > 0), np.minimum(mapa, prof_tapa), mapa)
    return mapa.reshape(alto, ancho).astype(np.float32)
