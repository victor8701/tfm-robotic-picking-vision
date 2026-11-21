"""Complemento de RobotStudio CajasVariables: la logica con su consola de pruebas, y que compila contra las DLL de
RobotStudio 2026 (si estan instaladas). Necesita dotnet de Windows (WSL) o dotnet."""
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ADDIN = RAIZ / "rapid" / "estacion" / "CajasVariables"
RS_BIN = Path("/mnt/c/Program Files (x86)/ABB/RobotStudio 2026/Bin")


def _dotnet():
    windows = "/mnt/c/Program Files/dotnet/dotnet.exe"
    return windows if os.path.exists(windows) else shutil.which("dotnet")


def _ruta(exe, ruta):
    return subprocess.check_output(["wslpath", "-w", str(ruta)], text=True).strip() if exe.lower().endswith(".exe") else str(ruta)


def _dotnet_run(*args, timeout=280):
    exe = _dotnet()
    cwd = "/mnt/c/Windows" if exe.lower().endswith(".exe") else None   # cmd no admite carpetas UNC
    return subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout, cwd=cwd)


requiere_dotnet = pytest.mark.skipif(_dotnet() is None, reason="dotnet no esta instalado")


@requiere_dotnet
def test_la_logica_del_complemento_pasa_su_consola_de_pruebas():
    r = _dotnet_run("run", "--project", _ruta(_dotnet(), ADDIN / "Pruebas" / "Pruebas.csproj"), "-c", "Release", "-nologo")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1500:]
    assert "TODO OK" in r.stdout and "FALLO" not in r.stdout


@requiere_dotnet
@pytest.mark.skipif(not RS_BIN.is_dir(), reason="RobotStudio 2026 no esta instalado")
def test_el_complemento_compila_contra_las_dll_de_robotstudio_2026():
    r = _dotnet_run("build", _ruta(_dotnet(), ADDIN / "CajasVariables.csproj"), "-c", "Release", "-nologo", "-v:m")
    assert r.returncode == 0 and re.search(r"\b0 Errores|\b0 Error\(s\)", r.stdout), r.stdout[-3000:]
    assert (ADDIN / "bin" / "Paquete" / "CajasVariables.dll").is_file()
    assert (ADDIN / "bin" / "Paquete" / "CajasVariables.rsaddin").is_file()


def test_el_rsaddin_apunta_a_la_dll_y_se_carga_con_la_estacion():
    ns = {"a": "urn:abb-robotics-robotstudio-addin"}
    raiz = ET.parse(ADDIN / "CajasVariables.rsaddin").getroot()
    assert raiz.get("autoLoad") == "true"
    assert raiz.findtext("a:Assembly/a:FileName", namespaces=ns) == "CajasVariables.dll"
    assert raiz.findtext("a:Dependencies", namespaces=ns) == "None"
    assert raiz.findtext("a:Assembly/a:Entrypoint", namespaces=ns) == "CajasVariables.Addin.AddinMain"
    assert raiz.findtext("a:ApplicationId", namespaces=ns)


def test_el_complemento_busca_las_mismas_piezas_que_crea_el_script_de_la_estacion():
    addin = (ADDIN / "Addin.cs").read_text(encoding="utf-8")
    script = (RAIZ / "rapid" / "estacion" / "aplicar_estacion.py").read_text(encoding="utf-8")
    assert 'NombreCaja = "CajaGrande"' in addin
    assert "CajaGrande" in script and 'Name="PosCaja{k:02d}"' in script       # los 12 Positioner
    assert '"PosCaja" + k.ToString("00")' in addin and "NumGiros = 12" in addin
    # el complemento lee el mismo caja.csv que RAPID escribe (largo;ancho;alto;giro)
    rapid = (RAIZ / "rapid" / "MOD_CajaPinza.mod").read_text(encoding="utf-8")
    assert 'Open "HOME:/caja.csv"' in rapid and 'NumToStr(largoCaja, 1) + ";" + NumToStr(anchoCaja, 1) + ";" + NumToStr(altoCaja, 1)' in rapid


def test_la_especificacion_del_paquete_rspak_apunta_a_ficheros_que_existen():
    ns = {"d": "urn:abb-robotics-robotstudio-distributionpackagespec"}
    raiz = ET.parse(ADDIN / "CajasVariables.rspakspec").getroot()
    assert "RobotStudio-AddIn" in [t.text for t in raiz.findall("d:DistributionPackage/d:Tags/d:Tag", ns)]
    destinos = {f.get("src").split("\\")[-1]: f.get("target") for f in raiz.findall("d:Files/d:File", ns)}
    assert destinos == {"CajasVariables.dll": r"RobotStudio\Add-In", "CajasVariables.rsaddin": r"RobotStudio\Add-In",
                        "ruta_caja_csv.txt": r"RobotStudio\Add-In"}
    assert (ADDIN / "ruta_caja_csv.txt").is_file() and (ADDIN / "CajasVariables.rsaddin").is_file()


XSD_ADDIN = Path("/mnt/c/Program Files (x86)/ABB/SDK/RobotStudio 2024 SDK/RobotStudioAddin.xsd")


@pytest.mark.skipif(not XSD_ADDIN.is_file(), reason="el esquema RobotStudioAddin.xsd del SDK de ABB no esta instalado")
@pytest.mark.parametrize("ruta", [ADDIN / "CajasVariables.rsaddin", ADDIN / "ParaBinAddins" / "CajasVariables.rsaddin"])
def test_los_rsaddin_cumplen_el_esquema_de_abb(ruta):
    """RobotStudio no carga un .rsaddin que no valide («Failed to load CajasVariables.rsaddin», 18-nov): dentro de
    Assembly el orden es FileName, Path, Entrypoint."""
    lxml = pytest.importorskip("lxml.etree")
    esquema = lxml.XMLSchema(lxml.parse(str(XSD_ADDIN)))
    assert esquema.validate(lxml.parse(str(ruta))), "\n".join(str(e) for e in esquema.error_log)


def test_la_variante_para_bin_addins_apunta_a_la_carpeta_de_la_dll_y_a_la_version_26():
    ns = {"a": "urn:abb-robotics-robotstudio-addin"}
    raiz = ET.parse(ADDIN / "ParaBinAddins" / "CajasVariables.rsaddin").getroot()
    assert raiz.get("autoLoad") == "false"                      # como el ejemplo de ABB: se carga con Load Add-In
    assert raiz.findtext("a:MinimumHostVersion", namespaces=ns) == "26.1"
    assert raiz.findtext("a:Assembly/a:Path", namespaces=ns) == r"C:\Users\Viktor\Desktop\TFM_RAPID\Addin\CajasVariables"
    hijos = [h.tag.split("}")[1] for h in raiz.find("a:Assembly", ns)]
    assert hijos == ["FileName", "Path", "Entrypoint"]


def test_el_fichero_de_fin_de_tanda_es_el_mismo_en_rapid_y_en_el_complemento():
    """RAPID escribe HOME:/fin_tanda.txt al acabar la tanda (MarcarFinTanda) y el complemento vigila ese mismo nombre junto a caja.csv."""
    modulo = (RAIZ / "rapid" / "MOD_CajaPinza.mod").read_text(encoding="utf-8")
    addin = (ADDIN / "Addin.cs").read_text(encoding="utf-8")
    nombre_rapid = re.search(r'Open "HOME:/([^"]+)", marca \\Write;', modulo).group(1)
    nombre_addin = re.search(r'FicheroFin = "([^"]+)"', addin).group(1)
    assert nombre_rapid == nombre_addin == "fin_tanda.txt"
    # y se escribe antes del Stop del final de la tanda, no despues (el Stop detiene el programa)
    fin = modulo[modulo.index("hmiFase := FASE_FIN;"):]
    assert fin.index("MarcarFinTanda;") < fin.index("Stop;")
