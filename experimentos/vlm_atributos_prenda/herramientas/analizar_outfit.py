#!/usr/bin/env python3
"""
Prototipo de looks completos: foto de una persona con varias prendas ->
atributos POR PRENDA + estilo del outfit.

El clasificador afinado (adapter LoRA) solo ha visto prendas sueltas, asi que
sobre una foto entera de calle degrada de forma estructural (ver README). Este
script lo evita en tres pasos:

  1. DETECTAR:
       - Personas y calzado/accesorios: Florence-2-base nativo, adapter
         DESACTIVADO, <OD> sobre la foto entera (vocabulario libre).
       - Prenda superior/inferior/abrigo/vestido: **detector real (v3 del script,
         2026-09-21)**, un YOLOv8-seg afinado sobre DeepFashion2 (13 categorias,
         Apache-2.0, `Bingsu/adetailer` en HuggingFace) -- ver DF2_REPO/MAPA_DF2 mas
         abajo. Sustituye lo que hacian las guardas heuristicas de la v1/v2 del
         script (grounding de una frase + torso geometrico, ver abajo), que se
         quedan solo como red de seguridad para lo que el detector no cubre (nunca
         se activan si DeepFashion2 ya encontro la prenda de esa persona).
       - Red de seguridad (v1/v2 del script, ahora residual): <CAPTION_TO_PHRASE_
         GROUNDING> con UNA sola frase ("shirt", "pants") sobre el recorte de la
         persona, y si la caja de la prenda superior no es plausible, torso
         geometrico (entre el 15% de la altura de la persona y el inicio de la
         prenda inferior) -- marcado como origen "geometrico" para poder contar
         cuantas veces hace falta (debería ser casi nunca ya).
  2. CLASIFICAR (adapter ACTIVADO): cada recorte de prenda pasa por
       <ATRIBUTOS_PRENDA>, exactamente igual que en el entrenamiento -- esto NO
       cambia con el detector nuevo, sigue siendo el mismo Florence-2+LoRA.
  3. AGREGAR: el estilo del outfit es el voto de los grupo_estilo de sus prendas,
       ponderado por la raiz del tamano relativo de cada recorte.

Guardas de la version 2 del script (anadidas tras ver los fallos de la primera pasada
sobre las 19 fotos de calle, asi que las cifras sobre ellas son EN MUESTRA): caja de
"prenda superior" que abarca a toda la persona -> torso geometrico; personas de fondo
por debajo del 12% del area de la principal -> descartadas; calzado solo si el par esta
junto; "pants" solo si empieza en la mitad baja; primer plano (persona >= 85% de la
foto) sin buscar pantalon ni torso geometrico. Siguen activas, ya que la red de
seguridad de grounding todavia las necesita cuando se dispara.

Aviso de versionado (mismo que ya avisa la memoria S8.3): "v2"/"v3" aqui son
iteraciones del SCRIPT de deteccion, no tienen nada que ver con "v1".."v5" del adapter
clasificador (--adapter mas abajo) -- son dos numeraciones independientes que
coinciden por casualidad.

La categoria de cada prenda se toma de la deteccion (DeepFashion2 o <OD>) cuando
existe; se guarda tambien la del clasificador para poder medir el desacuerdo entre
ambas (ver "coincide_categoria").

Uso:
    python3 analizar_outfit.py --carpeta ../data/fotos_calle --salida-json outfits.json \
        --salida-imagenes /ruta/anotadas [--cache detecciones_cache.json]
"""
import argparse
import collections
import json
import math
import re
import time
from pathlib import Path

import torch
from huggingface_hub import hf_hub_download
from PIL import Image, ImageDraw, ImageFont
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoProcessor
from ultralytics import YOLO

BASE_DIR = Path(__file__).parent.parent
MODELO_BASE = "microsoft/Florence-2-base"
TASK_ATRIBUTOS = "<ATRIBUTOS_PRENDA>"
PERSONAS = {"man", "woman", "person", "boy", "girl"}

# etiqueta de <OD> (vocabulario libre de Florence-2) -> categoria de nuestro esquema
# (mismas cabeceras que esquema_atributos.md). Se ignoran a proposito rostro, gafas,
# reloj, movil...: no son prendas de la taxonomia. El orden importa (primera que casa).
# Nota (v3 del script, 2026-09-21): de aqui abajo, solo se usan de verdad las dos
# ultimas filas (calzado, accesorio) -- ropa_superior/inferior/abrigo/cuerpo_entero
# ahora las detecta DeepFashion2 (ver MAPA_DF2), mucho mas fiable que este regex sobre
# el vocabulario libre de <OD>. Se dejan las filas igual (no se borran) porque
# documentan lo que <OD> es capaz de nombrar y sirven de referencia si algun dia hace
# falta lo contrario (DeepFashion2 no reconoce calzado/accesorios en absoluto, asi que
# ahi <OD> se queda siendo la unica fuente).
MAPA_OD = [
    (r"dress|gown|jumpsuit|romper", "cuerpo_entero"),
    (r"jacket|coat|blazer|parka|windbreaker", "abrigo"),
    (r"shirt|\btop\b|blouse|sweater|sweatshirt|hoodie|jumper|cardigan|waistcoat|\bvest\b", "ropa_superior"),
    (r"trouser|pant|jean|short|skirt|legging|tights", "ropa_inferior"),
    (r"footwear|shoe|boot|sneaker|sandal|heel|slipper", "calzado"),
    (r"\bhat\b|\bcap\b|beanie|bag|backpack|purse|\btie\b|scarf|\bbelt\b", "accesorio"),
]
CATEGORIAS_DE_OD = {"calzado", "accesorio"}  # el resto las cubre DeepFashion2, ver detectar()

# Detector real (v3 del script): YOLOv8s-seg afinado sobre DeepFashion2 (491K imagenes,
# 13 categorias, licencia Apache-2.0), pesos de terceros -- no se commitea al repo
# (igual que microsoft/Florence-2-base tampoco se commitea), se descarga y cachea de
# HuggingFace la primera vez. DeepFashion2 NO tiene calzado ni accesorios (es un
# dataset de prendas puestas en el torso/piernas), de ahi que <OD> se siga usando para
# esas dos categorias.
DF2_REPO = "Bingsu/adetailer"
DF2_ARCHIVO = "deepfashion2_yolov8s-seg.pt"
MAPA_DF2 = {
    "short_sleeved_shirt": "ropa_superior", "long_sleeved_shirt": "ropa_superior",
    "vest": "ropa_superior", "sling": "ropa_superior",
    "short_sleeved_outwear": "abrigo", "long_sleeved_outwear": "abrigo",
    "shorts": "ropa_inferior", "trousers": "ropa_inferior", "skirt": "ropa_inferior",
    "short_sleeved_dress": "cuerpo_entero", "long_sleeved_dress": "cuerpo_entero",
    "vest_dress": "cuerpo_entero", "sling_dress": "cuerpo_entero",
}

COLOR_CATEGORIA = {
    "ropa_superior": (0, 120, 255), "ropa_inferior": (0, 170, 90), "cuerpo_entero": (220, 40, 140),
    "abrigo": (240, 140, 0), "calzado": (130, 60, 200), "accesorio": (90, 90, 90),
}


# ---------------------------------------------------------------- geometria

def area(c):
    return max(0, c[2] - c[0]) * max(0, c[3] - c[1])


def interseccion(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def iou(a, b):
    inter = interseccion(a, b)
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def union(cajas):
    return [min(c[0] for c in cajas), min(c[1] for c in cajas), max(c[2] for c in cajas), max(c[3] for c in cajas)]


def con_margen(caja, im, frac=0.08):
    w, h = caja[2] - caja[0], caja[3] - caja[1]
    return [max(0, caja[0] - frac * w), max(0, caja[1] - frac * h),
            min(im.width, caja[2] + frac * w), min(im.height, caja[3] + frac * h)]


def sin_solapes(items, umbral=0.5):
    """NMS simple: a igual categoria, se queda con la caja mas grande."""
    items = sorted(items, key=lambda it: -area(it["caja"]))
    fuera = []
    for it in items:
        if all(not (o["categoria"] == it["categoria"] and iou(o["caja"], it["caja"]) > umbral) for o in fuera):
            fuera.append(it)
    return fuera


def persona_de(caja, personas):
    """Indice de la persona que contiene la prenda (>=60% de su area); si hay
    varias, la de centro horizontal mas cercano (personas solapadas)."""
    cx = (caja[0] + caja[2]) / 2
    candidatas = [(abs(cx - (p["caja"][0] + p["caja"][2]) / 2), k) for k, p in enumerate(personas)
                  if interseccion(caja, p["caja"]) >= 0.6 * area(caja)]
    return min(candidatas)[1] if candidatas else None


# ---------------------------------------------------------------- Florence-2

class Motor:
    def __init__(self, adapter, ruta_cache=None):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.amp = self.device == "cuda"
        base = AutoModelForCausalLM.from_pretrained(MODELO_BASE, trust_remote_code=True, torch_dtype=torch.float32)
        self.modelo = PeftModel.from_pretrained(base, adapter).to(self.device).eval()
        self.proc = AutoProcessor.from_pretrained(MODELO_BASE, trust_remote_code=True)
        self.ruta_cache = Path(ruta_cache) if ruta_cache else None
        self.cache = json.loads(self.ruta_cache.read_text()) if self.ruta_cache and self.ruta_cache.exists() else {}

    def guardar_cache(self):
        if self.ruta_cache:
            self.ruta_cache.write_text(json.dumps(self.cache), encoding="utf-8")

    def _generar(self, imagen, texto, beams, max_tokens):
        inp = self.proc(text=texto, images=imagen, return_tensors="pt").to(self.device)
        with torch.no_grad(), torch.autocast(device_type="cuda", dtype=torch.float16, enabled=self.amp):
            gen = self.modelo.generate(input_ids=inp["input_ids"], pixel_values=inp["pixel_values"],
                                       max_new_tokens=max_tokens, num_beams=beams)
        return gen

    def base(self, imagen, tarea, texto="", clave=None, beams=3, max_tokens=512):
        """Capacidad nativa de Florence-2 (adapter desactivado). `clave` permite
        cachear la salida para iterar sobre la logica de despues sin recalcularla."""
        if clave and clave in self.cache:
            return self.cache[clave]
        with self.modelo.disable_adapter():
            gen = self._generar(imagen, tarea + texto, beams, max_tokens)
        crudo = self.proc.batch_decode(gen, skip_special_tokens=False)[0]
        salida = self.proc.post_process_generation(crudo, task=tarea, image_size=imagen.size)[tarea]
        if clave:
            self.cache[clave] = salida
        return salida

    def atributos(self, imagen):
        """Clasificador afinado (adapter activado)."""
        gen = self._generar(imagen, TASK_ATRIBUTOS, 1, 96)
        texto = self.proc.batch_decode(gen, skip_special_tokens=True)[0].strip()
        m = re.search(r"\{.*\}", texto, re.DOTALL)
        try:
            return json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            return None


# ---------------------------------------------------------------- pipeline

def categoria_de_etiqueta(etiqueta):
    for patron, cat in MAPA_OD:
        if re.search(patron, etiqueta.lower()):
            return cat
    return None


def cargar_detector_df2():
    """Descarga (y cachea localmente, via huggingface_hub) el YOLOv8s-seg afinado
    sobre DeepFashion2 -- misma idea que AutoModelForCausalLM.from_pretrained para
    Florence-2-base: pesos de terceros, no se commitean al repo."""
    ruta = hf_hub_download(repo_id=DF2_REPO, filename=DF2_ARCHIVO)
    return YOLO(ruta)


def detectar_df2(detector_df2, im, min_conf):
    """Prenda superior/inferior/abrigo/vestido via DeepFashion2 -- una sola pasada
    sobre la foto entera, igual que <OD> para personas. Misma forma de diccionario que
    prendas_od (categoria/caja/origen) para que el resto del pipeline no note la
    diferencia; guarda ademas la etiqueta cruda de DeepFashion2 y la confianza."""
    r = detector_df2.predict(im, conf=min_conf, verbose=False)[0]
    prendas = []
    for box in r.boxes:
        etiqueta = detector_df2.names[int(box.cls)]
        prendas.append({
            "deteccion": etiqueta, "categoria": MAPA_DF2[etiqueta],
            "caja": [float(v) for v in box.xyxy[0]], "origen": "deepfashion2",
            "confianza": round(float(box.conf), 2),
        })
    return prendas


def detectar(motor, detector_df2, im, foto, args):
    od = motor.base(im, "<OD>", clave=f"{foto}|<OD>")
    H = im.height
    personas = [{"etiqueta": l, "caja": [float(v) for v in b]}
                for l, b in zip(od["labels"], od["bboxes"]) if l in PERSONAS]
    personas = [p for p in personas if (p["caja"][3] - p["caja"][1]) >= args.min_alto_persona * H]
    personas = sorted(personas, key=lambda p: -area(p["caja"]))
    depurados = []
    for p in personas:
        if all(iou(p["caja"], q["caja"]) < 0.6 for q in depurados):
            depurados.append(p)
    # fuera las personas de fondo: una persona mucho mas pequena que la principal
    # (desenfocada, cortada por el borde) solo aporta cajas de prenda ruidosas
    if depurados:
        depurados = [p for p in depurados if area(p["caja"]) >= args.min_area_rel * area(depurados[0]["caja"])]
    personas = depurados[: args.max_personas]
    if not personas:  # sin ninguna persona detectada: se trata la foto entera como una persona
        personas = [{"etiqueta": "imagen_completa", "caja": [0.0, 0.0, float(im.width), float(im.height)]}]

    # calzado/accesorio de <OD> (unica fuente, DeepFashion2 no los tiene) + prenda
    # superior/inferior/abrigo/cuerpo_entero de DeepFashion2 (fuente principal ahora;
    # ver aviso de MAPA_OD/CATEGORIAS_DE_OD mas arriba).
    prendas_od = []
    for l, b in zip(od["labels"], od["bboxes"]):
        cat = categoria_de_etiqueta(l)
        if cat in CATEGORIAS_DE_OD:
            prendas_od.append({"deteccion": l, "categoria": cat, "caja": [float(v) for v in b], "origen": "od"})
    prendas_od += detectar_df2(detector_df2, im, args.min_conf_df2)
    return personas, prendas_od


def par_de_calzado(calzado, pw, ph):
    """Un par de zapatos esta junto: parte del calzado mas grande y suma solo los que
    mantienen la union por debajo del 25% del alto de la persona (descarta calzado de
    otra persona o falsas detecciones en la pierna)."""
    calzado = sorted(calzado, key=lambda c: -area(c["caja"]))
    grupo = [calzado[0]]
    for c in calzado[1:]:
        u = union([g["caja"] for g in grupo] + [c["caja"]])
        if u[2] - u[0] <= pw and u[3] - u[1] <= 0.25 * ph:
            grupo.append(c)
    return {"deteccion": f"footwear (x{len(grupo)})", "categoria": "calzado",
            "caja": union([g["caja"] for g in grupo]), "origen": "od"}


def prendas_de_persona(motor, im, foto, k, persona, propias):
    px1, py1, px2, py2 = persona["caja"]
    pw, ph = px2 - px1, py2 - py1
    primer_plano = area(persona["caja"]) >= 0.85 * im.width * im.height  # selfie / retrato: no hay cuerpo entero

    calzado = [p for p in propias if p["categoria"] == "calzado"]
    prendas = [p for p in propias if p["categoria"] != "calzado"]
    if calzado:
        prendas.append(par_de_calzado(calzado, pw, ph))
    prendas = sin_solapes(prendas)
    hay = lambda *cats: any(p["categoria"] in cats for p in prendas)

    caja_rec = con_margen(persona["caja"], im, 0.05)
    ox, oy = caja_rec[:2]
    rec = im.crop(caja_rec)

    def grounding(frase):
        g = motor.base(rec, "<CAPTION_TO_PHRASE_GROUNDING>", frase,
                       clave=f"{foto}|P{k}|{[round(v) for v in caja_rec]}|{frase}")
        if not g["bboxes"]:
            return None
        b = g["bboxes"][0]
        return [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy]

    # prenda inferior: si <OD> no vio ni pantalon/falda ni vestido. Debe empezar en la mitad
    # baja de la persona y no ocuparla casi entera (grounding sobre "pants" sin pantalon
    # devuelve a veces la persona completa). En un primer plano no hay piernas: se omite.
    if not hay("ropa_inferior", "cuerpo_entero") and not primer_plano:
        caja = grounding("pants")
        if (caja and caja[1] >= py1 + 0.30 * ph and (caja[3] - caja[1]) <= 0.75 * ph
                and (caja[2] - caja[0]) >= 0.25 * pw):
            prendas.append({"deteccion": "pants (grounding)", "categoria": "ropa_inferior", "caja": caja, "origen": "grounding"})

    # prenda superior: <OD> casi nunca la nombra -> grounding de "shirt" con comprobacion de
    # plausibilidad (ancho, altura, posicion y que no sea la persona entera); si no pasa,
    # torso geometrico. En un primer plano el torso puede estar en cualquier parte: solo
    # se acepta el grounding (sin posicion) y no hay reserva geometrica.
    if not hay("ropa_superior", "cuerpo_entero"):
        caja = grounding("shirt")
        origen = "grounding"
        plausible = (caja and (caja[2] - caja[0]) >= 0.40 * pw
                     and 0.10 * ph <= (caja[3] - caja[1]) <= (0.80 if primer_plano else 0.55) * ph
                     and (primer_plano or py1 + 0.10 * ph <= (caja[1] + caja[3]) / 2 <= py1 + 0.65 * ph))
        if not plausible:
            y_ini = py1 + 0.15 * ph
            inferiores = [p["caja"][1] for p in prendas if p["categoria"] == "ropa_inferior"]
            y_fin = min(inferiores) if inferiores else py1 + 0.55 * ph
            caja, origen = ([px1, y_ini, px2, y_fin], "geometrico") if y_fin - y_ini >= 0.12 * ph and not primer_plano else (None, None)
        redundante = caja and any(p["categoria"] == "abrigo" and iou(p["caja"], caja) > 0.5 for p in prendas)
        if caja and not redundante and area(caja) > 0.02 * area(persona["caja"]):
            prendas.append({"deteccion": "shirt (grounding)" if origen == "grounding" else "torso (geometrico)",
                            "categoria": "ropa_superior", "caja": caja, "origen": origen})
    return prendas


def clasificar_prendas(motor, im, prendas, args):
    for pr in prendas:
        caja = con_margen(pr["caja"], im, 0.08)
        pr["caja"] = [round(v, 1) for v in pr["caja"]]
        if min(caja[2] - caja[0], caja[3] - caja[1]) < args.min_lado_recorte:
            pr["atributos"], pr["coincide_categoria"] = None, None
            continue
        a = motor.atributos(im.crop(caja))
        pr["atributos"] = a
        pr["coincide_categoria"] = bool(a) and a.get("categoria") == pr["categoria"]
    return prendas


def agregar_outfit(persona, prendas):
    pa = max(area(persona["caja"]), 1)
    votos = {c: collections.Counter() for c in ("grupo_estilo", "color_primario", "genero", "temporada")}
    for pr in prendas:
        a = pr.get("atributos")
        if not a:
            continue
        peso = math.sqrt(min(area(pr["caja"]) / pa, 1.0))
        for c in votos:
            votos[c][a.get(c)] += peso
    total = sum(votos["grupo_estilo"].values()) or 1
    top = lambda c: votos[c].most_common(1)[0][0] if votos[c] else None
    return {
        "estilo_outfit": {k: round(v / total, 2) for k, v in votos["grupo_estilo"].most_common()},
        "paleta": [k for k, _ in votos["color_primario"].most_common(3)],
        "genero": top("genero"),
        "temporada": top("temporada"),
    }


def dibujar(im, personas_res, ruta):
    lienzo = im.copy()
    d = ImageDraw.Draw(lienzo)
    fuente = ImageFont.load_default(size=max(14, im.width // 55))
    for k, pr in enumerate(personas_res):
        d.rectangle(pr["caja"], outline=(255, 255, 255), width=3)
        estilos = ", ".join(f"{e} {v:.0%}" for e, v in list(pr["outfit"]["estilo_outfit"].items())[:2])
        d.text((pr["caja"][0] + 4, pr["caja"][1] + 2), f"P{k}: {estilos}", fill=(255, 255, 0), font=fuente,
               stroke_width=2, stroke_fill=(0, 0, 0))
        for p in pr["prendas"]:
            col = COLOR_CATEGORIA.get(p["categoria"], (0, 0, 0))
            d.rectangle(p["caja"], outline=col, width=4)
            a = p.get("atributos") or {}
            marca = {"od": "", "deepfashion2": "+", "grounding": "~", "geometrico": "*"}[p["origen"]]
            txt = f"{marca}{p['categoria']}|{a.get('color_primario')}|{a.get('grupo_estilo')}"
            d.text((p["caja"][0] + 3, p["caja"][1] + 3), txt, fill=col, font=fuente, stroke_width=2, stroke_fill=(255, 255, 255))
    lienzo.save(ruta, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--carpeta", required=True, help="Carpeta plana con las fotos (.jpg/.png).")
    ap.add_argument("--salida-json", required=True)
    ap.add_argument("--salida-imagenes", help="Si se indica, guarda cada foto con cajas y atributos dibujados "
                                              "(sin marca = <OD>, + = DeepFashion2, ~ = grounding, * = torso geometrico).")
    ap.add_argument("--cache", help="JSON donde cachear la salida de <OD> y grounding (para iterar la logica sin recalcular; "
                                     "no cachea DeepFashion2, que ya es barato -- una pasada por foto, sin CPU de Florence-2).")
    ap.add_argument("--adapter", default=str(BASE_DIR / "modelos" / "florence2_base_lora_v3"),
                    help="v3 tiene el mejor acuerdo medio con la revision humana (ver memoria S11.4/S11.6); "
                         "los resultados de la memoria S8 se midieron con v1, sin repetir todavia con este default.")
    ap.add_argument("--min-conf-df2", type=float, default=0.3,
                    help="Confianza minima del detector DeepFashion2 (YOLOv8-seg) para aceptar una caja.")
    ap.add_argument("--max-personas", type=int, default=3)
    ap.add_argument("--min-area-rel", type=float, default=0.12,
                    help="Area minima de una persona respecto a la principal (descarta fondo desenfocado o cortado por el borde).")
    ap.add_argument("--min-alto-persona", type=float, default=0.22,
                    help="Altura minima de una persona, como fraccion del alto de la foto (descarta fondo lejano).")
    ap.add_argument("--min-lado-recorte", type=int, default=40)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    fotos = sorted(p for p in Path(args.carpeta).expanduser().iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    if args.limite:
        fotos = fotos[: args.limite]
    motor = Motor(args.adapter, args.cache)
    print("Cargando detector DeepFashion2 (YOLOv8s-seg, se descarga la primera vez)...")
    detector_df2 = cargar_detector_df2()
    if args.salida_imagenes:
        Path(args.salida_imagenes).mkdir(parents=True, exist_ok=True)

    resultados = {}
    for n, f in enumerate(fotos, 1):
        t0 = time.time()
        im = Image.open(f).convert("RGB")
        personas, prendas_od = detectar(motor, detector_df2, im, f.stem, args)
        propias = collections.defaultdict(list)
        for pr in prendas_od:
            k = persona_de(pr["caja"], personas)
            if k is not None:
                propias[k].append(pr)
        personas_res = []
        for k, persona in enumerate(personas):
            prendas = clasificar_prendas(motor, im, prendas_de_persona(motor, im, f.stem, k, persona, propias[k]), args)
            personas_res.append({"caja": [round(v, 1) for v in persona["caja"]], "prendas": prendas,
                                 "outfit": agregar_outfit(persona, prendas)})
        motor.guardar_cache()
        resultados[f.stem] = {"n_personas": len(personas_res), "personas": personas_res}
        if args.salida_imagenes:
            dibujar(im, personas_res, Path(args.salida_imagenes) / f"{f.stem}.jpg")
        resumen = "; ".join(f"P{k}: {'+'.join(p['categoria'][:6] for p in pr['prendas'])}" for k, pr in enumerate(personas_res))
        print(f"[{n}/{len(fotos)}] {f.stem} ({time.time() - t0:.0f}s) {resumen}", flush=True)

    Path(args.salida_json).write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Guardado en {args.salida_json}")


if __name__ == "__main__":
    main()
