#!/usr/bin/env python3
"""
HMI simulado de aprobación de tendencias (Estado_arte.md §6.5) como página de toques (Artifact con base de datos).

  python3 hmi_aprobacion.py html [--trends trends] --salida PAGINA.html
        incrusta los Trend JSON pendientes (trends/pending), sus 5 mejores SKUs (trends/scored: miniaturas del inventario de prueba) y el índice de casillas sin generar
  python3 hmi_aprobacion.py aplicar --dir DIR [--trends trends]
        DIR = carpeta de ArtifactData (`list` sobre la colección `trends` con `out_dir`): lo aprobado pasa de pending/ a active/ (con el vector del texto de CLIP, como dice §6.5)
        y lo rechazado a rejected/ (sin efecto); lo que no tiene decisión se queda en pending/
"""
import argparse
import base64
import io
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
POC = AQUI.parent
REPO = POC.parent.parent
PLANTILLA = AQUI / "hmi_aprobacion.html"


def miniatura(ruta_rel: str, ancho: int = 90) -> str:
    im = Image.open(REPO / ruta_rel).convert("RGB")
    im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=84)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def datos_pagina(trends: Path, k: int = 5) -> dict:
    out = []
    for f in sorted((trends / "pending").glob("*.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        s = json.loads((trends / "scored" / f.name).read_text(encoding="utf-8"))
        out.append({"id": t["id"], "nombre": t["nombre"], "desc": t["descripcion"], "clip": t["descripcion_clip"], "grupos": t["grupo_estilo_detectado"], "fotos": t["evidencia"]["fotos"],
                    "prendas": [{"tipo": p["tipo"], "cuota": p["cuota"], "fotos": p["fotos"], "confianza": p.get("confianza")} for p in t["evidencia"]["prendas"]],
                    "alineados": s["n_alineados"], "dist": s["distribucion_semantica"],
                    "top": [{"nombre": Path(r["ruta"]).stem, "img": miniatura(r["ruta"]), "score": r["score"], "boost": r["boost"]} for r in s["top"][:k]]})
        meta = {"n_sku": s["n_sku"]}
    indice = json.loads((trends / "indice.json").read_text(encoding="utf-8"))
    meta.update({"fecha": indice["fecha"], "temporada": indice["temporada"]})
    return {"trends": out, "indice": indice["casillas"], "meta": meta}


def cmd_html(a):
    datos = datos_pagina(a.trends)
    pagina = PLANTILLA.read_text(encoding="utf-8").replace("__DATOS__", json.dumps(datos, ensure_ascii=False).replace("</", "<\\/"))
    Path(a.salida).write_text(pagina, encoding="utf-8")
    print(f"{len(datos['trends'])} tendencias pendientes → {a.salida} ({len(pagina) // 1024} KB)")


def codificar(texto: str) -> list[float]:
    sys.path.insert(0, str(POC))
    from clip_matching_poc import cargar_modelo, encodear_textos  # noqa: E402
    model, _, tok = cargar_modelo()
    return [round(float(x), 6) for x in encodear_textos(model, tok, [texto])[0].numpy()]


def cmd_aplicar(a, codificar=codificar):
    decisiones = {}
    for f in sorted(Path(a.dir).rglob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d = d.get("data", d)
        if isinstance(d, dict) and d.get("id") and d.get("e") in ("aprobada", "rechazada"):
            decisiones[d["id"]] = d
    for sub in ("active", "rejected"):
        (a.trends / sub).mkdir(parents=True, exist_ok=True)
    movidas = {"aprobada": 0, "rechazada": 0}
    for id_, d in decisiones.items():
        origen = a.trends / "pending" / f"{id_}.json"
        if not origen.exists():
            continue
        t = json.loads(origen.read_text(encoding="utf-8"))
        t.update({"estado": d["e"], "decidida_en": datetime.now(timezone.utc).isoformat(timespec="seconds"), "nota_operario": d.get("n", "")})
        if d["e"] == "aprobada":
            t["v_tendencia"] = codificar(t["descripcion_clip"])
        destino = a.trends / ("active" if d["e"] == "aprobada" else "rejected") / origen.name
        destino.write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
        origen.unlink()
        movidas[d["e"]] += 1
    print(f"Aprobadas {movidas['aprobada']} (a active/, con vector) · rechazadas {movidas['rechazada']} (a rejected/) · siguen pendientes {len(list((a.trends / 'pending').glob('*.json')))}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("html")
    p.add_argument("--trends", type=Path, default=AQUI / "trends")
    p.add_argument("--salida", required=True)
    p = sub.add_parser("aplicar")
    p.add_argument("--dir", required=True)
    p.add_argument("--trends", type=Path, default=AQUI / "trends")
    a = ap.parse_args()
    {"html": cmd_html, "aplicar": cmd_aplicar}[a.cmd](a)


if __name__ == "__main__":
    main()
