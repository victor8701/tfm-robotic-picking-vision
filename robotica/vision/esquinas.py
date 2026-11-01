"""Detección de las esquinas de la caja en la imagen.

Port de src/deteccion_esquinas.py (plastico_transparente), con dos métodos:
- esquinas_por_contorno: contorno mayor de la máscara de color y cuadrilátero aproximado.
  Es el método por defecto: sencillo y estable cuando la caja se ve entera.
- esquinas_por_lineas: segmentos de Hough sobre el borde de la máscara, agrupados por
  dirección y cortados en intersecciones (el método del proyecto previo).

Ambos devuelven las esquinas en orden TL, TR, BR, BL, en píxeles (float32), o None.
"""
from __future__ import annotations

import cv2
import numpy as np

PARAMS_POR_DEFECTO = {
    # Máscara de color (HSV de OpenCV: H 0..180). Cartón marrón/beige típico.
    "hsv_bajo": (10, 65, 60),
    "hsv_alto": (30, 255, 255),
    # HoughLinesP (método de líneas)
    "hough_umbral": 40,
    "hough_long_min": 60,
    "hough_hueco_max": 20,
    "n_lineas": 8,
    "tol_angulo_deg": 20.0,
    "dist_agrupar_px": 80.0,
    "margen_esquina_px": 120.0,
}


def _params(params) -> dict:
    return {**PARAMS_POR_DEFECTO, **(params or {})}


def mascara_caja(bgr: np.ndarray, params=None) -> tuple[np.ndarray, np.ndarray | None]:
    """Máscara sólida del área de la caja y su contorno mayor (None si no hay caja)."""
    p = _params(params)
    suave = cv2.GaussianBlur(bgr, (5, 5), 0)   # el ruido del sensor desplaza el borde de la máscara
    hsv = cv2.cvtColor(suave, cv2.COLOR_BGR2HSV)
    color = cv2.inRange(hsv, np.array(p["hsv_bajo"]), np.array(p["hsv_alto"]))
    k5 = np.ones((5, 5), np.uint8)
    color = cv2.morphologyEx(color, cv2.MORPH_OPEN, k5, iterations=1)
    k15 = np.ones((15, 15), np.uint8)
    cerrada = cv2.morphologyEx(color, cv2.MORPH_CLOSE, k15, iterations=3)

    contornos, _ = cv2.findContours(cerrada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    solida = np.zeros_like(color)
    if not contornos:
        return solida, None
    mayor = max(contornos, key=cv2.contourArea)
    if cv2.contourArea(mayor) <= 1000:
        return solida, None
    cv2.drawContours(solida, [mayor], -1, 255, thickness=cv2.FILLED)
    return solida, mayor


def ordenar_esquinas(puntos) -> np.ndarray:
    """Ordena 4 puntos como TL, TR, BR, BL (la esquina superior izquierda tiene suma mínima)."""
    pts = np.asarray(puntos, dtype=np.float32).reshape(4, 2)
    suma = pts.sum(axis=1)
    dif = pts[:, 1] - pts[:, 0]
    tl = pts[np.argmin(suma)]
    br = pts[np.argmax(suma)]
    tr = pts[np.argmin(dif)]
    bl = pts[np.argmax(dif)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def esquinas_por_contorno(bgr: np.ndarray, params=None) -> np.ndarray | None:
    _, contorno = mascara_caja(bgr, params)
    if contorno is None:
        return None
    perimetro = cv2.arcLength(contorno, True)
    for fraccion in (0.01, 0.02, 0.03, 0.05, 0.08):
        aprox = cv2.approxPolyDP(contorno, fraccion * perimetro, True)
        if len(aprox) == 4:
            return ordenar_esquinas(aprox.reshape(4, 2))
    # Si el contorno no es un cuadrilátero claro (solapas, sombras), rectángulo mínimo como respaldo.
    return ordenar_esquinas(cv2.boxPoints(cv2.minAreaRect(contorno)))


def _recta(seg) -> np.ndarray:
    x1, y1, x2, y2 = seg
    return np.cross([x1, y1, 1.0], [x2, y2, 1.0])


def _interseccion(l1: np.ndarray, l2: np.ndarray):
    p = np.cross(l1, l2)
    if abs(p[2]) < 1e-9:
        return None
    return p[0] / p[2], p[1] / p[2]


def _angulo_deg(seg) -> float:
    x1, y1, x2, y2 = seg
    return float(np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180.0)


def _dif_angular(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _agrupar(puntos, dist: float) -> list[tuple[float, float]]:
    grupos: list[list[tuple[float, float]]] = []
    for p in puntos:
        for g in grupos:
            if np.hypot(p[0] - g[0][0], p[1] - g[0][1]) < dist:
                g.append(p)
                break
        else:
            grupos.append([p])
    return [(float(np.mean([q[0] for q in g])), float(np.mean([q[1] for q in g]))) for g in grupos]


def esquinas_por_lineas(bgr: np.ndarray, params=None) -> np.ndarray | None:
    """Esquinas como intersecciones de las rectas del borde de la máscara (método del proyecto previo)."""
    p = _params(params)
    mask, contorno = mascara_caja(bgr, p)
    if contorno is None:
        return None
    h, w = mask.shape
    k3 = np.ones((3, 3), np.uint8)
    borde = cv2.dilate(mask - cv2.erode(mask, k3), k3)
    segmentos = cv2.HoughLinesP(borde, 1, np.radians(1.0), max(5, p["hough_umbral"]),
                                minLineLength=max(5, p["hough_long_min"]),
                                maxLineGap=max(1, p["hough_hueco_max"]))
    if segmentos is None:
        return None
    segmentos = [tuple(int(v) for v in s[0]) for s in segmentos]
    segmentos.sort(key=lambda s: -np.hypot(s[2] - s[0], s[3] - s[1]))

    # Agrupar por dirección y tomar en round-robin, para tener rectas de todas las direcciones.
    grupos: list[dict] = []
    for s in segmentos:
        a = _angulo_deg(s)
        for g in grupos:
            if _dif_angular(a, g["ang"]) < p["tol_angulo_deg"]:
                g["segs"].append(s)
                break
        else:
            grupos.append({"ang": a, "segs": [s]})
    elegidas: list[tuple[int, int, int, int]] = []
    indices = [0] * len(grupos)
    while len(elegidas) < p["n_lineas"]:
        avanzo = False
        for i, g in enumerate(grupos):
            if indices[i] < len(g["segs"]):
                elegidas.append(g["segs"][indices[i]])
                indices[i] += 1
                avanzo = True
                if len(elegidas) >= p["n_lineas"]:
                    break
        if not avanzo:
            break

    rectas = [(_recta(s), _angulo_deg(s)) for s in elegidas]
    puntos = []
    for i in range(len(rectas)):
        for j in range(i + 1, len(rectas)):
            if _dif_angular(rectas[i][1], rectas[j][1]) < p["tol_angulo_deg"]:
                continue
            pt = _interseccion(rectas[i][0], rectas[j][0])
            if pt is None:
                continue
            m = p["margen_esquina_px"]
            if -m <= pt[0] <= w + m and -m <= pt[1] <= h + m:
                puntos.append(pt)
    if len(puntos) < 4:
        return None
    candidatos = _agrupar(puntos, p["dist_agrupar_px"])
    if len(candidatos) < 4:
        return None
    hull = cv2.convexHull(np.array(candidatos, dtype=np.float32)).reshape(-1, 2)
    if len(hull) < 4:
        return None
    return ordenar_esquinas(_cuatro_extremos(hull))


def _cuatro_extremos(hull: np.ndarray) -> np.ndarray:
    """Los cuatro extremos de un polígono convexo: tl, tr, br, bl por suma y diferencia."""
    tl = hull[np.argmin(hull[:, 0] + hull[:, 1])]
    br = hull[np.argmax(hull[:, 0] + hull[:, 1])]
    tr = hull[np.argmin(hull[:, 1] - hull[:, 0])]
    bl = hull[np.argmax(hull[:, 1] - hull[:, 0])]
    return np.array([tl, tr, br, bl])
