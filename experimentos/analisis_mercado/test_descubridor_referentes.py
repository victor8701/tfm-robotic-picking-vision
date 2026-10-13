"""Pruebas de descubridor_referentes.py SIN red: un servidor local imita Reddit, Bing y Google Noticias, FxTwitter, los artículos y las fotos (formatos copiados de los que lee el resto del código).
La puerta CLIP y el detector de prendas se sustituyen por piezas falsas (aquí no hay torch): lo que se prueba es el cableado, los recuentos, los 403/429 y el formato de salida.
No mide nada real. Uso:  python3 test_descubridor_referentes.py"""
import base64
import io
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from PIL import Image

TMP = Path(tempfile.mkdtemp(prefix="test_descubridor_"))
os.environ["DESCUBRIDOR_TMP"] = str(TMP / "esc")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import descubridor_referentes as d  # noqa: E402

AHORA = datetime.now(timezone.utc)
MODO = {"reddit": "ok", "x": "ok"}   # «ok» | «403» | «429_una_vez»
VISTAS = {"429": 0}
PUERTO = None


def foto(nombre: str) -> bytes:
    """JPEG 420×560; `p…` = «persona con ropa» (fondo rojo), `n…` = no (azul); una marca en la esquina identifica el número: dos nombres con el mismo número son la misma imagen (repetida)."""
    rojo = nombre.startswith("p")
    n = int(re.sub(r"\D", "", nombre) or 0)
    im = Image.new("RGB", (420, 560), (230, 30, 30) if rojo else (30, 30, 230))
    im.paste((255, (n * 37) % 256, (n * 91) % 256), (0, 0, 40, 40))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=95)
    return b.getvalue()


def atom(entradas: list[str]) -> str:
    return '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">' + "".join(entradas) + "</feed>"


def entrada(sub: str, k: int, con_imagen: bool, dias: float = 3, img: str | None = None) -> str:
    cont = f'&lt;img src="http://127.0.0.1:{PUERTO}/img/{img or ("p" if k % 4 else "n") + str(k)}.jpg"&gt;' if con_imagen else "&lt;p&gt;texto&lt;/p&gt;"
    fecha = (AHORA - timedelta(days=dias)).isoformat()
    return (f'<entry><title>Outfit of the day {k} look</title><link href="https://www.reddit.com/r/{sub}/comments/id{k}/post/"/><updated>{fecha}</updated>'
            f'<category term="{sub}"/><id>t3_id{k}</id><content type="html">{cont}</content></entry>')


def rss(items: list[str], ns: str = "") -> str:
    return f'<?xml version="1.0"?><rss version="2.0" {ns}><channel>' + "".join(items) + "</channel></rss>"


class Servidor(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def responder(self, cuerpo, tipo="text/xml", codigo=200, cabeceras=()):
        datos = cuerpo if isinstance(cuerpo, bytes) else cuerpo.encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        for k, v in cabeceras:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):  # noqa: N802
        ruta, q = self.path.split("?")[0], self.path
        if ruta.startswith("/img/"):
            return self.responder(foto(ruta[5:-4]), "image/jpeg")
        if ruta.startswith("/art/"):
            k = ruta[5:]
            return self.responder(f'<html><head><title>Artículo {k}</title><meta property="og:image" content="http://127.0.0.1:{PUERTO}/img/p{k}.jpg"></head><body><img src="http://127.0.0.1:{PUERTO}/img/p{k}.jpg"></body></html>', "text/html")
        if ruta.startswith(("/subreddits", "/search.rss", "/r/")):
            if MODO["reddit"] == "403":
                return self.responder("blocked", codigo=403)
            if MODO["reddit"] == "429_una_vez" and VISTAS["429"] == 0:
                VISTAS["429"] += 1
                return self.responder("slow", codigo=429, cabeceras=[("Retry-After", "0")])
            if ruta.startswith("/subreddits"):
                return self.responder(atom([f'<entry><title>r/{s}</title><link href="https://www.reddit.com/r/{s}/"/><id>t5_{s}</id></entry>' for s in ("ivystyle", "pics", "OldMoney", "newmoneyreps")]))   # «pics» es genérica y «…reps» vende réplicas: no deben salir
            if ruta.startswith("/search.rss"):
                return self.responder(atom([entrada("ivystyle", k, True) for k in range(5)] + [entrada("OldMoney", 40, True)] + [entrada("astrologyexplore", k, True) for k in range(60, 66)]))   # astrología: ruido
            sub = ruta.split("/")[2]
            if sub == "quietluxury":
                return self.responder("no existe", codigo=404)
            # ivystyle: 6 publicaciones con imagen (una de hace 40 días, fuera de ventana), 1 de texto; OldMoney: 2 con imagen
            if sub == "ivystyle":
                return self.responder(atom([entrada(sub, k, True) for k in range(1, 6)] + [entrada(sub, 9, True, dias=40), entrada(sub, 10, False)]))
            return self.responder(atom([entrada(sub, 21, True), entrada(sub, 22, True, img="p21b")]))   # la segunda es la misma imagen que la primera
        if ruta == "/news/search" and "solo-google" in q:
            return self.responder(rss([]))
        if ruta == "/rss/search" and "solo-google" in q:
            nuevo = base64.urlsafe_b64encode(b"AU_yqLsinurl" * 5).decode().rstrip("=")
            return self.responder(rss([f"<item><title>Solo google {k} moda - Medio</title><link>https://news.google.com/rss/articles/{nuevo}{k}?oc=5</link><pubDate>{format_datetime(AHORA - timedelta(days=k))}</pubDate>"
                                       f'<description>moda</description><source url="https://medio.test">Medio</source></item>' for k in (1, 2)]))
        if ruta == "/news/search":
            hace = lambda dias: format_datetime(AHORA - timedelta(days=dias))   # noqa: E731
            items = [f'<item><title>Old money style {k} moda</title><link>http://www.bing.com/news/apiclick.aspx?url=http%3a%2f%2f127.0.0.1%3a{PUERTO}%2fart%2f{k}&amp;aid=x</link>'
                     f'<description>moda y estilo</description><pubDate>{hace(k)}</pubDate><News:Source>Diario {k % 3}</News:Source>' + (f"<News:Image>http://www.bing.com/th?id={k}</News:Image>" if k % 2 else "") + "</item>"
                     for k in range(1, 7)]
            items.append(f"<item><title>Old money viejo</title><link>http://x.test/v</link><description>moda</description><pubDate>{hace(80)}</pubDate></item>")
            return self.responder(rss(items, 'xmlns:News="https://www.bing.com/news/search"'))
        if ruta == "/rss/search":
            viejo = base64.urlsafe_b64encode(b'\x08\x13"\x2a' + f"http://127.0.0.1:{PUERTO}/art/7".encode() + b"\xd2\x01\x00").decode().rstrip("=")
            nuevo = base64.urlsafe_b64encode(b"AU_yqLsinurl" * 5).decode().rstrip("=")
            items = [f"<item><title>Old money style {k} moda - Medio {k}</title><link>https://news.google.com/rss/articles/{viejo if k == 7 else nuevo}?oc=5</link><pubDate>{format_datetime(AHORA - timedelta(days=k))}</pubDate>"
                     f'<description>moda</description><source url="https://medio{k}.test">Medio {k}</source></item>' for k in (3, 7, 8)]
            return self.responder(rss(items))
        if ruta.endswith("/statuses"):
            if MODO["x"] == "403":
                return self.responder("blocked", codigo=403)
            ts = lambda dias: int((AHORA - timedelta(days=dias)).timestamp())   # noqa: E731
            posts = [{"id": str(i), "url": f"https://x.com/h/status/{i}", "lang": "en", "created_timestamp": ts(dias), "author": {"followers": 1234},
                      "media": {"photos": [{"url": f"http://127.0.0.1:{PUERTO}/img/p{50 + i}.jpg"}]} if con else {}} for i, (dias, con) in enumerate([(2, True), (5, False), (9, True), (20, True)], 1)]
            posts.append({"id": "99", "reposted_by": {"x": 1}, "created_timestamp": ts(1), "media": {"photos": [{"url": "http://127.0.0.1/img/p1.jpg"}]}})
            return self.responder(json.dumps({"results": posts}), "application/json")
        self.responder("?", codigo=404)


def poner_servidor():
    global PUERTO
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Servidor)
    PUERTO = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PUERTO}"
    d.BASE.update({"reddit": base, "bing": base + "/news/search", "google": base + "/rss/search"})
    d.m.FXTWITTER = base
    d.RE_IMG_REDDIT = re.compile(r"http://127\.0\.0\.1:\d+/img/[a-z0-9_]+\.jpg")
    d.PAUSA_REDDIT = d.PAUSA_WEB = d.PAUSA_FOTO = 0
    return srv


def puerta_falsa(rutas):
    X, g = [], []
    for r in rutas:
        im = Image.open(r).convert("RGB")
        g.append(0.9 if im.getpixel((200, 200))[0] > 150 else 0.1)   # fondo rojo = persona con ropa
        marca = tuple(v // 16 for v in im.getpixel((20, 20)))          # la marca de la esquina identifica la imagen (aguanta el JPEG)
        v = np.random.default_rng(hash(marca) % 2**32).normal(size=64)
        X.append(v / np.linalg.norm(v))
    return np.array(g), np.array(X)


def ropa_falsa(rutas, lote=40):
    return {r: (Image.open(r).convert("RGB").getpixel((20, 20))[1] // 16) % 2 == 0 for r in rutas}   # determinista según la marca de la imagen


class Pruebas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = poner_servidor()
        d.puntuar_puerta, d.detectar_ropa = puerta_falsa, ropa_falsa

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        d.MEDIDAS.clear()
        d.RED.__init__()
        d.LIMITE_REDDIT[0] = None
        MODO.update({"reddit": "ok", "x": "ok"})
        VISTAS["429"] = 0

    def medir(self, *extra, estilos="old_money", mercados="US"):
        salida = TMP / f"salida_{time.time_ns()}.json"
        os.environ["DESCUBRIDOR_CONSERVAR"] = ""
        self.assertEqual(d.main(["medir", "--estilos", estilos, "--mercados", mercados, "--salida", str(salida), *extra]), 0)
        return json.loads(salida.read_text(encoding="utf-8")), salida

    # ---- piezas
    def test_google_antiguo_se_decodifica_y_el_nuevo_no(self):
        viejo = base64.urlsafe_b64encode(b'\x08\x13"\x2ahttps://ejemplo.es/a/b?x=1\xd2\x01\x00').decode().rstrip("=")
        self.assertEqual(d.decodificar_google(f"https://news.google.com/rss/articles/{viejo}?oc=5"), "https://ejemplo.es/a/b?x=1")
        self.assertIsNone(d.decodificar_google("https://news.google.com/rss/articles/" + base64.urlsafe_b64encode(b"AU_yqLabc" * 6).decode().rstrip("=")))

    def test_repartida_no_toma_solo_los_primeros(self):
        self.assertEqual(d.repartida(list(range(100)), 5), [0, 25, 50, 74, 99])
        self.assertEqual(d.repartida([1, 2], 8), [1, 2])

    def test_servicio_bloqueado_tras_tres_403_seguidos(self):
        for _ in range(3):
            d.RED.fallo("reddit", 403)
        self.assertTrue(d.RED.cerrado("reddit"))
        self.assertEqual(d.pedir("reddit", "http://127.0.0.1:9/x"), (None, None))
        d.RED.__init__()
        d.RED.acierto("reddit")
        for _ in range(5):
            d.RED.fallo("reddit", 403)
        self.assertFalse(d.RED.cerrado("reddit"), "con aciertos previos hacen falta 6 seguidos")
        d.RED.fallo("reddit", 404)
        self.assertEqual(d.RED.seguidos["reddit"], 0, "un 404 no cuenta como bloqueo")

    # ---- de punta a punta
    def test_todo_funciona(self):
        datos, salida = self.medir("--validar", "prendas")
        por = {(c["tipo"], c["valor"]): c for c in datos["candidatos"] if c["mercado"] == "US"}
        iv = por[("reddit", "ivystyle")]
        self.assertEqual(iv["estado"], "medido")
        self.assertEqual(iv["evidencia"]["con_imagen_30d"], 5, "la de hace 40 días y la de texto no cuentan")
        self.assertEqual(iv["evidencia"]["muestra"], 5)
        self.assertEqual(iv["evidencia"]["validacion"], "prendas")
        self.assertIn("con_ropa_visible", iv["evidencia"])
        self.assertLessEqual(len(iv["ejemplos"]), 3)
        self.assertTrue(all(u.startswith("https://www.reddit.com/r/ivystyle/comments/") for u in iv["ejemplos"]))
        self.assertEqual(por[("reddit", "quietluxury")]["estado"], "no_disponible")
        self.assertEqual(por[("reddit", "OldMoney")]["origen"], "propuesta", "semilla y descubierta a la vez: gana la semilla")
        self.assertNotIn(("reddit", "pics"), por, "las comunidades genéricas no se proponen")
        self.assertNotIn(("reddit", "newmoneyreps"), por, "ni las de réplicas")
        self.assertNotIn(("reddit", "astrologyexplore"), por, "el ruido que solo aparece en la búsqueda de publicaciones y no habla de moda tampoco")
        x = por[("x", "dieworkwear")]
        self.assertEqual((x["estado"], x["evidencia"]["con_imagen_30d"], x["evidencia"]["fotos_30d"]), ("medido", 3, 3), "3 posts con foto en 30 días; el repost no cuenta")
        self.assertTrue(x["evidencia"]["tope_lote"], "el lote llega solo a 20 días atrás: la cifra es un mínimo")
        prensa = [c for c in datos["candidatos"] if c["tipo"] == "noticias" and c["mercado"] == "US" and c["ambito"] == "estilo"]
        estados = {c["valor"]: c["estado"] for c in prensa}
        self.assertEqual(estados['"quiet luxury" fashion'], "sin_datos", "ningún titular suyo nombra «quiet luxury»")
        self.assertEqual(estados['"old money" style men'], "medido")
        prensa = [c for c in prensa if c["estado"] == "medido"]
        ev = prensa[0]["evidencia"]
        self.assertEqual(ev["publicaciones_30d"], 6 + 2, "6 de Bing (la de hace 80 días fuera) + 2 de Google sin duplicar la que ya estaba")
        self.assertEqual(ev["con_imagen_rss"], 3)
        self.assertTrue(ev["con_imagen_30d_estimada"])
        self.assertEqual(ev["sin_enlace_real"], 1, "el enlace nuevo de Google no se puede resolver")
        self.assertTrue(prensa[0]["fuente"]["nombre"], "la fuente lista para tendencia_fuentes.json lleva su regex de nombre")
        resumen = salida.with_name(salida.stem + "_resumen.md").read_text(encoding="utf-8")
        self.assertIn("▸ Old money · US", resumen)
        self.assertLess(len(resumen.splitlines()), 40)
        self.assertFalse((TMP / "esc").exists(), "las fotos de la muestra se borran")
        for c in datos["candidatos"]:
            self.assertEqual(set(c) >= {"id", "estilo", "mercado", "tipo", "valor", "evidencia", "ejemplos", "fuente", "estado"}, True)
        self.assertNotRegex(json.dumps(datos), r"@[\w.]+\.[a-z]{2,}", "ningún correo")

    def test_la_validacion_cuenta_repetidas(self):
        datos, _ = self.medir("--validar", "puerta", "--fuentes", "reddit")
        iv = {c["valor"]: c for c in datos["candidatos"]}["ivystyle"]["evidencia"]
        self.assertEqual(iv["validacion"], "puerta")
        # fotos 1..5: p1,p2,p3,n4,p5 → 4 con persona; ninguna repetida
        self.assertEqual((iv["con_persona"], iv["repetidas"]), (4, 0))
        self.assertEqual(iv["fotos_utiles_est"], 4.0)
        om = {c["valor"]: c for c in datos["candidatos"]}["OldMoney"]["evidencia"]
        self.assertEqual((om["muestra"], om["repetidas"], om["con_persona"]), (2, 1, 1), "dos fotos idénticas: una repetida; solo cuenta una")

    def test_reddit_403_se_anota_y_sigue(self):
        MODO["reddit"] = "403"
        datos, salida = self.medir("--validar", "nada")
        self.assertTrue(datos["red"]["reddit"]["bloqueado"], datos["red"])
        self.assertIsNone(datos["red"]["bing"]["bloqueado"])
        reddit = [c for c in datos["candidatos"] if c["tipo"] == "reddit"]
        self.assertTrue(reddit and all(c["estado"] == "bloqueado" for c in reddit))
        self.assertTrue(any(c["estado"] == "medido" for c in datos["candidatos"] if c["tipo"] in ("noticias", "x")), "prensa y X siguen")
        self.assertIn("reddit ✕", salida.with_name(salida.stem + "_resumen.md").read_text(encoding="utf-8"))

    def test_x_403_y_429_de_reddit_con_reintento(self):
        MODO["x"] = "403"
        MODO["reddit"] = "429_una_vez"
        datos, _ = self.medir("--validar", "nada", estilos="lujo")
        self.assertEqual(datos["red"]["reddit"]["respuestas"].get("429"), 1)
        self.assertIsNone(datos["red"]["reddit"]["bloqueado"], "un 429 seguido de aciertos no bloquea")
        self.assertTrue(datos["red"]["fxtwitter"]["bloqueado"])
        x = {c["valor"]: c for c in datos["candidatos"] if c["tipo"] == "x"}
        self.assertTrue(x and all(c["estado"] == "bloqueado" for c in x.values()))

    def test_tope_de_tiempo_de_reddit_deja_omitido_lo_que_no_llega(self):
        datos, _ = self.medir("--validar", "nada", "--fuentes", "reddit,x", "--tiempo-reddit", "0")
        reddit = [c for c in datos["candidatos"] if c["tipo"] == "reddit"]
        self.assertTrue(reddit and all(c["estado"] == "omitido" for c in reddit), [c["estado"] for c in reddit])
        self.assertGreater(datos["red"]["reddit"]["respuestas"]["omitido"], 0)
        self.assertIsNone(datos["red"]["reddit"]["bloqueado"])
        self.assertTrue(any(c["tipo"] == "x" and c["estado"] == "medido" for c in datos["candidatos"]), "lo demás sigue")

    def test_prensa_sin_enlaces_reales_dice_sin_comprobar_y_no_cero(self):
        med = d.MEDIDAS[d.medir_noticias(d.definicion_prensa("US", ["solo-google moda"], None), 4)]
        self.assertEqual(med["estado"], "medido")
        self.assertEqual(med["datos"]["publicaciones_30d"], 2)
        self.assertEqual(med["datos"]["sin_enlace_real"], 2)
        self.assertTrue(med["datos"]["sin_muestra"])
        self.assertEqual(med["fotos"], [])
        self.assertIn("foto sin comprobar", d.texto_evidencia(d.evidencia_de(med, "puerta"), "medido", med["http"]))

    def test_sin_clip_solo_cuenta_publicaciones(self):
        antes = d.puntuar_puerta
        d.puntuar_puerta = lambda r: (_ for _ in ()).throw(ImportError("sin torch"))
        try:
            datos, _ = self.medir("--validar", "puerta", "--fuentes", "reddit")
        finally:
            d.puntuar_puerta = antes
        self.assertEqual(datos["validacion"], "no_disponible")
        iv = {c["valor"]: c for c in datos["candidatos"]}["ivystyle"]["evidencia"]
        self.assertEqual((iv["con_imagen_30d"], iv["validacion"]), (5, "no_disponible"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
