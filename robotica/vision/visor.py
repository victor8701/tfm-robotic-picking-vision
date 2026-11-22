"""Visor en tiempo real: lo que ve la camara y lo que el programa considera la caja (contorno), su centro (punto verde con coordenadas) y el
hilo (de un lado corto al otro por el centro). Como la ventana del trabajo de pick and place de Robotica Industrial, pero con la vista previa
y el resultado de cada caja.

- Un hilo (`iniciar`) pide cada pocas decimas la vista previa a la `FuenteCamara` (sin gastar imagenes) y compone la imagen.
- El hilo PRINCIPAL llama a `bombear()` para dibujar la ventana (Qt/Windows exigen el hilo principal): `ejecutar_con_visor` lo hace mientras el
  ciclo corre en otro hilo; `nodo_celda` lo hace en su bucle de spin.
- Cuando el ciclo mide una caja (`FuenteCamara.al_medir`), la imagen de ese resultado se queda `MEDIDA_S` segundos.
- Sin pantalla (sin DISPLAY, OpenCV sin ventanas) avisa una vez y todo sigue sin ventana.
"""
from __future__ import annotations

import threading
import time

import cv2
import numpy as np

from vision.deteccion import dibujar

ANCHO_MAX = 1000     # px: las imagenes mas anchas se reducen para la ventana
ALTO_BANDA = 38      # px de la banda de texto de arriba
MEDIDA_S = 3.0       # segundos que se queda el resultado de una caja antes de volver a la vista previa
BLANCO, VERDE, ROJO, AMARILLO = (255, 255, 255), (0, 255, 0), (0, 0, 255), (0, 255, 255)


def _con_banda(img: np.ndarray, texto: str, color=BLANCO) -> np.ndarray:
    """La imagen (reducida si es muy ancha) con una banda negra arriba y el texto."""
    h, w = img.shape[:2]
    if w > ANCHO_MAX:
        img = cv2.resize(img, (ANCHO_MAX, round(h * ANCHO_MAX / w)), interpolation=cv2.INTER_AREA)
        w = ANCHO_MAX
    banda = np.zeros((ALTO_BANDA, w, 3), np.uint8)
    cv2.putText(banda, texto, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 1, cv2.LINE_AA)
    return np.vstack([banda, img])


def _lienzo(texto_central: str) -> np.ndarray:
    img = np.zeros((360, 640, 3), np.uint8)
    cv2.putText(img, texto_central, (30, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.8, BLANCO, 2, cv2.LINE_AA)
    return img


def _donde(vista) -> str:
    texto = vista.origen
    if vista.total is not None and vista.indice is not None:
        texto += f"  |  foto {min(vista.indice, vista.total)} de {vista.total}"
    return texto


class Visor:
    def __init__(self, fuente, hz: float = 5.0, titulo: str = "Vision de la celda", mostrar: bool = True, reloj=time.monotonic):
        self.fuente = fuente
        self.titulo = titulo
        self.mostrar = mostrar          # False: sin ventana (pruebas y equipos sin pantalla)
        self.sin_pantalla = False
        self._periodo = 1.0 / hz
        self._reloj = reloj
        self._cerrojo = threading.Lock()
        self._previa: np.ndarray | None = None
        self._medida: tuple[np.ndarray, float] | None = None   # imagen y hasta cuando
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None
        self._ventana_abierta = False
        self._cerrada = False
        self._aviso_error: str | None = None
        fuente.al_medir = self.al_medir

    # ---------------------------------------------------------------- hilo de la vista previa
    def iniciar(self) -> None:
        if self._hilo is None:
            self._hilo = threading.Thread(target=self._bucle, name="visor-previa", daemon=True)
            self._hilo.start()

    def parar(self) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(2.0)
        self.cerrar_ventana()

    def _bucle(self) -> None:
        while not self._parar.is_set():
            self.actualizar()
            self._parar.wait(self._periodo)

    def actualizar(self) -> None:
        """Una pasada de la vista previa: pide la vista a la fuente y compone la imagen. Nunca lanza."""
        try:
            vista = self.fuente.vista_previa()
            imagen = self._componer_previa(vista)
            self._aviso_error = None
        except Exception as e:   # noqa: BLE001 - un fallo de la camara no debe tirar el visor
            imagen = _con_banda(_lienzo("sin imagen"), f"error: {e}"[:110], ROJO)
            if str(e) != self._aviso_error:
                self._aviso_error = str(e)
                print(f"Visor: {e}")
        with self._cerrojo:
            self._previa = imagen

    def _componer_previa(self, vista) -> np.ndarray:
        if vista is None:
            return _con_banda(_lienzo("sin camara"), "sin camara configurada", ROJO)
        if vista.fotograma is None:
            return _con_banda(_lienzo("no quedan fotos"), _donde(vista) + "  |  sin mas fotos", ROJO)
        img = dibujar(vista.fotograma.bgr, vista.detecciones, vista.elegida)
        if vista.elegida is None:
            return _con_banda(img, _donde(vista) + "  |  VISTA PREVIA: no veo ninguna caja entera", ROJO)
        return _con_banda(img, _donde(vista) + "  |  VISTA PREVIA", BLANCO)

    # ---------------------------------------------------------------- resultado de cada caja (lo llama FuenteCamara.leer)
    def al_medir(self, fotograma, detecciones, elegida, i: int) -> None:
        img = dibujar(fotograma.bgr, detecciones, elegida)
        texto = f"CAJA {i + 1}: MEDIDA  |  {elegida.largo:.0f}x{elegida.ancho:.0f}x{elegida.alto:.0f} mm, giro {elegida.giro_deg:.0f}"
        imagen = _con_banda(img, texto, VERDE)
        with self._cerrojo:
            self._medida = (imagen, self._reloj() + MEDIDA_S)

    # ---------------------------------------------------------------- lo que se ve
    def imagen_actual(self) -> np.ndarray | None:
        """El resultado de la ultima caja medida si es reciente; si no, la vista previa."""
        with self._cerrojo:
            if self._medida is not None and self._reloj() < self._medida[1]:
                return self._medida[0]
            return self._previa

    def bombear(self) -> bool:
        """Dibuja la ventana y atiende el teclado. Hay que llamarla desde el hilo principal. Devuelve False si no hay (o ya no hay) ventana."""
        if not self.mostrar or self.sin_pantalla or self._cerrada:
            return False
        imagen = self.imagen_actual()
        if imagen is None:
            return True
        try:
            cv2.imshow(self.titulo, imagen)
            self._ventana_abierta = True
            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), 27) or cv2.getWindowProperty(self.titulo, cv2.WND_PROP_VISIBLE) < 1:
                self.cerrar_ventana()
                self._cerrada = True
                return False
        except cv2.error as e:
            self.sin_pantalla = True
            print(f"Visor: no puedo abrir la ventana ({str(e).splitlines()[0][:100]}). Sigo sin ventana.")
            return False
        return True

    def cerrar_ventana(self) -> None:
        if self._ventana_abierta:
            try:
                cv2.destroyWindow(self.titulo)
                cv2.waitKey(1)
            except cv2.error:
                pass
            self._ventana_abierta = False


def crear_visor(fuente, cfg):
    """El visor si la configuracion lo pide (camara.visor = true) y la fuente es una camara; si no, None."""
    camara = getattr(cfg, "camara", None) or {}
    if not camara.get("visor") or not hasattr(fuente, "vista_previa"):
        return None
    return Visor(fuente)


def ejecutar_con_visor(funcion, visor, mantener_s: float = 3.0) -> None:
    """Ejecuta `funcion` (el ciclo) en un hilo y bombea la ventana del visor en el principal hasta que acabe; la ventana se queda `mantener_s`
    segundos mas para ver la ultima imagen. Si `funcion` falla, se relanza el error en el hilo principal."""
    resultado: dict = {}

    def trabajo():
        try:
            funcion()
        except BaseException as e:   # noqa: BLE001 - se relanza abajo
            resultado["error"] = e

    visor.iniciar()
    hilo = threading.Thread(target=trabajo, name="ciclo-celda", daemon=True)
    hilo.start()
    try:
        while hilo.is_alive():
            if not visor.bombear():
                hilo.join(0.05)
            else:
                time.sleep(0.03)
        fin = time.monotonic() + mantener_s
        while time.monotonic() < fin and visor.bombear():
            time.sleep(0.03)
    finally:
        visor.parar()
    if "error" in resultado:
        raise resultado["error"]
