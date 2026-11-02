using System.Diagnostics;
using PuenteEgm;

// Uso: PuenteEgm [config.json]
// Arranca una sesión EGM (UDP) y un servidor de control (TCP) por cada entrada de "sesiones".

var ruta = args.Length > 0 ? args[0] : "config.json";
var cfg = ConfigPuente.Cargar(ruta);
var reloj = Stopwatch.StartNew();
using var registro = new Registro(cfg.RegistroCsv);

var sesiones = new List<(SesionEgm Sesion, ServidorControl Control)>();
foreach (var s in cfg.Sesiones)
{
    var sesion = new SesionEgm(s, registro, reloj);
    var control = new ServidorControl(sesion, s.IpControl, s.PuertoControl);
    sesion.Iniciar();
    control.Iniciar();
    sesiones.Add((sesion, control));
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
    if (++ciclo % 5 == 0)
    {
        foreach (var (sesion, _) in sesiones) Console.WriteLine(sesion.EstadoJson());
    }
}

foreach (var (sesion, control) in sesiones)
{
    control.Dispose();
    sesion.Dispose();
}
Console.WriteLine($"Registro: {registro.Descartadas} líneas descartadas por cola llena.");
