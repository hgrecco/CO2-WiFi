"""
    dashCO2.shared
    ~~~~~~~~~~~~~~

"""

import math
import pathlib
import secrets
from typing import Union

import arrow

from . import config

MAGIC_COOKIE_KEY = "CO2_TOKEN"
MAGIC_COOKIE = secrets.token_urlsafe(16)

DAY = 24 * 60 * 60


def check_cookie(value):
    return secrets.compare_digest(MAGIC_COOKIE, value)


def get_latest_firmware_version() -> Union[int, None]:
    try:
        stem, _ = sorted(
            pathlib.Path(config.FIRMWARE_FOLDER).glob("20*.ino.bin")
        )[-1].name.split(".", 1)
        return int(stem)
    except IndexError:
        return None


def firmware_version_exists(version: int) -> bool:
    return (
        pathlib.Path(config.FIRMWARE_FOLDER) / f"{version}.ino.bin"
    ).exists()


class COLORS:
    OFFLINE = "#666"
    OK = "#92e0d3"
    WARNING = "#f4d44d"
    DANGER = "#f45060"


def color_from_value(
    value,
    timestamp: float = None,
    consider_offline_sec=config.CONSIDER_OFFLINE_SEC,
) -> COLORS:
    if timestamp:
        try:
            if not isinstance(timestamp, (int, float)):
                timestamp = timestamp()
            if (
                arrow.utcnow().float_timestamp - timestamp
                > consider_offline_sec
            ):
                return COLORS.OFFLINE
        except Exception:
            raise Exception(
                (
                    arrow.utcnow().float_timestamp,
                    timestamp,
                    config.CONSIDER_OFFLINE_SEC,
                )
            )

    if math.isnan(value):
        return COLORS.OFFLINE

    elif value > config.RANGES.DANGER:
        return COLORS.DANGER

    elif value > config.RANGES.WARNING:
        return COLORS.WARNING

    return COLORS.OK
