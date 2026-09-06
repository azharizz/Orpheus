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
            response.raise_for_status()
            ident = response.json()["id"]
            response = client.post(
                f"/api/serviceaccounts/{ident}/tokens", json={"name": "local-runtime"}
            )
            response.raise_for_status()
            values["GRAFANA_MCP_TOKEN"] = response.json()["key"]
            save()
    obs.CONFIG.write_text(
        json.dumps(
            {
                "loki_url": f"http://127.0.0.1:{GRAFANA_PORTS['LOKI']}",
                "tempo_url": f"http://127.0.0.1:{GRAFANA_PORTS['OTLP']}",
                "dashboard_url": f"http://127.0.0.1:{GRAFANA_PORTS['GRAFANA']}/d/orpheus/foley-evidence",
                "mcp_url": f"http://127.0.0.1:{GRAFANA_PORTS['MCP']}/mcp",
                "mcp_token": values["MCP_CALLER_TOKEN"],
            }
        )
    )
    obs.CONFIG.chmod(0o600)
    compose("up", "-d", "mcp")
    print(
        f"Grafana: http://127.0.0.1:{GRAFANA_PORTS['GRAFANA']}/d/orpheus/foley-evidence · credentials stored privately."
    )


def dashboard():
    panels = []

    def panel(title, kind, expr, datasource="orpheus-loki", description=""):
        i = len(panels)
        panels.append(
            {
                "id": i + 1,
                "title": title,
                "type": kind,
                "description": description,
                "gridPos": {
                    "x": 0 if kind == "logs" else (i % 2) * 12,
                    "y": i * 5,
                    "w": 24 if kind == "logs" else 12,
                    "h": 8,
                },
                "datasource": {"uid": datasource},
                "targets": [{"refId": "A", "expr": expr, "queryType": "range"}],
                "options": {
                    "showTime": True,
                    "wrapLogMessage": True,
                    "sortOrder": "Descending",
                },
            }
        )

    base = '{service_name="orpheus"} | json | project_id=~"$project"'
    panel(
        "Sound measurements · candidates and input/takes",
        "logs",
        base + ' | event=~"candidate|sound_profile|take_recorded"',
        description="Signal descriptors are not perceptual approval. floor_p10 includes intentional quiet; active_fraction is a fixed -50 dBFS threshold.",
    )
    panel(
        "Impact, source landmark and coverage evidence",
        "logs",
        base + ' | event=~"sound_event|candidate_timing_measured"',
        description="Media timestamps are fields, not log timestamps. Peak errors are relative to agent anchors, not physical contact truth.",
    )
    panel(
        "Audio envelope · picture/source seconds (not wall clock)",
        "table",
        base + ' | event="sound_envelope"',
        description="RMS at up to 120 sampled windows per input/take. Select one project. Quiet is not automatically unwanted noise.",
    )
    panels[-1]["targets"][0]["maxLines"] = 500
    panels[-1]["transformations"] = [
        {
            "id": "extractFields",
            "options": {"source": "Line", "format": "json", "replace": True},
        },
        {
            "id": "filterFieldsByName",
            "options": {
                "include": {
                    "names": ["project_id", "role", "take_id", "media_s", "rms_dbfs"]
                }
            },
        },
    ]
    panel(
        "Take experiments and human decisions",
        "logs",
        base + ' | event=~"take_recorded|take_experiment|human_review|selection"',
    )
    panel(
        "Provider and rejected tool calls",
        "logs",
        base
        + ' | event=~".*failed|tool_result" | tool_error="true" or event=~".*failed"',
        description="Failed inference is not evidence of absent sound. Read-only MCP can investigate; no automatic purchases or retry loops.",
    )
    panel(
        "Agent, tool and MCP execution",
        "logs",
        base
        + ' | event=~"model_response|audio_response|grafana_query|tool_call|session_saved"',
        description="Trace IDs link into Tempo. No raw prompts, media or credentials exported.",
    )
    panel(
        "Telemetry outbox backlog",
        "timeseries",
        "orpheus_export_pending",
        "orpheus-prometheus",
    )
    panel(
        "Provider failures by status",
        "timeseries",
        "sum by(code) (increase(orpheus_provider_failures_total[5m]))",
        "orpheus-prometheus",
    )
    panel(
        "Reported token usage",
        "timeseries",
        "orpheus_reported_tokens_total",
        "orpheus-prometheus",
        description="Only usage returned by providers; missing usage is not zero billed usage.",
    )
    panel("Collector health", "timeseries", 'up{job="orpheus"}', "orpheus-prometheus")
    doc = {
        "uid": "orpheus",
        "title": "Foley evidence",
        "schemaVersion": 40,
        "version": 1,
        "refresh": "5s",
        "time": {"from": "now-14d", "to": "now"},
        "tags": ["orpheus", "local"],
        "templating": {
            "list": [
                {
                    "name": "project",
                    "type": "textbox",
                    "label": "Project ID regex",
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
