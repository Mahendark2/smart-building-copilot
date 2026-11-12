"""Fault detection: a few clear rules plus an Isolation Forest for odd behaviour.

Rules catch faults we can describe ("damper shut while the valve is wide open").
The model catches zones that just look different from the rest of the building.
A zone is only flagged when all of its last 5 readings look unusual, so one odd
reading does not raise an alarm.
"""
import numpy as np
from sklearn.ensemble import IsolationForest

FEATURES = ["zone_temp", "cool_setpoint", "supply_air_temp", "damper_pos",
            "valve_pos", "fan_speed", "co2"]


def last(frame, kind, n):
    vals = frame.get(kind, [])
    return vals[-n:] if vals else []


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def slope(xs):
    if len(xs) < 5:
        return 0.0
    x = np.arange(len(xs))
    return float(np.polyfit(x, xs, 1)[0])


def rule_faults(zone, frame, ref_supply=None, window=10, drift_window=30):
    out = []
    temp = last(frame, "zone_temp", window)
    if len(temp) < window:
        return out
    sp = mean(last(frame, "cool_setpoint", window))
    damper = mean(last(frame, "damper_pos", window))
    valve = mean(last(frame, "valve_pos", window))
    fan = mean(last(frame, "fan_status", window))
    occ = mean(last(frame, "occupied", window))
    co2 = last(frame, "co2", 1)[0]
    warm = mean(temp) - sp

    if damper < 5 and valve > 80 and warm > 1.0:
        out.append(fault(zone, "stuck_damper", "high",
                         f"Damper averaged {damper:.0f}% while the cooling valve was {valve:.0f}% open "
                         f"and the room sat {warm:.1f} C above setpoint. The damper is likely stuck shut."))
    if occ > 0.5 and fan < 0.5:
        out.append(fault(zone, "fan_off_while_occupied", "high",
                         "The zone is marked occupied but the fan has been off for the whole window."))
    if co2 > 1000:
        out.append(fault(zone, "high_co2", "medium",
                         f"CO2 is {co2:.0f} ppm, above the 1000 ppm comfort limit. Ventilation may be too low."))

    # Drift: compare with the building's median supply temperature, so a
    # restart or a change that hits every zone at once is not counted.
    supply = last(frame, "supply_air_temp", drift_window)
    valves = last(frame, "valve_pos", drift_window)
    ref = (ref_supply or [])[-drift_window:]
    if len(supply) >= drift_window and len(ref) == len(supply):
        gap = [a - b for a, b in zip(supply, ref)]
        rise = slope(gap) * (len(gap) - 1)
        if rise > 0.5 and np.std(valves) < 10:
            out.append(fault(zone, "supply_sensor_drift", "medium",
                             f"Supply air temperature rose {rise:.1f} C more than the rest of the building "
                             f"over the last {len(supply)} readings while the valve stayed steady. "
                             f"The sensor may be drifting."))
    if not out and warm > 2:
        out.append(fault(zone, "too_warm", "low",
                         f"The room has been {warm:.1f} C above its cooling setpoint."))
    return out


def fault(zone, kind, severity, detail, source="rule", score=None):
    return {"zone": zone, "type": kind, "severity": severity, "detail": detail,
            "source": source, "score": score}


def ml_faults(frames, recent=5):
    """frames: {zone: frame}. Fits one Isolation Forest on every zone's readings."""
    X, owner = [], []
    for z, frame in frames.items():
        n = min((len(frame.get(k, [])) for k in FEATURES), default=0)
        for i in range(n):
            vals = [frame[k][-n + i] for k in FEATURES]
            vals[0] = vals[0] - vals[1]  # use distance from setpoint, not raw temp
            X.append(vals[:1] + vals[2:])
            owner.append(z)
    if len(X) < 30:
        return []

    X = np.array(X, dtype=float)
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    model = IsolationForest(n_estimators=150, contamination=0.1, random_state=7)
    model.fit(X)
    scores = model.score_samples(X)
    flags = model.predict(X)

    out = []
    owner = np.array(owner)
    for z in frames:
        idx = np.where(owner == z)[0][-recent:]
        if len(idx) == recent and (flags[idx] == -1).all():
            sc = float(scores[idx].mean())
            out.append(fault(z, "ml_anomaly", "medium",
                             "This zone's recent readings look unusual compared with the rest of the building.",
                             source="isolation_forest", score=round(sc, 3)))
    return out


def median_supply(frames):
    series = [f.get("supply_air_temp", []) for f in frames.values()]
    n = min((len(x) for x in series), default=0)
    if not n:
        return []
    return [float(np.median([x[-n + i] for x in series])) for i in range(n)]


def detect(frames):
    found = []
    ref = median_supply(frames)
    for z, frame in frames.items():
        found += rule_faults(z, frame, ref)
    flagged = {f["zone"] for f in found if f["severity"] != "low"}
    for f in ml_faults(frames):
        if f["zone"] not in flagged:
            found.append(f)
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(found, key=lambda f: (order[f["severity"]], f["zone"]))
