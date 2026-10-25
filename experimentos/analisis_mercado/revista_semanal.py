#!/usr/bin/env python3
"""
Revista semanal de tendencias de prenda (11 de octubre de 2026, a petición de Víctor: «algo como una revista semanal» con los cambios del mercado, el acierto y lo que ha considerado).

Lee lo que deja `tendencia_prenda.py` en `tendencia_datos/` (informe, fotos, prendas, fuentes, fiabilidad, comparación geek-urbano) y compone un correo HTML con aspecto de revista:
  01 Lo que se lleva (por estilo y mercado, con margen y confianza de cada cifra y fotos de ejemplo) · 02 Qué ha cambiado (4 semanas frente a las 4 anteriores, y las novedades de la semana)
  03 Geek frente a urbano · 04 Cuánto fiarte (acierto medido por Víctor y señales internas) · 05 Qué ha considerado (fuentes, filtros y método).
Es HTML de correo (tablas, estilos en línea, sin imágenes remotas): las fotos van incrustadas por CID y el HTML se mantiene por debajo de los ~100 KB que Gmail recorta.

Uso:
  python3 revista_semanal.py generar [--salida DIR] [--as-of AAAA-MM-DD] [--sin-fotos]    escribe revista.html, revista_vista.html (fotos incrustadas, para abrir en un navegador) y revista.txt
  python3 revista_semanal.py enviar  [--salida DIR] [--as-of …] [--sin-fotos]              lo genera y lo manda (variables: SMTP_USER, SMTP_PASSWORD, MAIL_TO; opcional SMTP_HOST, SMTP_PORT, MAIL_FROM)
  python3 revista_semanal.py aviso-fallo --paso TEXTO [--enlace URL]                        correo corto cuando la tarea semanal falla
Variables: TENDENCIA_DATOS (carpeta de datos, por defecto tendencia_datos/).
"""
from __future__ import annotations

import argparse
import base64
import collections
import datetime as dt
import hashlib
import html
import io
import json
import math
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import tendencia_prenda as tp  # noqa: E402  (FAMILIA, valida, temporada, MIN_FOTOS…)

TD = tp.TD
PRIMERA = dt.date(2026, 10, 12)      # lunes de la primera edición programada (Nº 1)
VENTANA = 28                          # días de «las últimas semanas» frente a «las anteriores»
MIN_VENTANA = 8                       # fotos mínimas en cada ventana para compararlas
LADO_FOTO = 112                       # miniaturas de prendas (px)
MAX_HTML = 95_000                     # Gmail recorta el HTML a partir de ~102 KB

ESTILO = tp.NOMBRE_ESTILO
MERCADO = {"ES": "España", "US": "EEUU", "Biblioteca": "tus fotos aprobadas"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
NOMBRE_TEMP = lambda t: {"muestra": "muestra de referencia"}.get(t, t.replace("OI ", "otoño-invierno ").replace("PV ", "primavera-verano "))

# paleta editorial (papel, tinta, dos acentos por estilo)
INK, PAPEL, TARJETA, LINEA, SUAVE = "#1d1b16", "#f1ebdf", "#fffdf8", "#ddd4c3", "#6b655a"
COL = {"urbano": "#b5441f", "geek": "#6b4ba1", "clasico": "#2f4a6b", "old_money": "#4d6b3a", "lujo": "#a37b16", "bohemio": "#b0527a", "convencional": "#5c6670"}
OK, AVISO, MAL, AZUL = "#2e7d4f", "#a86a10", "#a8433a", "#2f4a6b"
SERIF = "Georgia,'Times New Roman',Times,serif"
SANS = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
esc = html.escape


# ---------------------------------------------------------------- utilidades
def pct(x: float, d: int = 0) -> str:
    return (f"{100 * x:.{d}f}".replace(".", ",")) + " %"


def num(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def mezcla(hex_: str, k: float) -> str:
    """El color mezclado con blanco (k = 1 el color, 0 blanco)."""
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    f = lambda c: round(255 - (255 - c) * k)
    return f"#{f(r):02x}{f(g):02x}{f(b):02x}"


def leer(nombre: str, defecto=None):
    f = TD / nombre
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else defecto


def fecha_iso(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0)) / d
    return max(0.0, c - h), min(1.0, c + h)


def p_dos_proporciones(k1: int, n1: int, k2: int, n2: int) -> float:
    """p de dos colas de la diferencia de dos proporciones (aproximación normal con proporción conjunta)."""
    if n1 == 0 or n2 == 0:
        return 1.0
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = abs(k1 / n1 - k2 / n2) / se
    return math.erfc(z / math.sqrt(2))


def edicion(as_of: dt.date) -> tuple[int, int, str]:
    """(número de edición, semana ISO, fecha larga) del lunes de esa semana."""
    # de sábado a domingo es la edición del lunes siguiente (una prueba manual el domingo por la noche cuenta para ese lunes)
    lunes = as_of - dt.timedelta(days=as_of.weekday()) if as_of.weekday() < 5 else as_of + dt.timedelta(days=7 - as_of.weekday())
    n = max(1, (lunes - PRIMERA).days // 7 + 1)
    return n, lunes.isocalendar()[1], f"{DIAS[lunes.weekday()]} {lunes.day} de {MESES[lunes.month - 1]} de {lunes.year}"


# ---------------------------------------------------------------- piezas de HTML
def etiqueta_conf(c: str | None) -> str:
    if not c:
        return ""
    col = {"alta": OK, "media": AZUL, "baja": MAL}[c]
    return f'<span style="font:700 10px {SANS};letter-spacing:.06em;text-transform:uppercase;color:{col};border:1px solid {col};border-radius:9px;padding:1px 6px;white-space:nowrap">confianza {c}</span>'


def chip_corto(c: str | None) -> str:
    if not c:
        return ""
    col = {"alta": OK, "media": AZUL, "baja": MAL}[c]
    return f'<span style="font:700 11px {SANS};letter-spacing:.04em;text-transform:uppercase;color:{col}">{c}</span>'


def barra(cuota: float, lo: float, hi: float, color: str, escala: float) -> str:
    """Barra de una cuota: oscuro hasta el mínimo, tono medio hasta la cifra (marca negra) y tono claro hasta el máximo (margen del 95 %)."""
    a, b, c = lo / escala * 100, max(cuota - lo, 0) / escala * 100, max(hi - cuota, 0) / escala * 100
    resto = max(100 - a - b - c, 0)
    celda = lambda w, bg, extra="": f'<td width="{w:.1f}%" height="8" bgcolor="{bg}" style="font-size:0;line-height:0;{extra}">&nbsp;</td>' if w > 0.05 else ""
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse"><tr>'
            + celda(a, color) + celda(b, mezcla(color, .55), f"border-right:2px solid {INK}") + celda(c, mezcla(color, .22)) + celda(resto, "#e9e2d3") + "</tr></table>")


def barra_div(dif: float, lo: float, hi: float, escala: float, col_pos: str | None = None, col_neg: str | None = None) -> str:
    """Barra que sale del centro: a la derecha, más frecuente en el primer grupo (geek); a la izquierda, en el segundo (urbano); el tono claro llega hasta el extremo del margen del 95 %."""
    col = (col_pos or COL["geek"]) if dif >= 0 else (col_neg or COL["urbano"])
    w_main = abs(dif) / escala * 50
    w_ext = (max(hi - dif, 0) if dif >= 0 else max(-lo - abs(dif), 0)) / escala * 50
    resto = max(50 - w_main - w_ext, 0)
    fondo = "#e9e2d3"
    c = lambda w, bg: f'<td width="{w:.1f}%" height="9" bgcolor="{bg}" style="font-size:0;line-height:0">&nbsp;</td>' if w > 0.05 else ""
    if dif >= 0:
        izq, der = c(50, fondo), c(w_main, col) + c(w_ext, mezcla(col, .25)) + c(resto, fondo)
    else:
        izq, der = c(resto, fondo) + c(w_ext, mezcla(col, .25)) + c(w_main, col), c(50, fondo)
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse"><tr>{izq}'
            f'<td width="2" bgcolor="{INK}" style="font-size:0;line-height:0">&nbsp;</td>{der}</tr></table>')


def seccion(n: str, titulo: str, entradilla: str = "") -> str:
    ent = f'<p style="margin:6px 0 0;font:15px/1.5 {SANS};color:{SUAVE}">{entradilla}</p>' if entradilla else ""
    return (f'<tr><td style="padding:34px 28px 6px"><div style="font:700 12px {SANS};letter-spacing:.14em;color:{COL["urbano"]}">{n}</div>'
            f'<h2 style="margin:2px 0 0;font:700 25px/1.2 {SERIF};color:{INK}">{titulo}</h2>{ent}'
            f'<div style="height:2px;background:{INK};margin-top:12px;font-size:0;line-height:0">&nbsp;</div></td></tr>')


def caja(contenido: str, pad: str = "10px 28px") -> str:
    return f'<tr><td style="padding:{pad};font:15px/1.55 {SANS};color:{INK}">{contenido}</td></tr>'


def nota(texto: str) -> str:
    return f'<div style="font:13px/1.5 {SANS};color:{SUAVE}">{texto}</div>'


# ---------------------------------------------------------------- datos
def miniatura(fid: str, idx: int, prendas: dict) -> bytes | None:
    """JPEG cuadrado centrado en una prenda (su recuadro y un 10 % más); None si la foto no está en la caché."""
    ruta = tp.m.IMG / f"{fid}.jpg"
    if not ruta.exists():
        return None
    try:
        x1, y1, x2, y2 = prendas[fid]["prendas"][idx]["caja"]
        im = Image.open(ruta).convert("RGB")
        W, H = im.size
        lado = min(max(x2 - x1, y2 - y1) * 1.1, W, H)
        izq = min(max(0, (x1 + x2) / 2 - lado / 2), W - lado)
        arr = min(max(0, (y1 + y2) / 2 - lado / 2), H - lado)
        c = im.crop((int(izq), int(arr), int(izq + lado), int(arr + lado))).resize((LADO_FOTO * 2, LADO_FOTO * 2), Image.LANCZOS)   # el doble de píxeles para pantallas nítidas
        b = io.BytesIO()
        c.save(b, "JPEG", quality=70, optimize=True)
        return b.getvalue()
    except Exception:  # noqa: BLE001 -- una miniatura que falla no tumba la revista
        return None


class Fotos:
    """Reúne las miniaturas de la revista con su identificador de contenido (cid)."""

    def __init__(self, activo: bool, fotos_d: dict | None = None):
        self.activo, self.items, self.fotos_d = activo, {}, fotos_d

    def cid(self, fid: str, idx: int, prendas: dict) -> str | None:
        if not self.activo:
            return None
        clave = f"{fid}-{idx}"
        if clave not in self.items:
            if self.fotos_d is not None:
                tp.asegurar_imagen(fid, self.fotos_d)   # en la nube la caché de fotos empieza vacía: se vuelve a bajar la de los ejemplos
            b = miniatura(fid, idx, prendas)
            self.items[clave] = b
        if self.items[clave] is None:
            return None
        return "f" + hashlib.sha1(clave.encode()).hexdigest()[:10]

    def bytes_de(self, cid: str) -> bytes | None:
        for clave, b in self.items.items():
            if b is not None and "f" + hashlib.sha1(clave.encode()).hexdigest()[:10] == cid:
                return b
        return None


def tira_fotos(ejemplos: list[tuple[str, int, str]], fotos: Fotos, prendas: dict, columnas: int = 4) -> str:
    """Una fila de miniaturas con su pie que se adapta al ancho (en el móvil se encogen). ejemplos = [(foto, índice, pie)]."""
    celdas = []
    for fid, i, pie in ejemplos[:columnas]:
        cid = fotos.cid(fid, i, prendas)
        if not cid:
            continue
        celdas.append(f'<td width="{100 // columnas}%" valign="top" align="left" style="padding:0 6px 0 0"><img src="cid:{cid}" width="{LADO_FOTO}" height="{LADO_FOTO}" alt="{esc(pie)}" '
                      f'style="display:block;border:0;border-radius:4px;background:#eee8dc;width:100%;max-width:{LADO_FOTO}px;height:auto"><div style="font:11px/1.3 {SANS};color:{SUAVE};padding-top:3px">{esc(pie)}</div></td>')
    if not celdas:
        return ""
    celdas += [f'<td width="{100 // columnas}%">&nbsp;</td>'] * (columnas - len(celdas))
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;table-layout:fixed"><tr>{"".join(celdas)}</tr></table>'


def grupo_actual(informe: dict, estilo: str, mercado: str, temporada: str) -> dict | None:
    cand = [g for g in informe["grupos"] if g["estilo"] == estilo and g["mercado"] == mercado]
    exacto = [g for g in cand if g["temporada"] == temporada]
    return (exacto or sorted(cand, key=lambda g: -g["fotos_con_prenda"]) or [None])[0]


def bloque_grupo(g: dict, fotos: Fotos, prendas: dict, hoy_temp: str) -> str:
    col = COL[g["estilo"]]
    filas = [f for f in g["prendas"] if f["cuota"] is not None][:5]
    cab = (f'<div style="font:700 13px {SANS};letter-spacing:.08em;text-transform:uppercase;color:{col}">{ESTILO[g["estilo"]]} · {MERCADO.get(g["mercado"], g["mercado"])}</div>'
           f'<div style="font:700 19px/1.25 {SERIF};margin:2px 0 2px">{esc(NOMBRE_TEMP(g["temporada"]).capitalize())}</div>'
           + nota(f'{g["fotos_con_prenda"]} fotos con prenda visible (pesan como {str(g["fotos_efectivas"]).replace(".", ",")} independientes). Fuentes: '
                  + esc(", ".join(f"{k} {v}" for k, v in list(g["fuentes"].items())[:5])) + "."))
    if not g.get("etiquetadas_con_modelo_grande", True):
        cab += nota(f'<b style="color:{AVISO}">Ojo:</b> algunas prendas de este grupo aún no las ha etiquetado el modelo grande y usan el tipo de CLIP, menos fiable; se corrige en cuanto termina esa etapa.')
    if g["temporada"] != hoy_temp and g["temporada"] != "muestra":
        cab += nota(f'<b style="color:{AVISO}">Ojo:</b> no hay fotos suficientes de {esc(NOMBRE_TEMP(hoy_temp))}; se enseña {esc(NOMBRE_TEMP(g["temporada"]))}.')
    if not filas:
        return cab + nota("Ningún tipo de prenda llega a las 5 fotos necesarias para enseñar una cifra.")
    escala = max(f["ic"][1] for f in filas) * 1.02
    cuerpo = []
    for f in filas:
        cuerpo.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px"><tr>'
            f'<td style="font:600 15px {SANS}">{esc(f["tipo"])} {etiqueta_conf(f["confianza"])}</td>'
            f'<td align="right" style="font:700 16px {SERIF};white-space:nowrap">{pct(f["cuota"])}</td></tr>'
            f'<tr><td colspan="2" style="padding-top:4px">{barra(f["cuota"], f["ic"][0], f["ic"][1], col, escala)}</td></tr>'
            f'<tr><td colspan="2" style="font:12px {SANS};color:{SUAVE};padding-top:3px">{f["fotos"]} fotos · margen del 95 %: de {pct(f["ic"][0])} a {pct(f["ic"][1])}'
            + (f' · <span style="color:{MAL}">{esc(f["aviso"])}</span>' if f.get("aviso") else "") + '</td></tr></table>')
    ejemplos = []
    for ronda in range(3):   # reparte los ejemplos entre los tipos: el primero de cada uno, luego el segundo…
        for f in filas[:4]:
            if len(f["ejemplos"]) > ronda and len(ejemplos) < 4:
                ejemplos.append((f["ejemplos"][ronda][0], f["ejemplos"][ronda][1], f["tipo"]))
    atr = []
    for c, et in (("forma", "Forma"), ("estampado", "Estampado"), ("tejido", "Tejido")):
        a = (g.get("atributos") or {}).get(c)
        if a:
            top = list(a["reparto"].items())[:3]
            atr.append(f'<b>{et}</b> ({etiqueta_conf(a["confianza"])}): ' + " · ".join(f'{esc(k)} {pct(v / a["n"])}' for k, v in top))
    cols = list((g.get("colores") or {}).items())[:4]
    extra = ""
    if atr:
        extra += f'<div style="font:13px/1.7 {SANS};margin-top:12px;color:{INK}">' + "<br>".join(atr) + "</div>"
    if cols:
        extra += f'<div style="font:12px/1.5 {SANS};color:{SUAVE};margin-top:6px">Colores más vistos: ' + ", ".join(f"{esc(k)} ({v})" for k, v in cols) + " · el color tiende a «negro»: confianza baja.</div>"
    return cab + "".join(cuerpo) + tira_fotos(ejemplos, fotos, prendas) + extra


# ---------------------------------------------------------------- cambios
def comparar_ventanas(as_of: dt.datetime, fotos_d: dict, prendas: dict) -> tuple[list[dict], dict]:
    """Últimas VENTANA días frente a los VENTANA anteriores, por estilo y mercado (solo mercados reales): cuota de fotos por tipo, con p de la diferencia."""
    g = {}
    for k, v in fotos_d.items():
        if v.get("descartada") or k not in prendas or v["mercado"] not in ("ES", "US") or not v.get("fecha"):
            continue
        edad = (as_of - fecha_iso(v["fecha"])).days
        if edad < 0 or edad >= 2 * VENTANA:
            continue
        tipos = {p["tipo"] for p in prendas[k]["prendas"] if tp.valida(p)}
        if not tipos:
            continue
        w = g.setdefault((v["estilo"], v["mercado"]), {"A": [0, collections.Counter()], "B": [0, collections.Counter()]})["A" if edad < VENTANA else "B"]
        w[0] += 1
        w[1].update(tipos)
    cambios, resumen = [], {}
    for (est, mer), w in sorted(g.items()):
        nA, nB = w["A"][0], w["B"][0]
        resumen[(est, mer)] = (nA, nB)
        if nA < MIN_VENTANA or nB < MIN_VENTANA:
            continue
        for t in set(w["A"][1]) | set(w["B"][1]):
            cA, cB = w["A"][1][t], w["B"][1][t]
            if cA + cB < 5:
                continue
            cambios.append({"estilo": est, "mercado": mer, "tipo": t, "A": cA / nA, "B": cB / nB, "nA": nA, "nB": nB, "dif": cA / nA - cB / nB, "p": p_dos_proporciones(cA, nA, cB, nB)})
    cambios.sort(key=lambda c: c["p"])
    return cambios, resumen


def novedades(fotos_d: dict, estado: dict, as_of: dt.datetime) -> dict:
    """Lo que entró en los últimos 7 días (fecha de captura) y el estado de cada fuente."""
    sem = as_of - dt.timedelta(days=7)
    nuevas = [v for v in fotos_d.values() if v.get("capturada") and fecha_iso(v["capturada"]) >= sem]
    utiles = [v for v in nuevas if not v.get("descartada")]
    motivos = collections.Counter(v["descartada"] for v in nuevas if v.get("descartada"))
    por_fuente = collections.Counter((v.get("referente") or "Biblioteca") for v in utiles)
    errores = [(e["referente"], e["tipo"], e["error"]) for e in estado.values() if e.get("error") and e.get("ultima") and fecha_iso(e["ultima"]) >= sem]
    ultima = max((fecha_iso(e["ultima"]) for e in estado.values() if e.get("ultima")), default=None)
    return {"nuevas": len(nuevas), "utiles": len(utiles), "motivos": motivos, "por_fuente": por_fuente, "errores": errores, "ultima": ultima}


def fp(x: float) -> str:
    return f"{x:.3f}".replace(".", ",")


def tarjetas_estilos(p7: dict) -> list[str]:
    """Una tarjeta por estilo: su perfil de tipos de prenda y lo que lo distingue del resto de estilos (muestra de referencia de la Biblioteca)."""
    dims = {d["dimension"]: d for d in p7["dimensiones"]}
    out = []
    sep_ok = [f'{k} (p = {fp(dims[k]["global"]["p"])})' for k in ("tipo", "forma", "tejido", "estampado", "familia") if k in dims and dims[k]["global"]["p"] < 0.05]
    sin = [k for k in ("tipo", "forma", "tejido", "estampado", "familia") if k in dims and dims[k]["global"]["p"] >= 0.05]
    out.append(caja(nota("<b>Los estilos se distinguen por:</b> " + (esc(", ".join(sep_ok)) if sep_ok else "ninguna dimensión, con estos datos") + "."
                         + (" No se distinguen por: " + esc(", ".join(sin)) + "." if sin else "")), "14px 28px 0"))
    for e in p7["estilos_con_datos"]:
        col = COL.get(e, INK)
        ejemplo = next((d["estilos"][e] for d in dims.values() if e in d["estilos"]), None)
        if not ejemplo:
            continue
        perfil = (dims.get("tipo", {}).get("perfil") or {}).get(e, [])[:3]
        rasgos = sorted(((c["dif"], dn, c) for dn, d in dims.items() if e in d["estilos"] for c in d["estilos"][e]["categorias"] if c["q"] < 0.10 and c["dif"] > 0), key=lambda t: -t[0])[:4]
        menos = sorted(((c["dif"], dn, c) for dn, d in dims.items() if e in d["estilos"] for c in d["estilos"][e]["categorias"] if c["q"] < 0.10 and c["dif"] < 0), key=lambda t: t[0])[:2]
        cuerpo = (f'<div style="font:700 13px {SANS};letter-spacing:.08em;text-transform:uppercase;color:{col}">{esc(ESTILO[e])}</div>'
                  + nota(f'{ejemplo["prendas"]} prendas en {ejemplo["fotos"]} fotos.' + (" Lo más frecuente: " + esc(", ".join(f"{k.lower()} {pct(v)}" for k, v in perfil)) + "." if perfil else "")))
        if rasgos:
            escala = max(max(abs(c["ic"][0]), abs(c["ic"][1]), abs(c["dif"])) for _, _, c in rasgos) * 1.05
            filas_ = "".join(
                f'<tr><td style="padding:8px 0 0;font:600 14px {SANS}">{esc(c["categoria"])} <span style="font:12px {SANS};color:{SUAVE};font-weight:400">({dn})</span></td>'
                f'<td align="right" style="padding:8px 0 0;font:12px {SANS};color:{SUAVE};white-space:nowrap">{pct(c["estilo"])} frente a {pct(c["resto"])} en el resto</td></tr>'
                f'<tr><td colspan="2" style="padding-top:3px">{barra_div(c["dif"], c["ic"][0], c["ic"][1], escala, col, SUAVE)}</td></tr>' for _, dn, c in rasgos)
            cuerpo += f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{filas_}</table>'
        else:
            cuerpo += nota("Ningún rasgo se distingue con seguridad del resto de estilos.")
        if menos:
            cuerpo += nota("Menos que el resto: " + esc(", ".join(f'{c["categoria"]} ({dn}, {round(100 * c["dif"]):+d} pts)' for _, dn, c in menos)) + ".")
        out.append(caja(f'<div style="border-left:4px solid {col};padding:2px 0 8px 12px">{cuerpo}</div>', "16px 28px 0"))
    return out


# ---------------------------------------------------------------- composición
def componer(as_of: dt.date, con_fotos: bool) -> tuple[str, str, Fotos, dict]:
    informe, fiab = leer("informe.json"), leer("fiabilidad.json", {})
    sep, fotos_d, prendas = leer("separacion_estilos.json"), leer("fotos.json", {}), leer("prendas.json", {})
    estado, fuentes_cfg = leer("estado.json", {}), json.loads(tp.FUENTES.read_text(encoding="utf-8"))["fuentes"]
    ahora = dt.datetime.combine(as_of, dt.time(12, 0), tzinfo=dt.timezone.utc)
    nº, semana, fecha_larga = edicion(as_of)
    hoy_temp = tp.temporada(ahora.isoformat())
    fotos = Fotos(con_fotos, fotos_d)
    info = {"edicion": nº, "semana": semana}

    # --- elegir los bloques de la sección 01: un grupo por estilo y mercado reales
    bloques, vacios = [], []
    con_fuentes = {s_["estilo"] for s_ in fuentes_cfg}
    sin_fuentes = [e for e in tp.NOMBRE_ESTILO if e not in con_fuentes]
    for est in [e for e in tp.NOMBRE_ESTILO if e in con_fuentes]:
        for mer in ("ES", "US"):
            g = grupo_actual(informe, est, mer, hoy_temp)
            if g and any(f["cuota"] is not None for f in g["prendas"]):
                bloques.append(g)
            else:
                vacios.append((est, mer, g["fotos_con_prenda"] if g else 0))
    bloques.sort(key=lambda g: -g["fotos_con_prenda"])
    portada = bloques[0] if bloques else None

    # --- titular de portada
    if portada:
        top = [f for f in portada["prendas"] if f["cuota"] is not None][:2]
        nombres = " y ".join(f["tipo"].lower() for f in top)
        titular = f'{ESTILO[portada["estilo"]]} en {MERCADO[portada["mercado"]]}: {nombres} {"encabezan" if len(top) > 1 else "encabeza"} el {NOMBRE_TEMP(portada["temporada"])}'
        deck = (f'La cifra se apoya en {portada["fotos_con_prenda"]} fotos de {len(portada["fuentes"])} fuentes. '
                + ("Es una muestra pequeña: el margen es amplio y conviene leerlo como orientación." if portada["fotos_con_prenda"] < 30 else "Es una muestra con volumen suficiente para una lectura firme."))
    else:
        titular, deck = "Primera edición: todavía no hay fotos suficientes para una cifra", "Cuando haya cinco fotos por tipo de prenda, aparecerán aquí."

    # --- 30 segundos
    nov = novedades(fotos_d, estado, ahora)
    cambios, resumen_v = comparar_ventanas(ahora, fotos_d, prendas)
    claros = [c for c in cambios if c["p"] < 0.05]
    seg = []
    seg.append(f'<b>Fotos:</b> {num(sum(1 for v in fotos_d.values() if not v.get("descartada")))} fotos útiles acumuladas'
               + ("; es la edición inaugural: todo lo reunido hasta hoy cuenta como novedad." if nº == 1 else
                  f'; esta semana entraron {nov["utiles"]} nuevas ({nov["nuevas"]} vistas).' if nov["ultima"] and (ahora - nov["ultima"]).days <= 8 else "; esta semana no hubo cosecha nueva."))
    for g in bloques[:2]:
        top = [f for f in g["prendas"] if f["cuota"] is not None][:3]
        seg.append(f'<b>{ESTILO[g["estilo"]]} · {MERCADO[g["mercado"]]}:</b> ' + ", ".join(f'{esc(f["tipo"].lower())} {pct(f["cuota"])}' + (" (dudosa)" if f.get("aviso") else "") for f in top) + ".")
    seg.append("<b>Cambios:</b> " + (f'{len(claros)} que aguantan el azar (4 semanas frente a las 4 anteriores).' if claros else "ninguno que se distinga del azar con las fotos que hay."))
    p7 = (sep or {}).get("solo_biblioteca", {}).get("por_estilo")
    multi = bool(p7 and len(p7["estilos_con_datos"]) > 2)
    if multi:
        d = {x["dimension"]: x["global"]["p"] for x in p7["dimensiones"]}
        sep_ok = [k for k in ("tipo", "forma", "tejido", "estampado") if d.get(k, 1) < 0.05]
        seg.append(f'<b>{len(p7["estilos_con_datos"])} estilos:</b> ' + (f'se distinguen por {", ".join(sep_ok)}' if sep_ok else "no se distinguen con estos datos"))
    elif sep:
        b = sep["solo_biblioteca"]
        d = {x["dimension"]: x["global"]["p"] for x in b["dimensiones"]}
        sep_ok = [k for k in ("forma", "tejido", "tipo") if d.get(k, 1) < 0.05]
        seg.append(f'<b>Geek frente a urbano:</b> se distinguen en {", ".join(sep_ok)}' if sep_ok else "<b>Geek frente a urbano:</b> no se distinguen con estos datos")
    r = fiab.get("vlm_tipo", {}).get("revision")
    if r:
        seg[-1] += "."
        seg.append(f'<b>Acierto:</b> en tu última revisión diste por buena la valoración del modelo en el {pct(r["aceptable"] / r["n"])} del tipo de prenda (a ciegas, {pct(fiab["vlm_tipo"]["acierto"] / fiab["vlm_tipo"]["n"])}).')
    resumen = "".join(f'<li style="margin:0 0 6px">{s}</li>' for s in seg)

    h = []
    # --- cabecera y portada
    h.append(f'<tr><td style="padding:30px 28px 0"><div style="font:700 12px {SANS};letter-spacing:.2em;color:{COL["urbano"]}">TENDENCIAS DE PRENDA</div>'
             f'<div style="font:700 40px/1.05 {SERIF};margin-top:4px;letter-spacing:-.01em">La revista semanal</div>'
             f'<div style="font:13px {SANS};color:{SUAVE};margin-top:8px">Nº {nº} · semana {semana} · {fecha_larga}</div>'
             f'<div style="height:3px;background:{INK};margin-top:16px;font-size:0;line-height:0">&nbsp;</div>'
             f'<div style="font:12px {SANS};color:{SUAVE};padding-top:6px">{"Siete estilos" if multi else "Urbano y geek"} · España y EEUU · fotos públicas de X, prensa y Reddit</div></td></tr>')
    h.append(f'<tr><td style="padding:26px 28px 6px"><h1 style="margin:0;font:700 31px/1.18 {SERIF};color:{INK}">{esc(titular)}</h1>'
             f'<p style="margin:10px 0 0;font:17px/1.5 {SANS};color:{SUAVE}">{esc(deck)}</p></td></tr>')
    h.append(f'<tr><td style="padding:18px 28px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{TARJETA};border:1px solid {LINEA};border-left:4px solid {COL["urbano"]}">'
             f'<tr><td style="padding:14px 18px"><div style="font:700 12px {SANS};letter-spacing:.14em;color:{COL["urbano"]}">EN 30 SEGUNDOS</div>'
             f'<ul style="margin:10px 0 0;padding-left:18px;font:15px/1.5 {SANS}">{resumen}</ul></td></tr></table></td></tr>')

    # --- 01 lo que se lleva
    h.append(seccion("01", "Lo que se lleva", "Reparto de las fotos de la temporada por tipo de prenda. La barra oscura llega al mínimo razonable, la clara al máximo (margen del 95 %) y la marca negra señala la cifra estimada."))
    for g in bloques:
        h.append(caja(bloque_grupo(g, fotos, prendas, hoy_temp), "22px 28px 4px"))
    if vacios:
        txt = "; ".join(f'{ESTILO[e]} en {MERCADO[m]}: {n} {"foto" if n == 1 else "fotos"}' for e, m, n in vacios)
        h.append(caja(f'<div style="background:{TARJETA};border:1px solid {LINEA};padding:12px 16px">{nota("<b>Sin datos suficientes para una cifra</b> (hacen falta 5 fotos por tipo de prenda): " + esc(txt) + ".")}'
                      + (nota("Geek solo se puede describir con tu muestra de referencia (sección 03).") if any(e == "geek" for e, _, _ in vacios) else "") + "</div>", "18px 28px 0"))
    if sin_fuentes:
        h.append(caja(f'<div style="background:{TARJETA};border:1px solid {LINEA};padding:12px 16px">'
                      + nota("<b>Sin fuentes de mercado todavía:</b> " + esc(", ".join(ESTILO[e] for e in sin_fuentes)) + ". Hacen falta personas de referencia y fuentes (X, prensa, Reddit) para cada uno; mientras tanto solo se describen con tu muestra de referencia (sección 03).") + "</div>", "14px 28px 0"))

    # --- 02 qué ha cambiado
    h.append(seccion("02", "Qué ha cambiado", f"Las últimas {VENTANA // 7} semanas frente a las {VENTANA // 7} anteriores, y lo que entró esta semana."))
    if cambios:
        top = cambios[:5]
        filas = "".join(
            f'<tr><td style="padding:6px 0;border-top:1px solid {LINEA};font:600 14px {SANS}">{ESTILO[c["estilo"]]} · {MERCADO[c["mercado"]]} · {esc(c["tipo"])}</td>'
            f'<td align="right" style="padding:6px 0;border-top:1px solid {LINEA};font:14px {SANS};white-space:nowrap;color:{OK if c["dif"] > 0 else MAL}">{"▲" if c["dif"] > 0 else "▼"} {pct(c["B"])} → {pct(c["A"])}</td>'
            f'<td align="right" style="padding:6px 0 6px 10px;border-top:1px solid {LINEA};font:12px {SANS};color:{SUAVE};white-space:nowrap">{"clara" if c["p"] < 0.05 else "orientativa"}</td></tr>' for c in top)
        h.append(caja(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{filas}</table>'
                      + nota(f'Cuota de fotos que llevan ese tipo, últimas {VENTANA // 7} semanas frente a las anteriores. «Clara» = la diferencia aguanta el azar (p &lt; 0,05); «orientativa», no: con {resumen_v and max(max(a, b) for a, b in resumen_v.values())} fotos o menos por ventana casi nada lo hace.'), "14px 28px 0"))
    else:
        base = "; ".join(f'{ESTILO[e]} · {MERCADO[m]}: {a} y {b} fotos' for (e, m), (a, b) in sorted(resumen_v.items())) or "ningún grupo con fotos fechadas en las dos ventanas"
        h.append(caja(f'<b>Todavía no se puede comparar.</b> Para decir que algo sube o baja hacen falta al menos {MIN_VENTANA} fotos en cada ventana de {VENTANA // 7} semanas. Ahora: {esc(base)}. '
                      "La primera comparación entre temporadas completas será hacia abril de 2027.", "14px 28px 0"))
    # novedades de la semana
    if nº == 1:
        txt = (f'<b>Edición inaugural:</b> la primera cosecha reunió {nov["nuevas"]} fotos, {nov["utiles"]} útiles; descartadas: '
               + (", ".join(f"{n} {m.replace('_', ' ')}" for m, n in nov["motivos"].most_common()) or "ninguna") + ". A partir de la próxima edición, esta línea contará solo lo nuevo de cada semana.")
    elif nov["ultima"] and (ahora - nov["ultima"]).days <= 8:
        mot = ", ".join(f"{n} {m.replace('_', ' ')}" for m, n in nov["motivos"].most_common()) or "ninguna descartada"
        fu = ", ".join(f"{esc(k)} {n}" for k, n in nov["por_fuente"].most_common(6)) or "ninguna"
        txt = f'<b>Novedades de la semana:</b> {nov["nuevas"]} fotos vistas, {nov["utiles"]} útiles ({esc(fu)}); descartadas: {esc(mot)}.'
        if nov["errores"]:
            txt += f' <span style="color:{MAL}">Fuentes con error: ' + esc("; ".join(f"{a} ({b}): {c[:60]}" for a, b, c in nov["errores"][:5])) + ".</span>"
    else:
        txt = f'<b>Novedades de la semana:</b> no hubo cosecha nueva (la última fue el {nov["ultima"].strftime("%d/%m/%Y") if nov["ultima"] else "—"}).'
    h.append(caja(txt, "10px 28px 0"))

    # --- 03 qué distingue a cada estilo
    if multi:
        h.append(seccion("03", "Qué distingue a cada estilo", "Para cada estilo, lo que lleva más (o menos) que el resto de estilos. Muestra de referencia: tus fotos aprobadas en la Biblioteca. La barra sale del centro hacia la derecha cuando el estilo lo lleva más que el resto; la parte clara es el margen del 95 %."))
        for t in tarjetas_estilos(p7):
            h.append(t)
        h.append(caja(nota("Si el modelo falla al azar, las diferencias reales se encogen pero no se inventan. Cada estilo se compara con la suma de los demás, y cada categoría se corrige por comparar muchas a la vez (solo salen las que aguantan)."), "10px 28px 0"))
    else:
        h.append(seccion("03", "Geek frente a urbano", "Qué distingue a un estilo del otro en las prendas. A la derecha, más frecuente en geek; a la izquierda, en urbano; el tono claro es el margen del 95 %."))
    if sep and not multi:
        for clave, titulo_s in (("solo_biblioteca", "Con tus fotos aprobadas (mismo origen en los dos estilos)"), ("todas_las_fuentes", "Con todas las fuentes")):
            bloque = sep[clave]
            d0 = bloque["dimensiones"][0]
            filas_s = []
            for d in bloque["dimensiones"]:
                vistas = sorted([c for c in d["categorias"] if c["q"] < 0.10], key=lambda c: -abs(c["dif"]))[:3]
                if not vistas:
                    continue
                escala = max(max(abs(c["ic"][0]), abs(c["ic"][1]), abs(c["dif"])) for c in vistas) * 1.05
                for c in vistas:
                    filas_s.append(
                        f'<tr><td style="padding:9px 0 0;font:600 14px {SANS}">{esc(c["categoria"])} <span style="font:12px {SANS};color:{SUAVE};font-weight:400">({d["dimension"]})</span></td>'
                        f'<td align="right" style="padding:9px 0 0;font:12px {SANS};color:{SUAVE};white-space:nowrap">geek {pct(c["geek"])} · urbano {pct(c["urbano"])}</td></tr>'
                        f'<tr><td colspan="2" style="padding-top:3px">{barra_div(c["dif"], c["ic"][0], c["ic"][1], escala)}</td></tr>')
            sin = [x["dimension"] for x in bloque["dimensiones"] if x["global"]["p"] >= 0.10]
            h.append(caja(f'<div style="font:700 15px {SERIF}">{titulo_s}</div>'
                          + nota(f'{bloque["prendas"]} prendas · geek {d0["prendas_geek"]} en {d0["fotos_geek"]} fotos, urbano {d0["prendas_urbano"]} en {d0["fotos_urbano"]}.')
                          + (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(filas_s)}</table>' if filas_s else nota("Ninguna categoría se distingue con seguridad."))
                          + (nota("No se separan con estos datos: " + esc(", ".join(sin)) + ".") if sin else ""), "16px 28px 0"))
        h.append(caja(nota("Si el modelo falla al azar, las diferencias reales se encogen pero no se inventan. Con «todas las fuentes», parte de la diferencia puede ser de origen: el geek es casi todo de tu galería y el urbano mezcla galería y mercado."), "8px 28px 0"))

    # --- 04 cuánto fiarte
    h.append(seccion("04", "Cuánto fiarte", "Acierto medido contigo y señales internas de esta semana."))
    filas_f = []
    for c, et in (("tipo", "Tipo de prenda"), ("estampado", "Estampado"), ("tejido", "Tejido"), ("forma", "Forma")):
        m = fiab.get(f"vlm_{c}", {})
        if not m:
            continue
        rev = m.get("revision")
        techo = informe["techos"]["vlm"].get(c, "baja")
        filas_f.append(
            f'<tr><td style="padding:7px 0;border-top:1px solid {LINEA};font:600 14px {SANS}">{et}</td>'
            f'<td align="right" style="padding:7px 6px;border-top:1px solid {LINEA};font:14px {SANS}">{pct(m["acierto"] / m["n"])}<div style="font:11px {SANS};color:{SUAVE}">{m["acierto"]} de {m["n"]}</div></td>'
            f'<td align="right" style="padding:7px 6px;border-top:1px solid {LINEA};font:14px {SANS}">{pct(rev["aceptable"] / rev["n"]) if rev else "—"}<div style="font:11px {SANS};color:{SUAVE}">{(str(rev["aceptable"]) + " de " + str(rev["n"])) if rev else ""}</div></td>'
            f'<td align="right" style="padding:7px 0 7px 6px;border-top:1px solid {LINEA}">{chip_corto(techo)}</td></tr>')
    cab_f = (f'<tr><td style="font:700 11px {SANS};letter-spacing:.06em;color:{SUAVE}">ATRIBUTO</td><td align="right" style="font:700 11px {SANS};letter-spacing:.06em;color:{SUAVE}">A CIEGAS</td>'
             f'<td align="right" style="font:700 11px {SANS};letter-spacing:.06em;color:{SUAVE}">TU REVISIÓN</td><td align="right" style="font:700 11px {SANS};letter-spacing:.06em;color:{SUAVE}">TECHO</td></tr>')
    h.append(caja(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{cab_f}{"".join(filas_f)}</table>'
                  + nota("<b>A ciegas:</b> coincidencia con lo que tú etiquetaste sin ver la respuesta del modelo. <b>Tu revisión:</b> lo que diste por bueno (OK o «más o menos») viendo su valoración; es más generosa, así que el acierto real queda entre las dos cifras. "
                         "<b>Techo:</b> la confianza máxima que puede tener una cifra de ese atributo por muchas fotos que haya."), "14px 28px 0"))
    # señales internas
    vl, coh, tot = 0, 0, 0
    for fid, r in prendas.items():
        for p in r["prendas"]:
            if tp.valida(p) and p.get("vlm"):
                tot += 1
                coh += tp.FAMILIA.get(p["vlm"]["tipo"]) == {"ropa_superior": "Arriba", "abrigo": "Abrigo", "ropa_inferior": "Abajo", "cuerpo_entero": "Cuerpo entero", "calzado": "Calzado", "accesorio": "Accesorio"}.get(p["cat"])
    niveles = collections.Counter(f["confianza"] for g in bloques for f in g["prendas"] if f["cuota"] is not None)
    descartadas = collections.Counter(v["descartada"] for v in fotos_d.values() if v.get("descartada"))
    sen = [f'<b>Coherencia interna:</b> en {pct(coh / tot) if tot else "—"} de las {num(tot)} prendas el modelo grande y el detector coinciden en la familia (arriba, abrigo, abajo…). No es acierto: es una señal para notar si algo cambia de una semana a otra.',
           f'<b>Confianza de las cifras por tipo de esta revista:</b> {niveles.get("alta", 0)} alta, {niveles.get("media", 0)} media, {niveles.get("baja", 0)} baja. Con pocas fotos, la confianza sale baja aunque el modelo acierte.',
           f'<b>Filtro de fotos:</b> de {num(len(fotos_d))} vistas se descartaron {num(sum(descartadas.values()))} (' + ", ".join(f"{n} {m.replace('_', ' ')}" for m, n in descartadas.most_common()) + ").",
           "<b>Punto débil conocido:</b> " + (esc("; ".join(f"«{t}»: {d['aceptado']} de {d['n']} dadas por buenas" for t, d in (fiab.get("vlm_tipo", {}).get("por_tipo") or {}).items() if d["n"] >= 6 and d["aceptado"] / d["n"] < .65)) or "ninguno") + "."]
    h.append(caja('<ul style="margin:0;padding-left:18px;font:14px/1.55 ' + SANS + '">' + "".join(f'<li style="margin:0 0 6px">{s}</li>' for s in sen) + "</ul>", "6px 28px 0"))

    # --- 05 qué ha considerado
    h.append(seccion("05", "Qué ha considerado", "De dónde salen las fotos y qué filtros pasan antes de contar."))
    util = collections.Counter((v.get("referente") or "Biblioteca") for v in fotos_d.values() if not v.get("descartada"))
    filas_c, sin_fotos, sin_lectura, vistos = [], [], [], set()
    for s_ in fuentes_cfg:
        sid = hashlib.sha1(f"{s_['tipo']}|{s_['valor']}|{s_['referente']}".encode()).hexdigest()[:8]
        e = estado.get(sid, {})
        clave = (s_["referente"], s_["tipo"])
        if clave in vistos:
            continue
        vistos.add(clave)
        medio = "X" if s_["tipo"] == "x" else "prensa" if s_["tipo"] == "noticias" else s_["tipo"]
        if e.get("error"):
            est = f'<span style="color:{MAL}">error</span>'
        elif e.get("ultima_foto_hace_dias") is not None and e["ultima_foto_hace_dias"] > 60:
            est = f'<span style="color:{AVISO}">sin fotos recientes</span>'
        else:
            est = f'<span style="color:{OK}">ok</span>'
        n_ = util.get(s_["referente"], 0)
        if e.get("sin_lectura") and n_ == 0 and not e.get("error"):
            sin_lectura.append(s_["referente"])
            continue
        if n_ == 0 and not e.get("error"):
            sin_fotos.append(f'{s_["referente"]} ({medio})')
            continue
        filas_c.append((n_, f'<tr><td style="padding:5px 0;border-top:1px solid {LINEA};font:13px {SANS}">{esc(s_["referente"])} <span style="color:{SUAVE}">· {medio}</span>'
                           f'<div style="font:11px {SANS};color:{SUAVE}">{ESTILO[s_["estilo"]]} · {s_["mercado"]}</div></td>'
                           f'<td align="right" style="padding:5px 6px;border-top:1px solid {LINEA};font:13px {SANS}">{n_}</td>'
                           f'<td align="right" style="padding:5px 0 5px 6px;border-top:1px solid {LINEA};font:12px {SANS}">{est}</td></tr>'))
    filas_c.sort(key=lambda t: -t[0])
    cab_c = f'<td style="font:700 11px {SANS};letter-spacing:.06em;color:{SUAVE}">FUENTE</td><td align="right" style="font:700 11px {SANS};letter-spacing:.06em;color:{SUAVE}">FOTOS ÚTILES</td><td align="right" style="font:700 11px {SANS};letter-spacing:.06em;color:{SUAVE}">ESTADO</td>'
    h.append(caja(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{cab_c}</tr>{"".join(t for _, t in filas_c)}</table>'
                  + nota(f'Además, tus {util.get("Biblioteca", 0)} fotos aprobadas (galería) sirven de muestra de referencia, sin fecha ni mercado. '
                         + ("Sin ninguna foto útil hasta ahora: " + esc(", ".join(sin_fotos)) + "." if sin_fotos else "")
                         + (f' Instagram: {len(sin_lectura)} cuentas de las fuentes todavía no se leen (no están dadas de alta en el plan de lectura actual; no es un fallo).' if sin_lectura else "")), "14px 28px 0"))
    metodo = ["<b>Quién da el estilo:</b> la persona de referencia (la cuenta o el nombre en el titular), no la foto. No hay reconocimiento facial.",
              "<b>Qué foto entra:</b> persona con ropa visible (CLIP) y no repetida; las prendas se localizan con un detector DeepFashion2 y Florence-2; se ignoran los recuadros del «torso» y las prendas vistas a medias.",
              "<b>Qué dice cada prenda:</b> tipo, estampado, tejido y forma los estima Qwen3-VL de 8 000 millones en Kaggle, con tu vocabulario. Las fotos se suben a un dataset privado que se borra al terminar.",
              f"<b>Cómo se cuenta:</b> una foto cuenta una vez por tipo, pesada por su popularidad y frescura (vida media de 10 días); por debajo de {tp.MIN_FOTOS} fotos no se enseña cifra; las fotos de hace más de 400 días no se analizan.",
              "<b>Temporadas:</b> primavera-verano de marzo a agosto y otoño-invierno de septiembre a febrero."]
    h.append(caja('<ul style="margin:0;padding-left:18px;font:14px/1.55 ' + SANS + '">' + "".join(f'<li style="margin:0 0 6px">{s}</li>' for s in metodo) + "</ul>", "14px 28px 0"))

    # --- pie
    pend = []
    if any(e == "geek" for e, _, _ in vacios):
        pend.append("Conseguir fotos geek del mercado: hoy casi no hay (X, prensa y Reddit dan muy poco).")
    if sin_fuentes:
        pend.append("Elegir personas de referencia y fuentes de mercado para " + ", ".join(ESTILO[e] for e in sin_fuentes) + ".")
    pend.append("Repetir la revisión «OK / más o menos / No» cada mes con recortes nuevos para seguir midiendo el acierto.")
    h.append(seccion("06", "Para la próxima", ""))
    h.append(caja('<ul style="margin:0;padding-left:18px;font:14px/1.55 ' + SANS + '">' + "".join(f'<li style="margin:0 0 6px">{s}</li>' for s in pend) + "</ul>", "10px 28px 0"))
    h.append(f'<tr><td style="padding:30px 28px 34px"><div style="height:2px;background:{INK};font-size:0;line-height:0">&nbsp;</div><p style="font:12px/1.55 {SANS};color:{SUAVE};margin:12px 0 0">'
             f'Se genera sola cada lunes con lo que han publicado las fuentes de arriba y se envía a tu correo. Las cifras son de fotos públicas y de un modelo que se equivoca: úsalas para orientarte, no para decidir. '
             f'Código y memoria en el repositorio del TFM.</p></td></tr>')

    preheader = f"Nº {nº} · {titular}"
    cuerpo = "".join(h)
    doc = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light only">'
           f'<title>Tendencias de prenda · Nº {nº}</title></head><body style="margin:0;padding:0;background:{PAPEL}">'
           f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{PAPEL}">{esc(preheader)}</div>'
           f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAPEL}"><tr><td align="center" style="padding:14px 8px">'
           f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:{TARJETA};color:{INK}">{cuerpo}</table>'
           f'</td></tr></table></body></html>')
    texto = [f"TENDENCIAS DE PRENDA · La revista semanal · Nº {nº} · semana {semana} · {fecha_larga}", "", titular, deck, "", "EN 30 SEGUNDOS"]
    import re
    texto += ["- " + re.sub(r"<[^>]+>", "", s.replace("&nbsp;", " ")) for s in seg]
    texto += ["", "Abre este correo en HTML para ver las barras, las fotos y las tablas completas."]
    info.update(titular=titular, asunto=f"Tendencias de prenda · Nº {nº} · {titular}")
    return doc, "\n".join(texto), fotos, info


def con_fotos_incrustadas(doc: str, fotos: Fotos) -> str:
    for clave, b in fotos.items.items():
        if b is not None:
            cid = "f" + hashlib.sha1(clave.encode()).hexdigest()[:10]
            doc = doc.replace(f"cid:{cid}", "data:image/jpeg;base64," + base64.b64encode(b).decode())
    return doc


def generar(salida: Path, as_of: dt.date, con_fotos: bool = True) -> tuple[str, str, Fotos, dict]:
    doc, texto, fotos, info = componer(as_of, con_fotos)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "revista.html").write_text(doc, encoding="utf-8")
    (salida / "revista_vista.html").write_text(con_fotos_incrustadas(doc, fotos), encoding="utf-8")
    (salida / "revista.txt").write_text(texto, encoding="utf-8")
    kb = len(doc.encode("utf-8")) / 1024
    n_fotos = sum(1 for b in fotos.items.values() if b is not None)
    print(f"Revista Nº {info['edicion']} (semana {info['semana']}): HTML {kb:.0f} KB {'⚠ Gmail lo recortará' if len(doc.encode('utf-8')) > MAX_HTML else '(cabe en Gmail)'} · {n_fotos} fotos · {salida}")
    return doc, texto, fotos, info


def mensaje(doc: str, texto: str, fotos: Fotos, asunto: str) -> EmailMessage:
    para, de = os.environ["MAIL_TO"], os.environ.get("MAIL_FROM") or os.environ["SMTP_USER"]
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"], msg["Date"] = asunto, de, para, formatdate(localtime=False)
    msg.set_content(texto)
    msg.add_alternative(doc, subtype="html")
    parte = msg.get_payload()[1]
    for clave, b in fotos.items.items():
        if b is not None:
            parte.add_related(b, "image", "jpeg", cid="<" + "f" + hashlib.sha1(clave.encode()).hexdigest()[:10] + ">", disposition="inline")
    return msg


def enviar_mensaje(msg: EmailMessage) -> None:
    host, port = os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=60) as s:
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre in ("generar", "enviar"):
        p = sub.add_parser(nombre)
        p.add_argument("--salida", type=Path, default=TD / "revista")
        p.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.datetime.now(dt.timezone.utc).date())
        p.add_argument("--sin-fotos", action="store_true", help="sin miniaturas de prendas (las fotos son de personas reales)")
    p = sub.add_parser("aviso-fallo")
    p.add_argument("--paso", required=True)
    p.add_argument("--enlace", default="")
    a = ap.parse_args()
    if a.cmd == "generar":
        generar(a.salida, a.as_of, not a.sin_fotos)
    elif a.cmd == "enviar":
        doc, texto, fotos, info = generar(a.salida, a.as_of, not a.sin_fotos)
        marca = TD / "ultima_revista.txt"   # edición ya enviada (viaja con los datos): una ejecución programada tardía no repite la que se lanzó a mano
        if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and marca.exists() and marca.read_text(encoding="utf-8").strip() == str(info["edicion"]):
            print(f"La edición Nº {info['edicion']} ya se envió: no se repite.")
            return
        asunto = info["asunto"] if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch" else "[prueba manual] " + info["asunto"]
        enviar_mensaje(mensaje(doc, texto, fotos, asunto))
        marca.write_text(str(info["edicion"]), encoding="utf-8")
        print("Enviada.")
    else:
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"], msg["Date"] = "Tendencias de prenda · no se pudo generar la revista de esta semana", os.environ.get("MAIL_FROM") or os.environ["SMTP_USER"], os.environ["MAIL_TO"], formatdate()
        msg.set_content(f"La tarea semanal falló en el paso: {a.paso}.\n" + (f"Detalle: {a.enlace}\n" if a.enlace else "") + "\nLos datos de la semana anterior siguen intactos; se reintentará el lunes que viene o puedes lanzarla a mano desde la pestaña Actions de GitHub.")
        enviar_mensaje(msg)
        print("Aviso de fallo enviado.")


if __name__ == "__main__":
    sys.exit(main())
