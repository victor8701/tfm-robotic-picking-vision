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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

os.environ["TENDENCIA_DATOS"] = tempfile.mkdtemp(prefix="test_meta_")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import instagram_meta as im  # noqa: E402
import prueba_instagram as pi  # noqa: E402

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


class GrafoConCuota(Grafo):
    """Como Grafo, pero cada respuesta de Business Discovery lleva x-app-usage con el porcentaje de `usos` (el último se repite), el sondeo `id` contesta con `sondeos`
    y una cuenta puede cortarse con el código 4 las veces que diga `cortes` antes de contestar bien."""

    def __init__(self, *a, usos=(0,), sondeos=(0,), cortes=None, **k):
        super().__init__(*a, **k)
        self.usos, self.sondeos, self.cortes = list(usos), list(sondeos), dict(cortes or {})
        self.n_sondeos = 0

    @staticmethod
    def _con_uso(resp, tiempo):
        resp.headers = {"x-app-usage": json.dumps({"call_count": 1, "total_cputime": 0, "total_time": tiempo})}
        return resp

    def __call__(self, req, timeout=0):
        campos = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query).get("fields", [""])[0]
        if campos == "id":
            self.n_sondeos += 1
            tiempo = self.sondeos.pop(0) if len(self.sondeos) > 1 else self.sondeos[0]
            resp = Resp(b'{"id": "17841400000"}')
            if tiempo is None:   # con la ventana vacía Meta no manda la cabecera
                resp.headers = {}
                return resp
            return self._con_uso(resp, tiempo)
        m = re.search(r"business_discovery\.username\(([^)]+)\)", campos)
        if m and self.cortes.get(m.group(1), 0) > 0:
            self.cortes[m.group(1)] -= 1
            raise error_http(req.full_url, 400, 4, "(#4) Application request limit reached")
        resp = super().__call__(req, timeout)
        if m:
            self._con_uso(resp, self.usos.pop(0) if len(self.usos) > 1 else self.usos[0])
        return resp


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

    def test_la_prueba_de_coste_mide_cuatro_formas_y_no_revienta(self):
        g = GrafoConCuota(accounts=PAGINA, cuentas={c: [[media(1)]] for c in pi.CUENTAS_COSTE}, usos=[5, 9, 12, 14, 17, 19, 21, 22, 23, 24, 25, 26], sondeos=[0, 8, 17, 23])
        pi.LINEAS.clear()
        pi.prueba_coste("17841400000", TOKEN, AHORA - timedelta(days=35), abrir=g)
        lineas = [x for x in pi.LINEAS if x.startswith("   · ")]
        self.assertEqual(len(lineas), len(pi.FORMAS_COSTE))
        self.assertIn("cuentas por hora", lineas[0])

    def test_la_prueba_de_coste_parte_de_cero_si_meta_no_manda_la_cabecera_con_la_ventana_vacia(self):
        g = GrafoConCuota(accounts=PAGINA, cuentas={c: [[media(1)]] for c in pi.CUENTAS_COSTE}, usos=[4, 8, 12, 14, 16, 18, 19, 20, 21, 22, 23, 24], sondeos=[None, 12, 18, 21])
        pi.LINEAS.clear()
        pi.prueba_coste("17841400000", TOKEN, AHORA - timedelta(days=35), abrir=g)
        self.assertTrue(any("se parte de cero" in x for x in pi.LINEAS))
        lineas = [x for x in pi.LINEAS if x.startswith("   · ")]
        self.assertEqual(len(lineas), len(pi.FORMAS_COSTE), "mide las cuatro formas aunque la primera consulta no traiga cabecera")
        self.assertIn("+4.0 de tiempo", lineas[0], "12 puntos de tiempo repartidos entre 3 cuentas")

    def test_la_prueba_de_coste_dice_que_es_de_cuota_si_meta_corta(self):
        g = GrafoConCuota(accounts=PAGINA, cuentas={c: [[media(1)]] for c in pi.CUENTAS_COSTE}, cortes={"stussy": 3})
        pi.LINEAS.clear()
        pi.CORTE_POR_CUOTA = False
        pi.prueba_coste("17841400000", TOKEN, AHORA - timedelta(days=35), abrir=g)
        self.assertTrue(pi.CORTE_POR_CUOTA)
        self.assertTrue(any("no es un fallo del token" in x for x in pi.LINEAS))
        pi.CORTE_POR_CUOTA = False

    def test_el_resumen_tambien_sale_como_anotacion_legible_sin_iniciar_sesion(self):
        cmd = pi.anotacion_resumen(["línea 1", "100 % seguro", "línea 3"])
        self.assertTrue(cmd.startswith("::notice title="))
        self.assertNotIn("\n", cmd)
        self.assertIn("100 %25 seguro", cmd)
        self.assertIn("%0A", cmd)

    def test_la_prueba_distingue_el_token_corto_del_largo(self):
        ahora = 1_800_000_000
        frase, corto = pi.texto_caducidad(ahora + 5400, 0, ahora)
        self.assertTrue(corto)
        self.assertIn("1,5 horas", frase)
        frase, corto = pi.texto_caducidad(ahora + 60 * 86400, 60, ahora)
        self.assertFalse(corto)
        self.assertIn("dentro de 60 días", frase)
        self.assertEqual(pi.texto_caducidad(0, None, ahora), ("no caduca", False))
        frase, corto = pi.texto_caducidad(ahora - 100, 0, ahora)
        self.assertIn("caducó", frase)
        self.assertFalse(corto)

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
        with mock.patch.object(im, "PAGINAS_MAX", 2):
            llena = [media(i) for i in range(im.MEDIA_POR_PAGINA)]
            g = Grafo(accounts=PAGINA, cuentas={"zara": [llena, [media(100)]]})
            por, _ = im.meta_filas(["zara"], TOKEN, abrir=g, pausa=0, ahora=AHORA)
            self.assertEqual(len(por["zara"]), im.MEDIA_POR_PAGINA + 1)
            self.assertTrue(any(".after(1)" in c for _, c in g.peticiones))
            g2 = Grafo(accounts=PAGINA, cuentas={"zara": [[media(1), media(2)], [media(100)]]})
            im.meta_filas(["zara"], TOKEN, abrir=g2, pausa=0, ahora=AHORA)
            self.assertFalse(any(".after(" in c for _, c in g2.peticiones), "una página corta no pide más")

    def test_por_defecto_una_sola_pagina_aunque_se_llene(self):
        llena = [media(i) for i in range(im.MEDIA_POR_PAGINA)]
        g = Grafo(accounts=PAGINA, cuentas={"zara": [llena, [media(100)]]})
        por, _ = im.meta_filas(["zara"], TOKEN, abrir=g, pausa=0, ahora=AHORA)
        self.assertEqual(len(por["zara"]), im.MEDIA_POR_PAGINA)
        self.assertFalse(any(".after(" in c for _, c in g.peticiones), "Meta limita por tiempo de proceso: una petición por cuenta")

    def test_leer_cuenta_puede_pedir_menos_y_sin_carruseles(self):
        g = Grafo(accounts=PAGINA, cuentas={"zara": [[media(1)]]})
        corte = AHORA - timedelta(days=35)
        im.leer_cuenta("17841400000", "zara", TOKEN, corte, abrir=g, limite=12, paginas=1, con_hijos=False)
        campos = g.peticiones[-1][1]
        self.assertIn("media.limit(12)", campos)
        self.assertNotIn("children", campos)
        im.leer_cuenta("17841400000", "zara", TOKEN, corte, abrir=g)
        self.assertIn(f"media.limit({im.MEDIA_POR_PAGINA})", g.peticiones[-1][1])
        self.assertNotIn("children", g.peticiones[-1][1], "por defecto no se piden los carruseles: cuestan 2,5 veces más cuota")
        im.leer_cuenta("17841400000", "zara", TOKEN, corte, abrir=g, con_hijos=True)
        self.assertIn("children", g.peticiones[-1][1])

    def test_uso_app_lee_la_cabecera_sin_importar_las_mayusculas(self):
        self.assertEqual(im.uso_app({"x-app-usage": '{"call_count":5,"total_cputime":0,"total_time":42}'}), 42.0)
        self.assertEqual(im.uso_app({"X-App-Usage": '{"call_count":61,"total_time":3}'}), 61.0)
        self.assertIsNone(im.uso_app({}))
        self.assertIsNone(im.uso_app({"x-app-usage": "no es json"}))
        self.assertIsNone(im.uso_app(None))

    def test_rotar_empieza_por_otro_sitio_y_no_pierde_cuentas(self):
        cuentas = [f"c{i}" for i in range(68)]
        self.assertEqual(im.rotar(cuentas, 0), cuentas)
        r = im.rotar(cuentas, 1)
        self.assertEqual(sorted(r), sorted(cuentas))
        self.assertNotEqual(r[0], cuentas[0])
        self.assertEqual(len({im.rotar(cuentas, k)[0] for k in range(10)}), 10, "diez semanas seguidas empiezan por diez cuentas distintas")
        self.assertEqual(im.rotar([], 3), [])

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

    @mock.patch.object(im, "CON_HIJOS", True)
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


class PruebasCuota(unittest.TestCase):
    """Meta limita la app por tiempo de proceso: con tiempo de espera, la lectura se pausa y sigue en vez de rendirse."""

    CUENTAS = {"a": [[media(1)]], "b": [[media(2)]], "c": [[media(3)]]}

    def test_con_la_cuota_casi_llena_espera_y_sigue(self):
        g = GrafoConCuota(accounts=PAGINA, cuentas=self.CUENTAS, usos=[90, 20, 20], sondeos=[30])
        pausas = []
        por, res = im.meta_filas(["a", "b", "c"], TOKEN, abrir=g, pausa=0, ahora=AHORA, espera_max_s=3600, dormir=pausas.append)
        self.assertEqual(sorted(por), ["a", "b", "c"])
        self.assertEqual(pausas, [im.SONDEO_S], "una sola espera: tras la primera cuenta, y el sondeo ya vio la cuota baja")
        self.assertEqual(res["esperado_s"], im.SONDEO_S)
        self.assertEqual(g.n_sondeos, 1)

    def test_sin_tiempo_de_espera_no_espera_nunca(self):
        g = GrafoConCuota(accounts=PAGINA, cuentas=self.CUENTAS, usos=[99])
        pausas = []
        por, res = im.meta_filas(["a", "b", "c"], TOKEN, abrir=g, pausa=0, ahora=AHORA, dormir=pausas.append)
        self.assertEqual(sorted(por), ["a", "b", "c"])
        self.assertEqual(pausas, [])
        self.assertEqual(res["esperado_s"], 0)

    def test_si_la_cuota_no_baja_dentro_del_presupuesto_se_para_con_aviso(self):
        g = GrafoConCuota(accounts=PAGINA, cuentas=self.CUENTAS, usos=[90], sondeos=[95])
        pausas = []
        por, res = im.meta_filas(["a", "b", "c"], TOKEN, abrir=g, pausa=0, ahora=AHORA, espera_max_s=2 * im.SONDEO_S, dormir=pausas.append)
        self.assertEqual(list(por), ["a"])
        self.assertEqual(len(pausas), 2, "se espera hasta agotar el presupuesto y ni un turno más")
        self.assertTrue(any("no se liberó a tiempo" in a for a in res["avisos"]))
        self.assertIn("b", res["sin_lectura"])
        self.assertIn("c", res["sin_lectura"])

    def test_un_codigo_4_a_mitad_espera_y_repite_la_misma_cuenta(self):
        g = GrafoConCuota(accounts=PAGINA, cuentas=self.CUENTAS, usos=[10], sondeos=[20], cortes={"b": 1})
        pausas = []
        por, res = im.meta_filas(["a", "b", "c"], TOKEN, abrir=g, pausa=0, ahora=AHORA, espera_max_s=3600, dormir=pausas.append)
        self.assertEqual(sorted(por), ["a", "b", "c"])
        self.assertEqual(len(pausas), 1)
        self.assertEqual(res["avisos"], [])

    def test_un_codigo_4_sin_presupuesto_de_espera_corta_como_antes(self):
        g = GrafoConCuota(accounts=PAGINA, cuentas=self.CUENTAS, cortes={"b": 5})
        por, res = im.meta_filas(["a", "b", "c"], TOKEN, abrir=g, pausa=0, ahora=AHORA)
        self.assertEqual(list(por), ["a"])
        self.assertTrue(res["avisos"])

    def test_un_codigo_4_en_la_primera_cuenta_espera_antes_de_rendirse(self):
        g = GrafoConCuota(accounts=PAGINA, cuentas=self.CUENTAS, usos=[10], sondeos=[20], cortes={"a": 1})
        por, _ = im.meta_filas(["a", "b"], TOKEN, abrir=g, pausa=0, ahora=AHORA, espera_max_s=3600, dormir=lambda s: None)
        self.assertEqual(sorted(por), ["a", "b"])
        g2 = GrafoConCuota(accounts=PAGINA, cuentas=self.CUENTAS, cortes={"a": 5})
        with self.assertRaises(im.MetaError) as cm:
            im.meta_filas(["a", "b"], TOKEN, abrir=g2, pausa=0, ahora=AHORA)
        self.assertEqual(cm.exception.tipo, "cupo")


class GrafoVentanaMovil:
    """Meta como se midió el 27-oct: cada petición de Business Discovery gasta `coste` puntos de total_time, la cuota es una ventana móvil de 1 h y al llegar a 100 corta con el código 4.
    Reloj virtual: `dormir` lo adelanta."""

    def __init__(self, coste):
        self.t, self.coste, self.gastos, self.pausas = 0.0, coste, [], []

    def uso(self):
        return round(sum(c for t, c in self.gastos if t > self.t - 3600))

    def dormir(self, s):
        self.pausas.append(s)
        self.t += s

    def __call__(self, req, timeout=0):
        u = urllib.parse.urlparse(req.full_url)
        ruta = u.path.split("/", 2)[2]
        campos = urllib.parse.parse_qs(u.query).get("fields", [""])[0]
        if ruta == "debug_token":
            resp = Resp(json.dumps({"data": {"type": "USER", "is_valid": True, "expires_at": 0, "scopes": []}}).encode())
        elif ruta == "me/accounts":
            resp = Resp(json.dumps({"data": PAGINA}).encode())
        elif campos == "id":
            self.gastos.append((self.t, 0.05))
            self.t += 0.3
            resp = Resp(b'{"id": "17841400000"}')
        else:
            if self.uso() >= 100:
                raise error_http(req.full_url, 400, 4, "(#4) Application request limit reached")
            usuario = re.search(r"business_discovery\.username\(([^)]+)\)", campos).group(1)
            self.gastos.append((self.t, self.coste))
            self.t += 1.3
            medios = [media(i) for i in range(20)]
            resp = Resp(json.dumps({"business_discovery": {"username": usuario, "followers_count": 10, "media": {"data": medios, "paging": {"cursors": {}}}}, "id": "17841"}).encode())
        resp.headers = {"x-app-usage": json.dumps({"call_count": 1, "total_cputime": 0, "total_time": self.uso()})}
        return resp


class PruebasCuotaMedida(unittest.TestCase):
    """Lo medido el 27-oct: ~1,2 puntos por cuenta con 20 publicaciones y sin carruseles; ~3 con carruseles."""

    CUENTAS = [f"cuenta{i}" for i in range(68)]

    def _lee(self, coste, espera_max_s=75 * 60):
        g = GrafoVentanaMovil(coste)
        por, res = im.meta_filas(self.CUENTAS, TOKEN, abrir=g, pausa=0, ahora=AHORA, espera_max_s=espera_max_s, dormir=g.dormir)
        return g, por, res

    def test_las_68_cuentas_con_el_coste_medido_se_leen_de_una_vez_sin_esperar(self):
        g, por, res = self._lee(1.2)
        self.assertEqual(len(por), 68)
        self.assertEqual(g.pausas, [])
        self.assertEqual(res["avisos"], [])

    def test_si_cada_cuenta_costara_el_doble_se_espera_una_hora_y_se_leen_todas(self):
        g, por, res = self._lee(2.4)
        self.assertEqual(len(por), 68)
        self.assertTrue(g.pausas)
        self.assertLessEqual(res["esperado_s"], 75 * 60)
        self.assertGreater(res["esperado_s"], 30 * 60, "una ráfaga no sale de la ventana móvil hasta pasada 1 h")

    def test_con_los_carruseles_y_poco_presupuesto_se_lee_lo_que_cabe_y_se_avisa(self):
        g, por, res = self._lee(3.0, espera_max_s=10 * 60)
        self.assertLess(len(por), 68)
        self.assertTrue(any("no se liberó a tiempo" in a for a in res["avisos"]))
        self.assertEqual(len(por) + len(res["sin_lectura"]), 68, "cada cuenta o se lee o queda anotada como sin lectura")


class PruebasEnsayoSemanal(unittest.TestCase):
    """El modo «todas» de la prueba de Instagram: lo mismo que hará la tarea del lunes con las 68 cuentas, contado en español."""

    CUENTAS = [f"cuenta{i}" for i in range(68)]

    def setUp(self):
        os.environ.pop("META_IG_USER_ID", None)
        pi.LINEAS.clear()
        pi.CORTE_POR_CUOTA = False
        self.addCleanup(setattr, pi, "CORTE_POR_CUOTA", False)
        parche = mock.patch.object(pi, "foto_bajable", return_value="sí")
        parche.start()
        self.addCleanup(parche.stop)

    def _ensaya(self, coste, espera_s=6 * 60):
        g = GrafoVentanaMovil(coste)
        with mock.patch.object(pi, "ESPERA_ENSAYO_S", espera_s):
            ok = pi.ensayo_semanal(TOKEN, self.CUENTAS, abrir=g, pausa=0, dormir=g.dormir, ahora=AHORA)
        return ok, g, "\n".join(pi.LINEAS)

    def test_con_el_coste_medido_se_leen_las_68_sin_esperar(self):
        ok, g, texto = self._ensaya(1.2)
        self.assertTrue(ok)
        self.assertEqual(g.pausas, [])
        self.assertIn("Leídas 68 de 68 cuentas: 1360 publicaciones", texto)
        self.assertIn("Cuota de la app al final: 82 %", texto)
        self.assertIn("Fotos que se pueden bajar: 4 de 4", texto)
        self.assertIn("✔ Meta dejó leer todas las cuentas", texto)
        self.assertFalse(pi.CORTE_POR_CUOTA)

    def test_si_cada_cuenta_costara_el_doble_dice_que_meta_corto_y_marca_el_corte_por_cuota(self):
        ok, g, texto = self._ensaya(2.4)
        self.assertFalse(ok)
        self.assertTrue(pi.CORTE_POR_CUOTA)
        self.assertIn("✘ Meta cortó antes de terminar", texto)
        self.assertIn("la cuota de la app de Meta no se liberó a tiempo", texto)
        self.assertNotIn("Leídas 68 de 68", texto)

    def test_un_fallo_de_token_se_cuenta_sin_sacar_el_token(self):
        def abrir(req, timeout=0):
            raise error_http(req.full_url, 400, 190, "Invalid OAuth access token")

        self.assertFalse(pi.ensayo_semanal(TOKEN, self.CUENTAS, abrir=abrir, pausa=0, dormir=lambda s: None, ahora=AHORA))
        self.assertNotIn(TOKEN, "\n".join(pi.LINEAS))
        self.assertFalse(pi.CORTE_POR_CUOTA, "un token malo no es un corte por cuota")


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
