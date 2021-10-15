"""
    dashCO2
    ~~~~~~~

    Aplicación web para recibir y mostrar datos de los medidores de CO2.
"""

import secrets as pysecrets
from logging.config import dictConfig

from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(debug=False):
    from . import config, models

    dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {
                    "format": "[%(asctime)s] %(levelname)s "
                    "in %(module)s: %(message)s",
                }
            },
            "handlers": {
                "wsgi": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://flask.logging.wsgi_errors_stream",
                    "formatter": "default",
                }
            },
            "root": {"level": "DEBUG", "handlers": ["wsgi"]},
        }
    )

    flask_app = Flask(__name__, instance_relative_config=True)

    flask_app.config["SECRET_KEY"] = pysecrets.token_urlsafe(16)
    flask_app.config[
        "SQLALCHEMY_DATABASE_URI"
    ] = config.SQLALCHEMY_DATABASE_URI
    flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(flask_app)

    with flask_app.app_context():
        db.create_all()

        if "memory" in flask_app.config["SQLALCHEMY_DATABASE_URI"]:
            # Datos de demo para base en memoria.
            flask_app.logger.info("Database contains no records.")
            dev = models.Device(
                serial_number=100,
                acq_period=5000,
                screen_mode=0,
                last_calibration=12302023,
                firmware_version=2021071801,
                hardware_info="",
            )
            db.session.add(dev)

            rec = models.Record(
                serial_number=10,
                timestamp=14302023,
                co2=123,
                temperature=12,
                uptime=412,
                ntp_epoch=14302023,
                boot_id=231212,
            )
            db.session.add(rec)

            db.session.commit()

    from . import api, secrets

    api.init_app(flask_app, secrets.API_KEY)

    try:
        from . import _basicauth

        auth = _basicauth.init_app(flask_app)
    except ImportError:
        pass

    from . import crud

    crud.init_app(flask_app, auth)

    from . import dashapp

    dash_app = dashapp.build_app(
        server=flask_app, url_base_pathname="/dashboard/"
    )

    if debug:
        dash_app.enable_dev_tools(debug)

    @flask_app.route("/")
    def index():
        return redirect("/admin")

    return flask_app
