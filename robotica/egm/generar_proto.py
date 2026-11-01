"""Genera egm.proto y el descriptor embebido a partir del código C# generado por protoc.

Uso (desde la carpeta robotica/):
    python3 egm/generar_proto.py ruta/a/Egm.cs

El Egm.cs del proyecto previo lleva el FileDescriptorProto completo de egm.proto en base64.
Este script lo decodifica, escribe un egm.proto equivalente y guarda el descriptor en
_descriptor_egm.py. Los tests comprueban el resultado con protoc.
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

from google.protobuf import descriptor_pb2

FD = descriptor_pb2.FieldDescriptorProto

_TIPOS = {
    FD.TYPE_DOUBLE: "double", FD.TYPE_FLOAT: "float", FD.TYPE_INT64: "int64",
    FD.TYPE_UINT64: "uint64", FD.TYPE_INT32: "int32", FD.TYPE_FIXED64: "fixed64",
    FD.TYPE_FIXED32: "fixed32", FD.TYPE_BOOL: "bool", FD.TYPE_STRING: "string",
    FD.TYPE_BYTES: "bytes", FD.TYPE_UINT32: "uint32", FD.TYPE_SFIXED32: "sfixed32",
    FD.TYPE_SFIXED64: "sfixed64", FD.TYPE_SINT32: "sint32", FD.TYPE_SINT64: "sint64",
}
_ETIQUETAS = {
    FD.LABEL_OPTIONAL: "optional", FD.LABEL_REQUIRED: "required", FD.LABEL_REPEATED: "repeated",
}


def base64_desde_csharp(texto: str) -> str:
    m = re.search(r"FromBase64String\(\s*string\.Concat\((.*?)\)\s*\);", texto, re.S)
    if not m:
        raise ValueError("no se encuentra el descriptor base64 en el archivo C#")
    return "".join(re.findall(r'"([A-Za-z0-9+/=]*)"', m.group(1)))


def _campo(f) -> str:
    if f.HasField("oneof_index"):
        raise ValueError("oneof no soportado por este generador")
    if f.type in (FD.TYPE_MESSAGE, FD.TYPE_ENUM):
        tipo = f.type_name
    else:
        tipo = _TIPOS[f.type]
    opciones = ""
    if f.HasField("default_value"):
        valor = f.default_value
        if f.type == FD.TYPE_STRING:
            valor = f'"{valor}"'
        opciones = f" [default = {valor}]"
    return f"{_ETIQUETAS[f.label]} {tipo} {f.name} = {f.number}{opciones};"


def _enum(e, sangria: str) -> list[str]:
    lineas = [f"{sangria}enum {e.name} {{"]
    lineas += [f"{sangria}  {v.name} = {v.number};" for v in e.value]
    lineas.append(f"{sangria}}}")
    return lineas


def _mensaje(m, sangria: str) -> list[str]:
    lineas = [f"{sangria}message {m.name} {{"]
    for e in m.enum_type:
        lineas += _enum(e, sangria + "  ")
    for anidado in m.nested_type:
        lineas += _mensaje(anidado, sangria + "  ")
    lineas += [f"{sangria}  {_campo(f)}" for f in m.field]
    lineas.append(f"{sangria}}}")
    return lineas


def generar_proto(fdp) -> str:
    lineas = [
        "// Reconstruido por generar_proto.py a partir del descriptor embebido en Egm.cs.",
        "// Equivale al egm.proto de ABB que usa el proyecto previo (ver egm/generar_proto.py).",
        f'syntax = "{fdp.syntax or "proto2"}";',
        "",
        f"package {fdp.package};",
        "",
    ]
    for m in fdp.message_type:
        lineas += _mensaje(m, "")
        lineas.append("")
    return "\n".join(lineas).rstrip() + "\n"


def generar_descriptor_py(b64: str) -> str:
    trozos = [b64[i:i + 96] for i in range(0, len(b64), 96)]
    cuerpo = "\n".join(f'    "{t}"' for t in trozos)
    return (
        '"""Descriptor de egm.proto en base64 (generado por generar_proto.py; no editar a mano)."""\n\n'
        "DESCRIPTOR_BASE64 = (\n"
        f"{cuerpo}\n"
        ")\n"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    b64 = base64_desde_csharp(Path(sys.argv[1]).read_text(encoding="utf-8"))
    fdp = descriptor_pb2.FileDescriptorProto()
    fdp.ParseFromString(base64.b64decode(b64))
    carpeta = Path(__file__).resolve().parent
    (carpeta / "egm.proto").write_text(generar_proto(fdp), encoding="utf-8")
    (carpeta / "_descriptor_egm.py").write_text(generar_descriptor_py(b64), encoding="utf-8")
    print(f"escritos: egm.proto ({fdp.name}, paquete {fdp.package}) y _descriptor_egm.py")
