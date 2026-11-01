"""Mensajes EGM de ABB como clases de Python, a partir del descriptor de egm.proto.

Convenciones, las mismas del resto del proyecto:
- posiciones en mm; orientación como cuaternión (w, x, y, z) = (u0, u1, u2, u3).
- Robot → sensor: EgmRobot en cada ciclo (4 ms). Sensor → robot: EgmSensor como respuesta.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

import numpy as np
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from ._descriptor_egm import DESCRIPTOR_BASE64

MSGTYPE_DATA = 2          # robot → sensor (EgmHeader.MessageType)
MSGTYPE_CORRECTION = 3    # sensor → robot, corrección de posición

_POOL = descriptor_pool.DescriptorPool()
_FDP = descriptor_pb2.FileDescriptorProto()
_FDP.ParseFromString(base64.b64decode(DESCRIPTOR_BASE64))
_POOL.Add(_FDP)


def _clase(nombre: str):
    return message_factory.GetMessageClass(_POOL.FindMessageTypeByName(f"abb.egm.{nombre}"))


EgmRobot = _clase("EgmRobot")
EgmSensor = _clase("EgmSensor")


@dataclass(frozen=True)
class EstadoRobot:
    seqno: int
    tm: int
    pos: np.ndarray   # mm
    q: np.ndarray     # (w, x, y, z)


@dataclass(frozen=True)
class EstadoSensor:
    seqno: int
    tm: int
    mtype: int
    pos: np.ndarray | None   # None si el sensor no envía consigna cartesiana
    q: np.ndarray | None


def _asignar_pose(pose, pos, q) -> None:
    pose.pos.x, pose.pos.y, pose.pos.z = (float(v) for v in pos)
    pose.orient.u0, pose.orient.u1, pose.orient.u2, pose.orient.u3 = (float(v) for v in q)


def crear_egm_robot(seqno: int, tm: int, pos, q) -> bytes:
    """Mensaje que enviaría el controlador con su pose cartesiana actual."""
    m = EgmRobot()
    m.header.seqno = seqno
    m.header.tm = tm
    m.header.mtype = MSGTYPE_DATA
    _asignar_pose(m.feedBack.cartesian, pos, q)
    return m.SerializeToString()


def leer_egm_robot(datos: bytes) -> EstadoRobot:
    m = EgmRobot.FromString(datos)
    if not (m.HasField("feedBack") and m.feedBack.HasField("cartesian")):
        raise ValueError("EgmRobot sin feedBack.cartesian")
    p = m.feedBack.cartesian
    return EstadoRobot(
        seqno=m.header.seqno,
        tm=m.header.tm,
        pos=np.array([p.pos.x, p.pos.y, p.pos.z]),
        q=np.array([p.orient.u0, p.orient.u1, p.orient.u2, p.orient.u3]),
    )


def crear_egm_sensor(seqno: int, tm: int, pos, q, mtype: int = MSGTYPE_CORRECTION) -> bytes:
    """Respuesta del sensor con la consigna cartesiana (planned)."""
    m = EgmSensor()
    m.header.seqno = seqno
    m.header.tm = tm
    m.header.mtype = mtype
    _asignar_pose(m.planned.cartesian, pos, q)
    return m.SerializeToString()


def leer_egm_sensor(datos: bytes) -> EstadoSensor:
    m = EgmSensor.FromString(datos)
    pos = q = None
    if m.HasField("planned") and m.planned.HasField("cartesian"):
        p = m.planned.cartesian
        pos = np.array([p.pos.x, p.pos.y, p.pos.z])
        q = np.array([p.orient.u0, p.orient.u1, p.orient.u2, p.orient.u3])
    return EstadoSensor(seqno=m.header.seqno, tm=m.header.tm, mtype=m.header.mtype, pos=pos, q=q)
