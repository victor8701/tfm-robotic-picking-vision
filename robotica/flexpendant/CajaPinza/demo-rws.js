/*
 * RWS simulado para ver y probar la app sin controlador: ?demo en la direccion del navegador, y las
 * pruebas con jsdom (tests/js/app.test.js). Imita lo que hace main_movimiento de MOD_CajaPinza.mod y lo
 * que cuenta el PC por el socket; NO es RAPID, solo sirve para ver la pantalla y comprobar que la app
 * pone y consume las ordenes como espera RAPID. Los nombres y el orden de las fases son los de logica.js.
 */
(function (raiz, fabrica) {
    'use strict';
    if (typeof module === 'object' && module.exports) {
        module.exports = fabrica();
    } else {
        raiz.DemoRws = fabrica();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    const PARADO = {};   // se lanza para abandonar el programa al hacer Stop

    function crear(L, opciones) {
        const o = Object.assign({
            escala: 1,             // multiplica todas las esperas (las pruebas usan 0.01)
            ejecucion: 'stopped',  // estado inicial del programa
            pcConectado: true,
            sin: [],               // PERS que "no existen" en RAPID (modulo antiguo)
            falloEscritura: null,  // texto con el que falla setValue (mastership ocupada)
            falloFicheros: null,   // texto con el que falla el acceso a ficheros del controlador (sin permiso de fileservice)
            ficheros: {},          // ficheros que ya hay en el controlador: {'$HOME/parametros/x.csv': 'texto'}
            giroPc: null,          // function (giroCaja) -> giro que "lee" el PC; por defecto, el mismo
            egmMaxPos: 1500,       // egmMaxPos de RAPID (con 1000 solo caben 4 cajas de 200 mm en la mesa de la simulacion)
            valores: {}            // PERS que arrancan con otro valor que el de RAPID (en bruto, p. ej. {cajasVariables: 'FALSE'})
        }, opciones || {});
        const F = L.FASES;

        // Valores en bruto, como los entrega RWS.
        const pers = {
            usarHmi: 'TRUE', hmiFase: '0', hmiIniciar: 'FALSE', hmiCajaEnPosicion: 'FALSE', hmiConfirmar: 'TRUE',
            hmiPcConectado: 'FALSE', hmiGiroCaja: String(L.SIN_GIRO), hmiGiroPc: String(L.SIN_GIRO),
            hmiMensaje: '""', cajaNum: '0', nCajas: '1', modoSimulacion: 'TRUE', indiceFijo: '0', semillaGiros: '1234',
            mesaX0: String(L.MESA_SIM.mesaX0), mesaY0: String(L.MESA_SIM.mesaY0), mesaLargo: String(L.MESA_SIM.mesaLargo),
            mesaAncho: String(L.MESA_SIM.mesaAncho), mesaZ: String(L.MESA_SIM.mesaZ), mesaHueco: String(L.MESA_SIM.mesaHueco),
            egmMaxPos: String(o.egmMaxPos), alcanceMax: '790',
            cajaLargo: String(L.CAJA_SIM.cajaLargo), cajaAncho: String(L.CAJA_SIM.cajaAncho), cajaAlto: String(L.CAJA_SIM.cajaAlto),
            cajasVariables: 'TRUE', hmiMensajes: 'FALSE', hmiCaja: '""'
        };
        // Ajustes de puesta en marcha y demas PERS que la app conoce y no estan arriba: arrancan con su valor por defecto.
        const porDefecto = L.estadoInicial();
        Object.keys(L.VARIABLES).forEach(function (nombre) {
            if (Object.prototype.hasOwnProperty.call(pers, nombre)) { return; }
            const valor = porDefecto[L.VARIABLES[nombre].clave];
            pers[nombre] = typeof valor === 'boolean' ? (valor ? 'TRUE' : 'FALSE') : String(valor);
        });
        Object.assign(pers, o.valores);
        const nombresSenal = {sensor: 'CajaEnRecogida', cinta: 'CintaMover', pinzaCerrar: 'PinzaCerrar', pinzaCerrada: 'PinzaCerrada'};
        const senal = {CajaEnRecogida: 0, CintaMover: 0, PinzaCerrar: 0, PinzaCerrada: 0};
        const oyentesPers = {};
        const oyentesSenal = {};
        const oyentesEjecucion = [];
        let ejecucion = o.ejecucion;
        let generacion = 0;

        function aBruto(v) {
            if (typeof v === 'boolean') { return v ? 'TRUE' : 'FALSE'; }
            if (typeof v === 'number') { return String(v); }
            return '"' + String(v) + '"';
        }

        function avisar(lista, valor) {
            (lista || []).forEach(function (cb) { Promise.resolve().then(function () { cb(valor); }); });
        }

        function poner(nombre, valor) {
            const bruto = aBruto(valor);
            if (pers[nombre] === bruto) { return; }
            pers[nombre] = bruto;
            avisar(oyentesPers[nombre], bruto);
        }

        function ponerSenal(nombre, valor) {
            if (senal[nombre] === valor) { return; }
            senal[nombre] = valor;
            avisar(oyentesSenal[nombre], valor);
        }

        function ponerEjecucion(valor) {
            if (ejecucion === valor) { return; }
            ejecucion = valor;
            avisar(oyentesEjecucion, valor);
        }

        const bool = function (nombre) { return pers[nombre] === 'TRUE'; };
        const num = function (nombre) { return parseFloat(pers[nombre]); };

        function esperar(ms, gen) {
            return new Promise(function (ok, no) {
                setTimeout(function () { if (gen === generacion) { ok(); } else { no(PARADO); } }, ms * o.escala);
            });
        }

        async function hasta(condicion, gen) {
            while (!condicion()) { await esperar(20, gen); }
        }

        // main_movimiento de MOD_CajaPinza.mod (y las respuestas de T_COM a los mensajes del PC)
        async function programa(gen) {
            poner('hmiPcConectado', o.pcConectado);
            poner('hmiMensaje', '');
            poner('hmiGiroCaja', L.SIN_GIRO);
            poner('hmiGiroPc', L.SIN_GIRO);
            poner('cajaNum', 0);
            poner('hmiIniciar', false);
            poner('hmiCajaEnPosicion', false);
            poner('hmiFase', F.ESPERA_INICIAR);
            if (bool('usarHmi')) {
                await hasta(function () { return bool('hmiIniciar'); }, gen);
                poner('hmiIniciar', false);
            }
            poner('hmiFase', F.A_SEGURA);
            poner('nCajas', L.limitarCajas(num('nCajas')));
            const sim = bool('modoSimulacion');
            const n = num('nCajas');
            const indices = L.indicesGiro(n, num('semillaGiros'), num('indiceFijo'));
            poner('cajaNum', 0);
            await esperar(1500, gen);

            while (num('cajaNum') < n) {
                const i = num('cajaNum');
                let giroCaja = L.SIN_GIRO;
                poner('hmiGiroPc', L.SIN_GIRO);
                if (sim) {
                    giroCaja = L.giroDeIndice(indices[i]);
                    poner('hmiGiroCaja', giroCaja);
                    poner('hmiCaja', num('cajaLargo') + ' x ' + num('cajaAncho') + ' x ' + num('cajaAlto') + ' mm');
                    poner('hmiFase', F.COLOCANDO);
                    await esperar(500, gen);
                    poner('hmiFase', F.CINTA);
                    ponerSenal('CintaMover', 1);
                    await esperar(2000, gen);
                    ponerSenal('CintaMover', 0);
                    ponerSenal('CajaEnRecogida', 1);
                } else {
                    poner('hmiGiroCaja', L.SIN_GIRO);
                }
                poner('hmiCajaEnPosicion', false);
                poner('hmiFase', F.ESPERA_CAJA);
                if (bool('usarHmi') && bool('hmiConfirmar')) {
                    await hasta(function () { return bool('hmiCajaEnPosicion'); }, gen);
                    poner('hmiCajaEnPosicion', false);
                } else if (!sim) {
                    await hasta(function () { return senal.CajaEnRecogida === 1; }, gen);
                }
                poner('hmiFase', F.EGM_ABIERTO);
                await esperar(400, gen);
                const leido = o.giroPc ? o.giroPc(giroCaja) : (sim ? giroCaja : 15 * ((i % 5) - 2));
                poner('hmiGiroPc', leido);   // giro:<grados> del PC
                await esperar(1500, gen);
                ponerSenal('PinzaCerrar', 1);
                ponerSenal('PinzaCerrada', 1);
                ponerSenal('CajaEnRecogida', 0);   // la caja se va con la pinza
                poner('hmiFase', F.AGARRADA);
                await esperar(1500, gen);
                ponerSenal('PinzaCerrar', 0);
                ponerSenal('PinzaCerrada', 0);
                poner('hmiFase', F.SOLTADA);
                await esperar(1500, gen);
                poner('hmiFase', F.CERRANDO_EGM);
                await esperar(2500, gen);
                poner('hmiFase', F.VUELTA);
                await esperar(1500, gen);
                poner('cajaNum', i + 1);
            }
            poner('hmiFase', F.FIN);
            poner('hmiMensaje', 'Todas las cajas hechas. EGM cerrado.');
            poner('hmiPcConectado', false);
            ponerEjecucion('stopped');   // el Stop del final de main_movimiento
        }

        function play() {
            if (ejecucion === 'running') { return; }
            generacion += 1;
            ponerEjecucion('running');
            programa(generacion).catch(function (err) {
                if (err !== PARADO) { throw err; }
            });
        }

        function stop() {
            generacion += 1;
            ponerEjecucion('stopped');
        }

        function crearData(nombre) {
            return {
                fetch: function () {
                    return (nombre in pers && o.sin.indexOf(nombre) < 0)
                        ? Promise.resolve() : Promise.reject('Symbol ' + nombre + ' not found');
                },
                getRawValue: function () { return Promise.resolve(pers[nombre]); },
                addCallbackOnChanged: function (cb) { (oyentesPers[nombre] = oyentesPers[nombre] || []).push(cb); },
                subscribe: function () { return Promise.resolve(); },
                setValue: function (valor) {
                    if (o.falloEscritura) { return Promise.reject(o.falloEscritura); }
                    poner(nombre, valor);
                    return Promise.resolve();
                }
            };
        }

        function crearSenal(nombre) {
            return {
                getValue: function () { return Promise.resolve(senal[nombre]); },
                addCallbackOnChanged: function (cb) { (oyentesSenal[nombre] = oyentesSenal[nombre] || []).push(cb); },
                subscribe: function () { return Promise.resolve(); }
            };
        }

        // Sistema de ficheros del controlador (RWS.FileSystem), en memoria: lo justo para guardar y cargar ajustes.
        const ficheros = Object.assign({}, o.ficheros);
        const carpetas = {'$HOME': true};
        Object.keys(ficheros).forEach(function (ruta) { carpetas[ruta.substring(0, ruta.lastIndexOf('/'))] = true; });
        const rechazoFicheros = function () { return o.falloFicheros ? Promise.reject({message: o.falloFicheros}) : null; };
        const FileSystem = {
            getDirectory: function (ruta) {
                const fallo = rechazoFicheros();
                if (fallo) { return fallo; }
                if (!carpetas[ruta]) { return Promise.reject({message: 'Failed to fetch directory contents.'}); }
                const archivos = Object.keys(ficheros).filter(function (r) { return r.substring(0, r.lastIndexOf('/')) === ruta; })
                    .map(function (r) { return {name: r.substring(r.lastIndexOf('/') + 1), size: ficheros[r].length}; });
                return Promise.resolve({getContents: function () { return Promise.resolve({directories: [], files: archivos}); }});
            },
            createDirectory: function (ruta) {
                const fallo = rechazoFicheros();
                if (fallo) { return fallo; }
                carpetas[ruta] = true;
                return Promise.resolve({});
            },
            createFileObject: function (ruta) {
                let contenido = null;
                return {
                    setContents: function (texto) { contenido = texto; return true; },
                    fileExists: function () { return rechazoFicheros() || Promise.resolve(Object.prototype.hasOwnProperty.call(ficheros, ruta)); },
                    save: function (sobrescribir) {
                        const fallo = rechazoFicheros();
                        if (fallo) { return fallo; }
                        if (!carpetas[ruta.substring(0, ruta.lastIndexOf('/'))]) { return Promise.reject({message: 'Failed saving file.'}); }
                        if (!sobrescribir && Object.prototype.hasOwnProperty.call(ficheros, ruta)) { return Promise.reject({message: 'File already exists.'}); }
                        ficheros[ruta] = contenido;
                        return Promise.resolve();
                    },
                    getContents: function () { return Promise.resolve(contenido); }
                };
            },
            getFile: function (ruta) {
                const fallo = rechazoFicheros();
                if (fallo) { return fallo; }
                if (!Object.prototype.hasOwnProperty.call(ficheros, ruta)) { return Promise.reject({message: 'Failed fetching contents.'}); }
                return Promise.resolve({getContents: function () { return Promise.resolve(ficheros[ruta]); }});
            }
        };

        const RWS = {
            FileSystem: FileSystem,
            Rapid: {
                MonitorResources: {execution: 'execution'},
                getData: function (tarea, modulo, nombre) {
                    if (tarea !== L.TAREA || modulo !== L.MODULO) { return Promise.reject('Task or module not found'); }
                    return Promise.resolve(crearData(nombre));
                },
                getExecutionState: function () { return Promise.resolve(ejecucion); },
                stopExecution: function () { stop(); return Promise.resolve(); },    // Stop de RAPID
                resetPP: function () { return Promise.resolve(); },                  // PP a Main (el programa ya esta parado)
                getMonitor: function () {
                    return {
                        addCallbackOnChanged: function (cb) { oyentesEjecucion.push(cb); },
                        subscribe: function () { return Promise.resolve(); }
                    };
                }
            },
            IO: {
                getSignal: function (nombre) {
                    return nombre in senal ? Promise.resolve(crearSenal(nombre)) : Promise.reject('Signal ' + nombre + ' not found');
                }
            }
        };

        return {
            RWS: RWS,
            play: play,
            stop: stop,
            pers: pers,
            ficheros: ficheros,
            valor: function (nombre) { return pers[nombre]; },
            ejecucion: function () { return ejecucion; },
            forzarSenal: function (clave, valor) { ponerSenal(nombresSenal[clave], valor ? 1 : 0); },
            senal: function (clave) { return senal[nombresSenal[clave]]; }
        };
    }

    return {crear: crear};
}));
