import json

import numpy as np

from calibracion.cli import main
from calibracion.homografia import aplicar
from nucleo.geometria import Pose, quat_desde_rotvec

rng = np.random.default_rng(11)
H_VERDADERA = np.array([[0.80, 0.10, 100.0], [-0.05, 0.90, 50.0], [1e-4, 2e-4, 1.0]])


def _datos_homografia(n=12, ruido=0.0, fuera_validacion=None):
    src = rng.uniform([0, 0], [640, 480], size=(n, 2))
    dst = aplicar(H_VERDADERA, src) + rng.normal(0, ruido, (n, 2))
    if fuera_validacion is not None:
        dst[-1] += fuera_validacion
        dst[-2] += fuera_validacion
    return {"src": src.tolist(), "dst": dst.tolist(), "n_validacion": 2}


def test_homografia_con_ruido_da_criterio_objetivo_y_salida_0(tmp_path):
    entrada = tmp_path / "datos.json"
    salida = tmp_path / "resultado.json"
    entrada.write_text(json.dumps(_datos_homografia(ruido=0.3)), encoding="utf-8")
    assert main(["homografia", str(entrada), str(salida)]) == 0
    res = json.loads(salida.read_text(encoding="utf-8"))
    assert res["criterio"] == "objetivo"
    assert np.array(res["H"]).shape == (3, 3)


def test_homografia_mala_da_salida_1(tmp_path):
    entrada = tmp_path / "datos.json"
    entrada.write_text(json.dumps(_datos_homografia(fuera_validacion=np.array([30.0, 30.0]))), encoding="utf-8")
    assert main(["homografia", str(entrada), str(tmp_path / "r.json")]) == 1


def test_homografia_con_pocos_puntos_da_salida_2(tmp_path):
    datos = _datos_homografia(n=5)
    entrada = tmp_path / "datos.json"
    entrada.write_text(json.dumps(datos), encoding="utf-8")
    assert main(["homografia", str(entrada), str(tmp_path / "r.json")]) == 2


def test_mano_ojo_recupera_la_camara_en_la_mano(tmp_path):
    X = Pose.crear(t=[30.0, -20.0, 80.0], q=quat_desde_rotvec([0.2, -0.1, 0.4]))
    Z = Pose.crear(t=[600.0, 100.0, 0.0], q=quat_desde_rotvec([0.0, 0.0, 0.5]))
    base, camara = [], []
    for _ in range(12):
        eje = rng.normal(size=3)
        eje /= np.linalg.norm(eje)
        G = Pose.crear(t=rng.uniform(-200, 200, 3), q=quat_desde_rotvec(eje * rng.uniform(0.3, 1.3)))
        base.append({"t": G.t.tolist(), "q": G.q.tolist()})
        C = X.inversa().componer(G.inversa()).componer(Z)
        camara.append({"t": C.t.tolist(), "q": C.q.tolist()})
    entrada = tmp_path / "mano.json"
    salida = tmp_path / "x.json"
    entrada.write_text(json.dumps({"base_mano": base, "objetivo_camara": camara}), encoding="utf-8")
    assert main(["mano_ojo", str(entrada), str(salida)]) == 0
    res = json.loads(salida.read_text(encoding="utf-8"))
    assert np.linalg.norm(np.array(res["X"]["t"]) - X.t) < 0.5
    assert res["dispersion_mm"] < 0.5


def test_archivo_inexistente_da_salida_2(tmp_path):
    assert main(["mano_ojo", str(tmp_path / "no.json"), str(tmp_path / "r.json")]) == 2
