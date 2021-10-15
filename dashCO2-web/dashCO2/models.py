"""
    dashCO2.models
    ~~~~~~~~~~~~~~

    Modelos para la base de datos.
"""

from __future__ import annotations

import collections
from typing import Any, Union

import arrow
from sqlalchemy import and_, desc

from . import db


class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.Integer, nullable=False, index=True)
    timestamp = db.Column(db.Integer, nullable=False)
    co2 = db.Column(db.Integer, nullable=False)
    temperature = db.Column(db.Integer, nullable=False)
    uptime = db.Column(db.Integer, nullable=False)
    ntp_epoch = db.Column(db.Integer, nullable=False)
    boot_id = db.Column(db.Integer, nullable=False)


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.Integer, nullable=False, index=True)

    acq_period = db.Column(db.Integer, nullable=False)
    screen_mode = db.Column(db.Integer, nullable=False)
    last_calibration = db.Column(db.Integer, nullable=False)
    firmware_version = db.Column(db.Integer, nullable=False)
    hardware_info = db.Column(db.TEXT, nullable=False)
    reference_device = db.Column(db.Integer, nullable=False, default=0)

    building = db.Column(db.String, nullable=False, default="s/d")
    floor = db.Column(db.String, nullable=False, default="s/d")
    room = db.Column(db.String, nullable=False, default="s/d")

    last_seen = db.Column(db.Integer)
    last_co2 = db.Column(db.Integer)


def revgen(gen):
    """Reversed list from a generator."""
    return list(reversed(list(gen)))


def get_values(
    serialno: int, min_ts: int, limit: int
) -> tuple[list[int], list[int]]:
    """Get values from a given device, inversed sorted by timestamp.

    Use:
    - min_ts to specify the minimum timestamp.
    - limit to specify how many values will be returned.
    """
    if min_ts < 0:
        min_ts = arrow.now().timestamp + min_ts

    data = (
        Record.query.with_entities(Record.timestamp, Record.co2)
        .filter(
            and_(
                Record.serial_number == serialno,
                Record.timestamp >= min_ts,
                Record.co2 < 5000,
            )
        )
        .order_by(desc(Record.timestamp))
    )
    data = data.limit(limit).all()
    if not data:
        return [], []
    timestamp, values = zip(*data)
    return revgen(timestamp), revgen(values)


def load_devices():
    """Load devices and buildings (used in dash)."""
    buildings = {"s/d": "building-filter-NO"}
    devices = []

    for dev in Device.query.all():
        tmp = dict(dev.__dict__)
        tmp.pop("_sa_instance_state")
        devices.append(tmp)
        if dev.building not in buildings:
            buildings[dev.building] = "building-filter-%03d" % len(
                buildings
            )

    building_options = [
        dict(label=k, value=v) for k, v in buildings.items()
    ]

    return devices, buildings, building_options


def get_devices_by_status(
    consider_offline_sec=None,
) -> dict[Any, set[int]]:
    """ """
    from . import config
    from .shared import COLORS, color_from_value

    consider_offline_sec = (
        consider_offline_sec or config.CONSIDER_OFFLINE_SEC
    )
    out = {
        COLORS.OK: set(),
        COLORS.WARNING: set(),
        COLORS.DANGER: set(),
        COLORS.OFFLINE: set(),
    }
    for dev in Device.query.all():
        color = color_from_value(
            dev.last_co2, dev.last_seen, consider_offline_sec
        )
        out[color].add(dev.serial_number)

    return out


def calibration_range_from_date(val, nocal):
    DAY = 24 * 60 * 60
    cal_ranges = {
        "day": DAY,
        "week": 7 * DAY,
        "month": 30 * DAY,
        "year": 365 * DAY,
        "longer": None,
    }
    now = arrow.utcnow().timestamp
    if val == nocal:
        return "N/A"

    for k, delta in cal_ranges.items():
        if delta is None:
            return k
        if val > now - delta:
            return k

    raise ValueError("DELTAS for groupcal should end in None")


def summarize_devices(
    consider_offline_sec: int, nocal: int
) -> dict[str, Union[set[Any], int]]:
    from .shared import COLORS, color_from_value

    status = collections.defaultdict(set)
    firmware_version = collections.defaultdict(set)
    building = collections.defaultdict(set)
    last_calibration = collections.defaultdict(set)

    total = 0
    for dev in Device.query.all():
        if dev.last_seen is None:
            color = COLORS.OFFLINE
        else:
            color = color_from_value(
                dev.last_co2, dev.last_seen, consider_offline_sec
            )
        status[color].add(dev.serial_number)
        building[dev.building].add(dev.serial_number)
        firmware_version[dev.firmware_version].add(dev.serial_number)
        last_calibration[
            calibration_range_from_date(dev.last_calibration, nocal)
        ].add(dev.serial_number)
        total += 1

    return dict(
        by_status=status,
        by_firmware_version=firmware_version,
        by_building=building,
        by_last_calibration=last_calibration,
        total=total,
    )
