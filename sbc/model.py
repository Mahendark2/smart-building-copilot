"""Simple HVAC physics for the simulated controller.

Each zone has a fan, a damper and a cooling valve. The zone temperature drifts
toward the outside temperature and gets pulled down when cool air comes in.
A few faults can be switched on so the fault detection has something to find.
"""
import math
import random

FAULT_TYPES = ("stuck_damper", "sensor_drift", "fan_off", "high_co2")
DRIFT_MAX = 4.0  # degrees C a drifting supply sensor ends up off by


class Zone:
    def __init__(self, n, fault=None, seed=None):
        self.n = n
        self.fault = fault
        self.rnd = random.Random(seed if seed is not None else n)
        self.temp = 22.0 + self.rnd.uniform(-0.5, 0.5)
        self.cool_sp = 23.0
        self.heat_sp = 20.0
        self.humidity = 45.0
        self.co2 = 550.0
        self.damper = 40.0
        self.valve = 30.0
        self.fan_speed = 60.0
        self.fan_on = True
        self.occupied = True
        self.drift = 0.0
        self.t = 0

    def step(self):
        self.t += 1
        hour = (self.t / 60.0) % 24
        outside = 24 + 6 * math.sin((hour - 9) / 24 * 2 * math.pi)
        self.occupied = 7 <= hour <= 19 or self.fault == "fan_off"

        # simple controller: open valve and damper when the room is warm
        err = self.temp - self.cool_sp
        self.valve = min(100, max(0, 30 + err * 35))
        self.damper = min(100, max(10, 40 + err * 25))
        self.fan_on = self.occupied
        self.fan_speed = 30 + self.valve * 0.6 if self.fan_on else 0

        if self.fault == "stuck_damper":
            self.damper = 0.0
        if self.fault == "fan_off":
            self.fan_on = False
            self.fan_speed = 0.0

        supply = 13.0 + (100 - self.valve) * 0.05
        airflow = (self.damper / 100) * (self.fan_speed / 100)
        heat_in = (outside - self.temp) * 0.02 + (0.15 if self.occupied else 0)
        cool = airflow * (self.temp - supply) * 0.12
        self.temp += heat_in - cool + self.rnd.gauss(0, 0.03)

        people = 1.0 if self.occupied else 0.1
        vent = airflow * 40
        if self.fault == "high_co2":
            vent *= 0.1
        self.co2 += people * 12 - vent - (self.co2 - 420) * 0.01 + self.rnd.gauss(0, 3)
        self.co2 = max(400, self.co2)
        self.humidity += (50 - self.humidity) * 0.02 + self.rnd.gauss(0, 0.2)

        if self.fault == "sensor_drift":
            # a real sensor drifts a few degrees and then sits there
            self.drift = min(self.drift + 0.05, DRIFT_MAX)
        self.supply = supply + self.drift + self.rnd.gauss(0, 0.05)
        self.ret = self.temp + 0.8 + self.rnd.gauss(0, 0.05)

    def values(self):
        return {
            "zone_temp": round(self.temp, 2),
            "cool_setpoint": self.cool_sp,
            "heat_setpoint": self.heat_sp,
            "supply_air_temp": round(self.supply, 2),
            "return_air_temp": round(self.ret, 2),
            "humidity": round(self.humidity, 1),
            "co2": round(self.co2, 0),
            "damper_pos": round(self.damper, 1),
            "valve_pos": round(self.valve, 1),
            "fan_speed": round(self.fan_speed, 1),
            "fan_status": 1.0 if self.fan_on else 0.0,
            "occupied": 1.0 if self.occupied else 0.0,
        }


def parse_faults(text):
    """'3:stuck_damper,5:sensor_drift' -> {3: 'stuck_damper', 5: 'sensor_drift'}"""
    out = {}
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        z, f = part.split(":")
        if f not in FAULT_TYPES:
            raise ValueError(f"unknown fault {f}")
        out[int(z)] = f
    return out


class Building:
    def __init__(self, zones=6, faults=None, start_hour=10):
        faults = faults or {}
        self.zones = [Zone(n, faults.get(n)) for n in range(1, zones + 1)]
        for z in self.zones:
            z.t = start_hour * 60
            z.step()

    def step(self):
        for z in self.zones:
            z.step()

    def values(self):
        out = {}
        for z in self.zones:
            for k, v in z.values().items():
                out[f"zone{z.n}.{k}"] = v
        return out
