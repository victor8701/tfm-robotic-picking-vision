#!/usr/bin/env python3
"""
Script "kernel" para correr el Stage 3 (fine-tuning LoRA v2) en un notebook de Kaggle con
GPU, disparado por API en vez de por la interfaz web de Colab -- pensado para cuando no hay
forma comoda de manejar la interfaz de un notebook (p.ej. desde el movil).

Es la alternativa a herramientas/notebook_colab_entrenamiento.ipynb, mismos pasos, pero
como un script secuencial de una sola pasada (nada de reiniciar el kernel a mano: cada paso
que depende de paquetes recien instalados/desinstalados se lanza en un subproceso nuevo, asi
que no hay imports ya cacheados de los que preocuparse, a diferencia de una sesion
interactiva de notebook).

No se corre aqui directamente -- lo sube y lo lanza kaggle_kernels_push.sh via la API de
Kaggle (`kaggle kernels push`), y Kaggle lo ejecuta en su propia maquina con GPU.

Uso (en la maquina de Kaggle, no en local):
    python3 entrenar_en_kaggle.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAMA = "clip-trend-semantic-matching-poc"
REPO_URL = "https://github.com/victor8701/tfm-robotic-picking-vision.git"
SALIDA_KAGGLE = Path("/kaggle/working")
# El repo clonado se queda FUERA de /kaggle/working a proposito: Kaggle trata todo lo que hay
# en /kaggle/working al terminar como "salida del kernel" (lo que devuelve `kaggle kernels
# output`), y clonar ahi dentro colaba el repo entero (miles de ficheros, incluidas las
# imagenes de data/imagenes_cache/) como si fuera un resultado -- visto en el primer run real
# (2026-09-20): la descarga fallaba al toparse con ficheros sueltos del propio repo mezclados
# con los 3 ficheros que de verdad importan.
CARPETA_TRABAJO = Path(tempfile.mkdtemp(prefix="repo_"))


def run(cmd):
    print(f"\n$ {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True)


def run_capturando(cmd, ruta_log):
    """Como run(), pero ademas guarda stdout+stderr en un fichero (para los pasos cuyo
    texto impreso es en si mismo un resultado a conservar, no solo progreso)."""
    print(f"\n$ {cmd}  (log -> {ruta_log})", flush=True)
    with open(ruta_log, "w", encoding="utf-8") as f:
        proceso = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        f.write(proceso.stdout)
    print(proceso.stdout)
    if proceso.returncode != 0:
        raise subprocess.CalledProcessError(proceso.returncode, cmd)


def main():
    run(f"git clone --branch {RAMA} --single-branch {REPO_URL} {CARPETA_TRABAJO / 'repo'}")
    import os
    os.chdir(CARPETA_TRABAJO / "repo" / "experimentos" / "vlm_atributos_prenda")

    # torchao: mismo problema que en Colab (ImportError: incompatible version of torchao al
    # aplicar LoRA), pero aqui no hace falta el truco de "matar el proceso y reiniciar": como
    # entrenar_lora.py se lanza como un subprocess nuevo (mas abajo), nunca hereda un torchao
    # ya importado en memoria de este proceso orquestador.
    run("pip install -q -r requirements.txt")
    subprocess.run("pip uninstall -y -q torchao", shell=True)  # no pasa nada si no estaba instalado

    run("python3 herramientas/preparar_dataset_florence2.py")  # determinista (semilla 42) -- reproduce train/val/test.jsonl ya commiteados
    run("python3 herramientas/entrenar_lora.py --salida modelos/florence2_base_lora_v2")
    run_capturando(
        "python3 herramientas/evaluar_modelo.py --adapter modelos/florence2_base_lora_v2 --sin-zero-shot --sin-1207",
        "modelos/florence2_base_lora_v2/evaluacion_test_v2.txt",
    )

    shutil.make_archive(str(SALIDA_KAGGLE / "florence2_base_lora_v2"), "zip", "modelos/florence2_base_lora_v2")
    shutil.copy("modelos/florence2_base_lora_v2/resultados_entrenamiento.json", SALIDA_KAGGLE)
    shutil.copy("modelos/florence2_base_lora_v2/evaluacion_test_v2.txt", SALIDA_KAGGLE)
    print("\nLISTO -- adapter + resultados en /kaggle/working/, listos para `kaggle kernels output`.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\nFALLO en: {e.cmd}", file=sys.stderr)
        raise
