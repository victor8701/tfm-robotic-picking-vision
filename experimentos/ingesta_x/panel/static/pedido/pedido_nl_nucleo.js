// Núcleo del «pedido en lenguaje natural» (31 de octubre de 2026): el MISMO algoritmo que pedido_nl.py, sin dependencias, para que la página funcione sin servidor.
// `test_pedido_nl.py` ejecuta este fichero con node y comprueba que entiende, ordena y redacta igual que el de Python. Si se cambia uno, hay que cambiar el otro.
(function (raiz) {
  'use strict';

  function crear(vocab, datos) {
    const U = vocab.umbrales;
    const normalizar = (t) => t.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
    const palabras = new Set();
    vocab.frases.forEach((f) => f[0].forEach((t) => palabras.add(t)));
    const parasitas = new Set(vocab.parasitas);
    const pct = (x) => Math.floor(x * 100 + 0.5);
    const lista = (xs, conj) => (xs.length === 1 ? xs[0] : xs.slice(0, -1).join(', ') + ' ' + conj + ' ' + xs[xs.length - 1]);
    const lema = (t) => {
      if (palabras.has(t)) return t;
      if (t.endsWith('es') && palabras.has(t.slice(0, -2))) return t.slice(0, -2);
      if (t.endsWith('s') && palabras.has(t.slice(0, -1))) return t.slice(0, -1);
      return t;
    };
    const igual = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
    const tipo = (k) => vocab.tipos.find((t) => t.clave === k);
    const material = (k) => vocab.materiales.find((m) => m.clave === k);
    const color = (k) => vocab.colores.find((c) => c.clave === k);
    const estilo = (k) => vocab.estilos.find((e) => e.clave === k);

    function parsear(texto) {
      const orig = normalizar(texto).split(/\s+/).filter(Boolean);
      const toks = orig.map(lema);
      const p = { cantidad: null, tipos: [], materiales: [], colores: [], estilos: [], no_entendido: [] };
      let i = 0;
      while (i < toks.length) {
        let hallada = false;
        for (const [frase, clase, clave] of vocab.frases) {
          if (igual(toks.slice(i, i + frase.length), frase)) {
            if (!p[clase].includes(clave)) p[clase].push(clave);
            i += frase.length;
            hallada = true;
            break;
          }
        }
        if (hallada) continue;
        const t = toks[i];
        const n = /^\d{1,4}$/.test(t) ? parseInt(t, 10) : (Object.prototype.hasOwnProperty.call(vocab.numeros, t) ? vocab.numeros[t] : null);
        if (n !== null) {
          if (p.cantidad === null) p.cantidad = n;
        } else if (!parasitas.has(t)) {
          p.no_entendido.push(orig[i]);
        }
        i += 1;
      }
      for (const [generico, grupo] of [['pantalon_generico', vocab.grupos_tipo.pantalon_generico], ['zapatilla', vocab.grupos_tipo.zapatilla]]) {
        if (p.tipos.includes(generico)) {
          p.tipos = p.tipos.filter((x) => x !== generico);
          if (!grupo.some((x) => p.tipos.includes(x))) p.tipos = p.tipos.concat(grupo);
        }
      }
      return p;
    }

    function notaEstiloMaterial(p) {
      if (!p.materiales.length || !p.estilos.length) return null;
      const avisos = [];
      for (const m of p.materiales) {
        const mat = material(m);
        const info = datos.estilos_info;
        const enPedido = p.estilos.filter((e) => info[e].modificadores.some((x) => x.valor === mat.valor));
        if (enPedido.length) continue;
        const enOtros = [];
        for (const e of Object.keys(info)) for (const x of info[e].modificadores) if (x.valor === mat.valor) enOtros.push([x.estilo, x.resto, e]);
        enOtros.sort((a, b) => (b[0] - a[0]) || (b[1] - a[1]) || (a[2] < b[2] ? 1 : a[2] > b[2] ? -1 : 0));
        const est = lista(p.estilos.map((e) => info[e].nombre), 'y');
        let frase = 'Ojo: en tus datos, «' + mat.es + '» no está entre los rasgos que distinguen al estilo ' + est;
        if (enOtros.length) {
          const [a, b, e] = enOtros[0];
          frase += '; sí distingue al estilo ' + info[e].nombre + ' (' + pct(a) + ' % de sus prendas frente a ' + pct(b) + ' % del resto)';
        }
        avisos.push(frase + '.');
      }
      return avisos.length ? avisos.join(' ') : null;
    }

    function redactar(p, r) {
      if (!p.tipos.length) {
        return 'No he entendido qué prenda quieres. Prueba con «sudaderas», «camisas», «vaqueros», «chaquetas»…' + (p.no_entendido.length ? ' (No he reconocido: ' + lista(p.no_entendido, 'y') + '.)' : '');
      }
      const nombres = lista(p.tipos.map((k) => tipo(k).plural), 'y');
      const duros = [];
      if (p.materiales.length) duros.push('de ' + lista(p.materiales.map((k) => material(k).es), 'o'));
      if (p.colores.length) duros.push('de color ' + lista(p.colores.map((k) => color(k).es), 'o'));
      const req = duros.join(' ');
      const est = p.estilos.length ? lista(p.estilos.map((k) => estilo(k).es), 'o') : null;
      const total = r.total, k0 = r.n_cumplen, k1 = r.n_quiza, pedido = p.cantidad;
      const frases = [];
      if (!duros.length) {
        const n = Math.min(pedido || U.mostrar, total);
        frases.push('Hay ' + total + ' ' + nombres + ' en el inventario.' + (est ? ' Propongo ' + n + ' unidades, las de mayor afinidad con el estilo ' + est + '.' : ' Propongo ' + n + ' unidades.'));
        if (pedido && pedido > total) frases.push('Pides ' + pedido + ', pero solo hay ' + total + '.');
      } else if (k0 >= 1) {
        const n = Math.min(pedido || U.mostrar, k0);
        frases.push('Hay ' + k0 + ' ' + nombres + ' ' + req + ' con seguridad entre las ' + total + ' del inventario.'
          + (est ? ' Propongo ' + n + ' unidades, las de mayor afinidad con el estilo ' + est + '.' : ' Propongo ' + n + ' unidades.'));
        if (pedido && pedido > k0) frases.push('Pides ' + pedido + ', pero solo ' + k0 + ' lo cumplen con seguridad.');
      } else if (k1 >= 1) {
        frases.push('No veo ' + nombres + ' ' + req + ' con seguridad entre las ' + total + ' del inventario. Hay ' + k1 + ' que podrían serlo (dudosas). '
          + 'No propongo ninguna hasta que decidas si las preparo igualmente o cambias el pedido.');
      } else if (p.materiales.length && !p.colores.length) {
        frases.push(r.con_vlm
          ? 'No veo ' + nombres + ' ' + req + ' entre las ' + total + ' del inventario: el modelo grande no etiqueta ninguna con ese tejido y la más probable para CLIP llega solo al ' + pct(r.max_material || 0) + ' %.'
          : 'No veo ' + nombres + ' ' + req + ' entre las ' + total + ' del inventario: la más probable llega solo al ' + pct(r.max_material || 0) + ' % en el material pedido.');
      } else {
        frases.push('No veo ' + nombres + ' ' + req + ' entre las ' + total + ' del inventario. No propongo ninguna hasta que decidas si preparo las más cercanas o cambias el pedido.');
      }
      if (p.materiales.length) frases.push(r.con_vlm ? vocab.aviso_material_vlm : vocab.aviso_material);
      const nota = notaEstiloMaterial(p);
      if (nota) frases.push(nota);
      if (p.no_entendido.length) frases.push('No he reconocido: ' + lista(p.no_entendido, 'y') + '; lo he ignorado.');
      return frases.join(' ');
    }

    // Material pedido: manda el tejido que le pone el modelo grande; CLIP solo decide si no hay etiqueta, y desempata en un caso («no se distingue» o el modelo dice otro tejido pero CLIP está seguro).
    function veredictoMaterial(clipP, tejido, valores) {
      const porClip = clipP >= U.si ? 'si' : clipP >= U.quiza ? 'quiza' : 'no';
      if (tejido === null || tejido === undefined) return porClip;
      if (valores.has(tejido)) return 'si';
      if (tejido === 'no se distingue') return porClip !== 'no' ? 'quiza' : 'no';
      return clipP >= U.si ? 'quiza' : 'no';
    }

    function buscar(p) {
      const cats = new Set();
      p.tipos.forEach((t) => tipo(t).categorias.forEach((c) => cats.add(c)));
      const cat = datos.cats;
      const cands = [];
      for (let i = 0; i < cat.length; i++) if (cats.has(cat[i])) cands.push(i);
      const imat = p.materiales.map((m) => datos.materiales.indexOf(m));
      const icol = p.colores.map((c) => datos.colores.indexOf(c));
      const iest = p.estilos.map((e) => datos.estilos.indexOf(e));
      const valoresMat = new Set(p.materiales.map((k) => material(k).valor));
      const tej = datos.vlm_tejido || null, pat = datos.vlm_estampado || null, forma = datos.vlm_forma || null;
      const maxDe = (fila, idx) => Math.max.apply(null, idx.map((k) => fila[k]));
      const afin = {};
      if (iest.length) cands.forEach((i) => { afin[i] = maxDe(datos.est[i], iest); });
      const porCat = {};
      if (iest.length) for (let j = 0; j < cat.length; j++) if (cats.has(cat[j])) (porCat[cat[j]] = porCat[cat[j]] || []).push(maxDe(datos.est[j], iest));
      const v = (x) => (x === null ? null : x >= U.si ? 'si' : x >= U.quiza ? 'quiza' : 'no');
      const filas = cands.map((i) => {
        const mClip = imat.length ? maxDe(datos.mat[i], imat) : null;
        const c = icol.length ? maxDe(datos.col[i], icol) : null;
        const tVlm = tej ? tej[i] : null;
        const vmat = imat.length ? veredictoMaterial(mClip, tVlm, valoresMat) : null;
        const m = (imat.length && valoresMat.has(tVlm)) ? 1.0 : mClip;   // para ordenar: si el modelo grande lo confirma, vale como seguro
        let e = null;
        if (iest.length) {
          const otros = porCat[cat[i]];
          e = otros.length > 1 ? otros.filter((a) => a < afin[i]).length / (otros.length - 1) : 1.0;
        }
        const vm = vmat, vc = v(c);
        const duros = [vm, vc].filter((x) => x !== null);
        const nivel = duros.every((x) => x === 'si') ? 0 : duros.every((x) => x !== 'no') ? 1 : 2;
        let duro = 0;
        if (m !== null) duro = duro + m;
        if (c !== null) duro = duro + c;
        const puntos = nivel === 0 ? (e !== null ? e : 0.0) + 0.01 * duro : 3 * duro + (e !== null ? 0.5 * e : 0.0);
        return { i, id: datos.ids[i], cat: cat[i], mat: mClip, tejido: imat.length ? tVlm : null, vlm: tej ? { tejido: tej[i], estampado: pat ? pat[i] : null, forma: forma ? forma[i] : null } : null, col: c, est: e, v_mat: vm, v_col: vc, v_est: e === null ? null : e >= U.alta ? 'alta' : e >= U.media ? 'media' : 'baja', nivel, puntos };
      });
      filas.sort((a, b) => (a.nivel - b.nivel) || (b.puntos - a.puntos) || (a.i - b.i));
      const r = { pedido: p, total: filas.length, n_cumplen: filas.filter((f) => f.nivel === 0).length, n_quiza: filas.filter((f) => f.nivel === 1).length, filas };
      const ms = filas.filter((f) => f.mat !== null).map((f) => f.mat);
      r.max_material = ms.length ? Math.max.apply(null, ms) : null;
      r.con_vlm = !!tej;
      r.texto = redactar(p, r);
      return r;
    }

    function propuesta(r, relajar) {
      const buenas = r.filas.filter((f) => f.nivel === 0);
      const candidatas = buenas.length ? buenas : (relajar ? r.filas : []);
      return candidatas.slice(0, Math.min(r.pedido.cantidad || U.mostrar, candidatas.length));
    }

    return { normalizar, parsear, buscar, redactar, propuesta, pct, tipo, material, color, estilo };
  }

  const api = { crear };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else raiz.PedidoNL = api;
})(typeof window !== 'undefined' ? window : globalThis);
