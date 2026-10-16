#!/usr/bin/env python3
"""
Prueba de viabilidad de Instagram como fuente de fotos de referentes (16 de octubre de 2026).

Pregunta que solo se contesta con una cuenta de Víctor: ¿deja Meta leer, con una app en modo desarrollo y SIN revisión de Meta, las fotos de OTRAS cuentas profesionales (cantantes,
influencers, marcas) con «Business Discovery»? ¿Devuelve la dirección de la foto (`media_url`) y se puede bajar? (La documentación no lo aclara: ver memoria §6.11.)

Qué hace (solo biblioteca estándar; el token llega por la variable de entorno META_IG_TOKEN, un secreto de GitHub: nunca se imprime):
  1. con el token busca las páginas de Facebook y la cuenta de Instagram profesional enlazada a ellas;
  2. para cada @usuario de la lista pide por Business Discovery sus seguidores, número de publicaciones y las últimas 5, con `media_url`, `permalink`, `timestamp`, `caption`, likes y comentarios;
  3. comprueba que la dirección de la foto se puede bajar (cabecera, sin guardar nada) y resume: cuentas que responden, cuentas personales/no encontradas, errores de permisos.
Uso:  META_IG_TOKEN=… python3 instagram_prueba.py [usuario1 usuario2 …]       (sin argumentos, una lista de ejemplo)
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = "v25.0"
EJEMPLO = ["zara", "gucci", "rosalia.vt", "badbunnypr", "dieworkwear", "zendaya", "casareal", "nike"]
CAMPOS = "username,name,followers_count,media_count,media.limit(5){id,media_type,media_url,thumbnail_url,permalink,timestamp,caption,like_count,comments_count}"


def pedir(ruta: str, params: dict) -> dict:
    url = f"https://graph.facebook.com/{VERSION}/{ruta}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=40) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.load(e).get("error", {"message": f"HTTP {e.code}"})}
        except Exception:  # noqa: BLE001
            return {"error": {"message": f"HTTP {e.code}"}}
    except Exception as e:  # noqa: BLE001
        return {"error": {"message": f"{type(e).__name__}: {e}"}}


def se_puede_bajar(url: str) -> str:
    try:
        req = urllib.request.Request(url, method="GET", headers={"Range": "bytes=0-1023", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return f"sí ({r.status}, {r.headers.get('Content-Type', '?')})"
    except Exception as e:  # noqa: BLE001
        return f"no ({type(e).__name__})"


def main():
    token = os.environ.get("META_IG_TOKEN", "").strip()
    if not token:
        sys.exit("Falta el secreto META_IG_TOKEN.")
    cuentas = [c.lstrip("@") for c in sys.argv[1:]] or EJEMPLO
    paginas = pedir("me/accounts", {"access_token": token, "fields": "name,instagram_business_account"})
    if "error" in paginas:
        sys.exit(f"El token no sirve para listar páginas: {paginas['error'].get('message')} (código {paginas['error'].get('code')})")
    ig = [(p["name"], p["instagram_business_account"]["id"]) for p in paginas.get("data", []) if p.get("instagram_business_account")]
    print(f"Páginas con cuenta de Instagram profesional enlazada: {len(ig)}")
    if not ig:
        sys.exit("Ninguna página tiene una cuenta de Instagram profesional enlazada (hay que pasarla a Creador/Empresa y enlazarla a la página).")
    nombre, ig_id = ig[0]
    print(f"Se usa la página «{nombre}»")
    resumen = {"ok": 0, "sin_media_url": 0, "no_encontrada_o_personal": 0, "permisos": 0, "otros_errores": 0, "foto_bajable": 0, "fotos_probadas": 0}
    for u in cuentas:
        r = pedir(ig_id, {"access_token": token, "fields": f"business_discovery.username({u}){{{CAMPOS}}}"})
        if "error" in r:
            e = r["error"]
            msg = (e.get("message") or "")[:160]
            if e.get("code") in (10, 200, 190, 102) or "permission" in msg.lower():
                resumen["permisos"] += 1
            elif e.get("code") == 110 or "not found" in msg.lower() or "does not exist" in msg.lower() or "business or creator" in msg.lower():
                resumen["no_encontrada_o_personal"] += 1
            else:
                resumen["otros_errores"] += 1
            print(f"  @{u}: ERROR código {e.get('code')}: {msg}")
            continue
        d = r["business_discovery"]
        fotos = (d.get("media") or {}).get("data", [])
        con_url = [m for m in fotos if m.get("media_url") or m.get("thumbnail_url")]
        resumen["ok"] += 1
        if not con_url:
            resumen["sin_media_url"] += 1
        tipos = sorted({m.get("media_type", "?") for m in fotos})
        print(f"  @{u}: OK · {d.get('followers_count')} seguidores · {d.get('media_count')} publicaciones · últimas {len(fotos)} ({', '.join(tipos)}) · con dirección de foto: {len(con_url)}")
        if con_url:
            url = con_url[0].get("media_url") or con_url[0].get("thumbnail_url")
            res = se_puede_bajar(url)
            resumen["fotos_probadas"] += 1
            resumen["foto_bajable"] += res.startswith("sí")
            print(f"      primera foto ({con_url[0].get('media_type')}, {con_url[0].get('timestamp', '')[:10]}): se puede bajar → {res}; enlace {con_url[0].get('permalink')}")
    print("\nRESUMEN:", json.dumps(resumen, ensure_ascii=False))
    resp = os.environ.get("GITHUB_STEP_SUMMARY")
    if resp:
        with open(resp, "a", encoding="utf-8") as f:
            f.write("### Prueba de Instagram (Business Discovery)\n\n```json\n" + json.dumps(resumen, ensure_ascii=False, indent=1) + "\n```\n")


if __name__ == "__main__":
    main()
