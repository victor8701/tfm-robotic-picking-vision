// Pruebas de la logica de la app CajaPinza (sin DOM ni RWS). Las lanza tests/test_flexpendant.py con Node.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const L = require(path.join(__dirname, '..', '..', 'flexpendant', 'CajaPinza', 'logica.js'));
const F = L.FASES;

// Estado de una tanda en marcha: el programa corre, el PC esta conectado, 5 cajas en simulacion.
function estado(cambios) {
    return Object.assign(L.estadoInicial(), {
        rws: true, ejecucion: 'running', usarHmi: true, pcConectado: true, nCajas: 5, semilla: 1234, indiceFijo: 0,
        egmMaxPos: 1500,
        // La zona de la mesa de la simulacion antes de colocarla donde esta ahora (mesa_marron en -1120, 342):
        // los numeros de estas pruebas (2 o 5 sitios) son de esa zona. Los valores por defecto actuales se prueban aparte.
        mesaX0: -1120, mesaY0: 342
    }, cambios);
}

test('la secuencia de giros es la de RAPID (semilla 1234 -> -75, 30, 60, -75, -30)', () => {
    assert.deepEqual(L.secuenciaGiros(5, 1234, 0), [-75, 30, 60, -75, -30]);
});

test('con indiceFijo valido todas las cajas llevan ese giro (7 = 0 grados)', () => {
    assert.deepEqual(L.secuenciaGiros(4, 1234, 7), [0, 0, 0, 0]);
    assert.deepEqual(L.secuenciaGiros(2, 1234, 1), [-90, -90]);
    assert.deepEqual(L.secuenciaGiros(2, 1234, 12), [75, 75]);
});

test('un indiceFijo fuera de 1..12 vale como al azar, como en RAPID', () => {
    for (const k of [0, 13, -1, 99]) {
        assert.deepEqual(L.secuenciaGiros(5, 1234, k), [-75, 30, 60, -75, -30]);
    }
});

test('el generador da enteros exactos de 0 a 8191 y recorre el periodo completo', () => {
    // RAPID guarda num en 24 bits: el producto semilla*1021+11 debe seguir siendo exacto
    const maximo = (L.SEMILLA_MOD - 1) * 1021 + 11;
    assert.ok(maximo < 8388608, 'el producto del generador cabe en un num de RAPID');
    const vistos = new Set();
    let s = 1234;
    for (let i = 0; i < L.SEMILLA_MOD; i++) {
        s = L.siguienteSemilla(s);
        assert.ok(Number.isInteger(s) && s >= 0 && s < L.SEMILLA_MOD);
        vistos.add(s);
    }
    assert.equal(vistos.size, L.SEMILLA_MOD);
});

test('los 12 giros van de -90 a 75 en pasos de 15 y el indice 7 es 0', () => {
    const giros = Array.from({length: 12}, (_, i) => L.giroDeIndice(i + 1));
    assert.deepEqual(giros, [-90, -75, -60, -45, -30, -15, 0, 15, 30, 45, 60, 75]);
});

test('nuevaSemilla y limitarCajas respetan sus topes', () => {
    assert.equal(L.nuevaSemilla(() => 0), 0);
    assert.equal(L.nuevaSemilla(() => 0.999999999), 8191);
    assert.ok(L.semillaValida(L.nuevaSemilla()));
    assert.equal(L.limitarCajas(0), 1);
    assert.equal(L.limitarCajas(-5), 1);
    assert.equal(L.limitarCajas(1000), 100);
    assert.equal(L.limitarCajas('7'), 7);
    assert.equal(L.limitarCajas(NaN), 1);
    assert.equal(L.semillaValida(8192), false);
    assert.equal(L.semillaValida(-1), false);
    assert.equal(L.semillaValida(12.5), false);
});

test('textoGiro usa el signo menos tipografico y tolera lo que no se sabe', () => {
    assert.equal(L.textoGiro(-75), '−75°');
    assert.equal(L.textoGiro(30), '30°');
    assert.equal(L.textoGiro(0), '0°');
    assert.equal(L.textoGiro(null), '—');
    assert.equal(L.textoGiro(undefined), '—');
});

test('conversiones de lo que devuelve RWS (cadenas en bruto)', () => {
    assert.equal(L.aBool('TRUE'), true);
    assert.equal(L.aBool('FALSE'), false);
    assert.equal(L.aBool(' true '), true);
    assert.equal(L.aBool(true), true);
    assert.equal(L.aBool(undefined), false);
    assert.equal(L.aNum('-75'), -75);
    assert.equal(L.aNum('0.5'), 0.5);
    assert.equal(L.aNum('basura', 3), 3);
    assert.equal(L.aTexto('"hola mundo"'), 'hola mundo');
    assert.equal(L.aTexto('""'), '');
    assert.equal(L.aTexto(null), '');
    assert.equal(L.aTexto('sin comillas'), 'sin comillas');
});

test('aplicarVariable pone cada PERS en su campo y no toca las que la app solo escribe', () => {
    const e = L.estadoInicial();
    L.aplicarVariable(e, 'hmiFase', '5');
    L.aplicarVariable(e, 'nCajas', '12');
    L.aplicarVariable(e, 'modoSimulacion', 'FALSE');
    L.aplicarVariable(e, 'hmiMensaje', '"El PC no ha dirigido la caja 1"');
    L.aplicarVariable(e, 'semillaGiros', '77');
    L.aplicarVariable(e, 'hmiIniciar', 'TRUE');
    L.aplicarVariable(e, 'noExiste', 'TRUE');
    assert.equal(e.fase, 5);
    assert.equal(e.nCajas, 12);
    assert.equal(e.modoSimulacion, false);
    assert.equal(e.mensaje, 'El PC no ha dirigido la caja 1');
    assert.equal(e.semilla, 77);
    assert.equal('iniciar' in e, false);
    assert.equal('noExiste' in e, false);
});

test('normalizarEjecucion acepta el texto de RWS y un objeto con state', () => {
    assert.equal(L.normalizarEjecucion('running'), 'running');
    assert.equal(L.normalizarEjecucion('stopped'), 'stopped');
    assert.equal(L.normalizarEjecucion({state: 'running'}), 'running');
    assert.equal(L.normalizarEjecucion('otra'), null);
    assert.equal(L.normalizarEjecucion(undefined), null);
});

test('puntosCaja: giro 0 es un cuadrado recto y el giro positivo es antihorario (y hacia arriba)', () => {
    assert.deepEqual(L.puntosCaja(0, 50, 120, 120), [[70, 170], [170, 170], [170, 70], [70, 70]]);
    // 90 grados: el mismo cuadrado con las esquinas desplazadas una posicion
    assert.deepEqual(L.puntosCaja(90, 50, 120, 120), [[170, 170], [170, 70], [70, 70], [70, 170]]);
    // 30 grados: la esquina (+1, -1) sube hacia la derecha, es decir, y de pantalla baja menos que en 0 grados
    const p = L.puntosCaja(30, 50, 120, 120);
    assert.deepEqual(p[1], [188.3, 138.3]);
    assert.deepEqual(p[2], [138.3, 51.7]);
});

// ---------------------------------------------------------------- calcularVista
test('sin conexion con RAPID: aviso de error y ningun boton', () => {
    const v = L.calcularVista(L.estadoInicial());
    assert.equal(v.banner.tono, 'error');
    assert.equal(v.botones.iniciar.habilitado, false);
    assert.equal(v.botones.cajaEnPosicion.habilitado, false);
    assert.ok(v.avisos.some(a => a.nivel === 'error'));
});

test('esperando INICIAR: se puede iniciar y ajustar, pero no pulsar CAJA EN POSICION', () => {
    const v = L.calcularVista(estado({fase: F.ESPERA_INICIAR}));
    assert.equal(v.botones.iniciar.habilitado, true);
    assert.equal(v.botones.cajaEnPosicion.habilitado, false);
    assert.equal(v.ajustes.editable, true);
    assert.equal(v.banner.titulo, 'Listo para empezar');
    assert.equal(v.caja.texto, '5 cajas en la tanda');
    assert.equal(v.giros.length, 5);
    assert.deepEqual(v.giros.map(g => g.giro), [-75, 30, 60, -75, -30]);
    assert.ok(v.giros.every(g => g.estado === 'pendiente'));
    assert.match(v.resumenTanda, /5 cajas · simulación · giros al azar \(semilla 1234\)/);
});

test('esperando CAJA EN POSICION con boton: solo vale ese boton y los ajustes se bloquean', () => {
    const v = L.calcularVista(estado({fase: F.ESPERA_CAJA, cajaNum: 1, giroCaja: 30}));
    assert.equal(v.botones.cajaEnPosicion.habilitado, true);
    assert.equal(v.botones.iniciar.habilitado, false);
    assert.equal(v.botones.iniciar.motivo, 'La tanda ya está en marcha.');
    assert.equal(v.ajustes.editable, false);
    assert.equal(v.ajustes.nCajas.menosHabil, false);
    assert.match(v.banner.titulo, /CAJA EN POSICIÓN/);
    assert.equal(v.caja.texto, 'Caja 2 de 5');
    assert.equal(v.ajustes.confirmar.editable, true);
    assert.match(v.ajustes.confirmar.nota, /siguiente caja/);
});

test('sin boton (hmiConfirmar FALSE) en real el boton no vale: RAPID espera la senal', () => {
    const v = L.calcularVista(estado({fase: F.ESPERA_CAJA, confirmar: false, modoSimulacion: false}));
    assert.equal(v.botones.cajaEnPosicion.habilitado, false);
    assert.match(v.botones.cajaEnPosicion.motivo, /CajaEnRecogida/);
    assert.match(v.banner.titulo, /CajaEnRecogida/);
});

test('programa parado a mitad de caja: se avisa y no vale ningun boton', () => {
    const v = L.calcularVista(estado({fase: F.EGM_ABIERTO, ejecucion: 'stopped'}));
    assert.equal(v.banner.titulo, 'Programa parado');
    assert.match(v.banner.detalle, /EGM abierto/);
    assert.equal(v.botones.cajaEnPosicion.habilitado, false);
    assert.equal(v.botones.iniciar.habilitado, false);
    const parado = L.calcularVista(estado({fase: F.ESPERA_INICIAR, ejecucion: 'stopped'}));
    assert.equal(parado.botones.iniciar.habilitado, false);
    assert.match(parado.botones.iniciar.motivo, /Play/);
});

test('si no se sabe el estado de ejecucion, manda la fase', () => {
    const v = L.calcularVista(estado({fase: F.ESPERA_INICIAR, ejecucion: null}));
    assert.equal(v.botones.iniciar.habilitado, true);
    assert.equal(v.chips[0].valor, '—');
});

test('con usarHmi = FALSE la app solo muestra', () => {
    const v = L.calcularVista(estado({fase: F.ESPERA_INICIAR, usarHmi: false}));
    assert.equal(v.botones.iniciar.habilitado, false);
    assert.match(v.botones.iniciar.motivo, /usarHmi/);
    assert.ok(v.avisos.some(a => /usarHmi = FALSE/.test(a.texto)));
});

test('progreso y pasos mientras se hace la caja 3 de 5', () => {
    const v = L.calcularVista(estado({fase: F.AGARRADA, cajaNum: 2}));
    assert.equal(v.caja.texto, 'Caja 3 de 5');
    assert.equal(v.caja.actual, 3);
    const estados = v.pasos.map(p => p.estado);
    assert.deepEqual(estados, ['hecho', 'hecho', 'hecho', 'hecho', 'actual', 'pendiente', 'pendiente', 'pendiente']);
    assert.ok(v.progreso > 2 / 5 && v.progreso < 3 / 5);
    assert.deepEqual(v.giros.map(g => g.estado), ['hecha', 'hecha', 'actual', 'pendiente', 'pendiente']);
});

test('en real no hay pasos de cinta ni lista de giros, y el giro sale del PC', () => {
    const v = L.calcularVista(estado({fase: F.EGM_ABIERTO, modoSimulacion: false, giroPc: -15}));
    assert.deepEqual(v.pasos.map(p => p.id), ['posicion', 'egm', 'agarrada', 'soltada', 'cerrando', 'vuelta']);
    assert.equal(v.giros.length, 0);
    assert.equal(v.orientacion.giro, -15);
    assert.match(v.orientacion.etiqueta, /PC/);
    assert.equal(v.ajustes.giro.editable, false);
    assert.equal(v.senales.some(s => s.id === 'cinta'), false);
    assert.match(v.chips[2].valor, /REAL/);
});

test('tanda terminada: todo hecho y la tanda siguiente exige Play', () => {
    const v = L.calcularVista(estado({fase: F.FIN, cajaNum: 5, giroCaja: -30, ejecucion: 'stopped'}));
    assert.equal(v.caja.texto, '5 de 5 cajas hechas');
    assert.equal(v.progreso, 1);
    assert.ok(v.pasos.every(p => p.estado === 'hecho'));
    assert.ok(v.giros.every(g => g.estado === 'hecha'));
    assert.equal(v.banner.tono, 'ok');
    assert.equal(v.ajustes.editable, true);
    assert.match(v.botones.iniciar.motivo, /Play/);
    assert.match(v.orientacion.etiqueta, /Última/);
});

test('la orientacion compara lo que puso RAPID con lo que lee el PC', () => {
    const bien = L.calcularVista(estado({fase: F.EGM_ABIERTO, giroCaja: -75, giroPc: -75}));
    assert.equal(bien.orientacion.coincide, true);
    assert.equal(bien.orientacion.texto, '−75°');
    assert.equal(bien.orientacion.puntos.length, 4);
    assert.ok(!bien.avisos.some(a => a.nivel === 'error'));

    const mal = L.calcularVista(estado({fase: F.EGM_ABIERTO, giroCaja: -75, giroPc: 30}));
    assert.equal(mal.orientacion.coincide, false);
    assert.ok(mal.avisos.some(a => a.nivel === 'error' && /PC lee 30°/.test(a.texto)));

    const aun = L.calcularVista(estado({fase: F.EGM_ABIERTO, giroCaja: -75}));
    assert.equal(aun.orientacion.coincide, null);
});

test('antes de empezar se dibuja la primera caja prevista de la lista', () => {
    const v = L.calcularVista(estado({fase: F.ESPERA_INICIAR}));
    assert.equal(v.orientacion.giro, -75);
    assert.match(v.orientacion.etiqueta, /prevista/);
    const sin = L.calcularVista(estado({fase: F.ESPERA_INICIAR, modoSimulacion: false}));
    assert.equal(sin.orientacion.giro, null);
    assert.equal(sin.orientacion.puntos, null);
});

test('avisos: PC sin conectar, semilla fuera de rango, PERS que faltan y mensaje de RAPID', () => {
    const v = L.calcularVista(estado({fase: F.ESPERA_INICIAR, pcConectado: false, semilla: 99999,
        faltan: ['hmiFase', 'hmiMensaje'], mensaje: 'La caja no ha llegado al sensor de la cinta'}));
    const textos = v.avisos.map(a => a.texto).join(' | ');
    assert.match(textos, /PC no está conectado/);
    assert.match(textos, /semilla/);
    assert.match(textos, /hmiFase, hmiMensaje/);
    assert.match(textos, /RAPID: La caja no ha llegado/);
    assert.equal(v.botones.iniciar.avisoSinPc, true);
});

test('en error, el mensaje de RAPID sale como error', () => {
    const v = L.calcularVista(estado({fase: F.ERROR, mensaje: 'El PC no ha dirigido la caja 1: paro. Revisa el PC.', ejecucion: 'stopped'}));
    assert.equal(v.banner.tono, 'error');
    assert.ok(v.avisos.some(a => a.nivel === 'error' && /dirigido/.test(a.texto)));
    assert.equal(v.ajustes.editable, false);
});

test('una fase que la app no conoce no rompe la pantalla', () => {
    const v = L.calcularVista(estado({fase: 42}));
    assert.equal(v.banner.tono, 'error');
    assert.match(v.banner.titulo, /42/);
});

test('los numeros de fase no se repiten y cada una tiene texto', () => {
    const valores = Object.values(F);
    assert.equal(new Set(valores).size, valores.length);
    for (const [nombre, valor] of Object.entries(F)) {
        const t = L.textoFase(valor, L.estadoInicial());
        assert.ok(t.titulo && t.detalle && t.tono, nombre);
        assert.ok(!/^Fase \d+$/.test(t.titulo), nombre + ' sin texto');
    }
});

test('el estado de las senales se pasa a la vista', () => {
    const v = L.calcularVista(estado({fase: F.AGARRADA, senales: {sensor: false, cinta: false, pinzaCerrar: true, pinzaCerrada: null}}));
    const por = Object.fromEntries(v.senales.map(s => [s.id, s.valor]));
    assert.equal(por.pinzaCerrar, true);
    assert.equal(por.sensor, false);
    assert.equal(por.pinzaCerrada, null);
});

// ---------------------------------------------------------------- mesa de deposito
// cajas iguales (cajasVariables apagado) salvo que la prueba diga otra cosa: asi la cuenta de la mesa es exacta
const sim = (cambios) => estado(Object.assign({fase: F.ESPERA_INICIAR, cajasVariables: false}, cambios));

test('el limite del EGM, el alcance y el espacio del puente descartan huecos', () => {
    const lim = {egmMaxPos: 1000, alcanceMax: 790};
    assert.equal(L.puntoPermitido({x: -60, y: 482, z: 420}, lim), true);
    assert.equal(L.puntoPermitido({x: -300, y: 482, z: 420}, lim), false);          // a 1031 mm del inicio del EGM
    assert.equal(L.puntoPermitido({x: -60, y: 800, z: 420}, {egmMaxPos: 1500, alcanceMax: 790}), false);   // radio 802 > 790
    assert.equal(L.puntoPermitido({x: -650, y: 300, z: 420}, {egmMaxPos: 1500, alcanceMax: 790}), false);  // fuera del puente (x < -600)
    assert.equal(L.puntoPermitido({x: 100, y: 300, z: 700}, {egmMaxPos: 1500, alcanceMax: 790}), false);   // brida a 847 > 800
});

test('INICIAR se bloquea si la tanda no cabe en la mesa y dice cuantas caben', () => {
    const v = L.calcularVista(sim({egmMaxPos: 1000, nCajas: 5}));
    assert.equal(v.mesa.capacidad, 2);
    assert.equal(v.botones.iniciar.habilitado, false);
    assert.match(v.botones.iniciar.motivo, /caben 2 cajas y la tanda tiene 5/);
    assert.equal(v.ajustes.nCajas.sobra, true);
    assert.match(v.ajustes.nCajas.nota, /admite 2 cajas/);
    const ok = L.calcularVista(sim({egmMaxPos: 1000, nCajas: 2}));
    assert.equal(ok.botones.iniciar.habilitado, true);
});

test('con una mesa mas grande la tanda cabe; los campos tienen sus margenes', () => {
    const v = L.calcularVista(sim({egmMaxPos: 1500, nCajas: 6, mesaHueco: 10, mesaX0: -500, mesaLargo: 580, mesaAncho: 400}));
    assert.ok(v.mesa.capacidad >= 1);
    assert.equal(L.limitarCampoMesa('mesaLargo', 5), 50);
    assert.equal(L.limitarCampoMesa('mesaHueco', 1000), 300);
    assert.equal(L.limitarCampoMesa('mesaX0', '-1120.04'), -1120);
    assert.equal(L.limitarCampoMesa('mesaZ', 'x'), 0);
});

test('antes de empezar la tanda cajaNum cuenta 0 aunque RAPID conserve el de la anterior', () => {
    const v = L.calcularVista(sim({cajaNum: 5}));
    assert.equal(v.caja.hechas, 0);
    assert.ok(v.mesa.huecos.filter((h) => h.util).every((h) => h.estado !== 'hecha'));
});

test('los valores por defecto de la mesa son los de la mesa de la simulacion', () => {
    const e = L.estadoInicial();
    for (const [clave, valor] of Object.entries(L.MESA_SIM)) { assert.equal(e[clave], valor); }
});

const centros = (destinos) => destinos.map((d) => [Math.round(d.x * 10) / 10, Math.round(d.y * 10) / 10]);

test('la mesa de la simulacion (mesa_marron en -700, 350) deja 4 sitios con el limite 1000 y 8 con el 1500 por defecto', () => {
    const e = L.estadoInicial();
    assert.equal(e.egmMaxPos, 1500);
    assert.deepEqual([e.mesaX0, e.mesaY0], [-900, 150]);
    const con = (egm) => L.estimarMesa(L.mesaDeEstado(e), L.cajaDeReferencia(e), {egmMaxPos: egm, alcanceMax: 790});
    assert.equal(con(1000).capacidad, 4);
    assert.deepEqual(centros(con(1000).destinos), [[-300, 290], [-60, 290], [-230, 530], [10, 530]]);
    assert.equal(con(1500).capacidad, 8);
    assert.deepEqual(centros(con(1500).destinos),
        [[-600, 290], [-360, 290], [-120, 290], [120, 290], [-580, 530], [-340, 530], [-100, 530], [140, 530]]);
    // diez cajas de tamaños distintos caben todas con el limite por defecto
    const mezcla = [[200, 200, 200], [160, 120, 150], [120, 120, 100], [180, 140, 200], [140, 100, 120],
        [200, 120, 150], [150, 150, 100], [120, 100, 200], [180, 180, 150], [100, 100, 100]].map(([largo, ancho, alto]) => ({largo, ancho, alto}));
    assert.equal(L.repartir(L.mesaDeEstado(e), mezcla, {egmMaxPos: 1500, alcanceMax: 790}).sinSitio, null);
});

test('la zona antigua de la mesa (mesa_marron en -1120, 342) con el limite 1000 deja 2 sitios, con 1500 deja 5', () => {
    const e = estado({});
    const con = (egm) => L.estimarMesa(L.mesaDeEstado(e), L.cajaDeReferencia(e), {egmMaxPos: egm, alcanceMax: 790});
    assert.equal(con(1000).capacidad, 2);
    assert.deepEqual(centros(con(1000).destinos), [[-260, 482], [-70, 722]]);
    assert.equal(con(1500).capacidad, 5);
    assert.deepEqual(centros(con(1500).destinos), [[-600, 482], [-360, 482], [-120, 482], [-320, 722], [-80, 722]]);
});

test('las cajas se reparten en filas segun llegan, con medidas distintas, de x menor a mayor', () => {
    const mesa = {x0: -300, y0: 100, largo: 700, ancho: 500, z: 150, hueco: 20};
    const lim = {egmMaxPos: 1500, alcanceMax: 790};
    const cubos = L.repartir(mesa, new Array(4).fill({largo: 200, ancho: 200, alto: 200}), lim);
    assert.equal(cubos.sinSitio, null);
    assert.deepEqual(centros(cubos.destinos), [[-180, 220], [40, 220], [260, 220], [-180, 440]]);
    // medidas distintas: la fila mide lo que la caja mas ancha y la siguiente va pegada tras ella
    const mixtas = L.repartir(mesa, [{largo: 150, ancho: 100, alto: 120}, {largo: 120, ancho: 80, alto: 90},
        {largo: 150, ancho: 60, alto: 100}, {largo: 400, ancho: 150, alto: 100}, {largo: 100, ancho: 100, alto: 80}], lim);
    assert.equal(mixtas.sinSitio, null);
    const [a, b, c, d, f] = mixtas.destinos;
    assert.equal(a.y - 50, 120);                                     // borde cercano de la fila 1 = y0 + hueco
    assert.equal(b.x - 60, a.x + 75 + 20);                           // cada caja va tras la anterior, con hueco
    assert.equal(c.x - 75, b.x + 60 + 20);
    assert.equal(d.y - 75, 120 + 100 + 20);                          // fila 2: tras la caja mas ancha de la 1 (100) + hueco
    assert.ok(f.x - 50 >= d.x + 200 + 20 - 1e-9 || f.y > d.y);       // no se solapa con la anterior
});

test('si una caja no cabe, repartir dice cual y las anteriores siguen colocadas', () => {
    const mesa = {x0: -300, y0: 100, largo: 700, ancho: 500, z: 150, hueco: 20};
    const lim = {egmMaxPos: 1500, alcanceMax: 790};
    const r = L.repartir(mesa, [{largo: 150, ancho: 100, alto: 120}, {largo: 900, ancho: 100, alto: 120}], lim);
    assert.equal(r.sinSitio, 1);
    assert.equal(r.destinos.length, 1);
});

test('los puntos de un destino: entrada por +x fuera de la zona, sobre el hueco, deposito y salida', () => {
    const caja = {largo: 200, ancho: 200, alto: 200};
    const p = L.puntosDestino(caja, {x: -60, y: 482, zMesa: 320, xEntrada: 220, altoLibre: 200});
    assert.deepEqual(p.map((q) => [q.x, q.y, q.z]), [[220, 482, 485], [-60, 482, 485], [-60, 482, 420], [-60, 482, 585]]);
    // la salida sube por encima de la caja mas alta ya dejada
    const alta = L.puntosDestino({largo: 100, ancho: 100, alto: 80}, {x: 0, y: 400, zMesa: 100, xEntrada: 200, altoLibre: 300});
    assert.equal(alta[3].z, 485);   // z_seguro manda aqui; con zMesa 300 mandaria 300 + 300 + 65
    assert.equal(L.puntosDestino({largo: 100, ancho: 100, alto: 80}, {x: 0, y: 400, zMesa: 300, xEntrada: 200, altoLibre: 300})[3].z, 665);
});

test('la vista de la mesa cuenta sitios, marca los hechos y el actual y dibuja la zona inalcanzable', () => {
    const v = L.calcularVista(estado({fase: F.AGARRADA, cajaNum: 1, nCajas: 3}));
    assert.equal(v.mesa.capacidad, 5);
    assert.deepEqual(v.mesa.huecos.map((h) => h.estado), ['hecha', 'actual', 'prevista', 'libre', 'libre']);
    assert.match(v.mesa.resumen, /Caben 5 cajas de 200 × 200 × 200 mm\. La tanda \(3\) cabe\./);
    assert.deepEqual(v.mesa.campos.map((c) => c.clave),
        ['mesaX0', 'mesaY0', 'mesaLargo', 'mesaAncho', 'mesaZ', 'mesaHueco', 'cajaLargo', 'cajaAncho', 'cajaAlto']);
    assert.deepEqual([...new Set(v.mesa.campos.map((c) => c.grupo))], ['zona', 'caja']);   // el limite del EGM esta en Parametros
    assert.equal(v.mesa.geometria.huecos.length, 5);
    assert.ok(v.mesa.geometria.zona.w > 0 && v.mesa.geometria.inalcanzable.length > 0);
});

test('INICIAR se bloquea si la tanda no cabe (cajas iguales) y dice cuantas caben', () => {
    const v = L.calcularVista(sim({egmMaxPos: 1000, nCajas: 5}));
    assert.equal(v.mesa.capacidad, 2);
    assert.equal(v.botones.iniciar.habilitado, false);
    assert.match(v.botones.iniciar.motivo, /caben 2 cajas y la tanda tiene 5/);
    assert.equal(v.ajustes.nCajas.sobra, true);
    assert.match(v.ajustes.nCajas.nota, /admite 2 cajas/);
    assert.equal(L.calcularVista(sim({egmMaxPos: 1000, nCajas: 2})).botones.iniciar.habilitado, true);
});

test('con cajas de tamanos distintos o en real, la estimacion no bloquea: el PC comprueba cada caja', () => {
    for (const cambios of [{cajasVariables: true}, {modoSimulacion: false}]) {
        const v = L.calcularVista(sim(Object.assign({egmMaxPos: 1000, nCajas: 5}, cambios)));
        assert.equal(v.botones.iniciar.habilitado, true);
        assert.match(v.mesa.resumen, /Con cajas más pequeñas que la de referencia caben más/);
        assert.match(v.ajustes.nCajas.nota, /comprobará las medidas reales/);
    }
});

test('con una mesa mas grande la tanda cabe; los campos tienen sus margenes', () => {
    const v = L.calcularVista(sim({egmMaxPos: 1500, nCajas: 6, mesaHueco: 10, mesaX0: -500, mesaLargo: 580, mesaAncho: 400}));
    assert.ok(v.mesa.capacidad >= 1);
    assert.equal(L.limitarCampoMesa('mesaLargo', 5), 50);
    assert.equal(L.limitarCampoMesa('mesaHueco', 1000), 300);
    assert.equal(L.limitarCampoMesa('mesaX0', '-1120.04'), -1120);
    assert.equal(L.limitarCampoMesa('mesaZ', 'x'), 0);
    assert.equal(L.limitarCampoMesa('cajaLargo', 5000), 600);
    assert.equal(L.limitarCampoMesa('egmMaxPos', 100), 500);
});

test('abortar vale mientras la tanda esta en marcha y no cuando el programa esta parado o sin empezar', () => {
    for (const fase of [F.ESPERA_INICIAR, F.COLOCANDO, F.ESPERA_CAJA, F.EGM_ABIERTO, F.VUELTA]) {
        assert.equal(L.calcularVista(estado({fase})).botones.abortar.habilitado, true, 'fase ' + fase);
    }
    for (const cambios of [{fase: F.PARADO}, {fase: F.FIN}, {fase: F.ERROR}, {fase: F.EGM_ABIERTO, ejecucion: 'stopped'}, {fase: F.EGM_ABIERTO, rws: false}]) {
        assert.equal(L.calcularVista(estado(cambios)).botones.abortar.habilitado, false, JSON.stringify(cambios));
    }
});

test('las medidas de la caja en curso y el estado de los mensajes llegan a la vista', () => {
    const v = L.calcularVista(estado({fase: F.EGM_ABIERTO, caja: '150 x 100 x 120 mm', mensajes: false}));
    assert.equal(v.orientacion.medidas, '150 x 100 x 120 mm');
    const e = L.estadoInicial();
    L.aplicarVariable(e, 'hmiMensajes', 'FALSE');
    L.aplicarVariable(e, 'cajasVariables', 'TRUE');
    L.aplicarVariable(e, 'hmiCaja', '"150 x 100 x 120 mm"');
    assert.deepEqual([e.mensajes, e.cajasVariables, e.caja], [false, true, '150 x 100 x 120 mm']);
});

test('valores por defecto: simulacion con giros al azar y cajas distintas, mensajes apagados, esperar el boton', () => {
    const e = L.estadoInicial();
    assert.deepEqual(
        [e.modoSimulacion, e.indiceFijo, e.cajasVariables, e.mensajes, e.confirmar],
        [true, 0, true, false, true]);
    const v = L.calcularVista(Object.assign(e, {rws: true, ejecucion: 'running', fase: F.ESPERA_INICIAR, pcConectado: true}));
    assert.equal(v.ajustes.giro.modo, 'azar');
});

test('cada modo tiene sus ajustes por defecto: simulacion = azar y cajas distintas; real = esperar el boton', () => {
    assert.deepEqual(L.ajustesDeModo(true), {indiceFijo: 0, cajasVariables: true});
    assert.deepEqual(L.ajustesDeModo(false), {hmiConfirmar: true});
    // los nombres son PERS de RAPID que la app sabe escribir
    for (const modo of [true, false]) {
        for (const nombre of Object.keys(L.ajustesDeModo(modo))) {
            assert.ok(L.VARIABLES[nombre], nombre);
        }
    }
});

// ---------------------------------------------------------------- tarjeta Pinza
test('la pinza se ve abierta, cerrada, cerrando o abriendo segun la orden y su confirmacion', () => {
    const con = (orden, conf, cambios) => L.vistaPinza(estado(Object.assign({senales: {sensor: false, cinta: false, pinzaCerrar: orden, pinzaCerrada: conf}}, cambios)), 1000);
    assert.deepEqual([con(false, false).titulo, con(false, false).tono], ['ABIERTA', 'activo']);
    assert.deepEqual([con(true, true).titulo, con(true, true).tono], ['CERRADA', 'ok']);
    assert.deepEqual([con(true, false).titulo, con(true, false).tono], ['CERRANDO…', 'espera']);
    assert.deepEqual([con(false, true).titulo, con(false, true).tono], ['ABRIENDO…', 'espera']);
    assert.deepEqual([con(true, true).orden, con(true, true).confirmacion], [true, true]);
    // sin leer alguna de las dos senales no se inventa un estado
    for (const par of [[null, null], [true, null], [null, false]]) {
        const v = con(par[0], par[1]);
        assert.equal(v.estado, 'sin-lectura');
        assert.match(v.detalle, /Access Level = All/);
    }
});

test('si la confirmacion tarda mas de 3 s la tarjeta lo dice, como RAPID (fallo_pinza)', () => {
    const e = estado({senales: {sensor: false, cinta: false, pinzaCerrar: true, pinzaCerrada: false}});
    e.pinza.cambio = 10000;
    assert.equal(L.vistaPinza(e, 12500).titulo, 'CERRANDO…');
    const tarde = L.vistaPinza(e, 13100);
    assert.deepEqual([tarde.titulo, tarde.tono], ['SIN CONFIRMACIÓN', 'error']);
    assert.match(tarde.detalle, /fallo_pinza/);
    // y entra tambien por calcularVista
    assert.equal(L.calcularVista(e, 13100).pinza.titulo, 'SIN CONFIRMACIÓN');
});

test('las ordenes de pinza se cuentan por la senal PinzaCerrar y se reponen al empezar otra tanda', () => {
    const e = L.estadoInicial();
    e.nCajas = 3;
    L.ponerSenal(e, 'pinzaCerrar', false, 100);     // primera lectura: solo valor de partida
    L.ponerSenal(e, 'pinzaCerrada', false, 100);
    assert.deepEqual([e.pinza.cerrar, e.pinza.abrir, e.pinza.ultima], [0, 0, null]);
    e.cajaNum = 1;                                   // RAPID va por la caja 2
    L.ponerSenal(e, 'pinzaCerrar', true, 2000);
    L.ponerSenal(e, 'pinzaCerrar', true, 2100);     // una lectura repetida no cuenta
    L.ponerSenal(e, 'pinzaCerrada', true, 2200);
    L.ponerSenal(e, 'pinzaCerrar', false, 5000);
    assert.deepEqual([e.pinza.cerrar, e.pinza.abrir, e.pinza.ultima, e.pinza.caja, e.pinza.tUltima], [1, 1, 'abrir', 2, 5000]);
    assert.match(L.vistaPinza(e, 7000).resumen, /cerrar 1 · abrir 1 · última: abrir \(caja 2\) hace 2 s/);
    assert.match(L.vistaPinza(e, 5500).resumen, /ahora mismo/);
    // una tanda nueva (RAPID vuelve a esperar INICIAR) pone los contadores a cero
    e.fase = L.FASES.FIN;
    L.aplicarVariable(e, 'hmiFase', String(L.FASES.ESPERA_INICIAR));
    assert.deepEqual([e.pinza.cerrar, e.pinza.abrir, e.pinza.ultima], [0, 0, null]);
    assert.equal(e.pinza.cambio, 5000);   // lo ultimo que cambio la senal se conserva
});

// ---------------------------------------------------------------- ventana Parametros
test('los ajustes de puesta en marcha tienen por defecto los de RAPID', () => {
    const e = L.estadoInicial();
    assert.deepEqual([e.recogidaModo, e.recogidaX, e.recogidaY, e.zCinta], [0, 700, 0, 220]);
    assert.deepEqual([e.agarreModo, e.agarrePorcentaje, e.agarreMinimo, e.solapeMinimo, e.aperturaPinza], [0, 50, 10, 10, 0]);
    assert.deepEqual([e.tAntesAgarrar, e.tAgarre, e.tSuelta, e.tMaxPinza, e.tMaxCaja, e.tiempoConv], [0, 0, 0, 3, 40, 2.5]);
    assert.deepEqual([e.velocidad, e.zMinima, e.seguroX, e.seguroY, e.seguroZ, e.tcpZ, e.margenAproximacion], [100, 0, 600, -6.5, 543, 147, 65]);
    // todo ajuste de la ventana es una PERS que la app lee y escribe
    for (const c of L.CAMPOS_PARAMETROS) { assert.equal(L.VARIABLES[c.clave].escribe, true, c.clave); }
    for (const s of L.PARAMETROS) { for (const it of s.items) { assert.ok(L.VARIABLES[it.clave], it.clave); } }
});

test('la ventana Parametros reparte los ajustes en secciones y dice por que alguno no se puede cambiar', () => {
    const v = L.calcularVista(estado({fase: F.ESPERA_INICIAR})).parametros;
    assert.deepEqual(v.secciones.map((s) => s.id), ['recogida', 'pinza', 'tiempos', 'movimiento']);
    const item = (clave) => v.secciones.flatMap((s) => s.items).find((i) => i.clave === clave);
    // en simulacion, la camara y la recogida en Y no cuentan; X si, con aviso de que la estacion manda
    assert.equal(item('recogidaModo').activo, false);
    assert.match(item('recogidaModo').nota, /Solo en Real/);
    assert.equal(item('recogidaY').activo, false);
    assert.equal(item('recogidaX').activo, true);
    assert.match(item('recogidaX').nota, /x = 700/);
    assert.equal(item('agarreHundimiento').activo, false);   // modo Porcentaje
    assert.match(item('agarreHundimiento').nota, /modo Desde la tapa/);
    assert.equal(item('agarrePorcentaje').activo, true);
    assert.equal(item('alcanceMax').tipo, 'lectura');
    assert.equal(item('alcanceMax').activo, false);
    assert.deepEqual(['velocidad', 'zMinima', 'zCinta', 'tcpZ', 'seguroX', 'egmMaxPos', 'recogidaTolX'].map((c) => item(c).protegido), new Array(7).fill(true));
    assert.equal(item('tAgarre').protegido, false);
    // en real con camara: se activan los ajustes de la camara y X, Y
    const real = L.calcularVista(estado({fase: F.ESPERA_INICIAR, modoSimulacion: false, recogidaModo: 1})).parametros;
    const itemR = (clave) => real.secciones.flatMap((s) => s.items).find((i) => i.clave === clave);
    for (const c of ['recogidaModo', 'recogidaY', 'recogidaTolX', 'camaraOffsetX', 'camaraOffsetGiro', 'tMaxCamara']) { assert.equal(itemR(c).activo, true, c); }
    // con la tanda en marcha todo se bloquea
    const marcha = L.calcularVista(estado({fase: F.EGM_ABIERTO})).parametros;
    assert.equal(marcha.editable, false);
    assert.equal(marcha.secciones.flatMap((s) => s.items).every((i) => !i.activo), true);
});

test('la confirmacion de un ajuste protegido dice que cambia y de que a que', () => {
    const it = (clave) => L.CAMPOS_PARAMETROS.find((c) => c.clave === clave);
    const egm = L.textoConfirmacion(it('egmMaxPos'), 1500, 1000);
    assert.equal(egm.titulo, 'Cambiar el límite del EGM');
    assert.match(egm.lineas.join(' '), /¿Cambiarlo de 1000 a 1500 mm\?/);
    const vel = L.textoConfirmacion(it('velocidad'), 40, 100);
    assert.match(vel.lineas[0], /Empieza lento/);
    assert.equal(vel.lineas[1], '¿Cambiarlo de 100 a 40 mm/s?');
    assert.equal(L.limitarCampoMesa('velocidad', 500), 100);
    assert.equal(L.limitarCampoMesa('tMaxPinza', 0), 0.5);
    assert.equal(L.limitarCampoMesa('egmMaxPos', 100), 500);
});

test('altura de agarre: por porcentaje o desde la tapa, con minimo, alto minimo y apertura (como altura_agarre del PC)', () => {
    const ag = (cambios) => Object.assign({modo: 0, porcentaje: 50, hundimiento: 30, minimo: 10, solape: 10, apertura: 0}, cambios);
    const h = (caja, a) => L.alturaAgarre(caja, {agarre: ag(a)});
    assert.equal(h({largo: 200, ancho: 100, alto: 120}, {}).h, 60);
    assert.equal(h({largo: 200, ancho: 100, alto: 120}, {porcentaje: 75}).h, 90);
    for (const alto of [80, 120, 200]) { assert.equal(alto - h({largo: 150, ancho: 100, alto}, {modo: 1}).h, 30); }
    assert.equal(h({largo: 150, ancho: 100, alto: 100}, {porcentaje: 10, minimo: 25}).h, 25);
    assert.match(h({largo: 150, ancho: 100, alto: 20}, {minimo: 30, solape: 5}).error, /por encima de la tapa/);
    assert.match(h({largo: 150, ancho: 100, alto: 15}, {solape: 20}).error, /necesita tocar/);
    assert.match(h({largo: 150, ancho: 100, alto: 120}, {apertura: 90}).error, /abre 90 mm/);
    assert.equal(h({largo: 300, ancho: 80, alto: 120}, {apertura: 90}).h, 60);   // el lado que cierra es el ancho
});

test('el reparto de la mesa usa los ajustes de puesta en marcha: altura de agarre, punto de espera, TCP y suelo', () => {
    const caja = {largo: 200, ancho: 200, alto: 200};
    const d = {x: -60, y: 482, zMesa: 320, xEntrada: 220, altoLibre: 200};
    const defecto = L.puntosDestino(caja, d, {});
    assert.deepEqual(defecto.map((p) => p.z), [485, 485, 420, 585]);
    // desde la tapa con 30 mm: h = 170 -> el TCP baja a 320 + 170 y el viaje sube lo mismo
    const tapa = L.puntosDestino(caja, d, {agarre: {modo: 1, porcentaje: 50, hundimiento: 30, minimo: 10, solape: 10, apertura: 0}});
    assert.deepEqual(tapa.map((p) => p.z), [555, 555, 490, 585]);
    // un margen mayor sube el viaje y la salida
    assert.deepEqual(L.puntosDestino(caja, d, {margen: 100}).map((p) => p.z), [520, 520, 420, 620]);
    // el punto de espera y el largo de la pinza cambian lo que el robot alcanza
    const lim = {egmMaxPos: 1500, alcanceMax: 790};
    const p = {x: -300, y: 400, z: 420};
    assert.equal(L.puntoPermitido(p, lim), true);
    assert.equal(L.puntoPermitido(p, Object.assign({inicio: [-900, 400, 543]}, lim)), true);
    assert.equal(L.puntoPermitido(p, {inicio: [600, -6.5, 543], egmMaxPos: 900, alcanceMax: 790}), false);   // a 995 mm de su punto de espera, con limite 900
    assert.equal(L.puntoPermitido({x: 0, y: 300, z: 600}, Object.assign({tcp: 147}, lim)), true);   // brida 747
    assert.equal(L.puntoPermitido({x: 0, y: 300, z: 600}, Object.assign({tcp: 250}, lim)), false);  // brida 850 > 800
    // suelo del TCP: por debajo de zMinima o de las superficies, no
    assert.equal(L.puntoPermitido({x: 0, y: 300, z: 300}, Object.assign({zMesa: 320, zCinta: 220}, lim)), true);
    assert.equal(L.puntoPermitido({x: 0, y: 300, z: 200}, Object.assign({zMesa: 320, zCinta: 220}, lim)), false);
    assert.equal(L.puntoPermitido({x: 0, y: 300, z: 400}, Object.assign({zMesa: 320, zCinta: 220, zMinima: 450}, lim)), false);
});

test('si la caja de referencia no se puede agarrar con los ajustes de agarre, la vista avisa', () => {
    const v = L.calcularVista(estado({aperturaPinza: 150}));   // la caja de referencia mide 200 de ancho
    assert.ok(v.avisos.some((a) => a.nivel === 'aviso' && /no se puede agarrar.*abre 150 mm/.test(a.texto)));
    assert.equal(L.calcularVista(estado({})).avisos.some((a) => /no se puede agarrar/.test(a.texto)), false);
});

test('la tarjeta Pinza usa el tiempo maximo de la app para decir SIN CONFIRMACION', () => {
    const e = estado({tMaxPinza: 6, senales: {sensor: false, cinta: false, pinzaCerrar: true, pinzaCerrada: false}});
    e.pinza.cambio = 10000;
    assert.equal(L.vistaPinza(e, 14000).titulo, 'CERRANDO…');           // 4 s < 6 s
    assert.equal(L.vistaPinza(e, 16100).titulo, 'SIN CONFIRMACIÓN');
    assert.match(L.vistaPinza(e, 16100).detalle, /RAPID espera 6 s/);
});
