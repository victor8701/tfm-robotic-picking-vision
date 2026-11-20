#!/usr/bin/env python3
"""Modifica la estacion Proyecto_1mayo.rsstnx para la celda GoFa + pinza.

Cambios (todo en texto, preservando BOM y CRLF):
  1. Sustituye las 11 conexiones del Station Logic del programa antiguo por las nuevas.
  2. Crea 12 Positioner (PosCaja01..12) que colocan CajaGrande en la cinta con un giro distinto.
  3. Attacher/Detacher de VacuumPen_SComp: Child fijo = CajaGrande, sin depender del LineSensor
     (se quitan los dos Bindings LineSensor.SensedPart -> Child).

Uso: aplicar_estacion.py ENTRADA SALIDA     (no toca ENTRADA)
"""
import math
import re
import sys
import uuid
import xml.etree.ElementTree as ET

ENTRADA, SALIDA = sys.argv[1], sys.argv[2]

ID_CONTROLADOR = 9808          # ControllerTFG_EGM
ID_VACUUM_SC = 1199            # VacuumPen_SComp
ID_ATTACHER, ID_DETACHER = 1206, 1207
ID_CAJA_GRANDE = 2597          # ComponentInstance CajaGrande
ID_POSITIONER_PLANTILLA = 2920
ID_ULTIMO_POSITIONER = 3259    # tras su cierre se insertan los nuevos
ID_RAIZ = 1183                 # AssemblyRoot
ID_NUEVO_0 = 15001
N_GIROS, GIRO_MIN, GIRO_PASO = 12, -90.0, 15.0
CENTRO_LOCAL = (0.9, 0.2, 0.5)     # centro de la caja en el sistema local de la pieza (m)
CENTRO_RECOGIDA = (0.9, 0.2, 0.52)  # centro de la caja parada en la cinta, mundo (m)
NOMBRE_CTRL, NOMBRE_VACUUM = "ControllerTFG_EGM", "VacuumPen_SComp"

raw = open(ENTRADA, "rb").read()
assert raw.startswith(b"\xef\xbb\xbf"), "se esperaba BOM utf-8"
t = raw[3:].decode("utf-8")
assert "\r\n" in t and "\n" not in t.replace("\r\n", ""), "se esperaba CRLF puro"


def fmt(v, decimales=6):
    s = ("%.*f" % (decimales, v)).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def bloque(tag_inicio, texto, desde=0):
    i = texto.index(tag_inicio, desde)
    j = texto.index("</SmartComponentInstance>", i) + len("</SmartComponentInstance>")
    return i, j


# ---------- 1. conexiones del Station Logic ----------
def conexion(so, ss, to, ts, sn, tn):
    return (
        '        <Element type="TIOConnection" AllowCycle="false">\r\n'
        f'          <SourceObject ID="{so}" />\r\n'
        f'          <SourceSignal Value="{ss}" />\r\n'
        f'          <TargetObject ID="{to}" />\r\n'
        f'          <TargetSignal Value="{ts}" />\r\n'
        f'          <SourceObjectName Value="{sn}" />\r\n'
        f'          <TargetObjectName Value="{tn}" />\r\n'
        '        </Element>\r\n'
    )


nuevas = [
    conexion(ID_CONTROLADOR, "PinzaCerrar", ID_VACUUM_SC, "diAttacher_2", NOMBRE_CTRL, NOMBRE_VACUUM),
    conexion(ID_VACUUM_SC, "doAtacher_2", ID_CONTROLADOR, "PinzaCerrada", NOMBRE_VACUUM, NOMBRE_CTRL),
    conexion(ID_CONTROLADOR, "CajaLlegada", ID_CONTROLADOR, "CajaEnRecogida", NOMBRE_CTRL, NOMBRE_CTRL),
]
for k in range(1, N_GIROS + 1):
    nuevas.append(conexion(ID_CONTROLADOR, f"CajaPos{k:02d}", ID_NUEVO_0 + k - 1, "Execute",
                           NOMBRE_CTRL, f"PosCaja{k:02d}"))

a = t.index("<IOConnections>")
b = t.index("</IOConnections>", a)
previo = t[a:b]
assert previo.count('type="TIOConnection"') == 11, "las conexiones de la estacion no son las 11 esperadas"
assert previo.count('ID="9808"') == 11 + 0 or previo.count(f'ID="{ID_CONTROLADOR}"') >= 11
t = t[:a] + "<IOConnections>\r\n" + "".join(nuevas) + "      " + t[b:]

# ---------- 2. Positioner clonados ----------
i0, j0 = bloque(f'<SmartComponentInstance ID="{ID_POSITIONER_PLANTILLA}"', t)
plantilla = t[i0:j0]
assert 'Name="Positioner"' in plantilla and "[0 -3 0.02]" in plantilla

clones = []
for k in range(1, N_GIROS + 1):
    th = math.radians(GIRO_MIN + (k - 1) * GIRO_PASO)
    c, s = math.cos(th), math.sin(th)
    px = CENTRO_RECOGIDA[0] - (CENTRO_LOCAL[0] * c - CENTRO_LOCAL[1] * s)
    py = CENTRO_RECOGIDA[1] - (CENTRO_LOCAL[0] * s + CENTRO_LOCAL[1] * c)
    pz = CENTRO_RECOGIDA[2] - CENTRO_LOCAL[2]
    blk = plantilla
    blk = blk.replace(f'ID="{ID_POSITIONER_PLANTILLA}" Name="Positioner"',
                      f'ID="{ID_NUEVO_0 + k - 1}" Name="PosCaja{k:02d}"', 1)
    blk = blk.replace('<String Value="[0 -3 0.02]" />',
                      f'<String Value="[{fmt(px)} {fmt(py)} {fmt(pz)}]" />', 1)
    # Orientation: la primera aparicion de [0 0 0] tras la clave Orientation
    # Los angulos se guardan en RADIANES (la interfaz los muestra en grados). Con grados la caja
    # acababa en otro sitio: -75 se leia como -75 rad.
    m = re.search(r'(Orientation">\r\n\s*<Value>\r\n\s*<String Value=")\[0 0 0\]', blk)
    assert m, "no encuentro Orientation en la plantilla"
    blk = blk[:m.start()] + m.group(1) + f"[0 0 {fmt(math.radians(GIRO_MIN + (k - 1) * GIRO_PASO), 9)}]" + blk[m.end():]
    blk = re.sub(r'<UniqueId Value="\{[^}]+\}" />', '<UniqueId Value="{%s}" />' % uuid.uuid4(), blk, count=1)
    blk = re.sub(r'(Key="DesignerX">\r\n\s*<Value>\r\n\s*<Double Value=")[^"]*', r"\g<1>%s" % (1250 + 170 * ((k - 1) % 6)), blk, count=1)
    blk = re.sub(r'(Key="DesignerY">\r\n\s*<Value>\r\n\s*<Double Value=")[^"]*', r"\g<1>%s" % (450 + 150 * ((k - 1) // 6)), blk, count=1)
    clones.append(blk)

i3, j3 = bloque(f'<SmartComponentInstance ID="{ID_ULTIMO_POSITIONER}"', t)
t = t[:j3] + "".join("\r\n    " + c for c in clones) + t[j3:]

# registro en la lista Instances de la raiz
ra = t.index(f'<AssemblyRoot ID="{ID_RAIZ}"')
rb = t.index("</Instances>", ra)
refs = "".join(f'        <ObjectRef ID="{ID_NUEVO_0 + k}" />\r\n' for k in range(N_GIROS))
t = t[:rb].rstrip(" ") + refs + "      " + t[rb:]

# ---------- 3. Attacher / Detacher con Child fijo ----------
for idc in (ID_ATTACHER, ID_DETACHER):
    i, j = bloque(f'<SmartComponentInstance ID="{idc}"', t)
    blk = t[i:j]
    nuevo, n = re.subn(r'(&gt;Child">\r\n\s*<Value>\r\n\s*<ObjectRef ID=")-1(" />)', r"\g<1>%d\g<2>" % ID_CAJA_GRANDE, blk, count=1)
    assert n == 1, f"no he podido fijar Child en {idc}"
    t = t[:i] + nuevo + t[j:]

ba = t.index("<Bindings>")
bb = t.index("</Bindings>", ba) + len("</Bindings>")
assert ba < t.index('<SmartComponentInstance ID="1206"') and t[ba:bb].count("TPropertyBinding") == 2 \
    and "LineSensor_2" in t[ba:bb] and t.count("<Bindings>") == 2, "los Bindings no son los esperados"
# quitar el elemento <Bindings> entero (con su sangria y salto de linea)
ini = t.rfind("\r\n", 0, ba)
t = t[:ini] + t[bb:]

# ---------- validacion ----------
raiz = ET.fromstring(t.encode("utf-8"))
ids = re.findall(r'<(?:SmartComponentInstance|ComponentInstance|PartDef|AssemblyRoot)[^>]* ID="(\d+)"', t)
import collections
rep = sorted(k for k, v in collections.Counter(ids).items() if v > 1)
assert rep == ["1183"], ("IDs repetidos nuevos", rep)  # el 1183 ya venia repetido en el original
assert all(ids.count(str(ID_NUEVO_0 + k)) == 1 for k in range(N_GIROS))
uids = re.findall(r'<UniqueId Value="(\{[^}]+\})" />', t)
assert len(uids) == len(set(uids)), "UniqueId repetidos"
nconn = t[t.index("<IOConnections>"):t.index("</IOConnections>")].count('type="TIOConnection"')
assert nconn == 3 + N_GIROS, nconn
assert t.count("<Bindings>") == 1
for k in range(N_GIROS):
    assert f'ID="{ID_NUEVO_0 + k}" Name="PosCaja{k + 1:02d}"' in t

open(SALIDA, "wb").write(b"\xef\xbb\xbf" + t.encode("utf-8"))
print("OK: conexiones", nconn, "| positioners", N_GIROS, "| bytes", len(t))
for k in range(1, N_GIROS + 1):
    th = GIRO_MIN + (k - 1) * GIRO_PASO
    m = re.search(r'Name="PosCaja%02d".*?<String Value="(\[[^\]]*\])" />' % k, t, re.S)
    print(f"  PosCaja{k:02d}  giro {th:6.1f} grados  pos {m.group(1)}")
