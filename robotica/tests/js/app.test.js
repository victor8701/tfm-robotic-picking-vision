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
            ['Recogida', 'Cámara', 'Pinza y agarre', 'Tiempos', 'Movimiento y seguridad']);
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

// ---------------------------------------------------------------- valores por defecto y fichero CSV
const CARPETA = '$HOME/parametros';

test('Valores por defecto: pide confirmacion, repone lo modificado (tambien mesa y protegidos) y no toca lo de la tanda', async () => {
    const app = await abrir({valores: {velocidad: '40', tAgarre: '1.5', mesaHueco: '25', seguroZ: '560', nCajas: '3', hmiMensajes: 'TRUE'}});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('tab-parametros');
        app.pulsar('par-defecto');
        await hasta(() => app.popup().length > 0, 'popup');
        const texto = app.popup().join(' | ');
        assert.match(texto, /valores por defecto del módulo en \d+ ajustes/);
        assert.match(texto, /Incluye ajustes protegidos: .*Velocidad máxima.*Punto de espera Z/);
        assert.match(texto, /guárdalos antes en un fichero/);
        app.pulsarPopup('Cancel');
        await dormir(150);
        assert.equal(app.sim.valor('velocidad'), '40');
        app.pulsar('par-defecto');
        await hasta(() => app.popup().length > 0, 'popup otra vez');
        app.pulsarPopup('OK');
        await hasta(() => ['velocidad', 'tAgarre', 'mesaHueco', 'seguroZ'].every((c) => app.sim.valor(c) === {velocidad: '100', tAgarre: '0', mesaHueco: '40', seguroZ: '543'}[c]), 'ajustes repuestos');
        assert.match(app.texto('par-estado'), /Valores por defecto puestos en \d+ ajustes/);
        assert.equal(app.sim.valor('nCajas'), '3');            // lo de cada tanda no se toca
        assert.equal(app.sim.valor('hmiMensajes'), 'TRUE');
        // ya estan todos: lo dice y no pregunta
        app.pulsar('par-defecto');
        await dormir(150);
        assert.equal(app.popup().length, 0);
        assert.match(app.texto('par-estado'), /ya tienen su valor por defecto/);
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('Guardar: escribe el CSV en $HOME/parametros con el nombre elegido y pide confirmacion para sustituirlo', async () => {
    const app = await abrir({valores: {velocidad: '40', tAgarre: '1.5'}});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('tab-parametros');
        await hasta(() => /Aún no hay ningún fichero guardado/.test(app.texto('par-ficheros')), 'lista vacia');
        const ui = app.w.CajaPinzaPrueba.ui;
        ui.nombreFichero.text = 'lab 1.csv';   // el .csv se admite y se ignora
        app.pulsar('par-guardar');
        await hasta(() => app.sim.ficheros[CARPETA + '/lab 1.csv'] !== undefined, 'fichero escrito');
        const csv = app.sim.ficheros[CARPETA + '/lab 1.csv'];
        assert.match(csv, /^parametro;valor;unidad;descripcion\r\n/);
        assert.match(csv, /\r\nvelocidad;40;mm\/s;/);
        assert.match(csv, /\r\ntAgarre;1\.5;s;/);
        assert.match(app.texto('par-estado'), /Guardado en \$HOME\/parametros\/lab 1\.csv \(\d+ ajustes\)/);
        await hasta(() => app.texto('par-ficheros') === 'lab 1.csv', 'el fichero sale en la lista');
        // otra vez con el mismo nombre: pregunta antes de sustituir
        app.sim.pers.tAgarre = '3';
        await hasta(() => app.w.document.querySelector('#in-tAgarre .fp-components-input-container p').textContent === '3', 'la app ve el cambio');
        app.pulsar('par-guardar');
        await hasta(() => app.popup().length > 0, 'popup de sustitucion');
        assert.match(app.popup().join(' '), /Ya existe lab 1\.csv/);
        app.pulsarPopup('Cancel');
        await dormir(150);
        assert.match(app.sim.ficheros[CARPETA + '/lab 1.csv'], /\r\ntAgarre;1\.5;s;/);   // sin cambios
        app.pulsar('par-guardar');
        await hasta(() => app.popup().length > 0, 'popup otra vez');
        app.pulsarPopup('OK');
        await hasta(() => /\r\ntAgarre;3;s;/.test(app.sim.ficheros[CARPETA + '/lab 1.csv']), 'fichero sustituido');
        await dormir(80);   // deja terminar el aviso y la lista que siguen al guardado
        // tocar un fichero tocando el chip: el nombre se rellena
        ui.nombreFichero.text = 'otro';
        app.w.document.querySelector('#par-ficheros button').click();
        assert.equal(ui.nombreFichero.text, 'lab 1');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('un nombre de fichero no valido no escribe nada y lo explica', async () => {
    const app = await abrir();
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        const ui = app.w.CajaPinzaPrueba.ui;
        for (const nombre of ['', '../x', 'a/b', 'niño']) {
            ui.nombreFichero.text = nombre;
            app.pulsar('par-guardar');
            await dormir(60);
            assert.equal(app.$('par-estado').className, 'param-estado error', JSON.stringify(nombre));
        }
        assert.match(app.texto('par-estado'), /letras, números/);
        assert.deepEqual(Object.keys(app.sim.ficheros), []);
        ui.nombreFichero.text = 'ok';
        app.pulsar('par-cargar');
        await hasta(() => /No encuentro \$HOME\/parametros\/ok\.csv/.test(app.texto('par-estado')), 'no existe');
        assert.equal(app.$('par-estado').className, 'param-estado error');
    } finally { app.cerrar(); }
});

test('Cargar: lee el CSV, enseña lo que cambia, ignora lo que no vale y escribe en RAPID al aceptar', async () => {
    const csv = ['parametro;valor;unidad;descripcion', 'velocidad;40;mm/s;x', 'tAgarre;1,5;s;x', 'mesaX0;-850;mm;x', 'nCajas;9;;x',
        'tMaxPinza;0.1;s;x', 'agarreModo;1;;x'].join('\r\n');
    const app = await abrir({ficheros: {[CARPETA + '/prueba.csv']: csv}});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('tab-parametros');
        await hasta(() => app.texto('par-ficheros') === 'prueba.csv', 'lista de ficheros');
        const ui = app.w.CajaPinzaPrueba.ui;
        ui.nombreFichero.text = 'prueba';
        app.pulsar('par-cargar');
        await hasta(() => app.popup().length > 0, 'popup');
        const texto = app.popup().join(' | ');
        assert.match(texto, /prueba\.csv: cambian 4 de 4 ajustes/);
        assert.match(texto, /Velocidad máxima: 100 → 40 mm\/s/);
        assert.match(texto, /Incluye ajustes protegidos: Velocidad máxima/);
        assert.match(texto, /Se ignoran 2 líneas: línea 5 \(nCajas\): ajuste desconocido; línea 6 \(tMaxPinza\): fuera de margen/);
        assert.equal(app.sim.valor('velocidad'), '100');   // todavia no
        app.pulsarPopup('OK');
        await hasta(() => app.sim.valor('velocidad') === '40' && app.sim.valor('tAgarre') === '1.5'
            && app.sim.valor('mesaX0') === '-850' && app.sim.valor('agarreModo') === '1', 'ajustes cargados');
        assert.equal(app.sim.valor('nCajas'), '1');   // lo que el fichero trae de mas no se aplica
        assert.equal(app.sim.valor('tMaxPinza'), '3');
        assert.match(app.texto('par-estado'), /Cargados 4 ajustes de \$HOME\/parametros\/prueba\.csv/);
        // cargarlo otra vez no cambia nada
        app.pulsar('par-cargar');
        await hasta(() => /ya valen lo mismo/.test(app.texto('par-estado')), 'sin cambios');
        assert.equal(app.popup().length, 0);
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('Guardar y cargar de vuelta: lo guardado se recupera despues de cambiarlo', async () => {
    const app = await abrir({valores: {velocidad: '60', seguroX: '580', aperturaPinza: '90', recogidaTolX: '30'}});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        const ui = app.w.CajaPinzaPrueba.ui;
        ui.nombreFichero.text = 'mi puesta';
        app.pulsar('par-guardar');
        await hasta(() => app.sim.ficheros[CARPETA + '/mi puesta.csv'] !== undefined, 'guardado');
        // se vuelve a los valores por defecto y se carga lo guardado
        app.pulsar('par-defecto');
        await hasta(() => app.popup().length > 0, 'popup defectos');
        app.pulsarPopup('OK');
        await hasta(() => app.sim.valor('velocidad') === '100' && app.sim.valor('aperturaPinza') === '0', 'por defecto');
        app.pulsar('par-cargar');
        await hasta(() => app.popup().length > 0, 'popup carga');
        // los 4 de arriba y la zona de la mesa del arnes de pruebas (la antigua), que tambien se guarda y se recupera
        assert.match(app.popup().join(' '), /cambian 6 de \d+ ajustes/);
        app.pulsarPopup('OK');
        await hasta(() => app.sim.valor('velocidad') === '60' && app.sim.valor('seguroX') === '580'
            && app.sim.valor('aperturaPinza') === '90' && app.sim.valor('recogidaTolX') === '30', 'recuperado');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('Cargar y Valores por defecto se bloquean con la tanda en marcha; Guardar sigue valiendo', async () => {
    const app = await abrir({valores: {hmiConfirmar: 'FALSE'}, ficheros: {[CARPETA + '/a.csv']: 'velocidad;40'}});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        assert.equal(app.$('par-cargar').disabled, false);
        app.pulsarFp('btn-iniciar');
        await hasta(() => app.popup().length > 0, 'popup');
        app.pulsarPopup('OK');
        await hasta(() => app.$('par-cargar').disabled && app.$('par-defecto').disabled, 'botones bloqueados');
        assert.equal(app.$('par-guardar').disabled, false);
        const ui = app.w.CajaPinzaPrueba.ui;
        ui.nombreFichero.text = 'en marcha';
        app.pulsar('par-guardar');
        await hasta(() => app.sim.ficheros[CARPETA + '/en marcha.csv'] !== undefined, 'guardar vale en marcha');
    } finally { app.cerrar(); }
});

test('si el controlador no deja usar ficheros, la app lo dice con el motivo', async () => {
    const app = await abrir({falloFicheros: 'sin permiso de fileservice'});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('tab-parametros');
        const ui = app.w.CajaPinzaPrueba.ui;
        ui.nombreFichero.text = 'x';
        app.pulsar('par-guardar');
        await hasta(() => /No he podido guardar \$HOME\/parametros\/x\.csv/.test(app.texto('par-estado')), 'error al guardar');
        assert.match(app.texto('par-estado'), /sin permiso de fileservice/);
        app.pulsar('par-cargar');
        await hasta(() => /No encuentro \$HOME\/parametros\/x\.csv/.test(app.texto('par-estado')) && /sin permiso/.test(app.texto('par-estado')), 'error al cargar');
        assert.equal(app.$('par-estado').className, 'param-estado error');
    } finally { app.cerrar(); }
});

test('la carpeta de fotos se elige con botones entre las que da el PC, se ve el numero de fotos y Valores por defecto la deja en la camara de la celda', async () => {
    const dicho = [];
    const app = await abrir({valores: {modoSimulacion: 'FALSE', camaraLista1: '"juego_a;juego_b"', camaraLista2: '"celda"'},
        camara: (carpeta) => { dicho.push(carpeta); return carpeta === 'celda' ? {fotos: 3, estado: 'ok'} : {fotos: 0, estado: 'no existe'}; }});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('tab-parametros');
        app.pulsar('pnav-camara');
        assert.equal(app.$('psec-camara').hidden, false);
        // los botones salen de la lista del PC: la camara de la celda y tres carpetas
        const botones = () => Array.from(app.$('pcar-camaraCarpeta').querySelectorAll('button')).map((b) => b.textContent);
        assert.deepEqual(botones(), ['La del PC (su configuración)', 'juego_a', 'juego_b', 'celda']);
        assert.equal(app.$('par-camaraCarpeta-0').classList.contains('activo'), true);
        assert.equal(app.texto('plect-camaraFotos'), '—');
        // elegir una: se escribe en la PERS y, cuando el PC responde, se ve cuantas fotos tiene
        app.pulsar('par-camaraCarpeta-3');
        await hasta(() => app.sim.valor('camaraCarpeta') === '"celda"', 'carpeta escrita en RAPID');
        await hasta(() => app.texto('plect-camaraFotos') === '3 fotos', 'el PC cuenta las fotos');
        assert.equal(app.texto('plect-camaraEstado'), 'ok');
        assert.equal(app.$('par-camaraCarpeta-3').classList.contains('activo'), true);
        assert.equal(app.$('par-camaraCarpeta-0').classList.contains('activo'), false);
        app.pulsar('par-camaraCarpeta-1');
        await hasta(() => app.texto('plect-camaraEstado') === 'no existe', 'estado de una carpeta que el PC no abre');
        assert.deepEqual(dicho, ['celda', 'juego_a']);
        // Valores por defecto: la carpeta vuelve a la camara de la celda (aunque no sea numerica)
        app.pulsar('par-defecto');
        await hasta(() => app.popup().length > 0, 'popup de valores por defecto');
        assert.match(app.popup().join(' '), /valores por defecto del módulo en \d+ ajustes/);
        app.pulsarPopup('OK');
        await hasta(() => app.sim.valor('camaraCarpeta') === '""', 'carpeta vuelta a la camara de la celda');
        await hasta(() => app.$('par-camaraCarpeta-0').classList.contains('activo'), 'boton de la camara de la celda activo');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});

test('en simulacion los botones de la carpeta de fotos estan apagados y la app no escribe nada', async () => {
    const app = await abrir({valores: {camaraLista1: '"juego_a"'}});
    try {
        app.sim.play();
        await hasta(() => app.texto('banner-titulo') === 'Listo para empezar', 'fase 1');
        app.pulsar('tab-parametros');
        app.pulsar('pnav-camara');
        assert.equal(app.$('par-camaraCarpeta-1').disabled, true);
        assert.match(app.texto('pnota-camaraCarpeta'), /Solo en Real/);
        app.pulsar('par-camaraCarpeta-1');
        await dormir(120);
        assert.equal(app.sim.valor('camaraCarpeta'), '""');
        assert.deepEqual(app.errores, []);
    } finally { app.cerrar(); }
});
