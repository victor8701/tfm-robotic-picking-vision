"""Ver la cámara en vivo con lo que el programa identifica, sin robot, sin RAPID y sin la app.

Abre una cámara (la webcam del PC, USB...) y enseña la ventana «Vision de la celda» en tiempo real: la imagen, el contorno de lo que considera
la caja, el centro (punto verde con sus coordenadas), el hilo de lado corto a lado corto por el centro y las medidas. Es el paso previo a usar
la cámara en la celda: comprueba que se ve, que se detecta la caja y con qué rango de color.

Uso (en Windows, desde la carpeta robotica):
    python -m vision.ver_camara --listar                           qué cámaras abren y a qué resolución, y las que ve Windows
    python -m vision.ver_camara --listar --ver                     además, una ventana con la imagen de cada una para saber cuál es cuál
    python -m vision.ver_camara --indice 0 --alto 120              la cámara 0, con cajas de 120 mm de alto
    python -m vision.ver_camara --url https://MI-SERVICIO.onrender.com/c/MI-CLAVE --alto 120
                                                                   la cámara de un móvil por la página propia (movil_camara): la misma dirección
                                                                   que se abre en el teléfono. También vale el vídeo de una app («IP Webcam»...)
    python -m vision.ver_camara --altura 700 --fov 62 --alto 120   con la altura de la cámara sobre la mesa y su campo de visión
    python -m vision.ver_camara --cajas 3                          identifica hasta 3 cajas a la vez (por defecto, 1: la mejor)
    python -m vision.ver_camara --calibracion camara.json --z 220  con la calibración de la celda (medidas reales en la base del robot)
    python -m vision.ver_camara --altura 700 --guardar-calibracion celda/camara_webcam.json --z 220 --centro 700,0
                                                                   además, guarda esa cámara cenital aproximada como camara.json para probar
                                                                   la celda con la webcam: el centro de la imagen cae en el punto --centro de la
                                                                   base del robot (la recogida) y el plano de la cinta a --z; ver docs/vision.md

Sin `--calibracion` se supone una cámara cenital (mirando hacia abajo) a `--altura` mm sobre la mesa: las medidas en mm son aproximadas (la
banda de la ventana pone «SIN CALIBRAR»), pero el contorno, el centro y el hilo en la imagen valen. Una webcam no mide profundidad: el alto de la
caja se da con `--alto`. Se sale con la tecla q o cerrando la ventana.

Códigos de salida: 0 bien; 2 datos incorrectos o la cámara no abre.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

import cv2
import numpy as np

from vision.camara import ModeloCamara, modelo_cenital_aproximado
from vision.proveedores import abrir_camara_usb
from vision.visor import Visor

INDICES_A_PROBAR = 5
DESCARTAR_FOTOGRAMAS = 5   # las webcams dan los primeros fotogramas negros o sin exposición
AVISO_SIN_CALIBRAR = "SIN CALIBRAR: mm aproximados"


def listar_camaras(maximo: int = INDICES_A_PROBAR, abrir=None) -> list[tuple[int, tuple[int, int]]]:
    """Índices de cámara que abren y su resolución. Abre y cierra cada una (la luz de la cámara se enciende un momento)."""
    abrir = abrir or cv2.VideoCapture
    halladas = []
    for i in range(maximo):
        cap = abrir(i)
        try:
            if cap.isOpened():
                halladas.append((i, (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))))
        finally:
            cap.release()
    return halladas


def nombres_windows() -> list[str]:
    """Las cámaras que Windows tiene conectadas (nombre y cuántas entradas: una webcam con infrarrojos sale como dos). [] fuera de Windows o si falla."""
    if sys.platform != "win32":
        return []
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-PnpDevice -Class Camera -PresentOnly | ForEach-Object { $_.FriendlyName }"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return []
    nombres = [n.strip() for n in r.stdout.splitlines() if n.strip()]
    return [f"{n} (x{nombres.count(n)})" if nombres.count(n) > 1 else n for n in dict.fromkeys(nombres)]


def mosaico_de_camaras(indices, abrir=None, lado: tuple[int, int] = (320, 240)) -> np.ndarray:
    """Una imagen con una miniatura de cada cámara (con su índice), para saber cuál es cuál. Abre cada una y tira los primeros fotogramas."""
    abrir = abrir or cv2.VideoCapture
    miniaturas = []
    for i in indices:
        cap = abrir(i)
        frame = None
        try:
            for _ in range(DESCARTAR_FOTOGRAMAS):
                ok, f = cap.read()
                frame = f if ok else frame
        finally:
            cap.release()
        mini = np.full((lado[1], lado[0], 3), 60, np.uint8)
        if frame is not None:
            mini = cv2.resize(frame if frame.ndim == 3 else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR), lado)
        texto = f"camara {i}" + ("" if frame is not None else ": sin imagen")
        cv2.rectangle(mini, (0, 0), (lado[0], 30), (0, 0, 0), -1)
        cv2.putText(mini, texto, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        miniaturas.append(mini)
    return np.hstack(miniaturas) if miniaturas else np.zeros((lado[1], lado[0], 3), np.uint8)


def abrir_camara(indice: int, tam: tuple[int, int] | None, api=None, url: str | None = None):
    """La cámara `indice` o, con `url`, la del móvil por red. En Windows, si el backend por defecto no abre la cámara, se prueba DirectShow (`api` fuerza
    uno: dshow o msmf)."""
    try:
        return abrir_camara_usb(indice, tam, api, url)
    except ValueError as e:
        if url:
            raise
        raise ValueError(f"{e}. Prueba otro --indice (mira --listar), cierra los programas que usen la cámara (Teams, Zoom, la app Cámara) y "
                         "mira que Windows deje a las aplicaciones de escritorio usarla (Configuración, Privacidad, Cámara).") from None


def construir_fuente(proveedor, args):
    """La FuenteCamara para ver la cámara y si va sin calibrar. Lee un fotograma para saber el tamaño de la imagen."""
    from celda.percepcion import FuenteCamara
    fot = None
    for _ in range(getattr(proveedor, "descartar", DESCARTAR_FOTOGRAMAS)):
        fot = proveedor.siguiente()
    if fot is None:
        raise ValueError(getattr(proveedor, "motivo", None) or "la cámara no da imágenes")
    alto, ancho = fot.bgr.shape[:2]
    params = {"modo": args.modo}
    fondo = None
    if args.modo == "fondo":
        if not args.fondo:
            raise ValueError("--modo fondo necesita --fondo: una foto de la escena sin cajas")
        fondo = cv2.imread(args.fondo, cv2.IMREAD_COLOR)
        if fondo is None:
            raise ValueError(f"no puedo leer {args.fondo}")
    if args.calibracion:
        modelo, z, sin_calibrar = ModeloCamara.cargar(args.calibracion), args.z, False
    else:
        modelo, z, sin_calibrar = modelo_cenital_aproximado((ancho, alto), args.altura, args.fov), 0.0, True
    fuente = FuenteCamara(proveedor, modelo, z, args.alto, params, fondo, None, 5.0, 0.05)
    fuente.max_cajas = max(1, getattr(args, "cajas", 1))
    return fuente, sin_calibrar


def guardar_calibracion_aproximada(ruta, tam: tuple[int, int], altura: float, fov: float, z: float, centro=(0.0, 0.0)) -> None:
    """camara.json de una cámara cenital aproximada: a `altura` mm sobre el plano de la cinta, que está a `z` mm en la base del robot, con el
    centro de la imagen sobre el punto `centro` (x, y) de la base (la recogida: así una caja bajo el centro de la imagen es una caja en la recogida, y
    si se mueve hacia la derecha de la imagen, el robot va a +x; hacia arriba, a +y). Las medidas y las posiciones son aproximadas (dependen de que
    `altura` y `fov` sean los de tu webcam). Vale para probar el ciclo de la celda con una webcam; para medir de verdad hay que calibrar (Prueba 7 de
    docs/vision.md)."""
    from nucleo.geometria import Pose
    modelo = modelo_cenital_aproximado(tam, altura + z, fov)
    pose = Pose.crear(t=[float(centro[0]), float(centro[1]), altura + z], q=modelo.T_base_cam.q)
    info = {"origen": "cenital aproximada (vision.ver_camara)", "altura_sobre_la_cinta_mm": altura, "z_cinta_mm": z, "fov_horizontal_deg": fov,
            "centro_de_la_imagen_en_la_base_mm": [float(centro[0]), float(centro[1])]}
    ModeloCamara(modelo.K, modelo.dist, pose, modelo.tam, info).guardar(ruta)


def _centro(texto: str) -> tuple[float, float]:
    try:
        x, y = (float(v) for v in texto.replace(";", ",").split(","))
        return x, y
    except ValueError:
        raise argparse.ArgumentTypeError(f"el centro se escribe x,y en mm, por ejemplo 700,0 (y es {texto!r})") from None


def _tam(texto: str) -> tuple[int, int]:
    try:
        ancho, alto = (int(v) for v in texto.lower().split("x"))
        return ancho, alto
    except ValueError:
        raise argparse.ArgumentTypeError(f"el tamaño se escribe ancho x alto, por ejemplo 1280x720 (y es {texto!r})") from None


def main(argv=None, proveedor=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true", help="probar los índices de cámara y decir cuáles abren")
    ap.add_argument("--ver", action="store_true", help="con --listar: una ventana con la imagen de cada cámara que abre (para saber cuál es cuál)")
    ap.add_argument("--indice", type=int, default=0, help="índice de la cámara (0 por defecto)")
    ap.add_argument("--url", help="en vez de una cámara USB, el móvil: la página propia (https://servidor/c/clave) o el vídeo de una app (http://IP:puerto/video, rtsp://...)")
    ap.add_argument("--api", choices=("auto", "dshow", "msmf"), default="auto", help="backend de OpenCV de la cámara (en Windows, si no abre, prueba dshow)")
    ap.add_argument("--tam", type=_tam, default=None, help="resolución pedida a la cámara, p. ej. 1280x720")
    ap.add_argument("--alto", type=float, default=100.0, help="alto de las cajas en mm (una webcam no mide profundidad)")
    ap.add_argument("--modo", choices=("color", "fondo"), default="color")
    ap.add_argument("--fondo", help="foto de la escena sin cajas (con --modo fondo)")
    ap.add_argument("--cajas", type=int, default=1, help="cuántas cajas identifica a la vez (las mejores; 1 por defecto)")
    ap.add_argument("--centro", type=_centro, default=(700.0, 0.0), help="con --guardar-calibracion: el punto x,y de la base (mm) bajo el centro de la imagen")
    ap.add_argument("--calibracion", help="camara.json de la calibración de la celda")
    ap.add_argument("--z", type=float, default=220.0, help="altura del plano de la cinta en mm (con --calibracion)")
    ap.add_argument("--altura", type=float, default=600.0, help="altura de la cámara sobre la mesa en mm (sin --calibracion)")
    ap.add_argument("--fov", type=float, default=62.0, help="campo de visión horizontal de la cámara en grados (sin --calibracion)")
    ap.add_argument("--guardar-calibracion", metavar="RUTA", help="guardar la cámara cenital aproximada (--altura, --fov, --z) como camara.json")
    ap.add_argument("--segundos", type=float, default=None, help="cerrar solo a los N segundos (por defecto, hasta pulsar q)")
    ap.add_argument("--sin-ventana", action="store_true", help="no abrir ventana (pruebas)")
    args = ap.parse_args(argv)

    if args.listar:
        nombres = nombres_windows()
        if nombres:
            print("Windows tiene conectadas: " + "; ".join(nombres))
        halladas = listar_camaras()
        if not halladas:
            print("Ninguna cámara abre en los índices 0 a 4. ¿Está conectada? ¿Otro programa la usa? ¿Permiso de cámara en Windows?")
            return 2
        for i, (w, h) in halladas:
            print(f"cámara {i}: abre ({w} x {h})")
        print("Prueba con: python -m vision.ver_camara --indice <número>. Una cámara con infrarrojos (Windows Hello) sale como dos índices: una en color "
              "y otra en blanco y negro. Si esperabas una webcam externa y solo salen las del portátil, conéctala por USB y vuelve a ejecutar esto: "
              "debe salir otro índice.")
        if args.ver:
            imagen = mosaico_de_camaras([i for i, _ in halladas])
            if not args.sin_ventana:
                try:
                    cv2.imshow("Camaras (cualquier tecla cierra)", imagen)
                    cv2.waitKey(15000)
                    cv2.destroyAllWindows()
                except cv2.error as e:
                    print(f"No puedo abrir la ventana ({str(e).splitlines()[0][:100]})")
        return 0

    propio = proveedor is None
    try:
        if propio:
            proveedor = abrir_camara(args.indice, args.tam, None if args.api == "auto" else args.api, args.url)
        fuente, sin_calibrar = construir_fuente(proveedor, args)
    except ValueError as e:
        print(f"error: {e}")
        if propio and proveedor is not None:
            proveedor.cerrar()
        return 2
    if args.guardar_calibracion:
        if not sin_calibrar:
            print("error: --guardar-calibracion es para la cámara aproximada; con --calibracion ya tienes un camara.json")
            if propio:
                proveedor.cerrar()
            return 2
        alto, ancho = proveedor.siguiente().bgr.shape[:2]
        guardar_calibracion_aproximada(args.guardar_calibracion, (ancho, alto), args.altura, args.fov, args.z, args.centro)
        print(f"Guardada la cámara aproximada en {args.guardar_calibracion} (a {args.altura:g} mm sobre la cinta, a z = {args.z:g} mm; el centro de la imagen "
              f"es el punto {args.centro[0]:g},{args.centro[1]:g} del robot)")
    visor = Visor(fuente, hz=15.0, mostrar=not args.sin_ventana, aviso=AVISO_SIN_CALIBRAR if sin_calibrar else "")
    print("Cámara abierta. " + ("SIN CALIBRAR: contorno, centro e hilo valen, los mm son aproximados. " if sin_calibrar else "")
          + "Pulsa q o cierra la ventana para salir.")
    visor.iniciar()
    fin = None if args.segundos is None else time.monotonic() + args.segundos
    try:
        while fin is None or time.monotonic() < fin:
            if not visor.bombear():
                if args.sin_ventana or visor.sin_pantalla:
                    time.sleep(0.05)       # sin ventana no hay quien cierre: se espera al tiempo
                    if fin is None:
                        break
                else:
                    break
            else:
                time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        visor.parar()
        if propio:
            proveedor.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
