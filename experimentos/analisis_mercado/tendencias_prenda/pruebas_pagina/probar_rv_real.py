"""
Prueba de «Revisar valoraciones» con la base falsa que congela los datos (fakedb_real.js), en móvil (390 px, táctil):
marcar / desmarcar OK, abrir «Entonces es», marcar y quitar alternativas, pasar al apartado siguiente, «No sirve», volver atrás, recargar con lo guardado y seguir editando.
La ronda 1 usa los ids r1-1…; para otra ronda, pasar su prefijo en la variable de entorno RV_PREFIJO (por ejemplo r2-).

Uso:  python3 probar_rv_real.py DIR_CON_fakedb_real.js PAGINA.html [stale]
  (la página se genera con `revisar_valoraciones.py html --salida PAGINA.html`)
"""
import json, os, sys
from playwright.sync_api import sync_playwright
SC, HTML = sys.argv[1], sys.argv[2]
PREF = "v" + os.environ.get("RV_PREFIJO", "r1-")   # ids de los documentos de la base: v<prefijo><n>
STALE = len(sys.argv) > 3 and sys.argv[3] == "stale"
FAKE = open(SC + "/fakedb_real.js", encoding="utf-8").read()
fallos = []
def comprobar(cond, txt):
    print(("  ✓ " if cond else "  ✗ FALLA: ") + txt)
    if not cond: fallos.append(txt)
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 780}, color_scheme="light", has_touch=True, is_mobile=True)
    pg = ctx.new_page()
    errores = []
    pg.on("pageerror", lambda e: errores.append("PAGEERROR " + str(e)))
    pg.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pg.add_init_script(("window.__STALE=true;" if STALE else "") + FAKE)
    pg.goto("file://" + HTML)
    pg.wait_for_selector(".vb", timeout=10000)
    pg.wait_for_timeout(300)
    fv = lambda i: pg.locator(".fv").nth(i)
    vb = lambda i: [pg.locator(".fv").nth(i).locator(".vb").nth(k).get_attribute("aria-pressed") == "true" for k in range(3)]   # ok, mm, no
    marcados = lambda i: pg.locator(".fv").nth(i).locator('.chip[aria-pressed="true"]').count()
    def paso(f, espera=700):
        f(); pg.wait_for_timeout(espera)
    print("modo:", "avisos atrasados" if STALE else "normal")
    paso(lambda: fv(0).locator('.vb[data-r="ok"]').tap());                 comprobar(vb(0) == [True, False, False], "tipo → OK queda marcado tras guardarse")
    paso(lambda: fv(0).locator('.vb[data-r="ok"]').tap());                 comprobar(vb(0) == [False, False, False], "tocar OK otra vez lo deselecciona")
    paso(lambda: fv(0).locator('.vb[data-r="ok"]').tap());                 comprobar(vb(0)[0], "y se puede volver a marcar")
    paso(lambda: fv(2).locator('.vb[data-r="no"]').tap());                 comprobar(vb(2)[2] and fv(2).locator(".chip").count() == 12, "tejido → No abre «Entonces es» (12 opciones)")
    paso(lambda: fv(2).locator(".chip").nth(0).tap());                     comprobar(marcados(2) == 1, "chip de tejido marcado")
    paso(lambda: fv(2).locator(".chip").nth(4).tap());                     comprobar(marcados(2) == 2, "segundo chip de tejido marcado")
    paso(lambda: fv(2).locator(".chip").nth(0).tap());                     comprobar(marcados(2) == 1, "quitar un chip de tejido")
    paso(lambda: fv(3).locator('.vb[data-r="mm"]').tap());                 comprobar(vb(3)[1] and marcados(3) == 0, "luego, forma → Más o menos (siguiente apartado)")
    paso(lambda: fv(3).locator(".chip").nth(1).tap());                     comprobar(marcados(3) == 1, "chip en forma marcado")
    paso(lambda: fv(2).locator('.vb[data-r="mm"]').tap());                 comprobar(vb(2)[1] and marcados(2) == 0, "cambiar tejido de No a Más o menos vacía las marcas anteriores")
    paso(lambda: fv(1).locator('.vb[data-r="ok"]').tap());                 comprobar(vb(1)[0], "estampado → OK")
    guardado = pg.evaluate("window.__docs")
    d = guardado.get(PREF + "1", {})
    comprobar(d.get("r") == {"tipo": "ok", "estampado": "ok", "tejido": "mm", "forma": "mm"}, f"el documento guardado tiene las 4 respuestas: {d.get('r')}")
    comprobar(d.get("alt", {}).get("forma") == ["regular"] and d["alt"]["tejido"] == [], f"y las alternativas: {d.get('alt')}")
    comprobar(pg.inner_text("#ptxt").startswith("1 de"), "el progreso cuenta el recorte hecho: " + pg.inner_text("#ptxt"))
    # siguiente recorte, «No sirve» y volver atrás
    paso(lambda: pg.click("#sig"), 300);                                   comprobar(pg.inner_text(".num").startswith("2 /"), "Siguiente lleva al recorte 2")
    paso(lambda: pg.click("#nos"), 900);                                   comprobar(PREF + "2" in pg.evaluate("window.__docs") and pg.evaluate("window.__docs")[PREF + "2"]["x"] is True, "«No sirve» se guarda")
    paso(lambda: pg.locator(".cell").nth(0).tap(), 300);                   comprobar(vb(0)[0] and vb(1)[0] and vb(2)[1] and vb(3)[1], "volver al recorte 1 muestra lo que marcaste")
    print("  errores de la página:", [e for e in errores if "font" not in e.lower()][:5])
    comprobar(not [e for e in errores if "font" not in e.lower()], "sin errores en la consola")
    # recargar con lo guardado: se restaura y empieza por el primer recorte pendiente
    seed = json.dumps(pg.evaluate("window.__docs"))
    pg2 = ctx.new_page()
    pg2.add_init_script("window.__SEED=" + seed + ";" + FAKE)
    pg2.goto("file://" + HTML)
    pg2.wait_for_selector(".vb", timeout=10000); pg2.wait_for_timeout(400)
    comprobar(pg2.inner_text(".num").startswith("3 /"), "al recargar empieza en el primer pendiente (3): " + pg2.inner_text(".num"))
    comprobar(pg2.inner_text("#ptxt").startswith("2 de"), "y cuenta 2 hechos (uno «no sirve»): " + pg2.inner_text("#ptxt"))
    pg2.locator(".cell").nth(0).tap(); pg2.wait_for_timeout(200)
    est = [[pg2.locator(".fv").nth(i).locator(".vb").nth(k).get_attribute("aria-pressed") == "true" for k in range(3)] for i in range(4)]
    comprobar(est == [[True, False, False], [True, False, False], [False, True, False], [False, True, False]], "el recorte 1 recargado conserva sus respuestas")
    # y se puede seguir editando lo recargado (datos congelados)
    pg2.locator(".fv").nth(0).locator('.vb[data-r="no"]').tap(); pg2.wait_for_timeout(600)
    comprobar(pg2.locator(".fv").nth(0).locator('.vb[data-r="no"]').get_attribute("aria-pressed") == "true", "se puede editar un recorte cargado de la base")
    pg2.locator(".fv").nth(0).locator(".chip").nth(2).tap(); pg2.wait_for_timeout(600)
    comprobar(pg2.locator(".fv").nth(0).locator('.chip[aria-pressed="true"]').count() == 1, "y marcar alternativas en él")
    print("RESULTADO:", "TODO BIEN" if not fallos else f"{len(fallos)} FALLOS")
    b.close()
