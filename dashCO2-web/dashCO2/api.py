"""
    dashCO2.api
    ~~~~~~~~~~~

    La api para los dispositivos consta de 4 enpoints:
    /now [GET]
        Hora en el servidor, útil cuando los clientes no pueden acceder al NTP.
    /register [POST]
        Registra un dispositivo en la base de datos.
    /store [POST]
        Registra una medición.
    /updates/<int:version> [GET]
        Versiones del firmware
"""


import dataclasses
import functools
import json

import arrow
import flask

from . import config
from .shared import get_latest_firmware_version

# Número que indica que version del firmware se usa para
# registrar el dispositivo.
_REGISTER = 1
# Número que indica que se desea la última version
_LATEST = 10


def int_or(value, default=0):
    """Helper function to convert to int or give a default value."""
    try:
        return int(value)
    except ValueError:
        return default


@dataclasses.dataclass(frozen=True)
class SensorHeader:
    """Helper class to deal with headers."""

    serial_number: int
    acq_period: int
    method: int
    last_calibration: int
    firmware_version: int
    screen_mode: int

    @classmethod
    def from_headers(cls, headers):
        return cls(
            serial_number=int(headers["SNO-SERIAL-NUMBER"]),
            acq_period=int_or(headers["SNO-ACQ-PERIOD"], 5000),
            method=int_or(headers.get("SNO-METHOD", "0"), 0),
            last_calibration=int_or(
                headers["SNO-USER-lastCalibration"], config.NO_CAL
            ),
            firmware_version=int_or(
                headers["SNO-USER-firmwareVersion"], _REGISTER
            ),
            screen_mode=int_or(
                headers.get("SNO-USER-screenMode", 0), 0
            ),
        )


def init_app(app, api_key):

    from .models import Device, Record, db

    if api_key:

        def require_appkey(view_function):
            @functools.wraps(view_function)
            def decorated_function(*args, **kwargs):
                if (
                    flask.request.headers.get("SNO-API-KEY")
                    and flask.request.headers.get("SNO-API-KEY")
                    == api_key
                ):
                    return view_function(*args, **kwargs)
                else:
                    flask.abort(401)

            return decorated_function

    else:

        def require_appkey(view_function):
            return view_function

    @app.route("/now")
    def now():
        """Time in the server. USed to sync client clock
        when NTP is not available."""
        return str(arrow.now().timestamp)

    @app.route("/register", methods=["POST"])
    @require_appkey
    def register():
        """Register a device in the system and
        then pushes the latest firmware."""

        try:
            content = flask.request.json
        except Exception as ex:
            app.logger.error(str(ex))
            return flask.jsonify()

        try:
            headers = SensorHeader.from_headers(flask.request.headers)
        except Exception as ex:
            app.logger.error(str(ex))
            return flask.jsonify()

        # app.logger.debug(headers)

        devs = Device.query.filter(
            Device.serial_number == headers.serial_number
        ).all()

        next_firmware = get_latest_firmware_version()
        app.logger.info(f"Next firmware: {next_firmware}")
        if devs:
            app.logger.warning(
                f"There is already {len(devs)} device registered "
                f"for {headers.serial_number}"
            )
        else:
            try:
                dev = Device(
                    serial_number=headers.serial_number,
                    acq_period=headers.acq_period,
                    screen_mode=0,
                    last_calibration=headers.last_calibration,
                    firmware_version=next_firmware,
                    hardware_info=json.dumps(
                        content["userRecord"]["hardwareInfo"]
                    ),
                )
                db.session.add(dev)
                db.session.commit()
            except Exception as ex:
                app.logger.error(str(ex))

        return flask.jsonify(
            dict(userServerPayload=dict(firmwareVersion=next_firmware))
        )

    @app.route("/store", methods=["POST"])
    @require_appkey
    def store():
        """Register a record in the database and handles"""

        try:
            headers = SensorHeader.from_headers(flask.request.headers)
        except Exception as ex:
            app.logger.error(f"Cannot parse headers: {ex}")
            return flask.jsonify()

        devs = Device.query.filter(
            Device.serial_number == headers.serial_number
        ).all()

        if not devs:
            app.logger.warning(
                f"No device found for {headers.serial_number}"
            )
            return flask.jsonify(
                dict(userServerPayload=dict(firmwareVersion=_REGISTER))
            )

        if len(devs) > 1:
            app.logger.error(
                f"{len(devs)} devices found for {headers.serial_number}"
            )

        record = flask.request.json

        # app.logger.debug(record)

        if headers.method == 0:
            return store_record_method0(headers, record, devs[0])
        elif headers.method == 1:
            return store_device_info_method1(headers, record, devs[0])

        app.logger.error(f"Unknown method: {headers.method}")
        return flask.jsonify()

    def store_record_method0(
        headers: SensorHeader, record: dict, dev: Device
    ):
        try:
            rec = Record(
                serial_number=headers.serial_number,
                timestamp=record["timestamp"],
                co2=record["userRecord"]["co2"],
                temperature=record["userRecord"]["temperature"],
                uptime=record["uptime"],
                ntp_epoch=record["ntpEpoch"],
                boot_id=record["bootID"],
            )
            db.session.add(rec)
            dev.last_seen = record["timestamp"]
            dev.last_co2 = record["userRecord"]["co2"]
            db.session.commit()
        except Exception as ex:
            app.logger.error(str(ex))

        payload = {}
        userServerPayload = {}

        if headers.acq_period != dev.acq_period:
            payload["acqPeriod"] = dev.acq_period

        # payload["devInfoCheck"] = 1

        if headers.screen_mode != dev.screen_mode:
            userServerPayload["screenMode"] = dev.screen_mode

        if headers.last_calibration != dev.last_calibration:
            date1, chk1 = (
                str(headers.last_calibration)[:-1],
                str(headers.last_calibration)[-1],
            )
            date2, chk2 = (
                str(dev.last_calibration)[:-1],
                str(dev.last_calibration)[-1],
            )

            # calibration is achieved in the following way.
            # 1.- The server changes the last digit (chk)
            # 2.- The device finds out this and recalibrates
            # 3.- The device changes date to the current date
            #     and set the last digit to chk.
            # 4.- The server updates its value
            # TODO: SIMPLIFY using the sendDeviceInfo method.

            if date1 != date2:
                # The device has been recalibrated,
                # update the value in the server
                dev.last_calibration = headers.last_calibration
                db.session.commit()
            elif chk1 != chk2:
                # The server changed its last digit,
                # send instruction to the device.
                userServerPayload[
                    "lastCalibration"
                ] = dev.last_calibration

        if headers.firmware_version != dev.firmware_version:
            userServerPayload["firmwareVersion"] = dev.firmware_version

        if userServerPayload:
            payload["userServerPayload"] = userServerPayload

        # app.logger.info(payload)
        return flask.jsonify(payload)

    def store_device_info_method1(
        headers: SensorHeader, record: dict, dev: Device
    ):
        try:
            dev.firmware_version = headers.firmware_version
            dev.last_calibration = headers.last_calibration
            dev.hardware_info = json.dumps(record)
            db.session.add(dev)
            db.session.commit()
        except Exception as ex:
            app.logger.error(str(ex))

        payload = {}
        userServerPayload = {}

        if headers.acq_period != dev.acq_period:
            payload["acqPeriod"] = dev.acq_period

        if headers.screen_mode != dev.screen_mode:
            userServerPayload["screenMode"] = dev.screen_mode

        if headers.last_calibration != dev.last_calibration:
            date1, chk1 = (
                str(headers.last_calibration)[:-1],
                str(headers.last_calibration)[-1],
            )
            date2, chk2 = (
                str(dev.last_calibration)[:-1],
                str(dev.last_calibration)[-1],
            )

            # calibration is achieved in the following way.
            # 1.- The server changes the last digit (chk)
            # 2.- The device finds out this and recalibrates
            # 3.- The device changes date to the current date
            #     and set the last digit to chk.
            # 4.- The server updates its value

            if date1 != date2:
                # The device has been recalibrated,
                # update the value in the server
                dev.last_calibration = headers.last_calibration
                db.session.commit()
            elif chk1 != chk2:
                # The server changed its last digit,
                # send instruction to the device.
                userServerPayload[
                    "lastCalibration"
                ] = dev.last_calibration

        if headers.firmware_version != dev.firmware_version:
            userServerPayload["firmwareVersion"] = dev.firmware_version

        if userServerPayload:
            payload["userServerPayload"] = userServerPayload

        # app.logger.info(payload)
        return flask.jsonify(payload)

    @app.route("/updates/<int:version>")
    def updates(version):
        if version == _REGISTER:
            version = "first"
        elif version == _LATEST:
            version = get_latest_firmware_version()
        return flask.send_from_directory(
            "/firmware", f"{version}.ino.bin"
        )
