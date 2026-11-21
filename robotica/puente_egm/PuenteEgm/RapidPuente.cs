using System.Collections.Concurrent;
using System.Net;
using System.Net.Sockets;
using System.Text;

namespace PuenteEgm;

/// <summary>Relé del socket de RAPID. La tarea T_COM del controlador (cliente TCP) se conecta aquí, y el programa de la celda habla con
/// ella a través de los comandos rapid_* del servidor de control, sin abrir ningún socket propio con el controlador.
///
/// El protocolo con RAPID es el de siempre: sin separadores ni concurrencia (una orden, una respuesta). Cada Receive devuelve un
/// mensaje completo. El relé no interpreta nada: lo que manda el PC llega tal cual a RAPID y lo que contesta RAPID vuelve tal cual.
/// Si RAPID se reconecta (cada Play abre un socket nuevo), la conexión nueva sustituye a la anterior.</summary>
public sealed class RapidPuente : IDisposable
{
    /// <summary>Las cadenas de RAPID tienen como mucho 80 caracteres.</summary>
    public const int MaxMensaje = 80;

    private const int TamBuffer = 256;
    private const int RodajaMs = 500;

    private readonly string _nombre;
    private readonly TcpListener _listener;
    private readonly object _bloqueo = new();
    private readonly ConcurrentQueue<string> _avisos = new();
    private TcpClient? _cliente;
    private string _origen = "";
    private volatile bool _parar;
    private Thread? _hilo;

    public RapidPuente(string nombre, string ip, int puerto)
    {
        _nombre = nombre;
        _listener = new TcpListener(IPAddress.Parse(ip), puerto);
    }

    public void Iniciar()
    {
        _listener.Start();
        _hilo = new Thread(Aceptar) { IsBackground = true, Name = "rapid-" + _nombre };
        _hilo.Start();
    }

    private void Aceptar()
    {
        while (!_parar)
        {
            TcpClient nuevo;
            try
            {
                nuevo = _listener.AcceptTcpClient();
            }
            catch (Exception ex) when (ex is SocketException or ObjectDisposedException)
            {
                break;
            }
            nuevo.NoDelay = true;
            string origen = nuevo.Client.RemoteEndPoint?.ToString() ?? "?";
            lock (_bloqueo)
            {
                _cliente?.Dispose();
                _cliente = nuevo;
                _origen = origen;
            }
            _avisos.Enqueue($"[{_nombre}] RAPID conectado al socket desde {origen}");
        }
    }

    private TcpClient? Actual()
    {
        lock (_bloqueo) return _cliente;
    }

    /// <summary>Si RAPID tiene el socket abierto (un socket cerrado por el otro lado se detecta aquí) y desde dónde.</summary>
    public (bool Conectado, string Origen) Estado()
    {
        TcpClient? c;
        string origen;
        lock (_bloqueo)
        {
            c = _cliente;
            origen = _origen;
        }
        if (c is null) return (false, "");
        try
        {
            var s = c.Client;
            bool cerrado = s.Poll(0, SelectMode.SelectRead) && s.Available == 0;
            return (!cerrado, origen);
        }
        catch (Exception ex) when (ex is SocketException or ObjectDisposedException)
        {
            return (false, origen);
        }
    }

    public (bool Ok, string Error) Enviar(string mensaje)
    {
        var c = Actual();
        if (c is null) return (false, "RAPID no está conectado al socket");
        // Escribir en un socket que el otro lado ya cerró no falla la primera vez (el sistema lo acepta): se mira antes.
        if (!Estado().Conectado) return (false, "RAPID ha cerrado el socket");
        try
        {
            var bytes = Encoding.UTF8.GetBytes(mensaje);
            c.GetStream().Write(bytes, 0, bytes.Length);
            return (true, "");
        }
        catch (Exception ex) when (ex is IOException or SocketException or ObjectDisposedException or InvalidOperationException)
        {
            return (false, "RAPID ha cerrado el socket");
        }
    }

    /// <summary>Espera un mensaje de RAPID. timeoutS &lt; 0: sin límite. Códigos: "timeout", "cerrado", "desconectado".</summary>
    public (string? Mensaje, string Codigo, string Error) Recibir(double timeoutS)
    {
        var c = Actual();
        if (c is null) return (null, "desconectado", "RAPID no está conectado al socket");
        var limite = timeoutS < 0 ? DateTime.MaxValue : DateTime.UtcNow.AddSeconds(timeoutS);
        var buffer = new byte[TamBuffer];
        try
        {
            while (true)
            {
                if (_parar || !ReferenceEquals(Actual(), c))
                    return (null, "cerrado", "la conexión con RAPID se ha sustituido o cerrado");
                var restanteMs = limite == DateTime.MaxValue ? RodajaMs : (limite - DateTime.UtcNow).TotalMilliseconds;
                if (restanteMs <= 0)
                    return (null, "timeout", $"RAPID no ha contestado en {timeoutS:g} s");
                if (!c.Client.Poll((int)Math.Min(RodajaMs, restanteMs) * 1000, SelectMode.SelectRead)) continue;
                int n = c.Client.Receive(buffer);
                if (n == 0) return (null, "cerrado", "RAPID ha cerrado el socket");
                return (Encoding.UTF8.GetString(buffer, 0, n).Trim(), "", "");
            }
        }
        catch (Exception ex) when (ex is IOException or SocketException or ObjectDisposedException or InvalidOperationException)
        {
            return (null, "cerrado", "RAPID ha cerrado el socket");
        }
    }

    public IEnumerable<string> DrenarAvisos()
    {
        while (_avisos.TryDequeue(out var a)) yield return a;
    }

    public void Dispose()
    {
        _parar = true;
        _listener.Stop();
        lock (_bloqueo)
        {
            _cliente?.Dispose();
            _cliente = null;
        }
        _hilo?.Join(1000);
    }
}
