#!/usr/bin/env python3
"""
Página de toques «Cuentas de Instagram» (Artifact con base de datos): Víctor marca ✓ Fuente / ✕ No en cada cuenta candidata y «Ya la sigo»; puede cambiar el estilo y el mercado propuestos.

  python3 cuentas_instagram.py html --tsv ../diario_feed_instagram/candidatos_instagram.tsv --salida PAGINA.html [--fotos CARPETA]
        incrusta las candidatas (y la lista de las que no se leen) en la plantilla `cuentas_instagram.html`
  python3 cuentas_instagram.py importar --dir DIR [--aplicar]
        DIR = carpeta de ArtifactData (`list` sobre la colección `ig` con `out_dir`): resume sus respuestas; con --aplicar añade las ✓ a `tendencia_fuentes.json`
        como fuentes de tipo `instagram` (sin duplicar; estilo y mercado = los que dejó en la página)
"""
import argparse
import csv
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PLANTILLA = AQUI / "cuentas_instagram.html"
FUENTES = AQUI.parent / "tendencia_fuentes.json"


def cargar(tsv: Path):
    cuentas, no_leen = [], []
    with open(tsv, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["windsor"].startswith("NO se lee"):
                no_leen.append(r["usuario"])
                continue
            cuentas.append({"u": r["usuario"], "e": r["estilo_propuesto"], "m": r["mercado_propuesto"], "t": r["tipo"], "s": r["seguidores"], "c": r["categoria_del_perfil"],
                            "w": "leida" if r["windsor"].startswith("le") else "sin", "p": r["publicaciones_14d"], "g": r["buenas_de_las_bajadas"], "k": r["nota"], "r": 1 if r.get("propuesta") else 0})
    return cuentas, no_leen


def cmd_html(a):
    cuentas, no = cargar(Path(a.tsv))
    if getattr(a, "fotos", None):
        p = Path(a.fotos)   # carpeta con <usuario>.jpg, o un .txt con un usuario por línea (las fotos ya están publicadas junto a la página)
        con = {x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()} if p.is_file() else {f.stem for f in p.glob("*.jpg")}
        for c in cuentas:
            c["i"] = 1 if c["u"] in con else 0
    pagina = PLANTILLA.read_text(encoding="utf-8").replace("__CUENTAS__", json.dumps(cuentas, ensure_ascii=False).replace("</", "<\\/")).replace("__NO__", json.dumps(no, ensure_ascii=False))
    Path(a.salida).write_text(pagina, encoding="utf-8")
    print(f"{len(cuentas)} cuentas ({sum(c['w'] == 'leida' for c in cuentas)} leídas por Windsor) y {len(no)} no legibles → {a.salida} ({len(pagina) // 1024} KB)")


def cmd_importar(a):
    docs = []
    for f in sorted(Path(a.dir).rglob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d = d.get("data", d)
        if isinstance(d, dict) and d.get("u"):
            docs.append(d)
    si = [d for d in docs if d.get("r") == "si"]
    no = [d for d in docs if d.get("r") == "no"]
    print(f"Respuestas: {len(docs)} · ✓ {len(si)} · ✕ {len(no)} · ya las sigue {sum(bool(d.get('f')) for d in docs)}")
    if not a.aplicar:
        for d in si:
            print(f"  ✓ @{d['u']} → {d.get('e') or '(estilo propuesto)'} {d.get('m') or '(mercado propuesto)'}")
        return
    base = {c["u"]: c for c in cargar(Path(a.tsv))[0]} if a.tsv else {}
    cfg = json.loads(FUENTES.read_text(encoding="utf-8"))
    ya = {(x["tipo"], x["valor"].lstrip("@").lower()) for x in cfg["fuentes"]}
    n = 0
    for d in si:
        u = d["u"]
        if ("instagram", u.lower()) in ya:
            continue
        c = base.get(u, {})
        estilo, mercado = d.get("e") or c.get("e"), d.get("m") or c.get("m")
        if not estilo or not mercado:
            print(f"  (sin estilo o mercado: @{u}; no se añade)")
            continue
        cfg["fuentes"].append({"referente": u, "estilo": estilo, "mercado": mercado, "tipo": "instagram", "valor": u})
        n += 1
    FUENTES.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Añadidas {n} fuentes de Instagram a {FUENTES.name} (total {len(cfg['fuentes'])})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("html")
    p.add_argument("--tsv", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--fotos", default=None, help="carpeta con una tira <usuario>.jpg por cuenta (se publica como f/<usuario>.jpg junto a la página) o un .txt con los usuarios que ya tienen foto")
    p = sub.add_parser("importar")
    p.add_argument("--dir", required=True)
    p.add_argument("--tsv", default=None, help="candidatos_instagram.tsv (necesario con --aplicar para el estilo/mercado propuestos)")
    p.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    {"html": cmd_html, "importar": cmd_importar}[a.cmd](a)


if __name__ == "__main__":
    main()
