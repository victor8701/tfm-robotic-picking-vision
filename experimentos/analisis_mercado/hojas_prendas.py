#!/usr/bin/env python3
"""
Hojas de recortes de prendas para etiquetar desde el móvil (2026-10-06): tipo, estampado y forma de cada prenda.

  crear     elige N recortes de `tendencia_datos/prendas.json` (variedad de tipos, estilos y fuentes; un tercio de los más dudosos para el modelo) y los dibuja en
            hojas de 12 recortes numerados P01… (`tendencia_datos/cache/hojas_prendas/`). NO se escribe la predicción del modelo: así lo que contestas sirve también
            para medir cuánto acierta el modelo de verdad.
  resolver  pasa tus respuestas a `tendencia_datos/etiquetas_prendas.json` (va a git: id de foto, caja y tus etiquetas; sin imágenes).
  html      genera la página «Etiquetar prendas» (Artifact) con los recortes incrustados, para etiquetar a toques desde el móvil (sin teclear códigos).
  importar  lee las etiquetas que la página guardó en su base (exportadas con ArtifactData `--out_dir`) y las pasa a `etiquetas_prendas.json`.

Formato de respuesta, una línea por recorte:   <recorte> <tipo> <estampado> <forma>      p. ej.  "3 7 L O" = recorte 3, sudadera, lisa, oversized.
  tipo: número de la leyenda (1-28);  estampado: L liso · R rayas · C cuadros/tartán · G gráfico/dibujo · T texto/logo · K camuflaje · O otro;
  forma: O oversized/baggy · R regular · S ajustada · C corta/cropped · N no aplica (calzado, falda, vestido…).   "5 x" = recorte inservible.

Uso:  python3 hojas_prendas.py crear [--n 36]   |   python3 hojas_prendas.py resolver --respuestas "1 7 L O; 2 14 L R; 3 x"
      python3 hojas_prendas.py html --salida etiquetar_prendas_build.html   |   python3 hojas_prendas.py importar --dir <carpeta exportada de la base>
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
TD = AQUI / "tendencia_datos"
CACHE = TD / "cache"
SALIDA = CACHE / "hojas_prendas"
ETIQ = TD / "etiquetas_prendas.json"
TIPOS = ["Camiseta manga corta", "Camiseta de tirantes", "Camiseta manga larga", "Top", "Camisa", "Polo", "Sudadera", "Hoodie", "Jersey", "Chaleco sin mangas", "Chaqueta", "Americana",
         "Abrigo", "Plumas", "Pantalón", "Falda", "Short", "Legging/Malla", "Vestido", "Mono", "Zapatillas deportivas", "Zapatillas casual/lifestyle", "Zapatos de vestir",
         "Zapatos de tacón", "Sandalias", "Botas", "Bolso", "Riñonera", "Gorra/Gorro/Sombrero"]
ESTAMPADOS = {"L": "liso", "R": "rayas", "C": "cuadros", "G": "gráfico / dibujo", "T": "texto / logo", "K": "camuflaje", "O": "otro"}
FORMAS = {"O": "oversized / baggy", "R": "regular", "S": "ajustada", "C": "corta / cropped", "N": "no aplica"}
# prioridad de cobertura (n recortes por tipo que predijo el modelo) en una tanda de 36
CUPO = {"Sudadera": 5, "Camiseta manga corta": 4, "Camiseta manga larga": 2, "Jersey": 3, "Chaqueta": 4, "Pantalón": 5, "Falda": 3, "Short": 2, "Vestido": 1,
        "Camisa": 2, "Botas": 2, "Zapatillas deportivas": 1, "Zapatillas casual/lifestyle": 1, "Polo": 1}


def candidatos() -> list[dict]:
    fotos = json.loads((TD / "fotos.json").read_text(encoding="utf-8"))
    prendas = json.loads((TD / "prendas.json").read_text(encoding="utf-8"))
    ya = json.loads(ETIQ.read_text(encoding="utf-8")) if ETIQ.exists() else {}
    out = []
    for fid, r in prendas.items():
        f = fotos.get(fid)
        if not f or f.get("descartada") or not (CACHE / "img" / f"{fid}.jpg").exists():
            continue
        for i, p in enumerate(r["prendas"]):
            x1, y1, x2, y2 = p["caja"]
            ancho, alto = x2 - x1, y2 - y1
            if not p["visible"] or min(ancho, alto) < 110 or not 0.4 <= ancho / alto <= 2.5 or f"{fid}#{i}" in ya:
                continue
            out.append({"foto": fid, "idx": i, "caja": p["caja"], "tipo": p["tipo"], "p": p["p_tipo"], "cat": p["cat"], "estilo": f["estilo"],
                        "mercado": f["mercado"], "fuente": f.get("referente") or "Biblioteca"})
    return out


def elegir(c: list[dict], n: int, semilla: int = 3) -> list[dict]:
    rnd = random.Random(semilla)
    rnd.shuffle(c)
    elegidos, usadas = [], collections_counter()
    # 1) cupo por tipo, alternando estilos y repartiendo las fotos (un recorte por foto)
    for tipo, cupo in CUPO.items():
        pool = [x for x in c if x["tipo"] == tipo]
        pool.sort(key=lambda x: (usadas[x["foto"]], x["estilo"] != ("geek" if len(elegidos) % 2 else "urbano")))
        for x in pool:
            if cupo and len([e for e in elegidos if e["tipo"] == tipo]) < cupo and usadas[x["foto"]] < 1:
                elegidos.append(x)
                usadas[x["foto"]] += 1
    # 2) relleno con los más dudosos del resto
    resto = sorted([x for x in c if x not in elegidos and usadas[x["foto"]] < 1], key=lambda x: x["p"])
    for x in resto:
        if len(elegidos) >= n:
            break
        elegidos.append(x)
        usadas[x["foto"]] += 1
    rnd.shuffle(elegidos)
    return elegidos[:n]


def collections_counter():
    import collections
    return collections.defaultdict(int)


def recorte(x: dict) -> Image.Image:
    im = Image.open(CACHE / "img" / f"{x['foto']}.jpg").convert("RGB")
    W, H = im.size
    x1, y1, x2, y2 = x["caja"]
    bw, bh = x2 - x1, y2 - y1
    return im.crop((max(0, int(x1 - .06 * bw)), max(0, int(y1 - .06 * bh)), min(W, int(x2 + .06 * bw)), min(H, int(y2 + .06 * bh))))


def sugerir(el: list[dict]) -> list[list[str]]:
    """Las tres opciones de tipo más probables según CLIP ViT-B/32 sin restringir (en el lote 1 acertó la de Víctor 18/27 a la primera y 23/27 entre las tres)."""
    sys.path.insert(0, str(AQUI.parent / "vlm_atributos_prenda" / "herramientas"))
    import evaluar_etiquetas_prendas as ev
    import numpy as np
    import torch
    torch.set_grad_enabled(False)
    model, prep, tok = ev.pc.cargar(None, None)
    nombres = list(ev.TIPOS)
    t = model.encode_text(tok(["a photo of " + p for p in ev.TIPOS.values()]))
    T = (t / t.norm(dim=-1, keepdim=True)).numpy()
    out = []
    for x in el:
        v = model.encode_image(prep(ev.recorte(CACHE / "img" / f"{x['foto']}.jpg", x["caja"])).unsqueeze(0))
        v = (v / v.norm(dim=-1, keepdim=True)).numpy()[0]
        orden = [nombres[j] for j in np.argsort(-(T @ v))]
        out.append(orden[:3])
    return out


def cmd_crear(a):
    c = candidatos()
    if not c:
        raise SystemExit("No hay recortes nuevos para etiquetar.")
    el = elegir(c, a.n)
    sugerencias = sugerir(el)
    SALIDA.mkdir(parents=True, exist_ok=True)
    for f in SALIDA.glob("*"):
        f.unlink()
    try:
        fu = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
        fp = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    except OSError:
        fu = fp = ImageFont.load_default()
    W, H = 300, 250
    medidor = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    def partir(prefijo: str, items: list[str], ancho: int = 880) -> list[str]:
        lineas, actual = [], prefijo
        for it in items:
            prueba = actual + ("  " if actual.strip() else "") + it
            if medidor.textlength(prueba, font=fp) > ancho and actual.strip():
                lineas.append(actual)
                actual = "    " + it
            else:
                actual = prueba
        return lineas + [actual]
    leyenda = (partir("TIPO:  ", [f"{i + 1} {t}" for i, t in enumerate(TIPOS)]) + partir("ESTAMPADO:  ", [f"{k} {v}" for k, v in ESTAMPADOS.items()])
               + partir("FORMA:  ", [f"{k} {v}" for k, v in FORMAS.items()]) + ["Respuesta:  recorte tipo estampado forma   (ej. 3 7 L O)     x = inservible"])
    FOOT = 14 + 22 * len(leyenda)
    estado = {}
    hojas = (len(el) + 11) // 12
    for h in range(hojas):
        im = Image.new("RGB", (3 * W, 4 * H + FOOT), (24, 24, 32))
        dr = ImageDraw.Draw(im)
        for n, x in enumerate(el[h * 12:(h + 1) * 12]):
            c_ = recorte(x)
            c_.thumbnail((W - 8, H - 8))
            px, py = (n % 3) * W, (n // 3) * H
            im.paste(c_, (px + 4 + (W - 8 - c_.width) // 2, py + 4))
            pid = h * 12 + n + 1
            dr.rectangle([px, py, px + 40, py + 22], fill=(0, 0, 0))
            dr.text((px + 5, py + 3), f"{pid}", fill=(255, 255, 255), font=fu)
            estado[f"{a.prefijo}{pid}"] = {"foto": x["foto"], "idx": x["idx"], "caja": x["caja"], "tipo_modelo": x["tipo"], "estilo": x["estilo"], "mercado": x["mercado"],
                                "sug": sugerencias[pid - 1]}
        y0 = 4 * H + 6
        for k, t in enumerate(leyenda):
            dr.text((8, y0 + k * 22), t, fill=(255, 220, 140) if t.startswith("Respuesta") else (210, 215, 235), font=fp)
        im.save(SALIDA / f"hoja_prendas_{h + 1}.jpg", quality=88)
    (SALIDA / "estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(el)} recortes en {hojas} hojas: {SALIDA}")


def cmd_resolver(a):
    estado = json.loads((SALIDA / "estado.json").read_text(encoding="utf-8"))
    etiq = json.loads(ETIQ.read_text(encoding="utf-8")) if ETIQ.exists() else {}
    hechas, malas = 0, []
    for linea in re.split(r"[;\n]+", a.respuestas):
        t = linea.strip().split()
        if not t:
            continue
        pid = t[0].lstrip("pP#")
        if pid not in estado:
            malas.append(linea.strip())
            continue
        e = estado[pid]
        clave = f"{e['foto']}#{e['idx']}"
        if len(t) == 2 and t[1].lower() in ("x", "?"):
            etiq[clave] = {"inservible": True, "caja": e["caja"], "tipo_modelo": e["tipo_modelo"], "estilo": e["estilo"]}
            hechas += 1
            continue
        try:
            tipo = TIPOS[int(t[1]) - 1]
            est, forma = ESTAMPADOS[t[2].upper()], FORMAS[t[3].upper()]
        except (IndexError, ValueError, KeyError):
            malas.append(linea.strip())
            continue
        etiq[clave] = {"tipo": tipo, "estampado": est, "forma": forma, "caja": e["caja"], "tipo_modelo": e["tipo_modelo"], "estilo": e["estilo"], "mercado": e["mercado"]}
        hechas += 1
    ETIQ.write_text(json.dumps(etiq, ensure_ascii=False, indent=1), encoding="utf-8")
    sin = sorted(set(estado) - {k.split("|")[0] for k in []} - {p for p, e in estado.items() if f"{e['foto']}#{e['idx']}" in etiq}, key=int)
    print(f"Guardadas {hechas} etiquetas ({len(etiq)} en total). No entendidas: {malas or 'ninguna'}. Sin contestar: {sin or 'ninguna'}")


def cmd_html(a):
    import base64
    import io
    estado = json.loads((SALIDA / "estado.json").read_text(encoding="utf-8"))
    crops = []
    for pid in sorted(estado, key=lambda k: (len(k), k)):   # «b2-1» … «b2-9» antes que «b2-10»
        im = recorte(estado[pid])
        im.thumbnail((480, 480))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=72)
        crops.append({"id": pid, "src": "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode(), "sug": estado[pid].get("sug", [])})
    plantilla = Path(a.plantilla).read_text(encoding="utf-8")
    Path(a.salida).write_text(plantilla.replace("__CROPS__", json.dumps(crops, ensure_ascii=False)), encoding="utf-8")
    print(f"{len(crops)} recortes incrustados en {a.salida} ({Path(a.salida).stat().st_size // 1024} KB)")


def cmd_importar(a):
    estado = json.loads(Path(a.estado).read_text(encoding="utf-8"))
    etiq = json.loads(ETIQ.read_text(encoding="utf-8")) if ETIQ.exists() else {}
    n = sin = 0
    for f in sorted(Path(a.dir).rglob("c*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d = d.get("data", d)
        pid = f.stem[1:]
        e = estado.get(pid)
        if not e:
            continue
        clave = f"{e['foto']}#{e['idx']}"
        ps = d.get("prendas") or [d]   # la página guarda una lista de prendas por recorte (y los campos de la primera sueltos, por compatibilidad)
        ps = [q for q in ps if q.get("tipo") or q.get("estampado") or q.get("tejido") or q.get("forma")]   # se guardan también las prendas a medias: lo vacío queda a None
        if d.get("x"):
            etiq[clave] = {"inservible": True, "caja": e["caja"], "tipo_modelo": e["tipo_modelo"], "estilo": e["estilo"]}
        elif ps:
            etiq[clave] = {"prendas": [{c: (q.get(c) or None) for c in ("tipo", "estampado", "tejido", "forma")} for q in ps],
                           "caja": e["caja"], "tipo_modelo": e["tipo_modelo"], "estilo": e["estilo"], "mercado": e["mercado"]}
            sin += not all(all(q.get(c) for c in ("tipo", "estampado", "tejido", "forma")) for q in ps)
        else:
            continue
        n += 1
    ETIQ.write_text(json.dumps(etiq, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Importadas {n} etiquetas ({sin} con alguna prenda a medias); {len(etiq)} en total")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("crear")
    p.add_argument("--n", type=int, default=36)
    p.add_argument("--prefijo", default="", help="prefijo de los números de recorte (p. ej. «b2-» en el lote 2) para no pisar las etiquetas de lotes anteriores en la base de la página")
    p = sub.add_parser("resolver")
    p.add_argument("--respuestas", required=True)
    p = sub.add_parser("html")
    p.add_argument("--plantilla", default=str(AQUI / "tendencias_prenda" / "etiquetar_prendas.html"))
    p.add_argument("--salida", required=True)
    p = sub.add_parser("importar")
    p.add_argument("--dir", required=True)
    p.add_argument("--estado", default=str(TD / "etiquetado_lote1_estado.json"), help="qué foto y caja es cada número de recorte del lote (se guarda aparte porque cache/ no va a git)")
    a = ap.parse_args()
    {"crear": cmd_crear, "resolver": cmd_resolver, "html": cmd_html, "importar": cmd_importar}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
