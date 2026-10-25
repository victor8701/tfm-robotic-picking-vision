#!/usr/bin/env python3
"""
Prueba de las claves de Instagram, en un minuto y sin esperar a la revista del lunes (25 de octubre de 2026).

Se lanza a mano desde GitHub: pestaña Actions → «Prueba de Instagram» → Run workflow. Solo usa la biblioteca estándar y NUNCA imprime una clave
(ni la dirección con la clave: Windsor, cuando rechaza una clave, la repite en su mensaje de error, así que los mensajes de error no se imprimen).
El resultado sale en español en el resumen de la ejecución (y en el registro).

Comprueba:
  · Windsor: que existe el secreto WINDSOR_API_KEY, que Windsor lo acepta, cuántas publicaciones devuelve para las cuentas de tendencia_fuentes.json
    (con la MISMA petición que hace la tarea semanal) y qué cuentas de las que pedimos no devuelven nada.
"""
import collections
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
WINDSOR_URL = "https://connectors.windsor.ai/instagram_public"
LINEAS: list[str] = []


def dice(txt: str = "") -> None:
    print(txt, flush=True)
    LINEAS.append(txt)


def cuentas_de_instagram() -> list[str]:
    cfg = json.loads((AQUI / "tendencia_fuentes.json").read_text(encoding="utf-8"))["fuentes"]
    return sorted({x["valor"].lstrip("@").lower() for x in cfg if x.get("tipo") == "instagram"})


def prueba_windsor() -> bool:
    dice("## Windsor (lectura de Instagram por el conector oficial)")
    clave = os.environ.get("WINDSOR_API_KEY", "").strip()
    if not clave:
        dice("✘ No llega el secreto WINDSOR_API_KEY: en GitHub → Settings → Secrets and variables → Actions debe existir con ese nombre EXACTO (sin espacios) y el fichero de la tarea debe pasarlo (ya lo pasa).")
        return False
    if len(clave) < 20 or " " in clave or clave.startswith(("'", '"')):
        dice(f"✘ La clave guardada tiene un aspecto raro (longitud {len(clave)}, con espacios o comillas): vuelve a copiarla en Windsor → Data preview → API key, sin comillas ni espacios.")
        return False
    cuentas = cuentas_de_instagram()
    hoy = datetime.now(timezone.utc).date()
    q = {"api_key": clave, "fields": "account_name,media_id,media_type,media_timestamp,media_url,profile_followers_count",
         "date_from": (hoy - timedelta(days=14)).isoformat(), "date_to": hoy.isoformat(), "select_accounts": ",".join(cuentas), "_renderer": "json"}

    def pedir(consulta: dict):
        try:
            with urllib.request.urlopen(urllib.request.Request(WINDSOR_URL + "?" + urllib.parse.urlencode(consulta), headers={"User-Agent": "Mozilla/5.0"}), timeout=180) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode("utf-8", "replace")
            return e.code, ("clave" if "API key" in cuerpo else "otro")
        except Exception as e:  # noqa: BLE001
            return 0, type(e).__name__

    estado, datos = pedir(q)
    dice(f"Petición con las {len(cuentas)} cuentas de las fuentes (igual que la de la revista): respuesta HTTP {estado}.")
    if estado == 400 and datos == "clave":
        dice("✘ Windsor RECHAZA la clave: no es válida. Cópiala de nuevo en Windsor (onboard.windsor.ai → Data preview → API key), sin comillas ni espacios, y guárdala otra vez como secreto WINDSOR_API_KEY.")
        return False
    if estado != 200:
        if estado in (400, 404, 422):
            dice("La petición con la lista completa de cuentas da error: la tarea semanal repite la petición SIN lista y se queda con las cuentas de las fuentes. Pruebo así:")
            q.pop("select_accounts")
            estado, datos = pedir(q)
            dice(f"Petición sin lista de cuentas: respuesta HTTP {estado}.")
        if estado != 200:
            dice(f"✘ Windsor no contesta bien ({estado}, {datos if isinstance(datos, str) else 'respuesta rara'}). Reintenta en unos minutos; si sigue igual, el fallo es de Windsor.")
            return False
    filas = datos.get("data", []) if isinstance(datos, dict) else datos
    por = collections.Counter(str(f.get("account_name") or "").lower() for f in filas or [])
    pedidas = set(cuentas)
    leidas = sorted(c for c in por if c in pedidas)
    dice(f"✔ La clave de Windsor FUNCIONA: {sum(por[c] for c in leidas)} publicaciones de {len(leidas)} cuentas en los últimos 14 días.")
    for c in leidas:
        dice(f"   · {c}: {por[c]}")
    ajenas = sorted(c for c in por if c not in pedidas)
    if ajenas:
        dice(f"(Windsor devuelve además {len(ajenas)} cuentas que no son fuentes: {', '.join(ajenas)}; la tarea las descarta.)")
    dice(f"Cuentas de las fuentes que Windsor NO lee ahora ({len(pedidas) - len(leidas)}): hay 14 dadas de alta durante la prueba gratuita; el resto se leerá con otro plan o con la app de Meta.")
    return True


def main() -> int:
    ok = prueba_windsor()
    dice()
    dice("RESULTADO: " + ("todo bien con Windsor." if ok else "hay algo que arreglar con Windsor (mira el ✘ de arriba)."))
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as f:
            f.write("### Prueba de Instagram\n\n```\n" + "\n".join(LINEAS) + "\n```\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
