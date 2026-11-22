"""Asistente con ventana para calibrar la cámara (webcam o la de la celda), paso a paso y con la imagen en vivo.

    python -m calibracion.app_camara                       (Windows: & "C:\\Program Files\\Python311\\python.exe" -m calibracion.app_camara --indice 1)
    python -m calibracion.app_camara --indice 1 --salida celda/camara_webcam.json

Cuatro pestañas:
  1 Tablero      el tablero de ajedrez que se imprime (columnas, filas y lado del cuadro medido con una regla).
  2 Cámara       «intrínsecos»: unas 15 fotos del tablero en distintas posiciones e inclinaciones (a mano o en automático) y calcular.
  3 Posición     con la cámara FIJA y el tablero tendido sobre la superficie donde irán las cajas: en casa se dice qué punto del robot es el centro
                 del tablero (700, 0 = la recogida); con el robot se dan las esquinas tocadas y sus x, y.
  4 Probar       la cámara en vivo con las cajas que identifica (contorno, centro, hilo) y las coordenadas en el robot de cada punto en el que
                 pinches; y guardar el camara.json que usa la celda.

La lógica está en `calibracion.asistente` (sin ventana); aquí solo la ventana (Tkinter, que ya trae Python) y la cámara en un hilo.
"""
from __future__ import annotations

import argparse
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibracion.asistente import FOTOS_RECOMENDADAS, Asistente  # noqa: E402
from calibracion.camara import Toque, guardar_tablero  # noqa: E402
from vision.deteccion import detectar_cajas, dibujar, elegir, ordenar  # noqa: E402
from vision.proveedores import abrir_camara_usb  # noqa: E402

TICK_MS = 40
PERIODO_DETECCION_S = 0.15
ESTABLE_PX = 2.0                 # el tablero se considera quieto si sus esquinas se mueven menos de esto entre dos detecciones
ESTABLE_VECES = 6                # ...durante este número de detecciones seguidas (~1 s): en automático, se guarda sola la foto
ESPERA_TRAS_FOTO_S = 1.5
ANCHO_MAX, ALTO_MAX = 800, 600   # tamaño máximo de la imagen en la ventana
VERDE, ROJO, AMARILLO = (0, 200, 0), (0, 0, 255), (0, 255, 255)
PESTANAS = ("1  Tablero", "2  Cámara", "3  Posición", "4  Probar y guardar")

TEXTO_TABLERO = (
    "El tablero es un tablero de ajedrez que se IMPRIME. Pulsa «Guardar tablero para imprimir», imprímelo AL 100 % (sin «ajustar a la página») y "
    "pégalo sobre algo plano y rígido (cartón, una tabla). Después MIDE con una regla el lado de un cuadro de tu impresión y escríbelo en mm: "
    "de ese número depende toda la escala."
)
TEXTO_CAMARA = (
    "La cámara FIJA donde va a trabajar. Muestra el tablero entero y, con Espacio o el botón, guarda fotos MOVIÉNDOLO e INCLINÁNDOLO "
    f"(como una hoja medio levantada): unas {FOTOS_RECOMENDADAS}, llevándolo a los bordes y a las esquinas de la imagen. En «Automático» "
    "guarda sola cada foto cuando el tablero se queda quieto. Luego «Calcular»."
)
TEXTO_POSICION = (
    "Deja la cámara FIJA como va a trabajar (no la muevas después) y tiende el tablero PLANO sobre la superficie donde irán las cajas, entero "
    "en la imagen. EN CASA decide qué punto del robot es el centro del tablero (la recogida es 700, 0) y cuánto está girado (0 = derecho en la "
    "imagen). CON EL ROBOT toca esquinas con el TCP y escribe cada una: «columna,fila:x,y» (una por línea; con una «v » delante, la esquina sirve "
    "para validar y no entra en el ajuste)."
)
TEXTO_PROBAR = (
    "Prueba: la cámara ya calibrada. Pon una caja en la superficie: debe salir su contorno, el centro con sus coordenadas en el robot (mm) y el "
    "hilo. Pincha en la imagen para ver las coordenadas de ese punto. Si es lo que esperas, guarda el camara.json: es el que usa la celda."
)


class Captura:
    """Lee la cámara en un hilo y guarda el último fotograma (la ventana nunca espera a la cámara)."""

    def __init__(self, proveedor, pausa_s: float = 0.0):
        self.proveedor = proveedor
        self._pausa = pausa_s
        self._bloqueo = threading.Lock()
        self._ultimo: np.ndarray | None = None
        self._parar = threading.Event()
        self.error: str | None = None
        self._hilo = threading.Thread(target=self._bucle, name="captura-camara", daemon=True)
        self._hilo.start()

    def _bucle(self) -> None:
        fallos = 0
        while not self._parar.is_set():
            try:
                fot = self.proveedor.siguiente()
            except Exception as e:   # noqa: BLE001 - la cámara puede desconectarse
                self.error = str(e)
                return
            if fot is None:
                fallos += 1
                if fallos > 50:
                    self.error = "la cámara ha dejado de dar imágenes"
                    return
                time.sleep(0.02)
                continue
            fallos = 0
            with self._bloqueo:
                self._ultimo = fot.bgr
            if self._pausa:
                time.sleep(self._pausa)

    def ultimo(self) -> np.ndarray | None:
        with self._bloqueo:
            return None if self._ultimo is None else self._ultimo.copy()

    def cerrar(self) -> None:
        self._parar.set()
        self._hilo.join(2.0)
        cerrar = getattr(self.proveedor, "cerrar", None)
        if cerrar is not None:
            try:
                cerrar()
            except Exception:   # noqa: BLE001
                pass


def a_ppm(bgr: np.ndarray) -> bytes:
    """La imagen como PPM, que Tk lee sin librerías (más rápido que PNG)."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return b"P6 %d %d 255\n" % (rgb.shape[1], rgb.shape[0]) + rgb.tobytes()


def parsear_toques(texto: str) -> tuple[list[Toque], list[Toque]]:
    """Las líneas «columna,fila:x,y» (ajuste) o «v columna,fila:x,y» (validación) del cuadro de texto del robot."""
    toques, validacion = [], []
    for n, linea in enumerate(texto.splitlines(), start=1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        es_validacion = linea[:2].lower() in ("v ", "v\t")
        try:
            t = Toque.desde_texto(linea[2:].strip() if es_validacion else linea)
        except ValueError as e:
            raise ValueError(f"línea {n}: {e}") from None
        (validacion if es_validacion else toques).append(t)
    return toques, validacion


class App(tk.Tk):
    def __init__(self, proveedor=None, indice: int = 0, tam: tuple[int, int] | None = (1280, 720), salida: str = "celda/camara_webcam.json",
                 columnas: int = 9, filas: int = 6, cuadro_mm: float = 25.0, pausa_captura_s: float = 0.0):
        super().__init__()
        self.title("Calibración de la cámara")
        self.asistente = Asistente(columnas, filas, cuadro_mm)
        self.captura: Captura | None = None
        self._tam_pedido = tam
        self._pausa_captura = pausa_captura_s
        self._cola: queue.Queue = queue.Queue()
        self._pendientes = 0
        self._esq_vivas: np.ndarray | None = None
        self._t_deteccion = 0.0
        self._detectando = False
        self._estable = 0
        self._ultima_esq: np.ndarray | None = None
        self._t_ultima_foto = 0.0
        self._guardando = False
        self._dets: list = []
        self._foto_tk = None
        self._escala = 1.0
        self._vista_tam = (1, 1)
        self._mensaje = tk.StringVar(value="")
        self._construir(indice, salida)
        self._abrir(proveedor, indice)
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.bind("<space>", lambda e: self._guardar_foto() if self._pestana() == 1 else None)
        self.after(TICK_MS, self._tick)

    # ---------------------------------------------------------------- ventana
    def _construir(self, indice: int, salida: str) -> None:
        sup = ttk.Frame(self)
        sup.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Label(sup, text="Cámara (índice):").pack(side="left")
        self.v_indice = tk.IntVar(value=indice)
        ttk.Spinbox(sup, from_=0, to=9, width=4, textvariable=self.v_indice).pack(side="left", padx=4)
        ttk.Button(sup, text="Abrir", command=lambda: self._abrir(None, self.v_indice.get())).pack(side="left")
        ttk.Button(sup, text="¿Cuál es cuál?", command=self._cual_es_cual).pack(side="left", padx=8)
        self.l_resolucion = ttk.Label(sup, text="")
        self.l_resolucion.pack(side="left", padx=8)

        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill="both", expand=True, padx=8, pady=8)
        self.canvas = tk.Canvas(cuerpo, width=ANCHO_MAX, height=ALTO_MAX, bg="#202020", highlightthickness=0)
        self.canvas.pack(side="left")
        self.canvas.bind("<Button-1>", self._pinchar)
        derecha = ttk.Frame(cuerpo)
        derecha.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.nb = ttk.Notebook(derecha)
        self.nb.pack(fill="both", expand=True)
        self.paginas = [ttk.Frame(self.nb, padding=8) for _ in PESTANAS]
        for p, t in zip(self.paginas, PESTANAS):
            self.nb.add(p, text=t)
        self._pestana_tablero(self.paginas[0])
        self._pestana_camara(self.paginas[1])
        self._pestana_posicion(self.paginas[2], )
        self._pestana_probar(self.paginas[3], salida)
        self.l_mensaje = ttk.Label(self, textvariable=self._mensaje, anchor="w", relief="sunken", padding=4)
        self.l_mensaje.pack(fill="x", side="bottom")

    @staticmethod
    def _texto(padre, texto: str) -> None:
        ttk.Label(padre, text=texto, wraplength=330, justify="left").pack(anchor="w", pady=(0, 8))

    def _pestana_tablero(self, p) -> None:
        self._texto(p, TEXTO_TABLERO)
        fila = ttk.Frame(p)
        fila.pack(anchor="w")
        a = self.asistente.tablero
        self.v_columnas, self.v_filas, self.v_cuadro = tk.IntVar(value=a.columnas), tk.IntVar(value=a.filas), tk.StringVar(value=f"{a.cuadro_mm:g}")
        for texto, var, ancho in (("Columnas", self.v_columnas, 4), ("Filas", self.v_filas, 4), ("Cuadro (mm)", self.v_cuadro, 7)):
            ttk.Label(fila, text=texto).pack(side="left")
            ttk.Entry(fila, textvariable=var, width=ancho).pack(side="left", padx=(2, 10))
        ttk.Button(p, text="Aplicar el tablero", command=self._aplicar_tablero).pack(anchor="w", pady=6)
        ttk.Button(p, text="Guardar tablero para imprimir…", command=self._guardar_tablero_para_imprimir).pack(anchor="w")
        self.l_aviso_tablero = ttk.Label(p, text="", wraplength=330, foreground="#b00000")
        self.l_aviso_tablero.pack(anchor="w", pady=6)

    def _pestana_camara(self, p) -> None:
        self._texto(p, TEXTO_CAMARA)
        self.l_fotos = ttk.Label(p, text="", font=("TkDefaultFont", 11, "bold"))
        self.l_fotos.pack(anchor="w")
        self.l_consejo = ttk.Label(p, text="", wraplength=330, justify="left")
        self.l_consejo.pack(anchor="w", pady=4)
        fila = ttk.Frame(p)
        fila.pack(anchor="w", pady=4)
        ttk.Button(fila, text="Guardar foto (Espacio)", command=self._guardar_foto).pack(side="left")
        self.v_auto = tk.BooleanVar(value=False)
        ttk.Checkbutton(fila, text="Automático", variable=self.v_auto).pack(side="left", padx=8)
        fila2 = ttk.Frame(p)
        fila2.pack(anchor="w", pady=4)
        ttk.Button(fila2, text="Quitar la última", command=self._quitar_ultima).pack(side="left")
        ttk.Button(fila2, text="Borrar todas", command=self._borrar_fotos).pack(side="left", padx=6)
        ttk.Button(p, text="Calcular los intrínsecos", command=self._calcular_intrinsecos).pack(anchor="w", pady=6)
        self.l_resultado_int = ttk.Label(p, text="", wraplength=330, justify="left")
        self.l_resultado_int.pack(anchor="w")
        ttk.Separator(p).pack(fill="x", pady=8)
        ttk.Button(p, text="Usar los intrínsecos de un camara.json anterior…", command=self._cargar_intrinsecos).pack(anchor="w")
        ttk.Label(p, text="(si solo has movido la cámara: ya no hace falta repetir las fotos)", wraplength=330).pack(anchor="w", pady=(0, 6))
        ttk.Label(p, text="Sin fotos (menos preciso): solo el campo de visión").pack(anchor="w")
        fila3 = ttk.Frame(p)
        fila3.pack(anchor="w", pady=4)
        self.v_fov = tk.StringVar(value="62")
        ttk.Entry(fila3, textvariable=self.v_fov, width=6).pack(side="left")
        ttk.Label(fila3, text="° horizontal (una webcam: 60-70)").pack(side="left", padx=4)
        ttk.Button(fila3, text="Usar", command=self._usar_fov).pack(side="left", padx=6)

    def _pestana_posicion(self, p) -> None:
        self._texto(p, TEXTO_POSICION)
        self.v_modo = tk.StringVar(value="casa")
        ttk.Radiobutton(p, text="En casa (decido dónde está el tablero)", variable=self.v_modo, value="casa").pack(anchor="w")
        fila = ttk.Frame(p)
        fila.pack(anchor="w", pady=4)
        self.v_cx, self.v_cy, self.v_giro, self.v_z = (tk.StringVar(value=v) for v in ("700", "0", "0", "220"))
        for texto, var in (("Centro X", self.v_cx), ("Y", self.v_cy), ("Giro °", self.v_giro), ("Altura z", self.v_z)):
            ttk.Label(fila, text=texto).pack(side="left")
            ttk.Entry(fila, textvariable=var, width=6).pack(side="left", padx=(2, 8))
        ttk.Radiobutton(p, text="Con el robot (esquinas tocadas)", variable=self.v_modo, value="robot").pack(anchor="w", pady=(8, 0))
        self.t_toques = tk.Text(p, width=36, height=5)
        self.t_toques.pack(anchor="w")
        self.t_toques.insert("1.0", "0,0:700,-100\n8,0:700,100\n0,5:550,-100\nv 8,5:550,100")
        ttk.Button(p, text="Calcular la posición de la cámara", command=self._calcular_posicion).pack(anchor="w", pady=8)
        self.t_resultado_pos = tk.Text(p, width=36, height=9, state="disabled", wrap="word")
        self.t_resultado_pos.pack(anchor="w")

    def _pestana_probar(self, p, salida: str) -> None:
        self._texto(p, TEXTO_PROBAR)
        fila = ttk.Frame(p)
        fila.pack(anchor="w")
        ttk.Label(fila, text="Alto de la caja (mm)").pack(side="left")
        self.v_alto = tk.StringVar(value="120")
        ttk.Entry(fila, textvariable=self.v_alto, width=6).pack(side="left", padx=6)
        self.v_marcar = tk.BooleanVar(value=True)
        ttk.Checkbutton(fila, text="Marcar cajas", variable=self.v_marcar).pack(side="left", padx=6)
        self.l_pinchado = ttk.Label(p, text="Pincha en la imagen para ver sus coordenadas.", wraplength=330, justify="left")
        self.l_pinchado.pack(anchor="w", pady=8)
        ttk.Label(p, text="Guardar el camara.json en:").pack(anchor="w")
        fila2 = ttk.Frame(p)
        fila2.pack(anchor="w", fill="x")
        self.v_salida = tk.StringVar(value=salida)
        ttk.Entry(fila2, textvariable=self.v_salida, width=34).pack(side="left")
        ttk.Button(fila2, text="…", width=3, command=self._elegir_salida).pack(side="left", padx=4)
        ttk.Button(p, text="Guardar la calibración", command=self._guardar).pack(anchor="w", pady=8)
        self.l_uso = ttk.Label(p, text="", wraplength=330, justify="left")
        self.l_uso.pack(anchor="w")

    # ---------------------------------------------------------------- utilidades
    def _pestana(self) -> int:
        return self.nb.index(self.nb.select())

    def decir(self, texto: str, error: bool = False) -> None:
        self._mensaje.set(texto)
        self.l_mensaje.configure(foreground="#b00000" if error else "#000000")

    def _lanzar(self, trabajo, al_acabar) -> None:
        """Corre `trabajo()` en un hilo; su resultado (o su excepción) llega a `al_acabar(resultado, error)` en el hilo de la ventana."""
        self._pendientes += 1

        def corre():
            try:
                self._cola.put((al_acabar, trabajo(), None))
            except Exception as e:   # noqa: BLE001 - se enseña en la ventana
                self._cola.put((al_acabar, None, e))
        threading.Thread(target=corre, daemon=True).start()

    def _vaciar_cola(self) -> None:
        while True:
            try:
                al_acabar, resultado, error = self._cola.get_nowait()
            except queue.Empty:
                return
            self._pendientes -= 1
            al_acabar(resultado, error)

    # ---------------------------------------------------------------- cámara
    def _abrir(self, proveedor, indice: int) -> None:
        if self.captura is not None:
            self.captura.cerrar()
            self.captura = None
        try:
            if proveedor is None:
                proveedor = abrir_camara_usb(int(indice), self._tam_pedido)
            self.captura = Captura(proveedor, self._pausa_captura)
        except ValueError as e:
            self.decir(f"{e}. Prueba otro índice (¿Cuál es cuál?), cierra los programas que usen la cámara y mira el permiso de cámara de Windows.", True)
            return
        self.decir(f"Cámara {indice} abierta.")

    def _cual_es_cual(self) -> None:
        """Una ventana con la imagen de cada cámara y su número (cierra la actual un momento)."""
        from vision.ver_camara import listar_camaras, mosaico_de_camaras
        if self.captura is not None:
            self.captura.cerrar()
            self.captura = None
        halladas = listar_camaras()
        if not halladas:
            self.decir("Ninguna cámara abre (índices 0 a 4). ¿Está conectada? ¿La usa otro programa?", True)
            return
        mosaico = mosaico_de_camaras([i for i, _ in halladas])
        top = tk.Toplevel(self)
        top.title("Cámaras: elige el número")
        foto = tk.PhotoImage(data=a_ppm(mosaico))
        etiqueta = tk.Label(top, image=foto)
        etiqueta.image = foto
        etiqueta.pack()
        ttk.Label(top, text="El número de cada cámara está en su esquina. Ciérrala y escribe el número en «Cámara (índice)» y pulsa Abrir.",
                  wraplength=600).pack(pady=6)
        self.decir("Cámaras que abren: " + ", ".join(f"{i} ({w}x{h})" for i, (w, h) in halladas))

    # ---------------------------------------------------------------- pestaña 1: tablero
    def _aplicar_tablero(self) -> bool:
        try:
            self.asistente.configurar_tablero(self.v_columnas.get(), self.v_filas.get(), float(self.v_cuadro.get().replace(",", ".")))
        except (ValueError, tk.TclError) as e:
            self.decir(f"Tablero no válido: {e}", True)
            return False
        self.l_aviso_tablero.configure(text=self.asistente.aviso_tablero)
        self.decir(f"Tablero de {self.asistente.tablero.columnas}x{self.asistente.tablero.filas} esquinas, cuadro de {self.asistente.tablero.cuadro_mm:g} mm.")
        self._actualizar_fotos()
        return True

    def _guardar_tablero_para_imprimir(self) -> None:
        if not self._aplicar_tablero():
            return
        ruta = filedialog.asksaveasfilename(title="Guardar el tablero", defaultextension=".png", initialfile="tablero.png", filetypes=[("PNG", "*.png")])
        if ruta:
            guardar_tablero(self.asistente.tablero, ruta)
            self.decir(f"Tablero guardado en {ruta}: imprímelo al 100 % y mide un cuadro con una regla.")

    # ---------------------------------------------------------------- pestaña 2: intrínsecos
    def _actualizar_fotos(self) -> None:
        r = self.asistente.resumen()
        self.l_fotos.configure(text=f"Fotos: {r.n} de {r.recomendadas}   (zonas de la imagen: {r.celdas_cubiertas}/9, inclinadas: {r.inclinadas})")
        self.l_consejo.configure(text=r.consejo)

    def _guardar_foto(self) -> None:
        if self._guardando or self.captura is None:
            return
        frame = self.captura.ultimo()
        if frame is None:
            self.decir("La cámara aún no da imagen.", True)
            return
        self._guardando = True
        self.decir("Guardando la foto (detección precisa, un momento)...")
        self._lanzar(lambda: self.asistente.guardar_foto(frame), self._foto_guardada)

    def _foto_guardada(self, resultado, error) -> None:
        self._guardando = False
        self._t_ultima_foto = time.monotonic()
        if error is not None:
            self.decir(f"Error: {error}", True)
            return
        ok, motivo = resultado
        self.decir(motivo.capitalize() if ok else motivo, not ok)
        self._actualizar_fotos()

    def _quitar_ultima(self) -> None:
        self.decir("Última foto quitada." if self.asistente.quitar_ultima() else "No hay fotos.")
        self._actualizar_fotos()

    def _borrar_fotos(self) -> None:
        self.asistente.borrar_fotos()
        self.decir("Fotos borradas.")
        self._actualizar_fotos()

    def _calcular_intrinsecos(self) -> None:
        if self._aplicar_tablero() is False:
            return
        self.decir("Calculando los intrínsecos...")
        self._lanzar(self.asistente.calcular_intrinsecos, self._intrinsecos_calculados)

    def _intrinsecos_calculados(self, informe, error) -> None:
        if error is not None:
            self.decir(str(error), True)
            return
        veredicto = Asistente.veredicto_intrinsecos(informe.rms_px)
        self.l_resultado_int.configure(text=f"Error medio {informe.rms_px:.2f} píxeles con {informe.n_usadas} fotos: {veredicto}. "
                                            f"Imagen de {informe.tam[0]}x{informe.tam[1]}. Siguiente: pestaña 3.")
        self.decir(f"Intrínsecos calculados: {informe.rms_px:.2f} px ({veredicto}).", informe.rms_px >= 1.0)

    def _cargar_intrinsecos(self, ruta: str | None = None) -> None:
        ruta = ruta or filedialog.askopenfilename(title="camara.json anterior", filetypes=[("camara.json", "*.json")])
        if not ruta:
            return
        try:
            self.asistente.usar_intrinsecos_de(ruta)
        except ValueError as e:
            self.decir(str(e), True)
            return
        tam = self.asistente.tam
        self.l_resultado_int.configure(text=f"Se usan los intrínsecos de {Path(ruta).name} (imagen de {tam[0]}x{tam[1]}). Siguiente: pestaña 3.")
        self.decir(f"Intrínsecos cargados de {ruta}.")

    def _usar_fov(self) -> None:
        frame = self.captura.ultimo() if self.captura is not None else None
        if frame is None:
            self.decir("Abre la cámara primero.", True)
            return
        try:
            fov = float(self.v_fov.get().replace(",", "."))
            if not 20.0 <= fov <= 140.0:
                raise ValueError
        except ValueError:
            self.decir("El campo de visión son grados, entre 20 y 140.", True)
            return
        self.asistente.usar_campo_de_vision((frame.shape[1], frame.shape[0]), fov)
        self.l_resultado_int.configure(text=f"Se usa solo el campo de visión de {fov:g}° (sin distorsión: menos preciso). Siguiente: pestaña 3.")
        self.decir("Intrínsecos aproximados con el campo de visión.")

    # ---------------------------------------------------------------- pestaña 3: posición
    def _escribir_resultado(self, texto: str) -> None:
        self.t_resultado_pos.configure(state="normal")
        self.t_resultado_pos.delete("1.0", "end")
        self.t_resultado_pos.insert("1.0", texto)
        self.t_resultado_pos.configure(state="disabled")

    def _calcular_posicion(self) -> None:
        if self._aplicar_tablero() is False:
            return
        frame = self.captura.ultimo() if self.captura is not None else None
        if frame is None:
            self.decir("Abre la cámara primero.", True)
            return
        try:
            z = float(self.v_z.get().replace(",", "."))
            if self.v_modo.get() == "casa":
                cx, cy, giro = (float(v.get().replace(",", ".")) for v in (self.v_cx, self.v_cy, self.v_giro))
                toques, validacion = self.asistente.toques_en_casa(cx, cy, giro)
            else:
                toques, validacion = parsear_toques(self.t_toques.get("1.0", "end"))
        except ValueError as e:
            self.decir(f"Datos no válidos: {e}", True)
            return
        self.decir("Calculando la posición de la cámara...")
        self._lanzar(lambda: self.asistente.calcular_posicion(frame, z, toques, validacion), self._posicion_calculada)

    def _posicion_calculada(self, resultado, error) -> None:
        if error is not None:
            self._escribir_resultado(str(error))
            self.decir(str(error), True)
            return
        modelo, inf = resultado
        o = modelo.posicion
        lineas = [f"Cámara en la base: x {o[0]:.0f}, y {o[1]:.0f}, z {o[2]:.0f} mm.",
                  f"Reproyección del tablero: {inf.rms_px:.2f} px.",
                  f"Puntos del ajuste: {inf.rms_toques_mm:.2f} mm."]
        if inf.rms_validacion_mm is not None:
            lineas.append(f"VALIDACIÓN: error {inf.rms_validacion_mm:.2f} mm (máximo {inf.max_validacion_mm:.2f}).")
        lineas.append(f"Criterio: {inf.criterio.upper()} (objetivo < 2 mm, aceptable < 5 mm).")
        lineas += [f"AVISO: {a}" for a in inf.avisos]
        self._escribir_resultado("\n".join(lineas))
        self.decir(f"Posición calculada: {inf.criterio}." + (" Repite con el tablero bien tendido y entero." if inf.criterio == "repetir" else
                                                              " Pasa a la pestaña 4 para probarla y guardarla."), inf.criterio == "repetir")

    # ---------------------------------------------------------------- pestaña 4: probar y guardar
    def _pinchar(self, ev) -> None:
        modelo = self.asistente.modelo
        if modelo is None or self._pestana() != 3:
            return
        px = np.array([[ev.x / self._escala, ev.y / self._escala]])
        try:
            z = float(self.v_z.get().replace(",", "."))
            x, y = modelo.pixel_a_plano(px, z)[0]
        except ValueError as e:
            self.l_pinchado.configure(text=f"No se puede medir ahí: {e}")
            return
        self.l_pinchado.configure(text=f"Ese punto está en x = {x:.0f} mm, y = {y:.0f} mm del robot (a z = {z:g} mm).")

    def _elegir_salida(self) -> None:
        ruta = filedialog.asksaveasfilename(title="Guardar la calibración", defaultextension=".json", initialfile=Path(self.v_salida.get()).name,
                                            filetypes=[("camara.json", "*.json")])
        if ruta:
            self.v_salida.set(ruta)

    def _guardar(self) -> None:
        try:
            ruta = self.asistente.guardar(self.v_salida.get())
        except (ValueError, OSError) as e:
            self.decir(str(e), True)
            return
        tam = self.asistente.tam
        self.l_uso.configure(text=(f"Guardada en {ruta} ({tam[0]}x{tam[1]}). Úsala en la celda poniendo en el JSON de la celda "
                                   f"camara.calibracion = esa ruta y origen.tam = [{tam[0]}, {tam[1]}]; y para verla: "
                                   f"python -m vision.ver_camara --calibracion {ruta} --z {self.v_z.get()}"))
        self.decir(f"Calibración guardada en {ruta}.")

    # ---------------------------------------------------------------- imagen en vivo
    def _detectar(self, frame: np.ndarray, pestana: int) -> None:
        """Lanza (si no hay otra en marcha) la detección que toca en esta pestaña: el tablero (2 y 3) o las cajas (4)."""
        if self._detectando or time.monotonic() - self._t_deteccion < PERIODO_DETECCION_S:
            return
        self._detectando = True
        self._t_deteccion = time.monotonic()
        if pestana == 3:
            modelo = self.asistente.modelo
            if modelo is None or not self.v_marcar.get():
                self._detectando = False
                self._dets = []
                return
            try:
                z, alto = float(self.v_z.get().replace(",", ".")), float(self.v_alto.get().replace(",", "."))
            except ValueError:
                self._detectando = False
                return
            self._lanzar(lambda: ordenar(detectar_cajas(frame, modelo, z, alto, {"modo": "color"}))[:1], self._cajas_detectadas)
        elif pestana in (1, 2):
            self._lanzar(lambda: self.asistente.esquinas_rapidas(frame), self._tablero_detectado)
        else:
            self._detectando = False

    def _cajas_detectadas(self, dets, error) -> None:
        self._detectando = False
        self._dets = [] if error is not None else dets

    def _tablero_detectado(self, esq, error) -> None:
        self._detectando = False
        esq = None if error is not None else esq
        if esq is not None and self._ultima_esq is not None and float(np.max(np.linalg.norm(esq - self._ultima_esq, axis=1))) < ESTABLE_PX:
            self._estable += 1
        else:
            self._estable = 0
        self._ultima_esq, self._esq_vivas = esq, esq
        if (self.v_auto.get() and self._pestana() == 1 and esq is not None and self._estable >= ESTABLE_VECES and not self._guardando
                and time.monotonic() - self._t_ultima_foto > ESPERA_TRAS_FOTO_S):
            self._estable = 0
            self._guardar_foto()

    def _vista(self, frame: np.ndarray, pestana: int) -> np.ndarray:
        vista = frame.copy()
        if pestana in (1, 2):
            t = self.asistente.tablero
            if self._esq_vivas is not None:
                cv2.drawChessboardCorners(vista, (t.columnas, t.filas), self._esq_vivas.astype(np.float32).reshape(-1, 1, 2), True)
                texto, color = "tablero detectado" + (" (quieto)" if self._estable >= ESTABLE_VECES else ""), VERDE
            else:
                texto, color = "no veo el tablero entero", ROJO
            cv2.putText(vista, texto, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(vista, texto, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
        elif pestana == 3:
            if self.asistente.modelo is None:
                cv2.putText(vista, "calcula antes la posicion (pestana 3)", (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, ROJO, 2, cv2.LINE_AA)
            elif self._dets:
                vista = dibujar(vista, self._dets, self._dets[0])
        return vista

    def _tick(self) -> None:
        try:
            self._vaciar_cola()
            if self.captura is not None:
                if self.captura.error:
                    self.decir(f"La cámara falla: {self.captura.error}", True)
                    self.captura.cerrar()
                    self.captura = None
                else:
                    frame = self.captura.ultimo()
                    if frame is not None:
                        pestana = self._pestana()
                        self._detectar(frame, pestana)
                        self._mostrar(self._vista(frame, pestana))
                        self.l_resolucion.configure(text=f"imagen de {frame.shape[1]}x{frame.shape[0]}")
            if self._pestana() == 1:
                self._actualizar_fotos()
        finally:
            if self.winfo_exists():
                self.after(TICK_MS, self._tick)

    def _mostrar(self, bgr: np.ndarray) -> None:
        alto, ancho = bgr.shape[:2]
        self._escala = min(ANCHO_MAX / ancho, ALTO_MAX / alto, 1.0)
        if self._escala < 1.0:
            bgr = cv2.resize(bgr, (round(ancho * self._escala), round(alto * self._escala)), interpolation=cv2.INTER_AREA)
        self._foto_tk = tk.PhotoImage(data=a_ppm(bgr))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self._foto_tk, anchor="nw")

    def cerrar(self) -> None:
        if self.captura is not None:
            self.captura.cerrar()
            self.captura = None
        self.destroy()


def _tam(texto: str) -> tuple[int, int]:
    try:
        ancho, alto = (int(v) for v in texto.lower().split("x"))
        return ancho, alto
    except ValueError:
        raise argparse.ArgumentTypeError(f"el tamaño se escribe ancho x alto, por ejemplo 1280x720 (y es {texto!r})") from None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--indice", type=int, default=0, help="cámara que se abre al empezar (se cambia en la ventana)")
    ap.add_argument("--tam", type=_tam, default=(1280, 720), help="resolución pedida a la cámara (la misma que usará la celda)")
    ap.add_argument("--salida", default="celda/camara_webcam.json", help="dónde se guarda el camara.json")
    ap.add_argument("--columnas", type=int, default=9)
    ap.add_argument("--filas", type=int, default=6)
    ap.add_argument("--cuadro", type=float, default=25.0, help="lado del cuadro del tablero en mm (el que mides en tu impresión)")
    args = ap.parse_args(argv)
    try:
        app = App(None, args.indice, args.tam, args.salida, args.columnas, args.filas, args.cuadro)
    except tk.TclError as e:
        print(f"No puedo abrir la ventana: {e}")
        return 2
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
