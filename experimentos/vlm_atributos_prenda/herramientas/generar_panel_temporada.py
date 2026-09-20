#!/usr/bin/env python3
"""
Genera el HTML del artifact "Reglas de temporada" (decision por tipo de prenda: todo el año
vs. según temporada real de Kaggle), con una propuesta ya calculada por tipo a partir de las
respuestas de la revision humana, y 1-2 fotos de ejemplo de las mismas fichas ya revisadas
(incrustadas en base64, no se sirven aparte).

Contexto: `Jackets` ya tiene una regla fija en preparar_dataset_florence2.py (todo_el_ano,
decision explicita del autor). El resto de tipos se queda con el mapeo de 2 valores por
`season` de Kaggle -- este panel es para decidir, tipo a tipo, si eso vale o si conviene
todo_el_ano tambien ahi. Ver memoria/TFM_clasificador_visual_atributos.md S11.1/S11.4.

La pagina generada NO se commitea (deriva de las fotos de la app de revision + los datos de
revisiones_app_n100 -- regenerable). Solo se commitea este generador y, mas adelante,
leer_reglas_temporada.py con las decisiones ya tomadas.

Uso:
    python3 generar_panel_temporada.py --salida /ruta/panel_temporada.html
    # luego: Artifact publish ese fichero (capabilities db) y sembrar temporada_reglas/*
    # con las propuestas via ArtifactData batch (ver el propio dict PROPUESTAS impreso al final).
"""
import argparse
import base64
import collections
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
APP_DIR = Path.home() / "app_revision_prendas"

NOMBRES_ES = {
    "Jackets": "Chaquetas", "Dresses": "Vestidos", "Tshirts": "Camisetas", "Backpacks": "Mochilas",
    "Caps": "Gorras", "Casual Shoes": "Zapatillas casual", "Shirts": "Camisas", "Clutches": "Clutches",
    "Tops": "Tops", "Shorts": "Shorts", "Jeans": "Vaqueros", "Flip Flops": "Chanclas", "Heels": "Tacones",
    "Track Pants": "Pantalón deportivo", "Sandals": "Sandalias", "Trousers": "Pantalón de vestir",
    "Leggings": "Leggings", "Sports Shoes": "Zapatillas deportivas", "Sweaters": "Jerséis",
    "Skirts": "Faldas", "Formal Shoes": "Zapatos de vestir", "Jumpsuit": "Monos",
}
TIPOS_YA_DECIDIDOS = {"Jackets": "todo_el_ano"}  # ver TIPOS_TODO_EL_ANO en preparar_dataset_florence2.py


def S(v):
    return set(v) if isinstance(v, list) else {v}


def calcular_propuesta(tipo, n, todo_frac, solo_pv, solo_oi):
    if tipo in TIPOS_YA_DECIDIDOS:
        return TIPOS_YA_DECIDIDOS[tipo], "ya_aplicado"
    if n < 3:
        return ("todo_el_ano" if todo_frac >= 0.5 else "estacional"), "pocos_datos"
    if todo_frac >= 0.6:
        return "todo_el_ano", "propuesta"
    if max(solo_pv, solo_oi) >= 0.7:
        return "estacional", "propuesta"
    return "estacional", "sin_patron"  # mixto (como Jackets/Dresses): se deja el default actual, marcado como dudoso


def construir_items(manifest, revs, n_ejemplos=2):
    por_tipo = collections.defaultdict(list)
    for i in revs:
        por_tipo[manifest[i]["articleType"]].append(i)

    items = []
    for tipo, ids in sorted(por_tipo.items(), key=lambda kv: -len(kv[1])):
        n = len(ids)
        combos = collections.Counter("+".join(sorted(S(revs[i]["temporada"]))) for i in ids)
        todo_frac = sum(1 for i in ids if "todo_el_ano" in S(revs[i]["temporada"])) / n
        solo_pv = sum(1 for i in ids if S(revs[i]["temporada"]) == {"primavera_verano"}) / n
        solo_oi = sum(1 for i in ids if S(revs[i]["temporada"]) == {"otono_invierno"}) / n
        regla, confianza = calcular_propuesta(tipo, n, todo_frac, solo_pv, solo_oi)

        imgs = []
        for i in ids[:n_ejemplos]:
            with open(APP_DIR / "imagenes" / manifest[i]["archivo"], "rb") as f:
                imgs.append("data:image/jpeg;base64," + base64.b64encode(f.read()).decode())

        items.append({
            "tipo": tipo, "slug": tipo.replace(" ", "_"), "nombre": NOMBRES_ES.get(tipo, tipo), "n": n,
            "combos": dict(combos.most_common()), "regla_propuesta": regla, "confianza": confianza, "imgs": imgs,
        })
    return items


PLANTILLA = r'''<title>Reglas de temporada</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{
  --bg:#f5f3ee; --surface:#ffffff; --ink:#201c22; --muted:#726d76; --line:#e4dfd6;
  --accent:#5b4b8a; --accent-bg:#efeaf8;
  --todo:#2f7d6b; --todo-bg:#e3f2ec; --est:#a8631f; --est-bg:#fbefe0; --none:#726d76; --none-bg:#eeebe3;
  padding-top:env(safe-area-inset-top,0px); padding-bottom:env(safe-area-inset-bottom,0px);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#17151a; --surface:#211e25; --ink:#eeebe6; --muted:#9d97a3; --line:#332f39;
    --accent:#a898db; --accent-bg:#2a2440;
    --todo:#6fd3b3; --todo-bg:#123028; --est:#e3a35c; --est-bg:#372509; --none:#9d97a3; --none-bg:#28242e;
  }
}
:root[data-theme="dark"]{
  --bg:#17151a; --surface:#211e25; --ink:#eeebe6; --muted:#9d97a3; --line:#332f39;
  --accent:#a898db; --accent-bg:#2a2440;
  --todo:#6fd3b3; --todo-bg:#123028; --est:#e3a35c; --est-bg:#372509; --none:#9d97a3; --none-bg:#28242e;
}
*{box-sizing:border-box}
body{background:var(--bg); color:var(--ink); font-family:"IBM Plex Sans",system-ui,-apple-system,sans-serif;
     padding:0 16px 40px; max-width:600px; margin:0 auto;}
.mono{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace; font-variant-numeric:tabular-nums;}
header{position:sticky; top:env(safe-area-inset-top,0px); background:var(--bg); z-index:5;
       padding:18px 0 12px; border-bottom:1px solid var(--line);}
.eyebrow{font-size:11px; text-transform:uppercase; letter-spacing:.09em; color:var(--muted); margin:0 0 2px;}
h1{font-size:18px; font-weight:600; margin:0; letter-spacing:-.01em;}
main{padding-top:16px; display:flex; flex-direction:column; gap:14px;}
.card{background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:15px;}
.intro p{font-size:13.5px; line-height:1.55; margin:0 0 8px; color:var(--muted);}
.intro p:last-child{margin-bottom:0}
.intro b{color:var(--ink); font-weight:600;}
.introcode{font-family:"IBM Plex Mono",monospace; background:var(--none-bg); padding:1px 5px; border-radius:5px; font-size:11.5px;}
.rowtop{display:flex; align-items:flex-start; justify-content:space-between; gap:10px;}
.titulo{font-size:14.5px; font-weight:600;}
.n{font-size:11.5px; color:var(--muted); font-weight:400;}
.badge{font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:.04em; padding:2px 7px;
      border-radius:999px; white-space:nowrap;}
.badge.aplicado{color:var(--todo); background:var(--todo-bg);}
.badge.propuesta{color:var(--accent); background:var(--accent-bg);}
.badge.pocos{color:var(--muted); background:var(--none-bg);}
.badge.mixto{color:var(--est); background:var(--est-bg);}
.thumbs{display:flex; gap:6px; margin:10px 0;}
.thumbs img{width:52px; height:70px; object-fit:cover; border-radius:7px; border:1px solid var(--line); background:var(--none-bg);}
.historial{font-size:11.5px; color:var(--muted); margin:0 0 10px;}
.seg{display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px;}
.seg button{font:inherit; font-size:12px; font-weight:600; padding:9px 6px; border-radius:9px; border:1px solid var(--line);
      background:var(--surface); color:var(--muted); cursor:pointer; line-height:1.25;}
.seg button.on.todo_el_ano{background:var(--todo-bg); border-color:var(--todo); color:var(--todo);}
.seg button.on.estacional{background:var(--est-bg); border-color:var(--est); color:var(--est);}
.seg button.on.pendiente{background:var(--none-bg); border-color:var(--muted); color:var(--ink);}
.reset{display:inline-block; margin-top:8px; font-size:11px; color:var(--accent); background:none; border:none;
      padding:0; cursor:pointer; font-family:inherit; text-decoration:underline; text-underline-offset:2px;}
.reset[hidden]{display:none;}
h2{font-size:12.5px; font-weight:600; margin:0 0 8px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);}
.foot{font-size:12px; color:var(--muted); line-height:1.6; padding:2px 2px 0;}
.foot code{font-family:"IBM Plex Mono",monospace; background:var(--none-bg); padding:1px 5px; border-radius:5px; font-size:11px;}
</style>

<header>
  <p class="eyebrow">TFM &middot; Florence-2 LoRA</p>
  <h1>Reglas de temporada, por tipo de prenda</h1>
</header>

<main>
  <div class="card intro">
    <p><b>Qué es esto.</b> La <span class="introcode">temporada</span> de Kaggle es la colecci&oacute;n del
    comerciante, no si la prenda es estacional de verdad &mdash; en tu revisi&oacute;n de 100 fichas, en 43
    marcaste <b>todo el a&ntilde;o</b>. Ya se aplic&oacute; esa regla a <b>Chaquetas</b> (siempre todo el
    a&ntilde;o, como pediste). Para el resto de tipos hay dos opciones por prenda: <b>todo el a&ntilde;o</b>
    o <b>seg&uacute;n la temporada real</b> (primavera-verano / oto&ntilde;o-invierno, la de Kaggle).</p>
    <p><b>C&oacute;mo funciona.</b> Cada tarjeta ya tiene <b>mi propuesta</b> marcada, calculada con tus
    propias 100 respuestas (cuantas m&aacute;s revisiones tenga el tipo, m&aacute;s fiable). Si no tocas
    nada, se queda mi propuesta. Toca otra opci&oacute;n para cambiarla &mdash; y si te arrepientes, tocar
    otra vez es todo lo que hace falta para revertirlo, no hay un paso aparte.</p>
  </div>

  <div class="card" id="tarjeta-default">
    <div class="rowtop">
      <div><div class="titulo">Regla por defecto</div><div class="n">para cualquier tipo no listado abajo</div></div>
    </div>
    <div class="seg" data-tipo="_default" style="margin-top:10px">
      <button data-valor="todo_el_ano">Todo el a&ntilde;o</button>
      <button data-valor="estacional">Seg&uacute;n temporada real</button>
      <button data-valor="pendiente">Sin decidir</button>
    </div>
  </div>

  <div id="lista"></div>

  <p class="foot">
    Esto no cambia nada todav&iacute;a por su cuenta: son tus decisiones guardadas para que Claude las
    aplique despu&eacute;s en <code>preparar_dataset_florence2.py</code> (igual que se hizo con Chaquetas) y
    se regenere el dataset para un pr&oacute;ximo reentrenamiento v3, cuando lo pidas.
  </p>
</main>

<script>
const ITEMS = __DATA__;

const ES_COMBO = { primavera_verano: "PV", otono_invierno: "OI", todo_el_ano: "TODO" };
function textoHistorial(it){
  const partes = Object.entries(it.combos).map(([k,v]) => {
    const nombre = k.split("+").map(x => ES_COMBO[x] || x).join("+");
    return `${nombre} ${v}`;
  });
  return `Tus ${it.n} revisiones: ` + partes.join(", ");
}
const BADGE = {
  ya_aplicado: ["aplicado", "Ya aplicado"], propuesta: ["propuesta", "Propuesta"],
  pocos_datos: ["pocos", "Pocos datos"], sin_patron: ["mixto", "Sin patrón claro"],
};
const ETIQUETA = { todo_el_ano: "Todo el año", estacional: "Según temporada real", pendiente: "Sin decidir" };

function tarjetaHTML(it){
  const [claseBadge, textoBadge] = BADGE[it.confianza];
  const imgs = it.imgs.map(src => `<img src="${src}" alt="${it.nombre}">`).join("");
  return `
    <div class="card" data-tipo="${it.slug}">
      <div class="rowtop">
        <div><div class="titulo">${it.nombre}</div><div class="n">${it.n} ${it.n===1?"revisión":"revisiones"} tuyas &middot; ${it.tipo}</div></div>
        <span class="badge ${claseBadge}">${textoBadge}</span>
      </div>
      <div class="thumbs">${imgs}</div>
      <div class="historial">${textoHistorial(it)}</div>
      <div class="seg" data-tipo="${it.slug}">
        <button data-valor="todo_el_ano">Todo el año</button>
        <button data-valor="estacional">Según temporada real</button>
        <button data-valor="pendiente">Sin decidir</button>
      </div>
      <button class="reset" hidden>&#8630; usar mi propuesta (${ETIQUETA[it.regla_propuesta]})</button>
    </div>`;
}

document.getElementById("lista").innerHTML = ITEMS.map(tarjetaHTML).join("");

(function(){
  const propuestaDe = {};
  ITEMS.forEach(it => propuestaDe[it.slug] = it.regla_propuesta);
  propuestaDe["_default"] = "estacional"; // el comportamiento actual del codigo para tipos no listados

  function pintar(tipo, valor){
    document.querySelectorAll(`.seg[data-tipo="${CSS.escape(tipo)}"] button`).forEach(b => {
      b.classList.toggle("on", b.dataset.valor === valor);
      b.classList.toggle(b.dataset.valor, b.dataset.valor === valor);
    });
    const tarjeta = document.querySelector(`[data-tipo="${CSS.escape(tipo)}"].card`) ||
                     document.getElementById("tarjeta-default");
    const btnReset = tarjeta.querySelector(".reset");
    if (btnReset) btnReset.hidden = (valor === propuestaDe[tipo]);
  }

  ITEMS.forEach(it => pintar(it.slug, it.regla_propuesta));
  pintar("_default", propuestaDe["_default"]);

  async function iniciar(){
    let db;
    try { db = await window.claude.use("db"); } catch (e) { db = null; }
    if (!db) return; // se queda con las propuestas pintadas arriba, solo de lectura

    const tipos = ITEMS.map(it => it.slug).concat(["_default"]);
    tipos.forEach(tipo => {
      db.doc("temporada_reglas/" + tipo).onSnapshot(snap => {
        const valor = snap.exists ? snap.data().regla : propuestaDe[tipo];
        pintar(tipo, valor);
      });
    });

    document.addEventListener("click", async (ev) => {
      const btn = ev.target.closest(".seg button");
      if (btn) {
        const tipo = btn.closest(".seg").dataset.tipo;
        pintar(tipo, btn.dataset.valor); // respuesta visual inmediata
        try {
          await db.doc("temporada_reglas/" + tipo).set({ regla: btn.dataset.valor, actualizado_en: new Date().toISOString() });
        } catch (e) { /* la vista ya se repinta sola desde onSnapshot si falla */ }
        return;
      }
      const reset = ev.target.closest(".reset");
      if (reset) {
        const tipo = reset.closest("[data-tipo]").dataset.tipo;
        pintar(tipo, propuestaDe[tipo]);
        try {
          await db.doc("temporada_reglas/" + tipo).set({ regla: propuestaDe[tipo], actualizado_en: new Date().toISOString() });
        } catch (e) {}
      }
    });
  }

  window.claude?.hot?.ready ? window.claude.hot.ready(iniciar) : iniciar();
})();
</script>
'''


def main():
    ap = argparse.ArgumentParser()
    datos = BASE_DIR / "data" / "revision_humana"
    ap.add_argument("--manifest", default=str(datos / "manifest_app_120.json"))
    ap.add_argument("--revisiones", default=str(datos / "revisiones_app_n100_2026-09-20.json"))
    ap.add_argument("--salida", required=True)
    args = ap.parse_args()

    manifest = {str(m["id"]): m for m in json.load(open(args.manifest, encoding="utf-8"))}
    revs = {str(i): d.get("data", d) for i, d in json.load(open(args.revisiones, encoding="utf-8")).items()}
    items = construir_items(manifest, revs)

    data_js = json.dumps(items, ensure_ascii=False).replace("</script", "<\\/script")
    html = PLANTILLA.replace("__DATA__", data_js)
    Path(args.salida).write_text(html, encoding="utf-8")
    print(f"{len(items)} tipos -> {args.salida} ({len(html) / 1024:.0f} KB)")

    print("\nPropuestas (para sembrar temporada_reglas/* con ArtifactData batch tras publicar):")
    for it in items:
        print(f"  {it['slug']:<14} {it['regla_propuesta']:<12} ({it['confianza']})")
    print("  _default       estacional   (comportamiento_actual)")


if __name__ == "__main__":
    main()
