import sys
from pathlib import Path

# Permite importar los paquetes de robotica/ (nucleo, vision, calibracion, egm, mock) desde los tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
