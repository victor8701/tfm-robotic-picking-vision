#!/usr/bin/env python3
"""
Operaciones de Kaggle para el «profesor»: crear y borrar datasets privados, subir y lanzar un kernel con GPU, seguirlo y bajar su salida.
Usa el SDK (`kagglesdk`) con el «API Token (Recommended)» de ~/.config/kaggle/api_token, porque la CLI instalada (kaggle 1.7.4.5) no lo soporta
(ver ../kaggle_kernel/README.md). El `kaggle.json` clásico de esta máquina ya no autentica.

Se puede usar como módulo (las funciones devuelven valores; lo usa `analisis_mercado/tendencia_prenda.py vlm`) o desde la línea de comandos:
    dataset-crear CARPETA            crea un dataset PRIVADO con lo que haya en CARPETA (lee dataset-metadata.json)
    dataset-estado SLUG              estado del dataset («ready» cuando se puede usar)
    dataset-borrar SLUG              borra el dataset para siempre
    datasets                         lista los datasets propios
    kernel-push SCRIPT TITULO SLUG_DATASET[,SLUG_DATASET…]    sube SCRIPT como kernel privado con GPU e internet y lo lanza
    estado [SLUG_KERNEL]             estado y últimas líneas del log (por defecto, el último kernel lanzado)
    log [SLUG_KERNEL]                log completo
    bajar DIR [SLUG_KERNEL]          descarga los ficheros de salida (cuando el estado es COMPLETE)
"""
import json
import os
import sys
import time
from pathlib import Path

TOKEN_FILE = Path.home() / ".config" / "kaggle" / "api_token"
os.environ["KAGGLE_API_TOKEN"] = TOKEN_FILE.read_text().strip()
USUARIO = "Victor871"
ULTIMO = Path.home() / ".cache" / "vlm_profesor_kernel.json"

from kagglesdk import KaggleClient  # noqa: E402
from kagglesdk.datasets.types.dataset_api_service import ApiDeleteDatasetRequest  # noqa: E402
from kagglesdk.kernels.types.kernels_api_service import (  # noqa: E402
    ApiSaveKernelRequest, ApiGetKernelSessionStatusRequest, ApiListKernelSessionOutputRequest,
)
from kagglesdk.kernels.types.kernels_enums import KernelWorkerStatus  # noqa: E402

TERMINADOS = ("COMPLETE", "ERROR", "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED")


def _asegurar_config():
    """La CLI exige un kaggle.json aunque se autentique con el token nuevo (en GitHub Actions no existe y `dataset_create_new` falla con «Could not find kaggle.json»): si falta, se crea uno de relleno."""
    f = Path.home() / ".config" / "kaggle" / "kaggle.json"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"username": USUARIO, "key": "no-se-usa"}), encoding="utf-8")
        f.chmod(0o600)


def api_cli():
    """La clase de la CLI, pero hablando con el SDK autenticado por el token nuevo."""
    _asegurar_config()
    from kaggle.api.kaggle_api_extended import KaggleApi
    a = KaggleApi()
    a.config_values = {a.CONFIG_NAME_USER: USUARIO}
    a.build_kaggle_client = lambda: KaggleClient()
    return a


# ---------------------------------------------------------------- datasets
def dataset_crear(carpeta, quiet=False) -> str:
    r = api_cli().dataset_create_new(str(carpeta), public=False, quiet=quiet, dir_mode="skip")
    if getattr(r, "error", None):
        raise RuntimeError(f"Kaggle rechazó el dataset: {r.error}")
    return r.url or r.ref


def dataset_estado(slug) -> str:
    return api_cli().dataset_status(f"{USUARIO.lower()}/{slug}")


def esperar_dataset(slug, intentos=120, pausa=5) -> None:
    """Espera a que el dataset esté listo. Justo después de crearlo, Kaggle contesta 403 (aún no lo ve): se sigue esperando."""
    for _ in range(intentos):
        try:
            if dataset_estado(slug) == "ready":
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(pausa)
    raise TimeoutError(f"el dataset {slug} no llegó a «ready»")


def dataset_borrar(slug, intentos=24, pausa=5) -> None:
    """Borra el dataset. Si aún no se puede (Kaggle contesta 403 mientras lo procesa), reintenta hasta ~2 minutos; si no, lanza el último error."""
    ultimo = None
    for _ in range(intentos):
        try:
            with KaggleClient() as k:
                req = ApiDeleteDatasetRequest()
                req.owner_slug, req.dataset_slug = USUARIO.lower(), slug
                r = k.datasets.dataset_api_client.delete_dataset(req)
            if getattr(r, "error", None):
                raise RuntimeError(f"no se pudo borrar {slug}: {r.error}")
            return
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(pausa)
    raise ultimo


def datasets() -> list[tuple[str, bool, str]]:
    from kagglesdk.datasets.types.dataset_api_service import ApiListDatasetsRequest
    from kagglesdk.datasets.types.dataset_enums import DatasetSelectionGroup
    with KaggleClient() as k:
        req = ApiListDatasetsRequest()
        req.group = DatasetSelectionGroup.DATASET_SELECTION_GROUP_MY
        r = k.datasets.dataset_api_client.list_datasets(req)
        return [(d.ref, bool(getattr(d, "is_private", False)), d.title) for d in r.datasets]


# ---------------------------------------------------------------- kernels
def kernel_push(texto, titulo, fuentes) -> str:
    """Sube `texto` (código) como kernel privado con GPU e internet y lo lanza. Devuelve el slug que Kaggle asigna (deriva del título en el primer push)."""
    req = ApiSaveKernelRequest()
    req.slug = f"{USUARIO}/{titulo.lower().replace(' ', '-')}"
    req.new_title = titulo   # límite de Kaggle: 50 caracteres
    req.text = texto
    req.language = "python"
    req.kernel_type = "script"
    req.is_private = True
    req.enable_gpu = True
    req.enable_internet = True
    req.dataset_data_sources = [f"{USUARIO.lower()}/{s}" for s in fuentes]
    with KaggleClient() as k:
        r = k.kernels.kernels_api_client.save_kernel(req)
    if r.error:
        raise RuntimeError(f"error al subir el kernel: {r.error} {getattr(r, 'invalid_dataset_sources', '')}")
    slug = r.url.rstrip("/").split("/")[-1]
    ULTIMO.parent.mkdir(parents=True, exist_ok=True)
    ULTIMO.write_text(json.dumps({"slug": slug, "url": r.url}), encoding="utf-8")
    return slug


def kernel_estado(slug) -> tuple[str, str]:
    """(estado, mensaje de fallo): COMPLETE, RUNNING, QUEUED, ERROR…"""
    with KaggleClient() as c:
        req = ApiGetKernelSessionStatusRequest()
        req.user_name, req.kernel_slug = USUARIO, slug
        r = c.kernels.kernels_api_client.get_kernel_session_status(req)
        return r.status.name, r.failure_message or ""


def esperar_kernel(slug, maximo_s=4 * 3600, pausa=45, avisar=None) -> str:
    """Espera a que termine; devuelve el estado final. Lanza TimeoutError si pasa `maximo_s`."""
    t0, previo = time.time(), None
    while time.time() - t0 < maximo_s:
        try:
            est, fallo = kernel_estado(slug)
        except Exception:   # un fallo de red puntual no debe tirar la espera
            time.sleep(pausa)
            continue
        if est != previo and avisar:
            avisar(f"{slug}: {est}" + (f" ({fallo})" if fallo else ""))
        previo = est
        if est in TERMINADOS:
            return est
        time.sleep(pausa)
    raise TimeoutError(f"el kernel {slug} no terminó en {maximo_s // 60} minutos")


def kernel_log(slug) -> str:
    with KaggleClient() as c:
        out = ApiListKernelSessionOutputRequest()
        out.user_name, out.kernel_slug = USUARIO, slug
        return c.kernels.kernels_api_client.list_kernel_session_output(out).log or ""


def kernel_bajar(destino, slug) -> list[str]:
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    bajados = []
    with KaggleClient() as c:
        out = ApiListKernelSessionOutputRequest()
        out.user_name, out.kernel_slug = USUARIO, slug
        resp = c.kernels.kernels_api_client.list_kernel_session_output(out)
        sesion = c.http_client()._session
        for f in resp.files:
            if "/" in f.file_name:
                continue
            r = sesion.get(f.url)
            r.raise_for_status()
            (destino / f.file_name).write_bytes(r.content)
            bajados.append(f.file_name)
    return bajados


# ---------------------------------------------------------------- línea de comandos
def slug_kernel(arg=None):
    return arg or json.loads(ULTIMO.read_text())["slug"]


def main(a):
    if not a:
        print(__doc__)
    elif a[0] == "dataset-crear":
        print("Dataset privado creado:", dataset_crear(a[1]))
    elif a[0] == "dataset-estado":
        print(dataset_estado(a[1]))
    elif a[0] == "dataset-borrar":
        dataset_borrar(a[1])
        print("Borrado:", a[1])
    elif a[0] == "datasets":
        for ref, priv, titulo in datasets():
            print(ref, "| privado" if priv else "| PÚBLICO", "|", titulo)
        if not datasets():
            print("(ningún dataset propio)")
    elif a[0] == "kernel-push":
        slug = kernel_push(Path(a[1]).read_text(encoding="utf-8"), a[2], a[3].split(","))
        print(f"Subido y lanzado: https://www.kaggle.com/code/{USUARIO.lower()}/{slug}; slug {slug}")
    elif a[0] == "estado":
        slug = slug_kernel(a[1] if len(a) > 1 else None)
        est, fallo = kernel_estado(slug)
        print(f"Estado: {est}" + (f"  -- {fallo}" if fallo else ""))
        if est != KernelWorkerStatus.QUEUED.name:
            log = kernel_log(slug)
            if log:
                print("--- últimas 15 líneas del log ---")
                print("\n".join(log.splitlines()[-15:]))
    elif a[0] == "log":
        print(kernel_log(slug_kernel(a[1] if len(a) > 1 else None)) or "(sin log todavía)")
    elif a[0] == "bajar":
        bajados = kernel_bajar(a[1], slug_kernel(a[2] if len(a) > 2 else None))
        for f in bajados:
            print("  ", f)
        if not bajados:
            print("(sin ficheros de salida todavía)")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
