"""Pruebas del reintento de la descarga de la salida de un kernel de Kaggle (kaggle_ops.kernel_bajar). Sin red. Uso:  python3 test_kaggle_reintentos.py"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vlm_atributos_prenda" / "herramientas" / "vlm_profesor"))
import kaggle_ops as ko  # noqa: E402


class Resp:
    def __init__(self, codigo, contenido=b"datos"):
        self.status_code, self.content = codigo, contenido

    def raise_for_status(self):
        if self.status_code >= 400:
            e = RuntimeError(f"{self.status_code} Server Error")
            e.response = self
            raise e


class Cliente:
    """Imita KaggleClient: una lista de ficheros y una sesión HTTP que responde lo que se le diga."""
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.kernels = mock.Mock()
        self.kernels.kernels_api_client.list_kernel_session_output.return_value = mock.Mock(files=[mock.Mock(file_name="pred.jsonl", url="https://x/pred")])

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def http_client(self):
        sesion = mock.Mock()
        sesion.get.side_effect = lambda url, timeout=None: self.respuestas.pop(0)
        return mock.Mock(_session=sesion)


class Pruebas(unittest.TestCase):
    def descargar(self, respuestas, **kw):
        cliente = Cliente(list(respuestas))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ko, "KaggleClient", return_value=cliente), mock.patch.object(ko.time, "sleep") as dormir:
            bajados = ko.kernel_bajar(d, "kernel", **kw)
            return bajados, (Path(d) / "pred.jsonl").read_bytes(), dormir.call_count

    def test_un_502_se_reintenta_y_acaba_bien(self):
        bajados, contenido, pausas = self.descargar([Resp(502), Resp(502), Resp(200, b"hola")])
        self.assertEqual(bajados, ["pred.jsonl"])
        self.assertEqual(contenido, b"hola")
        self.assertEqual(pausas, 2, "dos fallos, dos pausas")

    def test_un_error_de_cliente_no_se_reintenta(self):
        cliente = Cliente([Resp(404)])
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ko, "KaggleClient", return_value=cliente), mock.patch.object(ko.time, "sleep") as dormir:
            with self.assertRaises(RuntimeError):
                ko.kernel_bajar(d, "kernel")
            self.assertEqual(dormir.call_count, 0)

    def test_si_siempre_falla_se_rinde_tras_los_intentos(self):
        cliente = Cliente([Resp(502)] * 3)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ko, "KaggleClient", return_value=cliente), mock.patch.object(ko.time, "sleep") as dormir:
            with self.assertRaises(RuntimeError):
                ko.kernel_bajar(d, "kernel", intentos=3)
            self.assertEqual(dormir.call_count, 2, "con 3 intentos hay 2 pausas")


if __name__ == "__main__":
    unittest.main()
