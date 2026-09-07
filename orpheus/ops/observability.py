"""Local Grafana evidence plane. No raw prompts/media or credentials are exported."""

import asyncio
import fcntl
import hashlib
import json
import math
import os
import re
import sqlite3
import time
from contextlib import contextmanager

import httpx
import numpy as np

from ..config import OBSERVABILITY_DIR as STORE

CONFIG = STORE / "local.json"
DB = STORE / "outbox.sqlite"


def config():
    if os.environ.get("ORPHEUS_GRAFANA_ENABLED") == "0" or not CONFIG.exists():
        return None
    return json.loads(CONFIG.read_text())


@contextmanager
def connect():
    STORE.mkdir(exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    try:
        with db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, payload TEXT NOT NULL, trace TEXT, logs_sent INTEGER DEFAULT 0, trace_sent INTEGER DEFAULT 0)"
            )
            yield db
    finally:
        db.close()


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def numeric(values):
    return {
        k: v
        for k, v in (values or {}).items()
        if isinstance(k, str)
        and re.fullmatch(r"[a-zA-Z0-9_]+", k)
        and (finite(v) or isinstance(v, bool))
    }


def token(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_./:-]{1,120}", value)
        else "unknown"
    )


def sound_profile(path):
    """Signal descriptors, not silence/noise/material/quality ground truth."""
    from ..domain import media

    a = media.read_audio(path)
    if not len(a) or not np.isfinite(a).all():
        raise ValueError("Invalid audio samples")
    env = media.envelope(a)
    db = 20 * np.log10(np.maximum(env, 1e-9))
    peak = float(np.max(np.abs(a)))
    rms = float(np.sqrt(np.mean(a * a)))
    # ponytail: fixed energy threshold is a descriptor, not speech/activity detection.
    active = db > -50
    spectrum = np.abs(np.fft.rfft(a[: min(len(a), 48000 * 30)])) ** 2
    freq = np.fft.rfftfreq(min(len(a), 48000 * 30), 1 / 48000)
    total = max(float(spectrum.sum()), 1e-20)
    return {
        "duration_s": len(a) / 48000,
        "rms_dbfs": media.db(rms),
        "sample_peak_dbfs": media.db(peak),
        "crest_db": media.db(peak) - media.db(rms),
        "body_dbfs": media.body_level(a),
        "floor_p10_dbfs": float(np.percentile(db, 10)),
        "p90_dbfs": float(np.percentile(db, 90)),
        "dynamic_p90_p10_db": float(np.percentile(db, 90) - np.percentile(db, 10)),
        "active_fraction_above_minus50": float(np.mean(active)),
        "near_full_scale_samples": int(np.count_nonzero(np.abs(a) >= 0.999)),
        "dc_offset": float(np.mean(a)),
        "spectral_centroid_hz": float(np.dot(freq, spectrum) / total),
        "low_band_fraction_below250": float(spectrum[freq < 250].sum() / total),
        "high_band_fraction_above4000": float(spectrum[freq > 4000].sum() / total),
        "envelope": [
            {"media_s": round(i / 100, 3), "rms_dbfs": round(float(db[i]), 2)}
            for i in range(0, len(db), max(1, math.ceil(len(db) / 120)))
        ],
        "provenance": "signal_measurement",
        "warning": "Floor percentile includes intentional quiet; activity threshold is not semantic coverage. Mono PCM analysis, not acoustic calibration.",
    }


def enqueue(project_id, event, fields=None, turn_id="local", timestamp=None):
    if not config():
        return None
    if not re.fullmatch("[a-f0-9]{16}", project_id):
        raise ValueError("Invalid telemetry project")
    fields = fields or {}
    timestamp = time.time() if timestamp is None else timestamp
    if not finite(timestamp):
        raise ValueError("Invalid telemetry time")
    payload = {
        "project_id": project_id,
        "turn_id": token(turn_id),
        "event": token(event),
        "observed_at": timestamp,
        "trace_id": hashlib.sha256((project_id + turn_id).encode()).hexdigest()[:32],
    }
    for key in (
        "candidate_id",
        "family_id",
        "event_id",
        "mapping_id",
        "take_id",
        "parent_project_id",
        "requested_model",
        "served_model",
        "name",
        "status",
        "decision",
        "verdict",
        "role",
        "kind",
        "category",
        "error_type",
        "failure_code",
        "operation",
        "provenance",
        "topic",
        "receipt_id",
        "outcome",
    ):
        if key in fields:
            payload[key] = token(fields[key])
    if "id" in fields and re.fullmatch("[a-f0-9]{12}", str(fields["id"])):
        payload["candidate_id"] = fields["id"]
    for key in (
        "cycle",
        "elapsed_s",
        "status_code",
        "start_s",
        "end_s",
        "target_contact_s",
        "source_landmark_s",
        "gain_db",
        "clock_uncertainty_ms",
    ):
        if finite(fields.get(key)):
            payload[key] = fields[key]
    for key in ("metrics", "usage", "measurements"):
        if isinstance(fields.get(key), dict):
            payload.update(numeric(fields[key]))
    if isinstance(fields.get("profile"), dict):
        payload.update(numeric(fields["profile"]))
    response = fields.get("response")
    if isinstance(response, dict):
        payload["tool_error"] = bool(
            response.get("error")
            or response.get("status") in ("failed", "unavailable", "budget_exhausted")
        )
        if finite(response.get("status_code")):
            payload["status_code"] = response["status_code"]
    if event == "tool_result":
        payload["outcome"] = "failed" if payload.get("tool_error") else "completed"
    if isinstance(fields.get("timing"), dict):
        payload.update(numeric(fields["timing"]))
    coverage = fields.get("coverage")
    if isinstance(coverage, dict):
        payload["unmapped_hypotheses"] = len(coverage.get("unmapped_target_ids", []))
        payload["missing_output_rows"] = len(coverage.get("missing_output_ids", []))
    if "audio_sha256" in fields and re.fullmatch(
        "[a-f0-9]{64}", str(fields["audio_sha256"])
    ):
        payload["audio_sha256"] = fields["audio_sha256"]
    # Free-text descriptions, tool args/results, filenames, URLs and human notes never leave the app.
    for key in (
        "event_count",
        "time_s",
        "media_s",
        "rms_dbfs",
        "peak_dbfs",
        "body_dbfs",
        "crest_db",
        "timing_error_ms",
        "output_start_s",
        "output_end_s",
        "source_anchor_s",
        "target_anchor_s",
        "rendered_peak_s",
        "normalization_db",
        "decoded_mix_body_dbfs",
        "decoded_mix_peak_dbfs",
        "source_body_dbfs",
        "source_duration_s",
        "target_duration_s",
        "duration_mismatch_s",
        "trimmed_samples",
    ):
        if finite(fields.get(key)):
            payload[key] = fields[key]
    if event == "candidate":
        payload["event_count"] = len(fields.get("event_metrics", []))
    raw = json.dumps(payload, sort_keys=True, allow_nan=False)
    ident = hashlib.sha256(raw.encode()).hexdigest()
    payload["evidence_id"] = ident
    duration = (
        max(0, fields.get("elapsed_s", 0)) if finite(fields.get("elapsed_s", 0)) else 0
    )
    attrs = [
        {"key": k, "value": {"stringValue": str(v)}}
        for k, v in payload.items()
        if isinstance(v, (str, int, float, bool))
    ]
    span = {
        "traceId": payload["trace_id"],
        "spanId": ident[:16],
        "name": "orpheus." + token(event),
        "kind": 1,
        "startTimeUnixNano": str(int((timestamp - duration) * 1e9)),
        "endTimeUnixNano": str(int(timestamp * 1e9) + 1),
        "attributes": attrs,
        "status": {"code": 2 if "failed" in event or payload.get("tool_error") else 1},
    }
    root = hashlib.sha256((project_id + turn_id + ":root").encode()).hexdigest()[:16]
    if event == "turn_finished":
        span["spanId"] = root
    elif turn_id != "local":
        span["parentSpanId"] = root
    if event in ("model_response", "audio_response"):
        span["kind"] = 3
        for key, value in [
            ("gen_ai.operation.name", "chat"),
            ("gen_ai.request.model", payload.get("requested_model")),
            ("gen_ai.response.model", payload.get("served_model")),
            (
                "gen_ai.usage.input_tokens",
                payload.get("prompt_token_count", payload.get("prompt_tokens")),
            ),
            (
                "gen_ai.usage.output_tokens",
                payload.get("candidates_token_count", payload.get("completion_tokens")),
            ),
        ]:
            if value is not None:
                span["attributes"].append(
                    {
                        "key": key,
                        "value": {"intValue": str(value)}
                        if finite(value)
                        else {"stringValue": str(value)},
                    }
                )
    trace = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "orpheus"}}
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "orpheus.evidence", "version": "1"},
                        "spans": [span],
                    }
                ],
            }
        ]
    }
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO events(id,payload,trace) VALUES (?,?,?)",
            (ident, json.dumps(payload), json.dumps(trace)),
        )
    return ident


def emit(project_id, event, fields=None, turn_id="local", timestamp=None):
    """Export receipts never take down editing; persistent outbox is retried by collector."""
    try:
        ident = enqueue(project_id, event, fields, turn_id, timestamp)
        if ident and event in ("sound_profile", "take_recorded"):
            for index, m in enumerate(
                (fields or {}).get("profile", {}).get("envelope", [])
            ):
                enqueue(
                    project_id,
                    "sound_envelope",
                    {
                        **m,
                        "role": (fields or {}).get("role", "take"),
                        "take_id": (fields or {}).get("take_id", "unknown"),
                    },
                    turn_id,
                    (timestamp or time.time()) + index * 0.000001,
                )
        if ident and event in ("candidate", "candidate_timing_measured"):
            fitted = {
                r.get("mapping_id"): r for r in (fields or {}).get("fitted_impacts", [])
            }
            for index, m in enumerate((fields or {}).get("event_metrics", [])):
                row = {
                    **numeric(m),
                    **numeric(fitted.get(m.get("mapping_id"), {})),
                    "candidate_id": fields.get(
                        "candidate_id", fields.get("id", "unknown")
                    ),
                    "mapping_id": m.get("mapping_id", str(index)),
                }
                bounds = m.get("output_range_s", [])
                if len(bounds) == 2:
                    row.update(output_start_s=bounds[0], output_end_s=bounds[1])
                enqueue(
                    project_id,
                    "sound_event",
                    row,
                    turn_id,
                    (timestamp or time.time()) + index * 0.000001,
                )
        return ident
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return None


def flush(limit=500):
    cfg = config()
    if not cfg:
        return {"enabled": False}
    sent = 0
    errors = []
    # Short DB transactions; network outages must not lock the editor's outbox.
    with (STORE / "export.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"sent": 0, "busy": True, "pending": pending()}
        with connect() as db:
            rows = db.execute(
                "SELECT id,payload,trace,logs_sent,trace_sent FROM events WHERE logs_sent=0 OR trace_sent=0 ORDER BY rowid LIMIT ?",
                (limit,),
            ).fetchall()
        with httpx.Client(timeout=8, trust_env=False) as client:
            for backend, flag, column in [
                ("loki_url", 3, "logs_sent"),
                ("tempo_url", 4, "trace_sent"),
            ]:
                batch = [r for r in rows if not r[flag]]
                if not batch:
                    continue
                try:
                    if column == "logs_sent":
                        streams = {}
                        now = time.time_ns()
                        for index, (_, raw, *_) in enumerate(batch):
                            event = json.loads(raw)["event"]
                            # Loki clock = ingestion; observed_at retains original experiment time.
                            streams.setdefault(event, []).append(
                                [str(now + index), raw]
                            )
                        body = {
                            "streams": [
                                {
                                    "stream": {"service_name": "orpheus", "event": k},
                                    "values": v,
                                }
                                for k, v in streams.items()
                            ]
                        }
                        endpoint = "/loki/api/v1/push"
                    else:
                        body = {
                            "resourceSpans": [
                                s
                                for r in batch
                                for s in json.loads(r[2])["resourceSpans"]
                            ]
                        }
                        endpoint = "/v1/traces"
                    client.post(cfg[backend] + endpoint, json=body).raise_for_status()
                    with connect() as db:
                        db.executemany(
                            "UPDATE events SET " + column + "=1 WHERE id=?",
                            [(r[0],) for r in batch],
                        )
                    sent += len(batch)
                except httpx.HTTPError as exc:
                    errors.append(
                        type(exc).__name__
                        + ":"
                        + str(
                            getattr(
                                getattr(exc, "response", None), "status_code", "network"
                            )
                        )
                    )
    return {"sent": sent, "errors": errors, "pending": pending()}


def pending():
    with connect() as db:
        return db.execute(
            "SELECT count(*) FROM events WHERE logs_sent=0 OR trace_sent=0"
        ).fetchone()[0]


def metrics_text():
    # ponytail: scan the local experiment archive; pre-aggregate if scrape latency approaches 5s.
    with connect() as db:
        rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM events")]
    counts = {}
    failures = {}
    tokens = 0
    cost = 0
    latest = {}
    projects = {}
    for r in rows:
        counts[r["event"]] = counts.get(r["event"], 0) + 1
        project = projects.setdefault(
            r["project_id"],
            {"events": {}, "providers": {}, "tools": {}, "failures": 0, "tokens": 0, "cost": 0, "run_state": 0},
        )
        project["events"][r["event"]] = project["events"].get(r["event"], 0) + 1
        if r["event"] in ("model_failed", "audio_failed"):
            key = str(r.get("status_code", "unknown"))
            failures[key] = failures.get(key, 0) + 1
            project["failures"] += 1
        if r["event"] in ("model_response", "audio_response"):
            usage = r.get("total_token_count", r.get("total_tokens", 0))
            charge = r.get("cost", 0)
            tokens += usage
            cost += charge
            project["tokens"] += usage
            project["cost"] += charge
        if r["event"] in (
            "model_response", "audio_response", "model_failed", "audio_failed"
        ):
            provider = r.get("requested_model", "unknown")
            outcome = "failed" if r["event"].endswith("failed") else "served"
            key = (provider, outcome)
            project["providers"][key] = project["providers"].get(key, 0) + 1
        if r["event"] == "deterministic_baseline":
            project["baseline"] = r
            project["run_state"] = 0
            project["run_started_at"] = r["observed_at"]
            project.pop("run_finished_at", None)
        if r["event"] == "session_saved":
            project["run_state"] = 1
            project["run_finished_at"] = r["observed_at"]
        if r["event"] == "failed":
            project["run_state"] = -1
            project["run_finished_at"] = r["observed_at"]
        if r["event"] == "tool_result":
            key = (r.get("name", "unknown"), "failed" if r.get("tool_error") else "completed")
            project["tools"][key] = project["tools"].get(key, 0) + 1
        if r["event"] in ("candidate", "candidate_timing_measured"):
            latest = r
        if r["event"] == "candidate":
            project["candidate"] = r
        if r["event"] == "candidate_timing_measured":
            project["timing"] = r
        if r["event"] == "selection":
            project["selection"] = r
        if r["event"] == "human_review":
            project["review"] = r
        if r["event"] == "movie_analysis":
            project["movie_analysis"] = r
        if r["event"] == "movie_candidate":
            project["movie_candidate"] = r
    lines = ["# TYPE orpheus_events_total counter"]
    lines += [f'orpheus_events_total{{event="{key}"}} {n}' for key, n in counts.items()]
    lines += ["# TYPE orpheus_provider_failures_total counter"] + [
        f'orpheus_provider_failures_total{{code="{key}"}} {n}'
        for key, n in failures.items()
    ]
    lines += [
        f"orpheus_export_pending {pending()}",
        f"orpheus_reported_tokens_total {tokens}",
        f"orpheus_reported_cost_usd_total {cost}",
    ]
    for key in (
        "integrated_lufs",
        "true_peak_dbtp",
        "clipped_samples",
        "event_count",
        "max_abs_peak_error_ms",
        "unmapped_hypotheses",
        "missing_output_rows",
    ):
        if finite(latest.get(key)):
            lines.append(f"orpheus_latest_candidate_{key} {latest[key]}")
    selection_states = {"unsuitable": -1, "needs_human_review": 1}
    review_states = {"rejected": -1, "reject": -1, "approved": 1, "approve": 1}
    measured = (
        "integrated_lufs",
        "true_peak_dbtp",
        "clipped_samples",
        "event_count",
        "accepted_events",
        "max_abs_peak_error_ms",
        "picture_unchanged",
    )
    for project_id, project in projects.items():
        labels = f'project_id="{project_id}"'
        lines += [
            f"orpheus_project_candidate_state{{{labels}}} "
            + str(selection_states.get(project.get("selection", {}).get("decision"), 0)),
            f"orpheus_project_review_state{{{labels}}} "
            + str(review_states.get(project.get("review", {}).get("verdict"), 0)),
            f"orpheus_project_provider_failures_total{{{labels}}} {project['failures']}",
            f"orpheus_project_reported_tokens_total{{{labels}}} {project['tokens']}",
            f"orpheus_project_reported_cost_usd_total{{{labels}}} {project['cost']}",
            f"orpheus_project_run_state{{{labels}}} {project['run_state']}",
        ]
        analysis = project.get("movie_analysis", {})
        for key in ("progress", "events", "suggestions", "noise_regions", "duration_s"):
            value = analysis.get(key)
            if finite(value):
                lines.append(f"orpheus_movie_{key}{{{labels}}} {value}")
        if finite(project.get("run_started_at")) and finite(project.get("run_finished_at")):
            lines.append(
                f"orpheus_project_run_duration_seconds{{{labels}}} "
                + str(project["run_finished_at"] - project["run_started_at"])
            )
        lines += [
            f'orpheus_project_events_total{{{labels},event="{event}"}} {count}'
            for event, count in project["events"].items()
        ]
        lines += [
            f'orpheus_project_provider_events_total{{{labels},model="{model}",outcome="{outcome}"}} {count}'
            for (model, outcome), count in project["providers"].items()
        ]
        lines += [
            f'orpheus_project_tool_events_total{{{labels},tool="{tool}",outcome="{outcome}"}} {count}'
            for (tool, outcome), count in project["tools"].items()
        ]
        for stage in ("baseline", "candidate"):
            row = project.get(stage, {})
            for key in measured:
                value = row.get(key, project.get("timing", {}).get(key))
                if isinstance(value, bool):
                    value = int(value)
                if finite(value):
                    lines.append(f"orpheus_{stage}_{key}{{{labels}}} {value}")
    return "\n".join(lines) + "\n"


async def investigate(project_id, topic="history", candidate_id=""):
    """All evidence reads go through the official Grafana MCP server, not direct Loki APIs."""
    cfg = config()
    if not cfg:
        return {
            "status": "disabled",
            "warning": "Local Grafana not configured; no MCP evidence available.",
        }
    if not re.fullmatch("[a-f0-9]{16}", project_id):
        raise ValueError("Invalid project")
    if topic not in ("history", "failures", "sound", "takes", "runtime"):
        raise ValueError("Unknown investigation topic")
    if candidate_id and not re.fullmatch("[a-f0-9]{12}", candidate_id):
        raise ValueError("Invalid candidate")
    await asyncio.to_thread(flush)
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    selector = (
        '{service_name="orpheus",event!="sound_envelope"} | json | project_id="'
        + project_id
        + '"'
    )
    if topic == "takes":
        selector = (
            '{service_name="orpheus",event=~"take_recorded|take_experiment|human_review"} | json | parent_project_id="'
            + project_id
            + '"'
        )
    elif topic == "failures":
        selector += ' | event=~".*failed|tool_result|session_saved"'
    elif topic == "sound":
        selector += (
            ' | event=~"candidate|candidate_timing_measured|sound_event|sound_profile"'
        )
    if candidate_id:
        selector += ' | candidate_id="' + candidate_id + '"'
    started = time.time()
    try:
        async with asyncio.timeout(45):
            async with streamablehttp_client(
                cfg["mcp_url"], headers={"Authorization": "Bearer " + cfg["mcp_token"]}
            ) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    catalog = await session.list_tools()
                    available = {t.name: t for t in catalog.tools}
                    name = (
                        "query_prometheus" if topic == "runtime" else "query_loki_logs"
                    )
                    if name not in available:
                        return {
                            "status": "failed",
                            "error": "MCP tool unavailable",
                            "tool": name,
                        }
                    arguments = (
                        {
                            "datasourceUid": "orpheus-prometheus",
                            "expr": 'up{job="orpheus"} or orpheus_export_pending or orpheus_provider_failures_total or ALERTS',
                            "queryType": "instant",
                            "endTime": "now",
                        }
                        if topic == "runtime"
                        else {
                            "datasourceUid": "orpheus-loki",
                            "logql": selector,
                            "limit": 100,
                            "format": "compact",
                            "startRfc3339": "now-14d",
                            "endRfc3339": "now",
                        }
                    )
                    result = await session.call_tool(name, arguments)
                    blocks = [c.text for c in result.content if hasattr(c, "text")]
                    response = "\n".join(blocks)
                    if result.isError:
                        return {
                            "status": "failed",
                            "error": "MCP query rejected",
                            "detail": response[:500],
                        }
                    decoded = json.loads(response)
                    evidence = []
                    if name == "query_loki_logs":
                        for stream in decoded.get("streams", []):
                            for entry in stream.get("lines", []):
                                evidence.append(json.loads(entry["line"]))
                        evidence.sort(
                            key=lambda r: r.get("observed_at", 0), reverse=True
                        )
                    else:
                        evidence = decoded.get("data", [])
                    compact = json.dumps(evidence, separators=(",", ":"))
                    # Bounded model context; retain full query receipt locally.
                    report = {
                        "status": "ok",
                        "topic": topic,
                        "project_id": project_id,
                        "candidate_id": candidate_id,
                        "tool": name,
                        "query": arguments,
                        "data": compact[:24000],
                        "evidence_count": len(evidence),
                        "truncated": len(compact) > 24000,
                        "queried_at": time.time(),
                        "pending_exports": pending(),
                        "warning": "Grafana measurements and model/human provenance are distinct. Empty results or pending exports are not success. Telemetry cannot establish perceptual truth.",
                    }
                    report["receipt_id"] = hashlib.sha256(
                        json.dumps(report, sort_keys=True).encode()
                    ).hexdigest()[:20]
                    receipts = STORE / "receipts"
                    receipts.mkdir(exist_ok=True)
                    (receipts / (report["receipt_id"] + ".json")).write_text(
                        json.dumps({**report, "data": response})
                    )
                    emit(
                        project_id,
                        "grafana_query",
                        {
                            "name": name,
                            "status": "ok",
                            "elapsed_s": time.time() - started,
                        },
                    )
                    return report
    except Exception as exc:
        return {
            "status": "unavailable",
            "error_type": type(exc).__name__,
            "warning": "Grafana MCP unavailable; no evidence inferred, no automatic paid retry.",
        }


def status():
    cfg = config()
    return {
        "enabled": bool(cfg),
        "dashboard_url": cfg.get("dashboard_url") if cfg else None,
        "pending_exports": pending() if cfg else None,
        "mcp_url": cfg.get("mcp_url") if cfg else None,
    }
