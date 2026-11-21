using System.Text.Json;

namespace PuenteEgm;

/// <summary>Configuración de una sesión EGM (un controlador = un puerto UDP y un puerto de control).</summary>
public sealed class ConfigSesion
{
    public string Nombre { get; set; } = "sesion";

    /// <summary>Puerto UDP en el que el controlador envía EgmRobot y espera EgmSensor (6511 en el proyecto previo).</summary>
    public int PuertoEgm { get; set; } = 6511;

    /// <summary>Si se indica, solo se aceptan datagramas de esta IP (el controlador). Recomendado en producción.</summary>
    public string? IpControlador { get; set; }

    /// <summary>Dirección del servidor TCP de control. 127.0.0.1 para pruebas; en WSL2 hace falta la IP de Windows.</summary>
    public string IpControl { get; set; } = "127.0.0.1";

    public int PuertoControl { get; set; } = 7001;

    /// <summary>"absoluta": planned es la pose objetivo en el marco base. Es lo que hace el controlador del
    /// proyecto (resuelto el 15-nov-2026, ver docs/configuracion.md, D30).
    /// "desplazamiento": planned sería una corrección respecto a la pose de partida; con este controlador el
    /// robot iría al origen de la base, no usar.</summary>
    public string Semantica { get; set; } = "absoluta";

    /// <summary>Segundos sin objetivo nuevo antes de retener la posición real.</summary>
    public double WatchdogS { get; set; } = 0.1;

    /// <summary>Si se indica, el puente hace de servidor del socket de RAPID (T_COM se conecta a ip:puerto) y el programa de la celda habla con
    /// RAPID por los comandos rapid_* del control. Sin esta sección, el socket lo abre el PC (celda.ciclo con socket_rapid.via = "pc").</summary>
    public ConfigRapid? Rapid { get; set; }

    public LimitesConfig Limites { get; set; } = new();

    public EspacioConfig EspacioMm { get; set; } = new();
}

public sealed class ConfigRapid
{
    /// <summary>127.0.0.1 con el controlador virtual (corre en este mismo PC); con el real, la IP de este PC que ve el controlador (o 0.0.0.0).</summary>
    public string Ip { get; set; } = "127.0.0.1";

    /// <summary>Puerto al que se conecta T_COM (puertoPC en RAPID).</summary>
    public int Puerto { get; set; } = 5010;
}

public sealed class LimitesConfig
{
    public double PasoMm { get; set; } = 0.5;
    public double GiroRad { get; set; } = 0.0025;
    public double DesviacionMm { get; set; } = 20.0;
    public double DesviacionRad { get; set; } = 0.1;
}

public sealed class EspacioConfig
{
    public double[] X { get; set; } = { -600, 600 };
    public double[] Y { get; set; } = { -600, 600 };
    public double[] Z { get; set; } = { 0, 800 };
}

public sealed class ConfigPuente
{
    /// <summary>Ruta del CSV de registro por ciclo, o null para no registrar.</summary>
    public string? RegistroCsv { get; set; } = "registros/puente.csv";

    public List<ConfigSesion> Sesiones { get; set; } = new();

    /// <summary>Claves en snake_case como en el resto del proyecto (paso_mm, puerto_egm...).</summary>
    public static readonly JsonSerializerOptions Opciones = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
    };

    public static ConfigPuente Cargar(string ruta)
    {
        var cfg = JsonSerializer.Deserialize<ConfigPuente>(File.ReadAllText(ruta), Opciones)
                  ?? throw new InvalidOperationException("configuración vacía");
        foreach (var s in cfg.Sesiones)
        {
            if (s.Semantica is not ("desplazamiento" or "absoluta"))
                throw new InvalidOperationException($"semántica desconocida en '{s.Nombre}': {s.Semantica}");
            if (s.EspacioMm.X.Length != 2 || s.EspacioMm.Y.Length != 2 || s.EspacioMm.Z.Length != 2)
                throw new InvalidOperationException($"el espacio de '{s.Nombre}' debe tener [min, max] por eje");
        }
        return cfg;
    }
}
