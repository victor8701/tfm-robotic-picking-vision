using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using Abb.Egm;
using Google.Protobuf;

namespace PuenteEgm;

/// <summary>Estados de la sesión. Esperando/Activo/Retener son normales; Fallo y Parada exigen rearme explícito.</summary>
public enum EstadoSesion
{
    Esperando,
    Activo,
    Retener,
    Fallo,
    Parada,
}

/// <summary>Una sesión EGM = un controlador. Por cada EgmRobot recibido (cada 4 ms) responde con un EgmSensor.
///
/// Nunca hay E/S de disco ni consola en el bucle: el registro se encola (ver Registro).
/// Todo el estado compartido se toca bajo _lock; el bucle UDP y el servidor de control comparten el mismo lock.</summary>
public sealed class SesionEgm : IDisposable
{
    private readonly ConfigSesion _cfg;
    private readonly Registro _registro;
    private readonly Stopwatch _reloj;
    private readonly EspacioTrabajo _espacio;
    private readonly Limites _limites;
    private readonly Vigilante _vigilante;
    private readonly object _lock = new();

    private UdpClient? _udp;
    private Thread? _hilo;
    private volatile bool _parar;
    private readonly HashSet<string> _ipsVistas = new();   // solo lo usa el hilo EGM
    private readonly ConcurrentQueue<string> _avisos = new();  // el hilo EGM no escribe en consola

    // Estado compartido (solo con _lock).
    private EstadoSesion _estado = EstadoSesion.Esperando;
    private string _codigo = "";
    private Pose? _objetivo;
    private Pose? _referencia;
    private Pose? _referencia0;
    private Pose _real;
    private uint _seqno;
    private long _ciclos;
    private long _errores;
    private double _ultimoMensajeS = -1;
    private double _intervaloMaxS;

    public SesionEgm(ConfigSesion cfg, Registro registro, Stopwatch reloj)
    {
        _cfg = cfg;
        _registro = registro;
        _reloj = reloj;
        _espacio = new EspacioTrabajo(
            cfg.EspacioMm.X[0], cfg.EspacioMm.X[1],
            cfg.EspacioMm.Y[0], cfg.EspacioMm.Y[1],
            cfg.EspacioMm.Z[0], cfg.EspacioMm.Z[1]);
        _limites = new Limites(cfg.Limites.PasoMm, cfg.Limites.GiroRad, cfg.Limites.DesviacionMm, cfg.Limites.DesviacionRad);
        _vigilante = new Vigilante(cfg.WatchdogS);
    }

    public string Nombre => _cfg.Nombre;

    /// <summary>Avisos pendientes (IPs de origen nuevas). Los imprime el programa principal, fuera del bucle EGM.</summary>
    public IEnumerable<string> DrenarAvisos()
    {
        while (_avisos.TryDequeue(out var aviso)) yield return aviso;
    }

    /// <summary>Calienta protobuf antes del primer ciclo: el primer uso compila código (JIT) y tarda decenas de ms.</summary>
    private static void Calentar()
    {
        var punto = new EgmPose
        {
            Pos = new EgmCartesian { X = 0, Y = 0, Z = 0 },
            Orient = new EgmQuaternion { U0 = 1, U1 = 0, U2 = 0, U3 = 0 },
        };
        var robot = new EgmRobot
        {
            Header = new EgmHeader { Seqno = 1, Tm = 1 },
            FeedBack = new EgmFeedBack { Cartesian = punto },
        };
        _ = EgmRobot.Parser.ParseFrom(robot.ToByteArray());
        _ = new EgmSensor
        {
            Header = new EgmHeader { Seqno = 1, Tm = 1 },
            Planned = new EgmPlanned { Cartesian = punto },
        }.ToByteArray();
    }

    public void Iniciar()
    {
        Calentar();
        _udp = new UdpClient(_cfg.PuertoEgm);
        _hilo = new Thread(Bucle) { IsBackground = true, Name = "egm-" + _cfg.Nombre, Priority = ThreadPriority.Highest };
        _hilo.Start();
    }

    public void Detener()
    {
        _parar = true;
        _udp?.Close();
        _hilo?.Join(2000);
    }

    public void Dispose() => Detener();

    // ----- Bucle EGM (un hilo, bloqueante, sin E/S en el camino crítico) -----

    private void Bucle()
    {
        var remoto = new IPEndPoint(IPAddress.Any, 0);
        while (!_parar)
        {
            byte[] datos;
            try
            {
                datos = _udp!.Receive(ref remoto);
            }
            catch (Exception ex) when (ex is SocketException or ObjectDisposedException)
            {
                if (_parar) break;
                lock (_lock) _errores++;
                continue;
            }

            // Aviso una sola vez por IP de origen: así se ve qué poner en ip_controlador.
            // Solo se escribe al ver una IP nueva, nunca en cada ciclo.
            string ip = remoto.Address.ToString();
            bool aceptado = _cfg.IpControlador is null || ip == _cfg.IpControlador;
            if (_ipsVistas.Add(ip))
            {
                _avisos.Enqueue($"[{_cfg.Nombre}] primer datagrama de {ip}:{remoto.Port} " +
                                $"({(aceptado ? "aceptado" : "ignorado")}; ip_controlador = {_cfg.IpControlador ?? "sin filtro"})");
            }
            if (!aceptado)
            {
                continue;  // datagrama de otra máquina: se ignora
            }

            double ahora = _reloj.Elapsed.TotalSeconds;
            if (!TryLeerRobot(datos, out Pose real))
            {
                lock (_lock) _errores++;
                continue;
            }

            byte[] respuesta;
            lock (_lock)
            {
                respuesta = CicloLocked(real, ahora);
            }

            try
            {
                _udp!.Send(respuesta, respuesta.Length, remoto);
            }
            catch (Exception ex) when (ex is SocketException or ObjectDisposedException)
            {
                if (_parar) break;
                lock (_lock) _errores++;
            }
        }
    }

    private static bool TryLeerRobot(byte[] datos, out Pose real)
    {
        real = default;
        try
        {
            var msg = EgmRobot.Parser.ParseFrom(datos);
            var cart = msg.FeedBack?.Cartesian;
            if (cart?.Pos is null || cart.Orient is null) return false;
            var t = new V3(cart.Pos.X, cart.Pos.Y, cart.Pos.Z);
            var q = new Q(cart.Orient.U0, cart.Orient.U1, cart.Orient.U2, cart.Orient.U3);
            if (!t.EsFinito || !q.EsFinito) return false;
            real = new Pose(t, q.Normalizado());
            return true;
        }
        catch (InvalidProtocolBufferException)
        {
            return false;
        }
        catch (ArgumentException)
        {
            return false;  // cuaternión nulo
        }
    }

    /// <summary>Un ciclo: decide la consigna segura y devuelve el EgmSensor a enviar. Llamar con _lock.</summary>
    private byte[] CicloLocked(Pose real, double ahora)
    {
        _ciclos++;
        if (_ultimoMensajeS >= 0) _intervaloMaxS = Math.Max(_intervaloMaxS, ahora - _ultimoMensajeS);
        _ultimoMensajeS = ahora;
        _real = real;
        _referencia0 ??= real;
        _referencia ??= real;

        Pose nueva;
        if (_estado is EstadoSesion.Parada or EstadoSesion.Fallo)
        {
            nueva = Seguridad.Retener(real);
        }
        else if (_objetivo is null || _vigilante.Vencido(ahora))
        {
            if (_estado == EstadoSesion.Activo) _estado = EstadoSesion.Retener;
            nueva = Seguridad.Retener(real);
        }
        else
        {
            if (_estado is EstadoSesion.Esperando or EstadoSesion.Retener) _estado = EstadoSesion.Activo;
            var (referencia, resultado) = Seguridad.Filtrar(_referencia.Value, _objetivo.Value, real, _espacio, _limites);
            if (resultado == Resultado.Fallo)
            {
                _estado = EstadoSesion.Fallo;
                _codigo = "desviacion_excesiva";
            }
            nueva = referencia;
        }
        _referencia = nueva;

        return ConstruirSensor(nueva, ahora);
    }

    private byte[] ConstruirSensor(Pose referencia, double ahora)
    {
        V3 posPlan;
        Q qPlan;
        if (_cfg.Semantica == "absoluta")
        {
            posPlan = referencia.T;
            qPlan = referencia.R.Normalizado();
        }
        else
        {
            var r0 = _referencia0!.Value;
            posPlan = referencia.T - r0.T;
            qPlan = (referencia.R.Normalizado() * r0.R.Normalizado().Conjugado).Normalizado();
        }

        _seqno++;
        var sensor = new EgmSensor
        {
            Header = new EgmHeader
            {
                Seqno = _seqno,
                Tm = (uint)(ahora * 1000.0),
                Mtype = EgmHeader.Types.MessageType.MsgtypeCorrection,
            },
            Planned = new EgmPlanned
            {
                Cartesian = new EgmPose
                {
                    Pos = new EgmCartesian { X = posPlan.X, Y = posPlan.Y, Z = posPlan.Z },
                    Orient = new EgmQuaternion { U0 = qPlan.W, U1 = qPlan.X, U2 = qPlan.Y, U3 = qPlan.Z },
                },
            },
        };

        _registro.Escribir(string.Format(CultureInfo.InvariantCulture,
            "{0:F4},{1},{2},{3},{4:F3},{5:F3},{6:F3},{7:F3},{8:F3},{9:F3},{10:F3}",
            ahora, _cfg.Nombre, _seqno, _estado.ToString().ToLowerInvariant(),
            _real.T.X, _real.T.Y, _real.T.Z,
            referencia.T.X, referencia.T.Y, referencia.T.Z,
            (referencia.T - _real.T).Norma));

        return sensor.ToByteArray();
    }

    // ----- Órdenes del servidor de control (llamadas desde ServidorControl) -----

    /// <summary>Nuevo objetivo cartesiano (mm, cuaternión). Reinicia el watchdog.</summary>
    public string Objetivo(V3 t, Q q)
    {
        lock (_lock)
        {
            _objetivo = new Pose(t, q.Normalizado());
            _vigilante.Marcar(_reloj.Elapsed.TotalSeconds);
        }
        return "{\"ok\":true}";
    }

    public (bool Ok, string Error) Parar()
    {
        lock (_lock)
        {
            _estado = EstadoSesion.Parada;
            _codigo = "parada_por_comando";
        }
        return (true, "");
    }

    public (bool Ok, string Error) Arrancar()
    {
        lock (_lock)
        {
            if (_estado != EstadoSesion.Parada) return (false, "la sesión no está parada");
            _estado = EstadoSesion.Esperando;
            _codigo = "";
            return (true, "");
        }
    }

    /// <summary>Rearma tras un fallo. Descarta el objetivo anterior: hay que mandar uno nuevo.</summary>
    public (bool Ok, string Error) Rearmar()
    {
        lock (_lock)
        {
            if (_estado != EstadoSesion.Fallo) return (false, "no hay fallo que rearmar");
            _estado = EstadoSesion.Esperando;
            _codigo = "";
            _objetivo = null;
            return (true, "");
        }
    }

    public string EstadoJson()
    {
        lock (_lock)
        {
            var referencia = _referencia ?? _real;
            return JsonSerializer.Serialize(new
            {
                ok = true,
                sesion = _cfg.Nombre,
                estado = _estado.ToString().ToLowerInvariant(),
                codigo = _codigo,
                semantica = _cfg.Semantica,
                ciclos = _ciclos,
                errores = _errores,
                intervalo_max_ms = _intervaloMaxS * 1000.0,
                desviacion_mm = (referencia.T - _real.T).Norma,
                real = Serializar(_real),
                referencia = Serializar(referencia),
            });
        }
    }

    private static object Serializar(Pose p) => new
    {
        t = new[] { p.T.X, p.T.Y, p.T.Z },
        q = new[] { p.R.W, p.R.X, p.R.Y, p.R.Z },
    };
}
