"""Convierte tendencia_datos/informe.json en bloques para la pestaña «Cómo vamos» del Artifact (informe_bloques.json)."""
import json, sys
from pathlib import Path
src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/ubuntu22/repos/tfm-robotic-picking-vision/experimentos/analisis_mercado/tendencia_datos/informe.json")
inf = json.loads(src.read_text(encoding="utf-8"))
ESTILO = {"urbano": "Urbano", "geek": "Geek"}
MERC = {"ES": "España", "US": "EEUU", "Biblioteca": "tus fotos aprobadas"}
ORDEN = {"ES": 0, "US": 1, "Biblioteca": 2}
bloques, chicos = [], []
for g in sorted(inf["grupos"], key=lambda g: (ORDEN.get(g["mercado"], 9), g["estilo"], g["temporada"])):
    ref = "muestra de referencia" if g["mercado"] == "Biblioteca" else g["temporada"]
    if g["fotos"] < 5:
        chicos.append(f"{ESTILO.get(g['estilo'], g['estilo'])} · {MERC.get(g['mercado'], g['mercado'])} · {ref} ({g['fotos']})")
        continue
    filas = [{"etiqueta": f["tipo"], "valor": round(f["cuota"] * 100), "nota": f"{f['fotos']} fotos"} for f in g["prendas"] if f["cuota"] is not None][:8]
    pocos = [f"{f['tipo']} ({f['fotos']})" for f in g["prendas"] if f["pocos_datos"]]
    fuentes = ", ".join(f"{k} {v}" for k, v in list(g["fuentes"].items())[:6])
    b = {"tipo": "barras", "titulo": f"{ESTILO.get(g['estilo'], g['estilo'])} · {MERC.get(g['mercado'], g['mercado'])} · {ref}",
         "texto": f"{g['fotos']} fotos, {g['fotos_con_prenda']} con alguna prenda visible. Cuota = % de fotos (con más peso las populares y recientes) en que sale la prenda. Fuentes: {fuentes}.",
         "unidad": "%", "max": 100, "filas": filas}
    if not filas:
        b["texto"] += " Ninguna prenda llega a 5 fotos: no hay cifras."
    if pocos:
        b["nota"] = "Sin cifra por tener menos de 5 fotos: " + ", ".join(pocos[:10]) + "."
    bloques.append(b)
if chicos:
    bloques.append({"tipo": "texto", "titulo": "Grupos con menos de 5 fotos", "texto": "Sin informe por tener muy pocas fotos: " + "; ".join(chicos) + "."})
Path("informe_bloques.json").write_text(json.dumps({"generado": inf["generado"], "bloques": bloques}, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(bloques), "bloques")
