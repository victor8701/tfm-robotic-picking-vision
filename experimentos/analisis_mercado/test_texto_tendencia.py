"""Pruebas del generador de texto de tendencia (texto_tendencia.py): determinista, sin inventar, con el vocabulario completo y dentro del límite de CLIP. Sin red ni GPU. Uso:  python3 test_texto_tendencia.py"""
import sys
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "vlm_atributos_prenda" / "herramientas" / "vlm_profesor"))
import texto_tendencia as tt  # noqa: E402


def cat(valor, estilo, resto, q=0.001, n=50):
    return {"valor": valor, "estilo": estilo, "resto": resto, "dif": round(estilo - resto, 3), "q": q, "n": n}


def evidencia_falsa():
    return {"prendas": 100, "fotos": 40,
            "tipo": [cat("Americana", .25, .04), cat("Pantalón", .33, .20), cat("Zapatos de vestir", .18, .04), cat("Camisa", .10, .12, q=.6), cat("Bolso", .02, .03, q=.5), cat("Vestido", .04, .02, q=.9)],
            "forma": [cat("regular", .70, .50), cat("ajustada", .21, .10), cat("oversized / baggy", .02, .16)],
            "estampado": [cat("liso", .85, .66), cat("texto / logo", .00, .10)],
            "tejido": [cat("algodón", .40, .60), cat("lino", .11, .02)]}


class Pruebas(unittest.TestCase):
    def test_el_vocabulario_del_modelo_grande_esta_cubierto(self):
        import kernel_profesor as kp
        tipos = {n for n, _ in kp.TIPOS_V}
        self.assertEqual(tipos - set(tt.TIPO_EN), set(), "todo tipo que puede dar el modelo grande tiene su palabra en inglés")
        # valores que el modelo puede dar: o se traducen o se omiten a propósito (los de por defecto)
        omitidos = {"estampado": set(), "tejido": {"algodón", "no se distingue"}, "forma": {"regular", "no aplica"}}
        for campo, tabla in (("estampado", kp.OPC["pattern"]), ("tejido", kp.OPC["fabric"]), ("forma", kp.OPC["fit"])):
            for valor in tabla.values():
                self.assertTrue(valor in tt.TABLA[campo] or valor in omitidos[campo], f"{campo}: «{valor}» no está ni traducido ni omitido a propósito")

    def test_las_prendas_son_las_que_distinguen_y_no_las_mas_frecuentes(self):
        prendas, mods = tt.elegir(evidencia_falsa())
        nombres = [p["valor"] for p in prendas]
        self.assertEqual(nombres[:3], ["Americana", "Zapatos de vestir", "Pantalón"], "ordenadas por diferencia con el resto, no por cuota")
        self.assertNotIn("Camisa", nombres[:3], "una prenda por debajo del resto no distingue (aunque salga frecuente)")
        self.assertNotIn("Bolso", nombres, "con menos del 5 % de cuota no entra")
        self.assertEqual([m["valor"] for m in mods], ["liso", "ajustada", "lino"], "modificadores de más a menos diferencia; «regular» y «algodón» no entran; «liso» solo con +15 puntos")

    def test_un_estilo_sin_rasgo_propio_se_completa_con_lo_mas_frecuente(self):
        ev = {"prendas": 80, "fotos": 30, "tipo": [cat("Camisa", .20, .19, q=.9), cat("Pantalón", .30, .29, q=.9), cat("Vestido", .10, .11, q=.9), cat("Top", .06, .06, q=.9)], "forma": [], "estampado": [], "tejido": []}
        prendas, mods = tt.elegir(ev)
        self.assertEqual([p["valor"] for p in prendas], ["Pantalón", "Camisa", "Vestido"], "mínimo 3, las más frecuentes")
        self.assertEqual(mods, [])

    def test_el_texto_es_determinista_ascii_y_corto(self):
        ev = evidencia_falsa()
        prendas, mods = tt.elegir(ev)
        a, b = tt.texto_en("old_money", prendas, mods), tt.texto_en("old_money", prendas, mods)
        self.assertEqual(a, b)
        self.assertTrue(a.isascii(), a)
        self.assertLess(len(a.split()), 40, "muy por debajo de los 77 tokens de CLIP")
        self.assertTrue(a.startswith("old money style outfit, plain solid-color, slim-fit, linen: blazer"), a)
        es = tt.texto_es("old_money", prendas, mods, 40)
        self.assertIn("americana (25 %)", es)
        self.assertIn("40 fotos", es)

    def test_trend_json_cumple_el_formato_de_estado_arte_6_4(self):
        sep = {"dimensiones": [{"dimension": d, "estilos": {"old_money": {"prendas": 100, "fotos": 40, "categorias": [{"categoria": c["valor"], **{k: v for k, v in c.items() if k != "valor"}} for c in evidencia_falsa()[d]]}}} for d in ("tipo", "forma", "estampado", "tejido")]}
        t = tt.trend_json("old_money", sep, fecha="2026-10-16")
        for campo in ("mercado", "genero_objetivo", "tipo_prenda", "fuentes", "fecha_analisis", "descripcion", "grupo_estilo_detectado", "intensidad", "estado"):
            self.assertIn(campo, t)
        self.assertEqual(t["estado"], "pendiente")
        self.assertTrue(set(t["grupo_estilo_detectado"]) <= {"Casual", "Streetwear", "De vestir", "Fiesta/Noche", "Deportivo", "Playa/Resort"}, "solo valores del ERP (Estado_arte §3.4.1)")
        self.assertEqual(t["grupo_estilo_detectado"], ["De vestir", "Casual"])
        self.assertEqual(t["evidencia"]["receta"], tt.VERSION_RECETA)

    def test_todos_los_estilos_tienen_nombre_y_grupo(self):
        for e in tt.CLAVE_B:
            self.assertIn(e, tt.NOMBRE_ES)
            self.assertIn(e, tt.NOMBRE_EN)
            self.assertTrue(tt.GRUPOS_ERP[e])


if __name__ == "__main__":
    unittest.main()
