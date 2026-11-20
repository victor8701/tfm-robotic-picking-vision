#!/usr/bin/env python3
"""Segunda version de los cambios de la estacion (sustituye los Positioner de aplicar_estacion.py).

Parte de una estacion que ya tiene PosCaja01..12 y las conexiones de aplicar_estacion.py (puede
ser la que guarda RobotStudio: conserva el formato) y hace tres cosas:
  1. Los 12 PosCaja colocan la caja al INICIO de la cinta, con su giro, y la cinta la lleva hasta
     el sensor. Los angulos van en RADIANES: RobotStudio los muestra en grados pero los guarda
     en radianes (con grados, -75 se leia como -75 rad y la caja acababa en otro sitio).
  2. Conexiones: se quita CajaLlegada -> CajaEnRecogida y se ponen
        FinCinta_2.SensorOut -> ControllerTFG_EGM.CajaEnRecogida   (el sensor avisa de la llegada)
        ControllerTFG_EGM.CintaMover -> LinearMover.Execute          (RAPID mueve la cinta)
  3. El plano del sensor FinCinta_2 se ensancha en x (0,7 a 1,1 m) para que detecte la caja con
     cualquier giro. Una caja de 200 mm girada ocupa x = 0,9 +- 0,14 m.
  4. (y el Child fijo de Attacher/Detacher) El estado "Idle" que RobotStudio guarda dentro del fichero tambien lleva los valores de las
     propiedades de cada componente, y al abrir la estacion o hacer Reset los restaura POR ENCIMA
     de lo editado en 1 y 3. Se actualizan tambien ahi.

El script se puede ejecutar mas de una vez sobre el mismo fichero.

Uso: actualizar_estacion.py ENTRADA SALIDA     (no toca ENTRADA)
"""
import math
import re
import sys
import xml.etree.ElementTree as ET

ENTRADA, SALIDA = sys.argv[1], sys.argv[2]

ID_CONTROLADOR, ID_FINCINTA, ID_LINEARMOVER = 9808, 2921, 2991
ID_ATTACHER, ID_DETACHER, ID_CAJA_GRANDE = 1206, 1207, 2597
NOMBRE_CTRL = "ControllerTFG_EGM"
N_GIROS, GIRO_MIN, GIRO_PASO = 12, -90.0, 15.0
CENTRO_LOCAL = (0.9, 0.2, 0.5)        # centro de la caja en el sistema local de la pieza (m)
ARRANQUE = (0.9, -1.2, 0.52)          # centro de la caja al colocarla al inicio de la cinta (m, mundo)
PLANO_X0, PLANO_LARGO = -0.2, 0.4     # plano del sensor: origen y lado en x (locales; el sensor esta en x=0,9)

raw = open(ENTRADA, "rb").read()
assert raw.startswith(b"\xef\xbb\xbf"), "se esperaba BOM utf-8"
t = raw[3:].decode("utf-8")
assert "\r\n" in t and "\n" not in t.replace("\r\n", ""), "se esperaba CRLF puro"


def fmt(v, dec=6):
    s = ("%.*f" % (dec, v)).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def cambiar_cadena(texto, desde, clave, nuevo, esperado=None):
    """Sustituye el String Value de la propiedad `clave` (primera aparicion tras `desde`)."""
    m = re.compile(r'(&gt;%s">\r\n\s*<Value>\r\n\s*<String Value=")([^"]*)(")' % clave).search(texto, desde)
    assert m, f"no encuentro {clave}"
    if esperado is not None:
        assert m.group(2) == esperado, (clave, m.group(2), esperado)
    return texto[:m.start(2)] + nuevo + texto[m.end(2):], m.group(2)


# ---------- 1. PosCaja: inicio de la cinta, angulos en radianes ----------
valores_poscaja = {}
for k in range(1, N_GIROS + 1):
    th = math.radians(GIRO_MIN + (k - 1) * GIRO_PASO)
    c, s = math.cos(th), math.sin(th)
    px = ARRANQUE[0] - (CENTRO_LOCAL[0] * c - CENTRO_LOCAL[1] * s)
    py = ARRANQUE[1] - (CENTRO_LOCAL[0] * s + CENTRO_LOCAL[1] * c)
    pz = ARRANQUE[2] - CENTRO_LOCAL[2]
    i = t.index(f'Name="PosCaja{k:02d}"')
    pos, ori = f"[{fmt(px)} {fmt(py)} {fmt(pz)}]", f"[0 0 {fmt(th, 9)}]"
    t, _ = cambiar_cadena(t, i, "Position", pos)
    t, _ = cambiar_cadena(t, i, "Orientation", ori)
    valores_poscaja[k] = (pos, ori)

# ---------- 2. conexiones ----------
a = t.index("<IOConnections>")
b = t.index("</IOConnections>", a)
bloque = t[a:b]
patron = re.compile(r'        <Element type="TIOConnection" AllowCycle="false">\r\n'
                    r'          <SourceObject ID="%d" />\r\n          <SourceSignal Value="CajaLlegada" />\r\n'
                    r'          <TargetObject ID="%d" />\r\n          <TargetSignal Value="CajaEnRecogida" />\r\n'
                    r'          <SourceObjectName Value="[^"]*" />\r\n          <TargetObjectName Value="[^"]*" />\r\n'
                    r'        </Element>\r\n' % (ID_CONTROLADOR, ID_CONTROLADOR))
bloque, n = patron.subn("", bloque)
assert n <= 1


def conexion(so, ss, to, ts, sn, tn):
    return ('        <Element type="TIOConnection" AllowCycle="false">\r\n'
            f'          <SourceObject ID="{so}" />\r\n          <SourceSignal Value="{ss}" />\r\n'
            f'          <TargetObject ID="{to}" />\r\n          <TargetSignal Value="{ts}" />\r\n'
            f'          <SourceObjectName Value="{sn}" />\r\n          <TargetObjectName Value="{tn}" />\r\n'
            '        </Element>\r\n')


nuevas = [conexion(ID_FINCINTA, "SensorOut", ID_CONTROLADOR, "CajaEnRecogida", "FinCinta_2", NOMBRE_CTRL),
          conexion(ID_CONTROLADOR, "CintaMover", ID_LINEARMOVER, "Execute", NOMBRE_CTRL, "LinearMover")]
for c in nuevas:
    if c not in bloque:
        bloque += c
t = t[:a] + bloque + t[b:]

# ---------- 3. plano del sensor FinCinta_2 ----------
i = t.index(f'<SmartComponentInstance ID="{ID_FINCINTA}"')
t, _ = cambiar_cadena(t, i, "Origin", f"[{fmt(PLANO_X0)} 0 0]")
t, _ = cambiar_cadena(t, i, "Axis1", f"[{fmt(PLANO_LARGO)} 0 0]")
guid_fincinta = re.search(r'<UniqueId Value="(\{[^}]+\})"', t[i:]).group(1)

# ---------- 4. estado "Idle" guardado dentro del fichero ----------
def cambiar_estado(texto, guid, propiedad, nuevo):
    """Cambia DynamicProperty `propiedad` del estado del objeto `guid` (texto con comillas escapadas)."""
    a = texto.index(f"objectId=&quot;{guid}&quot;")
    b = texto.index("&lt;/StandardState&gt;", a)
    m = re.compile(r"(name=&quot;%s&quot; value=&quot;)([^&]*)(&quot;)" % propiedad).search(texto, a, b)
    assert m, (guid, propiedad)
    return texto[:m.start(2)] + nuevo + texto[m.end(2):]


for k in range(1, N_GIROS + 1):
    i = t.index(f'Name="PosCaja{k:02d}"')
    guid = re.search(r'<UniqueId Value="(\{[^}]+\})"', t[i:]).group(1)
    t = cambiar_estado(t, guid, "Position", valores_poscaja[k][0])
    t = cambiar_estado(t, guid, "Orientation", valores_poscaja[k][1])
t = cambiar_estado(t, guid_fincinta, "Origin", f"[{fmt(PLANO_X0)} 0 0]")
t = cambiar_estado(t, guid_fincinta, "Axis1", f"[{fmt(PLANO_LARGO)} 0 0]")
# Attacher y Detacher de VacuumPen_SComp: el Child fijo (caja grande) tambien se guarda en el estado
i = t.index(f'<ComponentInstance ID="{ID_CAJA_GRANDE}"')
guid_caja = re.search(r'<UniqueId Value="(\{[^}]+\})"', t[i:]).group(1)
for idc in (ID_ATTACHER, ID_DETACHER):
    i = t.index(f'<SmartComponentInstance ID="{idc}"')
    guid = re.search(r'<UniqueId Value="(\{[^}]+\})"', t[i:]).group(1)
    t = cambiar_estado(t, guid, "Child", guid_caja)

# ---------- validacion ----------
ET.fromstring(t.encode("utf-8"))
io = t[t.index("<IOConnections>"):t.index("</IOConnections>")]
assert io.count('type="TIOConnection"') == 16, io.count('type="TIOConnection"')
assert "CajaLlegada" not in io
open(SALIDA, "wb").write(b"\xef\xbb\xbf" + t.encode("utf-8"))
print("OK: 12 PosCaja al inicio de la cinta (radianes), 16 conexiones, plano del sensor ensanchado, estado Idle actualizado")
for k in range(1, N_GIROS + 1):
    i = t.index(f'Name="PosCaja{k:02d}"')
    m = re.search(r'Position">\r\n\s*<Value>\r\n\s*<String Value="([^"]*)"', t[i:])
    o = re.search(r'Orientation">\r\n\s*<Value>\r\n\s*<String Value="([^"]*)"', t[i:])
    print(f"  PosCaja{k:02d}  giro {GIRO_MIN + (k - 1) * GIRO_PASO:6.1f} grados  pos {m.group(1)}  orient {o.group(1)}")
