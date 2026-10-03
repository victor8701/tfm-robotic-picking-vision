#!/usr/bin/env python3
"""
Experimento B -- puntuación a ciegas (juicio humano, Estado_arte.md S11.2).

Arranca un servidor local MÍNIMO (solo librería estándar, sin instalar nada) y lo abres en el navegador:

    python3 evaluar_b.py            ->  http://localhost:8765

Ves una prenda cada vez, con el nombre de la tendencia y sus rasgos (la definición de TU taxonomía), y
la puntúas: 0 = no encaja · 1 = regular · 2 = sí encaja (teclas 0/1/2; flecha izquierda = volver).
No se muestra en ningún momento qué método propuso cada prenda: eso está en pool_b_clave.json, que esta
página no lee. Cada puntuación se guarda al instante en ratings_b.json, así que puedes parar y reanudar.

Las imágenes del inventario de prueba son miniaturas de 60x80 px: juzga por tipo de prenda, color y corte.
"""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AQUI = Path(__file__).resolve().parent
POC = AQUI.parent
CANDADO = threading.Lock()

PAGINA = """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Experimento B</title>
<style>
:root{--fondo:#f4f1ec;--tinta:#1e2430;--suave:#6a6f7a;--tarjeta:#fff;--linea:#d9d4cb;--acento:#2f4a6b}
@media (prefers-color-scheme:dark){:root{--fondo:#15181f;--tinta:#e9e6df;--suave:#9aa0ab;--tarjeta:#1f242e;--linea:#333a47;--acento:#8fb0d6}}
body{margin:0;background:var(--fondo);color:var(--tinta);font:16px/1.45 system-ui,sans-serif}
main{max-width:520px;margin:0 auto;padding:18px 16px 40px}
h1{font-size:1rem;margin:0 0 4px}.sub{color:var(--suave);font-size:.85rem;margin:0 0 12px}
.barra{height:6px;background:var(--linea);border-radius:4px;overflow:hidden;margin:6px 0 16px}
.barra div{height:100%;background:var(--acento);width:0}
.tarjeta{background:var(--tarjeta);border:1px solid var(--linea);border-radius:12px;padding:16px;text-align:center}
.tend{font-weight:700;font-size:1.15rem}.rasgos{color:var(--suave);font-size:.88rem;margin:4px 0 14px}
img{width:240px;height:320px;object-fit:contain;background:#fff;border:1px solid var(--linea);border-radius:8px}
.q{margin:14px 0 8px;font-size:.95rem}
.botones{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
button{font:inherit;padding:14px 6px;border-radius:10px;border:1px solid var(--linea);background:var(--tarjeta);color:var(--tinta);cursor:pointer}
button:hover,button:focus-visible{border-color:var(--acento);outline:2px solid var(--acento)}
button b{display:block;font-size:1.3rem}
.pie{display:flex;justify-content:space-between;margin-top:12px;color:var(--suave);font-size:.85rem}
.pie button{padding:6px 12px}
</style>
<main>
<h1>Experimento B — puntuación a ciegas</h1>
<p class="sub">Miniaturas de 60×80 px: juzga por tipo de prenda, color y corte. Teclas 0 · 1 · 2, ← para volver.</p>
<div class="barra"><div id="prog"></div></div>
<div class="tarjeta" id="caja"></div>
<div class="pie"><span id="cuenta"></span><button id="atras">← Volver</button></div>
</main>
<script>
let pool=[], rat={}, i=0;
const $=s=>document.querySelector(s);
async function cargar(){
  pool=await (await fetch('/api/pool')).json(); rat=await (await fetch('/api/ratings')).json();
  i=pool.findIndex(p=>!(p.clave in rat)); if(i<0) i=pool.length; pintar();
}
let avisado=false;
function pintar(){
  const hechas=Object.keys(rat).filter(k=>pool.some(p=>p.clave===k)).length;
  const t1=pool.filter(p=>p.tramo===1), t2=pool.filter(p=>p.tramo===2);
  const h1=t1.filter(p=>p.clave in rat).length, h2=t2.filter(p=>p.clave in rat).length;
  $('#prog').style.width=(100*hechas/pool.length)+'%';
  $('#cuenta').textContent='tramo 1 (top-5): '+h1+'/'+t1.length+' · tramo 2 (6-10): '+h2+'/'+t2.length;
  if(i<pool.length && pool[i].tramo===2 && h1===t1.length && !avisado){
    $('#caja').innerHTML='<p class="tend">Tramo 1 completo ✔</p><p class="rasgos">Ya tienes lo mínimo (el top-5 de todos los métodos). Puedes parar aquí y ejecutar <code>python3 experimento_b.py analizar</code>, o seguir con el tramo 2 (puestos 6-10) para más precisión.</p><button onclick="avisado=true;pintar()">Seguir con el tramo 2 →</button>';return;
  }
  if(i>=pool.length){
    $('#caja').innerHTML='<p class="tend">Terminado ✔</p><p class="rasgos">Cierra esta página y ejecuta:<br><code>python3 experimento_b.py analizar</code></p>';return;
  }
  const p=pool[i];
  $('#caja').innerHTML=`<div class="tend">${p.nombre}</div><div class="rasgos">${p.rasgos}</div>
    <img src="/img/${i}" alt="prenda ${i+1}"><div class="q">¿Esta prenda encajaría en un catálogo que siga la tendencia «${p.nombre}»?</div>
    <div class="botones"><button onclick="puntuar(0)"><b>0</b>No encaja</button><button onclick="puntuar(1)"><b>1</b>Regular</button><button onclick="puntuar(2)"><b>2</b>Sí encaja</button></div>`;
}
async function puntuar(v){
  const p=pool[i];
  const r=await fetch('/api/rate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clave:p.clave,valor:v})});
  if(!r.ok){alert('No se pudo guardar');return;} rat[p.clave]=v; i++; pintar();
}
$('#atras').onclick=()=>{if(i>0){i--;pintar();}};
document.addEventListener('keydown',e=>{
  if(e.key==='0'||e.key==='1'||e.key==='2'){ if(i<pool.length) puntuar(+e.key); }
  else if(e.key==='ArrowLeft'&&i>0){i--;pintar();}
});
cargar();
</script></html>"""


def crear_manejador(pool, ratings_path):
    claves = {p["clave"] for p in pool}

    def leer():
        return json.loads(ratings_path.read_text(encoding="utf-8")) if ratings_path.exists() else {}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silencioso
            pass

        def _enviar(self, cuerpo, tipo, codigo=200):
            if isinstance(cuerpo, str):
                cuerpo = cuerpo.encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            if self.path == "/":
                self._enviar(PAGINA, "text/html; charset=utf-8")
            elif self.path == "/api/pool":
                self._enviar(json.dumps(pool, ensure_ascii=False), "application/json")
            elif self.path == "/api/ratings":
                self._enviar(json.dumps(leer()), "application/json")
            elif self.path.startswith("/img/"):
                try:
                    ruta = (POC / pool[int(self.path[5:])]["imagen"]).resolve()
                    ok = ruta.is_file() and POC.resolve() in ruta.parents
                except (ValueError, IndexError):
                    ok = False
                if not ok:
                    return self._enviar("no encontrada", "text/plain", 404)
                self._enviar(ruta.read_bytes(), "image/jpeg" if ruta.suffix.lower() in {".jpg", ".jpeg"} else "image/png")
            else:
                self._enviar("no encontrada", "text/plain", 404)

        def do_POST(self):
            if self.path != "/api/rate":
                return self._enviar("no encontrada", "text/plain", 404)
            try:
                d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                clave, valor = d["clave"], d["valor"]
                assert clave in claves and valor in (0, 1, 2)
            except Exception:
                return self._enviar("petición no válida", "text/plain", 400)
            with CANDADO:
                r = leer()
                r[clave] = valor
                tmp = ratings_path.with_suffix(".tmp")
                tmp.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
                tmp.replace(ratings_path)
            self._enviar('{"ok":true}', "application/json")

    return Manejador


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--puerto", type=int, default=8765)
    p.add_argument("--pool", type=Path, default=AQUI / "pool_b.json")
    p.add_argument("--ratings", type=Path, default=AQUI / "ratings_b.json")
    a = p.parse_args()
    if not a.pool.exists():
        raise SystemExit("ERROR: falta pool_b.json. Ejecuta antes:  python3 experimento_b.py preparar")
    pool = json.loads(a.pool.read_text(encoding="utf-8"))
    print(f"{len(pool)} prendas por puntuar. Abre  http://localhost:{a.puerto}   (Ctrl+C para parar; se guarda al instante)")
    ThreadingHTTPServer(("127.0.0.1", a.puerto), crear_manejador(pool, a.ratings)).serve_forever()


if __name__ == "__main__":
    main()
