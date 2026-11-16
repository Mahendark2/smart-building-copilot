import os
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, Float, ForeignKey, Integer, String,
                        create_engine, func, select)
from sqlalchemy.orm import declarative_base, sessionmaker

from .points import POINTS

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://sbc:sbc@localhost:5432/sbc")

Base = declarative_base()


class Point(Base):
    __tablename__ = "points"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    zone = Column(Integer, nullable=False)
    kind = Column(String(32), nullable=False)
    object_type = Column(String(32), nullable=False)
    instance = Column(Integer, nullable=False)
    units = Column(String(16))


class DemoFault(Base):
    """Faults switched on from the dashboard's demo panel. The simulator reads
    this table and breaks the matching zone, so detection can be shown live."""
    __tablename__ = "demo_faults"
    zone = Column(Integer, primary_key=True)
    fault = Column(String(32), nullable=False)
    set_at = Column(DateTime(timezone=True), nullable=False)


class Reading(Base):
    __tablename__ = "readings"
    id = Column(Integer, primary_key=True)
    point_id = Column(Integer, ForeignKey("points.id"), index=True, nullable=False)
    ts = Column(DateTime(timezone=True), index=True, nullable=False)
    value = Column(Float, nullable=False)


_engine = None
_Session = None


def engine():
    global _engine, _Session
    if _engine is None:
        _engine = create_engine(DB_URL, pool_pre_ping=True)
        _Session = sessionmaker(bind=_engine)
    return _engine


def session():
    engine()
    return _Session()


def reset(url):
    """Point the module at another database (used by tests)."""
    global DB_URL, _engine, _Session
    DB_URL = url
    _engine = None
    _Session = None


def setup():
    Base.metadata.create_all(engine())
    with session() as s:
        have = {n for (n,) in s.execute(select(Point.name))}
        for p in POINTS:
            if p["name"] not in have:
                s.add(Point(**p))
        s.commit()


def now():
    return datetime.now(timezone.utc)


def save_readings(values, ts=None):
    """values: {point_name: float}"""
    ts = ts or now()
    with session() as s:
        ids = dict(s.execute(select(Point.name, Point.id)).all())
        for name, v in values.items():
            if name in ids and v is not None:
                s.add(Reading(point_id=ids[name], ts=ts, value=float(v)))
        s.commit()


def latest():
    with session() as s:
        last = (select(Reading.point_id, func.max(Reading.ts).label("ts"))
                .group_by(Reading.point_id).subquery())
        q = (select(Point, Reading.value, Reading.ts)
             .join(last, last.c.point_id == Point.id)
             .join(Reading, (Reading.point_id == Point.id) & (Reading.ts == last.c.ts))
             .order_by(Point.zone, Point.instance))
        out = []
        for p, v, ts in s.execute(q).all():
            out.append({"name": p.name, "zone": p.zone, "kind": p.kind,
                        "units": p.units, "value": round(v, 2), "ts": ts.isoformat()})
        return out


def history(name, since):
    with session() as s:
        q = (select(Reading.ts, Reading.value)
             .join(Point, Point.id == Reading.point_id)
             .where(Point.name == name, Reading.ts >= since)
             .order_by(Reading.ts))
        return [{"ts": ts.isoformat(), "value": round(v, 2)} for ts, v in s.execute(q).all()]


def zone_frame(zone, since):
    """All readings for one zone since a time, as {kind: [values in time order]}."""
    with session() as s:
        q = (select(Point.kind, Reading.ts, Reading.value)
             .join(Point, Point.id == Reading.point_id)
             .where(Point.zone == zone, Reading.ts >= since)
             .order_by(Reading.ts))
        data = {}
        for kind, ts, v in s.execute(q).all():
            data.setdefault(kind, []).append(v)
        return data


def demo_faults():
    """{zone: (fault, set_at)} for every zone that has a demo fault on."""
    with session() as s:
        return {r.zone: (r.fault, r.set_at) for r in s.execute(select(DemoFault)).scalars()}


def set_demo_fault(zone, fault):
    """Turn a fault on for a zone, or off when fault is None."""
    with session() as s:
        row = s.get(DemoFault, zone)
        if fault is None:
            if row:
                s.delete(row)
        elif row is None:
            s.add(DemoFault(zone=zone, fault=fault, set_at=now()))
        elif row.fault != fault:
            row.fault, row.set_at = fault, now()
        s.commit()


def seed_demo_faults(faults):
    """Start from the FAULTS setting, but only if nothing is stored yet."""
    if demo_faults():
        return
    for z, f in faults.items():
        set_demo_fault(z, f)
