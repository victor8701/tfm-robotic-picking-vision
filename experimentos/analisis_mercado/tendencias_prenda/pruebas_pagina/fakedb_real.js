// Base de datos FALSA que imita el contrato real de `db` de los Artifacts (para probar las páginas con Playwright sin publicar):
//  - los `data()` que entrega onSnapshot vienen CONGELADOS (Object.freeze profundo): una página que los modifique falla igual que en claude.ai (así se encontró el fallo de la ronda 1 de «Revisar valoraciones», 10-oct-2026);
//  - eco local inmediato (hasPendingWrites) y confirmación tras la latencia (window.__LAT, 250 ms);
//  - window.__STALE = true: tras resolver cada set llega primero un aviso ATRASADO (la versión anterior) y 150 ms después el correcto;
//  - window.__SEED = {docId: cuerpo}: contenido inicial (para probar «recargar»). El estado queda en window.__docs.
// Uso: page.add_init_script(open("fakedb_real.js").read()) antes de goto.
// db falsa que imita el contrato real: data() congelado, eco local inmediato (hasPendingWrites), confirmación tras la latencia
(function(){
  var server = window.__SEED ? JSON.parse(JSON.stringify(window.__SEED)) : {}, subs = [], pending = {};
  function deepFreeze(o){ if(o && typeof o==='object' && !Object.isFrozen(o)){ Object.freeze(o); Object.getOwnPropertyNames(o).forEach(function(k){ deepFreeze(o[k]) }) } return o }
  function view(over){ var m = {}; Object.keys(server).forEach(function(k){ m[k]=server[k] }); Object.keys(pending).forEach(function(k){ m[k]=pending[k] }); if(over){ Object.keys(over).forEach(function(k){ if(over[k]===null) delete m[k]; else m[k]=over[k] }) } return m }
  function snapshot(over){
    var m = view(over), hp = Object.keys(pending).length > 0;
    var docs = Object.keys(m).sort().map(function(k){ var body = deepFreeze(JSON.parse(JSON.stringify(m[k]))); return Object.freeze({id:k, exists:true, data:function(){return body}, metadata:{fromCache:false, hasPendingWrites: !!pending[k]}}) });
    return Object.freeze({docs: docs, size: docs.length, empty: !docs.length, docChanges:function(){return []}, metadata:{fromCache:false, hasPendingWrites: hp}});
  }
  function deliver(s){ subs.forEach(function(cb){ try{ cb(s) }catch(e){ console.error('callback', e.message) } }) }
  function notify(){ deliver(snapshot()) }
  var LAT = window.__LAT || 250;
  var db = {
    collection: function(name){ return { onSnapshot: function(cb){ subs.push(cb); setTimeout(function(){ cb(snapshot()) }, 30); return function(){} } } },
    doc: function(path){ var id = path.split('/').pop(); return {
      set: function(d){
        var body = JSON.parse(JSON.stringify(d));
        pending[id] = body; notify();                       // eco local inmediato
        return new Promise(function(res){ setTimeout(function(){ var prev = server[id]; server[id] = body; delete pending[id]; window.__docs = server; res();
          if (window.__STALE) { var o = {}; o[id] = (prev === undefined ? null : prev); deliver(snapshot(o)); setTimeout(notify, 150) } else setTimeout(notify, 0) }, LAT) });
      },
      get: function(){ return Promise.resolve({exists: !!server[id], data: function(){return server[id]}}) } } }
  };
  window.__docs = server;
  window.claude = { use: function(n){ return Promise.resolve(n === 'db' ? db : null) } };
})();
