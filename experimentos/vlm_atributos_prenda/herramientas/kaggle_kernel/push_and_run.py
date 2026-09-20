#!/usr/bin/env python3
"""
Sube y lanza entrenar_en_kaggle.py como un kernel de Kaggle, usando el SDK nuevo
(kagglesdk, autenticacion por KAGGLE_API_TOKEN -- el "API Token (Recommended)" de
Settings > API, no el kaggle.json clasico de usuario+key) porque la CLI instalada
(kaggle==1.7.4.5) todavia no soporta ese token para `kaggle kernels push` (ver el
comentario en kagglesdk/kaggle_http_client.py). El SDK si lo soporta -- se usa
directamente, sin pasar por la CLI.

Subcomandos:
    python3 push_and_run.py push     -- sube el kernel y lo pone a correr
    python3 push_and_run.py estado   -- status actual + ultimas lineas del log
    python3 push_and_run.py log      -- log completo hasta ahora
    python3 push_and_run.py bajar DIR -- descarga los ficheros de salida a DIR (cuando status=COMPLETE)
"""
import os
import sys
from pathlib import Path

TOKEN_FILE = Path.home() / ".config" / "kaggle" / "api_token"
os.environ["KAGGLE_API_TOKEN"] = TOKEN_FILE.read_text().strip()

from kagglesdk import KaggleClient
from kagglesdk.kernels.types.kernels_api_service import (
    ApiSaveKernelRequest, ApiGetKernelSessionStatusRequest, ApiListKernelSessionOutputRequest,
)
from kagglesdk.kernels.types.kernels_enums import KernelWorkerStatus

USUARIO = "Victor871"
# Kaggle ignora el slug pedido en el primer push de un kernel NUEVO y lo deriva del titulo --
# tras el primer `push()` de una version nueva, copiar aqui el que devuelva de verdad (ver la
# url de "Subido y lanzado") antes de llamar a estado()/log()/bajar().
SLUG = "tfm-florence-2-lora-v3-atributos-prenda"
CARPETA = Path(__file__).parent


def cliente():
    return KaggleClient()


def push():
    req = ApiSaveKernelRequest()
    req.slug = f"{USUARIO}/{SLUG}"
    req.new_title = "TFM Florence-2 LoRA v3 (atributos prenda)"  # limite de Kaggle: 50 caracteres
    req.text = (CARPETA / "entrenar_en_kaggle.py").read_text(encoding="utf-8")
    req.language = "python"
    req.kernel_type = "script"
    req.is_private = True
    req.enable_gpu = True
    req.enable_internet = True
    r = cliente().kernels.kernels_api_client.save_kernel(req)
    if r.error:
        print("ERROR al subir:", r.error)
        sys.exit(1)
    print(f"Subido y lanzado: {r.url} (version {r.version_number})")


def estado(lineas_log=15):
    c = cliente()
    req = ApiGetKernelSessionStatusRequest()
    req.user_name, req.kernel_slug = USUARIO, SLUG
    r = c.kernels.kernels_api_client.get_kernel_session_status(req)
    print(f"Estado: {r.status.name}" + (f"  -- {r.failure_message}" if r.failure_message else ""))
    if r.status != KernelWorkerStatus.QUEUED:
        out = ApiListKernelSessionOutputRequest()
        out.user_name, out.kernel_slug = USUARIO, SLUG
        resp = c.kernels.kernels_api_client.list_kernel_session_output(out)
        if resp.log:
            print(f"--- ultimas {lineas_log} lineas del log ---")
            print("\n".join(resp.log.splitlines()[-lineas_log:]))
    return r.status


def log_completo():
    c = cliente()
    out = ApiListKernelSessionOutputRequest()
    out.user_name, out.kernel_slug = USUARIO, SLUG
    resp = c.kernels.kernels_api_client.list_kernel_session_output(out)
    print(resp.log or "(sin log todavia)")


def bajar(destino):
    import requests
    c = cliente()
    out = ApiListKernelSessionOutputRequest()
    out.user_name, out.kernel_slug = USUARIO, SLUG
    resp = c.kernels.kernels_api_client.list_kernel_session_output(out)
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    sesion = c.http_client()._session
    for f in resp.files:
        # defensivo: si algo vuelve a dejar ficheros con ruta (p.ej. el repo clonado colandose
        # en /kaggle/working, ver la nota historica en entrenar_en_kaggle.py), se ignoran aqui
        # en vez de fallar -- solo interesan los ficheros sueltos que se copiaron a proposito.
        if "/" in f.file_name:
            continue
        r = sesion.get(f.url)
        r.raise_for_status()
        (destino / f.file_name).write_bytes(r.content)
        print(f"  {f.file_name} ({len(r.content)} bytes) -> {destino / f.file_name}")
    if not resp.files:
        print("(sin ficheros de salida todavia)")


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else "estado"
    if accion == "push":
        push()
    elif accion == "estado":
        estado()
    elif accion == "log":
        log_completo()
    elif accion == "bajar":
        bajar(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
