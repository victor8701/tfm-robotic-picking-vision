# Guía de la app de Meta

_Para que la revista lea las 68 cuentas de Instagram sin pagar Windsor. Cada paso se marca con un toque y dice qué deberías ver._

Versión del 25 de octubre de 2026. Hay una versión con casillas que se marcan con un toque en el Artifact «Guía app de Meta».

## De qué va

Instagram deja leer las publicaciones públicas de cuentas de empresa o creador a través de una «app» que se registra gratis en Meta, la empresa dueña de Instagram. La app no hace nada por sí sola. Sirve para que Meta te dé un **token**, una contraseña larga con la que la tarea del lunes pide las fotos.

Hoy Windsor lee solo 14 cuentas y su prueba gratuita acaba hacia el 23 de noviembre. Con la app de Meta la revista leería las 68.

Tú haces seis cosas: registrarte, crear la app, sacar el token, comprobar que Meta nos deja leer, hacer el token duradero y probarlo con las 68 cuentas. Yo ya he preparado el resto: la tarea semanal, una prueba de un clic y el aviso en la revista si el token caduca.

> **Lo que no puedo prometerte.** Meta describe este método (Business Discovery) pero no dice si una app privada «en desarrollo» puede leer cuentas ajenas sin pasar su revisión. Es probable, no está confirmado. La parte 3b lo decide con la primera prueba. Si Meta dice que no, habrás gastado unos 40 minutos y la revista sigue leyendo con Windsor. Nada de esta guía puede estropear la revista de los lunes.

> **Regla de oro.** El token es una contraseña. Pégalo solo en la casilla «Secret» de GitHub (parte 3b), nunca en el chat conmigo, en un correo o en un documento. Si lo pegas donde no debes, avísame: se anula quitando la app en Facebook, en Configuración → Apps y sitios web.

## Antes de empezar

- **Un ordenador con Chrome.** Con el móvil se puede, pero es incómodo: hay que activar «Sitio de escritorio» en el navegador.
- **Tu móvil a mano.** Meta puede mandarte un código por SMS.
- **Facebook abierto con la cuenta que administra la página «Tendencias Moda»,** la que usas en Meta Business Suite. Y **GitHub abierto como victor8701** en el mismo navegador.
- **Entre 45 y 60 minutos.** No hace falta dejar ningún ordenador encendido en casa: la tarea del lunes corre en los servidores de GitHub.
- **Si Meta te pide algo que no sale aquí** (pagar, verificar tu empresa, subir documentos, revisar la app), para y mándame una captura. Nada de eso hace falta.
- **Si un paso no sale como dice la guía,** pulsa «No me sale» en ese paso y mándame una captura por el chat. Yo veo qué pasos tienes marcados.

## Enlaces que vas a usar

- [Meta para desarrolladores](https://developers.facebook.com/) (partes 1 y 2)
- [Explorador de la API Graph](https://developers.facebook.com/tools/explorer/) (partes 3 y 4)
- [Depurador de tokens](https://developers.facebook.com/tools/debug/accesstoken/) (parte 4)
- [Secretos de GitHub](https://github.com/victor8701/tfm-robotic-picking-vision/settings/secrets/actions) (partes 3b y 4)
- [Prueba de Instagram](https://github.com/victor8701/tfm-robotic-picking-vision/actions/workflows/prueba_instagram.yml) (partes 3b, 4 y 5)

## Parte 1 · Hacerte desarrollador de Meta (5-10 min)

Se hace una sola vez.

- [ ] **1.1** Abre [developers.facebook.com](https://developers.facebook.com/) en Chrome. Si te pide entrar, entra con la cuenta de Facebook que administra la página «Tendencias Moda». Arriba a la derecha pulsa **Empezar** (Get Started).
  - *Deberías ver:* Si en lugar de «Empezar» ves tu nombre y «Mis apps», ya eres desarrollador. Marca los pasos 1.1 a 1.3 y pasa a la parte 2.

- [ ] **1.2** Acepta las condiciones de la plataforma. Meta te mandará un código por SMS o por correo para comprobar que eres tú: escríbelo.

- [ ] **1.3** Si te pregunta a qué te dedicas, elige **Desarrollador** (Developer) y termina con **Completar registro**.

- [ ] **1.4** Comprueba que has llegado al panel de desarrolladores.
  - *Deberías ver:* Un menú con «Mis apps» y un botón **Crear app** (Create app).
  - *Si no sale:* Si Meta pide verificar tu identidad (foto del DNI) o dice que tu cuenta no puede ser de desarrollador, no sigas y mándame una captura.

## Parte 2 · Crear la app (5-10 min)

Es una app en «modo desarrollo»: privada, solo la usas tú y no necesita revisión de Meta.

- [ ] **2.1** Pulsa **Crear app** (Create app), o abre [esta dirección](https://developers.facebook.com/apps/creation/).

- [ ] **2.2** Meta te hace unas preguntas seguidas y el orden puede cambiar. Contesta lo de abajo y pulsa **Siguiente** después de cada una.
  - Nombre de la app: `Tendencias Moda TFM`
  - *Si no sale:* Si no existe «Otro» o no te deja elegir «Empresa», marca en casos de uso «Gestionar mensajes y contenido en Instagram», «Gestionar todo en tu página» y «Autenticar y solicitar datos de usuarios con el inicio de sesión de Facebook», los que te dejen. Si algo no encaja, mándame una captura.

- [ ] **2.3** Revisa el resumen y pulsa **Crear app**. Puede pedirte la contraseña de Facebook: escríbela solo si la ventana es de facebook.com.

- [ ] **2.4** Comprueba que estás dentro del panel de tu app.
  - *Deberías ver:* Arriba el nombre «Tendencias Moda TFM», el ID de la app y un interruptor con «Modo de la app: En desarrollo» (App Mode: Development).
  - *Si no sale:* Déjalo EN DESARROLLO. No lo pases a «Activa», no pidas «Revisión de la app» ni «Verificación de empresa»: no hacen falta.

## Parte 3 · Permisos y token corto (10-15 min)

Aquí le dices a Meta qué página y qué cuenta de Instagram puede usar la app.

- [ ] **3.1** En el panel de tu app busca **Instagram** (menú de la izquierda, o la lista «Añadir productos») y pulsa **Configurar** (Set up). No cambies nada más en esa pantalla: con que el producto esté añadido basta.
  - *Si no sale:* Si tu panel no tiene lista de productos (solo «Casos de uso»), salta este paso.

- [ ] **3.2** Abre el [Explorador de la API Graph](https://developers.facebook.com/tools/explorer/), la pantalla de pruebas de Meta. Mejor en otra pestaña.

- [ ] **3.3** En la columna de la derecha, en **App de Meta** (Meta App), elige `Tendencias Moda TFM`. Debajo, en **Usuario o página**, deja **Token de usuario** (User Token). A la izquierda de la caja de la consulta deja el método **GET**.

- [ ] **3.4** Despliega **Permisos** (Permissions) y añade estos, uno a uno: escribe el nombre en el buscador y púlsalo. Los dos últimos solo si te los deja añadir.
  - Permiso: `instagram_basic`
  - Permiso: `instagram_manage_insights`
  - Permiso: `pages_read_engagement`
  - Permiso: `pages_show_list`
  - Si te deja: `ads_read`
  - Si te deja: `business_management`
  - *Si no sale:* Si alguno no aparece, sáltalo. Si no sale NINGUNO de los de Instagram, vuelve al panel de tu app, entra en Instagram → «Personalizar» → «Permisos y funciones», pulsa «Añadir» en esos permisos y vuelve aquí.

- [ ] **3.5** Pulsa **Generar token de acceso** (Generate Access Token). Se abre una ventana de Facebook. Si no se abre, permite las ventanas emergentes en la barra de direcciones de Chrome y pulsa otra vez. En la ventana: **Continuar como…**, marca la página **Tendencias Moda**, marca la cuenta de Instagram **tendencias.moda_**, y acepta hasta que la ventana se cierre.
  - *Si no sale:* Lo importante es marcar la página Y la cuenta de Instagram. Si no te ofrece Instagram, esa cuenta no está enlazada a la página: dímelo.

- [ ] **3.6** Mira el campo **Token de acceso** (Access Token).
  - *Deberías ver:* Un código larguísimo que empieza por `EAA`. Es el token corto: dura una o dos horas, de sobra para la prueba.

- [ ] **3.7** Prueba dentro del Explorador. Borra lo que haya en la caja de la consulta (suele ser `me?fields=id,name`), escribe lo de abajo y pulsa **Enviar** (Submit).
  - Consulta: `me/accounts?fields=name,instagram_business_account`
  - *Deberías ver:* A la derecha sale «Tendencias Moda» y, dentro, un «instagram_business_account» con un «id» (un número).
  - *Si no sale:* Si la lista sale vacía, añade el permiso `business_management`, pulsa otra vez «Generar token de acceso» y marca la página. Si sigue vacía, mándame una captura.

## Parte 3b · La prueba que decide (5 min)

**Punto de decisión.**

Punto de decisión. En cinco minutos sabremos si Meta deja leer cuentas ajenas con tu app. Si no, paramos aquí sin haber roto nada.

- [ ] **3b.1** Copia el token: haz clic dentro del campo **Token de acceso** del Explorador, pulsa Ctrl+A y luego Ctrl+C. En el móvil: mantén pulsado, «Seleccionar todo», «Copiar».

- [ ] **3b.2** Abre [esta página de GitHub](https://github.com/victor8701/tfm-robotic-picking-vision/settings/secrets/actions/new) y entra como victor8701 si te lo pide. En **Name** escribe el nombre de abajo. En **Secret** pega el token (Ctrl+V) y comprueba que no hay comillas ni espacios. Pulsa **Add secret**.
  - Name: `META_IG_TOKEN`
  - *Si no sale:* Si ya existe un secreto con ese nombre, GitHub te lo dice: ábrelo con el lápiz (Update secret) y pega el token nuevo. El token solo va aquí, en ningún otro sitio.

- [ ] **3b.3** Abre [Prueba de Instagram](https://github.com/victor8701/tfm-robotic-picking-vision/actions/workflows/prueba_instagram.yml). A la derecha pulsa **Run workflow**. Se despliega un cuadro: deja SIN marcar la casilla «Probar con Meta las 68 cuentas…» y pulsa el botón verde **Run workflow**.

- [ ] **3b.4** Espera 20 segundos y recarga la página (F5). Arriba de la lista aparece una ejecución nueva, «Prueba de Instagram #3» o el número que toque. Ábrela y baja hasta el recuadro **prueba summary**.
  - *Si no sale:* Aunque la ejecución salga en rojo, lo que cuenta es el texto del recuadro.

- [ ] **3b.5** Busca la sección «Meta (app propia: Business Discovery)» y mira cómo termina.
  - *Deberías ver:* «✔ Meta FUNCIONA: la tarea semanal puede leer Instagram con la app propia.» Perfecto: sigue con la parte 4.
  - *Si no sale:* «✘ Ningún token vale para Business Discovery» o un mensaje de permisos: copia ese texto (nunca el token) y mándamelo. Puede que Meta exija revisar la app y entonces seguimos con Windsor. · «⚠ Faltan permisos»: repite 3.4 a 3.6 y marca todos. · «El token guardado tiene un aspecto raro»: vuelve a copiarlo entero, sin espacios ni comillas.

## Parte 4 · Hacer el token duradero (10 min)

El token corto muere en horas. Aquí lo cambias por el de la página, que no caduca. Si esta parte te lía, hay un plan B en el último paso.

- [ ] **4.1** Vuelve al Explorador. Junto al campo «Token de acceso» hay una **i** azul: púlsala y elige **Abrir en la herramienta de token de acceso** (Open in Access Token Tool). Se abre el depurador de tokens con tu token ya puesto.

- [ ] **4.2** Abajo del todo pulsa **Ampliar token de acceso** (Extend Access Token). Sale un token nuevo, más largo, que dura unos 60 días. Selecciónalo entero y cópialo.
  - *Si no sale:* Si no ves el botón, el token ya es largo: usa el que tienes.

- [ ] **4.3** Vuelve a la pestaña del Explorador, borra lo que haya en el campo **Token de acceso** y pega el token largo.

- [ ] **4.4** En la caja de la consulta escribe lo de abajo y pulsa **Enviar**. Busca el bloque de «Tendencias Moda» y copia solo el valor de **access_token**, sin las comillas. Empieza por `EAA`. Es el **token de la página** y no caduca.
  - Consulta: `me/accounts?fields=name,access_token`

- [ ] **4.5** En GitHub abre [los secretos](https://github.com/victor8701/tfm-robotic-picking-vision/settings/secrets/actions), pulsa el lápiz de `META_IG_TOKEN` (Update secret), pega el token de la página y guarda.

- [ ] **4.6** Repite la prueba de la parte 3b (pasos 3b.3 a 3b.5).
  - *Deberías ver:* Una línea «Token de página; válido; no caduca.» y «✔ Meta FUNCIONA».
  - *Si no sale:* Plan B si esta parte falla o el token de página no vale: guarda en `META_IG_TOKEN` el token largo del paso 4.2. Vale unos 60 días y la revista te avisa cuando falten menos de 15 para renovarlo.

## Parte 5 · Prueba final con las 68 cuentas (3 min)

Comprueba que el token lee las cuentas de verdad, no solo unas de muestra.

- [ ] **5.1** En [Prueba de Instagram](https://github.com/victor8701/tfm-robotic-picking-vision/actions/workflows/prueba_instagram.yml) pulsa **Run workflow**, **marca** la casilla «Probar con Meta las 68 cuentas…» y lanza la prueba. Tarda uno o dos minutos.

- [ ] **5.2** Mira el resumen: «Resultado: N de 68 cuentas devuelven publicaciones».
  - *Deberías ver:* Un N alto. Las que salen como «Sin lectura» suelen ser cuentas personales, privadas o mal escritas, y el resumen dice el motivo de cada una.
  - *Si no sale:* Si N es menor de 20, mándame el resumen entero (sin tokens).

- [ ] **5.3** No repitas esta prueba más de una vez por hora. Meta limita las peticiones por hora a la app y esta prueba usa entre 70 y 150.

## Cuando termines

- **No tienes que hacer nada más.** El lunes a las 03:30 (GitHub suele retrasarla unas horas) la tarea lee Instagram con tu app: las 68 cuentas, no solo las 14 de Windsor. Si Meta falla, usa Windsor mientras dure su prueba.
- **Dónde lo verás.** En la revista del lunes, en «Qué ha considerado», las cuentas de Instagram pasan a tener fotos. Si el token se rompe, aparece un **Aviso** en «Para la próxima».
- **Cuándo se rompe.** Si cambias la contraseña de Facebook, quitas la app en «Apps y sitios web» o Meta la anula. Se arregla repitiendo las partes 3 y 4, unos 15 minutos.
- **Windsor.** Si Meta funciona, puedes dejar que termine la prueba gratuita y no pagar.

## Si algo falla

| Si ves | Qué pasa | Qué hacer |
|---|---|---|
| «Todavía no hay secreto META_IG_TOKEN» | El secreto no existe o tiene otro nombre. | En GitHub, Settings → Secrets → Actions, debe haber uno llamado exactamente `META_IG_TOKEN`. |
| «El token guardado tiene un aspecto raro» | Al copiarlo se colaron comillas o espacios, o se copió solo un trozo. | Copia el token entero (empieza por `EAA`) y guárdalo otra vez. |
| «Meta dice que el token ya no es válido» o «código 190» | El token caducó, cambiaste la contraseña de Facebook o quitaste la app. | Repite las partes 3 y 4. |
| «Faltan permisos» o «le falta algún permiso» | Al generar el token no se marcaron todos los permisos, o no se eligió la página y su Instagram. | Repite 3.4 y 3.5. |
| «Ninguna de tus páginas… tiene una cuenta de Instagram profesional enlazada» | En 3.5 no se marcó la página y su Instagram, o esa cuenta no está enlazada a la página. | Repite 3.5. Si sigue igual, mándame una captura. |
| «Ningún token vale para Business Discovery» | Meta puede exigir la revisión de la app para leer cuentas ajenas. | Copia el texto que sale (sin tokens) y mándamelo. Si es eso, seguimos con Windsor. |
| «Meta ha limitado las peticiones» | Demasiadas pruebas seguidas. | Espera una hora. |
| Algunas cuentas en «Sin lectura» | La cuenta es personal, privada, tiene límite de edad o está mal escrita. | Es normal. Si te importa una en concreto, dímelo. |
| «Al token le quedan N días» | Es un token de persona, que dura unos 60 días. | Renuévalo con la parte 4 o cámbialo por el de la página, que no caduca. |
| Meta pide verificar tu identidad o tu empresa, o «revisar la app» | Pasa con cuentas nuevas o al pedir permisos avanzados. | No lo hagas. Mándame una captura. |

## Qué he comprobado y qué no

**Probado por mí**

- La prueba de un clic funciona en GitHub. La lancé hace un rato (la ejecución #2): leyó los secretos, probó Windsor (✔ 174 publicaciones de 14 cuentas) y avisó de que aún no hay secreto de Meta.
- El lector de Meta y su unión con la tarea semanal tienen 35 pruebas automáticas. Cubren el token de persona y el de página, el token caducado, los permisos que faltan, las cuentas personales, el límite de peticiones y los campos que Meta rechaza. Comprueban también que el token nunca sale en un mensaje de error.
- Si el lector de Meta falla por cualquier motivo, incluido uno imprevisto, la tarea sigue con Windsor y deja un aviso en la revista.

**Confirmado en la documentación de Meta**

- Business Discovery es el método oficial para leer cuentas profesionales ajenas por su @.
- Pide un token de usuario de Facebook con `instagram_basic`, `instagram_manage_insights` y `pages_read_engagement`, y además `ads_read` o `ads_management` si tu rol en la página viene de una cartera de negocios.
- No devuelve cuentas con límite de edad, y a veces omite el enlace de vídeos con música con derechos. Para las fotos no es un problema.
- Un token de página sacado de un token largo de usuario no caduca.

**Sin comprobar: solo tu token lo confirma**

- Que Meta deje leer cuentas ajenas con una app privada sin revisión. Su documentación de Business Discovery no menciona el modo desarrollo. Lo decide la prueba 3b.
- Que Meta acepte el token de página en Business Discovery, porque su documentación habla de token de usuario. La tarea prueba primero el de persona y luego el de página, y la prueba te dice cuál funciona.
- Los nombres exactos de los botones de la web de Meta, que cambian a menudo. Por eso cada paso dice qué buscar, qué deberías ver y qué hacer si no sale.
