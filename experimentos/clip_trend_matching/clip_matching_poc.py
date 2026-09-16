#!/usr/bin/env python3
"""
POC de matching semantico prenda <-> tendencia (Estado_arte.md, seccion 7).

Implementa literalmente la formula de 7.2:

    score(SKU, tendencia) = score_semantico + beta * boost_estilo

donde score_semantico es la similitud coseno CLIP entre la imagen de la
prenda y el texto de la tendencia, y boost_estilo vale 1.0 si el
grupo_estilo de la prenda coincide con el grupo_estilo_detectado de la
tendencia (mismo vocabulario cerrado de 6 valores, seccion 3.4.1).

No hace falta registrar las imagenes en ningun sitio: el script lee
TODO el contenido de una carpeta (por defecto muestras/, o la que se
indique con --muestras) y le pone cualquier nombre de archivo vale. El
grupo_estilo de cada imagen lo infiere el propio CLIP por zero-shot
(comparando la imagen contra los 6 grupos posibles) -- en el sistema
real ese campo lo fija marketing en el ERP (Estado_arte.md S3.5), aqui
se infiere solo para no tener que etiquetar nada a mano en este POC.

--muestras acepta una ruta corta relativa a la carpeta de este script:
'streetwear' y '/streetwear' apuntan los dos a clip_trend_matching/streetwear.
Una ruta absoluta que ya exista (p.ej. una carpeta fuera del proyecto)
se sigue usando tal cual.
"""
import argparse
import json
from pathlib import Path

import open_clip
import torch
from PIL import Image

BASE_DIR = Path(__file__).parent
EXTENSIONES_VALIDAS = {".jpg", ".jpeg", ".png", ".webp"}

# Vocabulario cerrado de Grupo de estilo (Estado_arte.md S3.4.1), con una
# frase descriptiva por grupo para que la clasificacion zero-shot de CLIP
# funcione mejor que comparando solo contra la palabra suelta.
GRUPOS_ESTILO = {
    "Casual": "ropa casual de diario",
    "Streetwear": "ropa de estilo urbano, streetwear",
    "De vestir": "ropa elegante y formal, de vestir",
    "Fiesta/Noche": "ropa de fiesta o para salir de noche",
    "Deportivo": "ropa deportiva",
    "Playa/Resort": "ropa veraniega de playa o resort",
}

BETA_BOOST_ESTILO = 0.1  # mismo valor que Estado_arte.md, seccion 7.2


def parse_args():
    parser = argparse.ArgumentParser(
        description="POC de matching semantico CLIP prenda <-> tendencia (Estado_arte.md S7)."
    )
    parser.add_argument(
        "--muestras", "-m", type=str, default="muestras",
        help="Carpeta con las imagenes a comparar (por defecto: muestras/). "
             "Si no es una ruta absoluta que ya exista, se busca dentro de la "
             "carpeta de este script -- '--muestras streetwear' y "
             "'--muestras /streetwear' son equivalentes y ambas apuntan a "
             "clip_trend_matching/streetwear. Se leen TODAS las imagenes que "
             "haya dentro (.jpg/.jpeg/.png/.webp); el nombre de archivo puede "
             "ser cualquiera, solo se usa para mostrarlo.",
    )
    parser.add_argument(
        "--tendencias", "-t", type=Path, default=BASE_DIR / "tendencias_ejemplo.json",
        help="JSON con las tendencias a evaluar (por defecto: tendencias_ejemplo.json).",
    )
    return parser.parse_args()


def resolver_carpeta_muestras(valor):
    """Resuelve el argumento --muestras a una ruta real.

    Si 'valor' es una ruta absoluta que ya existe, se usa tal cual (para
    poder apuntar a carpetas fuera del proyecto, como antes). En
    cualquier otro caso -- incluido un valor con '/' inicial, tipo
    '/streetwear' -- se interpreta como relativo a la carpeta de este
    script, para poder escribir solo el nombre corto de la carpeta.
    """
    p = Path(valor)
    if p.is_absolute() and p.is_dir():
        return p
    return BASE_DIR / valor.lstrip("/\\")


def listar_imagenes(carpeta):
    if not carpeta.is_dir():
        raise SystemExit(f"ERROR: la carpeta '{carpeta}' no existe.")
    rutas = sorted(
        p for p in carpeta.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONES_VALIDAS
    )
    if not rutas:
        raise SystemExit(
            f"ERROR: no hay imagenes ({', '.join(sorted(EXTENSIONES_VALIDAS))}) en '{carpeta}'."
        )
    return rutas


def nombre_legible(ruta):
    return ruta.stem.replace("_", " ").replace("-", " ").strip().capitalize()


def cargar_modelo():
    print("Cargando CLIP (ViT-B-32, pesos openai)... (primera vez tarda por la descarga)")
    # "-quickgelu": los pesos originales de OpenAI se entrenaron con QuickGELU;
    # cargarlos con la variante GELU estandar (el default de open_clip) da un
    # mismatch de activacion silencioso que degrada la calidad del embedding.
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32-quickgelu", pretrained="openai"
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32-quickgelu")
    model.eval()
    return model, preprocess, tokenizer


def encodear_imagenes(model, preprocess, rutas):
    """Carga y encodea las imagenes validas. Devuelve (rutas_validas, vectores),
    saltandose con un aviso cualquier archivo que no se pueda abrir como imagen."""
    rutas_validas = []
    tensores = []
    for r in rutas:
        try:
            img = Image.open(r).convert("RGB")
        except Exception as e:
            print(f"  (aviso) no se pudo leer '{r.name}', se omite: {e}")
            continue
        tensores.append(preprocess(img))
        rutas_validas.append(r)

    if not tensores:
        raise SystemExit("ERROR: ninguna imagen de la carpeta se pudo leer correctamente.")

    lote = torch.stack(tensores)
    with torch.no_grad():
        v = model.encode_image(lote)
        v = v / v.norm(dim=-1, keepdim=True)
    return rutas_validas, v


def encodear_textos(model, tokenizer, textos):
    tokens = tokenizer(textos)
    with torch.no_grad():
        v = model.encode_text(tokens)
        v = v / v.norm(dim=-1, keepdim=True)
    return v


def inferir_grupos_estilo(model, tokenizer, v_prendas):
    """Clasificacion zero-shot: a cada prenda le asigna el grupo de estilo
    cuya frase descriptiva tiene mayor similitud coseno con su imagen."""
    etiquetas = list(GRUPOS_ESTILO.keys())
    v_grupos = encodear_textos(model, tokenizer, list(GRUPOS_ESTILO.values()))

    asignados = []
    for v_prenda in v_prendas:
        similitudes = v_grupos @ v_prenda
        idx = int(similitudes.argmax())
        asignados.append(etiquetas[idx])
    return asignados


def calcular_score(v_prenda, v_tendencia, grupo_prenda, grupos_tendencia):
    score_semantico = float((v_prenda @ v_tendencia).item())
    boost = BETA_BOOST_ESTILO if grupo_prenda in grupos_tendencia else 0.0
    return score_semantico, boost, score_semantico + boost


def main():
    args = parse_args()
    carpeta_muestras = resolver_carpeta_muestras(args.muestras)
    rutas_imagenes = listar_imagenes(carpeta_muestras)
    tendencias = json.loads(args.tendencias.read_text(encoding="utf-8"))

    print(f"\n{len(rutas_imagenes)} imagen(es) encontradas en '{carpeta_muestras}':")
    for r in rutas_imagenes:
        print(f"  - {r.name}")

    model, preprocess, tokenizer = cargar_modelo()

    rutas_imagenes, v_prendas = encodear_imagenes(model, preprocess, rutas_imagenes)
    grupos_prendas = inferir_grupos_estilo(model, tokenizer, v_prendas)

    print("\nGrupo de estilo detectado automaticamente por CLIP (zero-shot):")
    for ruta, grupo in zip(rutas_imagenes, grupos_prendas):
        print(f"  - {nombre_legible(ruta):<35} -> {grupo}")

    for tendencia in tendencias:
        print(f"\n{'=' * 78}")
        print(f"TENDENCIA: {tendencia['descripcion'][:90]}...")
        print(f"grupo_estilo_detectado: {tendencia['grupo_estilo_detectado']}  "
              f"(intensidad={tendencia['intensidad']})")
        print("=" * 78)

        v_tendencia = encodear_textos(model, tokenizer, [tendencia["descripcion"]])[0]

        resultados = []
        for ruta, v_prenda, grupo_prenda in zip(rutas_imagenes, v_prendas, grupos_prendas):
            s_sem, boost, s_total = calcular_score(
                v_prenda, v_tendencia, grupo_prenda, tendencia["grupo_estilo_detectado"]
            )
            resultados.append((ruta, grupo_prenda, s_sem, boost, s_total))

        resultados.sort(key=lambda r: r[4], reverse=True)

        for rank, (ruta, grupo_prenda, s_sem, boost, s_total) in enumerate(resultados, 1):
            marca = "*" if boost > 0 else " "
            print(
                f"{rank}. {marca} {nombre_legible(ruta):<35} "
                f"(grupo={grupo_prenda:<13}) "
                f"score_semantico={s_sem:+.4f}  boost={boost:.2f}  total={s_total:+.4f}"
            )


if __name__ == "__main__":
    main()
