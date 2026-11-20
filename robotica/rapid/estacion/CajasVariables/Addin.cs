// Complemento de RobotStudio: cada caja de la simulacion con el tamano de caja.csv, y las ya depositadas se quedan
// en la mesa. Ver README.md. Entrada: AddinMain (la llama RobotStudio al cargar el complemento).
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Windows.Threading;
using ABB.Robotics.Math;
using ABB.Robotics.RobotStudio;
using ABB.Robotics.RobotStudio.Stations;

[assembly: System.Runtime.Versioning.TargetFramework(".NETCoreApp,Version=v10.0", FrameworkDisplayName = ".NET 10.0")]

namespace CajasVariables
{
    public class Addin
    {
        private const string NombreCaja = "CajaGrande";   // la pieza que mueven los Positioner PosCaja01..12 y agarra la pinza
        private const int NumGiros = 12;

        private sealed class Estado
        {
            public Station Estacion;
            public Part Caja;
            public Seguimiento Seg;
            public Matrix4 Previa = Matrix4.Identity;
            public double CentroX, CentroY, BaseZ;      // donde esta (en local) la caja original: centro en x e y y cara de abajo
            public string RutaCsv;
            public DateTime CsvVisto = DateTime.MinValue;
            public List<Caja> Cajas = new List<Caja>();
            public List<GraphicComponent> Dejadas = new List<GraphicComponent>();
            public int NumDejadas;
        }

        private static DispatcherTimer _timer;
        private static object _estado;   // Estado: object para no cargar los tipos de la estacion hasta que haya una
        private static readonly HashSet<string> _avisados = new HashSet<string>();

        public static void AddinMain()
        {
            Log("Cajas variables: cargado. Vigilo " + NombreCaja + " y la redimensiono con las medidas de caja.csv.");
            _timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(50) };
            _timer.Tick += delegate { Tick(); };
            _timer.Start();
        }

        // ---------------------------------------------------------------- utilidades
        private static string _fichero;

        /// <summary>Escribe en la ventana Output de RobotStudio y en %TEMP%\CajasVariables.log (con hora).</summary>
        private static void Log(string texto)
        {
            try
            {
                if (_fichero == null) { _fichero = Path.Combine(Path.GetTempPath(), "CajasVariables.log"); }
                File.AppendAllText(_fichero, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + "  " + texto + Environment.NewLine);
            }
            catch (Exception) { /* sin fichero de registro no se para nada */ }
            try { Logger.AddMessage(texto); } catch (Exception) { /* Output aun no disponible */ }
        }

        private static void LogUnaVez(string texto)
        {
            if (_avisados.Add(texto)) { Log(texto); }
        }

        private static Vector3 LeerVector(SmartComponent sc, string nombre)
        {
            object v = sc.Properties[nombre].Value;
            if (v is Vector3) { return (Vector3)v; }
            return Vector3.Parse(Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture));
        }

        // ---------------------------------------------------------------- arranque sobre una estacion
        private static Estado Iniciar(Station est)
        {
            var e = new Estado { Estacion = est };
            GraphicComponent gc;
            if (!est.GraphicComponents.TryGetGraphicComponent(NombreCaja, out gc) || !(gc is Part))
            {
                LogUnaVez("Cajas variables: no hay una pieza llamada " + NombreCaja + " en la estacion.");
                return e;
            }
            e.Caja = (Part)gc;

            var recogidas = new List<Pose>();
            for (int k = 1; k <= NumGiros; k++)
            {
                GraphicComponent g;
                if (!est.GraphicComponents.TryGetGraphicComponent("PosCaja" + k.ToString("00"), out g)) { continue; }
                var sc = g as SmartComponent;
                if (sc == null) { continue; }
                Vector3 pos = LeerVector(sc, "Position");
                Vector3 ori = LeerVector(sc, "Orientation");
                recogidas.Add(new Pose(pos.x, pos.y, pos.z, ori.z));
            }
            if (recogidas.Count == 0)
            {
                LogUnaVez("Cajas variables: no encuentro los Positioner PosCaja01..12.");
                e.Caja = null;
                return e;
            }
            e.Seg = new Seguimiento(recogidas);

            BoundingBox caja0 = e.Caja.GetBoundingBox(false);
            Vector3 min = caja0.min, max = caja0.max;
            e.CentroX = (min.x + max.x) / 2.0;
            e.CentroY = (min.y + max.y) / 2.0;
            e.BaseZ = min.z;

            e.RutaCsv = BuscarCsv();
            if (e.RutaCsv != null)
            {
                RecargarCsv(e);
            }
            Log(string.Format("Cajas variables: {0} Positioner, caja de {1:0} x {2:0} x {3:0} mm, csv: {4}",
                recogidas.Count, (max.x - min.x) * 1000, (max.y - min.y) * 1000, (max.z - min.z) * 1000, e.RutaCsv ?? "no encontrado"));
            return e;
        }

        // ---------------------------------------------------------------- caja.csv
        private static string BuscarCsv()
        {
            string aqui = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string fichero = Path.Combine(aqui, "ruta_caja_csv.txt");
            if (File.Exists(fichero))
            {
                foreach (string l in File.ReadAllLines(fichero))
                {
                    if (!string.IsNullOrWhiteSpace(l)) { return l.Trim(); }
                }
            }
            string entorno = Environment.GetEnvironmentVariable("CAJAS_CSV");
            if (!string.IsNullOrWhiteSpace(entorno)) { return entorno; }

            // el caja.csv mas reciente de la carpeta HOME de algun controlador virtual de RobotStudio
            string raiz = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "RobotStudio", "Projects");
            string mejor = null;
            DateTime fecha = DateTime.MinValue;
            if (Directory.Exists(raiz))
            {
                foreach (string f in Directory.GetFiles(raiz, "caja.csv", SearchOption.AllDirectories))
                {
                    if (f.IndexOf(Path.DirectorySeparatorChar + "HOME" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) < 0) { continue; }
                    DateTime t = File.GetLastWriteTimeUtc(f);
                    if (t > fecha) { fecha = t; mejor = f; }
                }
            }
            return mejor;
        }

        private static bool CsvNuevo(Estado e)
        {
            if (e.RutaCsv == null || !File.Exists(e.RutaCsv)) { return false; }
            return File.GetLastWriteTimeUtc(e.RutaCsv) != e.CsvVisto;
        }

        private static void RecargarCsv(Estado e)
        {
            try
            {
                using (var fs = new FileStream(e.RutaCsv, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (var sr = new StreamReader(fs))
                {
                    e.Cajas = CajasCsv.Leer(sr.ReadToEnd());
                }
                e.CsvVisto = File.GetLastWriteTimeUtc(e.RutaCsv);
            }
            catch (Exception ex)
            {
                LogUnaVez("Cajas variables: no puedo leer " + e.RutaCsv + ": " + ex.Message);
            }
        }

        // ---------------------------------------------------------------- vigilancia
        private static void Tick()
        {
            try
            {
                // El complemento se carga al arrancar RobotStudio, antes que la estacion: hasta que haya un proyecto no se
                // toca ningun tipo de Stations.
                if (Project.ActiveProject == null) { _estado = null; return; }
                TickEstacion();
            }
            catch (Exception ex)
            {
                LogUnaVez("Cajas variables: " + ex.GetType().Name + ": " + ex.Message);
            }
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static void TickEstacion()
        {
            Station est = Project.ActiveProject as Station;
            if (est == null) { _estado = null; return; }
            Estado e = _estado as Estado;
            if (e == null || !ReferenceEquals(e.Estacion, est)) { e = Iniciar(est); _estado = e; }
            if (e.Caja == null || e.Seg == null) { return; }

            Matrix4 m = e.Caja.Transform.GlobalMatrix;
            var pose = new Pose(m.t.x, m.t.y, m.t.z, Math.Atan2(m.x.y, m.x.x));
            Evento ev = e.Seg.Actualizar(pose, delegate { return CsvNuevo(e); });
            if (!e.Seg.EnRecogida) { e.Previa = m; }
            if (ev != null) { CajaNueva(e, ev); }
        }

        private static void CajaNueva(Estado e, Evento ev)
        {
            Project.UndoContext.BeginUndoStep("Caja nueva");
            try
            {
                if (ev.NuevaTanda)
                {
                    BorrarDejadas(e);
                    RecargarCsv(e);
                }
                else if (ev.DejarCopia)
                {
                    DejarCopia(e);
                }
                if (e.Cajas.Count == 0)
                {
                    LogUnaVez("Cajas variables: caja.csv no tiene cajas; la caja se queda como esta.");
                    return;
                }
                if (ev.Indice >= e.Cajas.Count)
                {
                    LogUnaVez("Cajas variables: hay mas cajas colocadas que lineas en caja.csv; se repite la ultima.");
                }
                Caja c = e.Cajas[Math.Min(ev.Indice, e.Cajas.Count - 1)];
                Redimensionar(e, c);
                Log(string.Format("Cajas variables: caja {0}: {1}", ev.Indice + 1, c));
            }
            finally
            {
                Project.UndoContext.EndUndoStep();
            }
        }

        private static void DejarCopia(Estado e)
        {
            var copia = (GraphicComponent)e.Caja.Copy();   // copia completa: se queda con su tamano aunque la original cambie
            copia.Name = "CajaDejada_" + (++e.NumDejadas);
            e.Estacion.GraphicComponents.Add(copia);
            copia.Transform.GlobalMatrix = e.Previa;
            e.Dejadas.Add(copia);
        }

        private static void BorrarDejadas(Estado e)
        {
            foreach (GraphicComponent g in e.Dejadas)
            {
                try { e.Estacion.GraphicComponents.Remove(g); }
                catch (Exception ex) { LogUnaVez("Cajas variables: no puedo quitar " + g.Name + ": " + ex.Message); }
            }
            e.Dejadas.Clear();
            e.NumDejadas = 0;
        }

        /// <summary>Cambia la geometria de CajaGrande por una caja de largo x ancho x alto, con el mismo centro y la cara de
        /// abajo en el mismo sitio que la original: asi no cambia donde la deja cada Positioner ni donde la para el sensor.</summary>
        private static void Redimensionar(Estado e, Caja c)
        {
            double l = c.Largo / 1000.0, a = c.Ancho / 1000.0, h = c.Alto / 1000.0;
            var viejos = new List<Body>();
            foreach (Body b in e.Caja.Bodies) { viejos.Add(b); }
            foreach (Body b in viejos) { e.Caja.Bodies.Remove(b); }

            double ox = e.CentroX - l / 2.0, oy = e.CentroY - a / 2.0, oz = e.BaseZ;
            Body nuevo = Body.CreateSolidBox(new Matrix4(new Vector3(ox, oy, oz)), new Vector3(l, a, h));
            e.Caja.Bodies.Add(nuevo);

            // Comprobacion: si CreateSolidBox pusiera el origen en otro sitio que la esquina, se corrige una vez
            BoundingBox caja1 = e.Caja.GetBoundingBox(false);
            Vector3 min = caja1.min, max = caja1.max;
            double dx = e.CentroX - (min.x + max.x) / 2.0, dy = e.CentroY - (min.y + max.y) / 2.0, dz = e.BaseZ - min.z;
            if (Math.Abs(dx) > 1e-4 || Math.Abs(dy) > 1e-4 || Math.Abs(dz) > 1e-4)
            {
                e.Caja.Bodies.Remove(nuevo);
                Body corregido = Body.CreateSolidBox(new Matrix4(new Vector3(ox + dx, oy + dy, oz + dz)), new Vector3(l, a, h));
                e.Caja.Bodies.Add(corregido);
                LogUnaVez(string.Format("Cajas variables: CreateSolidBox colocaba la caja {0:0.0} {1:0.0} {2:0.0} mm desplazada; corregido.",
                    dx * 1000, dy * 1000, dz * 1000));
            }
        }
    }
}
