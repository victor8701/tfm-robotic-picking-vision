#!/usr/bin/env python3
"""
Compara Florence-2+LoRA (v3, el clasificador propio) contra Claude y Gemini directamente
sobre el mismo esquema y el mismo subconjunto del test -- el dato que responde con numeros
a "no vale usar Claude/Gemini directamente" (ver plan de la sesion / memoria S1).

Alcance deliberadamente pequeno (50 de las 500 filas de test.jsonl, estratificado por
categoria, semilla 42): Gemini vale dinero real por token de imagen y Claude aqui se corre
"a mano" (el propio Claude de esta sesion mirando cada imagen, sin API de pago -- el autor no
quiere gastar aparte de sus suscripciones Pro). No es del mismo orden que las 500 imagenes de
S6 o las 371 de S6.3; se lee como una comparacion indicativa, no como una medida definitiva.

Subcomandos:
    python3 comparar_llm_comercial.py muestra                    # elige y guarda las 50 filas
    python3 comparar_llm_comercial.py gemini                     # llama a Gemini sobre la muestra
    python3 comparar_llm_comercial.py florence                   # corre el adapter v3 local sobre la muestra
    python3 comparar_llm_comercial.py resumen                    # tabla comparativa con lo que haya

Las predicciones "claude" NO las genera este script -- se guardan a mano en
../data/revision_humana/predicciones_claude_comercial.json (mismo formato que las demas,
{id: {categoria, color_primario, grupo_estilo, genero, temporada}}), porque las genera el
propio Claude de la sesion mirando las imagenes, no una llamada de API.
"""
import argparse
import json
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATOS = BASE_DIR / "data" / "revision_humana"
SEMILLA = 42
N_MUESTRA = 50
CAMPOS = ["categoria", "color_primario", "grupo_estilo", "genero", "temporada"]

VOCABULARIO = {
    "categoria": ["ropa_superior", "ropa_inferior", "cuerpo_entero", "abrigo", "calzado", "accesorio"],
    "color_primario": ["blanco", "negro", "gris", "beige", "camel", "navy", "azul", "rojo", "verde",
                       "burdeos", "rosa", "lavanda", "menta", "amarillo", "naranja", "fucsia", "dorado", "plateado"],
    "grupo_estilo": ["casual", "streetwear", "de_vestir", "fiesta_noche", "deportivo", "playa_resort"],
    "genero": ["femenino", "masculino", "neutro"],
    "temporada": ["primavera_verano", "otono_invierno", "todo_el_ano"],
}

PROMPT = f"""Estas viendo una foto de producto de una prenda de ropa (fondo neutro, estilo catalogo).
Devuelve UNICAMENTE un JSON de una linea con estos 5 campos, cada uno con UN valor de su lista cerrada:

categoria: {VOCABULARIO['categoria']}
color_primario (el color dominante de la prenda): {VOCABULARIO['color_primario']}
grupo_estilo (a que ocasion/estetica encaja mas): {VOCABULARIO['grupo_estilo']}
genero (a quien va dirigida la prenda): {VOCABULARIO['genero']}
temporada: {VOCABULARIO['temporada']}

Ejemplo de formato de salida (no copies estos valores, son solo el formato):
{{"categoria":"ropa_superior","color_primario":"negro","grupo_estilo":"streetwear","genero":"masculino","temporada":"otono_invierno"}}

No expliques nada, no uses markdown, solo el JSON."""


def cargar_test():
    return [json.loads(l) for l in open(BASE_DIR / "data" / "test.jsonl", encoding="utf-8")]


def muestreo_estratificado_simple(filas, n_objetivo, rng):
    """Version reducida de la de preparar_dataset_florence2.py: reparte n_objetivo
    proporcionalmente a como aparecen las categorias en filas, sin dejar ninguna a 0 si es
    posible (para que las 6 categorias tengan representacion en una muestra de solo 50)."""
    import collections
    por_cat = collections.defaultdict(list)
    for f in filas:
        por_cat[f["categoria"]].append(f)
    for lista in por_cat.values():
        rng.shuffle(lista)
    cuotas = {c: max(1, round(n_objetivo * len(v) / len(filas))) for c, v in por_cat.items()}
    elegidas = []
    for c, cuota in cuotas.items():
        elegidas.extend(por_cat[c][:cuota])
    rng.shuffle(elegidas)
    return elegidas[:n_objetivo]


def parsear_json_seguro(texto):
    import re
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def cmd_muestra():
    import random
    rng = random.Random(SEMILLA)
    test = cargar_test()
    muestra = muestreo_estratificado_simple(test, N_MUESTRA, rng)
    ruta = DATOS / "muestra_llm_comercial.json"
    ruta.write_text(json.dumps(muestra, ensure_ascii=False, indent=1), encoding="utf-8")
    import collections
    print(f"{len(muestra)} filas -> {ruta}")
    print("Distribucion por categoria:", dict(collections.Counter(f["categoria"] for f in muestra)))


def cmd_gemini(modelo):
    from google import genai
    from PIL import Image

    # Free tier de gemini-3.6-flash: 5 peticiones/MINUTO (no el "1500/dia" que anuncia la
    # pagina de precios en general -- ese es un tope distinto, mas alto, que no protege del
    # limite por minuto). 13s de espera minima entre peticiones deja margen (4.6/min) sin
    # acercarse al limite. Descubierto en el primer intento real: 42/50 fallaron con 429
    # porque el script no esperaba nada entre peticiones -- ver commit.
    #
    # Ademas de 429 (limite propio), el servicio devuelve 503 "high demand" de vez en cuando
    # (ajeno al free tier, le pasa a cualquiera) -- tambien hay que reintentarlo, no solo
    # registrarlo y seguir. Descubierto en el segundo intento: crasheo entero el script sin
    # guardar mas alla de la fila 13 porque solo capturaba ClientError(429), no
    # ServerError(503) -- por eso el bucle de mas abajo captura genai_errors.APIError en
    # general (la clase base de la que cuelgan ClientError y ServerError) y reintenta
    # cualquier 429/5xx igual, en vez de limitarse al 429.
    ESPERA_MIN_S = 13
    REINTENTOS = 4

    clave = Path.home() / ".config" / "gemini" / "api_key"
    client = genai.Client(api_key=clave.read_text().strip())
    muestra = json.loads((DATOS / "muestra_llm_comercial.json").read_text(encoding="utf-8"))
    ruta = DATOS / f"predicciones_{modelo.replace('.', '_').replace('-', '_')}_comercial.json"
    predicciones = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}

    t_total = 0.0
    n_llamadas = 0
    for i, f in enumerate(muestra, 1):
        clave_id = str(f["id"])
        if predicciones.get(clave_id):  # ya conseguida en un intento anterior -- no repetir
            print(f"  [{i}/{len(muestra)}] {f['id']} (ya la tenia)")
            continue
        imagen = Image.open(BASE_DIR / "data" / f["imagen"]).convert("RGB")

        for intento in range(REINTENTOS + 1):
            t0 = time.time()
            try:
                r = client.models.generate_content(model=modelo, contents=[PROMPT, imagen])
                texto = r.text or ""
                break
            except Exception as e:
                # Cualquier excepcion, no solo genai_errors.APIError -- la primera version
                # solo capturaba ClientError(429) y un 503 sin capturar tumbo el proceso
                # entero (ver commit). Mejor fallar blando (reintentar o dejar None en esta
                # fila) que perder el progreso de las demas por un tipo de error nuevo.
                texto = ""
                codigo = getattr(e, "code", None)
                if codigo in (429, 500, 503) and intento < REINTENTOS:
                    print(f"  [{i}/{len(muestra)}] {f['id']} {codigo}, esperando 30s (intento {intento + 1}/{REINTENTOS})...")
                    time.sleep(30)
                    continue
                print(f"  [{i}/{len(muestra)}] {f['id']} ERROR definitivo: {e}")
                break
        n_llamadas += 1
        dt = time.time() - t0
        t_total += dt
        pred = parsear_json_seguro(texto)
        predicciones[clave_id] = pred or {}
        print(f"  [{i}/{len(muestra)}] {f['id']} ({dt:.1f}s) {pred}")
        ruta.write_text(json.dumps(predicciones, ensure_ascii=False, indent=1), encoding="utf-8")  # guarda progreso

        if i < len(muestra):
            time.sleep(max(0, ESPERA_MIN_S - dt))

    print(f"\n{len(predicciones)} predicciones -> {ruta}"
          + (f"  (latencia media llamada {t_total / n_llamadas:.1f}s)" if n_llamadas else ""))


def cmd_florence():
    import torch
    from peft import PeftModel
    from torch.amp import autocast
    from transformers import AutoModelForCausalLM, AutoProcessor
    from PIL import Image

    MODELO_BASE = "microsoft/Florence-2-base"
    ADAPTER = BASE_DIR / "modelos" / "florence2_base_lora_v3"
    muestra = json.loads((DATOS / "muestra_llm_comercial.json").read_text(encoding="utf-8"))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = AutoProcessor.from_pretrained(MODELO_BASE, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(MODELO_BASE, trust_remote_code=True, torch_dtype=torch.float32)
    modelo = PeftModel.from_pretrained(base, ADAPTER).to(device).eval()

    predicciones = {}
    t_total = 0.0
    for i, f in enumerate(muestra, 1):
        imagen = Image.open(BASE_DIR / "data" / f["imagen"]).convert("RGB")
        inp = processor(text="<ATRIBUTOS_PRENDA>", images=imagen, return_tensors="pt").to(device)
        t0 = time.time()
        with torch.no_grad(), autocast(device_type="cuda", dtype=torch.float16, enabled=device == "cuda"):
            gen = modelo.generate(input_ids=inp["input_ids"], pixel_values=inp["pixel_values"],
                                  max_new_tokens=96, num_beams=1)
        dt = time.time() - t0
        t_total += dt
        texto = processor.batch_decode(gen, skip_special_tokens=True)[0].strip()
        pred = parsear_json_seguro(texto)
        predicciones[str(f["id"])] = pred or {}
        if i % 10 == 0:
            print(f"  [{i}/{len(muestra)}] ({dt:.2f}s)")

    ruta = DATOS / "predicciones_florence_v3_comercial.json"
    ruta.write_text(json.dumps(predicciones, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(predicciones)} predicciones -> {ruta}  (latencia media {t_total / len(muestra):.2f}s/imagen, {device})")


def cmd_resumen():
    muestra = {str(f["id"]): f for f in json.loads((DATOS / "muestra_llm_comercial.json").read_text(encoding="utf-8"))}
    modelos = {}
    for nombre, patron in [
        ("Florence-2+LoRA v3 (propio)", "predicciones_florence_v3_comercial.json"),
        ("Claude (sin afinar)", "predicciones_claude_comercial.json"),
        ("Gemini 3.5 Flash-Lite (sin afinar)", "predicciones_gemini_3_5_flash_lite_comercial.json"),
    ]:
        ruta = DATOS / patron
        if ruta.exists():
            modelos[nombre] = json.loads(ruta.read_text(encoding="utf-8"))
    if not modelos:
        raise SystemExit("No hay ninguna prediccion todavia -- corre gemini/florence, o guarda las de claude a mano.")

    ids = sorted(muestra, key=int)
    cab = "".join(f"{n:>30}" for n in modelos)
    print(f"{'campo':<16} {cab}")
    total = {n: 0 for n in modelos}
    for campo in CAMPOS:
        fila = []
        for n, preds in modelos.items():
            usables = [i for i in ids if preds.get(i)]
            ok = sum(1 for i in usables if preds[i].get(campo) == muestra[i][campo])
            total[n] += ok
            fila.append(f"{ok}/{len(usables)} = {ok / len(usables):.0%}" if usables else "-")
        print(f"{campo:<16} " + "".join(f"{v:>30}" for v in fila))
    n5 = 5 * len(ids)
    print(f"{'MEDIA':<16} " + "".join(f"{total[n] / n5:>30.0%}" for n in modelos))
    print(f"\nJSON valido (de {len(ids)}):")
    for n, preds in modelos.items():
        validos = sum(1 for i in ids if preds.get(i))
        print(f"  {n:<30} {validos}/{len(ids)} = {validos / len(ids):.0%}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("comando", choices=["muestra", "gemini", "florence", "resumen"])
    ap.add_argument("--modelo", default="gemini-3.6-flash")
    args = ap.parse_args()

    if args.comando == "muestra":
        cmd_muestra()
    elif args.comando == "gemini":
        cmd_gemini(args.modelo)
    elif args.comando == "florence":
        cmd_florence()
    elif args.comando == "resumen":
        cmd_resumen()
