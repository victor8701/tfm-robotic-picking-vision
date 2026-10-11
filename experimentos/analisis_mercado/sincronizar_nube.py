#!/usr/bin/env python3
"""
Los datos GENERADOS por la tarea semanal (fotos vistas, prendas, informe, comparación entre estilos, embeddings) viven en la rama `datos-tendencia` de GitHub, aparte del código, para que
los commits de la tarea (cada lunes) no choquen con los de código ni con las etiquetas de Víctor. Este script los mueve entre esa rama y `tendencia_datos/`:

  python3 sincronizar_nube.py bajar              baja de GitHub lo último de la rama `datos-tendencia` a `tendencia_datos/` (git fetch + git show; no toca tu rama de trabajo)
  python3 sincronizar_nube.py traer CARPETA      copia los generados desde CARPETA (un clon de la rama) a `tendencia_datos/`     [lo usa la tarea]
  python3 sincronizar_nube.py llevar CARPETA     copia los generados de `tendencia_datos/` a CARPETA                              [lo usa la tarea]
  python3 sincronizar_nube.py crear-rama         crea la rama `datos-tendencia` en GitHub con los generados actuales (una sola vez; pide confirmación)
Los datos curados a mano (etiquetas, valoraciones, fiabilidad, lotes) NO se sincronizan: van con el código.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TD = Path(os.environ.get("TENDENCIA_DATOS") or AQUI / "tendencia_datos")
RAMA = "datos-tendencia"
GENERADOS = ["fotos.json", "prendas.json", "estado.json", "informe.json", "separacion_estilos.json", "embeddings.npz", "registro_semanal.txt"]


def git(*args, cwd=AQUI, check=True, **kw):
    return subprocess.run(["git", *args], cwd=cwd, check=check, text=True, **kw)


def traer(carpeta: Path) -> None:
    TD.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in GENERADOS:
        if (carpeta / f).exists():
            shutil.copy(carpeta / f, TD / f)
            n += 1
    print(f"Traídos {n} ficheros de {carpeta} a {TD}")


def llevar(carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in GENERADOS:
        if (TD / f).exists():
            shutil.copy(TD / f, carpeta / f)
            n += 1
    print(f"Llevados {n} ficheros de {TD} a {carpeta}")


def bajar() -> None:
    git("fetch", "origin", RAMA)
    TD.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in GENERADOS:
        r = subprocess.run(["git", "show", f"origin/{RAMA}:{f}"], cwd=AQUI, capture_output=True)
        if r.returncode == 0:
            (TD / f).write_bytes(r.stdout)
            n += 1
    print(f"Bajados {n} ficheros de origin/{RAMA} a {TD}")


def crear_rama() -> None:
    existe = subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", RAMA], cwd=AQUI, capture_output=True).returncode == 0
    if existe:
        sys.exit(f"La rama {RAMA} ya existe en GitHub: usa «bajar» para traer sus datos.")
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        llevar(t)
        (t / "LEEME.md").write_text("Datos generados por la tarea semanal de tendencias de prenda (rama de datos; el código está en la rama `analisis-mercado`).\n"
                                    "No se guardan fotos: solo identificadores, direcciones públicas, cajas y etiquetas.\n", encoding="utf-8")
        git("init", "-q", "-b", RAMA, cwd=t)
        git("add", "-A", cwd=t)
        git("-c", "user.name=Victor", "-c", "user.email=noreply@users.noreply.github.com", "commit", "-q", "-m", "Datos iniciales de la tarea semanal", cwd=t)
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=AQUI, capture_output=True, text=True).stdout.strip()
        git("push", url, f"{RAMA}:{RAMA}", cwd=t)
    print(f"Rama {RAMA} creada en GitHub.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("bajar", "traer", "llevar", "crear-rama"):
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "bajar":
        bajar()
    elif cmd == "crear-rama":
        crear_rama()
    elif len(sys.argv) < 3:
        sys.exit(f"{cmd} necesita CARPETA")
    elif cmd == "traer":
        traer(Path(sys.argv[2]))
    else:
        llevar(Path(sys.argv[2]))


if __name__ == "__main__":
    main()
