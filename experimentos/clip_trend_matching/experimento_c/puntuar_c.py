#!/usr/bin/env python3
"""
Página de toques para puntuar a ciegas las prendas nuevas del Experimento C (0 = no encaja, 1 = dudoso, 2 = encaja), con el mismo método que `../experimento_b/evaluar_b.py` pero desde el móvil.

  python3 puntuar_c.py html --salida PAGINA.html     incrusta las prendas de `pool_c.json` (miniaturas de 60×80 px ampliadas ×3) y guarda `pool_c_ids.json` (c1… → clave)
  python3 puntuar_c.py importar --dir DIR            pasa las respuestas de la base de la página (exportadas con ArtifactData `puntuaciones`) a `../experimento_b/ratings_b.json`

La página no enseña qué texto ni qué método propuso cada prenda: solo el nombre y los rasgos de la tendencia, como en B.
"""
import argparse
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
POC = AQUI.parent
POOL, IDS = AQUI / "pool_c.json", AQUI / "pool_c_ids.json"
RATINGS = POC / "experimento_b" / "ratings_b.json"
PLANTILLA = AQUI / "puntuar_c.html"


def ruta_imagen(rel: str) -> Path:
    for base in (POC, POC / "experimento_b" / "inventario_extra"):
        p = base / rel
        if p.exists():
            return p
    sys.exit(f"no encuentro la imagen {rel}")


def cmd_html(a):
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    items, ids = [], {}
    for n, p in enumerate(pool, 1):
        im = Image.open(ruta_imagen(p["imagen"])).convert("RGB")
        im = im.resize((im.width * 3, im.height * 3), Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, "JPEG", quality=88)
        items.append({"id": f"c{n}", "src": "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode(), "nombre": p["nombre"], "rasgos": p["rasgos"]})
        ids[f"c{n}"] = p["clave"]
    IDS.write_text(json.dumps(ids, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(a.salida).write_text(PLANTILLA.read_text(encoding="utf-8").replace("__ITEMS__", json.dumps(items, ensure_ascii=False)), encoding="utf-8")
    print(f"{len(items)} prendas incrustadas en {a.salida} ({Path(a.salida).stat().st_size // 1024} KB); ids en {IDS.name}")


def cmd_importar(a):
    ids = json.loads(IDS.read_text(encoding="utf-8"))
    ratings = json.loads(RATINGS.read_text(encoding="utf-8")) if RATINGS.exists() else {}
    n = nuevas = 0
    for f in sorted(Path(a.dir).rglob("p*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d = d.get("data", d)
        clave = ids.get(f.stem[1:])
        if not clave or d.get("r") not in ("0", "1", "2"):
            continue
        nuevas += clave not in ratings
        ratings[clave] = int(d["r"])
        n += 1
    RATINGS.write_text(json.dumps(ratings, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"Importadas {n} puntuaciones ({nuevas} nuevas); en total {len(ratings)} en {RATINGS}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("html")
    p.add_argument("--salida", required=True)
    p = sub.add_parser("importar")
    p.add_argument("--dir", required=True)
    a = ap.parse_args()
    {"html": cmd_html, "importar": cmd_importar}[a.cmd](a)


if __name__ == "__main__":
    main()
