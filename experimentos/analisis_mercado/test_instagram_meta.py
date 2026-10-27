"""Pruebas de la lectura de Instagram con la app propia de Meta (instagram_meta.py) y de cómo la tarea semanal la combina con Windsor. Sin red.
Uso:  python3 test_instagram_meta.py"""
import io
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

os.environ["TENDENCIA_DATOS"] = tempfile.mkdtemp(prefix="test_meta_")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import instagram_meta as im  # noqa: E402

TOKEN = "EAAtokensecretodeprueba1234567890"
AHORA = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


class Resp(io.BytesIO):
    status = 200
    headers = {"x-app-usage": '{"call_count":3}'}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def error_http(url, codigo_http, cod, msg):
    return urllib.error.HTTPError(url, codigo_http, "x", {}, io.BytesIO(json.dumps({"error": {"message": msg, "code": cod, "type": "OAuthException"}}).encode()))


def media(i, tipo="IMAGE", ts="2026-10-20T10:00:00+0000", **extra):
    m = {"id": f"m{i}", "media_type": tipo, "media_url": f"https://cdn.example/m{i}.jpg", "thumbnail_url": f"https://cdn.example/m{i}_t.jpg", "permalink": f"https://www.instagram.com/p/m{i}/",
         "timestamp": ts, "caption": "Look #ootd", "like_count": 10 + i, "comments_count": i}
    m.update(extra)
    return m


class Grafo:
    """Graph API de mentira: contesta por ruta y mira el campo `fields` pedido."""

    def __init__(self, cuentas=None, accounts=None, me=None, errores=None, rechaza=None, debug=None):
        self.cuentas, self.accounts, self.me, self.errores = cuentas or {}, accounts, me, errores or {}
        self.rechaza, self.debug = rechaza or {}, debug   # rechaza: {token: (HTTP, código, mensaje)} solo para Business Discovery
        self.peticiones = []

    def __call__(self, req, timeout=0):
        u = urllib.parse.urlparse(req.full_url)
        q = urllib.parse.parse_qs(u.query)
        ruta = u.path.split("/", 2)[2]
        campos = q.get("fields", [""])[0]
        self.peticiones.append((ruta, campos))
        if ruta == "debug_token":
            if self.debug is None:
                raise error_http(req.full_url, 400, 100, "no")
            return Resp(json.dumps({"data": self.debug}).encode())
        if ruta == "me/accounts":
            if self.accounts is None:
                raise error_http(req.full_url, 400, 100, "(#100) Tried accessing nonexisting field (accounts) on node type (Page)")
            return Resp(json.dumps({"data": self.accounts}).encode())
        if ruta == "me":
            if self.me is None:
                raise error_http(req.full_url, 400, 190, "Invalid OAuth access token - Cannot parse access token")
            return Resp(json.dumps(self.me).encode())
        m = re.search(r"business_discovery\.username\(([^)]+)\)", campos)
        usuario = m.group(1)
        if q.get("access_token", [""])[0] in self.rechaza:
            raise error_http(req.full_url, *self.rechaza[q["access_token"][0]])
        if usuario in self.errores:
            raise error_http(req.full_url, 400, *self.errores[usuario])
        paginas = self.cuentas.get(usuario)
        if paginas is None:
            raise error_http(req.full_url, 400, 110, "Invalid user id")
        despues = re.search(r"\.after\(([^)]+)\)", campos)
        idx = int(despues.group(1)) if despues else 0
        data = paginas[idx]
        cursor = {"after": str(idx + 1)} if idx + 1 < len(paginas) else {}
        return Resp(json.dumps({"business_discovery": {"username": usuario, "followers_count": 5000, "media_count": 77,
                                                       "media": {"data": data, "paging": {"cursors": cursor}} if data is not None else {}}, "id": "17841"}).encode())


PAGINA = [{"id": "pg1", "name": "Tendencias Moda", "access_token": "PAGTOKEN-no-caduca", "instagram_business_account": {"id": "17841400000"}}]


class PruebasMeta(unittest.TestCase):
    def test_token_de_persona_busca_la_pagina_y_usa_su_token(self):
        g = Grafo(accounts=PAGINA)
        cands, ig, tipo, det = im.preparar(TOKEN, abrir=g)
        self.assertEqual((cands, ig, tipo), ([TOKEN, "PAGTOKEN-no-caduca"], "17841400000", "persona"), "primero el de persona (lo que dice la documentación), después el de la página")
        self.assertIn("Tendencias Moda", det)

    def test_token_de_pagina_se_reconoce(self):
        g = Grafo(accounts=None, me={"id": "pg1", "name": "Tendencias Moda", "instagram_business_account": {"id": "17841400000"}})
        self.assertEqual(im.preparar(TOKEN, abrir=g)[:3], ([TOKEN], "17841400000", "página"))

    def test_persona_sin_paginas_con_instagram_da_un_mensaje_accionable(self):
        g = Grafo(accounts=[{"id": "p", "name": "Otra"}])
        with self.assertRaises(im.MetaError) as cm:
            im.preparar(TOKEN, abrir=g)
        self.assertIn("página", str(cm.exception))

    def test_token_caducado_dice_que_hay_que_generar_otro_y_no_lo_repite(self):
        def abrir(req, timeout=0):
            raise error_http(req.full_url, 400, 190, f"Error validating access token: Session has expired. token={TOKEN}")

        with self.assertRaises(im.MetaError) as cm:
            im.preparar(TOKEN, abrir=abrir)
        self.assertIn("generar otro", str(cm.exception))
        self.assertNotIn(TOKEN, str(cm.exception))

    def test_el_error_de_token_cuenta_lo_que_dijo_meta_para_distinguir_caducado_de_mal_copiado(self):
        def abrir(req, timeout=0):
            raise error_http(req.full_url, 400, 190, f"Invalid OAuth access token - Cannot parse access token ({TOKEN})")

        with self.assertRaises(im.MetaError) as cm:
            im.preparar(TOKEN, abrir=abrir)
        self.assertIn("Cannot parse access token", str(cm.exception))
        self.assertNotIn(TOKEN, str(cm.exception))

    def test_limpiar_token_quita_espacios_comillas_y_coma_del_json(self):
        self.assertEqual(im.limpiar_token(f'  "{TOKEN}",\n'), TOKEN)
        self.assertEqual(im.limpiar_token(f"'{TOKEN}'"), TOKEN)
        self.assertEqual(im.limpiar_token(TOKEN), TOKEN)
        self.assertEqual(im.limpiar_token(None), "")

    def test_filas_con_los_campos_de_windsor_ventana_y_carruseles(self):
        carrusel = media(2, "CAROUSEL_ALBUM", children={"data": [{"id": "h1", "media_type": "IMAGE", "media_url": "https://cdn.example/m2.jpg"}, {"id": "h2", "media_type": "IMAGE", "media_url": "https://cdn.example/h2.jpg"},
                                                                   {"id": "h3", "media_type": "VIDEO", "media_url": "https://cdn.example/h3.mp4"}]})
        sin_url = media(5, "CAROUSEL_ALBUM", media_url=None, children={"data": [{"id": "h9", "media_type": "IMAGE", "media_url": "https://cdn.example/h9.jpg"}]})
        g = Grafo(accounts=PAGINA, cuentas={"gucci": [[media(1), carrusel, media(3, "VIDEO"), media(4, ts="2026-08-01T10:00:00+0000"), sin_url]]})
        por, res = im.meta_filas(["gucci"], TOKEN, abrir=g, pausa=0, ahora=AHORA)
        filas = por["gucci"]
        ids = [f["media_id"] for f in filas]
        self.assertEqual(ids, ["m1", "m2", "h2", "m3", "m5"], "la publicación vieja se descarta; del carrusel, hijos de foto distintos del cover; sin url propia se usa la del primer hijo (y no se repite como fila aparte)")
        f0 = filas[0]
        for c in ("account_name", "media_id", "media_type", "media_url", "media_thumbnail_url", "media_permalink", "media_timestamp", "media_like_count", "media_comments_count", "profile_followers_count", "media_caption"):
            self.assertIn(c, f0)
        self.assertEqual((f0["account_name"], f0["profile_followers_count"], f0["media_like_count"]), ("gucci", 5000, 11))
        self.assertEqual([f["media_url"] for f in filas if f["media_id"] == "m5"], ["https://cdn.example/h9.jpg"])
        self.assertEqual(res["tipo_token"], "persona")
        self.assertEqual(res["leidas"], 1)

    def test_cuenta_no_profesional_queda_sin_lectura_sin_romper_el_resto(self):
        g = Grafo(accounts=PAGINA, cuentas={"gucci": [[media(1)]]})   # «persona» no existe en el grafo → error 110
        por, res = im.meta_filas(["persona", "gucci"], TOKEN, abrir=g, pausa=0, ahora=AHORA)
        self.assertEqual(list(por), ["gucci"])
        self.assertIn("profesional", res["sin_lectura"]["persona"])

    def test_si_el_cupo_se_agota_a_mitad_se_devuelve_lo_leido_y_se_avisa(self):
        g = Grafo(accounts=PAGINA, cuentas={"a": [[media(1)]], "c": [[media(3)]]}, errores={"b": (400, 613, "Calls to this api have exceeded the rate limit.")})
        por, res = im.meta_filas(["a", "b", "c"], TOKEN, abrir=g, pausa=0, ahora=AHORA)
        self.assertEqual(list(por), ["a"])
        self.assertTrue(res["avisos"])
        self.assertIn("c", res["sin_lectura"])

    def test_un_fallo_de_token_en_la_primera_cuenta_es_un_error(self):
        g = Grafo(accounts=PAGINA, errores={"a": (400, 190, "Error validating access token")})
        with self.assertRaises(im.MetaError):
            im.meta_filas(["a"], TOKEN, abrir=g, pausa=0, ahora=AHORA)

    def test_pagina_siguiente_solo_si_la_primera_se_llena_y_aun_hay_ventana(self):
        llena = [media(i) for i in range(im.MEDIA_POR_PAGINA)]
        g = Grafo(accounts=PAGINA, cuentas={"zara": [llena, [media(100)]]})
        por, _ = im.meta_filas(["zara"], TOKEN, abrir=g, pausa=0, ahora=AHORA)
        self.assertEqual(len(por["zara"]), im.MEDIA_POR_PAGINA + 1)
        self.assertTrue(any(".after(1)" in c for _, c in g.peticiones))
        g2 = Grafo(accounts=PAGINA, cuentas={"zara": [[media(1), media(2)], [media(100)]]})
        im.meta_filas(["zara"], TOKEN, abrir=g2, pausa=0, ahora=AHORA)
        self.assertFalse(any(".after(" in c for _, c in g2.peticiones), "una página corta no pide más")

    def test_si_el_token_de_persona_no_sirve_se_usa_el_de_la_pagina(self):
        g = Grafo(accounts=PAGINA, cuentas={"gucci": [[media(1)]], "zara": [[media(2)]]}, rechaza={TOKEN: (403, 10, "(#10) Application does not have permission for this action")})
        por, res = im.meta_filas(["gucci", "zara"], TOKEN, abrir=g, pausa=0, ahora=AHORA)
        self.assertEqual(sorted(por), ["gucci", "zara"])
        self.assertEqual(res["token_usado"], "página")
        self.assertTrue(any("página" in a for a in res["avisos"]))

    def test_si_ninguno_de_los_dos_tokens_sirve_el_error_dice_que_faltan_permisos(self):
        g = Grafo(accounts=PAGINA, cuentas={"gucci": [[media(1)]]}, rechaza={TOKEN: (403, 10, "(#10) sin permiso"), "PAGTOKEN-no-caduca": (403, 10, "(#10) sin permiso")})
        with self.assertRaises(im.MetaError) as cm:
            im.meta_filas(["gucci"], TOKEN, abrir=g, pausa=0, ahora=AHORA)
        self.assertEqual(cm.exception.tipo, "permisos")
        self.assertIn("permiso", str(cm.exception))

    def test_dias_restantes_del_token_de_persona(self):
        import time as _t
        g = Grafo(accounts=PAGINA, cuentas={"gucci": [[media(1)]]}, debug={"type": "USER", "is_valid": True, "expires_at": int(_t.time()) + 10 * 86400 + 600, "scopes": ["instagram_basic"]})
        _, res = im.meta_filas(["gucci"], TOKEN, abrir=g, pausa=0, ahora=AHORA)
        self.assertEqual(res["dias_restantes"], 10)
        g2 = Grafo(accounts=PAGINA, cuentas={"gucci": [[media(1)]]}, debug={"type": "PAGE", "is_valid": True, "expires_at": 0, "scopes": []})
        self.assertIsNone(im.meta_filas(["gucci"], TOKEN, abrir=g2, pausa=0, ahora=AHORA)[1]["dias_restantes"], "un token de página sin caducidad no avisa")

    def test_si_meta_rechaza_un_campo_opcional_se_quita_y_se_sigue(self):
        veces = {"n": 0}
        base = Grafo(accounts=PAGINA, cuentas={"zara": [[media(1)]]})

        def abrir(req, timeout=0):
            campos = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query).get("fields", [""])[0]
            if "business_discovery" in campos and ("thumbnail_url" in campos or "children" in campos):
                veces["n"] += 1
                malo = "thumbnail_url" if "thumbnail_url" in campos else "children"
                raise urllib.error.HTTPError(req.full_url, 400, "x", {}, io.BytesIO(json.dumps({"error": {"code": 100, "message": f"(#100) Tried accessing nonexisting field ({malo}) on node type (IGMedia)"}}).encode()))
            return base(req, timeout)

        por, _ = im.meta_filas(["zara"], TOKEN, abrir=abrir, pausa=0, ahora=AHORA)
        self.assertEqual(len(por["zara"]), 1)
        self.assertEqual(veces["n"], 2, "una vez por campo rechazado; después se recuerda")
        por2, _ = im.meta_filas(["zara"], TOKEN, abrir=abrir, pausa=0, ahora=AHORA)
        self.assertEqual(veces["n"], 4, "cada ejecución vuelve a empezar pidiéndolos todos")
        self.assertEqual(len(por2["zara"]), 1)

    def test_el_token_no_sale_en_ningun_error(self):
        def abrir_red(req, timeout=0):
            raise OSError("fallo con " + req.full_url)

        with self.assertRaises(im.MetaError) as cm:
            im.meta_filas(["a"], TOKEN, abrir=abrir_red, pausa=0)
        self.assertNotIn(TOKEN, str(cm.exception))
        self.assertNotIn("access_token", str(cm.exception))
        with self.assertRaises(im.MetaError) as cm:
            im.meta_filas(["a"], "", abrir=abrir_red)
        self.assertIn("META_IG_TOKEN", str(cm.exception))


class PruebasCombinacion(unittest.TestCase):
    def setUp(self):
        import tendencia_prenda as tp
        self.tp = tp
        self.antes = (tp.im.meta_filas, tp.windsor_filas)
        for k in ("META_IG_TOKEN", "META_IG_USER_ID", "WINDSOR_API_KEY"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.tp.im.meta_filas, self.tp.windsor_filas = self.antes
        for k in ("META_IG_TOKEN", "META_IG_USER_ID", "WINDSOR_API_KEY"):
            os.environ.pop(k, None)

    def _falsos(self, meta=None, windsor=None):
        llamadas = {"meta": [], "windsor": []}

        def f_meta(handles, token, ig_id="", dias=35, **kw):
            llamadas["meta"].append(list(handles))
            if isinstance(meta, Exception):
                raise meta
            return meta, {"tipo_token": "página", "detalle": "x", "leidas": len(meta), "avisos": [], "sin_lectura": {}}

        def f_windsor(handles, dias=35, **kw):
            llamadas["windsor"].append(list(handles))
            if isinstance(windsor, Exception):
                raise windsor
            return windsor

        self.tp.im.meta_filas, self.tp.windsor_filas = f_meta, f_windsor
        return llamadas

    def test_sin_ninguna_clave_falla_claro(self):
        with self.assertRaises(ValueError) as cm:
            self.tp.instagram_filas(["a"])
        self.assertIn("META_IG_TOKEN", str(cm.exception))
        self.assertIn("WINDSOR_API_KEY", str(cm.exception))

    def test_solo_meta_no_llama_a_windsor_si_lo_lee_todo(self):
        os.environ["META_IG_TOKEN"] = TOKEN
        os.environ["WINDSOR_API_KEY"] = "w" * 30
        ll = self._falsos(meta={"a": [{"x": 1}], "b": [{"x": 2}]}, windsor={})
        self.assertEqual(set(self.tp.instagram_filas(["a", "b"])), {"a", "b"})
        self.assertEqual(ll["windsor"], [], "Meta lo leyó todo: Windsor no hace falta")

    def test_windsor_completa_lo_que_meta_no_lee_y_meta_manda(self):
        os.environ["META_IG_TOKEN"] = TOKEN
        os.environ["WINDSOR_API_KEY"] = "w" * 30
        ll = self._falsos(meta={"a": [{"de": "meta"}]}, windsor={"b": [{"de": "windsor"}]})
        por = self.tp.instagram_filas(["a", "b"])
        self.assertEqual(ll["windsor"], [["b"]])
        self.assertEqual((por["a"][0]["de"], por["b"][0]["de"]), ("meta", "windsor"))

    def test_si_meta_falla_se_usa_windsor_sin_romper(self):
        os.environ["META_IG_TOKEN"] = TOKEN
        os.environ["WINDSOR_API_KEY"] = "w" * 30
        self._falsos(meta=im.MetaError("El token de Meta no vale"), windsor={"a": [{"de": "windsor"}]})
        self.assertEqual(self.tp.instagram_filas(["a"])["a"][0]["de"], "windsor")

    def test_si_fallan_las_dos_el_error_cuenta_las_dos_cosas(self):
        os.environ["META_IG_TOKEN"] = TOKEN
        os.environ["WINDSOR_API_KEY"] = "w" * 30
        self._falsos(meta=im.MetaError("El token de Meta no vale"), windsor=ValueError("Windsor contestó HTTP 400"))
        with self.assertRaises(ValueError) as cm:
            self.tp.instagram_filas(["a"])
        self.assertIn("Meta", str(cm.exception))
        self.assertIn("Windsor", str(cm.exception))

    def test_aviso_de_caducidad_se_guarda_y_se_quita(self):
        os.environ["META_IG_TOKEN"] = TOKEN
        f = self.tp.TD / "avisos.json"
        if f.exists():
            f.unlink()
        llam = self._falsos(meta={"a": [{"x": 1}]})
        self.tp.im.meta_filas = lambda handles, token, ig_id="", dias=35, **kw: ({"a": [{"x": 1}]}, {"tipo_token": "persona", "detalle": "x", "leidas": 1, "avisos": [], "dias_restantes": 7})
        self.tp.instagram_filas(["a"])
        self.assertIn("caduca en 7 días", json.loads(f.read_text(encoding="utf-8"))["instagram"])
        self.tp.im.meta_filas = lambda handles, token, ig_id="", dias=35, **kw: ({"a": [{"x": 1}]}, {"tipo_token": "persona", "detalle": "x", "leidas": 1, "avisos": [], "dias_restantes": 50})
        self.tp.instagram_filas(["a"])
        self.assertNotIn("instagram", json.loads(f.read_text(encoding="utf-8")))

    def test_un_fallo_imprevisto_del_lector_de_meta_no_quita_windsor(self):
        os.environ["META_IG_TOKEN"] = TOKEN
        os.environ["WINDSOR_API_KEY"] = "w" * 30
        self._falsos(meta=KeyError("media"), windsor={"a": [{"de": "windsor"}]})
        self.assertEqual(self.tp.instagram_filas(["a"])["a"][0]["de"], "windsor")
        av = json.loads((self.tp.TD / "avisos.json").read_text(encoding="utf-8"))["instagram"]
        self.assertIn("KeyError", av)
        self.assertNotIn(TOKEN, av)

    def test_si_el_lector_de_meta_falla_de_forma_imprevista_y_no_hay_windsor_se_dice_claro(self):
        os.environ["META_IG_TOKEN"] = TOKEN
        self._falsos(meta=TypeError("raro"))
        with self.assertRaises(ValueError) as cm:
            self.tp.instagram_filas(["a"])
        self.assertIn("TypeError", str(cm.exception))
        self.assertNotIn(TOKEN, str(cm.exception))

    def test_cosechar_no_repite_la_lectura_tras_un_fallo_imprevisto(self):
        os.environ["META_IG_TOKEN"] = TOKEN
        cfg = Path(tempfile.mkdtemp()) / "f.json"
        cfg.write_text(json.dumps({"fuentes": [{"tipo": "instagram", "valor": v, "referente": "R", "estilo": "lujo", "mercado": "US"} for v in ("a", "b", "c")]}), encoding="utf-8")
        antes_f, antes_i = self.tp.FUENTES, self.tp.instagram_filas
        veces = []
        try:
            self.tp.FUENTES = cfg
            self.tp._IG_CACHE.clear()

            def rota(handles, **kw):
                veces.append(1)
                raise RuntimeError("no debería ocurrir")

            self.tp.instagram_filas = rota
            for v in ("a", "b", "c"):
                with self.assertRaises(Exception):
                    self.tp.cosechar_instagram({"tipo": "instagram", "valor": v, "referente": "R", "estilo": "lujo", "mercado": "US"}, {})
            self.assertEqual(len(veces), 1, "se lee una sola vez y el fallo se recuerda para el resto de cuentas")
        finally:
            self.tp.FUENTES, self.tp.instagram_filas = antes_f, antes_i
            self.tp._IG_CACHE.clear()

    def test_meta_bien_y_windsor_caducado_no_es_un_error(self):
        os.environ["META_IG_TOKEN"] = TOKEN
        os.environ["WINDSOR_API_KEY"] = "w" * 30
        self._falsos(meta={"a": [{"x": 1}]}, windsor=ValueError("Windsor contestó HTTP 400"))
        self.assertEqual(list(self.tp.instagram_filas(["a", "b"])), ["a"], "tras la prueba de Windsor, la clave vieja falla pero Meta sigue leyendo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
