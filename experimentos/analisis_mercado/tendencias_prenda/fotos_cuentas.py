"""Baja las fotos recientes (direcciones `media_url` de Windsor, que caducan a los ~5 días) y monta una tira de 3 miniaturas por cuenta (JPEG de ~30 KB) para las tarjetas de «Cuentas de Instagram».

Uso:  python3 fotos_cuentas.py CARPETA   (CARPETA contiene `fotos_urls.json` = {"usuario": [url, url, url]} y recibe `fotos_pub/<usuario>.jpg`)
Después:  python3 cuentas_instagram.py html --tsv ... --salida pagina.html --fotos CARPETA/fotos_pub   y publicar `fotos_pub/<usuario>.jpg` como `f/<usuario>.jpg` junto a la página.
Privacidad: las fotos NO se guardan en el repositorio (solo viven dentro del Artifact privado de Víctor); la carpeta de trabajo se borra al terminar."""
import io, json, sys, urllib.request
from pathlib import Path
from PIL import Image, ImageOps

SC = Path(sys.argv[1])
URLS = json.load(open(SC / "fotos_urls.json", encoding="utf-8"))
OUT = SC / "fotos_pub"
OUT.mkdir(exist_ok=True)
W, H = 210, 280   # cada miniatura 3:4 (como la rejilla del perfil)
ok, fallos = {}, {}
for user, urls in URLS.items():
    tiles = []
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                img = Image.open(io.BytesIO(r.read())).convert("RGB")
            tiles.append(ImageOps.fit(img, (W, H), method=Image.LANCZOS, centering=(0.5, 0.35)))
        except Exception as e:  # noqa: BLE001
            fallos.setdefault(user, []).append(type(e).__name__ + " " + str(getattr(e, "code", "")))
    if not tiles:
        continue
    tira = Image.new("RGB", (W * 3 + 4, H), (47, 51, 70))   # siempre 3 casillas: las que faltan quedan en gris, así todas las tiras tienen la misma proporción
    for i, t in enumerate(tiles):
        tira.paste(t, (i * (W + 2), 0))
    tira.save(OUT / f"{user}.jpg", "JPEG", quality=72, optimize=True, progressive=True)
    ok[user] = len(tiles)
print("tiras:", ok)
print("fallos:", fallos)
print("tamaño total KB:", round(sum(p.stat().st_size for p in OUT.glob("*.jpg")) / 1024))
