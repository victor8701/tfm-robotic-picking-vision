#!/usr/bin/env python3
"""
Mide lo que acierta cada atributo del flujo de tendencia por prenda y lo guarda en `tendencia_datos/fiabilidad.json`. El informe (`tendencia_prenda.py informe`) lo lee
para poner un techo de confianza a cada cifra: un atributo que acierta la mitad no puede dar una cifra de confianza «alta» por muchas fotos que tenga.

- tipo fino y familia: el tipo que da el flujo semanal frente a la prenda PRINCIPAL que Víctor etiquetó (y, aparte, frente a cualquiera de las prendas de ese recorte).
  Hoodie y Sudadera cuentan como lo mismo (el flujo aún no distingue la capucha). Se recalcula con sus etiquetas (`tendencia_datos/etiquetas_prendas.json`).
- color: no hay etiquetas de Víctor; se guarda la revisión a ojo hecha por el asistente (una sola persona, 30 prendas al azar). Se actualiza a mano al repetirla.
- estampado, tejido y forma: no se estiman en el flujo; se anotan los mejores resultados medidos (ver `memoria/TFM_tendencias_de_prenda.md` §6).

Uso:  python3 fiabilidad_prenda.py [--etiquetas RUTA] [--salida RUTA]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TD = AQUI / "tendencia_datos"
EQ = {"Hoodie": "Sudadera"}


def familia_de(tipo: str) -> str:
    sys.path.insert(0, str(AQUI))
    import tendencia_prenda as tp   # importa mercado.py: solo para leer FAMILIA
    return tp.FAMILIA.get(tipo, "Otros")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--etiquetas", type=Path, default=TD / "etiquetas_prendas.json")
    ap.add_argument("--salida", type=Path, default=TD / "fiabilidad.json")
    a = ap.parse_args()
    etiq = {k: v for k, v in json.loads(a.etiquetas.read_text(encoding="utf-8")).items() if v.get("prendas") and v["prendas"][0].get("tipo")}
    n = fino = fino_cual = fam = fam_cual = 0
    for v in etiq.values():
        modelo = v["tipo_modelo"]
        principal = v["prendas"][0]["tipo"]
        todos = {q["tipo"] for q in v["prendas"] if q.get("tipo")}
        n += 1
        fino += EQ.get(modelo, modelo) == EQ.get(principal, principal)
        fino_cual += any(EQ.get(modelo, modelo) == EQ.get(t, t) for t in todos)
        fam += familia_de(modelo) == familia_de(principal)
        fam_cual += any(familia_de(modelo) == familia_de(t) for t in todos)
    fiab = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tipo_fino": {"acierto": fino, "n": n, "cualquiera": fino_cual, "fuente": "etiquetas de Víctor (lotes 1 y 2)",
                      "metodo": "tipo del flujo semanal (CLIP ViT-B/32 dentro de la lista de la categoría del detector) frente a la prenda principal etiquetada; Hoodie = Sudadera",
                      "nota": "con «cualquiera de las prendas del recorte» sube; CLIP ViT-L/14 y una capa entrenada con sus etiquetas no mejoran"},
        "familia": {"acierto": fam, "n": n, "cualquiera": fam_cual, "fuente": "etiquetas de Víctor (lotes 1 y 2)",
                    "metodo": "arriba · abrigo · abajo · cuerpo entero · calzado · accesorio, con el mismo tipo del flujo semanal"},
        "color": {"acierto": 21, "n": 30, "fuente": "revisión a ojo del asistente, 30 prendas al azar (no de Víctor)", "techo": "baja",
                  "metodo": "color_primario del adaptador Florence-2 v3 sobre el recorte",
                  "nota": "5 claramente mal y 4 dudosas; sesgo hacia «negro»: prendas rojas, moradas, doradas o de camuflaje salen negras o grises"},
        "estampado": {"estado": "no se estima", "mejor_medido": "12 a 13 de 22, igual que decir siempre «liso» (11 de 22)", "fuente": "memoria/TFM_tendencias_de_prenda.md §6"},
        "tejido": {"estado": "no se estima", "mejor_medido": "6 de 17 con CLIP; decir siempre «algodón» da 10 de 17", "fuente": "memoria/TFM_tendencias_de_prenda.md §6"},
        "forma": {"estado": "no se estima", "mejor_medido": "4 a 9 de 23; decir siempre «oversized» da 11 de 23", "fuente": "memoria/TFM_tendencias_de_prenda.md §6"},
    }
    a.salida.write_text(json.dumps(fiab, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"tipo fino {fino}/{n} ({fino / n:.0%}; cualquiera {fino_cual}/{n}) · familia {fam}/{n} ({fam / n:.0%}; cualquiera {fam_cual}/{n}) · color 21/30 a ojo → {a.salida}")


if __name__ == "__main__":
    main()
