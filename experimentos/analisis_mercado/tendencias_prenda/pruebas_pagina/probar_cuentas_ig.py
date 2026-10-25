"""
Prueba de «Cuentas de Instagram» con la base falsa que congela los datos (fakedb_real.js), en móvil (390 px, táctil):
✓ / ✕ y deselección, cambiar estilo y mercado, «Ya la sigo», filtros, «solo las que faltan», recargar con lo guardado y seguir editando, sin desbordes ni errores.
Uso:  [TOT=80] [ESTRELLAS=17] [FOTOS=77] python3 probar_cuentas_ig.py DIR_CON_fakedb_real.js PAGINA.html [capturas_dir]
"""
import json, os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
SC, HTML = sys.argv[1], sys.argv[2]
CAP = sys.argv[3] if len(sys.argv) > 3 else None
FAKE = open(SC + "/fakedb_real.js", encoding="utf-8").read()
# el esqueleto de publicación añade el meta viewport; en local se envuelve igual para medir bien los 390 px
envuelta = Path(HTML).with_name("_envuelta.html")
envuelta.write_text('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>' + open(HTML, encoding="utf-8").read() + "</body></html>", encoding="utf-8")
fallos = []
def comprobar(cond, txt):
    print(("  ✓ " if cond else "  ✗ FALLA: ") + txt)
    if not cond: fallos.append(txt)
with sync_playwright() as p:
    b = p.chromium.launch()
    for esquema in ("light", "dark"):
        ctx = b.new_context(viewport={"width": 390, "height": 780}, color_scheme=esquema, has_touch=True, is_mobile=True)
        pg = ctx.new_page()
        errores = []
        pg.on("pageerror", lambda e: errores.append("PAGEERROR " + str(e)))
        pg.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
        pg.add_init_script(FAKE)
        pg.goto("file://" + str(envuelta))
        pg.wait_for_selector(".card", timeout=10000); pg.wait_for_timeout(300)
        print("== esquema", esquema)
        n = pg.locator(".card").count()
        TOT = int(os.environ.get("TOT", "75"))
        EST = int(os.environ.get("ESTRELLAS", "14"))  # cuentas con ★ en la propuesta
        comprobar(n == TOT, f"se pintan las {TOT} cuentas ({n})")
        comprobar(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "sin desborde horizontal en 390 px")
        if os.environ.get("FOTOS"):
            esperadas = int(os.environ["FOTOS"])
            r_img = pg.evaluate("async()=>{const L=[...document.querySelectorAll('.fotos img')];L.forEach(i=>{i.loading='eager'});await new Promise(r=>setTimeout(r,1500));return [L.length,L.filter(i=>i.complete&&i.naturalWidth>0).length]}")
            comprobar(r_img[0] == esperadas and r_img[1] == esperadas, f"las {esperadas} tiras de fotos se pintan y cargan ({r_img})")
            comprobar(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "sin desborde horizontal con las fotos")
        comprobar(pg.inner_text("#ptxt") == f"0 de {TOT}", f"progreso inicial 0 de {TOT}")
        if CAP and esquema == "light":
            pg.screenshot(path=f"{CAP}/cuentas_{esquema}_arriba.png")
        c0 = pg.locator(".card").first
        u0 = c0.get_attribute("data-u")
        c0.locator('.rb[data-a="si"]').tap(); pg.wait_for_timeout(700)
        comprobar(pg.locator(".card").first.locator('.rb[data-a="si"]').get_attribute("aria-pressed") == "true", f"✓ Fuente marcado en @{u0}")
        d = pg.evaluate("window.__docs")[u0]
        comprobar(d.get("r") == "si" and d.get("u") == u0, f"y guardado en la base: {d}")
        comprobar(pg.inner_text("#ptxt") == f"1 de {TOT}", f"el progreso cuenta 1 de {TOT}")
        pg.locator(".card").first.locator('.rb[data-a="no"]').tap(); pg.wait_for_timeout(600)
        comprobar(pg.evaluate("window.__docs")[u0]["r"] == "no", "tocar ✕ cambia la respuesta a no")
        pg.locator(".card").first.locator('.rb[data-a="no"]').tap(); pg.wait_for_timeout(600)
        comprobar(pg.evaluate("window.__docs")[u0]["r"] == "", "tocar ✕ otra vez la quita")
        est0 = pg.locator(".card").first.locator('button[data-a="est"]').inner_text()
        pg.locator(".card").first.locator('button[data-a="est"]').tap(); pg.wait_for_timeout(600)
        est1 = pg.locator(".card").first.locator('button[data-a="est"]').inner_text()
        comprobar(est0 != est1 and pg.evaluate("window.__docs")[u0]["e"] != "", f"cambiar estilo: {est0} → {est1}")
        m0 = pg.locator(".card").first.locator('button[data-a="mkt"]').inner_text()
        pg.locator(".card").first.locator('button[data-a="mkt"]').tap(); pg.wait_for_timeout(600)
        m1 = pg.locator(".card").first.locator('button[data-a="mkt"]').inner_text()
        comprobar(m0 != m1 and pg.evaluate("window.__docs")[u0]["m"] == m1, f"cambiar mercado: {m0} → {m1}")
        pg.locator(".card").first.locator('input[data-a="f"]').check(); pg.wait_for_timeout(600)
        comprobar(pg.evaluate("window.__docs")[u0]["f"] is True, "«Ya la sigo» guardado")
        # filtros
        pg.locator('.fch[data-f="urbano"]').tap(); pg.wait_for_timeout(200)
        nu = pg.locator(".card").count()
        comprobar(0 < nu < TOT and all(pg.locator(".card").nth(i).locator('button[data-a="est"]').inner_text() == "Urbano" for i in range(nu)), f"el filtro Urbano deja {nu} cuentas, todas urbanas")
        pg.locator('.fch[data-f="todas"]').tap(); pg.wait_for_timeout(200)
        pg.locator("#solo").check(); pg.wait_for_timeout(200)
        comprobar(pg.locator(".card").count() in (TOT - 1, TOT), f"«solo las que faltan» oculta las respondidas ({pg.locator('.card').count()})")
        pg.locator("#solo").uncheck(); pg.wait_for_timeout(200)
        pg.locator('.fch[data-f="rec"]').tap(); pg.wait_for_timeout(200)
        nr = pg.locator(".card").count()
        comprobar(nr == EST and pg.locator(".card .star").count() == nr, f"el filtro ★ deja {nr} cuentas, todas con estrella")
        pg.locator('.fch[data-f="todas"]').tap(); pg.wait_for_timeout(200)
        if CAP and esquema == "dark":
            pg.screenshot(path=f"{CAP}/cuentas_{esquema}_arriba.png")
        # sin las tiras de fotos en local (FOTOS sin definir) los ficheros f/*.jpg no existen: no cuenta como error
        errs = [e for e in errores if "font" not in e.lower() and (os.environ.get("FOTOS") or "ERR_FILE_NOT_FOUND" not in e)]
        comprobar(not errs, "sin errores en la consola: " + str(errs[:3]))
        # recargar con lo guardado
        seed = json.dumps(pg.evaluate("window.__docs"))
        pg2 = ctx.new_page()
        pg2.add_init_script("window.__SEED=" + seed + ";" + FAKE)
        pg2.goto("file://" + str(envuelta)); pg2.wait_for_selector(".card", timeout=10000); pg2.wait_for_timeout(500)
        c = pg2.locator(f'.card[data-u="{u0}"]')
        comprobar(c.locator('button[data-a="est"]').inner_text() == est1 and c.locator('button[data-a="mkt"]').inner_text() == m1 and c.locator('input[data-a="f"]').is_checked(), "al recargar se restauran estilo, mercado y «Ya la sigo»")
        c.locator('.rb[data-a="si"]').tap(); pg2.wait_for_timeout(600)
        comprobar(pg2.evaluate("window.__docs")[u0]["r"] == "si", "y se puede seguir editando lo cargado de la base (datos congelados)")
        # botón «Aceptar las que faltan» de mi propuesta ★: marca ✓ sin pisar lo ya respondido
        for nombre, seed3 in (("sin respuestas previas", {}), ("con un ✕ previo", {"britishcountryheritage": {"u": "britishcountryheritage", "r": "no", "f": False, "e": "", "m": "", "t": "x"}})):
            pg3 = ctx.new_page()
            pg3.add_init_script("window.__SEED=" + json.dumps(seed3) + ";" + FAKE)
            pg3.goto("file://" + str(envuelta)); pg3.wait_for_selector(".card", timeout=10000); pg3.wait_for_timeout(400)
            comprobar(pg3.locator("#bulk").count() == 0, f"fuera del filtro ★ no hay botón de aceptar ({nombre})")
            pg3.locator('.fch[data-f="rec"]').tap(); pg3.wait_for_timeout(300)
            falta = EST - len(seed3)
            comprobar(pg3.locator("#bulk").count() == 1 and str(falta) in pg3.locator("#bulk").inner_text(), f"en el filtro ★ aparece «Aceptar las {falta} que faltan» ({nombre})")
            pg3.locator("#bulk").tap(); pg3.wait_for_timeout(1800)
            docs3 = pg3.evaluate("window.__docs")
            si = [k for k, d in docs3.items() if d.get("r") == "si"]
            comprobar(len(si) == falta and all(pg3.locator(f'.card[data-u="{k}"] .star').count() == 1 for k in si), f"se guardan {falta} ✓ y solo de cuentas ★ ({len(si)})")
            if seed3:
                comprobar(docs3["britishcountryheritage"]["r"] == "no", "no pisa el ✕ que ya había")
            comprobar(pg3.locator("#bulk").count() == 0 and pg3.locator('.card[data-r="si"], .card[data-r="no"]').count() == EST, f"el botón desaparece y las {EST} quedan respondidas")
            comprobar(pg3.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "sin desborde horizontal con el bloque nuevo")
            pg3.close()
        ctx.close()
    print("RESULTADO:", "TODO BIEN" if not fallos else f"{len(fallos)} FALLOS")
    b.close()
envuelta.unlink(missing_ok=True)
