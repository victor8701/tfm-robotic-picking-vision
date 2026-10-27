"""Pruebas del orden por turnos y del tope de tiempo del análisis de fotos (tendencia_prenda.py). Sin red ni torch. Uso:  python3 test_tendencia_cupo.py"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["TENDENCIA_DATOS"] = tempfile.mkdtemp(prefix="test_cupo_")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tendencia_prenda as tp  # noqa: E402


def foto(fuente, ref, dia):
    return {"fuente": fuente, "referente": ref, "estilo": "lujo", "mercado": "US", "fecha": f"2026-10-{dia:02d}T10:00:00+00:00" if dia else None}


class Pruebas(unittest.TestCase):
    def test_fuentes_por_turnos_y_lo_reciente_primero(self):
        fotos = {f"a{i}": foto("x", "A", i) for i in range(1, 7)}            # una fuente con muchas fotos
        fotos.update({"b1": foto("reddit", "B", 3), "b2": foto("reddit", "B", 9), "c1": foto("noticias", "C", 5)})
        orden = tp.ordenar_pendientes(fotos, list(fotos))
        self.assertEqual(sorted(orden), sorted(fotos), "no se pierde ni se repite ninguna foto")
        self.assertEqual(set(orden[:3]), {"a6", "b2", "c1"}, "primer turno: la foto más reciente de cada fuente")
        self.assertEqual(orden[3:5], ["b1", "a5"], "segundo turno: la siguiente de cada fuente que aún tenga fotos (la de noticias ya no tiene)")
        primeras_seis = set(orden[:6])
        self.assertTrue({"a6", "b2", "c1", "b1"} <= primeras_seis, "con un tope de 6 fotos, las tres fuentes están representadas")

    def test_un_tope_corto_no_deja_fuentes_sin_fotos(self):
        fotos = {f"a{i}": foto("x", "A", 1 + i % 28) for i in range(100)}
        fotos.update({f"b{i}": foto("reddit", "B", 1 + i % 28) for i in range(3)})
        orden = tp.ordenar_pendientes(fotos, list(fotos))[:10]
        self.assertTrue(any(k.startswith("b") for k in orden))

    def test_sin_fecha_va_al_final_de_su_fuente(self):
        fotos = {"s1": foto("biblioteca", None, 0), "s2": foto("biblioteca", None, 0), "f": foto("biblioteca", None, 4)}
        self.assertEqual(tp.ordenar_pendientes(fotos, list(fotos))[0], "f")

    def test_espera_del_modelo_grande_cabe_en_el_limite_de_la_tarea(self):
        self.assertEqual(tp.espera_vlm_s(0), 4 * 3600, "al empezar, como mucho 4 h")
        self.assertEqual(tp.espera_vlm_s(154 * 60), 146 * 60, "el 19-oct Kaggle se lanzó a los 154 min: quedaban 146 min de presupuesto, no 4 h")
        self.assertEqual(tp.espera_vlm_s(299 * 60), 15 * 60, "si ya casi no queda presupuesto, 15 min de gracia")
        self.assertEqual(tp.espera_vlm_s(400 * 60), 15 * 60)
        for t_ in range(0, 300 * 60, 600):
            self.assertLess(t_ + tp.espera_vlm_s(t_), 316 * 60, "lanzando antes del minuto 300, nunca se espera más allá de ~315 min: el límite de la tarea es 330")

    def test_tope_de_tiempo(self):
        self.assertFalse(tp.tiempo_agotado(1000.0, None, ahora=10**9), "sin tope no se agota")
        self.assertFalse(tp.tiempo_agotado(1000.0, 120, ahora=1000.0 + 119 * 60))
        self.assertTrue(tp.tiempo_agotado(1000.0, 120, ahora=1000.0 + 121 * 60))

    def test_sin_fotos(self):
        self.assertEqual(tp.ordenar_pendientes({}, []), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
