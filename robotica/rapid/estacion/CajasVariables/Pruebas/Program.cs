// Pruebas de Logica.cs (sin RobotStudio). Salida 0 si todo va bien; las lanza tests/test_cajas_variables.py.
using System;
using System.Collections.Generic;

namespace CajasVariables.Pruebas
{
    public static class Program
    {
        private static int _fallos;

        private static void Comprobar(bool ok, string que)
        {
            if (!ok) { _fallos++; Console.WriteLine("FALLO: " + que); } else { Console.WriteLine("ok: " + que); }
        }

        private static bool Lanza(Action f)
        {
            try { f(); return false; } catch (FormatException) { return true; }
        }

        public static int Main()
        {
            // ---- caja.csv
            var cajas = CajasCsv.Leer("200.0;200.0;200.0;-75.0\r\n150.5;100;120;30\n\n90;60;80;-0.5\n");
            Comprobar(cajas.Count == 3, "tres cajas");
            Comprobar(cajas[1].Largo == 150.5 && cajas[1].Ancho == 100 && cajas[1].Alto == 120 && cajas[1].Giro == 30, "medidas de la segunda");
            Comprobar(cajas[2].Giro == -0.5, "giro negativo con decimales (punto)");
            Comprobar(Lanza(() => CajasCsv.Leer("1;2;3")), "faltan campos");
            Comprobar(Lanza(() => CajasCsv.Leer("1;2;x;4")), "no es un numero");
            Comprobar(Lanza(() => CajasCsv.Leer("1;-2;3;4")), "dimension negativa");
            Comprobar(CajasCsv.Leer("").Count == 0, "fichero vacio");

            // ---- seguimiento: poses de los Positioner (origen de la pieza, m y rad)
            var pos07 = new Pose(0.0, -1.4, 0.02, 0.0);
            var pos01 = new Pose(0.7, -0.3, 0.02, -Math.PI / 2);
            var inicial = new Pose(0.47, -0.38, 0.02, 0.26);       // donde estaba al abrir la estacion
            var mesa1 = new Pose(-0.22, 0.54, 0.42, 0.0);          // donde se queda la primera caja
            var mesa2 = new Pose(-0.45, 0.54, 0.42, 0.0);
            var cintaMedia = new Pose(0.0, -0.6, 0.02, 0.0);
            var nuevoCsv = true;
            Func<bool> csv = () => nuevoCsv;

            var seg = new Seguimiento(new[] { pos07, pos01 });
            Comprobar(seg.Actualizar(pos07, csv) == null, "lo que hay al arrancar no cuenta como caja");
            Comprobar(seg.Actualizar(cintaMedia, csv) == null, "la caja se va por la cinta");

            // reinicio de la simulacion: la caja vuelve a su sitio de siempre, no es una caja nueva
            Comprobar(seg.Actualizar(inicial, csv) == null, "reset de la simulacion: sin evento");

            // primera caja de una tanda nueva (RAPID reescribio caja.csv)
            var ev = seg.Actualizar(pos07, csv);
            Comprobar(ev != null && ev.Indice == 0 && ev.NuevaTanda && !ev.DejarCopia, "primera caja: tanda nueva, indice 0, sin copia");
            Comprobar(seg.Actualizar(pos07, csv) == null, "mientras sigue en la pose de colocacion no se repite el aviso");
            Comprobar(seg.EnRecogida, "EnRecogida mientras esta en la pose");
            seg.Actualizar(cintaMedia, csv);
            Comprobar(!seg.EnRecogida, "ya no esta en la pose");
            seg.Actualizar(mesa1, csv);

            // segunda caja: mismo csv, otra pose de colocacion
            nuevoCsv = false;
            ev = seg.Actualizar(pos01, csv);
            Comprobar(ev != null && ev.Indice == 1 && !ev.NuevaTanda && ev.DejarCopia, "segunda caja: indice 1 y se deja copia de la primera");
            seg.Actualizar(cintaMedia, csv);
            seg.Actualizar(mesa2, csv);

            // tercera caja con el mismo giro que la segunda
            ev = seg.Actualizar(pos01, csv);
            Comprobar(ev != null && ev.Indice == 2 && ev.DejarCopia && seg.Colocadas == 3, "tercera caja: indice 2");

            // otra tanda: caja.csv nuevo, se empieza de cero y no se deja copia
            seg.Actualizar(mesa2, csv);
            nuevoCsv = true;
            ev = seg.Actualizar(pos07, csv);
            Comprobar(ev != null && ev.Indice == 0 && ev.NuevaTanda && !ev.DejarCopia && seg.Colocadas == 1, "tanda nueva: otra vez indice 0 y sin copia");

            // tolerancias
            var casi = new Seguimiento(new[] { pos07 });
            casi.Actualizar(cintaMedia, csv);
            Comprobar(casi.Actualizar(new Pose(0.0, -1.4 + 0.002, 0.02, 0.005), csv) != null, "2 mm y 0,3 grados cuentan como la pose");
            var lejos = new Seguimiento(new[] { pos07 });
            lejos.Actualizar(cintaMedia, csv);
            Comprobar(lejos.Actualizar(new Pose(0.0, -1.4 + 0.02, 0.02, 0.0), csv) == null, "2 cm de diferencia no cuentan");
            Comprobar(lejos.Actualizar(new Pose(0.0, -1.4, 0.02, 0.5), csv) == null, "0,5 rad de giro no cuentan");

            // el yaw se compara dando la vuelta: -pi y pi son lo mismo
            var plano = new Seguimiento(new[] { new Pose(0, 0, 0, Math.PI) });
            plano.Actualizar(cintaMedia, csv);
            Comprobar(plano.Actualizar(new Pose(0, 0, 0, -Math.PI + 0.001), csv) != null, "yaw -pi equivale a pi");

            Console.WriteLine(_fallos == 0 ? "TODO OK" : _fallos + " FALLOS");
            return _fallos == 0 ? 0 : 1;
        }
    }
}
