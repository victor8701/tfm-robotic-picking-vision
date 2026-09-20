#!/usr/bin/env python3
"""
Lee las decisiones guardadas en el artifact "Reglas de temporada" (coleccion
`temporada_reglas`, un documento por tipo de prenda + `_default`) y genera el fragmento de
Python para pegar en preparar_dataset_florence2.py -- reemplaza a mano el bloque
`TIPOS_TODO_EL_ANO = {"Jackets"}` y la funcion `mapear_temporada` por lo que imprime este
script, y regenera el dataset (nueva version, v3) antes de reentrenar.

No llama a la API de Claude/ArtifactData directamente (este script es solo texto y JSON) --
los documentos hay que exportarlos primero con ArtifactData `list` + `out_dir` sobre la
coleccion `temporada_reglas` del artifact, igual que se hizo con las revisiones de la app
"Ficha de Prenda".

Uso:
    python3 leer_reglas_temporada.py --reglas /ruta/temporada_reglas/
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reglas", required=True, help="Carpeta con un JSON por tipo (salida de ArtifactData list --out_dir).")
    args = ap.parse_args()

    docs = {}
    for p in Path(args.reglas).expanduser().glob("*.json"):
        d = json.load(open(p, encoding="utf-8"))
        docs[p.stem] = d.get("data", d)

    default = docs.pop("_default", {"regla": "estacional"})["regla"]
    todo_el_ano = sorted(tipo.replace("_", " ") for tipo, d in docs.items() if d["regla"] == "todo_el_ano")
    estacional = sorted(tipo.replace("_", " ") for tipo, d in docs.items() if d["regla"] == "estacional")
    pendientes = sorted(tipo.replace("_", " ") for tipo, d in docs.items() if d["regla"] == "pendiente")

    print(f"{len(docs)} tipos decididos. Por defecto (tipos no listados): {default}\n")
    print(f"todo_el_ano ({len(todo_el_ano)}): {todo_el_ano}")
    print(f"estacional  ({len(estacional)}): {estacional}")
    if pendientes:
        print(f"pendientes  ({len(pendientes)}) -- se quedan en el default ({default}) hasta que se decidan: {pendientes}")

    def como_set_python(nombre, tipos):
        lineas = ",\n".join(f'    "{t}"' for t in tipos)
        return f"{nombre} = {{\n{lineas},\n}}"

    print("\n--- pegar en preparar_dataset_florence2.py (reemplaza TIPOS_TODO_EL_ANO) ---\n")
    print(como_set_python("TIPOS_TODO_EL_ANO", todo_el_ano))
    if default == "todo_el_ano":
        print("\n# aviso: el default para tipos NO listados tambien se marco 'todo_el_ano' -- eso no")
        print("# se representa como un set de exclusion (TIPOS_TODO_EL_ANO), hace falta invertir la")
        print("# logica de mapear_temporada() a 'todo_el_ano salvo estos tipos estacionales':")
        print(como_set_python("TIPOS_ESTACIONALES", estacional))
        print(
            "\ndef mapear_temporada(fila):\n"
            "    if fila.get('articleType') in TIPOS_ESTACIONALES:\n"
            "        return TEMPORADA_POR_SEASON.get(fila['season'])\n"
            "    return 'todo_el_ano'"
        )


if __name__ == "__main__":
    main()
