"""
    dashCO2.crud
    ~~~~~~~~~~~~

    Infraestructura para listar y exportar mediciones y configurar
    dispositivos.

"""

import operator

import arrow
from flask import (
    flash,
    has_app_context,
    make_response,
    redirect,
    request,
)
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.actions import action
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import rules
from flask_admin.helpers import get_redirect_target
from markupsafe import Markup
from sqlalchemy import and_, desc, func
from wtforms import Form, HiddenField, IntegerField, StringField
from wtforms.validators import AnyOf, InputRequired, NumberRange

from .shared import DAY


def init_app(app, auth=None):

    if auth is None:

        class Auth:
            """Dummy auth in case it is not provided."""

            users = ("admin",)

            @staticmethod
            def get_current_user(*args, **kwargs):
                return "admin"

            @staticmethod
            def login_required(*args, **kwargs):
                def _inner(f):
                    return f

                return _inner

        auth = Auth()

    from . import config, models, shared
    from .models import Record
    from .shared import (
        COLORS,
        firmware_version_exists,
        get_latest_firmware_version,
    )

    @app.template_filter()
    def insert_logout(text):
        """Convert a string to all caps."""
        for prefix in ("http://", "https://"):
            sz = len(prefix)
            if text[:sz] == prefix:
                return prefix + "log:out@" + text[sz:]
        return text

    class SecureModelView(ModelView):
        def is_accessible(self):
            return auth.get_current_user() in auth.users

        def inaccessible_callback(self, name, **kwargs):
            # redirect to login page if user doesn't have access
            return redirect("/admin")

        def get_current_user(self):
            return auth.get_current_user()

    def format_utc(value):
        return (
            arrow.Arrow.utcfromtimestamp(value)
            .to(config.TIMEZONE)
            .format("YYYY-MM-DD HH:mm:ss")
        )

    ##############
    # Formatters
    ##############

    def _timestamp_formatter(column):
        def _inner(view, context, model, name):
            value = getattr(model, column)
            if value:
                return format_utc(value)
            else:
                return ""

        return _inner

    def _last_calibration_formatter(view, context, model, name):
        value = model.last_calibration
        if value == config.NO_CAL:
            return "N/A"
        if value:
            return format_utc(value)
        else:
            return ""

    def _last_seen_formatter(view, context, model, name):
        rec = (
            Record.query.filter(
                Record.serial_number == model.serial_number
            )
            .order_by(desc(Record.timestamp))
            .first()
        )
        if rec:
            return format_utc(rec.timestamp)
        else:
            return "N/A"

    def _links_formatter(view, context, model, name):
        base = f"/admin/%s/?flt1_serial_number_equals={model.serial_number}"
        day_link = base % "day"
        week_link = base % "week"
        month_link = base % "month"
        return Markup(
            f"<a href='{day_link}'>24 h</a> <br/> "
            f"<a href='{week_link}'>7 d</a> <br/> "
            f"<a href='{month_link}'>30 d</a>"
        )

    def _dict_formatter(column, conversion, default="N/A"):
        def _inner(view, context, model, name):
            return conversion.get(getattr(model, column), default)

        return _inner

    #########
    # Vistas
    #########

    class RecordView(SecureModelView):
        named_filter_urls = True

        can_delete = False
        can_create = False
        can_edit = False
        can_view_details = True

        column_searchable_list = ["serial_number"]
        column_filters = ["serial_number"]
        can_export = True

        column_formatters = {
            "timestamp": _timestamp_formatter("timestamp"),
            "ntp_epoch": _timestamp_formatter("ntp_epoch"),
        }

    class WithFilter:
        def get_query(self):
            return self.session.query(self.model).filter(
                self._my_filter()
            )

        def get_count_query(self):
            return (
                self.session.query(func.count("*"))
                .select_from(self.model)
                .filter(self._my_filter())
            )

    class RelativeTemporalFilter(WithFilter):
        _column = ""
        _delta_ts = 0
        _operator = None

        def _my_filter(self):
            now = arrow.utcnow().timestamp

            if self._operator == "between":
                return getattr(self.model, self._column).between(
                    now - self._delta_ts[0], now - self._delta_ts[1]
                )

            return self._operator(
                getattr(self.model, self._column), now - self._delta_ts
            )

    class DayView(RelativeTemporalFilter, RecordView):
        _column = "timestamp"
        _delta_ts = DAY
        _operator = operator.gt

    class WeekView(RelativeTemporalFilter, RecordView):
        _column = "timestamp"
        _delta_ts = 7 * DAY
        _operator = operator.gt

    class MonthView(RelativeTemporalFilter, RecordView):
        _column = "timestamp"
        _delta_ts = 30 * DAY
        _operator = operator.gt

    class HiddenView:
        def is_visible(self):
            return False

    class DeviceView(SecureModelView):
        @action("firmware", "Actualizar firmware")
        def action_firmware_update(self, ids):
            url = get_redirect_target() or self.get_url(".index_view")
            sigil = "&" if "?" in url else "?"
            return redirect(
                url + f"{sigil}action=firmware_update", code=307
            )

        @action("recalibrate", "Recalibrar")
        def action_recalibrate(self, ids):
            url = get_redirect_target() or self.get_url(".index_view")
            sigil = "&" if "?" in url else "?"
            return redirect(
                url + f"{sigil}action=recalibrate", code=307
            )

        @action("screen_mode", "Modo pantalla")
        def action_screen_mode(self, ids):
            url = get_redirect_target() or self.get_url(".index_view")
            sigil = "&" if "?" in url else "?"
            return redirect(
                url + f"{sigil}action=screen_mode", code=307
            )

        @action("acq_period", "Período de adquisición")
        def action_acq_period(self, ids):
            url = get_redirect_target() or self.get_url(".index_view")
            sigil = "&" if "?" in url else "?"
            return redirect(url + f"{sigil}action=acq_period", code=307)

        @expose("/", methods=["POST"])
        def index(self):
            if request.method == "POST":
                url = get_redirect_target() or self.get_url(
                    ".index_view"
                )
                action = request.args.get("action", None)
                if action == "firmware_update":
                    change_form = ChangeFirmwareForm()
                    new_title = "Actualizar Firmware"
                    msg = f"Última versión: {get_latest_firmware_version()}"
                elif action == "recalibrate":
                    change_form = RecalibrateForm()
                    new_title = "Recalibrar"
                    msg = "Escriba 'recalibrar' para confirmar (sin comillas)"
                elif action == "screen_mode":
                    change_form = ChangeScreenModeForm()
                    new_title = "Modo pantalla"
                    msg = ""
                elif action == "acq_period":
                    change_form = ChangeAcqPeriodForm()
                    new_title = "Período de adquisición [ms]"
                    msg = ""
                else:
                    return self.index_view()

                ids = request.form.getlist("rowid")
                joined_ids = ",".join(ids)
                change_form.ids.data = joined_ids
                self._template_args["modal_title"] = new_title
                self._template_args["modal_url"] = url
                self._template_args["modal_change_form"] = change_form
                self._template_args["modal_change_modal"] = True
                self._template_args["modal_next"] = f"device.{action}"
                self._template_args["modal_count"] = len(ids)
                self._template_args["modal_msg"] = msg
                return self.index_view()

        @expose("/firmware_update/", methods=["POST"])
        def firmware_update(self):
            if request.method == "POST":
                if self.get_current_user() != "admin":
                    flash(
                        f"El usuario {self.get_current_user()} no "
                        f"tiene permisos para actualizar el firmware.",
                        category="error",
                    )
                    return redirect(self.get_url(".index_view"))
                url = get_redirect_target() or self.get_url(
                    ".index_view"
                )
                change_form = ChangeFirmwareForm(request.form)
                ids = change_form.ids.data.split(",")
                if change_form.validate():
                    firmware_version = change_form.firmware_version.data

                    if not firmware_version_exists(firmware_version):
                        flash(
                            f"La version {firmware_version} del firmware"
                            f"no está disponible en el servidor.",
                            category="error",
                        )
                        return redirect(url)

                    _update_mappings = [
                        {
                            "id": rowid,
                            "firmware_version": firmware_version,
                        }
                        for rowid in ids
                    ]
                    self.session.bulk_update_mappings(
                        models.Device, _update_mappings
                    )
                    self.session.commit()
                    flash(
                        "Set firmware_version for {} device{} to {}.".format(
                            len(ids),
                            "s" if len(ids) > 1 else "",
                            firmware_version,
                        ),
                        category="info",
                    )
                    return redirect(url)
                else:
                    # Form didn't validate
                    self._template_args[
                        "modal_title"
                    ] = "Actualizar Firmware"
                    self._template_args["modal_url"] = url
                    self._template_args[
                        "modal_change_form"
                    ] = change_form
                    self._template_args["modal_change_modal"] = True
                    self._template_args[
                        "modal_next"
                    ] = "device.firmware_update"
                    self._template_args["modal_count"] = len(ids)
                    return self.index_view()

        @expose("/recalibrate/", methods=["POST"])
        def recalibrate(self):
            if request.method == "POST":
                if self.get_current_user() != "admin":
                    flash(
                        f"El usuario {self.get_current_user()} no tiene "
                        f"permisos para actualizar el iniciar "
                        f"una calibración.",
                        category="error",
                    )
                    return redirect(self.get_url(".index_view"))
                url = get_redirect_target() or self.get_url(
                    ".index_view"
                )
                change_form = RecalibrateForm(request.form)
                ids = change_form.ids.data.split(",")
                ids = tuple(int(val) for val in ids)
                if change_form.validate():
                    devices = models.Device.query.filter(
                        models.Device.id.in_(ids)
                    ).all()
                    for dev in devices:
                        if str(dev.last_calibration)[-1] == "9":
                            dev.last_calibration -= 9
                        else:
                            dev.last_calibration += 1

                    self.session.commit()
                    flash(
                        f"La recalibración se ha iniciado para {len(devices)} "
                        f"dispositivos{'s' if len(devices) > 1 else ''}. "
                        f"Puede demorar un poco ...",
                        category="info",
                    )
                    return redirect(url)
                else:
                    # Form didn't validate
                    self._template_args["modal_title"] = "Recalibrar"
                    self._template_args["modal_url"] = url
                    self._template_args[
                        "modal_change_form"
                    ] = change_form
                    self._template_args["modal_change_modal"] = True
                    self._template_args[
                        "modal_next"
                    ] = "device.recalibrate"
                    self._template_args["modal_count"] = len(ids)
                    return self.index_view()

        @expose("/screen_mode/", methods=["POST"])
        def screen_mode(self):
            if request.method == "POST":
                url = get_redirect_target() or self.get_url(
                    ".index_view"
                )
                change_form = ChangeScreenModeForm(request.form)
                ids = change_form.ids.data.split(",")
                if change_form.validate():
                    screen_mode = change_form.screen_mode.data
                    _update_mappings = [
                        {"id": rowid, "screen_mode": screen_mode}
                        for rowid in ids
                    ]
                    self.session.bulk_update_mappings(
                        models.Device, _update_mappings
                    )
                    self.session.commit()
                    flash(
                        "Set screen_mode for {} device{} to {}.".format(
                            len(ids),
                            "s" if len(ids) > 1 else "",
                            screen_mode,
                        ),
                        category="info",
                    )
                    return redirect(url)
                else:
                    # Form didn't validate
                    self._template_args["modal_title"] = "Modo pantalla"
                    self._template_args["modal_url"] = url
                    self._template_args[
                        "modal_change_form"
                    ] = change_form
                    self._template_args["modal_change_modal"] = True
                    self._template_args[
                        "modal_next"
                    ] = "device.screen_mode"
                    self._template_args["modal_count"] = len(ids)
                    return self.index_view()

        @expose("/acq_period/", methods=["POST"])
        def acq_period(self):
            if request.method == "POST":
                url = get_redirect_target() or self.get_url(
                    ".index_view"
                )
                change_form = ChangeAcqPeriodForm(request.form)
                ids = change_form.ids.data.split(",")
                if change_form.validate():
                    acq_period = change_form.acq_period.data
                    _update_mappings = [
                        {"id": rowid, "acq_period": acq_period}
                        for rowid in ids
                    ]
                    self.session.bulk_update_mappings(
                        models.Device, _update_mappings
                    )
                    self.session.commit()
                    flash(
                        "Set acq_period for {} device{} to {}.".format(
                            len(ids),
                            "s" if len(ids) > 1 else "",
                            acq_period,
                        ),
                        category="info",
                    )
                    return redirect(url)
                else:
                    # Form didn't validate
                    self._template_args[
                        "modal_title"
                    ] = "Período de adquisición [ms]"
                    self._template_args["modal_url"] = url
                    self._template_args[
                        "modal_change_form"
                    ] = change_form
                    self._template_args["modal_change_modal"] = True
                    self._template_args[
                        "modal_next"
                    ] = "device.acq_period"
                    self._template_args["modal_count"] = len(ids)
                    return self.index_view()

        column_default_sort = "serial_number"

        list_template = "custom_list.html"

        named_filter_urls = True

        can_delete = False
        can_create = False
        can_view_details = True

        column_searchable_list = ["serial_number"]
        column_filters = [
            "serial_number",
            "building",
            "floor",
            "room",
            "firmware_version",
            "reference_device",
        ]
        can_export = True

        cols = []
        column_list = [
            "serial_number",
            "acq_period",
            "screen_mode",
            "last_calibration",
            "firmware_version",
            "reference_device",
            "building",
            "floor",
            "room",
        ]
        column_list += ["last_seen", "links"]

        column_details_list = [
            "serial_number",
            "acq_period",
            "screen_mode",
            "last_calibration",
            "firmware_version",
            "reference_device",
            "building",
            "floor",
            "room",
            "hardware_info",
        ]
        column_details_list += ["last_seen", "links"]

        _user_form_edit_rules = (
            "acq_period",
            "screen_mode",
            "building",
            "floor",
            "room",
        )

        _admin_form_edit_rules = _user_form_edit_rules + (
            "firmware_version",
            "last_calibration",
            "reference_device",
        )

        column_formatters = {
            "screen_mode": _dict_formatter(
                "screen_mode", {0: "on", 1: "minimal", 2: "off"}
            ),
            "last_calibration": _last_calibration_formatter,
            "last_seen": _last_seen_formatter,
            "links": _links_formatter,
        }

        form_choices = {
            "screen_mode": [(0, "full"), (1, "minimal"), (2, "off")],
        }

        form_args = dict(
            acq_period=dict(
                validators=[
                    NumberRange(
                        5 * 1000,
                        10 * 60 * 1000,
                        message="Usar valores entre 5000 ms y 600000 ms "
                        "(5 seg y 10 min)",
                    )
                ]
            ),
        )

        @property
        def _form_edit_rules(self):
            return rules.RuleSet(self, self.form_edit_rules)

        @_form_edit_rules.setter
        def _form_edit_rules(self, value):
            pass

        @property
        def form_edit_rules(self):
            if (
                not has_app_context()
                or self.get_current_user() == "admin"
            ):
                return self._admin_form_edit_rules

            return self._user_form_edit_rules

    class LastCalibrationDayView(
        HiddenView, RelativeTemporalFilter, DeviceView
    ):
        _column = "last_calibration"
        _delta_ts = DAY
        _operator = operator.gt

    class LastCalibrationWeekView(
        HiddenView, RelativeTemporalFilter, DeviceView
    ):
        _column = "last_calibration"
        _delta_ts = (7 * DAY, DAY)
        _operator = "between"

    class LastCalibrationMonthView(
        HiddenView, RelativeTemporalFilter, DeviceView
    ):
        _column = "last_calibration"
        _delta_ts = (30 * DAY, 7 * DAY)
        _operator = "between"

    class LastCalibrationYearView(
        HiddenView, RelativeTemporalFilter, DeviceView
    ):
        _column = "last_calibration"
        _delta_ts = (365 * DAY, 30 * DAY)
        _operator = "between"

    class LastCalibrationLongerView(HiddenView, WithFilter, DeviceView):
        def _my_filter(self):
            abs_ts = arrow.utcnow().timestamp - 365 * DAY
            return and_(
                models.Device.last_calibration != config.NO_CAL,
                models.Device.last_calibration < abs_ts,
            )

    class LastCalibrationNoView(HiddenView, WithFilter, DeviceView):
        def _my_filter(self):
            return models.Device.last_calibration == config.NO_CAL

    class ChangeFirmwareForm(Form):
        ids = HiddenField()
        firmware_version = IntegerField(validators=[InputRequired()])

    class RecalibrateForm(Form):
        ids = HiddenField()
        confirmation = StringField(
            validators=[
                AnyOf(
                    ["recalibrar"],
                    message="Escriba 'recalibrar' para confirmar "
                    "(sin comillas)",
                )
            ]
        )

    class ChangeScreenModeForm(Form):
        ids = HiddenField()
        screen_mode = IntegerField(
            validators=[
                AnyOf(
                    (0, 1, 2),
                    message="Usar 0 (full), 1 (minimal) y 2 (off)",
                )
            ]
        )

    class ChangeAcqPeriodForm(Form):
        ids = HiddenField()
        acq_period = IntegerField(
            validators=[
                NumberRange(
                    5 * 1000,
                    10 * 60 * 1000,
                    message="Usar valores entre 5000 ms y 600000 ms "
                    "(5 seg y 10 min)",
                )
            ]
        )

    class ByStatusView(HiddenView, WithFilter, DeviceView):

        _status = None

        def is_visible(self):
            return False

        def _my_filter(self):
            try:
                offline_secs = int(
                    request.args.get("offline_secs", None)
                )
            except Exception:
                offline_secs = None
            grouped_devices = models.get_devices_by_status(offline_secs)
            return models.Device.serial_number.in_(
                grouped_devices[self._status]
            )

    class ByOfflineStatus(ByStatusView):
        _status = COLORS.OFFLINE

    class ByDangerStatus(ByStatusView):
        _status = COLORS.DANGER

    class ByWarningStatus(ByStatusView):
        _status = COLORS.WARNING

    class ByOkStatus(ByStatusView):
        _status = COLORS.OK

    class IndexView(HiddenView, AdminIndexView):
        @expose("/login")
        @auth.login_required
        def login(self):
            return redirect(self.get_url(".index"))

        @expose("/")
        @auth.login_required(optional=True)
        def index(self):
            current_user = auth.get_current_user()
            if current_user is None:
                return self.render("anon.html")

            try:
                offline_secs = int(
                    request.args.get(
                        "offline_secs", config.CONSIDER_OFFLINE_SEC
                    )
                )
            except Exception:
                offline_secs = config.CONSIDER_OFFLINE_SEC

            summary = models.summarize_devices(
                offline_secs, config.NO_CAL
            )

            rendered = self.render(
                "my_index.html",
                by_status=summary["by_status"],
                by_firmware_version=summary["by_firmware_version"],
                by_last_calibration=summary["by_last_calibration"],
                by_building=summary["by_building"],
                COLORS=COLORS,
                total=summary["total"],
                last_firmware_version=get_latest_firmware_version(),
                current_user=current_user,
            )
            resp = make_response(rendered)
            resp.set_cookie(
                shared.MAGIC_COOKIE_KEY,
                shared.MAGIC_COOKIE,
                samesite="Lax",
            )
            return resp

    admin = Admin(
        app,
        name="Monitoreo de CO2",
        base_template="my_base.html",
        template_mode="bootstrap4",
        index_view=IndexView(),
    )

    admin.add_view(
        DeviceView(models.Device, models.db.session, name="Sensores")
    )
    admin.add_view(
        RecordView(models.Record, models.db.session, name="Registros")
    )
    admin.add_view(
        DayView(
            models.Record,
            models.db.session,
            endpoint="/day",
            name="Últimas 24h",
        )
    )
    admin.add_view(
        WeekView(
            models.Record,
            models.db.session,
            endpoint="/week",
            name="Últimos 7d",
        )
    )
    admin.add_view(
        MonthView(
            models.Record,
            models.db.session,
            endpoint="/month",
            name="Últimos 30d",
        )
    )

    admin.add_view(
        ByOkStatus(
            models.Device,
            models.db.session,
            endpoint="/special/by_status/ok",
        )
    )
    admin.add_view(
        ByOfflineStatus(
            models.Device,
            models.db.session,
            endpoint="/special/by_status/offline",
        )
    )
    admin.add_view(
        ByWarningStatus(
            models.Device,
            models.db.session,
            endpoint="/special/by_status/warning",
        )
    )
    admin.add_view(
        ByDangerStatus(
            models.Device,
            models.db.session,
            endpoint="/special/by_status/danger",
        )
    )

    admin.add_view(
        LastCalibrationDayView(
            models.Device,
            models.db.session,
            endpoint="/special/last_calibration/day",
        )
    )
    admin.add_view(
        LastCalibrationWeekView(
            models.Device,
            models.db.session,
            endpoint="/special/last_calibration/week",
        )
    )
    admin.add_view(
        LastCalibrationMonthView(
            models.Device,
            models.db.session,
            endpoint="/special/last_calibration/month",
        )
    )
    admin.add_view(
        LastCalibrationYearView(
            models.Device,
            models.db.session,
            endpoint="/special/last_calibration/year",
        )
    )
    admin.add_view(
        LastCalibrationLongerView(
            models.Device,
            models.db.session,
            endpoint="/special/last_calibration/longer",
        )
    )
    admin.add_view(
        LastCalibrationNoView(
            models.Device,
            models.db.session,
            endpoint="/special/last_calibration/nocal",
        )
    )
