// Logica del complemento CajasVariables, sin tipos de RobotStudio: asi se prueba con una consola (Pruebas/).
using System;
using System.Collections.Generic;
using System.Globalization;

namespace CajasVariables
{
    /// <summary>Una caja de caja.csv: largo;ancho;alto en mm y giro en grados.</summary>
    public sealed class Caja
    {
        public readonly double Largo, Ancho, Alto, Giro;

        public Caja(double largo, double ancho, double alto, double giro)
        {
            Largo = largo; Ancho = ancho; Alto = alto; Giro = giro;
        }

        public override string ToString()
        {
            return string.Format(CultureInfo.InvariantCulture, "{0:0.#} x {1:0.#} x {2:0.#} mm, giro {3:0.#}", Largo, Ancho, Alto, Giro);
        }
    }

    public static class CajasCsv
    {
        /// <summary>Lee caja.csv: una caja por linea, campos separados por ';' (punto decimal).</summary>
        public static List<Caja> Leer(string texto)
        {
            var cajas = new List<Caja>();
            int n = 0;
            foreach (string linea in texto.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries))
            {
                if (string.IsNullOrWhiteSpace(linea)) { continue; }
                n++;
                string[] partes = linea.Trim().Split(';');
                if (partes.Length != 4)
                {
                    throw new FormatException(string.Format("caja.csv, linea {0}: se esperan 4 campos (largo;ancho;alto;giro) y hay {1}", n, partes.Length));
                }
                var v = new double[4];
                for (int i = 0; i < 4; i++)
                {
                    if (!double.TryParse(partes[i], NumberStyles.Float, CultureInfo.InvariantCulture, out v[i]))
                    {
                        throw new FormatException(string.Format("caja.csv, linea {0}: '{1}' no es un numero", n, partes[i]));
                    }
                }
                if (v[0] <= 0 || v[1] <= 0 || v[2] <= 0)
                {
                    throw new FormatException(string.Format("caja.csv, linea {0}: las dimensiones deben ser positivas", n));
                }
                cajas.Add(new Caja(v[0], v[1], v[2], v[3]));
            }
            return cajas;
        }
    }

    /// <summary>Pose del origen de la pieza en el mundo: metros y yaw en radianes.</summary>
    public struct Pose
    {
        public readonly double X, Y, Z, Yaw;

        public Pose(double x, double y, double z, double yaw)
        {
            X = x; Y = y; Z = z; Yaw = yaw;
        }
    }

    /// <summary>Lo que ha pasado en un tick: se ha colocado una caja nueva.</summary>
    public sealed class Evento
    {
        /// <summary>Posicion (0, 1, 2...) de la caja dentro de la tanda; sale de caja.csv.</summary>
        public int Indice;
        /// <summary>caja.csv es nuevo (RAPID lo reescribe al empezar): empieza otra tanda.</summary>
        public bool NuevaTanda;
        /// <summary>Hay una caja anterior que se quedo en la mesa y hay que dejar copiada donde estaba.</summary>
        public bool DejarCopia;
    }

    /// <summary>
    /// Vigila la pose de CajaGrande. RAPID coloca cada caja pulsando CajaPosKK: el Positioner KK la lleva a una pose
    /// fija (Position y Orientation de PosCajaKK). Esa llegada es el aviso de caja nueva; la ultima pose vista antes
    /// es donde se quedo la anterior (en la mesa), y es donde hay que dejar su copia.
    /// </summary>
    public sealed class Seguimiento
    {
        private readonly List<Pose> _recogidas;
        private readonly double _tolPos, _tolYaw;
        private bool _inicializado, _enRecogidaAntes, _hayPrevia;
        private int _colocadas;

        public Seguimiento(IEnumerable<Pose> recogidas, double tolPosM = 0.003, double tolYawRad = 0.01)
        {
            _recogidas = new List<Pose>(recogidas);
            _tolPos = tolPosM;
            _tolYaw = tolYawRad;
        }

        /// <summary>La caja esta ahora en una de las poses de colocacion.</summary>
        public bool EnRecogida { get; private set; }

        /// <summary>Cajas colocadas en la tanda en curso.</summary>
        public int Colocadas { get { return _colocadas; } }

        private bool EsRecogida(Pose p)
        {
            foreach (Pose r in _recogidas)
            {
                double d = Math.Sqrt((p.X - r.X) * (p.X - r.X) + (p.Y - r.Y) * (p.Y - r.Y) + (p.Z - r.Z) * (p.Z - r.Z));
                double dy = Math.Abs(Math.IEEERemainder(p.Yaw - r.Yaw, 2 * Math.PI));
                if (d <= _tolPos && dy <= _tolYaw) { return true; }
            }
            return false;
        }

        /// <summary>Un tick de vigilancia. csvNuevo solo se evalua cuando llega una caja nueva.</summary>
        public Evento Actualizar(Pose actual, Func<bool> csvNuevo)
        {
            EnRecogida = EsRecogida(actual);
            Evento ev = null;
            if (!_inicializado)
            {
                _inicializado = true;   // lo que haya al arrancar no es una caja colocada
            }
            else if (EnRecogida && !_enRecogidaAntes)
            {
                bool nueva = csvNuevo();
                if (nueva) { _colocadas = 0; }
                ev = new Evento { Indice = _colocadas, NuevaTanda = nueva, DejarCopia = !nueva && _colocadas > 0 && _hayPrevia };
                _colocadas++;
            }
            _enRecogidaAntes = EnRecogida;
            _hayPrevia = _hayPrevia || !EnRecogida;
            return ev;
        }
    }

    /// <summary>
    /// Fin de la tanda. RAPID escribe (o reescribe) fin_tanda.txt junto a caja.csv cuando termina la ultima caja. Este vigilante
    /// ve que la fecha del fichero ha cambiado y avisa una sola vez, pasada una espera (para que se vea el resultado). Lo que
    /// ya hubiera al arrancar el complemento no cuenta como un fin nuevo.
    /// </summary>
    public sealed class VigilanteFin
    {
        private readonly TimeSpan _espera;
        private DateTime _visto;
        private DateTime? _avisarEn;

        /// <param name="marcaInicial">fecha del fichero al arrancar (DateTime.MinValue si no existe)</param>
        public VigilanteFin(DateTime marcaInicial, TimeSpan espera)
        {
            _visto = marcaInicial;
            _espera = espera;
        }

        /// <summary>Hay un fin de tanda pendiente de avisar.</summary>
        public bool Pendiente { get { return _avisarEn.HasValue; } }

        /// <summary>marca = fecha de modificacion de fin_tanda.txt (DateTime.MinValue si no existe). Devuelve true una vez, cuando toca borrar.</summary>
        public bool Actualizar(DateTime marca, DateTime ahora)
        {
            if (marca != DateTime.MinValue && marca != _visto)
            {
                _visto = marca;
                _avisarEn = ahora + _espera;
            }
            if (_avisarEn.HasValue && ahora >= _avisarEn.Value)
            {
                _avisarEn = null;
                return true;
            }
            return false;
        }

        /// <summary>Llega otra caja antes de borrar (otra tanda ya en marcha): el fin pendiente ya no vale.</summary>
        public void Cancelar()
        {
            _avisarEn = null;
        }
    }
}
