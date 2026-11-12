ZONES = 6

# name, BACnet object type, units
KINDS = [
    ("zone_temp", "analog-value", "degC"),
    ("cool_setpoint", "analog-value", "degC"),
    ("heat_setpoint", "analog-value", "degC"),
    ("supply_air_temp", "analog-value", "degC"),
    ("return_air_temp", "analog-value", "degC"),
    ("humidity", "analog-value", "percent"),
    ("co2", "analog-value", "ppm"),
    ("damper_pos", "analog-value", "percent"),
    ("valve_pos", "analog-value", "percent"),
    ("fan_speed", "analog-value", "percent"),
    ("fan_status", "binary-value", "on/off"),
    ("occupied", "binary-value", "yes/no"),
]


def all_points():
    pts = []
    for z in range(1, ZONES + 1):
        for i, (kind, otype, units) in enumerate(KINDS, start=1):
            pts.append({
                "name": f"zone{z}.{kind}",
                "zone": z,
                "kind": kind,
                "object_type": otype,
                "instance": z * 100 + i,
                "units": units,
            })
    return pts


POINTS = all_points()
BY_NAME = {p["name"]: p for p in POINTS}
