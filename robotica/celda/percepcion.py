"""Percepcion de la caja: en simulacion, las medidas que genero RAPID en caja.csv;
en el laboratorio, la camara (vision/, calibracion/camara.py). La interfaz es la misma: leer(i) -> Caja."""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Caja:
    largo: float
    ancho: float
    alto: float
    giro_deg: float
    # Centro de la caja (x, y) en mm respecto a la base. None = el centro de recogida de la config.
    centro: tuple[float, float] | None = None


def centro_parada(largo: float, ancho: float, giro_deg: float, centro_x: float, sensor_y: float):
    """Donde queda el centro de la caja cuando el sensor de final de cinta la para.

    La cinta lleva la caja en +y y se para cuando su cara delantera toca el plano del sensor
    (y = sensor_y). Con giro 0, el largo va en x. Es lo que veria una camara en la simulacion.
    """
    g = math.radians(giro_deg)
    medio_y = (largo / 2.0) * abs(math.sin(g)) + (ancho / 2.0) * abs(math.cos(g))
    return (centro_x, sensor_y - medio_y)


def _linea(texto: str, n: int) -> Caja:
    partes = texto.strip().split(";")
    if len(partes) != 4:
        raise ValueError(f"caja.csv, linea {n}: se esperan 4 campos (largo;ancho;alto;giro) y hay {len(partes)}")
    largo, ancho, alto, giro = (float(p) for p in partes)
    if min(largo, ancho, alto) <= 0.0:
        raise ValueError(f"caja.csv, linea {n}: las dimensiones deben ser positivas")
    if not -90.0 <= giro < 90.0:
        raise ValueError(f"caja.csv, linea {n}: el giro debe estar en [-90, 90)")
    return Caja(largo, ancho, alto, giro)


class FuenteCsv:
    """Cajas de la simulacion. RAPID escribe caja.csv al arrancar, asi que el fichero se lee
    en la primera caja (no al crear la fuente, que puede ser antes que RAPID)."""

    def __init__(self, ruta, centro_x: float | None = None, sensor_y: float | None = None):
        self._ruta = Path(ruta)
        self._centro_x = centro_x
        self._sensor_y = sensor_y
        self._cajas: list[Caja] | None = None

    def _cargar(self) -> list[Caja]:
        if not self._ruta.is_file():
            raise FileNotFoundError(f"no existe {self._ruta}: ¿esta RAPID en marcha y ha generado caja.csv?")
        lineas = [ln for ln in self._ruta.read_text(encoding="utf-8").splitlines() if ln.strip()]
        cajas = [_linea(ln, n) for n, ln in enumerate(lineas, start=1)]
        if self._sensor_y is None or self._centro_x is None:
            return cajas
        return [Caja(c.largo, c.ancho, c.alto, c.giro_deg,
                     centro_parada(c.largo, c.ancho, c.giro_deg, self._centro_x, self._sensor_y)) for c in cajas]

    def leer(self, i: int) -> Caja:
        if self._cajas is None:
            self._cajas = self._cargar()
        if not 0 <= i < len(self._cajas):
            raise IndexError(f"caja {i} fuera de caja.csv ({len(self._cajas)} cajas)")
        return self._cajas[i]

    def total(self) -> int:
        """Cajas de la tanda: las que RAPID ha escrito en caja.csv, una por linea. Asi el PC y RAPID no
        pueden discrepar en la cuenta (con n_cajas = 1 en el PC y nCajas = 5 en RAPID, RAPID hacia las
        cajas 2 a 5 sin que el PC las agarrara)."""
        if self._cajas is None:
            self._cajas = self._cargar()
        return len(self._cajas)


@dataclass(frozen=True)
class Vista:
    """Lo que ve la camara ahora y lo que el programa considera la caja (para el visor). fotograma None = no hay imagen (carpeta agotada)."""
    fotograma: object | None
    detecciones: list
    elegida: object | None
    origen: str                # «carpeta celda», «camara»...
    indice: int | None = None  # imagen actual de una carpeta (1..total), None si es una camara
    total: int | None = None


class FuenteCamara:
    """La caja que ve la camara, medida en la base del robot (vision.deteccion): largo, ancho, alto, giro y centro.

    Cada leer() pide fotogramas al proveedor hasta ver una caja entera (no recortada por el borde de la imagen) o agotar tiempo_max_s
    (PERS tMaxCamara de RAPID): entonces para con un error, nunca inventa una posicion. El PC la configura al empezar la tanda con
    los ajustes de RAPID (configurar): altura de la cinta, punto de recogida (para elegir la caja mas cercana si hay varias) y espera."""

    def __init__(self, proveedor=None, modelo=None, z_cinta: float = 220.0, alto_mm: float | None = None, params=None, fondo=None,
                 centro_nominal=None, tiempo_max_s: float = 5.0, pausa_s: float = 0.1, motivo_sin_configurar: str | None = None):
        self.proveedor = proveedor
        self.modelo = modelo
        self.z_cinta = z_cinta
        self.alto_mm = alto_mm
        self.params = params
        self.fondo = fondo
        self.centro_nominal = centro_nominal
        self.tiempo_max_s = tiempo_max_s
        self.pausa_s = pausa_s
        self._motivo = motivo_sin_configurar
        # El ciclo y el visor piden imagenes desde hilos distintos: solo uno a la vez habla con el proveedor.
        self._cerrojo = threading.RLock()
        self._proveedor_base = proveedor
        self._modelo_base = modelo
        self._cache_vista = None
        # Aviso opcional tras medir cada caja: al_medir(fotograma, detecciones, elegida, i). Nunca para el ciclo.
        self.al_medir = None
        # Cuantas cajas identifica la vista previa en cada imagen (las mejores segun el criterio de elegir): normalmente 1; None = todas.
        self.max_cajas: int | None = None

    @classmethod
    def desde_config(cls, cfg, proveedor=None) -> "FuenteCamara":
        """A partir de la seccion 'camara' de la configuracion de la celda (ver docs/vision.md). proveedor: uno ya creado (por ejemplo, el de
        ROS 2, que necesita un nodo); si no, se abre el de la seccion 'origen'."""
        import cv2

        from vision.camara import ModeloCamara
        from vision.proveedores import abrir_proveedor
        c = cfg.camara
        if not c:
            return cls(motivo_sin_configurar="falta la seccion 'camara' en config_celda.json (calibracion, origen de las imagenes y alto "
                                              "de la caja): ver docs/vision.md")
        if not c.get("calibracion"):
            raise ValueError("camara.calibracion: falta la ruta del camara.json de calibracion.camara")
        params = dict(c.get("params") or {})
        for clave in ("modo", "hsv_bajo", "hsv_alto", "umbral_fondo"):
            if clave in c:
                params[clave] = c[clave]
        fondo = None
        if c.get("fondo"):
            fondo = cv2.imread(c["fondo"], cv2.IMREAD_COLOR)
            if fondo is None:
                raise ValueError(f"camara.fondo: no puedo leer {c['fondo']}")
        modelo = ModeloCamara.cargar(c["calibracion"])   # antes que abrir la camara: si falta la calibracion, que lo diga primero
        fuente = cls(proveedor if proveedor is not None else abrir_proveedor(c.get("origen") or {}), modelo, cfg.z_cinta,
                     None if c.get("alto_mm") is None else float(c["alto_mm"]), params, fondo, cfg.centro_recogida, cfg.t_max_camara)
        fuente.max_cajas = int(c.get("cajas", 1)) if c.get("cajas") != "todas" else None   # la vista previa identifica 1 caja salvo que se pida otra cosa
        return fuente

    def configurar(self, cfg) -> None:
        """Pone lo que RAPID dice (la app del FlexPendant): altura de la cinta, punto de recogida y espera maxima a la camara."""
        self.z_cinta = cfg.z_cinta
        self.centro_nominal = cfg.centro_recogida
        self.tiempo_max_s = cfg.t_max_camara

    def leer(self, i: int) -> Caja:
        if self.proveedor is None:
            raise RuntimeError("percepcion por camara sin configurar: " + (self._motivo or "falta el proveedor de imagenes"))
        from vision.deteccion import detectar_cajas, elegir
        limite = time.monotonic() + self.tiempo_max_s
        recortada = False
        while True:
            with self._cerrojo:
                proveedor, modelo = self.proveedor, self.modelo
                fot = proveedor.siguiente()
            if fot is None:
                raise RuntimeError("la camara no tiene mas imagenes (carpeta agotada o camara cerrada)")
            dets = detectar_cajas(fot.bgr, modelo, self.z_cinta, self.alto_mm, self.params, self.fondo, fot.profundidad)
            enteras = [d for d in dets if not d.recortada]
            recortada = recortada or (bool(dets) and not enteras)
            d = elegir(enteras, self.centro_nominal)
            if d is not None:
                self._avisar_medida(fot, dets, d, i)
                return d.a_caja()
            if time.monotonic() >= limite:
                raise RuntimeError(f"la camara no ve ninguna caja entera en {self.tiempo_max_s:g} s (tMaxCamara)"
                                   + ("; la que ve esta cortada por el borde de la imagen" if recortada else ""))
            time.sleep(self.pausa_s)

    def _avisar_medida(self, fot, dets, elegida, i: int) -> None:
        if self.al_medir is not None:
            try:
                self.al_medir(fot, dets, elegida, i)
            except Exception:   # noqa: BLE001 - el visor nunca debe parar el ciclo
                pass

    # ---------------------------------------------------------------- visor y carpeta de ensayo
    def origen(self) -> str:
        """De donde vienen las imagenes, en una palabra o dos (para el visor y la app)."""
        p = self.proveedor
        if p is None:
            return "sin camara"
        if hasattr(p, "nombre") and hasattr(p, "n"):
            return f"carpeta {p.nombre}"
        nombre = {"CamaraOpenCV": "camara USB", "RealSense": "RealSense", "ProveedorRos": "camara por ROS"}.get(type(p).__name__, type(p).__name__.lower())
        indice = getattr(p, "indice", None)
        return nombre if indice is None else f"{nombre} {indice}"

    def n_imagenes(self) -> int | None:
        """Imagenes de la carpeta (None si la camara no es una carpeta). No es total(): total() sigue sin fin conocido."""
        return getattr(self.proveedor, "n", None)

    def vista_previa(self) -> "Vista | None":
        """Lo que ve la camara ahora, con lo que el programa considera la caja, SIN gastar la imagen (en una carpeta, la actual; en una
        camara, el ultimo fotograma). None si no hay proveedor. Se llama desde el hilo del visor."""
        if self.proveedor is None:
            return None
        from vision.deteccion import detectar_cajas, elegir, ordenar
        with self._cerrojo:
            p, modelo = self.proveedor, self.modelo
            ver = getattr(p, "ver", None)
            carpeta = ver is not None
            fot = ver() if carpeta else p.siguiente()
            n, indice = (getattr(p, "n", None), getattr(p, "indice", None))
            origen = self.origen()
            clave = (id(p), id(modelo), fot.nombre if fot is not None else None, self.z_cinta, self.alto_mm, self.centro_nominal, self.max_cajas)
            if carpeta and self._cache_vista is not None and self._cache_vista[0] == clave:
                return self._cache_vista[1]
        if fot is None:
            return Vista(None, [], None, origen, None if n is None else n, n)
        dets = detectar_cajas(fot.bgr, modelo, self.z_cinta, self.alto_mm, self.params, self.fondo, fot.profundidad)
        elegida = elegir([d for d in dets if not d.recortada], self.centro_nominal)
        if self.max_cajas is not None:   # solo las N mejores (normalmente 1): lo demas en la imagen es ruido o cajas que no se cogen ahora
            dets = ordenar(dets, self.centro_nominal)[:max(1, int(self.max_cajas))]
        vista = Vista(fot, dets, elegida, origen, None if indice is None else indice + 1, n)
        if carpeta:
            self._cache_vista = (clave, vista)
        return vista

    def usar_carpeta(self, ruta, exigir_calibracion: bool = True) -> int:
        """Pasa a leer las fotos de una carpeta (la que se elige en la app) y devuelve cuantas tiene. Si la carpeta trae su camara.json, esa es
        la calibracion (cada juego de fotos se hizo con una camara distinta); si no la trae y exigir_calibracion, ValueError."""
        from vision.camara import ModeloCamara
        from vision.proveedores import Carpeta
        r = Path(ruta)
        carpeta = Carpeta(r)                                  # ValueError si no existe o no hay imagenes
        calibracion = r / "camara.json"
        if calibracion.is_file():
            modelo = ModeloCamara.cargar(calibracion)
        elif exigir_calibracion:
            raise ValueError(f"{r.name} no tiene camara.json (la calibracion de esa camara)")
        else:
            modelo = self._modelo_base
        with self._cerrojo:
            self.proveedor, self.modelo, self._cache_vista = carpeta, modelo, None
        return carpeta.n

    def restaurar_origen(self) -> None:
        """Vuelve a la camara (o carpeta) de la configuracion del PC."""
        with self._cerrojo:
            self.proveedor, self.modelo, self._cache_vista = self._proveedor_base, self._modelo_base, None

    def total(self):
        return None  # sin fin conocido: manda nCajas de RAPID (la app)


def crear_fuente(cfg):
    if not cfg.modo_simulacion:
        return FuenteCamara.desde_config(cfg)
    return FuenteCsv(cfg.csv_caja, cfg.centro_recogida[0], cfg.sensor_cinta_y)
