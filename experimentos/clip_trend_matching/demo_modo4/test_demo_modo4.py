"""Pruebas del flujo Trend JSON → puntuación de SKUs → aprobación (demo del Modo 4). Sin red, sin CLIP, sin imágenes. Uso:  python3 test_demo_modo4.py"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import hmi_aprobacion as hmi  # noqa: E402
import puntuar_skus as ps  # noqa: E402
import trend_json_mercado as tj  # noqa: E402

SEIS_GRUPOS = {"Casual", "Streetwear", "De vestir", "Fiesta/Noche", "Deportivo", "Playa/Resort"}


def casilla(estilo="urbano", mercado="US", temp="OI 2026/27", prendas=None, fotos=40):
    prendas = prendas if prendas is not None else [("Pantalón", 0.30, 12), ("Chaqueta", 0.22, 9), ("Zapatillas deportivas", 0.15, 6), ("Hoodie", 0.12, 5), ("Camiseta manga corta", 0.08, 3)]
    return {"estilo": estilo, "mercado": mercado, "temporada": temp, "fotos": fotos, "fotos_efectivas": fotos * 0.6, "fuentes": {"x: A": 10, "r/streetwear": 30},
            "prendas": [{"tipo": t, "cuota": c, "fotos": n, "ic": [c - .1, c + .1], "confianza": "baja"} for t, c, n in prendas]}


def sep(estilo="urbano"):
    cat = lambda v, e, r, q: {"categoria": v, "estilo": e, "resto": r, "dif": e - r, "q": q, "n": 20}  # noqa: E731
    return {"dimensiones": [
        {"dimension": "tipo", "estilos": {estilo: {"prendas": 100, "fotos": 40, "categorias": [cat("Pantalón", .3, .2, .01), cat("Hoodie", .15, .05, .01)]}}},
        {"dimension": "forma", "estilos": {estilo: {"prendas": 100, "fotos": 40, "categorias": [cat("oversized / baggy", .5, .2, .01), cat("regular", .4, .6, .01)]}}},
        {"dimension": "estampado", "estilos": {estilo: {"prendas": 100, "fotos": 40, "categorias": [cat("texto / logo", .3, .15, .02)]}}},
        {"dimension": "tejido", "estilos": {estilo: {"prendas": 100, "fotos": 40, "categorias": []}}}]}


class Pruebas(unittest.TestCase):
    def test_casilla_con_datos_genera_el_trend_json_de_la_seccion_6_4(self):
        t, motivo = tj.trend_de_casilla(casilla(), sep(), "2026-10-25")
        self.assertIsNone(motivo)
        for k in ("mercado", "genero_objetivo", "tipo_prenda", "fuentes", "fecha_analisis", "descripcion", "grupo_estilo_detectado", "intensidad", "estado"):
            self.assertIn(k, t, f"campo de §6.4: {k}")
        self.assertEqual((t["estado"], t["mercado"], t["id"]), ("pendiente", "EEUU", "2026-10-25_US_urbano"))
        self.assertTrue(set(t["grupo_estilo_detectado"]) <= SEIS_GRUPOS, "solo valores del vocabulario cerrado del ERP")
        self.assertIsNone(t["intensidad"], "la intensidad no se inventa")
        self.assertEqual(len(t["evidencia"]["prendas"]), 4, "solo prendas con al menos 5 fotos (la quinta tiene 3)")

    def test_texto_ingles_corto_con_los_rasgos_del_estilo_y_las_prendas_de_la_casilla(self):
        t, _ = tj.trend_de_casilla(casilla(), sep(), "2026-10-25")
        self.assertEqual(t["descripcion_clip"], "urban style outfit, oversized baggy, logo print: trousers, jacket, sneakers, hoodie")
        self.assertIn("pantalón (30 %", t["descripcion"])
        self.assertIn("confianza baja", t["descripcion"])

    def test_casilla_con_pocas_prendas_no_se_genera_y_dice_por_que(self):
        t, motivo = tj.trend_de_casilla(casilla(prendas=[("Pantalón", .5, 6), ("Chaqueta", .3, 3)]), sep(), "2026-10-25")
        self.assertIsNone(t)
        self.assertIn("solo 1 prendas", motivo)

    def test_el_indice_cubre_las_14_casillas(self):
        informe = {"grupos": [casilla(), casilla("lujo", "ES", prendas=[("Vestido", .5, 6)]), casilla("urbano", "US", "PV 2026"), casilla("urbano", "Biblioteca", "muestra")]}
        trends, indice = tj.generar(informe, sep(), "2026-10-25")
        self.assertEqual(len(indice), 14, "7 estilos × 2 mercados")
        self.assertEqual(len(trends), 1)
        por = {(x["estilo"], x["mercado"]): x for x in indice}
        self.assertTrue(por[("urbano", "US")]["generada"])
        self.assertFalse(por[("lujo", "ES")]["generada"])
        self.assertIn("ninguna foto", por[("geek", "US")]["motivo"])

    def test_temporada_por_fecha(self):
        from datetime import datetime
        self.assertEqual(tj.temporada(datetime(2026, 10, 25)), "OI 2026/27")
        self.assertEqual(tj.temporada(datetime(2027, 1, 5)), "OI 2026/27")
        self.assertEqual(tj.temporada(datetime(2026, 5, 1)), "PV 2026")

    def test_puntuacion_coseno_mas_boost_y_umbral(self):
        V = np.array([[1, 0], [0.9, 0.436], [0, 1], [0.6, 0.8]], dtype=np.float32)
        V /= np.linalg.norm(V, axis=1, keepdims=True)
        grupos = ["Casual", "Streetwear", "Streetwear", None]
        top = ps.puntuar(np.array([1.0, 0.0]), V, grupos, ["Streetwear"], beta=0.1, theta=0.5, k=4)
        self.assertEqual([r["i"] for r in top], [0, 1, 3, 2], "orden por score: el idéntico, el de Streetwear (+0,1), el sin grupo, el ortogonal con boost")
        self.assertAlmostEqual(top[1]["boost"], 0.1)
        self.assertEqual(top[3]["semantico"], 0.0)
        self.assertAlmostEqual(top[3]["score"], 0.1)
        self.assertEqual([r["alineado"] for r in top], [True, True, True, False], "alineado = coseno ≥ θ, sin contar el boost")
        self.assertEqual(top[2]["boost"], 0.0, "un SKU sin grupo del ERP no recibe boost")
        self.assertEqual(len(ps.puntuar(np.array([1.0, 0.0]), V, grupos, ["Casual"], k=2)), 2)

    def test_grupos_del_catalogo_por_carpeta(self):
        self.assertEqual(ps.GRUPO_ERP["de_vestir"], "De vestir")
        self.assertEqual(set(ps.GRUPO_ERP.values()), SEIS_GRUPOS)

    def test_aplicar_mueve_lo_aprobado_con_vector_y_lo_rechazado(self):
        raiz = Path(tempfile.mkdtemp())
        trends = raiz / "trends"
        (trends / "pending").mkdir(parents=True)
        for id_ in ("a", "b", "c"):
            (trends / "pending" / f"{id_}.json").write_text(json.dumps({"id": id_, "descripcion_clip": f"texto {id_}", "estado": "pendiente"}), encoding="utf-8")
        dec = raiz / "dec"
        dec.mkdir()
        for d in ({"id": "a", "e": "aprobada", "n": "vale"}, {"id": "b", "e": "rechazada", "n": ""}, {"id": "c", "e": ""}):
            (dec / f"{d['id']}.json").write_text(json.dumps(d), encoding="utf-8")
        hmi.cmd_aplicar(SimpleNamespace(dir=str(dec), trends=trends), codificar=lambda texto: [0.5, 0.5])
        act = json.loads((trends / "active" / "a.json").read_text(encoding="utf-8"))
        self.assertEqual((act["estado"], act["v_tendencia"], act["nota_operario"]), ("aprobada", [0.5, 0.5], "vale"))
        self.assertEqual(json.loads((trends / "rejected" / "b.json").read_text(encoding="utf-8"))["estado"], "rechazada")
        self.assertEqual([f.name for f in (trends / "pending").glob("*.json")], ["c.json"], "lo que no tiene decisión sigue pendiente")


if __name__ == "__main__":
    unittest.main(verbosity=2)
