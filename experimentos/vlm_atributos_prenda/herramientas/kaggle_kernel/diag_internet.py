#!/usr/bin/env python3
"""
Kernel de Kaggle de una sola linea de sentido: comprueba si el kernel tiene internet de
verdad, sin esperar a que falle a mitad del entrenamiento real (git clone / pip / descarga
del dataset y de Florence-2 tardan minutos en fallar por timeout de DNS).

Se subio y se uso el 2026-09-20 para diagnosticar el primer intento real de
entrenar_en_kaggle.py: fallaba "Could not resolve host" en TODOS los hosts pese a pedir
`enable_internet=True` -- causa real: la cuenta de Kaggle no tenia el telefono verificado
(Settings > Account > Phone Verification), requisito de Kaggle para dar internet en un kernel
aunque se pida por API. Tras verificarlo, este mismo diagnostico salio OK en los 4 hosts.

Subir con push_and_run.py (editar SLUG a mano, o adaptar) si hace falta volver a comprobarlo.
"""
import urllib.request

for host in ["https://pypi.org", "https://github.com", "https://raw.githubusercontent.com", "https://huggingface.co"]:
    try:
        urllib.request.urlopen(host, timeout=10)
        print(f"OK   {host}")
    except Exception as e:
        print(f"FALLO {host}: {e}")
