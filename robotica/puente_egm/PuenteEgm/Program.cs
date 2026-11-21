using System.Diagnostics;
using PuenteEgm;

// Uso: PuenteEgm [config.json] [--prueba]
// Arranca una sesión EGM (UDP) y un servidor de control (TCP) por cada entrada de "sesiones".
// --prueba: cada sesión genera sola la secuencia de prueba (diagonales xy, xz, yz en bucle).

var prueba = Array.IndexOf(args, "--prueba") >= 0;
var ruta = Array.Find(args, a => !a.StartsWith("--")) ?? "config.json";
var cfg = ConfigPuente.Cargar(ruta);
var reloj = Stopwatch.StartNew();
using var registro = new Registro(cfg.RegistroCsv);

var sesiones = new List<(SesionEgm Sesion, ServidorControl Control)>();
var reles = new List<RapidPuente>();
foreach (var s in cfg.Sesiones)
{
    var sesion = new SesionEgm(s, registro, reloj);
    RapidPuente? rele = s.Rapid is null ? null : new RapidPuente(s.Nombre, s.Rapid.Ip, s.Rapid.Puerto);
    var control = new ServidorControl(sesion, s.IpControl, s.PuertoControl, rele);
    sesion.Iniciar();
    control.Iniciar();
    if (rele is not null)
    {
        rele.Iniciar();
        reles.Add(rele);
        Console.WriteLine($"[{s.Nombre}] socket de RAPID TCP {s.Rapid!.Ip}:{s.Rapid.Puerto} (T_COM se conecta aquí; el PC habla con RAPID por el control)");
    }
    sesiones.Add((sesion, control));
    if (prueba)
    {
        sesion.ActivarPrueba(paso: 1.0, pasos: 50);
        Console.WriteLine($"[{s.Nombre}] prueba interna en bucle: diagonales xy, xz, yz (ida y vuelta, 50 pasos de 1 mm).");
    }
    Console.WriteLine($"[{s.Nombre}] EGM UDP:{s.PuertoEgm}  control TCP {s.IpControl}:{s.PuertoControl}  semantica={s.Semantica}");
}

using var salir = new ManualResetEventSlim(false);
Console.CancelKeyPress += (_, e) =>
{
    e.Cancel = true;
    salir.Set();
};

Console.WriteLine("Puente en marcha. Ctrl+C para parar.");
// Cada segundo se imprimen los avisos nuevos; cada 5 segundos, el estado de cada sesión.
int ciclo = 0;
while (!salir.Wait(TimeSpan.FromSeconds(1)))
{
    foreach (var (sesion, _) in sesiones)
    {
        foreach (var aviso in sesion.DrenarAvisos()) Console.WriteLine(aviso);
    }
    foreach (var rele in reles)
    {
        foreach (var aviso in rele.DrenarAvisos()) Console.WriteLine(aviso);
    }
    if (++ciclo % 5 == 0)
    {
        foreach (var (sesion, _) in sesiones) Console.WriteLine(sesion.EstadoJson());
    }
}

foreach (var rele in reles) rele.Dispose();
foreach (var (sesion, control) in sesiones)
{
    control.Dispose();
    sesion.Dispose();
}
Console.WriteLine($"Registro: {registro.Descartadas} líneas descartadas por cola llena.");
