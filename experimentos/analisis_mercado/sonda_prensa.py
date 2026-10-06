"""Sonda (2026-10-06): ¿cuántas fotos de «persona con ropa» salen de la prensa que nombra a cada referente? Consulta Bing Noticias (RSS público), se queda con las
noticias de los últimos --dias que nombran a la persona y traen alguna palabra de contexto, baja las imágenes de cada artículo (>= 400 px) y cuenta las que pasan la puerta
CLIP «persona con ropa» sin repetir. NO toca los datos de la app: usa MERCADO_DATOS para que la caché de embeddings quede aparte.

    MERCADO_DATOS=/tmp/datos_prueba python3 sonda_prensa.py --salida /tmp/prensa_probe [--dias 180]
Resultado de la primera pasada y su revisión a ojo: resultados_sonda_prensa_2026-10-06.json
"""
import argparse
import json, re, sys, time, unicodedata, urllib.parse, urllib.request, html
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mercado as m

_ap = argparse.ArgumentParser(); _ap.add_argument("--salida", required=True, type=Path); _ap.add_argument("--dias", type=int, default=180); _a = _ap.parse_args()
OUT = _a.salida; (OUT / "img").mkdir(parents=True, exist_ok=True)
DIAS = _a.dias
AHORA = datetime.now(timezone.utc)
norm = lambda s: unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()
MUSICA = ["cantante", "rapero", "artista", "cancion", "disco", "concierto", "musica", "trap", "gira", "festival", "album", "tema", "single"]
REF = {
    "Quevedo": (['"Quevedo" cantante', '"Quevedo" cantante concierto', '"Quevedo" look'], r"\bquevedo\b", MUSICA, ["euge quevedo", "francisco de quevedo"]),
    "Morad": (['"Morad" rapero', '"Morad" rapero concierto'], r"\bmorad\b", MUSICA, ["morad stern"]),
    "Beny Jr": (['"Beny Jr" rapero', '"Beny Jr" concierto'], r"\bbeny jr\b", MUSICA, []),
    "Israel B": (['"Israel B" rapero', '"Israel B" concierto'], r"\bisrael b\b", MUSICA, []),
    "Hoke": (['"Hoke" rapero', '"Hoke" "Tres Creus"'], r"\bhoke\b", MUSICA + ["tres creus", "valencia"], []),
    "Cruz Cafuné": (['"Cruz Cafuné"'], r"cruz cafune", MUSICA, []),
    "orslok": (['"Orslok"', '"Orslok" streamer'], r"\borslok\b", ["streamer", "twitch", "youtuber", "directo", "juego"], []),
    "Shoda Monkas": (['"Shoda Monkas"', '"El Neolandés"'], r"shoda monkas|neolandes", ["streamer", "youtuber", "twitch", "shoda", "monkas"], []),
}

def rss(q, mkt="es-ES"):
    url = "https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": q, "format": "rss", "mkt": mkt})
    req = urllib.request.Request(url, headers={"User-Agent": m.UA, "Accept": "application/rss+xml,text/xml"})
    with urllib.request.urlopen(req, timeout=25) as r:
        raiz = ET.fromstring(r.read(3_000_000))
    out = []
    for it in (e for e in raiz.iter() if e.tag.rsplit("}", 1)[-1] == "item"):
        h = {e.tag.rsplit("}", 1)[-1]: (e.text or "") for e in it}
        link = h.get("link", "")
        real = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url", [link])[0]
        try: fecha = parsedate_to_datetime(h.get("pubDate", ""))
        except Exception: fecha = None
        out.append({"titulo": html.unescape(h.get("title", "")), "desc": html.unescape(re.sub(r"<[^>]+>", " ", h.get("description", ""))), "url": real, "fecha": fecha})
    return out

resumen, todas = {}, []
for nombre, (consultas, rx, ctx, excl) in REF.items():
    items = {}
    for q in consultas:
        try:
            for it in rss(q): items.setdefault(it["url"], it)
        except Exception as e:
            print(f"  {nombre}: consulta fallida {q!r}: {type(e).__name__}", flush=True)
        time.sleep(2)
    en_ventana = [it for it in items.values() if it["fecha"] and AHORA - it["fecha"] <= timedelta(days=DIAS)]
    buenas = []
    for it in en_ventana:
        t = norm(it["titulo"] + " " + it["desc"])
        if re.search(rx, t) and any(c in t for c in ctx) and not any(x in t for x in excl):
            buenas.append(it)
    print(f"[{nombre}] {len(items)} noticias, {len(en_ventana)} en {DIAS} d, {len(buenas)} nombran a la persona con contexto", flush=True)
    fotos = []
    for it in buenas[:10]:
        try:
            final, texto = m.pedir_html(it["url"])
            tit, grupos = m.imagenes_de_pagina(final, texto)
        except Exception as e:
            print(f"   ✖ {urllib.parse.urlparse(it['url']).netloc}: {type(e).__name__}", flush=True); time.sleep(1); continue
        n = 0
        for g in grupos[:25]:
            cid = "pr_" + re.sub(r"\W", "", nombre)[:8] + "_" + m.hashlib.sha1(g[-1].encode()).hexdigest()[:8]
            for u in g:
                try:
                    if m.descargar_imagen(u, OUT / "img" / f"{cid}.jpg", min_lado=400, referer=final, proporcion=(0.4, 2.5)):
                        fotos.append({"id": cid, "ref": nombre, "url_art": final, "titulo": it["titulo"][:100], "fecha": it["fecha"].isoformat() if it["fecha"] else None}); n += 1
                        break
                except Exception:
                    continue
        print(f"   {urllib.parse.urlparse(final).netloc}: {n} imágenes grandes", flush=True)
        time.sleep(1.5)
    pasan = []
    if fotos:
        X = m.embeber_imagenes([OUT / "img" / f"{f['id']}.jpg" for f in fotos], "probe_prensa")
        g = m.puntuacion_foto_real(X)
        orden = np.argsort(-g)
        vistos = []
        for i in orden:
            if g[i] < m.UMBRAL_PUERTA: break
            if any(float(X[i] @ X[j]) >= 0.97 for j in vistos): continue   # misma foto en otra noticia
            vistos.append(i); pasan.append({**fotos[i], "gate": round(float(g[i]), 3)})
    resumen[nombre] = {"noticias": len(items), "en_ventana": len(en_ventana), "nombran": len(buenas), "imagenes": len(fotos), "persona_con_ropa_distintas": len(pasan)}
    todas += pasan
    print(f"   → {len(fotos)} imágenes, {len(pasan)} distintas con persona y ropa", flush=True)
json.dump({"resumen": resumen, "fotos": todas}, open(OUT / "resumen.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\nRESUMEN", json.dumps(resumen, ensure_ascii=False))
