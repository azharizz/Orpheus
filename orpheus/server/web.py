"""Same-origin local API and the two Orpheus application routes."""

import argparse
import asyncio
import fcntl
import json
import re
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .. import config
from ..domain import families, family_agent, media, projects, review, takes
from ..ops import observability as obs
from .http import LocalHandler, RequestError

LOCK = threading.RLock()
UPLOAD_LOCK = threading.Lock()
PROCESS = None
INDEX_THREAD = None
INDEX_QUEUE = []
STATIC = config.ROOT / "frontend" / "dist"
DEFAULT_FEEDBACK = "Create a fitted alternative from these files."


def busy():
    projects.ROOT.mkdir(parents=True, exist_ok=True)
    with (projects.ROOT / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return (PROCESS is not None and PROCESS.poll() is None) or (
        INDEX_THREAD is not None and INDEX_THREAD.is_alive()
    )


def start_index(project_id):
    global INDEX_THREAD
    with LOCK:
        if project_id not in INDEX_QUEUE:
            INDEX_QUEUE.append(project_id)
        if INDEX_THREAD is not None and INDEX_THREAD.is_alive():
            return True

        def run():
            global INDEX_THREAD
            while True:
                with LOCK:
                    if not INDEX_QUEUE:
                        INDEX_THREAD = None
                        return
                    pending = INDEX_QUEUE.pop(0)
                try:
                    families.build_index(pending)
                except Exception:
                    pass

        INDEX_THREAD = threading.Thread(target=run, daemon=True, name="orpheus-index")
        INDEX_THREAD.start()
        return True


@contextmanager
def mutation():
    # ponytail: one local editing operation at a time; use per-project jobs for multiple users.
    with LOCK:
        if busy():
            raise BlockingIOError()
        with (projects.ROOT / "worker.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield


def start(project_id, family_id, feedback):
    global PROCESS
    family_agent.load_case(project_id, family_id)
    if (
        not isinstance(feedback, str)
        or not 1 <= len(feedback) <= config.MAX_FEEDBACK_CHARS
    ):
        raise ValueError("Feedback must be 1 to 500 characters.")
    with LOCK:
        if busy():
            raise BlockingIOError()
        with (projects.project_dir(project_id) / "worker.log").open("ab") as output:
            PROCESS = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "orpheus.server.worker",
                    project_id,
                    "--family-id",
                    family_id,
                    "--feedback",
                    feedback,
                ],
                cwd=config.ROOT,
                stdout=output,
                stderr=output,
                start_new_session=True,
            )


def project_list():
    rows, errors = [], []
    for path in sorted(
        projects.PROJECTS.glob("*/project.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            doc = json.loads(path.read_text())
            if doc.get("schema") != "orpheus.v3":
                raise ValueError("Unsupported project schema")
            doc["turn_details"] = [
                json.loads((path.parent / (tid + "-turn.json")).read_text())
                for tid in doc["turns"]
                if (path.parent / (tid + "-turn.json")).exists()
            ]
            doc["human_reviews"] = [
                json.loads(p.read_text())
                for p in sorted(path.parent.glob("*-human.json"))
            ]
            doc["similarity_index"] = families.index_status(doc["id"])
            rows.append(doc)
        except (ValueError, KeyError, OSError):
            errors.append(
                {
                    "project_id": path.parent.name,
                    "error": "Project receipt is unreadable; files retained.",
                }
            )
    return {"projects": rows, "running": busy(), "errors": errors}


def public_config():
    from ..agent.perception import MODEL
    from ..agent.provider import MODELS

    return {
        "max_file_bytes": config.MAX_FILE_BYTES,
        "max_duration_s": config.MAX_DURATION_S,
        "max_audio_bytes": config.AUDIO_UPLOAD_LIMIT_BYTES,
        "max_take_duration_s": config.MAX_TAKE_DURATION_S,
        "free_disk_margin_bytes": config.FREE_DISK_MARGIN_BYTES,
        "max_brief_chars": config.MAX_BRIEF_CHARS,
        "max_feedback_chars": config.MAX_FEEDBACK_CHARS,
        "max_controller_calls": config.MAX_CONTROLLER_CALLS,
        "audio_enabled": config.AUDIO_ENABLED,
        "controller_models": list(MODELS),
        "audio_model": MODEL,
        "storage": "local",
        "inference_destination": "Configured controller providers; audio observation through OpenRouter when enabled",
    }


class Handler(LocalHandler):
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            self.local_request()
            self.get_route()
        except RequestError as error:
            self.send_json({"error": str(error)}, error.status)
        except FileNotFoundError:
            self.send_json({"error": "Project or artifact not found."}, 404)
        except (ValueError, KeyError, TypeError, IndexError):
            self.send_json(
                {"error": "Invalid project, candidate or media window."}, 400
            )
        except (OSError, subprocess.SubprocessError):
            self.send_json(
                {
                    "error": "Local media is unavailable. Check the project files and FFmpeg."
                },
                422,
            )

    def get_route(self):
        parsed = urlparse(self.path)
        route = unquote(parsed.path)
        if route in ("/", "/workspace"):
            self.send_file(STATIC, "index.html")
        elif route.startswith("/assets/"):
            self.send_file(STATIC, route.lstrip("/"))
        elif route == "/api/config":
            self.send_json(public_config())
        elif route == "/api/projects":
            self.send_json(project_list())
        elif route == "/api/observability":
            self.send_json(obs.status())
        elif route == "/api/takes":
            pid = parse_qs(parsed.query)["project_id"][0]
            projects.load(pid)
            self.send_json(
                {
                    "takes": takes.list_takes(pid),
                    "experiments": [
                        json.loads(p.read_text())
                        for p in sorted(
                            projects.project_dir(pid).glob("*-experiment.json")
                        )
                    ],
                }
            )
        elif route == "/api/families":
            pid = parse_qs(parsed.query)["project_id"][0]
            projects.load(pid)
            self.send_json(
                {
                    "families": families.list_families(pid),
                    "index": families.index_status(pid),
                }
            )
        elif route == "/api/waveform":
            self.audio_data(route, parse_qs(parsed.query))
        elif route.startswith("/projects/"):
            self.project_file(route.removeprefix("/projects/"))
        else:
            raise RequestError("Route not found.", 404)

    def project_file(self, relative):
        allowed = re.fullmatch(
            r"([a-f0-9]{16})/(video\.mp4|poster\.jpg|original\.wav|events\.jsonl|"
            r"[a-f0-9]{12}\.(?:mp4|wav|json)|[a-f0-9]{12}-master\.(?:mp4|mkv)|"
            r"[a-f0-9]{12}-turn\.json|takes/[a-f0-9]{12}\.wav)",
            relative,
        )
        if not allowed:
            raise RequestError("Artifact not found.", 404)
        pid, name = allowed.groups()
        if name == "poster.jpg":
            case = projects.load(pid)
            poster = projects.project_dir(pid) / name
            with LOCK:
                if not poster.exists():
                    frames = projects.frames(
                        case,
                        [min(0.5, case["seconds"] / 2)],
                        projects.project_dir(pid) / "frames",
                    )
                    poster.write_bytes(frames[0][1].read_bytes())
        self.send_file(projects.PROJECTS, relative)

    def audio_data(self, route, query):
        case = projects.load(query["project_id"][0])
        role = query["role"][0]
        if role not in ("original", "candidate"):
            raise ValueError("Invalid waveform role")
        if role == "candidate":
            cid = query["candidate_id"][0]
            review.candidate(case, cid)
            path = projects.project_dir(case["id"]) / (cid + ".wav")
        else:
            path = case["original_path"]
        self.send_json(media.waveform(path))

    def do_POST(self):
        try:
            self.local_request(mutation=True)
            route = urlparse(self.path).path
            if route in ("/api/projects", "/api/takes"):
                if not UPLOAD_LOCK.acquire(blocking=False):
                    raise RequestError(
                        "Another upload is being prepared. Retry when it finishes.", 409
                    )
                try:
                    self.upload(route)
                finally:
                    UPLOAD_LOCK.release()
                return
            self.json_action(route)
        except RequestError as error:
            self.send_json({"error": str(error)}, error.status)
        except BlockingIOError:
            self.send_json(
                {"error": "An agent run or edit is active. Wait for it to finish."}, 409
            )
        except (ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            self.send_json(
                {
                    "error": "Invalid input. Check the selected project, values and file types."
                },
                400,
            )
        except FileNotFoundError:
            self.send_json({"error": "Project or artifact not found."}, 404)
        except (OSError, subprocess.SubprocessError):
            self.send_json(
                {
                    "error": "Media operation failed. Completed files remain available; check FFmpeg and disk space."
                },
                422,
            )

    def upload(self, route):
        take = route == "/api/takes"
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)

        def value(name, default=""):
            values = query.get(name, [default])
            if len(values) != 1:
                raise ValueError("Repeated upload field")
            return values[0]

        filename = Path(value("filename").replace("\\", "/")).name
        suffix = Path(filename).suffix.lower()
        allowed = (
            (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".mp4")
            if take
            else (".mp4", ".mov", ".webm", ".mkv")
        )
        if suffix not in allowed:
            raise ValueError("Unsupported media extension")
        with tempfile.TemporaryDirectory(prefix="orpheus-upload-") as temporary:
            path = Path(temporary) / (("audio" if take else "video") + suffix)
            self.read_file(
                config.AUDIO_UPLOAD_LIMIT_BYTES if take else config.VIDEO_UPLOAD_LIMIT_BYTES,
                path,
            )
            if take:
                family_id = value("family_id")
                if not family_id:
                    raise ValueError("Replacement take requires a sound family")
                with mutation():
                    result = takes.add_take(
                        value("project_id"),
                        path,
                        value("brief"),
                        float(value("start_s", "0")),
                        value("clock", "uploaded"),
                        family_id,
                    )
            else:
                result = {
                    "project": projects.create(
                        path,
                        context=value("context"),
                        style=value("style"),
                        video_name=filename,
                    )
                }
                start_index(result["project"]["id"])
        self.send_json(result, 201)

    def json_action(self, route):
        if route not in (
            "/api/run",
            "/api/review",
            "/api/families",
            "/api/families/review",
            "/api/families/render",
            "/api/grafana",
        ):
            raise RequestError("Route not found.", 404)
        data = self.read_json(100000 if route == "/api/families/review" else 3000)
        if route == "/api/run":
            family_id = data.get("family_id")
            if not family_id:
                raise RequestError(
                    "Choose a sound family and replacement take before running fitting.",
                    409,
                )
            if data.get("consent") is not True:
                raise RequestError("Confirm the paid fitting run before starting it.", 409)
            if not obs.config():
                raise RequestError(
                    "Start the local Grafana stack before agent fitting. The agent requires Grafana MCP evidence.",
                    409,
                )
            try:
                family_agent.load_case(data["project_id"], family_id)
            except (ValueError, FileNotFoundError) as exc:
                raise RequestError(str(exc), 409) from exc
            start(
                data["project_id"],
                family_id,
                data.get("feedback", DEFAULT_FEEDBACK),
            )
            self.send_json(
                {
                    "started": True,
                    "project_id": data["project_id"],
                    "family_id": family_id,
                },
                202,
            )
        elif route == "/api/grafana":
            projects.load(data["project_id"])
            self.send_json(
                asyncio.run(
                    obs.investigate(
                        data["project_id"],
                        data.get("topic", "history"),
                        data.get("candidate_id", ""),
                    )
                )
            )
        elif route == "/api/families":
            with mutation():
                result = families.create(
                    data["project_id"], data["name"], data["seed_range_s"]
                )
            self.send_json(result, 201)
        elif route == "/api/families/review":
            decisions = data.get("decisions")
            if (
                not isinstance(decisions, list)
                or any(
                    not isinstance(row, dict)
                    or set(row) != {"match_id", "decision"}
                    or row["decision"] not in ("accepted", "rejected")
                    for row in decisions
                )
                or len({row["match_id"] for row in decisions}) != len(decisions)
            ):
                raise ValueError("Invalid match decision batch")
            accepted = [
                row["match_id"]
                for row in decisions
                if row.get("decision") == "accepted"
            ]
            rejected = [
                row["match_id"]
                for row in decisions
                if row.get("decision") == "rejected"
            ]
            with mutation():
                result = families.review(
                    data["project_id"], data["family_id"], accepted, rejected
                )
            self.send_json(result, 201)
        elif route == "/api/families/render":
            with mutation():
                result = families.render(
                    data["project_id"],
                    data["family_id"],
                    data.get("take_id"),
                )
            self.send_json(result, 201)
        elif route == "/api/review":
            with mutation():
                result = review.save_review(data)
            self.send_json(result, 201)


def main():
    parser = argparse.ArgumentParser(description="Run the local Orpheus workbench.")
    parser.add_argument("--port", type=int, default=config.SERVER_PORT)
    args = parser.parse_args()
    projects.ROOT.mkdir(parents=True, exist_ok=True)
    projects.PROJECTS.mkdir(parents=True, exist_ok=True)
    if not (STATIC / "index.html").is_file():
        parser.error(
            "Build the interface first: cd frontend && npm ci && npm run build"
        )
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Orpheus: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
