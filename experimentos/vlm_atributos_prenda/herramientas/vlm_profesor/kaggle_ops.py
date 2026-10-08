#!/usr/bin/env python3
"""
Operaciones de Kaggle para la prueba del «profesor»: crear y borrar datasets privados, subir y lanzar un kernel con GPU, seguirlo y bajar su salida.
Usa el SDK (`kagglesdk`) con el «API Token (Recommended)» de ~/.config/kaggle/api_token, porque la CLI instalada (kaggle 1.7.4.5) no lo soporta
(ver ../kaggle_kernel/README.md). El `kaggle.json` clásico de esta máquina ya no autentica.

Subcomandos:
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


def api_cli():
    """La clase de la CLI, pero hablando con el SDK autenticado por el token nuevo."""
    from kaggle.api.kaggle_api_extended import KaggleApi
    a = KaggleApi()
    a.config_values = {a.CONFIG_NAME_USER: USUARIO}
    a.build_kaggle_client = lambda: KaggleClient()
    return a


def dataset_crear(carpeta):
    r = api_cli().dataset_create_new(carpeta, public=False, quiet=False, dir_mode="skip")
    if getattr(r, "error", None):
        print("ERROR:", r.error)
        sys.exit(1)
    print("Dataset privado creado:", r.url or r.ref)


def dataset_estado(slug):
    print(api_cli().dataset_status(f"{USUARIO.lower()}/{slug}"))


def dataset_borrar(slug):
    with KaggleClient() as k:
        req = ApiDeleteDatasetRequest()
        req.owner_slug, req.dataset_slug = USUARIO.lower(), slug
        r = k.datasets.dataset_api_client.delete_dataset(req)
        print("Borrado:", slug, getattr(r, "error", "") or "")


def datasets():
    with KaggleClient() as k:
        from kagglesdk.datasets.types.dataset_api_service import ApiListDatasetsRequest
        from kagglesdk.datasets.types.dataset_enums import DatasetSelectionGroup
        req = ApiListDatasetsRequest()
        req.group = DatasetSelectionGroup.DATASET_SELECTION_GROUP_MY
        r = k.datasets.dataset_api_client.list_datasets(req)
        for d in r.datasets:
            print(d.ref, "| privado" if getattr(d, "is_private", False) else "| PÚBLICO", "|", d.title)
        if not r.datasets:
            print("(ningún dataset propio)")


def kernel_push(script, titulo, fuentes):
    req = ApiSaveKernelRequest()
    req.slug = f"{USUARIO}/{titulo.lower().replace(' ', '-')}"
    req.new_title = titulo   # límite de Kaggle: 50 caracteres; el slug real lo deriva Kaggle del título en el primer push
    req.text = Path(script).read_text(encoding="utf-8")
    req.language = "python"
    req.kernel_type = "script"
    req.is_private = True
    req.enable_gpu = True
    req.enable_internet = True
    req.dataset_data_sources = [f"{USUARIO.lower()}/{s}" for s in fuentes]
    with KaggleClient() as k:
        r = k.kernels.kernels_api_client.save_kernel(req)
    if r.error:
        print("ERROR al subir:", r.error, getattr(r, "invalid_dataset_sources", ""))
        sys.exit(1)
    slug = r.url.rstrip("/").split("/")[-1]
    ULTIMO.parent.mkdir(parents=True, exist_ok=True)
    ULTIMO.write_text(json.dumps({"slug": slug, "url": r.url}), encoding="utf-8")
    print(f"Subido y lanzado: {r.url} (versión {r.version_number}); slug {slug}")


def slug_kernel(arg=None):
    return arg or json.loads(ULTIMO.read_text())["slug"]


def estado(slug=None, lineas=15):
    slug = slug_kernel(slug)
    with KaggleClient() as c:
        req = ApiGetKernelSessionStatusRequest()
        req.user_name, req.kernel_slug = USUARIO, slug
        r = c.kernels.kernels_api_client.get_kernel_session_status(req)
        print(f"Estado: {r.status.name}" + (f"  -- {r.failure_message}" if r.failure_message else ""))
        if r.status != KernelWorkerStatus.QUEUED:
            out = ApiListKernelSessionOutputRequest()
            out.user_name, out.kernel_slug = USUARIO, slug
            resp = c.kernels.kernels_api_client.list_kernel_session_output(out)
            if resp.log:
                print(f"--- últimas {lineas} líneas del log ---")
                print("\n".join(resp.log.splitlines()[-lineas:]))


def log_completo(slug=None):
    slug = slug_kernel(slug)
    with KaggleClient() as c:
        out = ApiListKernelSessionOutputRequest()
        out.user_name, out.kernel_slug = USUARIO, slug
        print(c.kernels.kernels_api_client.list_kernel_session_output(out).log or "(sin log todavía)")


def bajar(destino, slug=None):
    slug = slug_kernel(slug)
    with KaggleClient() as c:
        out = ApiListKernelSessionOutputRequest()
        out.user_name, out.kernel_slug = USUARIO, slug
        resp = c.kernels.kernels_api_client.list_kernel_session_output(out)
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        sesion = c.http_client()._session
        for f in resp.files:
            if "/" in f.file_name:
                continue
            r = sesion.get(f.url)
            r.raise_for_status()
            (destino / f.file_name).write_bytes(r.content)
            print(f"  {f.file_name} ({len(r.content)} bytes)")
        if not resp.files:
            print("(sin ficheros de salida todavía)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "dataset-crear":
        dataset_crear(a[1])
    elif a[0] == "dataset-estado":
        dataset_estado(a[1])
    elif a[0] == "dataset-borrar":
        dataset_borrar(a[1])
    elif a[0] == "datasets":
        datasets()
    elif a[0] == "kernel-push":
        kernel_push(a[1], a[2], a[3].split(","))
    elif a[0] == "estado":
        estado(a[1] if len(a) > 1 else None)
    elif a[0] == "log":
        log_completo(a[1] if len(a) > 1 else None)
    elif a[0] == "bajar":
        bajar(a[1], a[2] if len(a) > 2 else None)
    else:
        print(__doc__)
        sys.exit(1)
