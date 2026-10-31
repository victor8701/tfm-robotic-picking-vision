// Página «Pedido en lenguaje natural» del panel (31 de octubre de 2026). Carga el vocabulario y los datos del inventario de prueba (static/pedido/*.json) y usa `pedido_nl_nucleo.js`,
// el mismo algoritmo que `pedido_nl.py` (se prueba que dan lo mismo). Las miniaturas se piden a GitHub (raw), como las fotos de la galería.
(function () {
  'use strict';
  const raiz = document.getElementById('pedido-app');
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const EJEMPLOS = ['prepara un pedido de sudaderas estilo geek de cuero', 'dame 5 sudaderas negras estilo geek', 'chaquetas de cuero negras', '10 vaqueros urbanos', 'camisas de lino old money', 'algo bonito'];
  const PASO = 12;
  let nl = null, VOCAB = null, DATOS = null;
  let estado = null;   // { texto, p, relajar, mostrar, quitados, prop }

  const lista = (xs, conj) => (xs.length === 1 ? xs[0] : xs.slice(0, -1).join(', ') + ' ' + conj + ' ' + xs[xs.length - 1]);
  const tipoDeCat = (cat) => VOCAB.tipos.find((t) => t.categorias.includes(cat));
  const srcImagen = (i) => raiz.dataset.imagenes + DATOS.rutas[i];

  function ejecutar(texto) {
    estado = { texto, p: nl.parsear(texto), relajar: false, mostrar: PASO, quitados: [], prop: [] };
    $('aprobado').classList.add('pd-oculto');
    pintar();
  }

  function pintarEntendido(p) {
    const v = (xs, f) => (xs.length ? lista(xs.map(f), 'o') : null);
    const campos = [
      ['Cantidad', p.cantidad === null ? null : String(p.cantidad)],
      ['Prenda', p.tipos.length ? lista(p.tipos.map((k) => nl.tipo(k).singular), 'o') : null],
      ['Material', v(p.materiales, (k) => nl.material(k).es)],
      ['Color', v(p.colores, (k) => nl.color(k).es)],
      ['Estilo', v(p.estilos, (k) => nl.estilo(k).es)],
    ];
    $('entendido').innerHTML = campos.map(([k, val]) => '<div><dt>' + k + '</dt><dd class="' + (val ? '' : 'pd-vacio') + '">' + (val ? esc(val) : '—') + '</dd></div>').join('');
    const no = $('no-entendido');
    const partes = [];
    if (p.no_entendido.length) partes.push('No he reconocido: ' + p.no_entendido.join(', ') + '. Lo he ignorado; si importa, reescríbelo con otras palabras.');
    if (estado.quitados.length) partes.push('Has quitado: ' + estado.quitados.join(', ') + '.');
    no.classList.toggle('pd-oculto', !partes.length);
    no.textContent = partes.join(' ');
  }

  function pintar() {
    const p = estado.p;
    const r = nl.buscar(p);
    const prop = nl.propuesta(r, estado.relajar);
    estado.prop = prop;
    const enPedido = new Set(prop.map((f) => f.id));
    $('entendido-sec').classList.remove('pd-oculto');
    pintarEntendido(p);

    const duros = p.materiales.length + p.colores.length > 0;
    let nivel = 'ok', etiqueta = 'Hay resultados';
    if (!p.tipos.length) { nivel = 'no'; etiqueta = 'No he entendido la prenda'; }
    else if (duros && r.n_cumplen === 0) { nivel = r.n_quiza ? 'duda' : 'no'; etiqueta = r.n_quiza ? 'Falta decidir' : 'No veo ninguna'; }
    if (estado.relajar && prop.length && duros && r.n_cumplen === 0) { nivel = 'duda'; etiqueta = 'Más cercanas, por decisión tuya'; }
    const resp = $('respuesta');
    resp.className = 'pd-tarjeta pd-respuesta ' + nivel;
    $('estado-txt').textContent = etiqueta;
    $('respuesta-texto').innerHTML = r.texto.replace(/\.\s+(?=[A-ZÁÉÍÓÚ«])/g, '.\u0001').split('\u0001').map((f) => '<p>' + esc(f) + '</p>').join('');
    const acc = [];
    if (p.tipos.length && r.total && duros && r.n_cumplen === 0 && !estado.relajar) acc.push(['relajar', 'Preparar las ' + Math.min(p.cantidad || VOCAB.umbrales.mostrar, r.total) + ' más cercanas igualmente']);
    if (p.materiales.length && duros && r.n_cumplen === 0) acc.push(['sin-material', 'Quitar el material (' + p.materiales.map((k) => nl.material(k).es).join(', ') + ')']);
    if (p.colores.length && duros && r.n_cumplen === 0) acc.push(['sin-color', 'Quitar el color (' + p.colores.map((k) => nl.color(k).es).join(', ') + ')']);
    $('acciones').innerHTML = acc.map(([id, t]) => '<button type="button" data-accion="' + id + '">' + esc(t) + '</button>').join('');

    const sec = $('prendas-sec');
    sec.classList.toggle('pd-oculto', !r.filas.length);
    if (r.filas.length) {
      const nombres = lista(p.tipos.map((k) => nl.tipo(k).plural), 'y');
      const n = Math.min(estado.mostrar, r.filas.length);
      $('t-prendas').textContent = 'Mostrando ' + n + ' de ' + r.total + ' ' + nombres + ', de más a menos cercanas';
      $('prendas').innerHTML = r.filas.slice(0, n).map((f) => {
        const t = tipoDeCat(f.cat);
        const crit = [];
        if (f.mat !== null) crit.push('<span class="pd-crit ' + f.v_mat + '">' + (f.v_mat === 'si' ? '✓' : f.v_mat === 'quiza' ? '?' : '✗') + ' Material ' + nl.pct(f.mat) + ' %</span>');
        if (f.col !== null) crit.push('<span class="pd-crit ' + f.v_col + '">' + (f.v_col === 'si' ? '✓' : f.v_col === 'quiza' ? '?' : '✗') + ' Color ' + nl.pct(f.col) + ' %</span>');
        if (f.est !== null) crit.push('<span class="pd-crit ' + (f.v_est === 'alta' ? 'alta' : '') + '">Estilo: afinidad ' + f.v_est + '</span>');
        const num = f.id.slice(f.id.lastIndexOf('_') + 1);
        const nombre = t ? t.singular : f.cat;
        return '<li class="pd-prenda' + (enPedido.has(f.id) ? ' pd-en-pedido' : '') + '"><img src="' + esc(srcImagen(f.i)) + '" width="72" height="96" loading="lazy" alt="' + esc(nombre) + ' ' + num + '">'
          + '<div class="pd-cuerpo"><div class="pd-nombre">' + esc(nombre) + ' <span class="pd-id">#' + num + '</span></div>'
          + (crit.length ? '<div class="pd-criterios">' + crit.join('') + '</div>' : '') + (enPedido.has(f.id) ? '<div class="pd-marca">En el pedido</div>' : '') + '</div></li>';
      }).join('');
      $('mas').classList.toggle('pd-oculto', n >= r.filas.length);
    }

    $('aprobar-sec').classList.toggle('pd-oculto', !p.tipos.length);
    $('aprobar-texto').textContent = prop.length ? 'Pedido propuesto: ' + prop.length + ' unidades (las marcadas «En el pedido»). Una persona tiene que aprobarlo antes de pasar al picking.'
      : 'Nada que aprobar todavía: ninguna prenda cumple el pedido con seguridad. Decide arriba si preparas las más cercanas o cambias el pedido.';
    $('aprobar').disabled = !prop.length;

    const det = $('estilo-datos');
    det.classList.toggle('pd-oculto', !p.estilos.length);
    if (p.estilos.length) {
      const e = DATOS.estilos_info[p.estilos[0]];
      $('estilo-titulo').textContent = 'Qué dicen tus datos del estilo ' + e.nombre;
      $('estilo-cuerpo').innerHTML = '<p>Descripción medida que se usa para ordenar (' + e.fotos + ' fotos de referencia aprobadas por ti): <i>' + esc(e.descripcion_clip) + '</i></p>'
        + '<ul>' + e.prendas.map((x) => '<li>Prenda que lo distingue: ' + esc(x.valor) + ' (' + nl.pct(x.estilo) + ' % de sus prendas frente a ' + nl.pct(x.resto) + ' % del resto)</li>').join('')
        + e.modificadores.map((x) => '<li>Rasgo que lo distingue: ' + esc(x.valor) + ' (' + nl.pct(x.estilo) + ' % frente a ' + nl.pct(x.resto) + ' %)</li>').join('') + '</ul>';
    }
  }

  function enlazar() {
    $('form').addEventListener('submit', (ev) => { ev.preventDefault(); ejecutar($('texto').value); });
    $('ejemplos').innerHTML = EJEMPLOS.map((t) => '<button type="button" class="pd-ejemplo">' + esc(t) + '</button>').join('');
    $('ejemplos').addEventListener('click', (ev) => { const b = ev.target.closest('button.pd-ejemplo'); if (b) { $('texto').value = b.textContent; ejecutar(b.textContent); } });
    $('acciones').addEventListener('click', (ev) => {
      const b = ev.target.closest('button[data-accion]');
      if (!b || !estado) return;
      if (b.dataset.accion === 'relajar') estado.relajar = true;
      if (b.dataset.accion === 'sin-material') { estado.quitados.push('el material'); estado.p = Object.assign({}, estado.p, { materiales: [] }); }
      if (b.dataset.accion === 'sin-color') { estado.quitados.push('el color'); estado.p = Object.assign({}, estado.p, { colores: [] }); }
      pintar();
    });
    $('mas').addEventListener('click', () => { estado.mostrar += PASO; pintar(); });
    $('aprobar').addEventListener('click', () => {
      const p = estado.p;
      const pedido = { estado: 'aprobado (simulado)', pedido: estado.texto, entendido: { cantidad: p.cantidad, tipos: p.tipos, materiales: p.materiales, colores: p.colores, estilos: p.estilos, quitado_por_el_operario: estado.quitados },
        unidades: estado.prop.length, prendas: estado.prop.map((f) => f.id), fecha: new Date().toISOString() };
      const caja = $('aprobado');
      caja.classList.remove('pd-oculto');
      caja.innerHTML = '<p style="margin-top:10px"><b>Pedido aprobado (simulado).</b> Aquí empezaría el reparto entre los dos brazos; esta demo no se conecta a ningún robot ni ERP.</p><pre>' + esc(JSON.stringify(pedido, null, 2)) + '</pre>';
    });
  }

  const ok = (r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); };
  Promise.all([fetch(raiz.dataset.vocab).then(ok), fetch(raiz.dataset.datos).then(ok)]).then(([v, d]) => {
    VOCAB = v; DATOS = d; nl = PedidoNL.crear(v, d);
    $('cargando').classList.add('pd-oculto');
    $('contenido').classList.remove('pd-oculto');
    enlazar();
    ejecutar($('texto').value);
  }).catch((e) => {
    $('cargando').classList.add('pd-oculto');
    const err = $('error-carga');
    err.classList.remove('pd-oculto');
    err.textContent = 'No se pudieron cargar los datos del inventario (' + e.message + '). Recarga la página; si sigue igual, el despliegue está a medias.';
  });
})();
