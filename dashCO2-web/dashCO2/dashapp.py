"""
    dashCO2.dashapp
    ~~~~~~~~~~~~~~~

    Applicación en dash
"""

import arrow
import dash
import dash_core_components as dcc
import dash_daq as daq
import dash_html_components as html
import plotly.graph_objs as go
from dash.dependencies import Input, Output

from . import config, models
from .shared import COLORS, color_from_value

SPARKLINE_LAYOUT = {
    "uirevision": True,
    "margin": dict(l=0, r=0, t=4, b=4, pad=0),
    "xaxis": dict(
        showline=False,
        showgrid=False,
        zeroline=False,
        showticklabels=False,
    ),
    "yaxis": dict(
        showline=False,
        showgrid=False,
        zeroline=False,
        showticklabels=False,
    ),
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
}


def build_banner(dash_app):
    return html.Div(
        id="banner",
        className="banner",
        children=[
            html.Div(
                id="banner-logo",
                children=[
                    html.Img(
                        id="logo",
                        src=dash_app.get_asset_url("logo-exactas.png"),
                    ),
                ],
            ),
            html.Div(
                id="banner-text",
                className="row metric-row metric-row-up",
                children=[html.H5("Monitoreo de CO2")],
            ),
            html.Div(
                id="banner-summary",
                className="row metric-row",
                children=[
                    "DIA y HORA",
                    daq.Indicator(
                        id="summary-ok",
                        value=True,
                        color=COLORS.OK,
                        size=12,
                        className="indicator",
                    ),
                    " N",
                    daq.Indicator(
                        id="summary-warning",
                        value=True,
                        color=COLORS.WARNING,
                        size=12,
                        className="indicator",
                    ),
                    " N",
                    daq.Indicator(
                        id="summary-danger",
                        value=True,
                        color=COLORS.DANGER,
                        size=12,
                        className="indicator",
                    ),
                    " N",
                    daq.Indicator(
                        id="summary-offline",
                        value=True,
                        color=COLORS.OFFLINE,
                        size=12,
                        className="indicator",
                    ),
                    " N",
                ],
            ),
        ],
    )


def build_header():
    return html.Div(
        className="section-banner",
        style={"width": "100%", "display": "inline-block"},
        children=[
            "Sensores",
            html.Div(
                id="subsection-banner",
                children=[
                    dcc.Checklist(
                        options=[
                            dict(
                                label="Ver valores", value="view-values"
                            ),
                        ],
                        value=["view-values"],
                        id="view-options",
                        className="checklist-smoothing",
                        labelStyle={"display": "inline-block"},
                        labelClassName="mleft",
                    ),
                    html.Div(style=dict(width="35px")),
                    dcc.Checklist(
                        options=[],
                        value=[],
                        id="filter-buildings",
                        className="checklist-smoothing",
                        labelStyle={"display": "inline-block"},
                        labelClassName="mleft",
                    ),
                ],
                style={"float": "right", "display": "flex"},
            ),
        ],
    )


def build_box(
    device: dict,
    dev_recent_measurements: (list, list),
    buildings,
    view_options=(),
):

    devid = device["id"]
    serial_number = device["serial_number"]
    floor = device["floor"]
    box_title = device["room"]
    building = device["building"]

    if box_title == "s/d":
        box_title = f"s/n {serial_number}"

    ref_serial_no = reference_value = None
    # if 'view-reference' in view_options:
    #     ref_serial_no, reference_value = get_reference_value(serialno)

    x, y = dev_recent_measurements
    if x:
        current_value = y[-1]
        color = color_from_value(current_value, x[-1])

        # if reference_value is None:
        #     current_value_str = f"{current_value}"
        # else:
        #     current_value_str = f"{current_value - reference_value:+}"

        fig = go.Figure(
            {
                "data": [
                    {
                        "x": list(x),
                        "y": list(y),
                        "mode": "lines",
                        "name": f"sparkline-line-{serial_number}-id",
                        "line": {"color": "#888", "width": 3},
                    }
                ],
                "layout": SPARKLINE_LAYOUT,
            }
        )
    else:
        current_value = "s/d"
        color = COLORS.OFFLINE
        fig = go.Figure(
            {
                "layout": SPARKLINE_LAYOUT,
            }
        )

    xmax = arrow.utcnow().float_timestamp
    xmin = xmax - config.DISPLAY_LEN_SEC
    fig.update_layout(xaxis_range=[xmin, xmax], yaxis_range=[0, 1200])

    fig.add_hline(
        config.RANGES.OK,
        line_dash="dot",
        line_width=1,
        line_color=COLORS.OK,
    )
    fig.add_hline(
        config.RANGES.WARNING,
        line_dash="dot",
        line_width=1,
        line_color=COLORS.WARNING,
    )
    fig.add_hline(
        config.RANGES.DANGER,
        line_dash="dot",
        line_width=1,
        line_color=COLORS.DANGER,
    )

    return html.Div(
        className="grid-item " + buildings[building],
        children=[
            html.Div(
                id=f"header-{serial_number}-id",
                className="header",
                children=[
                    daq.Indicator(
                        id=f"indicator-{serial_number}-id",
                        value=True,
                        color=color,
                        size=12,
                        style={"margin": "5px", "float": "right"},
                    ),
                    box_title,
                ],
            ),
            html.Div(
                id=f"mainbody-{serial_number}-id",
                className="mainbody",
                children=[
                    dcc.Graph(
                        id=f"sparkline-{serial_number}-id",
                        className="sparkline-graph",
                        config={
                            "staticPlot": False,
                            "editable": False,
                            "displayModeBar": False,
                        },
                        figure=fig,
                    ),
                    html.Div(
                        id=f"bigvalue-{serial_number}-id",
                        className="bigvalue",
                        children=f"{current_value}",
                        style={"color": color},
                    ),
                    html.Div(
                        id=f"bigvalue-delta-{serial_number}-id",
                        className="bigvalue-delta",
                        children=f"Δ {current_value - reference_value} "
                        f"({ref_serial_no})",
                        style={"color": color},
                    )
                    if ref_serial_no is not None
                    else None,
                ],
            ),
            html.Div(
                id=f"footer-{serial_number}-id",
                className="footer",
                children=dcc.Link(
                    href=f"/admin/device/details/?id={devid}",
                    children=f"Nivel {floor} - {building} "
                    f"(s/n {serial_number})",
                    target="_blank",
                    className="footer",
                ),
            ),
        ],
    )


def build_app(**kwargs):

    dash_app = dash.Dash(
        __name__,
        meta_tags=[
            {
                "name": "viewport",
                "content": "width=device-width, initial-scale=1",
            }
        ],
        **kwargs,
    )

    @dash_app.callback(
        [
            Output("devices", "data"),
            Output("buildings", "data"),
            Output("filter-buildings", "options"),
        ],
        [Input("interval-component-devices", "n_intervals")],
    )
    def update_dbb(interval_value):
        return models.load_devices()

    @dash_app.callback(
        [
            Output("recent-measurements", "data"),
            Output("last-update", "data"),
        ],
        [
            Input("devices", "data"),
            Input("interval-component-records", "n_intervals"),
        ],
    )
    def update_recent_measurements(devices, interval_value):
        out = {}
        for dev in devices:
            serial_number = dev["serial_number"]
            out[str(serial_number)] = models.get_values(
                serial_number, -config.DISPLAY_LEN_SEC, 5000
            )
        return out, arrow.now(config.TIMEZONE).format(
            "YYYY-MM-DD HH:mm:ss"
        )

    @dash_app.callback(
        Output("summary-count", "data"),
        Input("recent-measurements", "data"),
    )
    def update_summary_count(recent_measurements):
        cnt_ok = cnt_warning = cnt_danger = cnt_offline = 0
        for k, (x, y) in recent_measurements.items():
            if not x:
                cnt_offline += 1
                continue

            col = color_from_value(y[-1], x[-1])
            if col == COLORS.OK:
                cnt_ok += 1
            elif col == COLORS.WARNING:
                cnt_warning += 1
            elif col == COLORS.WARNING:
                cnt_danger += 1
            elif col == COLORS.OFFLINE:
                cnt_offline += 1

        return cnt_ok, cnt_warning, cnt_danger, cnt_offline

    @dash_app.callback(
        Output("grid-content", "children"),
        Input("devices", "data"),
        Input("recent-measurements", "data"),
        Input("buildings", "data"),
        Input("view-options", "value"),
    )
    def update_boxes(
        devices, recent_measurements, buildings, view_options
    ):
        out = []
        for dev in devices:
            out.append(
                build_box(
                    dev,
                    recent_measurements[str(dev["serial_number"])],
                    buildings,
                    view_options,
                )
            )
        return out

    @dash_app.callback(
        Output("grid-content", "className"),
        Input("view-options", "value"),
    )
    def update_value_visibility(view_options):
        if "view-values" in view_options:
            return "grid"
        return "grid hide-bigvalue"

    @dash_app.callback(
        Output("banner-summary", "children"),
        Input("last-update", "data"),
        Input("summary-count", "data"),
    )
    def update_banner_summary(last_update, summary_count):
        cnt_ok, cnt_warning, cnt_danger, cnt_offline = summary_count
        return [
            f"{last_update}",
            daq.Indicator(
                id="summary-ok",
                value=True,
                color=COLORS.OK,
                size=12,
                className="indicator",
            ),
            html.Div(
                className="row metric-row",
                children=[
                    f"{cnt_ok:03d}",
                    daq.Indicator(
                        id="summary-warning",
                        value=True,
                        color=COLORS.WARNING,
                        size=12,
                        className="indicator",
                    ),
                    f"{cnt_warning:03d}",
                    daq.Indicator(
                        id="summary-danger",
                        value=True,
                        color=COLORS.DANGER,
                        size=12,
                        className="indicator",
                    ),
                    f"{cnt_danger:03d}",
                    daq.Indicator(
                        id="summary-offline",
                        value=True,
                        color=COLORS.OFFLINE,
                        size=12,
                        className="indicator",
                    ),
                    f"{cnt_offline:03d}",
                ],
            ),
        ]

    dash_app.clientside_callback(
        """
        function(filter_options) {
        query = filter_options.map(s => "." + s);
        query = query.reduce((a, s) => a + ", " + s, ".building-filter-none");
        if (document.iso === undefined) {
            return -1;
        };
        document.iso.arrange({ filter: query});
        return 0;
        }
        """,
        Output("n-interval-stage", "data"),
        Input("filter-buildings", "value"),
    )

    dash_app.clientside_callback(
        """
        function(value) {
            var iso = new Isotope('.grid', {
              // options
              itemSelector: '.grid-item',
              layoutMode: 'fitRows'
            });

            document.iso = iso;
            return 1;
        }
        """,
        Output("trash", "data"),
        Input("grid-content", "children"),
    )

    @dash_app.callback(
        Output("filter-buildings", "value"),
        Input("buildings", "data"),
        Input("app-container", "children"),
    )
    def check_all_boxes(buildings, _aux):
        return list(buildings.values())

    dash_app.layout = html.Div(
        id="big-app-container",
        children=[
            build_banner(dash_app),
            build_header(),
            html.Div(
                id="app-container",
                children=[
                    # Main app
                    html.Div(
                        id="div-loading-spinner",
                        children=[
                            html.Img(
                                id="loading-spinner",
                                src=dash_app.get_asset_url(
                                    "spinner.gif"
                                ),
                                style={
                                    "width": "50px",
                                    "height": "50px",
                                    "vertical-align": "middle",
                                    "display": "block",
                                    "margin-left": "auto",
                                    "margin-right": "auto",
                                    "margin-top": "100px",
                                },
                            ),
                        ],
                    ),
                    html.Div(
                        id="app-content",
                        className="my-hide",
                        children=[
                            html.Div(
                                id="grid-content",
                                className="grid",
                                children=[],
                            )
                        ],
                    ),
                ],
            ),
            dcc.Store(id="n-interval-stage", data=0),
            dcc.Store(id="devices", data=[]),
            dcc.Store(id="recent-measurements", data={}),
            dcc.Store(id="last-update", data="n/a"),
            dcc.Store(id="buildings", data="{}"),
            dcc.Store(id="summary-count", data=(0, 0, 0, 0)),
            dcc.Store(id="trash", data=0),
            dcc.Interval(
                id="interval-component-records",
                interval=3 * 60 * 1000,  # in milliseconds
                n_intervals=50,  # start at batch 50
                # disabled=False,
            ),
            dcc.Interval(
                id="interval-component-devices",
                interval=10 * 60 * 1000,  # in milliseconds
                n_intervals=50,  # start at batch 50
                # disabled=False,
            ),
        ],
    )

    dash_app.title = "Medición de CO2 / Exactas / UBA"

    return dash_app
