#!/usr/bin/env python3
"""
Los datos GENERADOS por la tarea semanal (fotos vistas, prendas, informe, comparación entre estilos, embeddings) viven en la rama `datos-tendencia` de GitHub, aparte del código, para que
los commits de la tarea (cada lunes) no choquen con los de código ni con las etiquetas de Víctor. Este script los mueve entre esa rama y `tendencia_datos/`:

  python3 sincronizar_nube.py bajar              baja de GitHub lo último de la rama `datos-tendencia` a `tendencia_datos/` (git fetch + git show; no toca tu rama de trabajo)
  python3 sincronizar_nube.py traer CARPETA      copia los generados desde CARPETA (un clon de la rama) a `tendencia_datos/`     [lo usa la tarea]
  python3 sincronizar_nube.py llevar CARPETA     copia los generados de `tendencia_datos/` a CARPETA                              [lo usa la tarea]
  python3 sincronizar_nube.py crear-rama         crea la rama `datos-tendencia` en GitHub (una sola vez) con los generados del último commit de código (los de la carpeta de trabajo solo si no están en git)
  python3 sincronizar_nube.py fusionar           mezcla lo de la rama `datos-tendencia` con lo local POR IDENTIFICADOR de foto (la nube manda en lo que ya tiene; lo local solo añade lo que falta) y lo deja en `tendencia_datos/`
  python3 sincronizar_nube.py subir [MENSAJE]    sube los generados de `tendencia_datos/` a la rama `datos-tendencia` (con reintentos si la nube escribió mientras tanto)
Los datos curados a mano (etiquetas, valoraciones, fiabilidad, lotes) NO se sincronizan: van con el código.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TD = Path(os.environ.get("TENDENCIA_DATOS") or AQUI / "tendencia_datos")
RAMA = "datos-tendencia"
GENERADOS = ["fotos.json", "prendas.json", "estado.json", "informe.json", "separacion_estilos.json", "embeddings.npz", "registro_semanal.txt", "fotos_kaggle.txt"]


def _ayudante() -> list[str]:
    """El ayudante de credenciales del repositorio de trabajo (en este equipo está solo en su configuración local): los repositorios temporales de este script no lo heredan."""
    r = subprocess.run(["git", "config", "--get", "credential.helper"], cwd=AQUI, capture_output=True, text=True).stdout.strip()
    return ["-c", f"credential.helper={r}"] if r else []


def git(*args, cwd=AQUI, check=True, **kw):
    return subprocess.run(["git", *_ayudante(), *args], cwd=cwd, check=check, text=True, **kw)


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
        elif f == "fotos_kaggle.txt" and (carpeta / f).exists():
            (carpeta / f).unlink()   # la marca de fotos de Kaggle desaparece de la rama de datos cuando ya se han usado (del resto de ficheros no se borra nada)
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


def desde_git(f: str) -> bytes | None:
    r = subprocess.run(["git", "show", f"HEAD:experimentos/analisis_mercado/tendencia_datos/{f}"], cwd=AQUI, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def crear_rama() -> None:
    existe = subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", RAMA], cwd=AQUI, capture_output=True).returncode == 0
    if existe:
        sys.exit(f"La rama {RAMA} ya existe en GitHub: usa «bajar» o «fusionar» para traer sus datos.")
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        for f in GENERADOS:
            b = desde_git(f)   # lo que está en el último commit: un estado coherente, sin lo que esté a medias en la carpeta de trabajo
            if b is not None:
                (t / f).write_bytes(b)
            elif (TD / f).exists():
                shutil.copy(TD / f, t / f)
        (t / "LEEME.md").write_text("Datos generados por la tarea semanal de tendencias de prenda (rama de datos; el código está en la rama `analisis-mercado`).\n"
                                    "No se guardan fotos: solo identificadores, direcciones públicas, cajas y etiquetas.\n", encoding="utf-8")
        git("init", "-q", "-b", RAMA, cwd=t)
        git("add", "-A", cwd=t)
        git("-c", "user.name=Victor", "-c", "user.email=noreply@users.noreply.github.com", "commit", "-q", "-m", "Datos iniciales de la tarea semanal", cwd=t)
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=AQUI, capture_output=True, text=True).stdout.strip()
        git("push", url, f"{RAMA}:{RAMA}", cwd=t)
        print("Ficheros:", sorted(p.name for p in t.iterdir() if p.is_file()))
    print(f"Rama {RAMA} creada en GitHub.")


def _json_nube(f: str):
    r = subprocess.run(["git", "show", f"origin/{RAMA}:{f}"], cwd=AQUI, capture_output=True)
    return json.loads(r.stdout.decode("utf-8")) if r.returncode == 0 else None


def _con_vlm(entrada: dict) -> int:
    return sum(1 for p in entrada.get("prendas", []) if p.get("vlm"))


def fusionar() -> None:
    """Une nube y local por identificador de foto. La nube manda donde las dos tienen la misma foto (salvo si lo local tiene más prendas etiquetadas por el modelo grande)."""
    import numpy as np
    git("fetch", "origin", RAMA)
    TD.mkdir(parents=True, exist_ok=True)
    for f in ("fotos.json", "prendas.json"):
        nube, local = _json_nube(f), (json.loads((TD / f).read_text(encoding="utf-8")) if (TD / f).exists() else {})
        if nube is None:
            continue
        sal, solo_local, mejor_local = dict(nube), 0, 0
        for k, v in local.items():
            if k not in sal:
                sal[k] = v
                solo_local += 1
            elif f == "prendas.json" and _con_vlm(v) > _con_vlm(sal[k]):
                sal[k] = v
                mejor_local += 1
        (TD / f).write_text(json.dumps(sal, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{f}: {len(nube)} en la nube + {solo_local} solo locales" + (f" + {mejor_local} locales más completas" if mejor_local else "") + f" = {len(sal)}")
    for f in ("estado.json", "informe.json", "separacion_estilos.json", "registro_semanal.txt"):   # la nube manda (el informe y la comparación se vuelven a calcular después)
        r = subprocess.run(["git", "show", f"origin/{RAMA}:{f}"], cwd=AQUI, capture_output=True)
        if r.returncode == 0:
            (TD / f).write_bytes(r.stdout)
    # embeddings: unión por identificador
    r = subprocess.run(["git", "show", f"origin/{RAMA}:embeddings.npz"], cwd=AQUI, capture_output=True)
    d = {}
    if r.returncode == 0:
        import io
        z = np.load(io.BytesIO(r.stdout), allow_pickle=False)
        d = dict(zip(z["ids"].tolist(), z["v"]))
    if (TD / "embeddings.npz").exists():
        z = np.load(TD / "embeddings.npz", allow_pickle=False)
        for k, v in zip(z["ids"].tolist(), z["v"]):
            d.setdefault(k, v)
    if d:
        np.savez_compressed(TD / "embeddings.npz", ids=np.array(list(d.keys())), v=np.array(list(d.values()), dtype=np.float16))
        print(f"embeddings.npz: {len(d)} fotos")


def subir(mensaje: str) -> None:
    url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=AQUI, capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp) / "datos"
        git("clone", "-q", "--depth", "1", "--branch", RAMA, url, str(t))
        llevar(t)
        git("add", "-A", cwd=t)
        if subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=t).returncode == 0:
            print("Sin cambios que subir.")
            return
        git("-c", "user.name=Victor", "-c", "user.email=noreply@users.noreply.github.com", "commit", "-q", "-m", mensaje, cwd=t)
        for intento in range(1, 6):
            if subprocess.run(["git", *_ayudante(), "push", "origin", f"HEAD:{RAMA}"], cwd=t).returncode == 0:
                print(f"Subido a {RAMA} (intento {intento}).")
                return
            git("pull", "--rebase", "origin", RAMA, cwd=t)
        sys.exit("No se pudo subir tras 5 intentos.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("bajar", "traer", "llevar", "crear-rama", "fusionar", "subir"):
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "bajar":
        bajar()
    elif cmd == "crear-rama":
        crear_rama()
    elif cmd == "fusionar":
        fusionar()
    elif cmd == "subir":
        subir(" ".join(sys.argv[2:]) or "Datos actualizados desde el portátil")
    elif len(sys.argv) < 3:
        sys.exit(f"{cmd} necesita CARPETA")
    elif cmd == "traer":
        traer(Path(sys.argv[2]))
    else:
        llevar(Path(sys.argv[2]))


if __name__ == "__main__":
    main()
