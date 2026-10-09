#!/usr/bin/env python3
"""
Prueba del «profesor»: ¿puede un modelo abierto grande de lenguaje y visión (Qwen-VL de 7 000 a 8 000 millones de parámetros) estimar el estampado, el tejido y la forma
de una prenda mejor que «decir siempre lo más frecuente» y que la capa pequeña sobre CLIP? Se mide en Kaggle (GPU), sin entrenar nada, sobre uno o varios datasets
privados que prepara `preparar_dataset.py` (un `manifiesto.json` y un `fotos.zip` cada uno).

Para cada modelo y cada configuración se guarda `pred_<modelo>_<configuración>.jsonl` (una línea por prenda, con la respuesta cruda y la ya traducida al vocabulario
de Víctor) y al final `resumen.json`. Las prendas de Fashionpedia llevan su etiqueta, así que el acierto se calcula aquí mismo; las de Víctor se miden en local
(`evaluar_profesor.py`) porque sus etiquetas no se suben.

Configuraciones:
  recorte      solo el recorte de la prenda (lo mismo que ve CLIP)
  foto         la foto entera con la prenda marcada en una caja roja + el recorte (el modelo ve cómo cae la prenda sobre el cuerpo)
  foto_razona  igual que «foto», pero primero describe en pocas frases y luego contesta (solo en una submuestra)
  tipo_recorte / tipo_foto  el modelo NO sabe qué prenda es: elige su tipo de una lista numerada (las 13 categorías de Fashionpedia, o los 29 tipos de Víctor)
  usable_a / usable_b  ¿el recuadro es una prenda bien visible o un recorte inservible (solo piel, manos, fondo, trozo cortado, diminuto o borroso)? a = criterio normal, b = más estricto
  semanal      la del análisis semanal: tipo entre los 29 con el recorte (24 de 38 con las etiquetas de Víctor) y luego, sabiendo ese tipo, estampado, tejido y forma con la foto
               entera + el recorte (la forma sube de 11 a 14 de 23 con la foto), con la guía v3
  profesor     etiquetado en dos pasos: primero, con la foto entera, elige el tipo entre los 29 de Víctor; luego, sobre el recorte y sabiendo ese tipo, estampado, tejido y forma
               (el recorte basta para el estampado: 74 % frente a 70 % con la foto en Fashionpedia, y es más barato)

Uso en Kaggle: lo sube y lo lanza `kaggle_ops.py`. En local, con un generador falso para probar la lógica:  PROFESOR_FALSO=1 PROFESOR_ENTRADA=<carpeta> PROFESOR_SALIDA=<carpeta> python3 kernel_profesor.py
"""
import json
import os
import random
import re
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

MODO = "completo"      # «humo»: 8 prendas, un modelo y la configuración «recorte» (para depurar); «completo»: todo
MODELOS = [("qwen25vl7b", "Qwen/Qwen2.5-VL-7B-Instruct"), ("qwen3vl8b", "Qwen/Qwen3-VL-8B-Instruct")]
CONFIGS = [  # (nombre, imágenes, razona, máximo de prendas, tarea)
    ("recorte", "recorte", False, None, "atributos"),
    ("foto", "foto", False, None, "atributos"),
    ("foto_razona", "foto", True, 80, "atributos"),
    ("tipo_recorte", "recorte", False, None, "tipo"),
    ("tipo_foto", "foto", False, None, "tipo"),
    ("profesor", "foto", False, None, "profesor"),
    ("profesor_v2", "foto", False, None, "profesor"),
    ("semanal", "recorte", False, None, "semanal"),
    ("usable_a", "foto", False, None, "usable"),
    ("usable_b", "foto", False, None, "usable"),
]
PARTE = None           # (k, n): procesa solo las prendas k, k+n, k+2n… (para repartir una tanda larga entre varios kernels)
SOLO = None            # lista de nombres de configuración a correr (None = todas); sirve para repetir solo una parte
MODELOS_SOLO = None    # ídem para los modelos, p. ej. ["qwen3vl8b"]
LOTE = 6
PRESUPUESTO_S = 4 * 3600
ENTRADA = Path(os.environ.get("PROFESOR_ENTRADA", "/kaggle/input"))
SALIDA = Path(os.environ.get("PROFESOR_SALIDA", "/kaggle/working"))
TEMPORAL = Path(os.environ.get("PROFESOR_TEMPORAL", "/kaggle/temp"))

# respuesta del modelo (inglés, una palabra) -> vocabulario de Víctor
OPC = {
    "pattern": {"plain": "liso", "striped": "rayas", "plaid": "cuadros", "graphic": "gráfico / dibujo", "text_logo": "texto / logo", "camouflage": "camuflaje", "other": "otro"},
    "fabric": {"denim": "denim (vaquero)", "leather": "cuero / vinilo", "cotton": "algodón", "knit": "punto", "fleece": "felpa / polar", "technical": "técnico / impermeable",
               "corduroy": "pana", "velvet": "terciopelo", "satin": "seda / satén", "lace": "tul / encaje", "linen": "lino", "unknown": "no se distingue"},
    "fit": {"oversized": "oversized / baggy", "regular": "regular", "slim": "ajustada", "cropped": "corta / cropped", "n/a": "no aplica"},
}
CAMPO = {"pattern": "estampado", "fabric": "tejido", "fit": "forma"}
TIPOS_FP = [("shirt, blouse", "a shirt or blouse"), ("top, t-shirt, sweatshirt", "a t-shirt, top or sweatshirt"), ("sweater", "a sweater"), ("cardigan", "a cardigan"), ("jacket", "a jacket"),
            ("vest", "a vest"), ("pants", "a pair of pants"), ("shorts", "a pair of shorts"), ("skirt", "a skirt"), ("coat", "a coat"), ("dress", "a dress"), ("jumpsuit", "a jumpsuit"), ("cape", "a cape")]
TIPOS_V = [("Camiseta manga corta", "a short-sleeved t-shirt"), ("Camiseta de tirantes", "a sleeveless tank top"), ("Camiseta manga larga", "a long-sleeved t-shirt"), ("Top", "a crop top"),
           ("Camisa", "a button-up shirt"), ("Polo", "a polo shirt"), ("Sudadera", "a crewneck sweatshirt without a hood"), ("Hoodie", "a hoodie with a hood"), ("Jersey", "a knitted sweater"),
           ("Chaleco sin mangas", "a sleeveless vest"), ("Chaqueta", "a jacket"), ("Americana", "a blazer"), ("Abrigo", "a long coat"), ("Plumas", "a puffer jacket"),
           ("Pantalón", "a pair of long trousers"), ("Falda", "a skirt"), ("Short", "a pair of shorts"), ("Legging/Malla", "leggings"), ("Vestido", "a dress"), ("Mono", "a jumpsuit"),
           ("Zapatillas deportivas", "a pair of sports sneakers"), ("Zapatillas casual/lifestyle", "a pair of casual canvas shoes"), ("Zapatos de vestir", "a pair of dress shoes"),
           ("Zapatos de tacón", "a pair of high heels"), ("Sandalias", "a pair of sandals"), ("Botas", "a pair of boots"), ("Bolso", "a handbag"), ("Riñonera", "a fanny pack"),
           ("Gorra/Gorro/Sombrero", "a cap or a hat")]
FORMATO = ('{"pattern": <plain|striped|plaid|graphic|text_logo|camouflage|other>, "fabric": <denim|leather|cotton|knit|fleece|technical|corduroy|velvet|satin|lace|linen|unknown>, '
           '"fit": <oversized|regular|slim|cropped|n/a>}')
GUIA = ("Guidelines:\n"
        "- pattern: plain = one solid color (tags or tiny logos do not count); graphic = illustration, photo or large artwork; text_logo = mainly words or a brand logo; "
        "other = floral, geometric, dots, animal print, etc.\n"
        "- fabric: leather also means vinyl or latex; knit = visibly knitted or ribbed (sweaters, crochet); fleece = sweatshirt or hoodie material, or polar fleece; "
        "technical = shiny nylon or polyester (windbreakers, puffers, tracksuits); cotton = ordinary t-shirt jersey or woven cotton; denim = jeans fabric; "
        "unknown only if the fabric really cannot be judged.\n"
        "- fit: how the garment sits on the body. oversized = clearly roomy, baggy, dropped shoulders or wide legs; regular = standard cut; slim = close to the body; "
        "cropped = hem clearly above the waist or hip, or a very short length; n/a = shoes, bags and hats.")
# v2: lo que se vio con las etiquetas de Víctor (7 fallos de tejido): una sudadera o una capucha de jersey normal es «algodón» para él, y «felpa / polar» solo el polar de pelo
GUIA_V2 = (GUIA.replace("fleece = sweatshirt or hoodie material, or polar fleece;", "fleece = only fuzzy polar fleece (a sweatshirt or hoodie in ordinary cotton jersey is cotton);")
           .replace("cotton = ordinary t-shirt jersey or woven cotton;", "cotton = ordinary t-shirt jersey, woven cotton, and sweatshirt or hoodie jersey;"))
assert GUIA_V2 != GUIA
# v3 (la del análisis semanal): v2 + «liso» admite logos y estampados pequeños (en las etiquetas de Víctor, 2 prendas lisas salieron «texto / logo»); «texto / logo» y «gráfico» son lo llamativo
GUIA_V3 = (GUIA_V2.replace("plain = one solid color (tags or tiny logos do not count);", "plain = one solid color (small chest or sleeve logos, tags and tiny prints still count as plain);")
           .replace("graphic = illustration, photo or large artwork;", "graphic = illustration, photo or large artwork that covers a notable part of the garment;")
           .replace("text_logo = mainly words or a brand logo;", "text_logo = prominent words, a slogan or a big brand logo;"))
assert GUIA_V3 != GUIA_V2


def prompt(variante: str, razona: bool, tipo_en: str, guia: str = GUIA) -> str:
    if variante == "foto":
        intro = "Image 1 is a photo of a person; the red box marks the garment of interest. Image 2 is a close-up crop of that same garment."
    else:
        intro = "The image is a close-up crop of one garment worn by a person."
    if razona:
        cola = "First write at most three short sentences about the print, the material and how the garment fits on the body. Then write the answer on a new line as: JSON: " + FORMATO
    else:
        cola = "Answer with ONLY this JSON object and nothing else: " + FORMATO
    return f"You are an expert fashion analyst. {intro} The garment of interest is {tipo_en}.\n{cola}\n{guia}"


def lista_tipos(origen: str, tarea: str):
    return TIPOS_FP if (origen == "fashionpedia" and tarea == "tipo") else TIPOS_V


def prompt_tipo(variante: str, origen: str, tarea: str = "tipo") -> str:
    lista = lista_tipos(origen, tarea)
    if variante == "foto":
        intro = "Image 1 is a photo of a person; the red box marks one garment. Image 2 is a close-up crop of that same garment."
    else:
        intro = "The image is a close-up crop of one garment worn by a person."
    opciones = "\n".join(f"{i}. {en}" for i, (_, en) in enumerate(lista, 1))
    return f"You are an expert fashion analyst. {intro} Which of these is that garment?\n{opciones}\nAnswer with ONLY the number."


MOTIVOS = ("clear", "cut_off", "tiny_or_blurry", "not_garment", "multiple_garments", "occluded")


def prompt_usable(nombre: str) -> str:
    base = ("You are checking crops for a fashion trend study. Image 1 is a photo of a person; the red box marks a candidate garment. Image 2 is a close-up crop of that box. "
            "Is the box a clearly visible, identifiable garment worn by a person, and not just skin, hands, hair, background, a tiny, blurred or cut-off fragment, or a box that mixes several garments?")
    if nombre.endswith("b"):
        base += " Answer yes only if you could confidently tell the garment type, its fabric and how it fits from the crop."
    return base + (' Answer ONLY a JSON object: {"usable": "yes" or "no", "reason": one of ' + " | ".join(MOTIVOS) + "}")


def parsear_usable(texto: str) -> dict:
    m = re.search(r"\{[^{}]*\}", texto or "")
    try:
        d = json.loads(m.group(0)) if m else {}
    except Exception:
        d = {}
    u = str(d.get("usable", "")).strip().lower()
    r = str(d.get("reason", "")).strip().lower()
    return {"usable": u if u in ("yes", "no") else None, "motivo": r if r in MOTIVOS else None}


def parsear_tipo(texto: str, origen: str, tarea: str = "tipo") -> str | None:
    lista = lista_tipos(origen, tarea)
    m = re.search(r"\d+", texto or "")
    return lista[int(m.group(0)) - 1][0] if m and 1 <= int(m.group(0)) <= len(lista) else None


def parsear(texto: str) -> dict:
    """Devuelve {'estampado':…, 'tejido':…, 'forma':…} en el vocabulario de Víctor (None si el valor no es válido)."""
    objetos = re.findall(r"\{[^{}]*\}", texto or "")
    d = {}
    if objetos:
        try:
            d = json.loads(objetos[-1])
        except Exception:
            d = {k: m.group(1) for k in OPC if (m := re.search(rf'"{k}"\s*:\s*"([^"]+)"', objetos[-1]))}
    salida = {}
    for k, tabla in OPC.items():
        v = str(d.get(k, "")).strip().lower().replace(" ", "_").replace("-", "_")
        v = {"na": "n/a", "not_applicable": "n/a", "text": "text_logo", "logo": "text_logo"}.get(v, v)
        salida[CAMPO[k]] = tabla.get(v)
    return salida


def ajustar(im, minimo=336, maximo=768):
    """Escala para que el lado largo quede entre minimo y maximo (ni diminuto ni enorme)."""
    from PIL import Image
    largo = max(im.size)
    s = maximo / largo if largo > maximo else (minimo / largo if largo < minimo else 1.0)
    return im if s == 1.0 else im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)


def imagenes_de(it: dict, variante: str):
    from PIL import Image, ImageDraw
    im = Image.open(it["ruta"]).convert("RGB")
    W, H = im.size
    x1, y1, x2, y2 = it["caja"]
    bw, bh = x2 - x1, y2 - y1
    recorte = ajustar(im.crop((max(0, int(x1 - .06 * bw)), max(0, int(y1 - .06 * bh)), min(W, int(x2 + .06 * bw)), min(H, int(y2 + .06 * bh)))))
    if variante == "recorte":
        return [recorte]
    foto = im.copy()
    ImageDraw.Draw(foto).rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=max(3, int(max(W, H) / 150)))
    return [ajustar(foto, minimo=0), recorte]


def cargar_items():
    """Busca todos los manifiestos en la entrada, extrae sus fotos.zip y devuelve la lista de prendas con la ruta de su foto."""
    items = []
    for man in sorted(ENTRADA.rglob("manifiesto.json")):
        carpeta = man.parent
        destino = TEMPORAL / f"fotos_{carpeta.name}"
        if not destino.exists():
            destino.mkdir(parents=True)
            zips = list(carpeta.rglob("fotos.zip"))
            if zips:
                with zipfile.ZipFile(zips[0]) as z:
                    z.extractall(destino)
            else:   # Kaggle ya descomprimió el zip
                destino = next((d for d in carpeta.rglob("*") if d.is_dir() and any(d.glob("*.jpg"))), carpeta)
        for it in json.loads(man.read_text(encoding="utf-8")):
            ruta = destino / it["foto"]
            if not ruta.exists():
                ruta = next(iter(carpeta.rglob(it["foto"])), ruta)
            it["ruta"] = str(ruta)
            items.append(it)
    return items


def liberar():
    """Libera memoria; quien llama debe haber soltado antes sus referencias (m = None)."""
    import gc
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass


def generar_real(m, proc, textos, imagenes, max_new):
    import torch
    entrada = proc(text=textos, images=imagenes, return_tensors="pt", padding=True).to(m.device)
    with torch.inference_mode():
        sal = m.generate(**entrada, max_new_tokens=max_new, do_sample=False)
    sal = sal[:, entrada["input_ids"].shape[1]:]
    return proc.batch_decode(sal, skip_special_tokens=True, clean_up_tokenization_spaces=False)


def cargar_modelo(nombre_hf, items):
    """Carga el modelo repartido entre las GPU (fp16, o bf16, o 4 bits si no cabe) y comprueba con dos prendas que contesta algo con sentido."""
    import torch
    from transformers import AutoProcessor
    try:
        from transformers import AutoModelForImageTextToText as AutoM
    except ImportError:
        from transformers import AutoModelForVision2Seq as AutoM
    n = torch.cuda.device_count()
    print(f"GPU: {n} x {torch.cuda.get_device_name(0) if n else '—'}", flush=True)
    intentos = ([("fp16", torch.float16, False), ("bf16", torch.bfloat16, False), ("fp16-4bit", torch.float16, True)] if n >= 2
                else [("fp16-4bit", torch.float16, True), ("bf16-4bit", torch.bfloat16, True)])
    proc = AutoProcessor.from_pretrained(nombre_hf)
    proc.tokenizer.padding_side = "left"
    for etiqueta, dtype, cuatro in intentos:
        m = None
        try:
            kw = {"device_map": "auto"}
            if n >= 2:
                kw["max_memory"] = {i: "13GiB" for i in range(n)}
            if cuatro:
                from transformers import BitsAndBytesConfig
                kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype)
            t0 = time.time()
            try:
                m = AutoM.from_pretrained(nombre_hf, dtype=dtype, **kw)
            except TypeError:
                m = AutoM.from_pretrained(nombre_hf, torch_dtype=dtype, **kw)
            m.eval()
            print(f"{nombre_hf} cargado en {time.time() - t0:.0f} s ({etiqueta})", flush=True)
            prueba = items[:2]
            textos, imgs = [], []
            for it in prueba:
                ims = imagenes_de(it, "recorte")
                textos.append(proc.apply_chat_template([{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt("recorte", False, it["tipo_en"])}]}],
                                                       tokenize=False, add_generation_prompt=True))
                imgs += ims
            crudos = generar_real(m, proc, textos, imgs, 70)
            print("prueba de humo:", [c[:100] for c in crudos], flush=True)
            if any(sum(v is not None for v in parsear(c).values()) >= 2 for c in crudos):
                return m, proc, etiqueta
            print(f"[{etiqueta}] la respuesta no tiene sentido; se prueba la siguiente variante", flush=True)
        except Exception:
            print(f"[{etiqueta}] falló:", traceback.format_exc()[-1500:], flush=True)
        m = None
        liberar()
    raise RuntimeError(f"No se pudo cargar {nombre_hf}")


def correr_config(m, proc, items, cfg, nombre_modelo, generador, t_inicio):
    nombre, variante, razona, maximo, tarea = cfg
    guia = GUIA_V2 if nombre.endswith("_v2") else GUIA
    sel = list(items)
    if maximo and len(sel) > maximo:
        sel = random.Random(5).sample(sel, maximo)
    if PARTE:
        sel = sel[PARTE[0]::PARTE[1]]
    if MODO == "humo":
        sel = sel[:8]
    ruta = SALIDA / f"pred_{nombre_modelo}_{nombre}.jsonl"
    t0 = time.time()
    with open(ruta, "w", encoding="utf-8") as f:
        for i in range(0, len(sel), LOTE):
            if time.time() - t_inicio > PRESUPUESTO_S:
                print("presupuesto de tiempo agotado; se corta aquí", flush=True)
                break
            lote = sel[i:i + LOTE]
            def pedir(textos_prompt, max_new, var=variante):
                textos, imgs = [], []
                for it, texto_prompt in zip(lote, textos_prompt):
                    ims = imagenes_de(it, var)
                    contenido = [{"type": "image"} for _ in ims] + [{"type": "text", "text": texto_prompt}]
                    textos.append(proc.apply_chat_template([{"role": "user", "content": contenido}], tokenize=False, add_generation_prompt=True) if proc is not None else "")
                    imgs += ims
                return generador(m, proc, textos, imgs, max_new)
            if tarea == "usable":
                crudos = pedir([prompt_usable(nombre) for _ in lote], 40)
                for it, crudo in zip(lote, crudos):
                    f.write(json.dumps({"id": it["id"], "origen": it["origen"], "modelo": nombre_modelo, "config": nombre, "crudo": crudo, **parsear_usable(crudo)}, ensure_ascii=False) + "\n")
            elif tarea == "semanal":   # producción: si falla un lote, se repite prenda a prenda y lo que no se pueda queda en blanco
                def pedir_seguro(textos_prompt, max_new, var):
                    try:
                        return pedir(textos_prompt, max_new, var)
                    except Exception:
                        print("lote fallido; se repite prenda a prenda:", traceback.format_exc()[-300:], flush=True)
                        salida = []
                        for it, tp in zip(lote, textos_prompt):
                            try:
                                ims = imagenes_de(it, var)
                                contenido = [{"type": "image"} for _ in ims] + [{"type": "text", "text": tp}]
                                t = proc.apply_chat_template([{"role": "user", "content": contenido}], tokenize=False, add_generation_prompt=True) if proc is not None else ""
                                salida.append(generador(m, proc, [t], ims, max_new)[0])
                            except Exception:
                                salida.append("")
                        return salida
                crudos_t = pedir_seguro([prompt_tipo("recorte", it["origen"], "profesor") for it in lote], 8, "recorte")
                tipos = [parsear_tipo(c, it["origen"], "profesor") for c, it in zip(crudos_t, lote)]
                en = dict(TIPOS_V)
                crudos_a = pedir_seguro([prompt("foto", False, en.get(t, "a garment"), GUIA_V3) for t in tipos], 70, "foto")
                for it, ct, t, ca in zip(lote, crudos_t, tipos, crudos_a):
                    f.write(json.dumps({"id": it["id"], "origen": it["origen"], "modelo": nombre_modelo, "config": nombre, "crudo_tipo": ct, "tipo29": t, "crudo": ca, **parsear(ca)}, ensure_ascii=False) + "\n")
            elif tarea == "profesor":   # paso 1: tipo entre los 29 de Víctor; paso 2: estampado, tejido y forma sabiendo ese tipo
                crudos_t = pedir([prompt_tipo(variante, it["origen"], "profesor") for it in lote], 8)
                tipos = [parsear_tipo(c, it["origen"], "profesor") for c, it in zip(crudos_t, lote)]
                en = dict(TIPOS_V)
                crudos_a = pedir([prompt("recorte", False, en.get(t, "a garment"), guia) for t in tipos], 70, "recorte")
                for it, ct, t, ca in zip(lote, crudos_t, tipos, crudos_a):
                    f.write(json.dumps({"id": it["id"], "origen": it["origen"], "modelo": nombre_modelo, "config": nombre, "crudo_tipo": ct, "tipo29": t, "crudo": ca, **parsear(ca)}, ensure_ascii=False) + "\n")
            else:
                crudos = pedir([prompt_tipo(variante, it["origen"]) if tarea == "tipo" else prompt(variante, razona, it["tipo_en"], guia) for it in lote], 230 if razona else (8 if tarea == "tipo" else 70))
                for it, crudo in zip(lote, crudos):
                    resultado = {"tipo": parsear_tipo(crudo, it["origen"])} if tarea == "tipo" else parsear(crudo)
                    f.write(json.dumps({"id": it["id"], "origen": it["origen"], "modelo": nombre_modelo, "config": nombre, "crudo": crudo, **resultado}, ensure_ascii=False) + "\n")
            f.flush()
            if (i // LOTE) % 10 == 0:
                print(f"  {nombre_modelo}/{nombre}: {min(i + LOTE, len(sel))}/{len(sel)} ({(time.time() - t0) / (i + len(lote)):.1f} s por prenda)", flush=True)
    return ruta, time.time() - t0


def resumen_fashionpedia(ruta, items_por_id):
    """Acierto por atributo y recall por clase, para las prendas de Fashionpedia (las únicas con etiqueta dentro del kernel)."""
    res = {}
    filas = [json.loads(linea) for linea in open(ruta, encoding="utf-8")]
    ok_t = n_t = 0
    for r in filas:
        it = items_por_id[r["id"]]
        if "tipo" in r and it["origen"] == "fashionpedia":
            n_t += 1
            ok_t += r["tipo"] == it["tipo"]
    if n_t:   # configuración de tipo: no lleva estampado ni forma
        res["tipo"] = {"acierto": [ok_t, n_t]}
        return res
    for campo in ("estampado", "forma"):
        ok = n = 0
        por_clase = {}
        for r in filas:
            it = items_por_id[r["id"]]
            if it["origen"] != "fashionpedia" or not it.get(campo):
                continue
            n += 1
            acierto = r.get(campo) == it[campo]
            ok += acierto
            c = por_clase.setdefault(it[campo], [0, 0])
            c[0] += acierto
            c[1] += 1
        if n:
            recalls = [a / b for a, b in por_clase.values() if b]
            res[campo] = {"acierto": [ok, n], "recall_medio": round(sum(recalls) / len(recalls), 3), "por_clase": por_clase}
    return res


def main():
    t_inicio = time.time()
    SALIDA.mkdir(parents=True, exist_ok=True)
    TEMPORAL.mkdir(parents=True, exist_ok=True)
    falso = os.environ.get("PROFESOR_FALSO") == "1"
    if not falso:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers>=4.57", "accelerate", "bitsandbytes"], check=False)
    items = cargar_items()
    print(f"{len(items)} prendas ({sum(i['origen'] == 'victor' for i in items)} de Víctor, {sum(i['origen'] == 'fashionpedia' for i in items)} de Fashionpedia)", flush=True)
    por_id = {i["id"]: i for i in items}
    resumen = {"modo": MODO, "prendas": len(items), "ejecuciones": []}
    modelos = MODELOS[:1] if MODO == "humo" else [m_ for m_ in MODELOS if not MODELOS_SOLO or m_[0] in MODELOS_SOLO]
    configs = CONFIGS[:1] if MODO == "humo" else [c for c in CONFIGS if not SOLO or c[0] in SOLO]
    for nombre_modelo, nombre_hf in modelos:
        m = proc = None
        try:
            if falso:
                generador = lambda m, proc, textos, imgs, mx: ['{"pattern": "plain", "fabric": "cotton", "fit": "oversized"}'] * len(textos)   # noqa: E731
                etiqueta = "falso"
            else:
                m, proc, etiqueta = cargar_modelo(nombre_hf, items)
                generador = generar_real
            for cfg in configs:
                try:
                    ruta, seg = correr_config(m, proc, items, cfg, nombre_modelo, generador, t_inicio)
                    r = {"modelo": nombre_modelo, "carga": etiqueta, "config": cfg[0], "segundos": round(seg), "fashionpedia": resumen_fashionpedia(ruta, por_id)}
                    resumen["ejecuciones"].append(r)
                    print(json.dumps(r, ensure_ascii=False)[:900], flush=True)
                except Exception:
                    print(f"[{nombre_modelo}/{cfg[0]}] falló:", traceback.format_exc()[-1500:], flush=True)
        except Exception:
            print(f"[{nombre_modelo}] falló:", traceback.format_exc()[-1500:], flush=True)
        finally:
            m = proc = None
            liberar()
    (SALIDA / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nLISTO en {(time.time() - t_inicio) / 60:.0f} min", flush=True)


if __name__ == "__main__":
    main()
