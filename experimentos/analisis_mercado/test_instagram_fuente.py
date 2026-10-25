"""Pruebas de la fuente `instagram` de la tarea semanal (tendencia_prenda.py): lectura de Windsor, orden de las fotos, tope por cuenta y que la clave no se filtre. Sin red ni torch.
Uso:  python3 test_instagram_fuente.py"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

os.environ["TENDENCIA_DATOS"] = tempfile.mkdtemp(prefix="test_ig_")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tendencia_prenda as tp  # noqa: E402

CLAVE = "clave-secreta-de-prueba-123"


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fila(cuenta, mid, tipo="IMAGE", ts="2026-10-20T10:00:00+0000", **extra):
    f = {"account_name": cuenta, "media_id": mid, "media_type": tipo, "media_url": f"https://cdn.example/{mid}.jpg", "media_thumbnail_url": f"https://cdn.example/{mid}_t.jpg",
         "media_permalink": f"https://www.instagram.com/p/{mid}/", "media_timestamp": ts, "media_like_count": 100, "media_comments_count": 5, "profile_followers_count": 5000,
         "media_caption": "Look de otoño #ootd"}
    f.update(extra)
    return f


def fuente(valor="gucci"):
    return {"tipo": "instagram", "valor": valor, "referente": "Gucci", "estilo": "lujo", "mercado": "US"}


class Pruebas(unittest.TestCase):
    def setUp(self):
        os.environ["WINDSOR_API_KEY"] = CLAVE
        tp._IG_CACHE.clear()

    def test_windsor_agrupa_por_cuenta_y_pide_lo_necesario(self):
        vistas = {}

        def abrir(req, timeout=0):
            vistas["url"] = req.full_url
            return Resp(json.dumps({"data": [fila("Gucci", "1"), fila("gucci", "2"), fila("kidcudi", "3")]}).encode())

        por = tp.windsor_filas(["gucci", "kidcudi"], dias=35, abrir=abrir)
        self.assertEqual({k: len(v) for k, v in por.items()}, {"gucci": 2, "kidcudi": 1}, "se agrupa en minúsculas")
        for t in ("select_accounts=gucci%2Ckidcudi", "media_url", "date_from=", "_renderer=json"):
            self.assertIn(t, vistas["url"])

    def test_si_una_cuenta_pedida_no_esta_en_windsor_se_reintenta_sin_filtro_y_se_filtra_aqui(self):
        urls = []

        def abrir(req, timeout=0):
            urls.append(req.full_url)
            if "select_accounts" in req.full_url:
                raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)
            return Resp(json.dumps({"data": [fila("gucci", "1"), fila("sobrante", "2")]}).encode())

        por = tp.windsor_filas(["gucci", "noconfigurada"], abrir=abrir)
        self.assertEqual(len(urls), 2)
        self.assertNotIn("select_accounts", urls[1])
        self.assertEqual(list(por), ["gucci"], "solo las cuentas pedidas, aunque Windsor devuelva más")

    def test_un_error_de_clave_o_de_cupo_no_se_reintenta(self):
        veces = []

        def abrir(req, timeout=0):
            veces.append(1)
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, None)

        with self.assertRaises(ValueError) as cm:
            tp.windsor_filas(["gucci"], abrir=abrir)
        self.assertEqual(len(veces), 1)
        self.assertIn("429", str(cm.exception))
        self.assertNotIn(CLAVE, str(cm.exception))

    def test_sin_clave_falla_con_mensaje_claro(self):
        del os.environ["WINDSOR_API_KEY"]
        with self.assertRaises(ValueError) as cm:
            tp.windsor_filas(["gucci"])
        self.assertIn("WINDSOR_API_KEY", str(cm.exception))

    def test_la_clave_no_aparece_en_los_errores(self):
        def abrir_http(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, 403, "no", {}, None)

        def abrir_red(req, timeout=0):
            raise OSError("fallo con " + req.full_url)

        for abrir in (abrir_http, abrir_red):
            with self.assertRaises(ValueError) as cm:
                tp.windsor_filas(["gucci"], abrir=abrir)
            self.assertNotIn(CLAVE, str(cm.exception))
            self.assertNotIn("api_key", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            tp.windsor_filas(["gucci"], abrir=abrir_http)
        self.assertIn("403", str(cm.exception))

    def test_primero_imagenes_recientes_y_los_videos_con_miniatura(self):
        bajadas = []

        def bajar(url, destino, **kw):
            bajadas.append(url)
            return True

        filas = [fila("gucci", "v1", "VIDEO", "2026-10-22T10:00:00+0000"), fila("gucci", "a", "IMAGE", "2026-10-10T10:00:00+0000"),
                 fila("gucci", "b", "CAROUSEL_ALBUM", "2026-10-21T10:00:00+0000")]
        out, info = tp.instagram_registros(filas, fuente(), {}, bajar=bajar)
        self.assertEqual(list(out), ["ig_b", "ig_a", "ig_v1"], "imágenes y carruseles por fecha descendente, vídeos al final")
        self.assertTrue(bajadas[2].endswith("v1_t.jpg"), "el vídeo usa su miniatura")
        r = out["ig_b"]
        self.assertEqual((r["fuente"], r["referente"], r["estilo"], r["mercado"]), ("instagram", "Gucci", "lujo", "US"))
        self.assertEqual((r["likes"], r["seguidores_autor"], r["enlace"]), (100, 5000, "https://www.instagram.com/p/b/"))
        self.assertTrue(r["fecha"].startswith("2026-10-21T10:00:00"), "fecha en UTC")
        self.assertEqual(info, {"publicaciones": 3, "sin_foto": 0})

    def test_tope_por_cuenta_y_lo_conocido_solo_actualiza_popularidad(self):
        filas = [fila("gucci", str(i), ts=f"2026-10-{i + 1:02d}T10:00:00+0000") for i in range(12)]
        existentes = {"ig_11": {"likes": 1, "fuente": "instagram"}}
        out, info = tp.instagram_registros(filas, fuente(), existentes, bajar=lambda *a, **k: True, max_nuevas=5)
        self.assertEqual(len(out), 5)
        self.assertNotIn("ig_11", out, "la ya conocida no se vuelve a bajar")
        self.assertEqual(existentes["ig_11"]["likes"], 100, "pero se actualiza su popularidad")
        self.assertEqual(list(out)[0], "ig_10", "las más recientes primero")

    def test_descarga_fallida_o_sin_direccion_se_cuenta_y_no_rompe(self):
        def bajar(url, destino, **kw):
            if "mala" in url:
                raise OSError("caducada")
            return "pequena" not in url

        filas = [fila("gucci", "1", media_url="https://cdn.example/mala.jpg"), fila("gucci", "2", media_url="https://cdn.example/pequena.jpg"), fila("gucci", "3", media_url=None),
                 fila("gucci", "4"), fila("gucci", "")]
        out, info = tp.instagram_registros(filas, fuente(), {}, bajar=bajar)
        self.assertEqual(list(out), ["ig_4"])
        self.assertEqual(info["sin_foto"], 3, "caducada, demasiado pequeña y sin dirección")

    def test_cosechar_pide_una_sola_vez_y_recuerda_el_error(self):
        cfg = Path(tempfile.mkdtemp()) / "f.json"
        cfg.write_text(json.dumps({"fuentes": [fuente("gucci"), fuente("@KidCudi"), {"tipo": "x", "valor": "otra", "referente": "O", "estilo": "urbano", "mercado": "US"}]}), encoding="utf-8")
        antes = (tp.FUENTES, tp.windsor_filas, tp.instagram_registros)
        llamadas = []
        try:
            tp.FUENTES = cfg
            tp.windsor_filas = lambda handles, **kw: llamadas.append(handles) or {"gucci": [fila("gucci", "1")], "kidcudi": []}
            tp.instagram_registros = lambda filas, s, ex, **kw: ({"ig_1": {}}, {"publicaciones": len(filas)})
            self.assertEqual(tp.cosechar_instagram(fuente("gucci"), {})[1], {"publicaciones": 1})
            with self.assertRaises(ValueError):
                tp.cosechar_instagram(fuente("@KidCudi"), {})   # sin publicaciones: error legible, no silencio
            self.assertEqual(llamadas, [["gucci", "kidcudi"]], "una sola petición con las cuentas de tipo instagram, sin @ y en minúsculas")
            tp._IG_CACHE.clear()

            def falla(handles, **kw):
                llamadas.append("otra")
                raise ValueError("Windsor contestó HTTP 401")

            tp.windsor_filas = falla
            for _ in range(2):
                with self.assertRaises(ValueError):
                    tp.cosechar_instagram(fuente("gucci"), {})
            self.assertEqual(llamadas.count("otra"), 1, "si falla, no se insiste en cada cuenta")
        finally:
            tp.FUENTES, tp.windsor_filas, tp.instagram_registros = antes

    def test_registrada_en_la_cosecha(self):
        self.assertIs(tp.COSECHA["instagram"], tp.cosechar_instagram)


if __name__ == "__main__":
    unittest.main(verbosity=2)
