"""Tablero de ajedrez como referencia: detección de sus esquinas y pose de la cámara respecto a él.

Sirve para calibrar la cámara (intrínsecos y posición en la base, `calibracion.camara`) y, en las pruebas en casa, para
dar escala y marco de referencia a una foto (`vision.probar_en_casa`).

Marco del tablero: origen en la esquina interior (columna 0, fila 0), u hacia la derecha y v hacia arriba tal como se ve el
tablero de frente (en la imagen, la fila 0 está arriba y las filas crecen hacia abajo), z hacia el observador. Es un marco
directo con z hacia arriba, como el de la base del robot: un tablero tendido boca arriba sobre la cinta pasa a la base con un
giro y una traslación en el plano.

Las esquinas son las INTERIORES. Un tablero de 9 x 6 esquinas tiene 10 x 7 cuadros. Para que el origen no sea ambiguo, una de las
dos cuentas tiene que ser par y la otra impar (9 x 6, 7 x 4...).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from nucleo.geometria import Pose
from vision.camara import ModeloCamara


@dataclass(frozen=True)
class Tablero:
    columnas: int      # esquinas interiores a lo largo de la imagen (hacia la derecha)
    filas: int         # esquinas interiores hacia abajo
    cuadro_mm: float   # lado de un cuadro

    def __post_init__(self):
        if self.columnas < 3 or self.filas < 3 or self.cuadro_mm <= 0:
            raise ValueError("el tablero necesita al menos 3 x 3 esquinas y un cuadro de lado positivo")

    @classmethod
    def desde_texto(cls, texto: str, cuadro_mm: float) -> "Tablero":
        """'9x6' -> Tablero(9, 6, cuadro_mm)."""
        try:
            c, f = (int(v) for v in texto.lower().replace("×", "x").split("x"))
        except ValueError:
            raise ValueError(f"el tablero se escribe columnasxfilas, por ejemplo 9x6 (y es {texto!r})") from None
        return cls(c, f, cuadro_mm)

    @property
    def n_esquinas(self) -> int:
        return self.columnas * self.filas

    @property
    def origen_inequivoco(self) -> bool:
        return self.columnas % 2 != self.filas % 2

    def indice(self, columna: int, fila: int) -> int:
        if not (0 <= columna < self.columnas and 0 <= fila < self.filas):
            raise ValueError(f"la esquina ({columna}, {fila}) no existe en un tablero de {self.columnas} x {self.filas}")
        return fila * self.columnas + columna

    def puntos_plano(self) -> np.ndarray:
        """Esquinas en el marco del tablero (N, 2) mm, en el orden de detección: por filas, de izquierda a derecha."""
        s = self.cuadro_mm
        return np.array([[c * s, -f * s] for f in range(self.filas) for c in range(self.columnas)], dtype=np.float64)


def detectar_esquinas(bgr: np.ndarray, tablero: Tablero) -> np.ndarray | None:
    """Esquinas interiores del tablero en píxeles (N, 2), con precisión de subpíxel, o None si no lo encuentra.

    Salen siempre por filas y de izquierda a derecha (fila 0 arriba) mientras el tablero no esté girado más de 90° en la imagen."""
    gris = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    patron = (tablero.columnas, tablero.filas)
    esq = None
    # El detector de sectores (más lento, ~0,6 s por foto) es el más preciso y aguanta mejor el desenfoque, los brillos y el poco
    # contraste; si no lo encuentra, el clásico con afinado a subpíxel. Solo se usa al calibrar o en las pruebas, no en el ciclo.
    if hasattr(cv2, "findChessboardCornersSB"):
        ok, c = cv2.findChessboardCornersSB(gris, patron, flags=cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY)
        if ok:
            esq = c.reshape(-1, 2).astype(np.float64)
    if esq is None:
        ok, c = cv2.findChessboardCorners(gris, patron, flags=cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
        if not ok:
            return None
        criterio = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
        esq = cv2.cornerSubPix(gris, c, (11, 11), (-1, -1), criterio).reshape(-1, 2).astype(np.float64)
    return _orientar(esq, tablero)


def _orientar(esq: np.ndarray, tablero: Tablero) -> np.ndarray:
    """Que la fila 0 quede arriba y las columnas crezcan hacia la derecha (OpenCV puede devolver el tablero al revés)."""
    c = tablero.columnas
    a_lo_largo = esq[c - 1] - esq[0]
    hacia_abajo = esq[(tablero.filas - 1) * c] - esq[0]
    if a_lo_largo[0] < 0 and hacia_abajo[1] < 0:
        return esq[::-1].copy()
    return esq


def pose_tablero(esquinas_px, tablero: Tablero, K, dist) -> tuple[np.ndarray, float]:
    """Pose T_cam_tablero (4x4, mm) del marco del tablero en la cámara y error de reproyección medio (px)."""
    obj = np.hstack([tablero.puntos_plano(), np.zeros((tablero.n_esquinas, 1))])
    img = np.asarray(esquinas_px, dtype=np.float64).reshape(-1, 2)
    K = np.asarray(K, dtype=np.float64)
    dist = np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64)
    n, rvecs, tvecs, errores = cv2.solvePnPGeneric(obj, img, K, dist, flags=cv2.SOLVEPNP_IPPE)
    if n == 0:
        raise ValueError("no se pudo estimar la pose del tablero")
    mejor = int(np.argmin(errores.reshape(-1)))
    rvec, tvec = cv2.solvePnPRefineLM(obj, img, K, dist, rvecs[mejor], tvecs[mejor])
    proy, _ = cv2.projectPoints(obj, rvec, tvec, K, dist)
    rms = float(np.sqrt(np.mean(np.sum((proy.reshape(-1, 2) - img) ** 2, axis=1))))
    T = np.eye(4)
    T[:3, :3], _ = cv2.Rodrigues(rvec)
    T[:3, 3] = tvec.reshape(3)
    if T[2, 3] <= 0:
        raise ValueError("el tablero queda detrás de la cámara: la pose no es válida")
    return T, rms


def modelo_desde_tablero(bgr: np.ndarray, tablero: Tablero, K, dist, tam=None) -> ModeloCamara | None:
    """Modelo de la cámara que toma como base el marco del tablero (z = 0 es el plano del tablero). Es lo que usan las
    pruebas en casa: el tablero que aparece en la foto da el origen, la escala y la altura cero. None si no lo ve."""
    esq = detectar_esquinas(bgr, tablero)
    if esq is None:
        return None
    T_cam_tab, rms = pose_tablero(esq, tablero, K, dist)
    alto, ancho = bgr.shape[:2]
    return ModeloCamara(np.asarray(K, dtype=np.float64), np.zeros(5) if dist is None else np.asarray(dist, dtype=np.float64),
                        Pose.desde_matriz(np.linalg.inv(T_cam_tab)), tam or (ancho, alto), {"origen": "tablero", "rms_px": rms})
