namespace PuenteEgm;

/// <summary>Resultado de filtrar una consigna en un ciclo.</summary>
public enum Resultado
{
    Ok,
    Limitado,
    Fallo,
}

/// <summary>Caja de trabajo en el marco base del robot (mm).</summary>
public sealed record EspacioTrabajo(double XMin, double XMax, double YMin, double YMax, double ZMin, double ZMax)
{
    public V3 Ajustar(V3 p) => new(
        Math.Clamp(p.X, XMin, XMax),
        Math.Clamp(p.Y, YMin, YMax),
        Math.Clamp(p.Z, ZMin, ZMax));
}

/// <summary>Límites por ciclo de 4 ms y desviación máxima respecto al robot real.</summary>
public sealed record Limites(double PasoMm, double GiroRad, double DesviacionMm, double DesviacionRad);

/// <summary>Port de nucleo/seguridad.py. Misma regla: la referencia nunca se aleja del robot real más de la desviación.</summary>
public static class Seguridad
{
    /// <summary>Consigna de retención: la posición real del robot.</summary>
    public static Pose Retener(Pose real) => real;

    public static (Pose Referencia, Resultado Resultado) Filtrar(
        Pose refPrevia, Pose objetivo, Pose real, EspacioTrabajo espacio, Limites limites)
    {
        bool limitado = false;

        V3 tObj = espacio.Ajustar(objetivo.T);
        if (tObj != objetivo.T) limitado = true;

        V3 paso = tObj - refPrevia.T;
        double n = paso.Norma;
        if (n > limites.PasoMm)
        {
            paso = paso * (limites.PasoMm / n);
            limitado = true;
        }
        V3 tNuevo = refPrevia.T + paso;

        double theta = refPrevia.R.AnguloHasta(objetivo.R);
        Q qNuevo;
        if (theta <= limites.GiroRad)
        {
            qNuevo = objetivo.R.Normalizado();
        }
        else
        {
            qNuevo = Q.Slerp(refPrevia.R, objetivo.R, limites.GiroRad / theta);
            limitado = true;
        }
        var referencia = new Pose(tNuevo, qNuevo);

        double desvT = (referencia.T - real.T).Norma;
        double desvR = (referencia.R.Normalizado() * real.R.Normalizado().Conjugado).RotVec().Norma;
        if (desvT > limites.DesviacionMm || desvR > limites.DesviacionRad)
        {
            return (Retener(real), Resultado.Fallo);
        }
        return (referencia, limitado ? Resultado.Limitado : Resultado.Ok);
    }
}

/// <summary>Watchdog: el objetivo es viejo si no llega otro en 'plazoS' segundos.</summary>
public sealed class Vigilante
{
    private readonly double _plazoS;
    private double? _ultimo;

    public Vigilante(double plazoS)
    {
        if (plazoS <= 0) throw new ArgumentOutOfRangeException(nameof(plazoS), "el plazo debe ser positivo");
        _plazoS = plazoS;
    }

    public void Marcar(double instanteS) => _ultimo = instanteS;

    public bool Vencido(double instanteS) => _ultimo is null || instanteS - _ultimo.Value > _plazoS;
}
