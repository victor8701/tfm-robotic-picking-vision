// La app CajaPinza entera (index.html + librerias de ABB + app.js) en jsdom, contra el RWS simulado de
// demo-rws.js. Lanzada por tests/test_flexpendant.py con Node. Necesita jsdom: carpeta con node_modules/jsdom
// en el primer argumento, en CAJAPINZA_JSDOM o en tests/js/node_modules; si no esta, escribe
// JSDOM_NO_DISPONIBLE y termina sin error (la prueba de Python se salta).
const path = require('node:path');

function cargarJsdom() {
    const candidatos = [process.argv[2], process.env.CAJAPINZA_JSDOM, __dirname].filter(Boolean);
    for (const c of candidatos) {
        try { return require(require.resolve('jsdom', {paths: [c]})); } catch (e) { /* siguiente */ }
    }
    return null;
}

const jsdom = cargarJsdom();
if (jsdom === null) {
    console.log('JSDOM_NO_DISPONIBLE');
    process.exit(0);
}

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {pathToFileURL} = require('node:url');
const {JSDOM, VirtualConsole} = jsdom;

const RAIZ = path.join(__dirname, '..', '..', 'flexpendant', 'CajaPinza');
const L = require(path.join(RAIZ, 'logica.js'));
const Demo = require(path.join(RAIZ, 'demo-rws.js'));

const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

async function hasta(condicion, descripcion, ms = 4000) {
    const limite = Date.now() + ms;
    while (Date.now() < limite) {
        let ok = false;
        try { ok = condicion(); } catch (e) { ok = false; }
        if (ok) { return; }
        await dormir(5);
    }
    assert.fail('Tiempo agotado esperando: ' + descripcion);
}

// Abre la app con un RAPID simulado. escala pequena = el programa simulado va rapido.
async function abrir(opciones, simExistente) {
    // simExistente: un RAPID simulado ya creado (para cerrar la app y abrirla otra vez con las mismas PERS)
    // Las pruebas con numeros de sitios (2, 5...) son de la zona antigua de la mesa (mesa_marron en -1120, 342);
    // las de los valores por defecto actuales pasan valores: {mesaX0: '-900', mesaY0: '150'}.
    const o = Object.assign({escala: 0.01, ejecucion: 'stopped', egmMaxPos: 1500}, opciones || {});
    o.valores = Object.assign({mesaX0: '-1120', mesaY0: '342'}, o.valores);
    const sim = simExistente || Demo.crear(L, o);
    const consola = new VirtualConsole();
    const errores = [];
    consola.on('jsdomError', (e) => errores.push(String(e && e.stack || e)));
    consola.on('error', (...a) => errores.push(a.join(' ')));
    consola.on('warn', (...a) => { if (process.env.CAJAPINZA_DEBUG) { console.log('[warn]', ...a); } });
    // Las librerias de RWS de ABB no se cargan: no hay controlador y al arrancar piden la lista de tareas. La app
    // usa el RWS simulado de la prueba (window.RWS_SIMULADO). Lo demas (FPComponents, logica.js, app.js) es el real.
    const ruta = path.join(RAIZ, 'index.html');
    const html = fs.readFileSync(ruta, 'utf8').replace(/<script src="rws-api\/[^"]+"><\/script>\s*/g, '');
    const dom = new JSDOM(html, {
        url: pathToFileURL(ruta).href,
        runScripts: 'dangerously',
        resources: 'usable',
        pretendToBeVisual: true,
        virtualConsole: consola,
        beforeParse(window) { window.RWS_SIMULADO = sim.RWS; }
    });
    const w = dom.window;
    if (w.document.readyState !== 'complete') {
        await new Promise((r) => w.addEventListener('load', r));
    }
    const app = {
        sim, dom, w, errores,
        $: (id) => w.document.getElementById(id),
        texto: (id) => w.document.getElementById(id).textContent.trim(),
        pulsarFp: (id) => w.document.querySelector('#' + id + ' > div').click(),   // Button_A de ABB: un div
        fpHabilitado: (id) => w.document.querySelector('#' + id + ' > div').className.indexOf('disabled') < 0,
        pulsar: (id) => w.document.getElementById(id).click(),
        popup: () => Array.from(w.document.querySelectorAll('.fp-components-popup-message-text')).map((e) => e.textContent),
        pulsarPopup: (texto) => {
            const b = Array.from(w.document.querySelectorAll('.fp-components-button-text')).find((e) => e.textContent === texto);
            assert.ok(b, 'no hay boton ' + texto + ' en el popup');
            b.parentElement.click();
        },
        cerrar: (conservarRapid) => { if (!conservarRapid) { sim.stop(); } w.close(); }
    };
    // espera a que la app haya terminado de abrir las variables de RAPID
    await hasta(() => w.document.body.getAttribute('data-rws') !== null, 'conexion de la app con RAPID');
    return app;
}

test('la app arranca, lee RAPID y no da errores de JavaScript', async () => {
    const app = await abrir();
    try {
        assert.equal(app.texto('banner-titulo'), 'Sin arrancar');   // fase 0 y programa parado
        assert.equal(app.fpHabilitado('btn-iniciar'), false);
        assert.equal(app.fpHabilitado('btn-caja'), false);
        assert.equal(app.texto('caja-texto'), '1 caja en la tanda');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('con el programa esperando INICIAR se ve el aviso y se pueden ajustar las cajas', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        assert.equal(app.fpHabilitado('btn-iniciar'), true);
        assert.equal(app.fpHabilitado('btn-caja'), false);
        assert.equal(app.texto('chips').includes('En marcha'), true);
        assert.equal(app.texto('chips').includes('Conectado'), true);

        app.pulsar('c-mas');
        app.pulsar('c-mas');
        app.pulsar('c-mas10');
        await hasta(() => app.texto('c-valor') === '13', 'el contador se ve sin esperar a RAPID');
        await hasta(() => app.sim.valor('nCajas') === '13', 'nCajas escrito en RAPID');
        assert.equal(app.sim.valor('nCajas'), '13');                       // una sola escritura con el ultimo valor
        assert.equal(app.texto('caja-texto'), '13 cajas en la tanda');
        assert.equal(app.$('lista-giros').children.length, 13);

        app.pulsar('c-menos10');
        app.pulsar('c-menos10');
        await hasta(() => app.sim.valor('nCajas') === '1', 'tope inferior');
        assert.equal(app.$('c-menos').disabled, true);
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('modo, giro fijo y giro al azar se escriben en las PERS de RAPID', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');

        app.pulsar('giro-azar');
        await hasta(() => app.sim.valor('indiceFijo') === '0', 'indiceFijo 0');
        assert.equal(app.$('fila-semilla').hidden, false);
        assert.equal(app.$('giro-opciones').hidden, true);
        const antes = app.sim.valor('semillaGiros');
        app.pulsar('nueva-semilla');
        await hasta(() => app.sim.valor('semillaGiros') !== antes, 'semilla nueva');
        const semilla = parseInt(app.sim.valor('semillaGiros'), 10);
        assert.ok(semilla >= 0 && semilla < 8192);

        app.pulsar('giro-fijo');
        await hasta(() => app.sim.valor('indiceFijo') === '7', 'giro fijo a 0 grados');
        assert.equal(app.$('giro-opciones').hidden, false);
        app.pulsar('giro-12');   // 75 grados
        await hasta(() => app.sim.valor('indiceFijo') === '12', 'giro fijo a 75');
        assert.equal(app.texto('orient-texto'), '75°');

        app.pulsar('modo-real');
        await hasta(() => app.sim.valor('modoSimulacion') === 'FALSE', 'modo real');
        assert.equal(app.texto('chips').includes('REAL'), true);
        assert.equal(app.$('giro-opciones').hidden, true);
        assert.equal(app.$('giro-azar').disabled, true);
        app.pulsar('modo-sim');
        await hasta(() => app.sim.valor('modoSimulacion') === 'TRUE', 'modo simulacion');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('el interruptor de confirmar escribe hmiConfirmar', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        assert.equal(app.sim.valor('hmiConfirmar'), 'TRUE');
        app.w.document.querySelector('#sw-confirmar .fp-components-switch-container').click();
        await hasta(() => app.sim.valor('hmiConfirmar') === 'FALSE', 'confirmar apagado');
    } finally { app.cerrar(); }
});

test('una tanda de 2 cajas: INICIAR, esperar CAJA EN POSICION, pulsarla y llegar al final', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('c-mas');                       // 2 cajas
        app.pulsar('giro-fijo');                   // 0 grados
        app.pulsar('giro-3');                      // -60 grados
        await hasta(() => app.sim.valor('nCajas') === '2' && app.sim.valor('indiceFijo') === '3', 'ajustes escritos');

        app.pulsarFp('btn-iniciar');               // pide confirmacion
        await hasta(() => app.popup().length > 0, 'popup de confirmacion');
        const lineas = app.popup().join(' | ');
        assert.match(lineas, /2 cajas · simulación · giros fijos a −60°/);
        assert.match(lineas, /¿Empezar la tanda\?/);
        assert.equal(app.sim.valor('hmiIniciar'), 'FALSE');   // todavia no se ha enviado
        app.pulsarPopup('OK');

        // la caja 1 llega al sensor y RAPID espera el boton
        await hasta(() => app.texto('banner-titulo') === 'Esperando CAJA EN POSICIÓN', 'esperando el boton');
        assert.equal(app.sim.valor('hmiIniciar'), 'FALSE');   // RAPID la consumio
        assert.equal(app.fpHabilitado('btn-caja'), true);
        assert.equal(app.fpHabilitado('btn-iniciar'), false);
        assert.equal(app.texto('caja-texto'), 'Caja 1 de 2');
        assert.equal(app.texto('orient-texto'), '−60°');
        assert.equal(app.texto('g-rapid'), '−60°');
        assert.equal(app.$('c-mas').disabled, true);          // ajustes bloqueados
        assert.equal(app.sim.valor('hmiFase'), String(L.FASES.ESPERA_CAJA));
        // el sensor de la cinta esta activo
        assert.ok(app.$('senales').innerHTML.includes('led on'));

        // sin pulsar, RAPID sigue esperando
        await dormir(120);
        assert.equal(app.sim.valor('hmiFase'), String(L.FASES.ESPERA_CAJA));

        app.pulsarFp('btn-caja');
        await hasta(() => app.sim.valor('hmiCajaEnPosicion') === 'TRUE' || app.sim.valor('hmiFase') !== String(L.FASES.ESPERA_CAJA), 'orden enviada');
        await hasta(() => app.texto('banner-titulo') === 'EGM abierto: a por la caja', 'EGM abierto');
        assert.equal(app.fpHabilitado('btn-caja'), false);
        await hasta(() => app.texto('g-ok') === '✓ coincide', 'el PC lee el mismo giro');
        await hasta(() => app.texto('banner-titulo') === 'Caja agarrada', 'agarrada');
        await hasta(() => app.texto('banner-titulo') === 'Caja depositada', 'depositada');
        await hasta(() => app.texto('banner-titulo') === 'Cerrando el EGM', 'cerrando el EGM');

        // segunda caja
        await hasta(() => app.texto('banner-titulo') === 'Esperando CAJA EN POSICIÓN' && app.texto('caja-texto') === 'Caja 2 de 2',
            'segunda caja esperando el boton', 8000);
        assert.equal(app.fpHabilitado('btn-caja'), true, 'el boton vuelve a valer en la caja 2');
        app.pulsarFp('btn-caja');
        await hasta(() => app.texto('banner-titulo') === 'Tanda terminada', 'fin de la tanda', 8000);
        assert.equal(app.texto('caja-texto'), '2 de 2 cajas hechas');
        assert.equal(app.$('progreso-barra').style.width, '100%');
        assert.equal(app.$('c-mas').disabled, false);         // al terminar se desbloquean los ajustes de la tanda siguiente
        assert.equal(app.sim.ejecucion(), 'stopped');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('sin boton (hmiConfirmar FALSE) en simulacion la tanda va sola', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.w.document.querySelector('#sw-confirmar .fp-components-switch-container').click();
        await hasta(() => app.sim.valor('hmiConfirmar') === 'FALSE', 'confirmar apagado');
        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        assert.match(app.popup().join(' '), /sin botón/);
        app.pulsarPopup('OK');
        await hasta(() => app.texto('banner-titulo') === 'Tanda terminada', 'tanda sola', 8000);
        assert.equal(app.texto('motivo-caja').length > 0, true);
    } finally { app.cerrar(); }
});

test('si el PC lee otro giro que el que puso RAPID, se avisa', async () => {
    const app = await abrir({giroPc: (giro) => giro + 30});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        app.pulsarPopup('OK');
        await hasta(() => app.texto('banner-titulo') === 'Esperando CAJA EN POSICIÓN', 'esperando el boton');
        app.pulsarFp('btn-caja');
        await hasta(() => app.texto('g-ok') === '✗ distinto', 'giro distinto');
        assert.match(app.texto('avisos'), /el PC no usa la caja\.csv/);
    } finally { app.cerrar(); }
});

test('sin PC conectado, INICIAR avisa en la confirmacion', async () => {
    const app = await abrir({pcConectado: false});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        assert.match(app.texto('avisos'), /PC no está conectado/);
        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        assert.match(app.popup().join(' '), /no está conectado/);
        app.pulsarPopup('Cancel');
        await dormir(100);
        assert.equal(app.sim.valor('hmiIniciar'), 'FALSE');
        assert.equal(app.texto('banner-titulo'), 'Listo para empezar');
    } finally { app.cerrar(); }
});

test('si RAPID rechaza la escritura (mastership) sale un error con el motivo', async () => {
    const app = await abrir({falloEscritura: 'Failed to get Mastership. Held by RobotStudio'});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('c-mas');
        await hasta(() => app.popup().length > 0, 'popup de error');
        const texto = app.popup().join(' | ');
        assert.match(texto, /No he podido guardar nCajas/);
        assert.match(texto, /Mastership/);
        assert.match(texto, /Request Write Access/);
    } finally { app.cerrar(); }
});

test('un modulo antiguo, sin las PERS hmi*, se nota en pantalla', async () => {
    const app = await abrir({sin: ['hmiFase', 'hmiMensaje']});
    try {
        assert.match(app.texto('avisos'), /No encuentro en RAPID: hmiFase, hmiMensaje/);
    } finally { app.cerrar(); }
});

test('programa parado a mitad de tanda: aviso y botones bloqueados', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        app.pulsarPopup('OK');
        await hasta(() => app.texto('banner-titulo') === 'Esperando CAJA EN POSICIÓN', 'esperando el boton');
        app.sim.stop();
        await hasta(() => app.texto('banner-titulo') === 'Programa parado', 'parado');
        assert.equal(app.fpHabilitado('btn-caja'), false);
        assert.match(app.texto('motivo-caja'), /Play/);
    } finally { app.cerrar(); }
});

test('en real: sin lista de giros y el boton CAJA EN POSICION arranca el EGM', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('modo-real');
        await hasta(() => app.sim.valor('modoSimulacion') === 'FALSE', 'modo real');
        assert.match(app.texto('lista-giros'), /cámara/);
        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        assert.match(app.popup().join(' '), /real/);
        app.pulsarPopup('OK');
        await hasta(() => app.texto('banner-titulo') === 'Esperando CAJA EN POSICIÓN', 'esperando el boton');
        assert.match(app.texto('banner-detalle'), /Coloca la caja/);
        app.pulsarFp('btn-caja');
        await hasta(() => app.texto('banner-titulo') === 'EGM abierto: a por la caja', 'EGM abierto');
        await hasta(() => app.texto('g-pc') !== '—', 'giro leido por el PC');
        assert.equal(app.texto('g-rapid'), '—');
    } finally { app.cerrar(); }
});

test('pestana Mesa: los campos escriben las PERS de la mesa y el dibujo y la capacidad se actualizan', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        assert.equal(app.$('vista-mesa').hidden, true);
        app.pulsar('tab-mesa');
        assert.equal(app.$('vista-mesa').hidden, false);
        assert.equal(app.$('vista-tanda').hidden, true);
        assert.match(app.texto('mesa-resumen'), /Caben 5 cajas de 200 × 200 × 200 mm/);
        assert.equal(app.$('svg-mesa').querySelectorAll('rect.hueco').length, 5);
        assert.ok(app.$('svg-mesa').querySelectorAll('rect.mesa-rojo').length > 0);   // lo que el robot no alcanza
        assert.match(app.$('svg-mesa').textContent, /largo 1200 mm \(x\)/);
        assert.equal(app.w.document.querySelector('#in-mesaLargo .fp-components-input-container p').textContent, '1200');

        // se escribe como lo haria el teclado numerico de ABB
        const ui = app.w.CajaPinzaPrueba.ui;
        ui.campos.mesaHueco.onchange('20');
        ui.campos.mesaY0.onchange('360.5');
        await hasta(() => app.sim.valor('mesaHueco') === '20' && app.sim.valor('mesaY0') === '360.5', 'PERS de la mesa escritas');
        ui.campos.mesaLargo.onchange('99999');   // se limita al maximo que acepta la app
        await hasta(() => app.sim.valor('mesaLargo') === '4000', 'largo limitado');

        // caja de referencia: tambien se escribe y cambia la estimacion
        ui.campos.cajaLargo.onchange('150');
        ui.campos.cajaAncho.onchange('100');
        ui.campos.cajaAlto.onchange('120');
        await hasta(() => app.sim.valor('cajaLargo') === '150' && app.sim.valor('cajaAncho') === '100' && app.sim.valor('cajaAlto') === '120', 'caja de referencia');
        await hasta(() => app.texto('mesa-resumen').includes('150 × 100 × 120 mm'), 'resumen con la caja de referencia');

        app.pulsar('mesa-sim');   // vuelve a las medidas de la simulacion
        await hasta(() => app.sim.valor('mesaLargo') === '1200' && app.sim.valor('mesaHueco') === '40' && app.sim.valor('mesaX0') === '-900' && app.sim.valor('mesaY0') === '150', 'medidas de la simulacion');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('cajas de tamanos distintos: el interruptor escribe cajasVariables; apagado, INICIAR se bloquea si no caben', async () => {
    const app = await abrir({egmMaxPos: 1000});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        assert.equal(app.sim.valor('cajasVariables'), 'TRUE');   // por defecto: cajas de tamaños distintos
        app.pulsar('c-mas'); app.pulsar('c-mas');
        await hasta(() => app.sim.valor('nCajas') === '3', '3 cajas');
        await hasta(() => app.fpHabilitado('btn-iniciar') === true, 'con cajas distintas INICIAR no se bloquea: el PC comprueba cada caja');
        app.pulsar('tab-mesa');
        const interruptor = () => app.w.document.querySelector('#sw-variables .fp-components-switch-container').click();
        interruptor();
        await hasta(() => app.sim.valor('cajasVariables') === 'FALSE', 'cajasVariables apagado');
        await hasta(() => app.fpHabilitado('btn-iniciar') === false, 'INICIAR bloqueado con 3 cajas iguales');
        interruptor();
        await hasta(() => app.sim.valor('cajasVariables') === 'TRUE', 'cajasVariables encendido');
        await hasta(() => app.fpHabilitado('btn-iniciar') === true, 'INICIAR ya no se bloquea');
    } finally { app.cerrar(); }
});

test('el limite del EGM se cambia desde la app, pero pide confirmacion', async () => {
    const app = await abrir({egmMaxPos: 1000});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('tab-mesa');
        const ui = app.w.CajaPinzaPrueba.ui;
        ui.campos.egmMaxPos.onchange('1500');
        await hasta(() => app.popup().length > 0, 'popup de confirmacion');
        assert.match(app.popup().join(' '), /¿Cambiarlo de 1000 a 1500 mm\?/);
        app.pulsarPopup('Cancel');
        await dormir(80);
        assert.equal(app.sim.valor('egmMaxPos'), '1000');
        ui.campos.egmMaxPos.onchange('1500');
        await hasta(() => app.popup().length > 0, 'popup otra vez');
        app.pulsarPopup('OK');
        await hasta(() => app.sim.valor('egmMaxPos') === '1500', 'egmMaxPos escrito');
        await hasta(() => /Caben 5 cajas/.test(app.texto('mesa-resumen')), 'mas sitio con el limite nuevo');
    } finally { app.cerrar(); }
});

test('el interruptor de mensajes escribe hmiMensajes', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        assert.equal(app.sim.valor('hmiMensajes'), 'FALSE');   // por defecto, apagado
        const interruptor = () => app.w.document.querySelector('#sw-mensajes .fp-components-switch-container').click();
        interruptor();
        await hasta(() => app.sim.valor('hmiMensajes') === 'TRUE', 'mensajes encendidos');
        interruptor();
        await hasta(() => app.sim.valor('hmiMensajes') === 'FALSE', 'mensajes apagados');
    } finally { app.cerrar(); }
});

test('ABORTAR: confirma, para RAPID, vuelve al principio y deja la app como al arrancar', async () => {
    const app = await abrir();
    try {
        assert.equal(app.fpHabilitado('btn-abortar'), false);            // programa parado
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        app.pulsarPopup('OK');
        await hasta(() => app.texto('banner-titulo') === 'Esperando CAJA EN POSICIÓN', 'esperando el boton');
        app.pulsarFp('btn-caja');
        await hasta(() => app.texto('banner-titulo') === 'EGM abierto: a por la caja', 'EGM abierto');
        assert.equal(app.fpHabilitado('btn-abortar'), true);

        app.pulsarFp('btn-abortar');
        await hasta(() => app.popup().length > 0, 'confirmacion de abortar');
        assert.match(app.popup().join(' '), /paro de emergencia del FlexPendant/);
        app.pulsarPopup('Cancel');
        await dormir(80);
        assert.equal(app.sim.ejecucion(), 'running');                    // cancelar no hace nada

        app.pulsarFp('btn-abortar');
        await hasta(() => app.popup().length > 0, 'confirmacion otra vez');
        app.pulsarPopup('OK');
        await hasta(() => app.sim.ejecucion() === 'stopped', 'RAPID parado');
        await hasta(() => app.sim.valor('hmiFase') === String(L.FASES.PARADO), 'fase a 0');
        await hasta(() => app.texto('banner-titulo') === 'Sin arrancar', 'la app muestra sin arrancar');
        assert.match(app.texto('avisos'), /Tanda abortada desde la app/);
        assert.equal(app.fpHabilitado('btn-abortar'), false);
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('las medidas de la caja en curso se ven en la orientacion', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        app.pulsarPopup('OK');
        await hasta(() => app.texto('orient-medidas') === 'Medidas: 200 x 200 x 200 mm', 'medidas de la caja');
    } finally { app.cerrar(); }
});

test('si la tanda no cabe en la mesa, INICIAR queda bloqueado y lo explica', async () => {
    const app = await abrir({egmMaxPos: 1000, valores: {cajasVariables: 'FALSE'}});   // limite de RAPID por defecto: caben 2 cajas iguales
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('c-mas'); app.pulsar('c-mas');   // 3 cajas
        await hasta(() => app.sim.valor('nCajas') === '3', '3 cajas');
        await hasta(() => app.fpHabilitado('btn-iniciar') === false, 'INICIAR bloqueado');
        assert.match(app.texto('motivo-iniciar'), /caben 2 cajas y la tanda tiene 3/);
        assert.match(app.texto('nota-capacidad'), /admite 2 cajas/);
        assert.equal(app.$('nota-capacidad').classList.contains('mala'), true);
        app.pulsar('c-menos');
        await hasta(() => app.fpHabilitado('btn-iniciar') === true, 'INICIAR vuelve a valer con 2 cajas');
    } finally { app.cerrar(); }
});

test('mientras la tanda esta en marcha los campos de la mesa se bloquean y el hueco actual se marca', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        app.pulsarPopup('OK');
        await hasta(() => app.texto('banner-titulo') === 'Esperando CAJA EN POSICIÓN', 'esperando el boton');
        app.pulsar('tab-mesa');
        assert.equal(app.$('mesa-sim').disabled, true);
        assert.match(app.texto('nota-mesa'), /Bloqueado/);
        assert.equal(app.$('svg-mesa').querySelectorAll('rect.hueco-actual').length, 1);
        assert.equal(app.w.document.querySelector('#in-mesaX0 .fp-components-input').className.includes('disabled'), true);
    } finally { app.cerrar(); }
});

test('cambiar de modo pone los ajustes por defecto de ese modo, y se pueden volver a cambiar', async () => {
    const app = await abrir({valores: {indiceFijo: '7', cajasVariables: 'FALSE', hmiConfirmar: 'FALSE'}});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        // pulsar el modo que ya esta activo no toca los ajustes del usuario
        app.pulsar('modo-sim');
        await dormir(400);
        assert.deepEqual([app.sim.valor('indiceFijo'), app.sim.valor('cajasVariables'), app.sim.valor('hmiConfirmar')], ['7', 'FALSE', 'FALSE']);
        // real: esperar CAJA EN POSICION activado
        app.pulsar('modo-real');
        await hasta(() => app.sim.valor('modoSimulacion') === 'FALSE' && app.sim.valor('hmiConfirmar') === 'TRUE', 'real con esperar el boton');
        // y se puede desactivar si se quiere
        app.w.document.querySelector('#sw-confirmar .fp-components-switch-container').click();
        await hasta(() => app.sim.valor('hmiConfirmar') === 'FALSE', 'confirmar apagado a mano en real');
        // simulacion: giros al azar y cajas de tamaños distintos
        app.pulsar('modo-sim');
        await hasta(() => app.sim.valor('modoSimulacion') === 'TRUE' && app.sim.valor('indiceFijo') === '0' && app.sim.valor('cajasVariables') === 'TRUE', 'simulacion al azar y cajas distintas');
        assert.equal(app.sim.valor('hmiConfirmar'), 'FALSE');   // la simulacion no toca el boton
        assert.equal(app.$('giro-azar').classList.contains('activo'), true);
        app.pulsar('giro-fijo');
        await hasta(() => app.sim.valor('indiceFijo') === '7', 'giro fijo a mano en simulacion');
    } finally { app.cerrar(); }
});

test('los ajustes se guardan en RAPID: abrir la app no los toca y al volver a abrirla siguen', async () => {
    const app1 = await abrir({valores: {nCajas: '4', indiceFijo: '5', hmiMensajes: 'TRUE', hmiConfirmar: 'FALSE', cajasVariables: 'FALSE'}});
    const sim = app1.sim;
    try {
        sim.play();
        await hasta(() => app1.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        await dormir(400);
        // la app no escribe nada al abrir: lo que habia en RAPID sigue igual y es lo que se ve
        assert.deepEqual([sim.valor('nCajas'), sim.valor('indiceFijo'), sim.valor('hmiMensajes'), sim.valor('hmiConfirmar'), sim.valor('cajasVariables')],
            ['4', '5', 'TRUE', 'FALSE', 'FALSE']);
        assert.equal(app1.texto('c-valor'), '4');
        app1.pulsar('c-mas');
        await hasta(() => sim.valor('nCajas') === '5', 'cajas escritas');
    } finally { app1.cerrar(true); }
    // "cerrar el FlexPendant": otra instancia de la app contra el mismo RAPID
    const app2 = await abrir(null, sim);
    try {
        await hasta(() => app2.texto('c-valor') === '5', 'la app nueva lee las 5 cajas');
        assert.equal(sim.valor('indiceFijo'), '5');
        assert.equal(app2.$('giro-fijo').classList.contains('activo'), true);
        assert.equal(sim.valor('hmiMensajes'), 'TRUE');
    } finally { app2.cerrar(); }
});

test('con los valores por defecto de RAPID la mesa de la simulacion da sitio a 8 cajas y el limite es 1500', async () => {
    const app = await abrir({egmMaxPos: 1500, valores: {mesaX0: '-900', mesaY0: '150'}});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('tab-mesa');
        await hasta(() => /Caben 8 cajas de 200 × 200 × 200 mm/.test(app.texto('mesa-resumen')), 'caben 8');
        assert.equal(app.sim.valor('egmMaxPos'), '1500');
    } finally { app.cerrar(); }
});

test('la tarjeta Pinza muestra abierta, cerrada y cuantas ordenes se han visto en la tanda', async () => {
    const app = await abrir({valores: {hmiConfirmar: 'FALSE'}});
    const led = (id) => app.$(id).className;
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        // antes de empezar: abierta, sin ordenes
        await hasta(() => app.texto('pinza-titulo') === 'ABIERTA', 'pinza abierta al empezar');
        assert.equal(led('pinza-led-orden'), 'led off');
        assert.equal(led('pinza-led-conf'), 'led off');
        assert.match(app.texto('pinza-resumen'), /cerrar 0 · abrir 0$/);

        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        app.pulsarPopup('OK');

        // RAPID cierra: orden y confirmacion encendidas
        await hasta(() => app.texto('pinza-titulo') === 'CERRADA', 'pinza cerrada');
        assert.equal(led('pinza-led-orden'), 'led on');
        assert.equal(led('pinza-led-conf'), 'led on');
        assert.equal(app.$('pinza').className, 'pinza tono-ok');
        assert.match(app.texto('pinza-resumen'), /cerrar 1 · abrir 0 · última: cerrar \(caja 1\)/);

        // RAPID abre: las dos se apagan
        await hasta(() => app.texto('pinza-titulo') === 'ABIERTA' && /abrir 1/.test(app.texto('pinza-resumen')), 'pinza abierta otra vez');
        assert.equal(led('pinza-led-orden'), 'led off');
        assert.match(app.texto('pinza-resumen'), /cerrar 1 · abrir 1 · última: abrir \(caja 1\)/);
        await hasta(() => app.texto('banner-titulo') === 'Tanda terminada', 'fin de la tanda', 8000);
        assert.match(app.texto('pinza-resumen'), /cerrar 1 · abrir 1/);   // se conserva al terminar
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('la pestana Parametros tiene sus secciones y el limite del EGM ya no esta en la pestana Mesa', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        assert.equal(app.$('vista-parametros').hidden, true);
        app.pulsar('tab-parametros');
        assert.equal(app.$('vista-parametros').hidden, false);
        assert.equal(app.$('vista-tanda').hidden, true);
        assert.equal(app.$('vista-mesa').hidden, true);
        assert.deepEqual(Array.from(app.$('param-nav').querySelectorAll('button')).map((b) => b.textContent),
            ['Recogida', 'Pinza y agarre', 'Tiempos', 'Movimiento y seguridad']);
        // una seccion cada vez
        assert.equal(app.$('psec-recogida').hidden, false);
        assert.equal(app.$('psec-pinza').hidden, true);
        app.pulsar('pnav-pinza');
        assert.equal(app.$('psec-pinza').hidden, false);
        assert.equal(app.$('psec-recogida').hidden, true);
        // el limite del EGM esta en Movimiento y seguridad, no en la pestana Mesa
        assert.ok(app.$('psec-movimiento').querySelector('#in-egmMaxPos'));
        assert.equal(app.$('vista-mesa').querySelector('#in-egmMaxPos'), null);
        // todos los campos numericos de la ventana existen y muestran el valor de RAPID
        assert.equal(app.w.document.querySelector('#in-seguroZ .fp-components-input-container p').textContent, '543');
        assert.equal(app.w.document.querySelector('#in-tMaxPinza .fp-components-input-container p').textContent, '3');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('un ajuste normal de Parametros se escribe en la PERS de RAPID al instante', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        const ui = app.w.CajaPinzaPrueba.ui;
        ui.campos.tAgarre.onchange('1.5');
        ui.campos.tSuelta.onchange('0.5');
        ui.campos.aperturaPinza.onchange('90');
        ui.campos.tMaxPinza.onchange('0');   // por debajo del minimo: se limita a 0.5
        await hasta(() => app.sim.valor('tAgarre') === '1.5' && app.sim.valor('tSuelta') === '0.5' && app.sim.valor('aperturaPinza') === '90', 'PERS escritas');
        await hasta(() => app.sim.valor('tMaxPinza') === '0.5', 'tMaxPinza limitado');
        // la caja de referencia (200 de ancho) no cabe en una apertura de 90: la app avisa
        await hasta(() => /no se puede agarrar/.test(app.texto('avisos')), 'aviso de agarre');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('un ajuste protegido de Parametros pide confirmacion antes de escribirse', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        const ui = app.w.CajaPinzaPrueba.ui;
        ui.campos.velocidad.onchange('40');
        await hasta(() => app.popup().length > 0, 'popup');
        assert.match(app.popup().join(' '), /Empieza lento/);
        assert.match(app.popup().join(' '), /¿Cambiarlo de 100 a 40 mm\/s\?/);
        app.pulsarPopup('Cancel');
        await dormir(120);
        assert.equal(app.sim.valor('velocidad'), '100');
        ui.campos.velocidad.onchange('500');   // se limita a 100: el tope del puente
        await hasta(() => app.popup().length > 0, 'popup otra vez');
        app.pulsarPopup('OK');
        await hasta(() => app.sim.valor('velocidad') === '100', 'velocidad limitada al tope');
        ui.campos.seguroZ.onchange('560');
        await hasta(() => app.popup().length > 0, 'popup del punto de espera');
        assert.match(app.popup().join(' '), /Punto de espera/);
        app.pulsarPopup('OK');
        await hasta(() => app.sim.valor('seguroZ') === '560', 'seguroZ escrito');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('los modos de Parametros: la altura de agarre cambia que campo vale y la camara solo en real', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('tab-parametros');
        // agarre por porcentaje: vale el porcentaje y no el hundimiento
        assert.equal(app.$('par-agarreModo-0').classList.contains('activo'), true);
        assert.equal(app.$('pitem-agarrePorcentaje').classList.contains('inactivo'), false);
        assert.equal(app.$('pitem-agarreHundimiento').classList.contains('inactivo'), true);
        assert.match(app.texto('pnota-agarreHundimiento'), /Solo con el modo Desde la tapa/);
        app.pulsar('par-agarreModo-1');
        await hasta(() => app.sim.valor('agarreModo') === '1', 'agarre desde la tapa');
        await hasta(() => app.$('pitem-agarreHundimiento').classList.contains('inactivo') === false, 'hundimiento activo');
        assert.equal(app.$('pitem-agarrePorcentaje').classList.contains('inactivo'), true);
        assert.equal(app.$('par-agarreModo-1').classList.contains('activo'), true);

        // la camara no vale en simulacion
        assert.equal(app.$('par-recogidaModo-1').disabled, true);
        assert.match(app.texto('pnota-recogidaModo'), /Solo en Real/);
        app.pulsar('par-recogidaModo-1');
        await dormir(120);
        assert.equal(app.sim.valor('recogidaModo'), '0');
        // en real: Fija o Camara, y con camara se activan la zona permitida y las correcciones
        app.pulsar('modo-real');
        await hasta(() => app.sim.valor('modoSimulacion') === 'FALSE', 'modo real');
        await hasta(() => app.$('par-recogidaModo-1').disabled === false, 'recogida elegible en real');
        assert.equal(app.$('pitem-camaraOffsetX').classList.contains('inactivo'), true);   // modo Fija
        app.pulsar('par-recogidaModo-1');
        await hasta(() => app.sim.valor('recogidaModo') === '1', 'recogida con camara');
        await hasta(() => app.$('pitem-camaraOffsetX').classList.contains('inactivo') === false, 'correcciones activas');
        assert.equal(app.$('pitem-recogidaTolX').classList.contains('inactivo'), false);
        assert.equal(app.$('pitem-tMaxCamara').classList.contains('inactivo'), false);
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('con la tanda en marcha, los ajustes de Parametros se bloquean', async () => {
    const app = await abrir({valores: {hmiConfirmar: 'FALSE'}});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        app.pulsarPopup('OK');
        await hasta(() => app.sim.valor('hmiFase') !== String(L.FASES.ESPERA_INICIAR), 'tanda en marcha');
        await hasta(() => app.$('pitem-tAgarre').classList.contains('inactivo'), 'ajuste bloqueado');
        assert.match(app.texto('pnota-tAgarre'), /Bloqueado mientras la tanda está en marcha/);
        assert.equal(app.$('par-agarreModo-1').disabled, true);
        const antes = app.sim.valor('tAgarre');
        app.w.CajaPinzaPrueba.ui.campos.tAgarre.onchange('9');
        await dormir(120);
        assert.equal(app.sim.valor('tAgarre'), antes);
    } finally { app.cerrar(); }
});
