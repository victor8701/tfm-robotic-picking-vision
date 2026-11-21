/*
 * Logica de la app CajaPinza, sin DOM ni RWS: asi se prueba con Node (tests/test_flexpendant.py lanza
 * logica.test.js). Las tablas (fases, nombres de las PERS y de las senales) y la formula de los giros
 * son copia de rapid/MOD_CajaPinza.mod y rapid/cfg/EIO/EIO.cfg; test_flexpendant.py comprueba que
 * siguen siendo iguales.
 *
 * Todo el estado de la celda cabe en un objeto (estadoInicial). calcularVista(estado) devuelve lo que
 * hay que dibujar: textos, botones activos, avisos, lista de giros... app.js solo lo pinta.
 */
(function (raiz, fabrica) {
    'use strict';
    if (typeof module === 'object' && module.exports) {
        module.exports = fabrica();
    } else {
        raiz.Logica = fabrica();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    // ---- Constantes de MOD_CajaPinza.mod ----
    const TAREA = 'T_ROB1';
    const MODULO = 'MOD_CajaPinza';
    const MAX_CAJAS = 100;      // maxCajas
    const N_GIROS = 12;         // nGiros
    const GIRO_MIN = -90;       // giroMin (grados)
    const GIRO_PASO = 15;       // giroPaso (grados)
    const SIN_GIRO = 999;       // sinGiro: el giro todavia no se sabe
    const SEMILLA_MOD = 8192;   // modulo del generador de giros; tambien el tope de semillaGiros

    // Momentos de la celda: FASE_<NOMBRE> de MOD_CajaPinza.mod.
    const FASES = Object.freeze({
        PARADO: 0, ESPERA_INICIAR: 1, A_SEGURA: 2, COLOCANDO: 3, CINTA: 4, ESPERA_CAJA: 5, EGM_ABIERTO: 6,
        AGARRADA: 7, SOLTADA: 8, CERRANDO_EGM: 9, VUELTA: 10, FIN: 11, ERROR: 99
    });

    // PERS de MOD_CajaPinza que usa la app. clave: nombre en el estado. escribe: la app la escribe.
    // lee: false = solo la escribe la app (no se suscribe). tipo: bool | num | string.
    const VARIABLES = Object.freeze({
        usarHmi:           {tipo: 'bool',   clave: 'usarHmi'},
        hmiFase:           {tipo: 'num',    clave: 'fase'},
        hmiIniciar:        {tipo: 'bool',   clave: 'iniciar', escribe: true, lee: false},
        hmiCajaEnPosicion: {tipo: 'bool',   clave: 'cajaEnPosicion', escribe: true, lee: false},
        hmiConfirmar:      {tipo: 'bool',   clave: 'confirmar', escribe: true},
        hmiPcConectado:    {tipo: 'bool',   clave: 'pcConectado'},
        hmiGiroCaja:       {tipo: 'num',    clave: 'giroCaja'},
        hmiGiroPc:         {tipo: 'num',    clave: 'giroPc'},
        hmiMensaje:        {tipo: 'string', clave: 'mensaje'},
        cajaNum:           {tipo: 'num',    clave: 'cajaNum'},
        nCajas:            {tipo: 'num',    clave: 'nCajas', escribe: true},
        modoSimulacion:    {tipo: 'bool',   clave: 'modoSimulacion', escribe: true},
        indiceFijo:        {tipo: 'num',    clave: 'indiceFijo', escribe: true},
        semillaGiros:      {tipo: 'num',    clave: 'semilla', escribe: true},
        mesaX0:            {tipo: 'num',    clave: 'mesaX0', escribe: true},
        mesaY0:            {tipo: 'num',    clave: 'mesaY0', escribe: true},
        mesaLargo:         {tipo: 'num',    clave: 'mesaLargo', escribe: true},
        mesaAncho:         {tipo: 'num',    clave: 'mesaAncho', escribe: true},
        mesaZ:             {tipo: 'num',    clave: 'mesaZ', escribe: true},
        mesaHueco:         {tipo: 'num',    clave: 'mesaHueco', escribe: true},
        egmMaxPos:         {tipo: 'num',    clave: 'egmMaxPos', escribe: true},
        alcanceMax:        {tipo: 'num',    clave: 'alcanceMax'},
        cajaLargo:         {tipo: 'num',    clave: 'cajaLargo', escribe: true},
        cajaAncho:         {tipo: 'num',    clave: 'cajaAncho', escribe: true},
        cajaAlto:          {tipo: 'num',    clave: 'cajaAlto', escribe: true},
        cajasVariables:    {tipo: 'bool',   clave: 'cajasVariables', escribe: true},
        hmiMensajes:       {tipo: 'bool',   clave: 'mensajes', escribe: true},
        recogidaModo:        {tipo: 'num',    clave: 'recogidaModo', escribe: true},
        recogidaX:           {tipo: 'num',    clave: 'recogidaX', escribe: true},
        recogidaY:           {tipo: 'num',    clave: 'recogidaY', escribe: true},
        recogidaTolX:        {tipo: 'num',    clave: 'recogidaTolX', escribe: true},
        recogidaTolY:        {tipo: 'num',    clave: 'recogidaTolY', escribe: true},
        camaraOffsetX:       {tipo: 'num',    clave: 'camaraOffsetX', escribe: true},
        camaraOffsetY:       {tipo: 'num',    clave: 'camaraOffsetY', escribe: true},
        camaraOffsetGiro:    {tipo: 'num',    clave: 'camaraOffsetGiro', escribe: true},
        tMaxCamara:          {tipo: 'num',    clave: 'tMaxCamara', escribe: true},
        zCinta:              {tipo: 'num',    clave: 'zCinta', escribe: true},
        giroPinza:           {tipo: 'num',    clave: 'giroPinza', escribe: true},
        agarreModo:          {tipo: 'num',    clave: 'agarreModo', escribe: true},
        agarrePorcentaje:    {tipo: 'num',    clave: 'agarrePorcentaje', escribe: true},
        agarreHundimiento:   {tipo: 'num',    clave: 'agarreHundimiento', escribe: true},
        agarreMinimo:        {tipo: 'num',    clave: 'agarreMinimo', escribe: true},
        solapeMinimo:        {tipo: 'num',    clave: 'solapeMinimo', escribe: true},
        aperturaPinza:       {tipo: 'num',    clave: 'aperturaPinza', escribe: true},
        grosorDedo:          {tipo: 'num',    clave: 'grosorDedo', escribe: true},
        tcpZ:                {tipo: 'num',    clave: 'tcpZ', escribe: true},
        margenAproximacion:  {tipo: 'num',    clave: 'margenAproximacion', escribe: true},
        tAntesAgarrar:       {tipo: 'num',    clave: 'tAntesAgarrar', escribe: true},
        tAgarre:             {tipo: 'num',    clave: 'tAgarre', escribe: true},
        tSuelta:             {tipo: 'num',    clave: 'tSuelta', escribe: true},
        tMaxPinza:           {tipo: 'num',    clave: 'tMaxPinza', escribe: true},
        tMaxCaja:            {tipo: 'num',    clave: 'tMaxCaja', escribe: true},
        tiempoConv:          {tipo: 'num',    clave: 'tiempoConv', escribe: true},
        velocidad:           {tipo: 'num',    clave: 'velocidad', escribe: true},
        zMinima:             {tipo: 'num',    clave: 'zMinima', escribe: true},
        seguroX:             {tipo: 'num',    clave: 'seguroX', escribe: true},
        seguroY:             {tipo: 'num',    clave: 'seguroY', escribe: true},
        seguroZ:             {tipo: 'num',    clave: 'seguroZ', escribe: true},
        hmiCaja:           {tipo: 'string', clave: 'caja'}
    });

    // Mesa de deposito. Valores por defecto de MOD_CajaPinza.mod: la mesa de la simulacion (mesa_marron).
    const MESA_SIM = Object.freeze({mesaX0: -900, mesaY0: 150, mesaLargo: 1200, mesaAncho: 1000, mesaZ: 320, mesaHueco: 40});
    // Campos numericos de la pestana Mesa: grupo, nombre, margenes que acepta la app y ayuda.
    const CAMPOS = Object.freeze([
        {grupo: 'zona', clave: 'mesaX0',    nombre: 'Esquina X mínima',   min: -3000, max: 3000, ayuda: 'x más pequeña de la zona'},
        {grupo: 'zona', clave: 'mesaY0',    nombre: 'Esquina Y mínima',   min: -3000, max: 3000, ayuda: 'y más pequeña de la zona'},
        {grupo: 'zona', clave: 'mesaLargo', nombre: 'Largo (en X)',       min: 50,    max: 4000, ayuda: 'hacia +x desde la esquina'},
        {grupo: 'zona', clave: 'mesaAncho', nombre: 'Ancho (en Y)',       min: 50,    max: 4000, ayuda: 'hacia +y desde la esquina'},
        {grupo: 'zona', clave: 'mesaZ',     nombre: 'Altura de la mesa',  min: 0,     max: 800,  ayuda: 'z de la superficie'},
        {grupo: 'zona', clave: 'mesaHueco', nombre: 'Hueco entre cajas',  min: 0,     max: 300,  ayuda: 'también al borde; más que las mordazas'},
        {grupo: 'caja', clave: 'cajaLargo', nombre: 'Largo máximo',       min: 10,    max: 600,  ayuda: 'lado largo de la mayor caja'},
        {grupo: 'caja', clave: 'cajaAncho', nombre: 'Ancho máximo',       min: 10,    max: 600,  ayuda: 'lado corto de la mayor caja'},
        {grupo: 'caja', clave: 'cajaAlto',  nombre: 'Alto máximo',        min: 10,    max: 600,  ayuda: 'altura de la mayor caja'}
    ]);
    const CAMPOS_MESA = Object.freeze(CAMPOS.filter(function (c) { return c.grupo === 'zona'; }));
    // Caja de referencia por defecto: el cubo de 200 mm de la simulacion.
    const CAJA_SIM = Object.freeze({cajaLargo: 200, cajaAncho: 200, cajaAlto: 200});
    // Geometria del PC con la que se calculan los huecos utiles (celda/config_celda.json y
    // puente_egm/config.celda.json). test_flexpendant.py comprueba que siguen siendo las mismas.
    const PC = Object.freeze({
        inicio: [600, -6.5, 543], zCinta: 220, zSeguro: 485, margen: 65, tcp: 147,
        puente: {x: [-600, 800], y: [-600, 800], z: [0, 800]}
    });

    // ---- Ventana Parametros: ajustes de puesta en marcha (PERS de MOD_CajaPinza.mod; el PC los pide a RAPID con los
    // mensajes recogida, agarre y celda). nombre, unidad y margenes que acepta la app. tipo: 'num' (por defecto), 'modo'
    // (opciones), 'lectura' (solo se muestra). solo: 'real' = no cuenta en simulacion. depende: {clave, valor, texto} = solo
    // vale con ese modo. protegido: pide confirmacion (advertencia). ----
    const MODO_CAMARA = {clave: 'recogidaModo', valor: 1, texto: 'el modo Cámara'};
    const PARAMETROS = Object.freeze([
        {id: 'recogida', titulo: 'Recogida',
            ayuda: 'Dónde está la caja que se agarra, en mm desde la base del robot. En simulación el punto lo da el sensor de la cinta.',
            items: [
                {clave: 'recogidaModo', tipo: 'modo', nombre: 'Posición de la caja', solo: 'real',
                    opciones: [{valor: 0, texto: 'Fija'}, {valor: 1, texto: 'Cámara'}],
                    ayuda: 'Fija: siempre en X, Y. Cámara: la que mide la cámara en cada caja, dentro de la zona permitida; si no la ve, el PC se para.'},
                {clave: 'recogidaX', nombre: 'Recogida X', unidad: 'mm', min: -1500, max: 1500,
                    ayuda: 'Centro de la caja en x. Con cámara es el punto nominal (centro de la zona permitida).',
                    notaSim: 'En simulación la estación pone la caja en x = 700: cámbialo solo si la mueves.'},
                {clave: 'recogidaY', nombre: 'Recogida Y', unidad: 'mm', min: -1500, max: 1500, solo: 'real',
                    ayuda: 'Centro de la caja en y. Con cámara es el punto nominal.'},
                {clave: 'recogidaTolX', nombre: 'Zona permitida ± X', unidad: 'mm', min: 0, max: 500, solo: 'real', depende: MODO_CAMARA, protegido: true,
                    advertencia: 'Es la zona donde el PC acepta cajas de la cámara: cuanto mayor, más riesgo de agarrar fuera de sitio.',
                    ayuda: 'Si la cámara pone la caja más lejos que esto de X, el PC no se mueve.'},
                {clave: 'recogidaTolY', nombre: 'Zona permitida ± Y', unidad: 'mm', min: 0, max: 500, solo: 'real', depende: MODO_CAMARA, protegido: true,
                    advertencia: 'Es la zona donde el PC acepta cajas de la cámara: cuanto mayor, más riesgo de agarrar fuera de sitio.',
                    ayuda: 'Si la cámara pone la caja más lejos que esto de Y, el PC no se mueve.'},
                {clave: 'camaraOffsetX', nombre: 'Corrección cámara X', unidad: 'mm', min: -200, max: 200, solo: 'real', depende: MODO_CAMARA,
                    ayuda: 'Se suma a la x que mide la cámara (ajuste fino de la calibración).'},
                {clave: 'camaraOffsetY', nombre: 'Corrección cámara Y', unidad: 'mm', min: -200, max: 200, solo: 'real', depende: MODO_CAMARA,
                    ayuda: 'Se suma a la y que mide la cámara.'},
                {clave: 'camaraOffsetGiro', nombre: 'Corrección cámara giro', unidad: '°', min: -90, max: 90, solo: 'real', depende: MODO_CAMARA,
                    ayuda: 'Se suma al giro de la caja que lee la cámara.'},
                {clave: 'zCinta', nombre: 'Altura de la cinta', unidad: 'mm', min: -500, max: 1500, protegido: true,
                    advertencia: 'Con la altura de la cinta mal medida, la pinza baja de más o de menos al agarrar.',
                    ayuda: 'z de la superficie de la cinta, desde la base del robot.'}
            ]},
        {id: 'pinza', titulo: 'Pinza y agarre',
            ayuda: 'Cómo agarra la pinza. h es la altura del punto de agarre sobre la base de la caja.',
            items: [
                {clave: 'giroPinza', nombre: 'Giro de la pinza', unidad: '°', min: -180, max: 180,
                    ayuda: 'Giro extra de las mordazas respecto a la caja (montaje de la pinza). 90 = mordazas en el otro eje.'},
                {clave: 'agarreModo', tipo: 'modo', nombre: 'Altura de agarre',
                    opciones: [{valor: 0, texto: 'Porcentaje'}, {valor: 1, texto: 'Desde la tapa'}],
                    ayuda: 'Porcentaje: h = alto × %. Desde la tapa: los dedos cierran siempre a la misma distancia bajo la tapa.'},
                {clave: 'agarrePorcentaje', nombre: 'Agarre (porcentaje)', unidad: '%', min: 1, max: 100, depende: {clave: 'agarreModo', valor: 0, texto: 'el modo Porcentaje'},
                    ayuda: '50 = a media altura de la caja.'},
                {clave: 'agarreHundimiento', nombre: 'Agarre bajo la tapa', unidad: 'mm', min: 0, max: 500, depende: {clave: 'agarreModo', valor: 1, texto: 'el modo Desde la tapa'},
                    ayuda: 'h = alto − este valor.'},
                {clave: 'agarreMinimo', nombre: 'Agarre mínimo', unidad: 'mm', min: 0, max: 500,
                    ayuda: 'h no baja de esto: los dedos sobresalen por debajo del punto de agarre y no deben tocar la cinta.'},
                {clave: 'solapeMinimo', nombre: 'Alto mínimo agarrable', unidad: 'mm', min: 0, max: 500,
                    ayuda: 'Lo que debe tocar el dedo la pared: una caja más baja no se coge.'},
                {clave: 'aperturaPinza', nombre: 'Apertura de la pinza', unidad: 'mm', min: 0, max: 500,
                    ayuda: 'El PC rechaza cajas cuyo lado agarrado (el ancho) es mayor. 0 = sin comprobar.'},
                {clave: 'grosorDedo', nombre: 'Grosor del dedo', unidad: 'mm', min: 0, max: 200,
                    ayuda: 'Tiene que caber en el hueco entre cajas de la mesa. 0 = sin comprobar.'},
                {clave: 'tcpZ', nombre: 'Largo de la pinza (TCP z)', unidad: 'mm', min: 1, max: 600, protegido: true,
                    advertencia: 'Distancia de la brida al punto de agarre: tiene que ser la de la pinza real o el robot irá a otro punto.',
                    ayuda: 'De la brida al punto donde cierran los dedos.'},
                {clave: 'margenAproximacion', nombre: 'Margen de aproximación', unidad: 'mm', min: 0, max: 500,
                    ayuda: 'Altura sobre la caja al acercarse y al transportar.'}
            ]},
        {id: 'tiempos', titulo: 'Tiempos',
            ayuda: 'Segundos. Las pausas dan tiempo a la pinza y a la caja; los máximos paran el programa con un aviso si algo no llega.',
            items: [
                {clave: 'tAntesAgarrar', nombre: 'Pausa antes de agarrar', unidad: 's', min: 0, max: 30,
                    ayuda: 'Desde CAJA EN POSICIÓN hasta empezar el movimiento: que la caja se pare.'},
                {clave: 'tAgarre', nombre: 'Pausa al agarrar', unidad: 's', min: 0, max: 30,
                    ayuda: 'Tras confirmar el cierre de la pinza, antes de subir la caja.'},
                {clave: 'tSuelta', nombre: 'Pausa al soltar', unidad: 's', min: 0, max: 30,
                    ayuda: 'Tras confirmar la apertura, antes de irse.'},
                {clave: 'tMaxPinza', nombre: 'Máximo esperando a la pinza', unidad: 's', min: 0.5, max: 30,
                    ayuda: 'Espera máxima a PinzaCerrada al cerrar y al abrir.'},
                {clave: 'tMaxCaja', nombre: 'Máximo esperando a la caja', unidad: 's', min: 0, max: 600,
                    ayuda: 'Espera máxima a que llegue la caja. 0 = sin límite.'},
                {clave: 'tMaxCamara', nombre: 'Máximo esperando a la cámara', unidad: 's', min: 0, max: 60, solo: 'real', depende: MODO_CAMARA,
                    ayuda: 'Espera máxima a una detección: si no llega, el PC se para.'},
                {clave: 'tiempoConv', nombre: 'Quieto antes de cerrar el EGM', unidad: 's', min: 0.5, max: 20,
                    ayuda: 'Segundos que el robot espera quieto en la salida antes de cerrar el EGM. Es lo que más alarga el ciclo.'}
            ]},
        {id: 'movimiento', titulo: 'Movimiento y seguridad',
            ayuda: 'Límites del movimiento. Cambiar los protegidos pide confirmación.',
            items: [
                {clave: 'velocidad', nombre: 'Velocidad máxima', unidad: 'mm/s', min: 5, max: 100, protegido: true,
                    advertencia: 'Velocidad máxima del TCP que manda el PC. Empieza lento en las primeras pruebas con el robot real; 100 es el tope del puente.',
                    ayuda: 'Más rápido que 100 exige cambiar el puente (config.celda.json).'},
                {clave: 'zMinima', nombre: 'Suelo del TCP', unidad: 'mm', min: 0, max: 1500, protegido: true,
                    advertencia: 'El PC rechaza cualquier punto por debajo de esta altura.',
                    ayuda: '0 = automático: el menor de la altura de la cinta y la de la mesa.'},
                {clave: 'seguroX', nombre: 'Punto de espera X', unidad: 'mm', min: -600, max: 800, protegido: true,
                    advertencia: 'Punto de espera donde empieza cada sesión EGM: el robot va allí al empezar la tanda.',
                    ayuda: 'Punto (TCP) sobre la cinta donde empieza cada caja y adonde vuelve el robot.'},
                {clave: 'seguroY', nombre: 'Punto de espera Y', unidad: 'mm', min: -600, max: 800, protegido: true,
                    advertencia: 'Punto de espera donde empieza cada sesión EGM: el robot va allí al empezar la tanda.',
                    ayuda: 'y del punto de espera.'},
                {clave: 'seguroZ', nombre: 'Punto de espera Z', unidad: 'mm', min: 0, max: 800, protegido: true,
                    advertencia: 'Punto de espera donde empieza cada sesión EGM: el robot va allí al empezar la tanda.',
                    ayuda: 'z del punto de espera. Debe quedar sobre la caja que llega.'},
                {clave: 'egmMaxPos', nombre: 'Límite del EGM', unidad: 'mm', min: 500, max: 2000, protegido: true,
                    tituloConfirmar: 'Cambiar el límite del EGM',
                    ayuda: 'Distancia máxima al punto de espera. Es lo que más limita cuántas cajas caben en la mesa.'},
                {clave: 'alcanceMax', tipo: 'lectura', nombre: 'Alcance máximo', unidad: 'mm',
                    ayuda: 'Radio máximo de la pinza desde el eje del robot. Solo se muestra.'}
            ]}
    ]);
    const CAMPOS_PARAMETROS = Object.freeze(PARAMETROS.reduce(function (todos, s) {
        return todos.concat(s.items.filter(function (it) { return (it.tipo || 'num') === 'num'; }));
    }, []));

    // Texto de la confirmacion al cambiar un ajuste protegido.
    function textoConfirmacion(item, valor, antes) {
        if (item.clave === 'egmMaxPos') {
            return {titulo: item.tituloConfirmar, lineas: [
                'El controlador para el EGM (Motors Off) si el robot se aleja más de ' + valor + ' mm del punto de espera.',
                'Con más límite caben más cajas en la mesa, pero hay menos protección. ¿Cambiarlo de ' + antes + ' a ' + valor + ' mm?'
            ]};
        }
        return {titulo: item.tituloConfirmar || ('Cambiar ' + item.nombre.toLowerCase()), lineas: [
            item.advertencia, '¿Cambiarlo de ' + antes + ' a ' + valor + ' ' + (item.unidad || '') + '?'
        ]};
    }

    // ---- Ajustes de puesta en marcha: valores por defecto y fichero CSV ----
    // Los que se reponen, se guardan y se cargan: todo lo de la ventana Parametros (menos lo de solo lectura), la zona de
    // la mesa y la caja de referencia. No entran los de cada tanda (cajas, modo, giro, boton, mensajes).
    const AJUSTES = Object.freeze(PARAMETROS.reduce(function (todos, s) {
        return todos.concat(s.items.filter(function (it) { return it.tipo !== 'lectura'; }).map(function (it) {
            return {clave: it.clave, nombre: it.nombre, unidad: it.unidad || '', tipo: it.tipo || 'num', min: it.min, max: it.max,
                opciones: it.opciones || null, protegido: !!it.protegido, seccion: s.titulo};
        }));
    }, []).concat(CAMPOS.map(function (c) {
        return {clave: c.clave, nombre: c.nombre, unidad: 'mm', tipo: 'num', min: c.min, max: c.max, opciones: null, protegido: false,
            seccion: c.grupo === 'zona' ? 'Mesa de depósito' : 'Caja de referencia'};
    })));

    // Valores por defecto de MOD_CajaPinza.mod (clave -> valor); test_flexpendant.py comprueba que son los del modulo.
    function valoresPorDefecto() {
        const e = estadoInicial();
        const v = {};
        AJUSTES.forEach(function (a) { v[a.clave] = e[a.clave]; });
        return v;
    }

    // Que ajustes cambiarian si se pusieran estos valores (clave -> valor) y cuantos ya valen lo mismo.
    function cambiosHacia(e, valores) {
        const cambios = [];
        let iguales = 0;
        AJUSTES.forEach(function (a) {
            if (!Object.prototype.hasOwnProperty.call(valores, a.clave)) { return; }
            if (e[a.clave] === valores[a.clave]) { iguales += 1; return; }
            cambios.push({clave: a.clave, nombre: a.nombre, unidad: a.unidad, antes: e[a.clave], ahora: valores[a.clave], protegido: a.protegido});
        });
        return {cambios: cambios, iguales: iguales};
    }

    // CSV con los ajustes del estado: parametro;valor;unidad;descripcion, uno por linea (punto decimal).
    function aCsv(e) {
        const filas = ['parametro;valor;unidad;descripcion'];
        AJUSTES.forEach(function (a) {
            filas.push([a.clave, e[a.clave], a.unidad, (a.seccion + ': ' + a.nombre).replace(/;/g, ',')].join(';'));
        });
        return filas.join('\r\n') + '\r\n';
    }

    // Lee un CSV de ajustes (el que escribe aCsv, o uno editado a mano: separador ; , o tabulador, coma decimal si el separador no
    // es la coma, cabecera opcional, lineas vacias o con # ignoradas). Devuelve lo que cambiaria y lo que no vale; no toca nada.
    function desdeCsv(texto, e) {
        const lineas = String(texto).replace(/^﻿/, '').split(/\r?\n/);
        const porClave = {};
        AJUSTES.forEach(function (a) { porClave[a.clave] = a; });
        const valores = {};
        const ignorados = [];
        let separador = null;
        let cabecera = true;
        lineas.forEach(function (linea, i) {
            const t = linea.trim();
            if (t === '' || t.charAt(0) === '#') { return; }
            if (separador === null) { separador = t.indexOf(';') >= 0 ? ';' : (t.indexOf('\t') >= 0 ? '\t' : ','); }
            const celdas = t.split(separador);
            const clave = celdas[0].trim();
            if (cabecera && clave.toLowerCase() === 'parametro') { cabecera = false; return; }
            cabecera = false;
            const a = porClave[clave];
            if (!a) { ignorados.push({linea: i + 1, texto: clave, motivo: 'ajuste desconocido'}); return; }
            let bruto = (celdas[1] || '').trim();
            if (separador !== ',') { bruto = bruto.replace(',', '.'); }
            if (!/^-?\d+(\.\d+)?$/.test(bruto)) { ignorados.push({linea: i + 1, texto: clave, motivo: 'valor no numérico'}); return; }
            const v = Math.round(Number(bruto) * 10) / 10;
            if (a.tipo === 'modo') {
                if (!a.opciones.some(function (o) { return o.valor === v; })) {
                    ignorados.push({linea: i + 1, texto: clave, motivo: 'modo no válido (' + a.opciones.map(function (o) { return o.valor + ' = ' + o.texto; }).join(', ') + ')'});
                    return;
                }
            } else if (v < a.min || v > a.max) {
                ignorados.push({linea: i + 1, texto: clave, motivo: 'fuera de margen (' + a.min + ' a ' + a.max + ')'});
                return;
            }
            valores[clave] = v;
        });
        const r = cambiosHacia(e, valores);
        return {reconocidos: Object.keys(valores).length, cambios: r.cambios, iguales: r.iguales, ignorados: ignorados};
    }

    // Nombre de fichero que escribe el usuario (sin .csv): letras, numeros, espacio, guion y guion bajo; hasta 40 caracteres.
    function nombreFicheroValido(texto) {
        const nombre = String(texto === undefined || texto === null ? '' : texto).trim().replace(/\.csv$/i, '').trim();
        if (nombre === '') { return {ok: false, nombre: '', motivo: 'Escribe un nombre para el fichero.'}; }
        if (!/^[A-Za-z0-9][A-Za-z0-9 _-]{0,39}$/.test(nombre)) {
            return {ok: false, nombre: nombre, motivo: 'El nombre solo puede llevar letras, números, espacios, guiones y guiones bajos (hasta 40 caracteres, sin tildes ni puntos).'};
        }
        return {ok: true, nombre: nombre, motivo: ''};
    }

    // Senales de E/S que se muestran (rapid/cfg/EIO/EIO.cfg, todas con Access Level All).
    const SENALES = Object.freeze({
        sensor: 'CajaEnRecogida',
        cinta: 'CintaMover',
        pinzaCerrar: 'PinzaCerrar',
        pinzaCerrada: 'PinzaCerrada'
    });

    // Pasos de una caja, en orden. soloSim: no existen en real (no hay cinta que mover).
    const PASOS = Object.freeze([
        {id: 'colocar',  texto: 'Poner la caja',        fases: [FASES.COLOCANDO],    soloSim: true},
        {id: 'cinta',    texto: 'Cinta hasta el sensor', fases: [FASES.CINTA],        soloSim: true},
        {id: 'posicion', texto: 'Caja en posición',      fases: [FASES.ESPERA_CAJA]},
        {id: 'egm',      texto: 'EGM: a por la caja',    fases: [FASES.EGM_ABIERTO]},
        {id: 'agarrada', texto: 'Agarrada, a la mesa',   fases: [FASES.AGARRADA]},
        {id: 'soltada',  texto: 'Soltada, salida',       fases: [FASES.SOLTADA]},
        {id: 'cerrando', texto: 'Cerrando el EGM',       fases: [FASES.CERRANDO_EGM]},
        {id: 'vuelta',   texto: 'Vuelta a seguridad',    fases: [FASES.VUELTA]}
    ]);

    // ---- Conversion de lo que devuelve RWS (cadenas en bruto: TRUE, 5, "texto") ----
    function aBool(v) {
        if (typeof v === 'boolean') { return v; }
        if (typeof v === 'number') { return v !== 0; }
        if (typeof v === 'string') { return v.trim().toUpperCase() === 'TRUE'; }
        return false;
    }

    function aNum(v, porDefecto) {
        const n = typeof v === 'number' ? v : parseFloat(String(v));
        return Number.isFinite(n) ? n : (porDefecto === undefined ? NaN : porDefecto);
    }

    function aTexto(v) {
        if (v === null || v === undefined) { return ''; }
        let s = String(v);
        if (s.length >= 2 && s.charAt(0) === '"' && s.charAt(s.length - 1) === '"') { s = s.slice(1, -1); }
        return s;
    }

    function convertir(tipo, v) {
        if (tipo === 'bool') { return aBool(v); }
        if (tipo === 'num') { return aNum(v, 0); }
        return aTexto(v);
    }

    // ---- Estado ----
    function estadoInicial() {
        return {
            rws: false,            // se ha podido leer RAPID
            ejecucion: null,       // 'running' | 'stopped' | null (no se sabe)
            faltan: [],            // PERS que no se han encontrado en RAPID
            usarHmi: true,
            fase: FASES.PARADO,
            cajaNum: 0,
            nCajas: 1,
            modoSimulacion: true,
            indiceFijo: 0,          // 0 = giros al azar
            semilla: 1234,
            confirmar: true,
            pcConectado: false,
            giroCaja: SIN_GIRO,
            giroPc: SIN_GIRO,
            mensaje: '',
            mesaX0: MESA_SIM.mesaX0, mesaY0: MESA_SIM.mesaY0, mesaLargo: MESA_SIM.mesaLargo,
            mesaAncho: MESA_SIM.mesaAncho, mesaZ: MESA_SIM.mesaZ, mesaHueco: MESA_SIM.mesaHueco,
            egmMaxPos: 1500,
            alcanceMax: 790,
            cajaLargo: CAJA_SIM.cajaLargo, cajaAncho: CAJA_SIM.cajaAncho, cajaAlto: CAJA_SIM.cajaAlto,
            cajasVariables: true,
            mensajes: false,
            caja: '',
            senales: {sensor: null, cinta: null, pinzaCerrar: null, pinzaCerrada: null},
            // Ordenes de pinza vistas por la senal PinzaCerrar (subida = cerrar, bajada = abrir) en la tanda en curso;
            // cambio: cuando cambio por ultima vez PinzaCerrar o PinzaCerrada (ms).
            pinza: {cerrar: 0, abrir: 0, ultima: null, caja: 0, tUltima: 0, cambio: 0},
            // Puesta en marcha (ventana Parametros): los valores por defecto de MOD_CajaPinza.mod
            recogidaModo: 0, recogidaX: 700, recogidaY: 0, recogidaTolX: 50, recogidaTolY: 50,
            camaraOffsetX: 0, camaraOffsetY: 0, camaraOffsetGiro: 0, tMaxCamara: 5, zCinta: 220,
            giroPinza: 0, agarreModo: 0, agarrePorcentaje: 50, agarreHundimiento: 30, agarreMinimo: 10, solapeMinimo: 10,
            aperturaPinza: 0, grosorDedo: 0, tcpZ: 147, margenAproximacion: 65,
            tAntesAgarrar: 0, tAgarre: 0, tSuelta: 0, tMaxPinza: 3, tMaxCaja: 40, tiempoConv: 2.5,
            velocidad: 100, zMinima: 0, seguroX: 600, seguroY: -6.5, seguroZ: 543
        };
    }

    // Guarda el valor de una senal (clave de SENALES; ahora en ms). Al cambiar PinzaCerrar anota la orden de la pinza:
    // la primera lectura solo fija el valor de partida.
    function ponerSenal(e, clave, valor, ahora) {
        const antes = e.senales[clave];
        e.senales[clave] = valor;
        if (antes === valor) { return e; }
        if (clave === 'pinzaCerrar' || clave === 'pinzaCerrada') { e.pinza.cambio = ahora; }
        if (clave === 'pinzaCerrar' && antes !== null && antes !== undefined) {
            const orden = valor ? 'cerrar' : 'abrir';
            e.pinza[orden] += 1;
            e.pinza.ultima = orden;
            e.pinza.caja = Math.min(e.cajaNum + 1, Math.max(e.nCajas, 1));
            e.pinza.tUltima = ahora;
        }
        return e;
    }

    function haceTexto(ms) {
        const s = Math.max(0, Math.round(ms / 1000));
        if (s < 2) { return 'ahora mismo'; }
        return s < 60 ? 'hace ' + s + ' s' : 'hace ' + Math.floor(s / 60) + ' min';
    }

    // La ventana Parametros: cada ajuste con su valor, si se puede cambiar ahora y por que no.
    function vistaParametros(e, editable) {
        const sim = e.modoSimulacion;
        return {
            editable: editable,
            secciones: PARAMETROS.map(function (s) {
                return {id: s.id, titulo: s.titulo, ayuda: s.ayuda, items: s.items.map(function (it) {
                    let nota = '';
                    let aplica = true;
                    if (it.solo === 'real' && sim) { nota = 'Solo en Real: en simulación el punto lo da el sensor de la cinta.'; aplica = false; }
                    else if (it.depende && e[it.depende.clave] !== it.depende.valor) { nota = 'Solo con ' + it.depende.texto + '.'; aplica = false; }
                    else if (it.notaSim && sim) { nota = it.notaSim; }
                    const tipo = it.tipo || 'num';
                    return {clave: it.clave, tipo: tipo, nombre: it.nombre, unidad: it.unidad || '', valor: e[it.clave], min: it.min, max: it.max,
                        opciones: it.opciones || null, ayuda: it.ayuda, protegido: !!it.protegido, nota: nota,
                        activo: tipo !== 'lectura' && editable && aplica};
                })};
            })
        };
    }

    // Lo que muestra la tarjeta Pinza: el estado segun las dos senales (orden PinzaCerrar y confirmacion PinzaCerrada),
    // y cuantas ordenes se han visto en la tanda.
    function vistaPinza(e, ahora) {
        const orden = e.senales.pinzaCerrar;
        const conf = e.senales.pinzaCerrada;
        const p = e.pinza;
        let estado, titulo, tono, detalle;
        if (orden === null || orden === undefined || conf === null || conf === undefined) {
            estado = 'sin-lectura'; titulo = 'SIN LECTURA'; tono = 'parado';
            detalle = 'No leo PinzaCerrar o PinzaCerrada. Comprueba que tienen Access Level = All en el EIO.cfg.';
        } else if (orden && conf) {
            estado = 'cerrada'; titulo = 'CERRADA'; tono = 'ok';
            detalle = 'Orden de cerrar enviada y confirmada por PinzaCerrada.';
        } else if (!orden && !conf) {
            estado = 'abierta'; titulo = 'ABIERTA'; tono = 'activo';
            detalle = 'Sin orden de cerrar.';
        } else {
            const colgada = ahora - p.cambio > Math.max(e.tMaxPinza, 0.5) * 1000;   // RAPID espera tMaxPinza s
            estado = orden ? 'cerrando' : 'abriendo';
            titulo = colgada ? 'SIN CONFIRMACIÓN' : (orden ? 'CERRANDO…' : 'ABRIENDO…');
            tono = colgada ? 'error' : 'espera';
            detalle = orden ? 'Orden de cerrar enviada; falta que PinzaCerrada suba.' : 'Orden de abrir enviada; falta que PinzaCerrada baje.';
            if (colgada) { detalle += ' RAPID espera ' + Math.max(e.tMaxPinza, 0.5) + ' s y para con fallo_pinza.'; }
        }
        let resumen = 'Órdenes de esta tanda: cerrar ' + p.cerrar + ' · abrir ' + p.abrir;
        if (p.ultima) { resumen += ' · última: ' + p.ultima + ' (caja ' + p.caja + ') ' + haceTexto(ahora - p.tUltima); }
        return {estado: estado, titulo: titulo, tono: tono, detalle: detalle, resumen: resumen,
            orden: orden === undefined ? null : orden, confirmacion: conf === undefined ? null : conf};
    }

    // Guarda en el estado el valor de una PERS de RAPID (nombre de RAPID, valor en bruto).
    function aplicarVariable(estado, nombreRapid, valor) {
        const def = VARIABLES[nombreRapid];
        if (!def || def.lee === false) { return estado; }
        const nuevo = convertir(def.tipo, valor);
        if (def.clave === 'fase' && nuevo === FASES.ESPERA_INICIAR && estado.fase !== FASES.ESPERA_INICIAR) {
            // tanda nueva: las ordenes de pinza se cuentan desde cero (cambio se conserva)
            Object.assign(estado.pinza, {cerrar: 0, abrir: 0, ultima: null, caja: 0, tUltima: 0});
        }
        estado[def.clave] = nuevo;
        return estado;
    }

    function normalizarEjecucion(v) {
        if (v === 'running' || v === 'stopped') { return v; }
        if (v && typeof v === 'object' && (v.state === 'running' || v.state === 'stopped')) { return v.state; }
        return null;
    }

    // ---- Giros: la misma cuenta que MOD_CajaPinza.mod ----
    // semilla := (semilla * 1021 + 11) MOD 8192;  k := ((semilla DIV 16) MOD 12) + 1  (o indiceFijo)
    function giroDeIndice(k) { return GIRO_MIN + (k - 1) * GIRO_PASO; }

    function siguienteSemilla(s) { return (s * 1021 + 11) % SEMILLA_MOD; }

    function semillaValida(s) { return Number.isInteger(s) && s >= 0 && s < SEMILLA_MOD; }

    function indicesGiro(nCajas, semilla, indiceFijo) {
        const salida = [];
        let s = semilla;
        for (let i = 1; i <= nCajas; i++) {
            s = siguienteSemilla(s);
            if (indiceFijo >= 1 && indiceFijo <= N_GIROS) {
                salida.push(indiceFijo);
            } else {
                salida.push((Math.floor(s / 16) % N_GIROS) + 1);
            }
        }
        return salida;
    }

    function secuenciaGiros(nCajas, semilla, indiceFijo) {
        return indicesGiro(nCajas, semilla, indiceFijo).map(giroDeIndice);
    }

    function nuevaSemilla(aleatorio) {
        const r = typeof aleatorio === 'function' ? aleatorio() : Math.random();
        return Math.min(SEMILLA_MOD - 1, Math.max(0, Math.floor(r * SEMILLA_MOD)));
    }

    // Ajustes que se ponen por defecto al cambiar de modo (nombre de la PERS de RAPID -> valor). Despues se
    // pueden cambiar a mano. Simulacion: giros al azar y cajas de tamaños distintos. Real: esperar el boton
    // CAJA EN POSICION en cada caja. Pulsar el modo que ya esta activo no toca nada.
    function ajustesDeModo(simulacion) {
        return simulacion ? {indiceFijo: 0, cajasVariables: true} : {hmiConfirmar: true};
    }

    function limitarCajas(n) {
        const v = Math.round(aNum(n, 1));
        return Math.max(1, Math.min(MAX_CAJAS, v));
    }

    function textoGiro(g) {
        if (g === null || g === undefined || !Number.isFinite(g)) { return '—'; }
        const r = Math.round(g * 10) / 10;
        return (r < 0 ? '−' : '') + Math.abs(r) + '°';
    }

    // Esquinas (x, y en pantalla) de una caja cuadrada de semilado `medio` girada `giro` grados
    // (antihorario visto desde arriba, x a la derecha e y hacia arriba, como la base del robot).
    function puntosCaja(giro, medio, cx, cy) {
        const a = giro * Math.PI / 180;
        const c = Math.cos(a);
        const s = Math.sin(a);
        const redondo = function (x) { return Math.round(x * 100) / 100; };
        return [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(function (p) {
            const x = (p[0] * c - p[1] * s) * medio;
            const y = (p[0] * s + p[1] * c) * medio;
            return [redondo(cx + x), redondo(cy - y)];
        });
    }

    // ---- Mesa de deposito: el mismo reparto y los mismos limites que el PC (celda/planificacion.py) ----
    const PASO_BUSQUEDA = 10;   // PASO_BUSQUEDA_MM del PC

    function mesaDeEstado(e) {
        return {x0: e.mesaX0, y0: e.mesaY0, largo: e.mesaLargo, ancho: e.mesaAncho, z: e.mesaZ, hueco: e.mesaHueco};
    }

    function cajaDeReferencia(e) {
        return {largo: e.cajaLargo, ancho: e.cajaAncho, alto: e.cajaAlto};
    }

    // Puntos del TCP de un destino: entrada, sobre el hueco, deposito y salida (_poses_destino del PC).
    // Ajustes del PC que cambian la geometria (los de la ventana Parametros). Lo que no venga en lim vale lo de PC y la
    // altura de agarre por defecto (el centro de la caja, sin comprobaciones).
    const AGARRE_POR_DEFECTO = Object.freeze({modo: 0, porcentaje: 50, hundimiento: 30, minimo: 10, solape: 10, apertura: 0});

    function limitesDeEstado(e) {
        return {
            egmMaxPos: e.egmMaxPos, alcanceMax: e.alcanceMax,
            inicio: [e.seguroX, e.seguroY, e.seguroZ], zCinta: e.zCinta, margen: e.margenAproximacion, tcp: e.tcpZ, zMinima: e.zMinima,
            agarre: {modo: e.agarreModo, porcentaje: e.agarrePorcentaje, hundimiento: e.agarreHundimiento, minimo: e.agarreMinimo,
                solape: e.solapeMinimo, apertura: e.aperturaPinza}
        };
    }

    // altura_agarre del PC: altura h del punto de agarre sobre la base de la caja. {h} o {error: texto}.
    function alturaAgarre(caja, lim) {
        const a = (lim && lim.agarre) || AGARRE_POR_DEFECTO;
        if (caja.alto < a.solape) {
            return {error: 'la caja mide ' + caja.alto + ' mm de alto y el dedo necesita tocar al menos ' + a.solape + ' mm de pared'};
        }
        if (a.apertura > 0 && caja.ancho > a.apertura) {
            return {error: 'el lado que agarra la pinza mide ' + caja.ancho + ' mm y la pinza abre ' + a.apertura + ' mm'};
        }
        let h = a.modo === 1 ? caja.alto - a.hundimiento : caja.alto * a.porcentaje / 100;
        h = Math.max(h, a.minimo);
        if (h > caja.alto) {
            return {error: 'el agarre más bajo posible (' + a.minimo + ' mm) queda por encima de la tapa de la caja (' + caja.alto + ' mm)'};
        }
        return {h: h};
    }

    function puntosDestino(caja, d, lim) {
        const l = lim || {};
        const zCinta = l.zCinta !== undefined ? l.zCinta : PC.zCinta;
        const margen = l.margen !== undefined ? l.margen : PC.margen;
        const ag = alturaAgarre(caja, l);
        const h = ag.error === undefined ? ag.h : caja.alto / 2;   // sin agarre posible, solo para el dibujo
        const zDeposito = d.zMesa + h;
        const zViaje = Math.max(zCinta + caja.alto + margen, zDeposito + margen);
        const zSalida = Math.max(PC.zSeguro, d.zMesa + Math.max(caja.alto, d.altoLibre) + margen);
        return [{x: d.xEntrada, y: d.y, z: zViaje}, {x: d.x, y: d.y, z: zViaje}, {x: d.x, y: d.y, z: zDeposito}, {x: d.x, y: d.y, z: zSalida}];
    }

    // validar_puntos del PC: espacio del puente (en la brida), ventana por eje, limite del EGM y alcance.
    function puntoPermitido(p, lim) {
        const inicio = lim.inicio || PC.inicio;
        const x0 = inicio[0];
        const y0 = inicio[1];
        const z0 = inicio[2];
        const brida = p.z + (lim.tcp !== undefined ? lim.tcp : PC.tcp);
        // suelo del TCP: el menor de la cinta y la mesa, o zMinima si es mayor (solo si se conoce la mesa: lim.zMesa)
        if (lim.zMesa !== undefined) {
            const suelo = Math.max(lim.zMinima || 0, Math.min(lim.zCinta !== undefined ? lim.zCinta : PC.zCinta, lim.zMesa));
            if (p.z < suelo - 1e-6) { return false; }
        }
        if (p.x < PC.puente.x[0] || p.x > PC.puente.x[1] || p.y < PC.puente.y[0] || p.y > PC.puente.y[1]
                || brida < PC.puente.z[0] || brida > PC.puente.z[1]) { return false; }
        const semiancho = lim.egmMaxPos - 100;
        if (Math.abs(p.x - x0) > semiancho || Math.abs(p.y - y0) > semiancho || Math.abs(p.z - z0) > semiancho) { return false; }
        if (Math.sqrt(Math.pow(p.x - x0, 2) + Math.pow(p.y - y0, 2) + Math.pow(p.z - z0, 2)) > lim.egmMaxPos - 1) { return false; }
        return Math.sqrt(p.x * p.x + p.y * p.y) <= lim.alcanceMax;
    }

    function alcanzable(caja, d, lim) {
        const limite = Object.assign({}, lim, {zMesa: d.zMesa});
        return puntosDestino(caja, d, lim).every(function (p) { return puntoPermitido(p, limite); });
    }

    function nuevoReparto(mesa) {
        return {mesa: mesa, filaY: mesa.y0 + mesa.hueco, fondo: 0, cursor: mesa.x0 + mesa.hueco, altoMax: 0, colocadas: 0};
    }

    // Reparto.colocar del PC: cajas en filas a lo largo de x, de x menor a mayor, la fila siguiente pegada a la
    // anterior; los sitios que el robot no alcanza se saltan. Devuelve el destino o null (el reparto no cambia).
    function colocar(rep, caja, lim) {
        const m = rep.mesa;
        const xBorde = m.x0 + m.largo - m.hueco;
        const yBorde = m.y0 + m.ancho - m.hueco;
        const entrada = m.x0 + m.largo + caja.largo / 2 + m.hueco;
        const altoLibre = Math.max(rep.altoMax, caja.alto);
        let filaY = rep.filaY;
        let fondo = rep.fondo;
        let cursor = rep.cursor;
        while (filaY + caja.ancho <= yBorde + 1e-6) {
            let x = cursor;
            while (x + caja.largo <= xBorde + 1e-6) {
                const xc = x + caja.largo / 2;
                const d = {x: xc, y: filaY + caja.ancho / 2, zMesa: m.z, xEntrada: Math.max(entrada, xc), altoLibre: altoLibre};
                if (alcanzable(caja, d, lim)) {
                    rep.filaY = filaY;
                    rep.fondo = Math.max(fondo, caja.ancho);
                    rep.cursor = x + caja.largo + m.hueco;
                    rep.altoMax = altoLibre;
                    rep.colocadas += 1;
                    return d;
                }
                x += PASO_BUSQUEDA;
            }
            if (fondo > 0) { filaY += fondo + m.hueco; fondo = 0; } else { filaY += PASO_BUSQUEDA; }
            cursor = m.x0 + m.hueco;
        }
        return null;
    }

    // Reparte una lista de cajas; se para en la primera que no cabe. {destinos, sinSitio: indice | null}
    function repartir(mesa, cajas, lim) {
        const rep = nuevoReparto(mesa);
        const destinos = [];
        for (let i = 0; i < cajas.length; i++) {
            const d = colocar(rep, cajas[i], lim);
            if (d === null) { return {destinos: destinos, sinSitio: i}; }
            destinos.push(d);
        }
        return {destinos: destinos, sinSitio: null};
    }

    // Cuantas cajas iguales a la de referencia caben (hasta MAX_CAJAS) y donde van.
    const memoria = {clave: null, valor: null};

    function estimarMesa(mesa, caja, lim) {
        const clave = JSON.stringify([mesa, caja, lim]);
        if (memoria.clave === clave) { return memoria.valor; }
        const r = repartir(mesa, new Array(MAX_CAJAS).fill(caja), lim);
        // zona a la que el robot no llega con una caja de referencia (celdas de 40 mm, en tiras por fila)
        const paso = 40;
        const tiras = [];
        for (let y = mesa.y0; y < mesa.y0 + mesa.ancho; y += paso) {
            let inicio = null;
            for (let x = mesa.x0; x <= mesa.x0 + mesa.largo + 1e-6; x += paso) {
                const dentro = x < mesa.x0 + mesa.largo - 1e-6;
                const xc = Math.min(x + paso / 2, mesa.x0 + mesa.largo);
                const d = {x: xc, y: Math.min(y + paso / 2, mesa.y0 + mesa.ancho), zMesa: mesa.z,
                    xEntrada: Math.max(mesa.x0 + mesa.largo + caja.largo / 2 + mesa.hueco, xc), altoLibre: caja.alto};
                const mal = dentro && !alcanzable(caja, d, lim);
                if (mal && inicio === null) { inicio = x; }
                if (!mal && inicio !== null) { tiras.push({x: inicio, y: y, w: x - inicio, h: Math.min(paso, mesa.y0 + mesa.ancho - y)}); inicio = null; }
            }
        }
        memoria.clave = clave;
        memoria.valor = {capacidad: r.destinos.length, destinos: r.destinos, inalcanzable: tiras};
        return memoria.valor;
    }

    function limitarCampoMesa(clave, valor) {
        const c = CAMPOS.concat(CAMPOS_PARAMETROS).filter(function (k) { return k.clave === clave; })[0];
        const v = Math.round(aNum(valor, 0) * 10) / 10;
        return c ? Math.max(c.min, Math.min(c.max, v)) : v;
    }

    // Dibujo de la mesa vista desde arriba: x a la derecha e y hacia arriba, con la base del robot de referencia.
    function geometriaMesa(mesa, destinos, caja, inalcanzable, ancho, alto) {
        const minX = Math.min(mesa.x0, -120);
        const maxX = Math.max(mesa.x0 + mesa.largo, 160);
        const minY = Math.min(mesa.y0, -120);
        const maxY = Math.max(mesa.y0 + mesa.ancho, 160);
        const margen = 14;
        const k = Math.min((ancho - 2 * margen) / (maxX - minX), (alto - 2 * margen) / (maxY - minY));
        const px = function (x) { return Math.round((margen + (x - minX) * k) * 10) / 10; };
        const py = function (y) { return Math.round((alto - margen - (y - minY) * k) * 10) / 10; };
        const r = function (v) { return Math.round(v * 10) / 10; };
        return {
            ancho: ancho, alto: alto,
            zona: {x: px(mesa.x0), y: py(mesa.y0 + mesa.ancho), w: r(mesa.largo * k), h: r(mesa.ancho * k)},
            base: {x: px(0), y: py(0)},
            huecos: destinos.map(function (d) {
                return {x: px(d.x - caja.largo / 2), y: py(d.y + caja.ancho / 2), w: r(caja.largo * k), h: r(caja.ancho * k),
                    cx: px(d.x), cy: py(d.y)};
            }),
            inalcanzable: inalcanzable.map(function (t) { return {x: px(t.x), y: py(t.y + t.h), w: r(t.w * k), h: r(t.h * k)}; })
        };
    }

    // ---- Textos de cada momento ----
    function textoFase(fase, e) {
        switch (fase) {
        case FASES.PARADO:
            return {titulo: 'Sin arrancar', detalle: 'RAPID no ha empezado la tanda. Arranca el programa con Play.', tono: 'parado'};
        case FASES.ESPERA_INICIAR:
            return {titulo: 'Listo para empezar', detalle: 'Ajusta la tanda y pulsa INICIAR TANDA.', tono: 'espera'};
        case FASES.A_SEGURA:
            return {titulo: 'Yendo a la posición segura', detalle: 'El robot se coloca sobre la cinta antes de la primera caja.', tono: 'activo'};
        case FASES.COLOCANDO:
            return {titulo: 'Poniendo la caja', detalle: 'Simulación: la caja aparece al principio de la cinta con su giro.', tono: 'activo'};
        case FASES.CINTA:
            return {titulo: 'Cinta en marcha', detalle: 'Simulación: la cinta lleva la caja hasta el sensor.', tono: 'activo'};
        case FASES.ESPERA_CAJA:
            if (e.confirmar) {
                return {
                    titulo: 'Esperando CAJA EN POSICIÓN',
                    detalle: e.modoSimulacion
                        ? 'El sensor ya ha visto llegar la caja. Pulsa CAJA EN POSICIÓN para arrancar el EGM.'
                        : 'Coloca la caja y pulsa CAJA EN POSICIÓN para arrancar el EGM.',
                    tono: 'espera'
                };
            }
            return {
                titulo: 'Esperando la señal CajaEnRecogida',
                detalle: 'Sin botón: RAPID arranca el EGM cuando se activa la señal (el sensor, o forzada a mano).',
                tono: 'espera'
            };
        case FASES.EGM_ABIERTO:
            return {titulo: 'EGM abierto: a por la caja', detalle: 'El PC dirige el robot: aproximación y agarre.', tono: 'activo'};
        case FASES.AGARRADA:
            return {titulo: 'Caja agarrada', detalle: 'La pinza ha cerrado: el PC la lleva a la mesa.', tono: 'activo'};
        case FASES.SOLTADA:
            return {titulo: 'Caja depositada', detalle: 'La pinza se ha abierto: el robot sale de la mesa.', tono: 'activo'};
        case FASES.CERRANDO_EGM:
            return {titulo: 'Cerrando el EGM', detalle: 'El robot queda quieto unos segundos y se cierra la sesión.', tono: 'activo'};
        case FASES.VUELTA:
            return {titulo: 'Volviendo a la posición segura', detalle: 'Movimiento por articulaciones hasta el punto de espera.', tono: 'activo'};
        case FASES.FIN:
            return {titulo: 'Tanda terminada', detalle: 'Todas las cajas hechas. Para otra tanda: relanza el PC y pulsa Play.', tono: 'ok'};
        case FASES.ERROR:
            return {titulo: 'Parada por error', detalle: 'RAPID se ha parado. Mira el aviso, corrígelo y reinicia el programa.', tono: 'error'};
        default:
            return {titulo: 'Fase ' + fase, detalle: 'Fase que esta versión de la app no conoce: ¿MOD_CajaPinza más nuevo?', tono: 'error'};
        }
    }

    // ---- Lo que hay que dibujar ----
    function calcularVista(est, ahoraMs) {
        const ahora = ahoraMs === undefined ? Date.now() : ahoraMs;
        const e = Object.assign(estadoInicial(), est);
        if (e.fase === FASES.ESPERA_INICIAR || e.fase === FASES.A_SEGURA) { e.cajaNum = 0; }   // la tanda aun no ha empezado
        const sim = e.modoSimulacion;
        const fase = e.fase;
        const parado = e.ejecucion === 'stopped';
        const enCaja = fase >= FASES.COLOCANDO && fase <= FASES.VUELTA;
        const total = limitarCajas(e.nCajas);
        const puedeActuar = e.rws && e.usarHmi && !parado;

        // Banner del momento
        let banner;
        if (!e.rws) {
            banner = {
                fase: null, tono: 'error', titulo: 'Sin conexión con RAPID',
                detalle: 'La app no consigue leer el controlador. Comprueba que el programa está cargado y que MOD_CajaPinza es la versión actual.'
            };
        } else {
            banner = Object.assign({fase: fase}, textoFase(fase, e));
            if (parado && fase !== FASES.FIN && fase !== FASES.ERROR && fase !== FASES.PARADO) {
                banner = {
                    fase: fase, tono: 'parado', titulo: 'Programa parado',
                    detalle: 'Estaba en: ' + banner.titulo + '. Pulsa Play para que siga.'
                };
            }
        }

        // Pasos de la caja en curso
        const lista = PASOS.filter(function (p) { return sim || !p.soloSim; });
        let activo = -1;
        lista.forEach(function (p, i) { if (p.fases.indexOf(fase) >= 0) { activo = i; } });
        const pasos = lista.map(function (p, i) {
            let estado = 'pendiente';
            if (fase === FASES.FIN) { estado = 'hecho'; } else if (activo >= 0) {
                estado = i < activo ? 'hecho' : (i === activo ? 'actual' : 'pendiente');
            }
            return {id: p.id, texto: p.texto, estado: estado};
        });

        // Progreso de la tanda
        const hechas = Math.min(Math.max(e.cajaNum, 0), total);
        const actual = enCaja ? Math.min(e.cajaNum + 1, total) : null;
        let caja;
        if (fase === FASES.FIN) {
            caja = {actual: null, hechas: hechas, total: total, texto: hechas + ' de ' + total + ' cajas hechas'};
        } else if (actual !== null) {
            caja = {actual: actual, hechas: hechas, total: total, texto: 'Caja ' + actual + ' de ' + total};
        } else {
            caja = {actual: null, hechas: hechas, total: total, texto: total + (total === 1 ? ' caja en la tanda' : ' cajas en la tanda')};
        }
        const fraccion = enCaja && activo >= 0 ? (activo + 1) / lista.length : 0;
        const progreso = fase === FASES.FIN ? 1 : Math.min(1, (hechas + fraccion) / total);

        // Mesa de deposito (estimacion con la caja de referencia; el PC reparte con la medida real de cada caja)
        const mesa = mesaDeEstado(e);
        const cajaRef = cajaDeReferencia(e);
        const limites = limitesDeEstado(e);
        const agarreRef = alturaAgarre(cajaRef, limites);
        const estimacion = estimarMesa(mesa, cajaRef, limites);
        const capacidad = estimacion.capacidad;
        const huecosVista = estimacion.destinos.map(function (d, i) {
            const n = i + 1;
            let estado = 'libre';
            if (n <= e.cajaNum) { estado = 'hecha'; } else if (enCaja && n === e.cajaNum + 1) { estado = 'actual'; } else if (n <= total) { estado = 'prevista'; }
            return {x: d.x, y: d.y, n: n, estado: estado};
        });
        const cabeTodo = capacidad >= total;
        const medidasRef = cajaRef.largo + ' × ' + cajaRef.ancho + ' × ' + cajaRef.alto + ' mm';
        const resumenMesa = 'Caben ' + capacidad + (capacidad === 1 ? ' caja' : ' cajas') + ' de ' + medidasRef
            + (capacidad >= MAX_CAJAS ? ' o más' : '') + '. '
            + (cabeTodo ? 'La tanda (' + total + ') cabe.' : 'La tanda (' + total + ') no cabe.')
            + (e.cajasVariables || !sim ? ' Con cajas más pequeñas que la de referencia caben más.' : '');
        // Con las cajas iguales a la de referencia (simulacion, tamanos fijos) la estimacion es exacta: se bloquea INICIAR.
        // Con tamanos variables o en real solo es una cota: el PC comprueba cada caja antes de moverla.
        const faltaSitio = sim && !e.cajasVariables && !cabeTodo;

        // Abortar: parar RAPID y volver al principio (Stop + PP a Main desde la app)
        const abortarOk = e.rws && !parado && fase >= FASES.ESPERA_INICIAR && fase <= FASES.VUELTA;

        // Botones
        let motivoIniciar = '';
        const iniciarListo = puedeActuar && fase === FASES.ESPERA_INICIAR;
        const iniciarOk = iniciarListo && !faltaSitio;
        if (!iniciarOk) {
            if (iniciarListo && faltaSitio) {
                motivoIniciar = 'En la mesa caben ' + capacidad + ' cajas y la tanda tiene ' + total
                    + ': agranda la zona, sube el límite del EGM, reduce el hueco o baja el número de cajas.';
            } else if (!e.rws) { motivoIniciar = 'Sin conexión con RAPID.'; }
            else if (!e.usarHmi) { motivoIniciar = 'RAPID tiene usarHmi = FALSE: no espera a la app.'; }
            else if (parado) { motivoIniciar = 'El programa está parado: pulsa Play.'; }
            else if (fase === FASES.PARADO) { motivoIniciar = 'Arranca el programa con Play.'; }
            else if (fase === FASES.FIN) { motivoIniciar = 'Tanda terminada: para otra, relanza el PC y pulsa Play.'; }
            else { motivoIniciar = 'La tanda ya está en marcha.'; }
        }
        let motivoCaja = '';
        const cajaOk = puedeActuar && fase === FASES.ESPERA_CAJA && e.confirmar;
        if (!cajaOk) {
            if (!e.rws) { motivoCaja = 'Sin conexión con RAPID.'; }
            else if (!e.usarHmi) { motivoCaja = 'RAPID tiene usarHmi = FALSE: no espera a la app.'; }
            else if (parado) { motivoCaja = 'El programa está parado: pulsa Play.'; }
            else if (fase === FASES.ESPERA_CAJA) { motivoCaja = 'Sin botón: RAPID espera la señal CajaEnRecogida.'; }
            else { motivoCaja = 'Solo vale cuando RAPID espera la caja.'; }
        }

        // Ajustes
        const editable = e.rws && (fase === FASES.PARADO || fase === FASES.ESPERA_INICIAR || fase === FASES.FIN);
        const giroFijo = e.indiceFijo >= 1 && e.indiceFijo <= N_GIROS;
        const opciones = [];
        for (let k = 1; k <= N_GIROS; k++) { opciones.push({indice: k, giro: giroDeIndice(k), texto: textoGiro(giroDeIndice(k))}); }
        const ajustes = {
            editable: editable,
            motivo: editable ? '' : (fase === FASES.ERROR ? 'Bloqueados hasta reiniciar el programa.' : 'Bloqueados mientras la tanda está en marcha.'),
            nCajas: {valor: total, min: 1, max: MAX_CAJAS, menosHabil: editable && total > 1, masHabil: editable && total < MAX_CAJAS,
                nota: 'La mesa admite ' + capacidad + (capacidad === 1 ? ' caja' : ' cajas') + ' como la de referencia (pestaña Mesa)'
                    + (!cabeTodo && !faltaSitio ? '; el PC comprobará las medidas reales.' : '.'),
                sobra: !cabeTodo},
            modo: sim ? 'sim' : 'real',
            giro: {
                editable: editable && sim,
                modo: giroFijo ? 'fijo' : 'azar',
                indice: giroFijo ? e.indiceFijo : 0,
                opciones: opciones,
                semilla: e.semilla,
                nota: sim ? '' : 'En real el giro lo da la cámara (el PC): aquí solo se muestra.'
            },
            confirmar: {
                valor: e.confirmar,
                editable: e.rws,
                nota: enCaja ? 'El cambio vale desde la siguiente caja.' : ''
            }
        };

        // Lista de giros de la tanda (simulacion: la misma cuenta que RAPID)
        let giros = [];
        if (sim) {
            giros = secuenciaGiros(total, e.semilla, e.indiceFijo).map(function (g, i) {
                const n = i + 1;
                let estado = 'pendiente';
                if (fase === FASES.FIN || n <= e.cajaNum) { estado = 'hecha'; } else if (enCaja && n === e.cajaNum + 1) { estado = 'actual'; }
                return {n: n, giro: g, texto: textoGiro(g), estado: estado};
            });
        }

        // Orientacion de la caja
        const giroRapid = e.giroCaja !== SIN_GIRO ? e.giroCaja : null;
        const giroPc = e.giroPc !== SIN_GIRO ? e.giroPc : null;
        const prevista = sim && giros.length > 0 && e.cajaNum < total ? giros[e.cajaNum].giro : null;
        let giro = null;
        let etiqueta = '';
        if (giroRapid !== null) {
            giro = giroRapid;
            etiqueta = fase === FASES.FIN ? 'Última caja' : (enCaja ? 'Caja en curso' : 'Última caja puesta por RAPID');
        } else if (giroPc !== null) {
            giro = giroPc;
            etiqueta = enCaja ? 'Caja en curso (la lee el PC)' : 'Última caja leída por el PC';
        } else if (prevista !== null) {
            giro = prevista;
            etiqueta = 'Primera caja (prevista)';
            if (e.cajaNum > 0) { etiqueta = 'Siguiente caja (prevista)'; }
        }
        const coincide = giroRapid !== null && giroPc !== null ? Math.abs(giroRapid - giroPc) < 0.05 : null;
        const orientacion = {
            giro: giro,
            texto: textoGiro(giro),
            etiqueta: etiqueta,
            rapid: giroRapid,
            pc: giroPc,
            medidas: e.caja,
            textoRapid: textoGiro(giroRapid),
            textoPc: textoGiro(giroPc),
            coincide: coincide,
            puntos: giro === null ? null : puntosCaja(giro, 50, 120, 120)
        };

        // Avisos
        const avisos = [];
        if (!e.rws) {
            avisos.push({nivel: 'error', texto: 'No se puede leer RAPID. Mira que el programa esté cargado y el módulo sea el actual.'});
        }
        if (e.faltan.length > 0) {
            avisos.push({nivel: 'error', texto: 'No encuentro en RAPID: ' + e.faltan.join(', ') + '. Carga el MOD_CajaPinza actual en T_ROB1 y T_COM.'});
        }
        if (e.rws && !e.usarHmi) {
            avisos.push({nivel: 'aviso', texto: 'usarHmi = FALSE en RAPID: el programa no espera a la app; esta pantalla solo muestra el estado.'});
        }
        if (e.rws && !parado && fase !== FASES.FIN && fase !== FASES.ERROR && !e.pcConectado) {
            avisos.push({nivel: 'aviso', texto: 'El PC no está conectado a RAPID (T_COM): arranca el PC antes de dar Play.'});
        }
        if (sim && !semillaValida(e.semilla)) {
            avisos.push({nivel: 'aviso', texto: 'La semilla debe ser un entero de 0 a ' + (SEMILLA_MOD - 1) + ': la lista de giros de la app puede no ser la real.'});
        }
        if (sim && enCaja && giroRapid !== null && e.cajaNum < total && giros.length > e.cajaNum && giros[e.cajaNum].giro !== giroRapid) {
            avisos.push({nivel: 'aviso', texto: 'La lista de giros de la app no coincide con la de RAPID (caja ' + (e.cajaNum + 1) + ').'});
        }
        if (coincide === false) {
            avisos.push({nivel: 'error', texto: 'El PC lee ' + textoGiro(giroPc) + ' y RAPID puso la caja a ' + textoGiro(giroRapid) + ': el PC no usa la caja.csv de esta tanda.'});
        }
        if (agarreRef.error !== undefined) {
            avisos.push({nivel: 'aviso', texto: 'Con los ajustes de agarre, la caja de referencia no se puede agarrar: ' + agarreRef.error + '. El PC rechaza las cajas así antes de moverse.'});
        }
        if (e.mensaje) {
            avisos.push({nivel: fase === FASES.ERROR ? 'error' : 'info', texto: 'RAPID: ' + e.mensaje});
        }

        // Cabecera y senales
        const chips = [
            {id: 'programa', texto: 'Programa', valor: parado ? 'Parado' : (e.ejecucion === 'running' ? 'En marcha' : '—'),
                tono: parado ? 'aviso' : (e.ejecucion === 'running' ? 'ok' : 'neutro')},
            {id: 'pc', texto: 'PC', valor: e.pcConectado ? 'Conectado' : 'Sin conexión', tono: e.pcConectado ? 'ok' : 'aviso'},
            {id: 'modo', texto: 'Modo', valor: sim ? 'SIMULACIÓN' : 'REAL', tono: sim ? 'neutro' : 'real'}
        ];
        const senales = [
            {id: 'sensor', texto: 'Sensor de la cinta', valor: e.senales.sensor},
            {id: 'cinta', texto: 'Cinta en marcha', valor: e.senales.cinta, soloSim: true},
            {id: 'pinzaCerrar', texto: 'Orden de cerrar la pinza', valor: e.senales.pinzaCerrar},
            {id: 'pinzaCerrada', texto: 'Pinza cerrada', valor: e.senales.pinzaCerrada}
        ].filter(function (s) { return sim || !s.soloSim; });

        return {
            rws: e.rws,
            banner: banner,
            pasos: pasos,
            caja: caja,
            progreso: progreso,
            botones: {
                iniciar: {habilitado: iniciarOk, motivo: motivoIniciar, avisoSinPc: !e.pcConectado},
                cajaEnPosicion: {habilitado: cajaOk, motivo: motivoCaja},
                abortar: {habilitado: abortarOk}
            },
            ajustes: ajustes,
            giros: giros,
            orientacion: orientacion,
            avisos: avisos,
            chips: chips,
            senales: senales,
            pinza: vistaPinza(e, ahora),
            parametros: vistaParametros(e, editable),
            mesa: {
                campos: CAMPOS.map(function (c) {
                    return {grupo: c.grupo, clave: c.clave, nombre: c.nombre, valor: e[c.clave], min: c.min, max: c.max, ayuda: c.ayuda};
                }),
                editable: editable,
                cajasVariables: e.cajasVariables,
                capacidad: capacidad,
                resumen: resumenMesa,
                huecos: huecosVista,
                caja: cajaRef,
                zona: {x0: mesa.x0, y0: mesa.y0, largo: mesa.largo, ancho: mesa.ancho},
                limites: 'Solo llegan las cajas a menos de ' + e.egmMaxPos + ' mm del punto de espera del EGM (600, −6,5, 543) y a menos de '
                    + e.alcanceMax + ' mm del eje del robot. La zona roja del dibujo es lo que queda fuera.',
                geometria: geometriaMesa(mesa, estimacion.destinos, cajaRef, estimacion.inalcanzable, 480, 420)
            },
            resumenTanda: total + (total === 1 ? ' caja' : ' cajas') + ' · ' + (sim ? 'simulación' : 'real')
                + (sim ? ' · giros ' + (giroFijo ? 'fijos a ' + textoGiro(giroDeIndice(e.indiceFijo)) : 'al azar (semilla ' + e.semilla + ')') : '')
                + ' · ' + (e.confirmar ? 'con botón CAJA EN POSICIÓN' : 'sin botón')
        };
    }

    return {
        TAREA: TAREA, MODULO: MODULO, MAX_CAJAS: MAX_CAJAS, N_GIROS: N_GIROS, GIRO_MIN: GIRO_MIN,
        GIRO_PASO: GIRO_PASO, SIN_GIRO: SIN_GIRO, SEMILLA_MOD: SEMILLA_MOD,
        FASES: FASES, VARIABLES: VARIABLES, SENALES: SENALES, PASOS: PASOS,
        aBool: aBool, aNum: aNum, aTexto: aTexto, convertir: convertir,
        estadoInicial: estadoInicial, aplicarVariable: aplicarVariable, normalizarEjecucion: normalizarEjecucion,
        giroDeIndice: giroDeIndice, siguienteSemilla: siguienteSemilla, semillaValida: semillaValida,
        indicesGiro: indicesGiro, secuenciaGiros: secuenciaGiros, nuevaSemilla: nuevaSemilla,
        limitarCajas: limitarCajas, ajustesDeModo: ajustesDeModo, textoGiro: textoGiro, puntosCaja: puntosCaja,
        textoFase: textoFase, calcularVista: calcularVista, ponerSenal: ponerSenal, vistaPinza: vistaPinza,
        MESA_SIM: MESA_SIM, CAMPOS: CAMPOS, CAMPOS_MESA: CAMPOS_MESA, CAJA_SIM: CAJA_SIM, PC: PC,
        mesaDeEstado: mesaDeEstado, cajaDeReferencia: cajaDeReferencia, puntosDestino: puntosDestino,
        puntoPermitido: puntoPermitido, nuevoReparto: nuevoReparto, colocar: colocar, repartir: repartir,
        estimarMesa: estimarMesa, limitarCampoMesa: limitarCampoMesa, geometriaMesa: geometriaMesa,
        PARAMETROS: PARAMETROS, CAMPOS_PARAMETROS: CAMPOS_PARAMETROS, textoConfirmacion: textoConfirmacion,
        limitesDeEstado: limitesDeEstado, alturaAgarre: alturaAgarre,
        AJUSTES: AJUSTES, valoresPorDefecto: valoresPorDefecto, cambiosHacia: cambiosHacia, aCsv: aCsv, desdeCsv: desdeCsv,
        nombreFicheroValido: nombreFicheroValido
    };
}));
