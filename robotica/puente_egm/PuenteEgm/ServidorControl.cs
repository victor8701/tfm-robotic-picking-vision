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
///
/// Si la sesión tiene socket de RAPID (sesion.rapid), el relé responde además a:
///   {"cmd":"rapid_estado"}                          {"ok":true,"conectado":bool,"origen":"ip:puerto"}
///   {"cmd":"rapid_enviar","msg":"cerrar"}           manda el texto a RAPID (máx. 80 caracteres)
///   {"cmd":"rapid_recibir","timeout_s":5}           espera el mensaje de RAPID; sin timeout_s, sin límite. Fallo con
///                                                   "codigo": "timeout" | "cerrado" | "desconectado"
/// rapid_recibir bloquea la conexión hasta que RAPID contesta: se usa una conexión de control aparte de la del movimiento.
/// </summary>
public sealed class ServidorControl : IDisposable
{
    private const int MaxLinea = 4096;

    private readonly SesionEgm _sesion;
    private readonly RapidPuente? _rapid;
    private readonly TcpListener _listener;
    private volatile bool _parar;
    private Thread? _hilo;

    public ServidorControl(SesionEgm sesion, string ip, int puerto, RapidPuente? rapid = null)
    {
        _sesion = sesion;
        _rapid = rapid;
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
                case "rapid_estado":
                    return RapidEstado();
                case "rapid_enviar":
                    return RapidEnviar(raiz.GetProperty("msg").GetString() ?? "");
                case "rapid_recibir":
                    return RapidRecibir(raiz.TryGetProperty("timeout_s", out var t) && t.ValueKind == JsonValueKind.Number ? t.GetDouble() : -1.0);
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

    private const string SinRapid = "el puente no tiene socket de RAPID: falta la sección 'rapid' en la sesión de la configuración";

    private string RapidEstado()
    {
        if (_rapid is null) return Error(SinRapid);
        var (conectado, origen) = _rapid.Estado();
        return JsonSerializer.Serialize(new { ok = true, conectado, origen });
    }

    private string RapidEnviar(string mensaje)
    {
        if (_rapid is null) return Error(SinRapid);
        if (mensaje.Length > RapidPuente.MaxMensaje)
            return Error($"mensaje de {mensaje.Length} caracteres: las cadenas de RAPID admiten {RapidPuente.MaxMensaje}");
        var (ok, error) = _rapid.Enviar(mensaje);
        return ok ? "{\"ok\":true}" : Error(error);
    }

    private string RapidRecibir(double timeoutS)
    {
        if (_rapid is null) return Error(SinRapid);
        var (mensaje, codigo, error) = _rapid.Recibir(timeoutS);
        return mensaje is not null
            ? JsonSerializer.Serialize(new { ok = true, msg = mensaje })
            : JsonSerializer.Serialize(new { ok = false, codigo, error });
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
