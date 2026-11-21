/*
 * App CajaPinza para el FlexPendant del GoFa (OmniCore App SDK 1.6.0).
 *
 * Habla con MOD_CajaPinza (T_ROB1) por RWS: lee sus PERS hmi* y las de la tanda, y escribe INICIAR,
 * CAJA EN POSICION y los ajustes. Toda la logica (que boton vale, que texto, que giro) esta en
 * logica.js; aqui solo se pinta y se escribe. Con ?demo en la direccion usa un RWS simulado
 * (demo-rws.js) para ver la pantalla sin controlador.
 */
(function () {
    'use strict';

    const L = window.Logica;
    const REFRESCO_MS = 2000;            // lectura de seguridad por si falla alguna suscripcion
    const RETARDO_ESCRITURA_MS = 300;    // junta los toques seguidos en +/- en una sola escritura
    const BLOQUEO_MAX_MS = 8000;         // tras una orden, el boton no vuelve a valer hasta que RAPID cambie de fase

    let rws = null;
    let simulador = null;
    const estado = L.estadoInicial();
    const datos = {};                    // nombre de PERS -> Data de RWS
    const senales = {};                  // clave -> Signal de RWS
    const ui = {};                       // componentes FPComponents
    const ultimo = {};                   // firma de lo ultimo pintado en cada lista
    const enVuelo = {};                  // PERS que se estan escribiendo ahora
    const bloqueo = {iniciar: null, caja: null};   // fase en la que se envio cada orden
    let escrituras = {};                 // ajustes pendientes de escribir (ultimo valor de cada uno)
    let temporizador = null;
    let cola = Promise.resolve();
    let pintarPedido = false;
    let refrescando = false;

    // ---------------------------------------------------------------- utilidades
    function $(id) { return document.getElementById(id); }

    function poner(id, texto) {
        const el = $(id);
        if (el && el.textContent !== texto) { el.textContent = texto; }
    }

    function clase(id, nombre, activa) {
        const el = $(id);
        if (el) { el.classList.toggle(nombre, !!activa); }
    }

    function reconstruir(id, firma, construir) {
        if (ultimo[id] === firma) { return false; }
        ultimo[id] = firma;
        const cont = $(id);
        cont.textContent = '';
        construir(cont);
        return true;
    }

    function textoError(err) {
        if (typeof err === 'string') { return err; }
        if (err && err.message) { return String(err.message); }
        try { return JSON.stringify(err); } catch (e) { return String(err); }
    }

    function avisarError(titulo, err) {
        const t = textoError(err);
        const lineas = [titulo + '.', t];
        if (/mastership/i.test(t)) {
            lineas.push('Otro cliente tiene el acceso de escritura a RAPID (RobotStudio con Request Write Access, por ejemplo). Suéltalo y vuelve a probar.');
        }
        const P = FPComponents.Popup_A;
        P.message('Error', lineas, null, P.STYLE ? P.STYLE.DANGER : null);
    }

    // ---------------------------------------------------------------- escritura en RAPID
    // Las escrituras van de una en una: cada setValue pide y suelta la mastership de RAPID.
    function enCola(tarea) {
        const siguiente = cola.then(tarea);
        cola = siguiente.catch(function () { /* la cola sigue aunque una tarea falle */ });
        return siguiente;
    }

    function escribir(nombre, valor) {
        enVuelo[nombre] = (enVuelo[nombre] || 0) + 1;   // mientras tanto, una lectura no pisa el valor nuevo
        const terminar = function () {
            enVuelo[nombre] -= 1;
            if (enVuelo[nombre] <= 0) { delete enVuelo[nombre]; }
        };
        return enCola(function () {
            const d = datos[nombre];
            if (!d) { return Promise.reject(new Error('No encuentro ' + nombre + ' en RAPID.')); }
            return d.setValue(valor);
        }).then(terminar, function (err) {
            terminar();
            throw err;
        });
    }

    // Ajuste de la tanda: se ve al instante y se escribe 300 ms despues del ultimo toque.
    function ajustar(nombre, valor) {
        estado[L.VARIABLES[nombre].clave] = valor;
        escrituras[nombre] = valor;
        pedirPintar();
        clearTimeout(temporizador);
        temporizador = setTimeout(volcarEscrituras, RETARDO_ESCRITURA_MS);
    }

    function volcarEscrituras() {
        clearTimeout(temporizador);
        temporizador = null;
        const lote = escrituras;
        escrituras = {};
        Object.keys(lote).forEach(function (nombre) {
            escribir(nombre, lote[nombre]).then(refrescar, function (err) {
                avisarError('No he podido guardar ' + nombre + ' en RAPID', err);
                refrescar();
            });
        });
    }

    // Orden (INICIAR, CAJA EN POSICION): un TRUE que RAPID devuelve a FALSE al usarlo.
    function orden(nombre, clave) {
        volcarEscrituras();   // los ajustes pendientes llegan antes que la orden
        bloqueo[clave] = estado.fase;
        setTimeout(function () { bloqueo[clave] = null; pedirPintar(); }, BLOQUEO_MAX_MS);
        pedirPintar();
        return escribir(nombre, true).catch(function (err) {
            bloqueo[clave] = null;
            pedirPintar();
            avisarError('No he podido enviar la orden a RAPID', err);
        });
    }

    // ---------------------------------------------------------------- lectura de RAPID
    function recibir(nombre, bruto) {
        if (Object.prototype.hasOwnProperty.call(escrituras, nombre) || enVuelo[nombre]) { return; }
        L.aplicarVariable(estado, nombre, bruto);
        estado.rws = true;
        pedirPintar();
    }

    async function abrirVariable(nombre) {
        const def = L.VARIABLES[nombre];
        const d = await rws.Rapid.getData(L.TAREA, L.MODULO, nombre);
        await d.fetch();   // si el simbolo no existe en RAPID, falla aqui
        if (def.lee !== false) {
            L.aplicarVariable(estado, nombre, await d.getRawValue());
            d.addCallbackOnChanged(function (bruto) { recibir(nombre, bruto); });
            await d.subscribe(false);
        }
        datos[nombre] = d;
        return def.lee !== false;
    }

    async function abrirSenal(clave, nombre) {
        const s = await rws.IO.getSignal(nombre);
        L.ponerSenal(estado, clave, L.aNum(await s.getValue(), 0) !== 0, Date.now());
        s.addCallbackOnChanged(function (valor) {
            L.ponerSenal(estado, clave, L.aNum(valor, 0) !== 0, Date.now());
            pedirPintar();
        });
        await s.subscribe(false);
        senales[clave] = s;
    }

    async function abrirEjecucion() {
        try {
            estado.ejecucion = L.normalizarEjecucion(await rws.Rapid.getExecutionState());
        } catch (err) { console.warn('CajaPinza: no leo el estado de ejecucion', err); }
        try {
            const monitor = rws.Rapid.getMonitor(rws.Rapid.MonitorResources.execution);
            monitor.addCallbackOnChanged(function (valor) {
                estado.ejecucion = L.normalizarEjecucion(valor);
                pedirPintar();
            });
            await monitor.subscribe(false);
        } catch (err) { console.warn('CajaPinza: no puedo suscribirme a la ejecucion', err); }
    }

    async function conectar() {
        const faltan = [];
        let leidas = 0;
        const nombres = Object.keys(L.VARIABLES);
        for (let i = 0; i < nombres.length; i++) {
            try {
                if (await abrirVariable(nombres[i])) { leidas++; }
            } catch (err) {
                faltan.push(nombres[i]);
                console.warn('CajaPinza: no puedo abrir ' + nombres[i], err);
            }
        }
        estado.faltan = faltan;
        estado.rws = leidas > 0;
        pedirPintar();

        const claves = Object.keys(L.SENALES);
        for (let i = 0; i < claves.length; i++) {
            try { await abrirSenal(claves[i], L.SENALES[claves[i]]); } catch (err) {
                console.warn('CajaPinza: no puedo leer la senal ' + L.SENALES[claves[i]], err);
            }
        }
        await abrirEjecucion();
        pintar();
        document.body.setAttribute('data-rws', estado.rws ? 'listo' : 'sin-conexion');   // las pruebas esperan a esto
        setInterval(refrescar, REFRESCO_MS);
    }

    // Lectura completa cada REFRESCO_MS: red de seguridad por si una suscripcion no avisa.
    async function refrescar() {
        if (refrescando) { return; }
        refrescando = true;
        try {
            let alguna = false;
            const nombres = Object.keys(datos);
            for (let i = 0; i < nombres.length; i++) {
                const nombre = nombres[i];
                if (L.VARIABLES[nombre].lee === false) { continue; }
                try {
                    await datos[nombre].fetch();
                    alguna = true;
                    recibir(nombre, await datos[nombre].getRawValue());
                } catch (err) { /* se cuenta como fallo de lectura */ }
            }
            const claves = Object.keys(senales);
            for (let i = 0; i < claves.length; i++) {
                try { L.ponerSenal(estado, claves[i], L.aNum(await senales[claves[i]].getValue(), 0) !== 0, Date.now()); } catch (err) { /* sin dato */ }
            }
            try { estado.ejecucion = L.normalizarEjecucion(await rws.Rapid.getExecutionState()); } catch (err) { /* sin dato */ }
            if (nombres.length > 0) { estado.rws = alguna; }
            pedirPintar();
        } finally {
            refrescando = false;
        }
    }

    // ---------------------------------------------------------------- pantalla
    function pedirPintar() {
        if (pintarPedido) { return; }
        pintarPedido = true;
        setTimeout(function () {
            pintarPedido = false;
            pintar();
        }, 0);
    }

    function pintar() {
        // una orden deja de bloquear su boton en cuanto RAPID cambia de fase
        ['iniciar', 'caja'].forEach(function (k) { if (bloqueo[k] !== null && bloqueo[k] !== estado.fase) { bloqueo[k] = null; } });
        const v = L.calcularVista(estado);
        pintarCabecera(v);
        pintarMomento(v);
        pintarAjustes(v);
        pintarCaja(v);
        pintarMesa(v);
        pintarParametros(v);
        pintarAvisos(v);
    }

    function pintarCabecera(v) {
        reconstruir('chips', v.chips.map(function (c) { return c.id + c.valor + c.tono; }).join('|'), function (cont) {
            v.chips.forEach(function (c) {
                const s = document.createElement('span');
                s.className = 'chip tono-' + c.tono;
                const b = document.createElement('b');
                b.textContent = c.texto;
                s.appendChild(b);
                s.appendChild(document.createTextNode(c.valor));
                cont.appendChild(s);
            });
        });
    }

    function pintarMomento(v) {
        $('banner').className = 'banner tono-' + v.banner.tono;
        poner('banner-titulo', v.banner.titulo);
        poner('banner-detalle', v.banner.detalle);
        $('progreso-barra').style.width = Math.round(v.progreso * 100) + '%';
        const pinza = v.pinza;
        $('pinza').className = 'pinza tono-' + pinza.tono;
        poner('pinza-titulo', pinza.titulo);
        poner('pinza-detalle', pinza.detalle);
        poner('pinza-resumen', pinza.resumen);
        $('pinza-led-orden').className = 'led' + (pinza.orden === true ? ' on' : (pinza.orden === false ? ' off' : ''));
        $('pinza-led-conf').className = 'led' + (pinza.confirmacion === true ? ' on' : (pinza.confirmacion === false ? ' off' : ''));
        poner('caja-texto', v.caja.texto);
        reconstruir('pasos', v.pasos.map(function (p) { return p.id + p.estado; }).join('|'), function (cont) {
            v.pasos.forEach(function (p) {
                const li = document.createElement('li');
                li.className = p.estado;
                li.textContent = p.texto;
                cont.appendChild(li);
            });
        });

        const iniciar = v.botones.iniciar.habilitado && bloqueo.iniciar === null;
        const caja = v.botones.cajaEnPosicion.habilitado && bloqueo.caja === null;
        if (ui.abortar) { ui.abortar.enabled = v.botones.abortar.habilitado && !abortando; }
        if (ui.mensajes) { ui.mensajes.active = estado.mensajes; }
        if (ui.iniciar) { ui.iniciar.enabled = iniciar; ui.iniciar.highlight = iniciar; }
        if (ui.caja) { ui.caja.enabled = caja; ui.caja.highlight = caja; }
        poner('motivo-iniciar', v.botones.iniciar.habilitado ? '' : v.botones.iniciar.motivo);
        poner('motivo-caja', v.botones.cajaEnPosicion.habilitado ? '' : v.botones.cajaEnPosicion.motivo);
    }

    function pintarAjustes(v) {
        const a = v.ajustes;
        poner('c-valor', String(a.nCajas.valor));
        $('c-menos10').disabled = !a.editable || a.nCajas.valor <= 1;
        $('c-menos').disabled = !a.nCajas.menosHabil;
        $('c-mas').disabled = !a.nCajas.masHabil;
        $('c-mas10').disabled = !a.editable || a.nCajas.valor >= a.nCajas.max;

        clase('modo-sim', 'activo', a.modo === 'sim');
        clase('modo-real', 'activo', a.modo === 'real');
        clase('modo-real', 'real', true);
        $('modo-sim').disabled = !a.editable;
        $('modo-real').disabled = !a.editable;

        const sim = a.modo === 'sim';
        $('fila-giro').hidden = !sim;   // en real el giro lo da la camara
        clase('giro-azar', 'activo', a.giro.modo === 'azar');
        clase('giro-fijo', 'activo', a.giro.modo === 'fijo');
        $('giro-azar').disabled = !a.giro.editable;
        $('giro-fijo').disabled = !a.giro.editable;
        $('giro-opciones').hidden = !(sim && a.giro.modo === 'fijo');
        $('fila-semilla').hidden = !(sim && a.giro.modo === 'azar');
        poner('semilla', '(' + a.giro.semilla + ')');
        $('nueva-semilla').disabled = !a.giro.editable;
        a.giro.opciones.forEach(function (o) {
            const b = $('giro-' + o.indice);
            if (b) {
                b.classList.toggle('activo', a.giro.indice === o.indice);
                b.disabled = !a.giro.editable;
            }
        });
        poner('nota-giro', a.giro.nota);
        poner('nota-capacidad', a.nCajas.nota);
        clase('nota-capacidad', 'mala', a.nCajas.sobra);

        if (ui.confirmar) {
            ui.confirmar.active = a.confirmar.valor;
            ui.confirmar.enabled = a.confirmar.editable;
        }
        poner('nota-confirmar', a.confirmar.nota);
        poner('nota-ajustes', a.editable ? '' : a.motivo);
    }

    function pintarCaja(v) {
        const o = v.orientacion;
        poner('orient-texto', o.texto);
        poner('orient-etiqueta', o.etiqueta);
        poner('orient-medidas', o.medidas ? 'Medidas: ' + o.medidas : '');
        poner('g-rapid', o.textoRapid);
        poner('g-pc', o.textoPc);
        const sello = $('g-ok');
        sello.textContent = o.coincide === true ? '✓ coincide' : (o.coincide === false ? '✗ distinto' : '');
        sello.className = 'sello' + (o.coincide === true ? ' ok' : (o.coincide === false ? ' mal' : ''));

        const grupo = $('svg-caja-grupo');
        if (o.puntos === null) {
            grupo.setAttribute('visibility', 'hidden');
            $('svg-vacio').setAttribute('visibility', 'visible');
        } else {
            grupo.setAttribute('visibility', 'visible');
            $('svg-vacio').setAttribute('visibility', 'hidden');
            $('svg-poligono').setAttribute('points', o.puntos.map(function (p) { return p[0] + ',' + p[1]; }).join(' '));
            const a = o.giro * Math.PI / 180;
            $('svg-eje-x').setAttribute('x2', String(Math.round((120 + Math.cos(a) * 72) * 100) / 100));
            $('svg-eje-x').setAttribute('y2', String(Math.round((120 - Math.sin(a) * 72) * 100) / 100));
        }

        const firmaGiros = v.giros.map(function (g) { return g.n + g.texto + g.estado; }).join('|') || 'real';
        if (reconstruir('lista-giros', firmaGiros, function (cont) {
            if (v.giros.length === 0) {
                const li = document.createElement('li');
                li.className = 'vacio';
                li.textContent = 'En real el giro lo da la cámara.';
                cont.appendChild(li);
            }
            v.giros.forEach(function (g) {
                const li = document.createElement('li');
                li.className = g.estado;
                const n = document.createElement('b');
                n.textContent = String(g.n);
                li.appendChild(n);
                li.appendChild(document.createTextNode(g.texto));
                cont.appendChild(li);
            });
        })) {
            const actual = $('lista-giros').querySelector('li.actual');
            if (actual) { $('lista-giros').scrollTop = Math.max(0, actual.offsetTop - 40); }
        }

        reconstruir('senales', v.senales.map(function (s) { return s.id + s.valor; }).join('|'), function (cont) {
            v.senales.forEach(function (s) {
                const li = document.createElement('li');
                const led = document.createElement('span');
                led.className = 'led' + (s.valor === true ? ' on' : (s.valor === false ? ' off' : ''));
                li.appendChild(led);
                li.appendChild(document.createTextNode(s.texto));
                cont.appendChild(li);
            });
        });
    }

    const SVG = 'http://www.w3.org/2000/svg';

    function elementoSvg(nombre, atributos, texto) {
        const el = document.createElementNS(SVG, nombre);
        Object.keys(atributos).forEach(function (k) { el.setAttribute(k, String(atributos[k])); });
        if (texto !== undefined) { el.textContent = texto; }
        return el;
    }

    // La mesa vista desde arriba: la zona, la base del robot, el lado por el que entran las cajas y los huecos.
    function dibujarMesa(m) {
        const g = m.geometria;
        const firma = JSON.stringify(g) + JSON.stringify(m.zona) + m.huecos.map(function (h) { return h.estado + h.n; }).join(',');
        reconstruir('svg-mesa', firma, function (svg) {
            svg.setAttribute('viewBox', '0 0 ' + g.ancho + ' ' + g.alto);
            svg.appendChild(elementoSvg('rect', {x: g.zona.x, y: g.zona.y, width: g.zona.w, height: g.zona.h, 'class': 'mesa-zona'}));
            g.inalcanzable.forEach(function (t) {   // lo que el robot no alcanza con la caja de referencia
                svg.appendChild(elementoSvg('rect', {x: t.x, y: t.y, width: t.w, height: t.h, 'class': 'mesa-rojo'}));
            });
            m.huecos.forEach(function (h, i) {
                const caja = g.huecos[i];
                svg.appendChild(elementoSvg('rect', {x: caja.x, y: caja.y, width: caja.w, height: caja.h, rx: 2, 'class': 'hueco hueco-' + h.estado}));
                svg.appendChild(elementoSvg('text', {x: caja.cx, y: caja.cy + 4, 'class': 'hueco-numero'}, String(h.n)));
            });
            // cotas de la zona: largo (x) y ancho (y)
            svg.appendChild(elementoSvg('text', {x: g.zona.x + g.zona.w / 2, y: g.zona.y - 4, 'class': 'mesa-texto', 'text-anchor': 'middle'},
                'largo ' + m.zona.largo + ' mm (x)'));
            svg.appendChild(elementoSvg('text', {x: g.zona.x - 4, y: g.zona.y + g.zona.h / 2, 'class': 'mesa-texto', 'text-anchor': 'middle',
                transform: 'rotate(-90 ' + (g.zona.x - 4) + ' ' + (g.zona.y + g.zona.h / 2) + ')'}, 'ancho ' + m.zona.ancho + ' mm (y)'));
            svg.appendChild(elementoSvg('circle', {cx: g.zona.x, cy: g.zona.y + g.zona.h, r: 4, 'class': 'mesa-base'}));
            svg.appendChild(elementoSvg('text', {x: g.zona.x + 7, y: g.zona.y + g.zona.h - 6, 'class': 'mesa-texto'},
                'esquina (' + m.zona.x0 + ', ' + m.zona.y0 + ')'));
            // entrada: las cajas llegan por el lado +x de la zona y se deslizan hacia -x
            const xe = g.zona.x + g.zona.w;
            svg.appendChild(elementoSvg('path', {d: 'M' + (xe + 70) + ' ' + (g.zona.y + 14) + ' L' + (xe + 6) + ' ' + (g.zona.y + 14)
                + ' M' + (xe + 14) + ' ' + (g.zona.y + 8) + ' L' + (xe + 6) + ' ' + (g.zona.y + 14) + ' L' + (xe + 14) + ' ' + (g.zona.y + 20),
                'class': 'mesa-entrada'}));
            svg.appendChild(elementoSvg('text', {x: xe + 72, y: g.zona.y + 18, 'class': 'mesa-texto'}, 'entrada'));
            // base del robot y ejes
            svg.appendChild(elementoSvg('circle', {cx: g.base.x, cy: g.base.y, r: 7, 'class': 'mesa-base'}));
            svg.appendChild(elementoSvg('text', {x: g.base.x + 11, y: g.base.y + 4, 'class': 'mesa-texto'}, 'base del robot'));
            svg.appendChild(elementoSvg('path', {d: 'M14 ' + (g.alto - 14) + ' L64 ' + (g.alto - 14) + ' M58 ' + (g.alto - 19) + ' L64 ' + (g.alto - 14)
                + ' L58 ' + (g.alto - 9) + ' M14 ' + (g.alto - 14) + ' L14 ' + (g.alto - 64) + ' M9 ' + (g.alto - 58) + ' L14 ' + (g.alto - 64)
                + ' L19 ' + (g.alto - 58), 'class': 'mesa-eje'}));
            svg.appendChild(elementoSvg('text', {x: 68, y: g.alto - 10, 'class': 'mesa-texto'}, 'x'));
            svg.appendChild(elementoSvg('text', {x: 20, y: g.alto - 66, 'class': 'mesa-texto'}, 'y'));
        });
    }

    function pintarMesa(v) {
        const m = v.mesa;
        m.campos.forEach(function (c) {
            const campo = ui.campos && ui.campos[c.clave];
            if (campo) {
                if (campo.text !== String(c.valor)) { campo.text = String(c.valor); }
                campo.enabled = m.editable;
            }
        });
        if (ui.variables) {
            ui.variables.active = m.cajasVariables;
            ui.variables.enabled = m.editable && estado.modoSimulacion;
        }
        poner('mesa-resumen', m.resumen);
        poner('mesa-limites', m.limites);
        poner('nota-mesa', m.editable ? '' : 'Bloqueado mientras la tanda está en marcha.');
        $('mesa-sim').disabled = !m.editable;
        dibujarMesa(m);
    }

    // ---------------------------------------------------------------- ventana Parametros
    function mostrarSeccion(id) {
        L.PARAMETROS.forEach(function (s) {
            $('psec-' + s.id).hidden = s.id !== id;
            clase('pnav-' + s.id, 'activa', s.id === id);
        });
    }

    // Construye las secciones, los campos y los botones de modo a partir de L.PARAMETROS (los campos numericos los crea
    // crearCampo despues, sobre los div in-<clave>).
    function crearParametros() {
        const nav = $('param-nav');
        const contenido = $('param-contenido');
        L.PARAMETROS.forEach(function (sec, indice) {
            const boton = document.createElement('button');
            boton.type = 'button';
            boton.id = 'pnav-' + sec.id;
            boton.className = 'pestana-param' + (indice === 0 ? ' activa' : '');
            boton.textContent = sec.titulo;
            boton.addEventListener('click', function () { mostrarSeccion(sec.id); });
            nav.appendChild(boton);

            const tarjeta = document.createElement('section');
            tarjeta.className = 'tarjeta param-seccion';
            tarjeta.id = 'psec-' + sec.id;
            tarjeta.hidden = indice !== 0;
            const titulo = document.createElement('h2');
            titulo.textContent = sec.titulo;
            tarjeta.appendChild(titulo);
            const ayuda = document.createElement('p');
            ayuda.className = 'ayuda';
            ayuda.textContent = sec.ayuda;
            tarjeta.appendChild(ayuda);
            const rejilla = document.createElement('div');
            rejilla.className = 'param-campos';
            sec.items.forEach(function (it) {
                const caja = document.createElement('div');
                caja.className = 'param-item';
                caja.id = 'pitem-' + it.clave;
                const tipo = it.tipo || 'num';
                if (tipo === 'num') {
                    const campo = document.createElement('div');
                    campo.id = 'in-' + it.clave;
                    campo.className = 'campo-mesa';
                    caja.appendChild(campo);
                } else {
                    const nombre = document.createElement('div');
                    nombre.className = 'param-nombre';
                    nombre.textContent = it.nombre;
                    caja.appendChild(nombre);
                    if (tipo === 'modo') {
                        const grupo = document.createElement('div');
                        grupo.className = 'segmentos';
                        it.opciones.forEach(function (op) {
                            const b = document.createElement('button');
                            b.type = 'button';
                            b.id = 'par-' + it.clave + '-' + op.valor;
                            b.className = 'segmento';
                            b.textContent = op.texto;
                            b.addEventListener('click', function () {
                                if (parametroActivo(it.clave)) { ajustar(it.clave, op.valor); }
                            });
                            grupo.appendChild(b);
                        });
                        caja.appendChild(grupo);
                    } else {
                        const lectura = document.createElement('div');
                        lectura.id = 'plect-' + it.clave;
                        lectura.className = 'param-lectura';
                        caja.appendChild(lectura);
                    }
                }
                const ayudaItem = document.createElement('div');
                ayudaItem.className = 'param-ayuda';
                ayudaItem.textContent = it.ayuda + (it.protegido ? ' Pide confirmación al cambiarlo.' : '');
                caja.appendChild(ayudaItem);
                const nota = document.createElement('div');
                nota.className = 'param-nota';
                nota.id = 'pnota-' + it.clave;
                caja.appendChild(nota);
                rejilla.appendChild(caja);
            });
            tarjeta.appendChild(rejilla);
            contenido.appendChild(tarjeta);
        });
    }

    // Se puede cambiar ahora (antes de INICIAR o al terminar; y solo si vale en este modo).
    function parametroActivo(clave) {
        const secciones = L.calcularVista(estado).parametros.secciones;
        for (let i = 0; i < secciones.length; i++) {
            for (let k = 0; k < secciones[i].items.length; k++) {
                if (secciones[i].items[k].clave === clave) { return secciones[i].items[k].activo; }
            }
        }
        return false;
    }

    function pintarParametros(v) {
        $('par-cargar').disabled = !v.parametros.editable;
        $('par-defecto').disabled = !v.parametros.editable;
        v.parametros.secciones.forEach(function (s) {
            s.items.forEach(function (it) {
                clase('pitem-' + it.clave, 'inactivo', it.tipo !== 'lectura' && !it.activo);
                poner('pnota-' + it.clave, it.nota || (v.parametros.editable ? '' : 'Bloqueado mientras la tanda está en marcha.'));
                if (it.tipo === 'num') {
                    const campo = ui.campos && ui.campos[it.clave];
                    if (campo) {
                        if (campo.text !== String(it.valor)) { campo.text = String(it.valor); }
                        campo.enabled = it.activo;
                    }
                } else if (it.tipo === 'modo') {
                    it.opciones.forEach(function (op) {
                        clase('par-' + it.clave + '-' + op.valor, 'activo', it.valor === op.valor);
                        $('par-' + it.clave + '-' + op.valor).disabled = !it.activo;
                    });
                } else {
                    poner('plect-' + it.clave, it.valor + ' ' + it.unidad);
                }
            });
        });
    }

    // ---------------------------------------------------------------- valores por defecto y fichero CSV de ajustes
    // Los ficheros viven en $HOME/parametros del controlador (RWS.FileSystem). Al cargar o reponer valores se pasa por
    // ajustar(): se escriben en las PERS como cualquier cambio a mano.
    const DIR_AJUSTES = '$HOME/parametros';

    function estadoAjustes(texto, nivel) {
        const el = $('par-estado');
        el.textContent = texto;
        el.className = 'param-estado' + (nivel ? ' ' + nivel : '');
    }

    async function listarAjustes() {
        try {
            const dir = await rws.FileSystem.getDirectory(DIR_AJUSTES);
            const contenido = await dir.getContents();
            return contenido.files.map(function (f) { return f.name; }).filter(function (n) { return /\.csv$/i.test(n); }).sort();
        } catch (err) {
            return [];   // la carpeta no existe todavia (se crea al guardar el primero)
        }
    }

    async function refrescarFicheros() {
        const nombres = await listarAjustes();
        try {
            const cont = $('par-ficheros');
            while (cont.firstChild) { cont.removeChild(cont.firstChild); }
            if (nombres.length === 0) {
                const vacio = document.createElement('span');
                vacio.className = 'vacio';
                vacio.textContent = 'Aún no hay ningún fichero guardado.';
                cont.appendChild(vacio);
                return;
            }
            nombres.forEach(function (n) {
                const b = document.createElement('button');
                b.type = 'button';
                b.textContent = n;
                b.addEventListener('click', function () { ui.nombreFichero.text = n.replace(/\.csv$/i, ''); });
                cont.appendChild(b);
            });
        } catch (err) { /* la pantalla ya no esta */ }
    }

    function resumenIgnorados(ignorados) {
        const lista = ignorados.slice(0, 3).map(function (i) { return 'línea ' + i.linea + ' (' + i.texto + '): ' + i.motivo; });
        return lista.join('; ') + (ignorados.length > 3 ? '; …' : '');
    }

    function textoCambios(cambios) {
        const lista = cambios.slice(0, 6).map(function (c) { return c.nombre + ': ' + c.antes + ' → ' + c.ahora + (c.unidad ? ' ' + c.unidad : ''); });
        return lista.join('; ') + (cambios.length > 6 ? '; …' : '');
    }

    function confirmarYAplicar(titulo, lineas, cambios, mensajeFinal) {
        const P = FPComponents.Popup_A;
        P.confirm(titulo, lineas, function (accion) {
            if (accion !== P.OK) { return; }
            if (!ajustesEditables()) { estadoAjustes('La tanda ha empezado: no se ha cambiado nada.', 'error'); return; }
            cambios.forEach(function (c) { ajustar(c.clave, c.ahora); });
            estadoAjustes(mensajeFinal, 'ok');
        }, P.STYLE ? P.STYLE.WARNING : null);
    }

    function ponerValoresPorDefecto() {
        if (!ajustesEditables()) { return; }
        const r = L.cambiosHacia(estado, L.valoresPorDefecto());
        if (r.cambios.length === 0) { estadoAjustes('Todos los ajustes ya tienen su valor por defecto.', 'ok'); return; }
        const protegidos = r.cambios.filter(function (c) { return c.protegido; });
        const lineas = ['Se pondrán los valores por defecto del módulo en ' + r.cambios.length + ' ajustes (los que has modificado), incluidos la zona de la mesa y la caja de referencia.'];
        if (protegidos.length > 0) { lineas.push('Incluye ajustes protegidos: ' + protegidos.map(function (c) { return c.nombre; }).join(', ') + '.'); }
        lineas.push('Si quieres conservar los valores actuales, guárdalos antes en un fichero. ¿Continuar?');
        confirmarYAplicar('Valores por defecto', lineas, r.cambios, 'Valores por defecto puestos en ' + r.cambios.length + ' ajustes.');
    }

    async function guardarAjustes() {
        const n = L.nombreFicheroValido(ui.nombreFichero.text);
        if (!n.ok) { estadoAjustes(n.motivo, 'error'); return; }
        const ruta = DIR_AJUSTES + '/' + n.nombre + '.csv';
        try {
            try { await rws.FileSystem.getDirectory(DIR_AJUSTES); } catch (err) { await rws.FileSystem.createDirectory(DIR_AJUSTES); }
            const fichero = rws.FileSystem.createFileObject(ruta);
            const existe = await fichero.fileExists();
            const escribir = async function () {
                try {
                    fichero.setContents(L.aCsv(estado));
                    await fichero.save(true);
                    estadoAjustes('Guardado en ' + ruta + ' (' + L.AJUSTES.length + ' ajustes).', 'ok');
                    refrescarFicheros();
                } catch (err) { estadoAjustes('No he podido guardar ' + ruta + ': ' + textoError(err), 'error'); }
            };
            if (!existe) { await escribir(); return; }
            const P = FPComponents.Popup_A;
            P.confirm('Sustituir el fichero', ['Ya existe ' + n.nombre + '.csv.', '¿Sustituirlo por los ajustes actuales?'], function (accion) {
                if (accion === P.OK) { escribir(); }
            }, P.STYLE ? P.STYLE.WARNING : null);
        } catch (err) { estadoAjustes('No he podido guardar ' + ruta + ': ' + textoError(err), 'error'); }
    }

    async function cargarAjustes() {
        if (!ajustesEditables()) { return; }
        const n = L.nombreFicheroValido(ui.nombreFichero.text);
        if (!n.ok) { estadoAjustes(n.motivo, 'error'); return; }
        const ruta = DIR_AJUSTES + '/' + n.nombre + '.csv';
        let texto;
        try {
            const fichero = await rws.FileSystem.getFile(ruta);
            texto = await fichero.getContents();
        } catch (err) { estadoAjustes('No encuentro ' + ruta + ': ' + textoError(err), 'error'); return; }
        const r = L.desdeCsv(texto, estado);
        const ignoradas = r.ignorados.length > 0 ? ' Ignoradas ' + r.ignorados.length + ' líneas: ' + resumenIgnorados(r.ignorados) + '.' : '';
        if (r.reconocidos === 0) { estadoAjustes(n.nombre + '.csv no tiene ningún ajuste que pueda cargar.' + ignoradas, 'error'); return; }
        if (r.cambios.length === 0) { estadoAjustes(n.nombre + '.csv: los ' + r.reconocidos + ' ajustes ya valen lo mismo.' + ignoradas, 'ok'); return; }
        const protegidos = r.cambios.filter(function (c) { return c.protegido; });
        const lineas = [n.nombre + '.csv: cambian ' + r.cambios.length + ' de ' + r.reconocidos + ' ajustes.', textoCambios(r.cambios)];
        if (protegidos.length > 0) { lineas.push('Incluye ajustes protegidos: ' + protegidos.map(function (c) { return c.nombre; }).join(', ') + '.'); }
        if (r.ignorados.length > 0) { lineas.push('Se ignoran ' + r.ignorados.length + ' líneas: ' + resumenIgnorados(r.ignorados) + '.'); }
        lineas.push('¿Aplicarlos?');
        confirmarYAplicar('Cargar ' + n.nombre + '.csv', lineas, r.cambios,
            'Cargados ' + r.cambios.length + ' ajustes de ' + ruta + '.' + ignoradas);
    }

    function pintarAvisos(v) {
        reconstruir('avisos', v.avisos.map(function (a) { return a.nivel + a.texto; }).join('|'), function (cont) {
            v.avisos.forEach(function (a) {
                const d = document.createElement('div');
                d.className = 'aviso aviso-' + a.nivel;
                d.textContent = a.texto;
                cont.appendChild(d);
            });
        });
    }

    // ---------------------------------------------------------------- acciones del usuario
    function alPulsarIniciar() {
        const v = L.calcularVista(estado);
        if (!v.botones.iniciar.habilitado || bloqueo.iniciar !== null) { return; }
        const lineas = [v.resumenTanda + '.'];
        if (v.botones.iniciar.avisoSinPc) { lineas.push('El PC no está conectado a RAPID: nadie dirigirá el robot por EGM.'); }
        lineas.push('¿Empezar la tanda?');
        const P = FPComponents.Popup_A;
        P.confirm('Iniciar tanda', lineas, function (accion) {
            if (accion === P.OK) { orden('hmiIniciar', 'iniciar'); }
        });
    }

    function alPulsarCaja() {
        const v = L.calcularVista(estado);
        if (!v.botones.cajaEnPosicion.habilitado || bloqueo.caja !== null) { return; }
        orden('hmiCajaEnPosicion', 'caja');
    }

    // ABORTAR: Stop + PP a Main desde la app. No es un paro de emergencia (ese es el del FlexPendant).
    let abortando = false;

    function esperarParado(intentos) {
        return rws.Rapid.getExecutionState().then(function (e) {
            if (L.normalizarEjecucion(e) === 'stopped' || intentos <= 0) { return null; }
            return new Promise(function (ok) { setTimeout(ok, 200); }).then(function () { return esperarParado(intentos - 1); });
        });
    }

    function abortar() {
        abortando = true;
        pedirPintar();
        return rws.Rapid.stopExecution({stopMode: 'stop'})
            .then(function () { return esperarParado(25); })
            .then(function () { return rws.Rapid.resetPP(); })
            .then(function () {
                // con el programa parado las PERS se pueden escribir: se deja todo como al arrancar
                estado.fase = L.FASES.PARADO;
                estado.ejecucion = 'stopped';
                estado.mensaje = 'Tanda abortada desde la app';
                return escribir('hmiIniciar', false)
                    .then(function () { return escribir('hmiCajaEnPosicion', false); })
                    .then(function () { return escribir('hmiFase', L.FASES.PARADO); })
                    .then(function () { return escribir('hmiMensaje', estado.mensaje); });
            })
            .catch(function (err) { avisarError('No he podido abortar la tanda', err); })
            .then(function () { abortando = false; pedirPintar(); return refrescar(); });
    }

    function alPulsarAbortar() {
        if (abortando || !L.calcularVista(estado).botones.abortar.habilitado) { return; }
        const P = FPComponents.Popup_A;
        P.confirm('Abortar la tanda', [
            'Se para el programa de RAPID y vuelve al principio (como Stop y PP a Main).',
            'El robot se detiene donde esté; si lleva una caja, la pinza sigue cerrada.',
            'Después: relanza el PC y pulsa Play. En una emergencia usa el paro de emergencia del FlexPendant, no esta pantalla.'
        ], function (accion) {
            if (accion === P.OK) { abortar(); }
        }, P.STYLE ? P.STYLE.DANGER : null);
    }

    function ajustesEditables() { return L.calcularVista(estado).ajustes.editable; }

    function cambiarCajas(delta) {
        if (!ajustesEditables()) { return; }
        ajustar('nCajas', L.limitarCajas(estado.nCajas + delta));
    }

    function fijarGiro(indice) {
        if (!ajustesEditables() || !estado.modoSimulacion) { return; }
        ajustar('indiceFijo', indice);
    }

    // Cambiar de modo pone los ajustes por defecto de ese modo (se pueden volver a cambiar). Pulsar el modo
    // que ya esta activo no toca nada.
    function cambiarModo(simulacion) {
        if (!ajustesEditables() || estado.modoSimulacion === simulacion) { return; }
        ajustar('modoSimulacion', simulacion);
        const porDefecto = L.ajustesDeModo(simulacion);
        Object.keys(porDefecto).forEach(function (nombre) { ajustar(nombre, porDefecto[nombre]); });
    }

    function mostrarPestana(nombre) {
        $('vista-tanda').hidden = nombre !== 'tanda';
        $('vista-mesa').hidden = nombre !== 'mesa';
        $('vista-parametros').hidden = nombre !== 'parametros';
        clase('tab-tanda', 'activa', nombre === 'tanda');
        clase('tab-mesa', 'activa', nombre === 'mesa');
        clase('tab-parametros', 'activa', nombre === 'parametros');
    }

    function crearInterfaz() {
        const P = FPComponents;
        ui.iniciar = new P.Button_A();
        ui.iniciar.text = '▶  INICIAR TANDA';
        ui.iniciar.onclick = alPulsarIniciar;
        ui.iniciar.attachToId('btn-iniciar');

        ui.caja = new P.Button_A();
        ui.caja.text = 'CAJA EN POSICIÓN';
        ui.caja.onclick = alPulsarCaja;
        ui.caja.attachToId('btn-caja');

        ui.confirmar = new P.Switch_A();
        ui.confirmar.desc = 'Esperar CAJA EN POSICIÓN en cada caja';
        ui.confirmar.onchange = function (activo) {
            ajustar('hmiConfirmar', activo);
        };
        ui.confirmar.attachToId('sw-confirmar');

        $('c-menos10').addEventListener('click', function () { cambiarCajas(-10); });
        $('c-menos').addEventListener('click', function () { cambiarCajas(-1); });
        $('c-mas').addEventListener('click', function () { cambiarCajas(1); });
        $('c-mas10').addEventListener('click', function () { cambiarCajas(10); });

        $('modo-sim').addEventListener('click', function () { cambiarModo(true); });
        $('modo-real').addEventListener('click', function () { cambiarModo(false); });

        $('giro-azar').addEventListener('click', function () { fijarGiro(0); });
        $('giro-fijo').addEventListener('click', function () {
            fijarGiro(estado.indiceFijo >= 1 && estado.indiceFijo <= L.N_GIROS ? estado.indiceFijo : 7);
        });
        $('nueva-semilla').addEventListener('click', function () {
            if (ajustesEditables() && estado.modoSimulacion) { ajustar('semillaGiros', L.nuevaSemilla()); }
        });

        const rejilla = $('giro-opciones');
        for (let k = 1; k <= L.N_GIROS; k++) {
            const b = document.createElement('button');
            b.type = 'button';
            b.id = 'giro-' + k;
            b.className = 'giro-opcion';
            b.textContent = L.textoGiro(L.giroDeIndice(k));
            b.addEventListener('click', (function (indice) { return function () { fijarGiro(indice); }; }(k)));
            rejilla.appendChild(b);
        }

        // campos numericos (teclado numerico de ABB): zona y caja de referencia de la pestana Mesa y los ajustes de la
        // pestana Parametros (los protegidos piden confirmacion)
        ui.campos = {};
        crearParametros();
        const crearCampo = function (c) {
            const campo = new P.Input_A();
            campo.desc = c.nombre;
            campo.label = c.nombre + ' (' + (c.unidad || 'mm') + ')';
            campo.variant = FP_COMPONENTS_KEYBOARD_NUM;
            campo.regex = /^-?\d{1,4}(\.\d)?$/;
            campo.validator = function (texto) {
                const v = parseFloat(texto);
                return Number.isFinite(v) && v >= c.min && v <= c.max;
            };
            campo.text = String(estado[c.clave]);
            campo.onchange = function (texto) {
                if (!ajustesEditables()) { pedirPintar(); return; }
                const valor = L.limitarCampoMesa(c.clave, texto);
                if (!c.protegido) { ajustar(c.clave, valor); return; }
                // un ajuste protegido (limite del EGM, velocidad, alturas...): se pide confirmacion
                const t = L.textoConfirmacion(c, valor, estado[c.clave]);
                P.Popup_A.confirm(t.titulo, t.lineas, function (accion) {
                    if (accion === P.Popup_A.OK) { ajustar(c.clave, valor); } else { pedirPintar(); }
                }, P.Popup_A.STYLE ? P.Popup_A.STYLE.WARNING : null);
            };
            campo.attachToId('in-' + c.clave);
            ui.campos[c.clave] = campo;
        };
        L.CAMPOS.forEach(crearCampo);
        L.CAMPOS_PARAMETROS.forEach(crearCampo);

        // nombre del fichero de ajustes (teclado de letras de ABB) y botones de la ventana Parametros
        ui.nombreFichero = new P.Input_A();
        ui.nombreFichero.desc = 'Nombre del fichero';
        ui.nombreFichero.label = 'Nombre del fichero (.csv)';
        ui.nombreFichero.variant = FP_COMPONENTS_KEYBOARD_ALPHA;
        ui.nombreFichero.regex = /^[A-Za-z0-9 _.-]{0,44}$/;
        ui.nombreFichero.validator = function (texto) { return L.nombreFicheroValido(texto).ok; };
        ui.nombreFichero.text = 'parametros';
        ui.nombreFichero.attachToId('in-nombreFichero');
        $('par-guardar').addEventListener('click', guardarAjustes);
        $('par-cargar').addEventListener('click', cargarAjustes);
        $('par-defecto').addEventListener('click', ponerValoresPorDefecto);
        ui.variables = new P.Switch_A();
        ui.variables.desc = 'Cajas de tamaños distintos (simulación)';
        ui.variables.onchange = function (activo) { if (ajustesEditables()) { ajustar('cajasVariables', activo); } else { pedirPintar(); } };
        ui.variables.attachToId('sw-variables');

        ui.mensajes = new P.Switch_A();
        ui.mensajes.desc = 'Mostrar mensajes de RAPID en el FlexPendant';
        ui.mensajes.onchange = function (activo) { ajustar('hmiMensajes', activo); };
        ui.mensajes.attachToId('sw-mensajes');

        ui.abortar = new P.Button_A();
        ui.abortar.text = '■  ABORTAR';
        ui.abortar.onclick = alPulsarAbortar;
        ui.abortar.attachToId('btn-abortar');

        $('mesa-sim').addEventListener('click', function () {
            if (!ajustesEditables()) { return; }
            Object.keys(L.MESA_SIM).forEach(function (clave) { ajustar(clave, L.MESA_SIM[clave]); });
        });

        $('tab-tanda').addEventListener('click', function () { mostrarPestana('tanda'); });
        $('tab-mesa').addEventListener('click', function () { mostrarPestana('mesa'); });
        $('tab-parametros').addEventListener('click', function () { mostrarPestana('parametros'); refrescarFicheros(); });

        if (window.RWS_SIMULADO) { window.CajaPinzaPrueba = {ui: ui, estado: estado}; }   // solo en las pruebas

        // caja sin girar: referencia fija en el dibujo
        $('svg-referencia').setAttribute('points', L.puntosCaja(0, 50, 120, 120).map(function (p) { return p[0] + ',' + p[1]; }).join(' '));
    }

    // ---------------------------------------------------------------- demo sin controlador
    function crearBarraDemo() {
        const barra = $('demo');
        barra.hidden = false;
        barra.textContent = 'DEMO sin controlador (RWS simulado): ';
        [['Play', function () { simulador.play(); }],
            ['Stop', function () { simulador.stop(); }],
            ['Forzar CajaEnRecogida', function () { simulador.forzarSenal('sensor', true); }]
        ].forEach(function (par) {
            const b = document.createElement('button');
            b.type = 'button';
            b.textContent = par[0];
            b.addEventListener('click', par[1]);
            barra.appendChild(b);
        });
    }

    function elegirRws() {
        if (window.RWS_SIMULADO) { return window.RWS_SIMULADO; }          // pruebas con jsdom
        if (/[?&]demo(=|&|$)/.test(window.location.search) && window.DemoRws) {
            simulador = window.DemoRws.crear(L, {escala: 1, ejecucion: 'stopped'});
            crearBarraDemo();
            simulador.play();
            return simulador.RWS;
        }
        return window.RWS;
    }

    window.addEventListener('load', function () {
        crearInterfaz();
        rws = elegirRws();
        pintar();
        conectar().catch(function (err) {
            console.error('CajaPinza: no he podido conectar con RAPID', err);
            estado.rws = false;
            pintar();
            document.body.setAttribute('data-rws', 'sin-conexion');
        });
    });
}());
