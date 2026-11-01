using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;

namespace PuenteEgm;

/// <summary>Servidor TCP de control: una línea JSON por comando, una línea JSON por respuesta.
///
/// Comandos:
///   {"cmd":"objetivo","t":[x,y,z],"q":[w,x,y,z]}   consigna cartesiana (mm, cuaternión)
///   {"cmd":"estado"}                               estado, referencia, real, desviación
///   {"cmd":"parar"}  {"cmd":"arrancar"}  {"cmd":"reset"}
/// </summary>
public sealed class ServidorControl : IDisposable
{
    private const int MaxLinea = 4096;

    private readonly SesionEgm _sesion;
    private readonly TcpListener _listener;
    private volatile bool _parar;
    private Thread? _hilo;

    public ServidorControl(SesionEgm sesion, string ip, int puerto)
    {
        _sesion = sesion;
        _listener = new TcpListener(IPAddress.Parse(ip), puerto);
    }

    public void Iniciar()
    {
        _listener.Start();
        _hilo = new Thread(Aceptar) { IsBackground = true, Name = "control-" + _sesion.Nombre };
        _hilo.Start();
    }

    private void Aceptar()
    {
        while (!_parar)
        {
            TcpClient cliente;
            try
            {
                cliente = _listener.AcceptTcpClient();
            }
            catch (Exception ex) when (ex is SocketException or ObjectDisposedException)
            {
                break;
            }
            var hilo = new Thread(() => Atender(cliente)) { IsBackground = true };
            hilo.Start();
        }
    }

    private void Atender(TcpClient cliente)
    {
        using (cliente)
        {
            var stream = cliente.GetStream();
            using var lector = new StreamReader(stream, Encoding.UTF8);
            using var escritor = new StreamWriter(stream, new UTF8Encoding(false)) { AutoFlush = true, NewLine = "\n" };
            while (!_parar)
            {
                string? linea;
                try
                {
                    linea = lector.ReadLine();
                }
                catch (IOException)
                {
                    break;
                }
                if (linea is null) break;
                try
                {
                    escritor.WriteLine(Procesar(linea));
                }
                catch (IOException)
                {
                    break;
                }
            }
        }
    }

    /// <summary>Interpreta una línea y devuelve la respuesta JSON. Nunca lanza excepciones.</summary>
    internal string Procesar(string linea)
    {
        if (linea.Length > MaxLinea) return Error("línea demasiado larga");
        try
        {
            using var doc = JsonDocument.Parse(linea);
            var raiz = doc.RootElement;
            var cmd = raiz.GetProperty("cmd").GetString();
            switch (cmd)
            {
                case "objetivo":
                    return _sesion.Objetivo(LeerVector3(raiz, "t"), LeerCuaternion(raiz, "q"));
                case "estado":
                    return _sesion.EstadoJson();
                case "parar":
                    return RespuestaOperacion(_sesion.Parar());
                case "arrancar":
                    return RespuestaOperacion(_sesion.Arrancar());
                case "reset":
                    return RespuestaOperacion(_sesion.Rearmar());
                default:
                    return Error($"comando desconocido: {cmd}");
            }
        }
        catch (Exception ex) when (ex is JsonException or KeyNotFoundException or InvalidOperationException
                                   or FormatException or ArgumentException)
        {
            return Error(ex.Message);
        }
    }

    private static V3 LeerVector3(JsonElement raiz, string nombre)
    {
        var a = LeerNumeros(raiz, nombre, 3);
        return new V3(a[0], a[1], a[2]);
    }

    private static Q LeerCuaternion(JsonElement raiz, string nombre)
    {
        var a = LeerNumeros(raiz, nombre, 4);
        return new Q(a[0], a[1], a[2], a[3]);
    }

    private static double[] LeerNumeros(JsonElement raiz, string nombre, int n)
    {
        var el = raiz.GetProperty(nombre);
        if (el.ValueKind != JsonValueKind.Array || el.GetArrayLength() != n)
            throw new ArgumentException($"'{nombre}' debe ser un array de {n} números");
        var r = new double[n];
        int i = 0;
        foreach (var x in el.EnumerateArray()) r[i++] = x.GetDouble();
        if (r.Any(v => !double.IsFinite(v)))
            throw new ArgumentException($"'{nombre}' contiene valores no finitos");
        return r;
    }

    private static string RespuestaOperacion((bool Ok, string Error) r) =>
        r.Ok ? "{\"ok\":true}" : Error(r.Error);

    private static string Error(string mensaje) => JsonSerializer.Serialize(new { ok = false, error = mensaje });

    public void Dispose()
    {
        _parar = true;
        _listener.Stop();
        _hilo?.Join(1000);
    }
}
