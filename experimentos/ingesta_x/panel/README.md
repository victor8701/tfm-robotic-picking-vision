# Panel web (Render)

Una sola app con una URL propia. Tres partes:

- **Galería (`/`)**: clasificar fotos por estilo, corregir con un toque, eje de ocasión
  (fiesta/deportivo/playa/arreglado), subir fotos propias, eliminar/restaurar. Sustituye por
  completo al artefacto de claude.ai que se usaba antes — mismos datos, migrados una vez.
- **Buscar en X (`/buscar-x`)**: pedir una búsqueda (estilo, ocasión opcional, texto tuyo o
  predeterminado o automático) para encontrar publicaciones reales de X y añadirlas a la cola de
  descarga. Dispara el workflow "Buscar en X", que busca con **Tavily** (capa gratuita, sin
  tarjeta), acotado a x.com/twitter.com, y aplica un filtro mecánico simple (lista de palabras a
  evitar tipo "cosplay"/"resultado del partido", más quedarse con las URLs con forma de
  publicación real) antes de encolarlas. No pasa por Claude: se probó primero con Claude Code
  filtrando (sin ninguna herramienta, autenticado con tu suscripción) y aun así consumía saldo
  de crédito de pago de la API — confirmado con el dueño de la cuenta que solo tiene el plan Pro
  mensual, sin saldo cargado, así que se quitó del todo para que esto sea gratis de verdad. El
  filtro mecánico es más flojo que el de un LLM (puede colar algo de ruido); lo que sobre se
  descarta a mano con el botón ✕ de la galería. El estado de cada búsqueda
  (pendiente/buscando/completado/error) se actualiza aquí según avanza el workflow.
- **Automatización de X (`/automatizacion`)**: ver la cola pendiente, disparar la Action ya
  mismo, cambiar el horario (`activo`/`hora_local`/`zona_horaria`) sin entrar en GitHub a mano.

**De dónde vienen los datos**: no hay base de datos de verdad (el plan gratuito de Render no
tiene disco persistente). Las clasificaciones viven en `data/clasificaciones.json` y las fotos
en `static/fotos/`, ambos dentro de este mismo repo de GitHub — el panel los lee y escribe con
la API de GitHub (misma que ya usaba para `config.json`), así que cada cambio en la galería
genera un commit real en el repo.

**Importante — qué es esto y qué no es**: la ejecución programada de X (diaria/horaria, según
`config.json`) ya corre sola dentro de GitHub Actions — eso no depende de que este panel exista
ni de que esté despierto. La pestaña de automatización es solo una interfaz más cómoda para
verla y controlarla desde una URL. La galería, en cambio, sí depende de que el panel esté
despierto (es la única forma de ver/editar las fotos ahora).

## Qué necesitas hacer tú una vez (esto no lo puede hacer Claude por ti)

Desplegar en Render y generar el token de GitHub requiere tu cuenta — son credenciales tuyas,
no algo que se pueda automatizar desde aquí.

1. **Genera un token de GitHub** (una vez): [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)
   (token "fine-grained") → dale acceso solo al repo `tfm-robotic-picking-vision`, con permisos
   **Contents: Read and write** y **Actions: Read and write**. Copia el token (solo se ve una
   vez). Si esa URL no te lleva directo, es Settings → Developer settings → Personal access
   tokens → Fine-grained tokens → Generate new token.
2. **Crea cuenta en Render** (gratis, sin tarjeta): [render.com](https://render.com) → conecta tu
   GitHub.
3. **New → Blueprint** → elige este repo → Render detecta `render.yaml` solo. Te pedirá los dos
   valores marcados `sync: false`:
   - `GITHUB_TOKEN`: el token del paso 1.
   - `PANEL_PASSWORD`: la contraseña que quieras para entrar al panel (es una URL pública en el
     plan gratuito de Render, sin contraseña la vería cualquiera que la encontrara).
4. Deploy. Render te da una URL tipo `https://ingesta-x-panel.onrender.com` — esa es la app.
5. **Para que funcione "Buscar en X"**, añade un secreto a este repo (Settings → Secrets and
   variables → **Actions** → New repository secret — es un secreto de GitHub, no de Render):
   `TAVILY_API_KEY`, gratis, sin tarjeta, 1000 búsquedas/mes — créala en
   [tavily.com](https://tavily.com), plan "Researcher"/free (ojo, no el plan "Pay as you go" que
   sale primero: ese sí es de pago), y copia la API key (empieza por `tvly-`).

   El repo tiene también permisos que revisar en el token de GitHub del paso 1: en
   [github.com/settings/tokens?type=beta](https://github.com/settings/tokens?type=beta) →
   abre el token → en **Repository permissions** confirma que **Contents** y **Actions** están
   en **Read and write** (no "Read-only") — sin esto, la app guarda todo en silencio y no avisa
   más que con un "no se pudo guardar" genérico si el token es antiguo; ahora sí debería avisar
   con el motivo real que dé GitHub.

   Sin `TAVILY_API_KEY`, las búsquedas se quedan en estado "error" — el panel te mostrará el
   motivo exacto en el paso correspondiente en vez de fallar en silencio.

**Aviso del plan gratuito de Render**: si nadie la visita en 15 minutos, el servicio se "duerme"
y la primera visita después tarda ~30-60s en despertar (normal, no está roto). Esto no afecta a
la ejecución programada de GitHub Actions, que es independiente de si este panel está despierto.

## Desarrollo local

```bash
cd experimentos/ingesta_x/panel
pip install -r requirements.txt
PANEL_PASSWORD=loquesea GITHUB_TOKEN=tu_token python3 app.py
```

Abre `http://localhost:5000`. Sin `GITHUB_TOKEN` válido verás la galería vacía (no puede leer
`data/clasificaciones.json` del repo) pero la app no se cae — sirve para probar la interfaz.

## Si cambiaste la contraseña alguna vez en el chat

Si en algún momento pegaste `PANEL_PASSWORD` en una conversación con Claude, trátala como
comprometida: cámbiala en Render → el servicio → *Environment* → `PANEL_PASSWORD`, y guarda
(Render redepliega solo con el valor nuevo).
