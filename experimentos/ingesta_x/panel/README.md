# Panel web (Render)

Una página con una URL propia para ver la cola pendiente, disparar la Action ya mismo, y cambiar
el horario (`activo`/`hora_local`/`zona_horaria`) sin entrar en GitHub a mano.

**Importante — qué es esto y qué no es**: la ejecución programada (diaria/horaria, según
`config.json`) ya corre sola dentro de GitHub Actions — eso no depende de que este panel exista
ni de que esté despierto. Este panel es solo una interfaz más cómoda para verla y controlarla
desde una URL, en vez de navegar la web de GitHub. No hace la ingesta más autónoma de lo que ya
era; la hace más cómoda de mirar y tocar.

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

**Aviso del plan gratuito de Render**: si nadie la visita en 15 minutos, el servicio se "duerme"
y la primera visita después tarda ~30-60s en despertar (normal, no está roto). Esto no afecta a
la ejecución programada de GitHub Actions, que es independiente de si este panel está despierto.

## Desarrollo local

```bash
cd experimentos/ingesta_x/panel
pip install -r requirements.txt
PANEL_PASSWORD=loquesea GITHUB_TOKEN=tu_token python3 app.py
```

Abre `http://localhost:5000`.
