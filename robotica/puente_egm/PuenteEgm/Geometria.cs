namespace PuenteEgm;

/// <summary>Vector de posición en mm.</summary>
public readonly record struct V3(double X, double Y, double Z)
{
    public static V3 operator +(V3 a, V3 b) => new(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
    public static V3 operator -(V3 a, V3 b) => new(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
    public static V3 operator *(V3 a, double s) => new(a.X * s, a.Y * s, a.Z * s);
    public double Norma => Math.Sqrt(X * X + Y * Y + Z * Z);
    public bool EsFinito => double.IsFinite(X) && double.IsFinite(Y) && double.IsFinite(Z);
}

/// <summary>Cuaternión (w, x, y, z). Mismas convenciones que nucleo/geometria.py.</summary>
public readonly record struct Q(double W, double X, double Y, double Z)
{
    public static Q Identidad => new(1, 0, 0, 0);

    /// <summary>Unitario con w >= 0 (un único representante por rotación).</summary>
    public Q Normalizado()
    {
        double n = Math.Sqrt(W * W + X * X + Y * Y + Z * Z);
        if (n < 1e-12) throw new ArgumentException("cuaternión nulo");
        var q = new Q(W / n, X / n, Y / n, Z / n);
        return q.W >= 0 ? q : new Q(-q.W, -q.X, -q.Y, -q.Z);
    }

    public Q Conjugado => new(W, -X, -Y, -Z);

    public bool EsFinito => double.IsFinite(W) && double.IsFinite(X) && double.IsFinite(Y) && double.IsFinite(Z);

    /// <summary>Producto de Hamilton: R(a * b) = R(a) R(b).</summary>
    public static Q operator *(Q a, Q b) => new(
        a.W * b.W - a.X * b.X - a.Y * b.Y - a.Z * b.Z,
        a.W * b.X + a.X * b.W + a.Y * b.Z - a.Z * b.Y,
        a.W * b.Y - a.X * b.Z + a.Y * b.W + a.Z * b.X,
        a.W * b.Z + a.X * b.Y - a.Y * b.X + a.Z * b.W);

    /// <summary>Logaritmo de la rotación: vector cuya norma es el ángulo (rad).</summary>
    public V3 RotVec()
    {
        var q = Normalizado();
        double nv = Math.Sqrt(q.X * q.X + q.Y * q.Y + q.Z * q.Z);
        if (nv < 1e-12) return new V3(2 * q.X, 2 * q.Y, 2 * q.Z);
        double ang = 2 * Math.Atan2(nv, q.W);
        return new V3(q.X / nv * ang, q.Y / nv * ang, q.Z / nv * ang);
    }

    /// <summary>Exponencial de la rotación (inversa de RotVec).</summary>
    public static Q DesdeRotVec(V3 r)
    {
        double th = r.Norma;
        if (th < 1e-12) return new Q(1, 0.5 * r.X, 0.5 * r.Y, 0.5 * r.Z).Normalizado();
        double s = Math.Sin(th / 2) / th;
        return new Q(Math.Cos(th / 2), r.X * s, r.Y * s, r.Z * s).Normalizado();
    }

    /// <summary>Ángulo (rad) de la rotación que lleva esta orientación a 'otra'.</summary>
    public double AnguloHasta(Q otra) => (Normalizado().Conjugado * otra.Normalizado()).RotVec().Norma;

    /// <summary>Recorre la fracción f (0..1) del camino más corto entre a y b.</summary>
    public static Q Slerp(Q a, Q b, double f)
    {
        a = a.Normalizado();
        b = b.Normalizado();
        double d = a.W * b.W + a.X * b.X + a.Y * b.Y + a.Z * b.Z;
        if (d < 0)
        {
            b = new Q(-b.W, -b.X, -b.Y, -b.Z);
            d = -d;
        }
        if (d > 0.9995)
        {
            return new Q(
                a.W + f * (b.W - a.W), a.X + f * (b.X - a.X),
                a.Y + f * (b.Y - a.Y), a.Z + f * (b.Z - a.Z)).Normalizado();
        }
        double th = Math.Acos(Math.Clamp(d, -1.0, 1.0));
        double s0 = Math.Sin((1 - f) * th) / Math.Sin(th);
        double s1 = Math.Sin(f * th) / Math.Sin(th);
        return new Q(
            s0 * a.W + s1 * b.W, s0 * a.X + s1 * b.X,
            s0 * a.Y + s1 * b.Y, s0 * a.Z + s1 * b.Z).Normalizado();
    }
}

/// <summary>Pose: posición T (mm) y orientación R (cuaternión).</summary>
public readonly record struct Pose(V3 T, Q R);
