"""Lógica del asistente de calibración de la cámara (sin ventana: la ventana es `calibracion.app_camara`).

Lleva la cuenta de lo que hace falta para dejar un `camara.json` (el que usa la detección de cajas):

  1. Intrínsecos: unas 15 fotos del tablero de ajedrez, en distintas posiciones e inclinaciones (`guardar_foto`, `calcular_intrinsecos`). Si de
     momento solo se sabe el campo de visión, `usar_campo_de_vision`.
  2. Posición de la cámara en la base del robot: una foto con la cámara FIJA y el tablero tendido sobre la superficie donde apoyan las cajas
     (`calcular_posicion`). Con el robot se tocan esquinas y se dan sus x, y; EN CASA (sin robot) se decide dónde está el tablero en la base
     (`toques_en_casa`): «el centro del tablero es el punto (700, 0) del robot y el tablero está derecho», y de ahí sale dónde está la cámara.
  3. `guardar` deja el JSON.

Marco del tablero: esquina (0, 0) arriba a la izquierda tal como se ve; las columnas crecen hacia la derecha (+u) y las filas hacia abajo (−v).
Con giro 0 el tablero está «derecho»: +u es +x de la base y +v es +y (hacia arriba en la imagen).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibracion.camara import (InformeExtrinsecos, InformeIntrinsecos, Toque, calibrar_extrinsecos,  # noqa: E402
                                calibrar_intrinsecos_con_esquinas, MIN_IMAGENES_INTRINSECOS)
from vision.camara import ModeloCamara, intrinsecos_por_campo_de_vision  # noqa: E402
from vision.tablero import Tablero, _orientar, detectar_esquinas  # noqa: E402

FOTOS_RECOMENDADAS = 15
SEPARACION_MIN_PX = 25.0          # una foto nueva tiene que mover el tablero al menos esto (media de las esquinas) respecto a las ya guardadas
INCLINACION_MIN = 0.05            # diferencia relativa entre lados opuestos del tablero a partir de la cual se considera inclinado
RMS_BUENO_PX = 0.5
RMS_ACEPTABLE_PX = 1.0
ANCHO_RAPIDO_PX = 640             # la detección en vivo se hace con la imagen reducida a este ancho


@dataclass(frozen=True)
class Resumen:
    n: int
    recomendadas: int
    celdas_cubiertas: int       # de 9 (cuadrícula 3 x 3 de la imagen)
    inclinadas: int
    consejo: str


class Asistente:
    def __init__(self, columnas: int = 9, filas: int = 6, cuadro_mm: float = 25.0):
        self.tablero = Tablero(columnas, filas, cuadro_mm)
        self._fotos: list[tuple[np.ndarray, np.ndarray]] = []     # (imagen BGR, esquinas precisas)
        self.tam: tuple[int, int] | None = None
        self.K: np.ndarray | None = None
        self.dist: np.ndarray | None = None
        self.informe_intrinsecos: InformeIntrinsecos | None = None
        self.origen_intrinsecos = ""                              # «fotos» o «campo de visión»
        self.modelo: ModeloCamara | None = None
        self.informe_posicion: InformeExtrinsecos | None = None

    # ---------------------------------------------------------------- tablero
    def configurar_tablero(self, columnas: int, filas: int, cuadro_mm: float) -> None:
        """Cambia el tablero. Si cambia, las fotos guardadas ya no valen y se pierden."""
        nuevo = Tablero(int(columnas), int(filas), float(cuadro_mm))
        if nuevo != self.tablero:
            self.tablero = nuevo
            self.borrar_fotos()
            self.K = self.dist = self.informe_intrinsecos = self.modelo = self.informe_posicion = None

    @property
    def aviso_tablero(self) -> str:
        if not self.tablero.origen_inequivoco:
            return (f"Un tablero de {self.tablero.columnas}x{self.tablero.filas} esquinas puede salir girado 180° y el origen sería ambiguo: usa una cuenta "
                    "par y otra impar (9x6, 7x4...).")
        return ""

    # ---------------------------------------------------------------- detección en vivo
    def esquinas_rapidas(self, bgr: np.ndarray) -> np.ndarray | None:
        """Esquinas del tablero (en píxeles de `bgr`) con una detección rápida y poco precisa, para dibujarlas en vivo; None si no lo ve entero."""
        alto, ancho = bgr.shape[:2]
        k = min(1.0, ANCHO_RAPIDO_PX / ancho)
        chica = cv2.resize(bgr, (round(ancho * k), round(alto * k)), interpolation=cv2.INTER_AREA) if k < 1.0 else bgr
        gris = cv2.cvtColor(chica, cv2.COLOR_BGR2GRAY)
        ok, esq = cv2.findChessboardCorners(gris, (self.tablero.columnas, self.tablero.filas),
                                            flags=cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_FAST_CHECK)
        if not ok:
            return None
        return _orientar(esq.reshape(-1, 2).astype(np.float64) / k, self.tablero)

    # ---------------------------------------------------------------- intrínsecos
    @property
    def n_fotos(self) -> int:
        return len(self._fotos)

    def borrar_fotos(self) -> None:
        self._fotos.clear()
        self.tam = None if self.K is None else self.tam

    def quitar_ultima(self) -> bool:
        if not self._fotos:
            return False
        self._fotos.pop()
        return True

    def guardar_foto(self, bgr: np.ndarray) -> tuple[bool, str]:
        """Guarda la foto para los intrínsecos si se ve el tablero entero (detección precisa, ~0,5 s) y no es casi igual a otra ya guardada."""
        tam = (bgr.shape[1], bgr.shape[0])
        if self._fotos and tam != (self._fotos[0][0].shape[1], self._fotos[0][0].shape[0]):
            return False, "la cámara ha cambiado de resolución: borra las fotos y empieza otra vez"
        esq = detectar_esquinas(bgr, self.tablero)
        if esq is None:
            return False, "no veo el tablero entero: que salga completo, sin brillos y enfocado"
        for _, otras in self._fotos:
            if float(np.mean(np.linalg.norm(esq - otras, axis=1))) < SEPARACION_MIN_PX:
                return False, "esta foto es casi igual a una ya guardada: mueve o inclina el tablero"
        self._fotos.append((bgr.copy(), esq))
        self.tam = tam
        return True, f"foto {len(self._fotos)} guardada"

    @staticmethod
    def _inclinado(esq: np.ndarray, tablero: Tablero) -> bool:
        """El tablero se ve en perspectiva (inclinado): sus lados opuestos no miden lo mismo."""
        c, f = tablero.columnas, tablero.filas
        arriba, abajo = np.linalg.norm(esq[c - 1] - esq[0]), np.linalg.norm(esq[c * f - 1] - esq[c * (f - 1)])
        izq, der = np.linalg.norm(esq[c * (f - 1)] - esq[0]), np.linalg.norm(esq[c * f - 1] - esq[c - 1])
        return abs(arriba / abajo - 1.0) > INCLINACION_MIN or abs(izq / der - 1.0) > INCLINACION_MIN

    def resumen(self) -> Resumen:
        """Cuántas fotos hay, cuántas de las 9 zonas de la imagen cubren y cuántas con el tablero inclinado, y qué falta."""
        celdas, inclinadas = set(), 0
        for bgr, esq in self._fotos:
            alto, ancho = bgr.shape[:2]
            cx, cy = esq.mean(axis=0)
            celdas.add((min(2, int(3 * cx / ancho)), min(2, int(3 * cy / alto))))
            inclinadas += self._inclinado(esq, self.tablero)
        n = len(self._fotos)
        if n < MIN_IMAGENES_INTRINSECOS:
            consejo = f"faltan al menos {MIN_IMAGENES_INTRINSECOS - n} fotos"
        elif len(celdas) < 5:
            consejo = "lleva el tablero a los bordes y las esquinas de la imagen: hay zonas sin cubrir"
        elif inclinadas < 3:
            consejo = "inclina el tablero (como una hoja medio levantada) en algunas fotos"
        elif n < FOTOS_RECOMENDADAS:
            consejo = f"bien; con {FOTOS_RECOMENDADAS - n} más será mejor"
        else:
            consejo = "suficientes fotos: calcula los intrínsecos"
        return Resumen(n, FOTOS_RECOMENDADAS, len(celdas), inclinadas, consejo)

    def calcular_intrinsecos(self) -> InformeIntrinsecos:
        """K y distorsión con las fotos guardadas. ValueError si hay pocas."""
        if not self._fotos:
            raise ValueError(f"no hay fotos: guarda al menos {MIN_IMAGENES_INTRINSECOS}")
        esquinas = {f"foto_{i + 1:02d}": esq for i, (_, esq) in enumerate(self._fotos)}
        informe = calibrar_intrinsecos_con_esquinas(esquinas, self.tam, self.tablero)
        self.informe_intrinsecos, self.K, self.dist, self.tam = informe, informe.K, informe.dist, informe.tam
        self.origen_intrinsecos = "fotos"
        self.modelo = self.informe_posicion = None
        return informe

    @staticmethod
    def veredicto_intrinsecos(rms_px: float) -> str:
        return "muy bien" if rms_px < RMS_BUENO_PX else ("aceptable" if rms_px < RMS_ACEPTABLE_PX else "repite con más fotos y más variadas")

    def usar_campo_de_vision(self, tam: tuple[int, int], fov_horizontal_deg: float) -> None:
        """Sin fotos: solo el campo de visión de la cámara (una webcam suele tener 60-70°). Menos preciso (sin distorsión)."""
        self.tam = (int(tam[0]), int(tam[1]))
        self.K, self.dist = intrinsecos_por_campo_de_vision(self.tam, fov_horizontal_deg), np.zeros(5)
        self.informe_intrinsecos = None
        self.origen_intrinsecos = f"campo de visión de {fov_horizontal_deg:g}°"
        self.modelo = self.informe_posicion = None

    def usar_intrinsecos_de(self, ruta) -> None:
        """Reutiliza los intrínsecos de un camara.json anterior (la misma cámara y resolución): si solo has movido la cámara basta repetir la
        posición (paso 3). ValueError si el fichero no vale."""
        m = ModeloCamara.cargar(ruta)
        self.K, self.dist, self.tam = m.K, m.dist, m.tam
        self.informe_intrinsecos = None
        self.origen_intrinsecos = f"los de {Path(ruta).name}"
        self.modelo = self.informe_posicion = None

    # ---------------------------------------------------------------- posición de la cámara en la base
    def _base_de(self, uv: np.ndarray, origen: np.ndarray, giro_deg: float) -> np.ndarray:
        a = np.radians(giro_deg)
        R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        return origen + R @ uv

    def toques_en_casa(self, centro_x: float, centro_y: float, giro_deg: float = 0.0) -> tuple[list[Toque], list[Toque]]:
        """«Toques» de mentira para trabajar sin robot: el centro del tablero está en el punto (centro_x, centro_y) de la base y el tablero está girado
        giro_deg (antihorario visto desde arriba; 0 = derecho, columnas hacia +x). Devuelve (toques, validación): tres esquinas para el ajuste y otras
        dos, independientes, para comprobar."""
        t = self.tablero
        plano = t.puntos_plano()
        centro_uv = np.array([(t.columnas - 1) * t.cuadro_mm / 2.0, -(t.filas - 1) * t.cuadro_mm / 2.0])
        a = np.radians(giro_deg)
        R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        origen = np.array([centro_x, centro_y]) - R @ centro_uv

        def toque(c: int, f: int) -> Toque:
            p = self._base_de(plano[t.indice(c, f)], origen, giro_deg)
            return Toque(c, f, float(p[0]), float(p[1]))
        c, f = t.columnas, t.filas
        return ([toque(0, 0), toque(c - 1, 0), toque(0, f - 1)], [toque(c - 1, f - 1), toque(c // 2, f // 2)])

    def calcular_posicion(self, bgr: np.ndarray, z_plano: float, toques: list[Toque], validacion: list[Toque] | None = None
                          ) -> tuple[ModeloCamara, InformeExtrinsecos]:
        """Pose de la cámara en la base con una foto de la cámara fija y el tablero tendido sobre el plano z = z_plano."""
        if self.K is None:
            raise ValueError("primero los intrínsecos: calcúlalos con las fotos o usa el campo de visión")
        if (bgr.shape[1], bgr.shape[0]) != self.tam:
            raise ValueError(f"los intrínsecos son de {self.tam[0]}x{self.tam[1]} y la cámara da {bgr.shape[1]}x{bgr.shape[0]}: usa la misma resolución")
        modelo, informe = calibrar_extrinsecos(bgr, self.K, self.dist, self.tablero, toques, z_plano, validacion)
        self.modelo, self.informe_posicion = modelo, informe
        return modelo, informe

    # ---------------------------------------------------------------- resultado
    def guardar(self, ruta) -> Path:
        """Deja el camara.json (intrínsecos + posición en la base)."""
        if self.modelo is None:
            raise ValueError("todavía no hay calibración: calcula la posición de la cámara (paso 3)")
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        info = dict(self.modelo.info)
        info["intrinsecos"] = self.origen_intrinsecos
        if self.informe_intrinsecos is not None:
            info["rms_intrinsecos_px"] = self.informe_intrinsecos.rms_px
            info["fotos_intrinsecos"] = self.informe_intrinsecos.n_usadas
        ModeloCamara(self.modelo.K, self.modelo.dist, self.modelo.T_base_cam, self.modelo.tam, info).guardar(ruta)
        return ruta
