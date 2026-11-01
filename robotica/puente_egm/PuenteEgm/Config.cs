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

    /// <summary>"desplazamiento": planned es una corrección respecto a la pose de partida.
    /// "absoluta": planned es la posición objetivo. Confirmar con el controlador virtual (D30).</summary>
    public string Semantica { get; set; } = "desplazamiento";

    /// <summary>Segundos sin objetivo nuevo antes de retener la posición real.</summary>
    public double WatchdogS { get; set; } = 0.1;

    public LimitesConfig Limites { get; set; } = new();

    public EspacioConfig EspacioMm { get; set; } = new();
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
