"""Routes for the optional intake and generation helpers."""

from pathlib import Path
from urllib.parse import parse_qs, urlparse

GET_ROUTES = ("/api/extras", "/api/narration")
POST_ROUTES = ("/api/lyria", "/api/stream/import", "/api/narration")


def capabilities():
    found = {}
    for name in ("lyria", "livestream", "narration"):
        try:
            module = __import__(f"orpheus.domain.{name}", fromlist=[name])
            found[name] = module.limits()
        except Exception:
            found[name] = None
    return found


def handle_get(handler, route, query):
    if route == "/api/extras":
        handler.send_json(capabilities())
        return True
    if route == "/api/narration":
        from ..domain import narration, projects

        project_id = (query.get("project_id") or [""])[0]
        projects.load(project_id)
        handler.send_json(
            narration.load(projects.project_dir(project_id)) or {"narration": None}
        )
        return True
    return False


def handle_post(handler, route):
    if route not in POST_ROUTES:
        return False
    if route == "/api/lyria":
        from ..domain import lyria

        handler.send_json(lyria.payload(handler.read_json(4000)))
        return True
    if route == "/api/stream/import":
        handler.send_json(_import_stream(handler))
        return True
    handler.send_json(_attach_narration(handler))
    return True


def _import_stream(handler):
    from .. import config
    from ..domain import livestream, projects
    from . import web

    body = handler.read_json(4000)
    if not web.UPLOAD_LOCK.acquire(blocking=False):
        raise ValueError("Another upload is being prepared. Retry when it finishes.")
    try:
        return _capture_project(handler, body, config, livestream, projects, web)
    finally:
        web.UPLOAD_LOCK.release()


def _capture_project(handler, body, config, livestream, projects, web):
    captured = livestream.capture(body.get("url", ""), body.get("seconds"))
    try:
        project = projects.intake(
            captured,
            context=str(body.get("context", ""))[:200],
            style=str(body.get("style", ""))[:200],
            video_name="livestream.mp4",
        )
    finally:
        try:
            captured.unlink()
            captured.parent.rmdir()
        except OSError:
            pass
    if config.RUNTIME_MODE == "cloud_run":
        project["owner_id"] = handler.owner_id
        projects.atomic(projects.project_dir(project["id"]) / "project.json", project)
    web.start_prepare(project["id"], handler.owner_id)
    return {"project": project}


def _attach_narration(handler):
    from ..domain import narration, projects

    query = parse_qs(urlparse(handler.path).query, keep_blank_values=True)
    project_id = (query.get("project_id") or [""])[0]
    filename = Path(str((query.get("filename") or ["narration.txt"])[0]).replace("\\", "/")).name
    if not narration.accepts(filename):
        raise ValueError("Upload a .txt or .md narration.")
    projects.load(project_id)
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0 or length > narration.MAX_BYTES:
        raise ValueError("Keep the narration under 400 KB.")
    raw = handler.rfile.read(length)
    return narration.save(projects.project_dir(project_id), filename, raw)
