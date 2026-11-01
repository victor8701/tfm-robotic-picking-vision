using System.Collections.Concurrent;
using System.Text;

namespace PuenteEgm;

/// <summary>Registro por ciclo sin E/S en el bucle de 250 Hz: las líneas se encolan y un hilo las escribe.
/// Si la cola llega a su límite se descartan líneas y se cuenta cuántas.</summary>
public sealed class Registro : IDisposable
{
    public const string Cabecera =
        "t_s,sesion,seqno,estado,real_x,real_y,real_z,ref_x,ref_y,ref_z,desviacion_mm";

    private const int LimiteCola = 200_000;

    private readonly ConcurrentQueue<string> _cola = new();
    private readonly string? _ruta;
    private readonly Thread? _hilo;
    private volatile bool _fin;
    private long _descartadas;

    public Registro(string? ruta)
    {
        _ruta = ruta;
        if (ruta is null) return;
        var carpeta = Path.GetDirectoryName(Path.GetFullPath(ruta));
        if (!string.IsNullOrEmpty(carpeta)) Directory.CreateDirectory(carpeta);
        _hilo = new Thread(Bucle) { IsBackground = true, Name = "registro-csv" };
        _hilo.Start();
    }

    public long Descartadas => Interlocked.Read(ref _descartadas);

    public void Escribir(string linea)
    {
        if (_ruta is null) return;
        if (_cola.Count >= LimiteCola)
        {
            Interlocked.Increment(ref _descartadas);
            return;
        }
        _cola.Enqueue(linea);
    }

    private void Bucle()
    {
        using var w = new StreamWriter(_ruta!, append: false, new UTF8Encoding(false)) { NewLine = "\n" };
        w.WriteLine(Cabecera);
        while (!_fin || !_cola.IsEmpty)
        {
            while (_cola.TryDequeue(out var linea)) w.WriteLine(linea);
            w.Flush();
            Thread.Sleep(200);
        }
    }

    public void Dispose()
    {
        _fin = true;
        _hilo?.Join(3000);
    }
}
