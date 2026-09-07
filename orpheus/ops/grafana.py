"""Setup, export and verify the local stack. No cloud credentials required."""

import argparse
import json
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from ..config import GRAFANA_PORTS, OBSERVABILITY_ASSETS
from . import observability as obs


def compose(*args):
    subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(obs.STORE / ".env"),
            "-f",
            str(OBSERVABILITY_ASSETS / "compose.yaml"),
            *args,
        ],
        check=True,
    )


def setup():
    obs.STORE.mkdir(parents=True, exist_ok=True)
    envpath = obs.STORE / ".env"
    if envpath.exists():
        values = dict(
            line.split("=", 1)
            for line in envpath.read_text().splitlines()
            if "=" in line
        )
    else:
        values = {
            "GRAFANA_ADMIN_PASSWORD": secrets.token_urlsafe(30),
            "MCP_CALLER_TOKEN": secrets.token_urlsafe(30),
        }

    def save():
        envpath.write_text("\n".join(k + "=" + v for k, v in values.items()) + "\n")
        envpath.chmod(0o600)

    values.update(
        {"ORPHEUS_" + name + "_PORT": str(port) for name, port in GRAFANA_PORTS.items()}
    )
    values["ORPHEUS_OBSERVABILITY_DIR"] = str(obs.STORE.resolve())
    template = (OBSERVABILITY_ASSETS / "prometheus.yaml").read_text()
    (obs.STORE / "prometheus.yaml").write_text(
        template.replace("__METRICS_PORT__", str(GRAFANA_PORTS["METRICS"]))
    )
    save()
    compose("up", "-d", "grafana", "loki", "tempo", "prometheus")
    with httpx.Client(
        base_url=f"http://127.0.0.1:{GRAFANA_PORTS['GRAFANA']}",
        auth=("admin", values["GRAFANA_ADMIN_PASSWORD"]),
        timeout=10,
        trust_env=False,
    ) as client:
        for attempt in range(45):
            try:
                if client.get("/api/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        if not values.get("GRAFANA_MCP_TOKEN"):
            response = client.post(
                "/api/serviceaccounts",
                json={"name": "orpheus-mcp-reader", "role": "Viewer"},
            )
            if response.status_code == 400:
                existing = client.get(
                    "/api/serviceaccounts/search",
                    params={"query": "orpheus-mcp-reader"},
                )
                existing.raise_for_status()
                ident = next(
                    row["id"]
                    for row in existing.json().get("serviceAccounts", [])
                    if row.get("name") == "orpheus-mcp-reader"
                )
            else:
                response.raise_for_status()
                ident = response.json()["id"]
            response = client.post(
                f"/api/serviceaccounts/{ident}/tokens",
                json={"name": "local-runtime-" + secrets.token_hex(4)},
            )
            response.raise_for_status()
            values["GRAFANA_MCP_TOKEN"] = response.json()["key"]
            save()
    obs.CONFIG.write_text(
        json.dumps(
            {
                "loki_url": f"http://127.0.0.1:{GRAFANA_PORTS['LOKI']}",
                "tempo_url": f"http://127.0.0.1:{GRAFANA_PORTS['OTLP']}",
                "dashboard_url": f"http://127.0.0.1:{GRAFANA_PORTS['GRAFANA']}/d/orpheus/agentic-foley-control-room",
                "mcp_url": f"http://127.0.0.1:{GRAFANA_PORTS['MCP']}/mcp",
                "mcp_token": values["MCP_CALLER_TOKEN"],
            }
        )
    )
    obs.CONFIG.chmod(0o600)
    compose("up", "-d", "mcp")
    print(
        f"Grafana: http://127.0.0.1:{GRAFANA_PORTS['GRAFANA']}/d/orpheus/agentic-foley-control-room · credentials stored privately."
    )


def dashboard():
    panels = []
    orange, green, amber, rose = "#FF5A36", "#9DCFAD", "#EAC17C", "#FF8790"
    prom, loki = "orpheus-prometheus", "orpheus-loki"
    base = '{service_name="orpheus"} | json | project_id=~"$project"'

    def target(expr, ref="A", datasource=prom, *, instant=False, legend=None):
        source_type = "loki" if datasource == loki else "prometheus"
        row = {
            "refId": ref,
            "expr": expr,
            "datasource": {"type": source_type, "uid": datasource},
            "editorMode": "code",
        }
        if instant:
            row.update(instant=True, range=False)
        elif datasource == prom:
            row.update(format="time_series", instant=False, range=True)
        if legend:
            row["legendFormat"] = legend
        if datasource == loki:
            row["queryType"] = "instant" if instant else "range"
            row["maxLines"] = 500
        return row

    def add(title, kind, grid, targets, *, description="", options=None,
            field=None, transformations=None, overrides=None, datasource=None):
        panel = {
            "id": len(panels) + 1,
            "title": title,
            "type": kind,
            "gridPos": grid,
            "description": description,
            "datasource": (
                {"type": "prometheus" if datasource == prom else "loki", "uid": datasource}
                if datasource
                else {"type": "datasource", "uid": "-- Mixed --"}
            ),
            "targets": targets,
            "options": options or {},
            "fieldConfig": {"defaults": field or {}, "overrides": overrides or []},
        }
        if transformations:
            panel["transformations"] = transformations
        panels.append(panel)
        return panel

    stat_options = {
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        "textMode": "auto",
    }
    safe_thresholds = {
        "mode": "absolute",
        "steps": [{"color": green, "value": None}, {"color": rose, "value": 1}],
    }
    project = '{project_id=~"$project"}'

    add(
        "Candidate status", "stat", {"x": 0, "y": 0, "w": 4, "h": 4},
        [target("orpheus_project_candidate_state" + project, instant=True)],
        options=stat_options,
        field={
            "color": {"mode": "thresholds"},
            "mappings": [{"type": "value", "options": {
                "-1": {"text": "UNSUITABLE", "color": rose},
                "0": {"text": "NO SELECTION", "color": amber},
                "1": {"text": "REVIEW READY", "color": green},
            }}],
            "thresholds": {"mode": "absolute", "steps": [{"color": amber, "value": None}]},
        },
    )
    add(
        "Contacts fitted", "stat", {"x": 4, "y": 0, "w": 4, "h": 4},
        [target("orpheus_candidate_accepted_events" + project, instant=True)],
        options=stat_options,
        field={"color": {"mode": "fixed", "fixedColor": orange}, "decimals": 0},
    )
    add(
        "Clipped samples", "stat", {"x": 8, "y": 0, "w": 4, "h": 4},
        [target("orpheus_candidate_clipped_samples" + project, instant=True)],
        options=stat_options,
        field={"color": {"mode": "thresholds"}, "decimals": 0, "thresholds": safe_thresholds},
    )
    add(
        "Picture integrity", "stat", {"x": 12, "y": 0, "w": 4, "h": 4},
        [target("orpheus_candidate_picture_unchanged" + project, instant=True)],
        options=stat_options,
        field={
            "color": {"mode": "thresholds"},
            "mappings": [{"type": "value", "options": {
                "0": {"text": "CHANGED", "color": rose},
                "1": {"text": "PRESERVED", "color": green},
            }}],
            "thresholds": {"mode": "absolute", "steps": [{"color": rose, "value": None}, {"color": green, "value": 1}]},
        },
    )
    add(
        "Human approval", "stat", {"x": 16, "y": 0, "w": 4, "h": 4},
        [target("orpheus_project_review_state" + project, instant=True)],
        options=stat_options,
        field={
            "color": {"mode": "thresholds"},
            "mappings": [{"type": "value", "options": {
                "-1": {"text": "REJECTED", "color": rose},
                "0": {"text": "PENDING", "color": amber},
                "1": {"text": "APPROVED", "color": green},
            }}],
            "thresholds": {"mode": "absolute", "steps": [{"color": amber, "value": None}]},
        },
    )
    add(
        "Grafana evidence reads", "stat", {"x": 20, "y": 0, "w": 4, "h": 4},
        [target('orpheus_project_events_total' + project[:-1] + ',event="grafana_investigation"}', instant=True)],
        options=stat_options,
        field={"color": {"mode": "fixed", "fixedColor": orange}, "decimals": 0},
    )

    gauge_options = {
        "displayMode": "gradient",
        "minVizHeight": 16,
        "minVizWidth": 8,
        "namePlacement": "left",
        "orientation": "horizontal",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        "showUnfilled": True,
        "sizing": "auto",
        "valueMode": "color",
    }
    add(
        "Baseline vs agent", "bargauge", {"x": 0, "y": 4, "w": 12, "h": 8},
        [
            target("orpheus_baseline_integrated_lufs" + project, "A", instant=True, legend="Baseline · LUFS"),
            target("orpheus_candidate_integrated_lufs" + project, "B", instant=True, legend="Agent · LUFS"),
            target("orpheus_baseline_true_peak_dbtp" + project, "C", instant=True, legend="Baseline · dBTP"),
            target("orpheus_candidate_true_peak_dbtp" + project, "D", instant=True, legend="Agent · dBTP"),
        ],
        description="A safer candidate retains every accepted contact while moving true peak farther below 0 dBTP. Loudness remains an audition decision.",
        options=gauge_options,
        field={
            "color": {"mode": "continuous-GrYlRd"},
            "decimals": 1,
            "max": 0,
            "min": -36,
            "thresholds": {"mode": "absolute", "steps": [
                {"color": green, "value": None}, {"color": amber, "value": -3}, {"color": rose, "value": -1},
            ]},
        },
    )
    add(
        "Loudness safety", "gauge", {"x": 12, "y": 4, "w": 6, "h": 8},
        [target("orpheus_candidate_true_peak_dbtp" + project, instant=True, legend="True peak")],
        description="Decoded exported AAC true peak. The warning band starts at -3 dBTP; 0 dBTP is unsafe.",
        options={"orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "showThresholdLabels": True, "showThresholdMarkers": True, "sizing": "auto"},
        field={
            "color": {"mode": "thresholds"}, "decimals": 1, "max": 0, "min": -12, "unit": "dB",
            "thresholds": {"mode": "absolute", "steps": [
                {"color": green, "value": None}, {"color": amber, "value": -3}, {"color": rose, "value": -1},
            ]},
        },
    )
    add(
        "Maximum timing deviation", "gauge", {"x": 18, "y": 4, "w": 6, "h": 8},
        [target("orpheus_candidate_max_abs_peak_error_ms" + project, instant=True, legend="Peak error")],
        description="Peak error is relative to reviewed agent anchors, not physical contact ground truth.",
        options={"orientation": "auto", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "showThresholdLabels": True, "showThresholdMarkers": True, "sizing": "auto"},
        field={
            "color": {"mode": "thresholds"}, "decimals": 1, "max": 100, "min": 0, "unit": "ms",
            "thresholds": {"mode": "absolute", "steps": [
                {"color": green, "value": None}, {"color": amber, "value": 30}, {"color": rose, "value": 60},
            ]},
        },
    )

    extract = {"id": "extractFields", "options": {"source": "Line", "format": "json", "replace": False}}
    add(
        "Contact timing · milliseconds from reviewed anchor", "barchart",
        {"x": 0, "y": 12, "w": 14, "h": 9},
        [target(
            'max by(mapping_id) (max_over_time(' + base
            + ' | event="sound_event" | unwrap timing_error_ms [$__range]))',
            datasource=loki,
            instant=True,
            legend="{{mapping_id}}",
        )],
        description="Each bar is one fitted contact. Zero is aligned; direction shows early or late placement.",
        options={"barRadius": 0, "barWidth": 0.7, "fullHighlight": False, "groupWidth": 0.7, "legend": {"displayMode": "hidden", "placement": "bottom", "showLegend": False}, "orientation": "horizontal", "showValue": "always", "stacking": "none", "tooltip": {"mode": "single", "sort": "none"}, "xField": "Metric"},
        field={"color": {"mode": "fixed", "fixedColor": orange}, "decimals": 1, "min": -60, "max": 60, "unit": "ms"},
        transformations=[{"id": "seriesToRows", "options": {}}],
    )
    add(
        "Family coverage · picture seconds", "barchart",
        {"x": 14, "y": 12, "w": 10, "h": 9},
        [target(base + ' | event="family_range"', datasource=loki)],
        description="Orange bars are reviewed ranges on the picture clock. Gaps remain untouched; row labels retain accepted or rejected status.",
        options={"barRadius": 0, "barWidth": 0.8, "fullHighlight": False, "groupWidth": 0.8, "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True}, "orientation": "horizontal", "showValue": "never", "stacking": "normal", "tooltip": {"mode": "multi", "sort": "none"}, "xField": "mapping_id"},
        field={"decimals": 2, "min": 0, "unit": "s"},
        transformations=[
            {"id": "extractFields", "options": {"source": "Line", "format": "json", "replace": True}},
            {"id": "filterFieldsByName", "options": {"include": {"names": ["mapping_id", "start_s", "range_duration_s"]}}},
        ],
        overrides=[
            {"matcher": {"id": "byName", "options": "start_s"}, "properties": [{"id": "displayName", "value": "start"}, {"id": "color", "value": {"mode": "fixed", "fixedColor": "#25272C"}}]},
            {"matcher": {"id": "byName", "options": "range_duration_s"}, "properties": [{"id": "displayName", "value": "reviewed range"}, {"id": "color", "value": {"mode": "fixed", "fixedColor": orange}}]},
        ],
    )

    table_options = {"cellHeight": "sm", "footer": {"countRows": False, "fields": "", "reducer": ["sum"], "show": False}, "showHeader": True}
    add(
        "Run status", "stat", {"x": 0, "y": 21, "w": 4, "h": 7},
        [target("orpheus_project_run_state" + project, instant=True)],
        description="A terminal session_saved or failed event closes the run. Human review is tracked separately.",
        options=stat_options,
        field={
            "color": {"mode": "thresholds"},
            "mappings": [{"type": "value", "options": {
                "-1": {"text": "FAILED", "color": rose},
                "0": {"text": "RUNNING", "color": amber},
                "1": {"text": "COMPLETED", "color": green},
            }}],
            "thresholds": {"mode": "absolute", "steps": [{"color": amber, "value": None}]},
        },
    )
    add(
        "Agent decision ledger", "table", {"x": 4, "y": 21, "w": 10, "h": 7},
        [target(base + ' | event=~"deterministic_baseline|grafana_investigation|candidate|candidate_timing_measured|selection|human_review"', datasource=loki)],
        description="Discrete, timestamped evidence gates. Rows never imply that a completed step is still running.",
        options=table_options,
        field={"custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False}},
        transformations=[
            {"id": "extractFields", "options": {"source": "Line", "format": "json", "replace": True, "keepTime": True}},
            {"id": "filterFieldsByName", "options": {"include": {"names": ["Time", "event", "topic", "status", "candidate_id", "decision"]}}},
            {"id": "sortBy", "options": {"fields": [{"field": "Time", "desc": False}]}},
        ],
        datasource=loki,
    )
    add(
        "Provider execution", "table", {"x": 14, "y": 21, "w": 10, "h": 7},
        [target(base + ' | event=~"model_failed|model_response|audio_failed|audio_response"', datasource=loki)],
        description="One completed response or failure per row. elapsed_s is real request duration, not a stretched dashboard state.",
        options=table_options,
        field={"custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False}},
        transformations=[
            {"id": "extractFields", "options": {"source": "Line", "format": "json", "replace": True, "keepTime": True}},
            {"id": "filterFieldsByName", "options": {"include": {"names": ["Time", "event", "requested_model", "served_model", "status_code", "elapsed_s"]}}},
            {"id": "sortBy", "options": {"fields": [{"field": "Time", "desc": False}]}},
        ],
        datasource=loki,
    )

    add(
        "Candidate evidence", "table", {"x": 0, "y": 28, "w": 12, "h": 8},
        [target(base + ' | event=~"candidate|candidate_timing_measured|candidate_audio_review"', datasource=loki)],
        description="Render, engineering measurement and acoustic review remain separate evidence records.",
        options=table_options,
        transformations=[
            {"id": "extractFields", "options": {"source": "Line", "format": "json", "replace": True, "keepTime": True}},
            {"id": "filterFieldsByName", "options": {"include": {"names": ["Time", "event", "candidate_id", "status", "integrated_lufs", "true_peak_dbtp", "clipped_samples", "max_abs_peak_error_ms", "picture_unchanged"]}}},
        ],
        field={"custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False}},
    )
    add(
        "Failure taxonomy", "bargauge", {"x": 12, "y": 28, "w": 6, "h": 8},
        [target('label_replace(orpheus_project_provider_events_total' + project[:-1] + ',outcome="failed"}, "provider", "$1", "model", "([^/]+).*" )', instant=True, legend="{{provider}}")],
        description="Failed provider requests grouped by requested model.",
        options={**gauge_options, "orientation": "horizontal"},
        field={"color": {"mode": "fixed", "fixedColor": rose}, "decimals": 0, "min": 0},
    )
    add(
        "Tool execution", "bargauge", {"x": 18, "y": 28, "w": 6, "h": 8},
        [target('orpheus_project_tool_events_total' + project, instant=True, legend="{{tool}} · {{outcome}}")],
        description="Completed and failed tool responses, normalized at the telemetry boundary.",
        options=gauge_options,
        field={"color": {"mode": "continuous-GrYlRd"}, "decimals": 0, "min": 0},
    )
    add(
        "Grafana MCP evidence", "table", {"x": 0, "y": 36, "w": 10, "h": 7},
        [target(base + ' | event="grafana_investigation"', datasource=loki)],
        description="Receipts prove that the agent queried project history before rendering and candidate evidence after measurement.",
        options=table_options,
        transformations=[
            {"id": "extractFields", "options": {"source": "Line", "format": "json", "replace": True, "keepTime": True}},
            {"id": "filterFieldsByName", "options": {"include": {"names": ["Time", "topic", "status", "candidate_id", "receipt_id"]}}},
        ],
        field={"custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False}},
    )
    add(
        "Experiment history", "table", {"x": 10, "y": 36, "w": 14, "h": 7},
        [target(base + ' | event=~"take_recorded|take_experiment|selection|human_review|candidate_timing_measured"', datasource=loki)],
        description="Immutable measurements and human decisions. Model observations remain hypotheses until reviewed.",
        options=table_options,
        transformations=[
            extract,
            {"id": "filterFieldsByName", "options": {"include": {"names": ["Time", "event", "candidate_id", "take_id", "decision", "verdict", "integrated_lufs", "true_peak_dbtp", "clipped_samples", "max_abs_peak_error_ms"]}}},
        ],
        field={"custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False}},
    )
    add(
        "Grafana MCP", "stat", {"x": 0, "y": 43, "w": 4, "h": 4},
        [target('(orpheus_project_events_total' + project[:-1] + ',event="grafana_investigation"} > bool 0)', instant=True)], options=stat_options,
        description="Verified when the agent has completed at least one successful project-scoped Grafana evidence read.",
        field={"mappings": [{"type": "value", "options": {"0": {"text": "NO EVIDENCE", "color": amber}, "1": {"text": "VERIFIED", "color": green}}}], "color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": amber, "value": None}, {"color": green, "value": 1}]}},
    )
    add(
        "Collector", "stat", {"x": 4, "y": 43, "w": 4, "h": 4},
        [target('up{job="orpheus"}', instant=True)], options=stat_options,
        field={"mappings": [{"type": "value", "options": {"0": {"text": "DOWN", "color": rose}, "1": {"text": "ONLINE", "color": green}}}], "color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": rose, "value": None}, {"color": green, "value": 1}]}},
    )
    add(
        "Pending exports", "stat", {"x": 8, "y": 43, "w": 4, "h": 4},
        [target("orpheus_export_pending", instant=True)], options=stat_options,
        field={"color": {"mode": "thresholds"}, "decimals": 0, "thresholds": safe_thresholds},
    )
    add(
        "Provider failures", "stat", {"x": 12, "y": 43, "w": 4, "h": 4},
        [target("orpheus_project_provider_failures_total" + project, instant=True)], options=stat_options,
        field={"color": {"mode": "thresholds"}, "decimals": 0, "thresholds": {"mode": "absolute", "steps": [{"color": green, "value": None}, {"color": amber, "value": 1}, {"color": rose, "value": 3}]}},
    )
    add(
        "Run duration", "stat", {"x": 16, "y": 43, "w": 4, "h": 4},
        [target("orpheus_project_run_duration_seconds" + project, instant=True)], options=stat_options,
        description="Wall-clock time from deterministic baseline to the terminal session event.",
        field={"color": {"mode": "fixed", "fixedColor": orange}, "decimals": 1, "unit": "s"},
    )
    add(
        "Reported cost", "stat", {"x": 20, "y": 43, "w": 4, "h": 4},
        [target("orpheus_project_reported_cost_usd_total" + project, instant=True)], options=stat_options,
        description="Only provider-reported cost. Missing receipts are not zero cost.",
        field={"color": {"mode": "fixed", "fixedColor": orange}, "decimals": 4, "unit": "currencyUSD"},
    )

    raw_children = []
    for title, expr in (
        ("Candidate and sound measurements", base + ' | event=~"candidate|candidate_timing_measured|sound_event|sound_profile"'),
        ("Failures and rejected tools", base + ' | event=~".*failed|tool_result"'),
        ("Agent, MCP and trace evidence", base + ' | event=~"model_response|audio_response|grafana_query|grafana_investigation|tool_call|session_saved"'),
    ):
        raw_children.append({
            "id": len(panels) + len(raw_children) + 2,
            "title": title,
            "type": "logs",
            "gridPos": {"x": 0, "y": 48 + len(raw_children) * 7, "w": 24, "h": 7},
            "datasource": {"type": "loki", "uid": loki},
            "targets": [target(expr, datasource=loki)],
            "options": {"dedupStrategy": "none", "enableLogDetails": True, "prettifyLogMessage": False, "showCommonLabels": False, "showLabels": False, "showTime": True, "sortOrder": "Descending", "wrapLogMessage": True},
        })
    panels.append({
        "id": len(panels) + 1,
        "title": "Raw evidence · open for diagnosis",
        "type": "row",
        "collapsed": True,
        "gridPos": {"x": 0, "y": 47, "w": 24, "h": 1},
        "panels": raw_children,
    })
    doc = {
        "uid": "orpheus",
        "title": "Agentic Foley Control Room",
        "schemaVersion": 40,
        "version": 5,
        "refresh": "5s",
        "time": {"from": "now-14d", "to": "now"},
        "tags": ["orpheus", "agent", "foley", "local"],
        "description": "One decision surface for deterministic baseline, agent fitting, Grafana evidence, provider execution and human approval.",
        "editable": False,
        "graphTooltip": 1,
        "links": [],
        "liveNow": True,
        "timepicker": {"refresh_intervals": ["5s", "10s", "30s", "1m"]},
        "templating": {
            "list": [
                {
                    "name": "project",
                    "type": "textbox",
                    "label": "Project",
                    "current": {"text": ".*", "value": ".*"},
                }
            ]
        },
        "panels": panels,
    }
    folder = OBSERVABILITY_ASSETS / "dashboards"
    folder.mkdir(exist_ok=True)
    (folder / "foley.json").write_text(json.dumps(doc, indent=2))


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_error(404)
            return
        data = obs.metrics_text().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def collect():
    # Docker Desktop reaches the host bridge; only aggregate, redacted metrics on this port.
    server = ThreadingHTTPServer(
        ("127.0.0.1", GRAFANA_PORTS["METRICS"]), MetricsHandler
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    while True:
        try:
            obs.flush()
        except Exception as exc:
            print(type(exc).__name__, flush=True)
        time.sleep(2)


def backfill():
    from ..domain.projects import PROJECTS

    count = 0
    for folder in PROJECTS.iterdir():
        if not (folder / "project.json").exists():
            continue
        path = folder / "events.jsonl"
        if path.exists():
            for line in path.read_text().splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                obs.emit(
                    folder.name,
                    row["event"],
                    row,
                    row.get("turn_id", "historical"),
                    row.get("ts"),
                )
                count += 1
        for role, name in [("target", "original.wav")]:
            if (folder / name).exists():
                obs.emit(
                    folder.name,
                    "sound_profile",
                    {"role": role, "profile": obs.sound_profile(folder / name)},
                    "input",
                    (folder / name).stat().st_mtime,
                )
        for receipt in (folder / "takes").glob("*.json") if (folder / "takes").exists() else ():
            take = json.loads(receipt.read_text())
            wav = receipt.with_suffix(".wav")
            if wav.exists():
                obs.emit(folder.name, "sound_profile", {
                    "role": "source", "take_id": take["id"],
                    "family_id": take.get("family_id"),
                    "profile": obs.sound_profile(wav)}, "input", wav.stat().st_mtime)
    print("Historical event receipts queued:", count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["setup", "collect", "backfill", "flush", "stop"]
    )
    args = parser.parse_args()
    if args.action == "setup":
        setup()
    elif args.action == "collect":
        collect()
    elif args.action == "backfill":
        backfill()
    elif args.action == "stop":
        compose("stop")
    else:
        print(obs.flush())
