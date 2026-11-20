// Imprime en JSON las tablas de la app que tienen que coincidir con MOD_CajaPinza.mod y EIO.cfg
// (las lee tests/test_flexpendant.py) y algunas secuencias de giros para compararlas con otra
// implementacion del generador.
const path = require('node:path');
const L = require(path.join(__dirname, '..', '..', 'flexpendant', 'CajaPinza', 'logica.js'));

const casos = [[1234, 0, 12], [1234, 7, 5], [0, 0, 20], [8191, 0, 20], [77, 0, 100], [4096, 13, 8]];
const cubo = (n, l = 200, a = 200, h = 200) => new Array(n).fill({largo: l, ancho: a, alto: h});
const mixtas = [[150, 100, 120], [120, 80, 90], [100, 100, 150], [140, 60, 100], [130, 90, 110], [110, 70, 80], [150, 100, 120],
    [90, 90, 140], [60, 40, 60], [150, 120, 200]].map(([largo, ancho, alto]) => ({largo, ancho, alto}));
const sim = {mesaX0: -1120, mesaY0: 342, mesaLargo: 1200, mesaAncho: 1000, mesaZ: 320, mesaHueco: 40};
const casosMesa = [
    Object.assign({}, sim, {egm: 1000, alcance: 790, cajas: cubo(10)}),
    Object.assign({}, sim, {egm: 1500, alcance: 790, cajas: cubo(10)}),
    Object.assign({}, sim, {egm: 1500, alcance: 790, cajas: mixtas}),
    Object.assign({}, sim, {egm: 1000, alcance: 790, cajas: mixtas}),
    // la zona por defecto (mesa_marron colocada en -700, 350, 500 mm)
    {mesaX0: -900, mesaY0: 150, mesaLargo: 1200, mesaAncho: 1000, mesaZ: 320, mesaHueco: 40, egm: 1500, alcance: 790, cajas: cubo(10)},
    {mesaX0: -900, mesaY0: 150, mesaLargo: 1200, mesaAncho: 1000, mesaZ: 320, mesaHueco: 40, egm: 1000, alcance: 790, cajas: mixtas},
    {mesaX0: -500, mesaY0: 300, mesaLargo: 580, mesaAncho: 500, mesaZ: 320, mesaHueco: 20, egm: 1500, alcance: 790, cajas: mixtas},
    {mesaX0: -300, mesaY0: 342, mesaLargo: 380, mesaAncho: 560, mesaZ: 400, mesaHueco: 30, egm: 1200, alcance: 760, cajas: mixtas},
    {mesaX0: -200, mesaY0: 342, mesaLargo: 300, mesaAncho: 400, mesaZ: 560, mesaHueco: 30, egm: 1500, alcance: 790, cajas: cubo(4)},
    {mesaX0: -400, mesaY0: 200, mesaLargo: 600, mesaAncho: 600, mesaZ: 100, mesaHueco: 10, egm: 1500, alcance: 790, cajas: mixtas}
];
const repartos = casosMesa.map((c) => {
    const r = L.repartir({x0: c.mesaX0, y0: c.mesaY0, largo: c.mesaLargo, ancho: c.mesaAncho, z: c.mesaZ, hueco: c.mesaHueco},
        c.cajas, {egmMaxPos: c.egm, alcanceMax: c.alcance});
    return Object.assign({}, c, {destinos: r.destinos.map((d) => [d.x, d.y]), sinSitio: r.sinSitio});
});
console.log(JSON.stringify({
    repartos, MESA_SIM: L.MESA_SIM, CAJA_SIM: L.CAJA_SIM, PC: L.PC,
    TAREA: L.TAREA, MODULO: L.MODULO, MAX_CAJAS: L.MAX_CAJAS, N_GIROS: L.N_GIROS, GIRO_MIN: L.GIRO_MIN,
    GIRO_PASO: L.GIRO_PASO, SIN_GIRO: L.SIN_GIRO, SEMILLA_MOD: L.SEMILLA_MOD,
    FASES: L.FASES, VARIABLES: L.VARIABLES, SENALES: L.SENALES,
    secuencias: casos.map(([semilla, indiceFijo, n]) => ({semilla, indiceFijo, n, giros: L.secuenciaGiros(n, semilla, indiceFijo)}))
}));
