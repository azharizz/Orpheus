"""Keep a written narration beside a picture for a later agent to read."""

import json
import re
import time

MAX_BYTES = 400_000
SUFFIXES = (".txt", ".md", ".markdown")
NAME = "narration.json"
CUE = re.compile(r"^\s*(?:\[)?(\d{1,2}):([0-5]\d)(?::([0-5]\d))?(?:\])?\s*[-–—:]?\s*(.+)$")


def accepts(filename):
    lowered = str(filename or "").lower()
    return any(lowered.endswith(suffix) for suffix in SUFFIXES)


def decode(raw):
    if not isinstance(raw, (bytes, bytearray)):
        raise ValueError("Send the narration as a file.")
    if not raw:
        raise ValueError("That narration file is empty.")
    if len(raw) > MAX_BYTES:
        raise ValueError("Keep the narration under 400 KB.")
    try:
        text = bytes(raw).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Save the narration as UTF-8 text.") from exc
    if "\x00" in text:
        raise ValueError("That narration file is not text.")
    return text


def cues(text):
    """Read timestamped lines so the agent can place a note against the picture clock."""
    found = []
    for line in text.splitlines():
        match = CUE.match(line)
        if not match:
            continue
        hours, minutes, seconds = match.group(1), match.group(2), match.group(3)
        if seconds is None:
            at = int(hours) * 60 + int(minutes)
        else:
            at = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        note = match.group(4).strip()
        if note:
            found.append({"at_s": at, "note": note[:500]})
    return found


def parse(filename, raw):
    text = decode(raw)
    stripped = text.strip()
    if not stripped:
        raise ValueError("That narration file has no words.")
    return {
        "schema": "narration.v1",
        "filename": str(filename or "narration.txt")[:200],
        "characters": len(stripped),
        "words": len(stripped.split()),
        "cues": cues(text),
        "text": stripped,
        "created_at": time.time(),
    }


def save(folder, filename, raw):
    from .projects import atomic

    document = parse(filename, raw)
    target = folder / NAME
    atomic(target, document)
    return {key: document[key] for key in ("filename", "characters", "words") } | {
        "cues": len(document["cues"])
    }


def load(folder):
    target = folder / NAME
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def limits():
    return {"max_bytes": MAX_BYTES, "suffixes": list(SUFFIXES)}


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    assert accepts("a.md") and accepts("A.TXT") and not accepts("a.pdf")
    for bad in (b"", None, "text", b"\x00\x01", b"x" * (MAX_BYTES + 1)):
        try:
            decode(bad)
            raise SystemExit(f"must reject {bad!r}")
        except ValueError:
            pass
    body = b"01:05 A door closes down the hall\nnot a cue line\n[00:02:10] Rain starts\n"
    found = cues(body.decode())
    assert [c["at_s"] for c in found] == [65, 130], found
    doc = parse("scene.md", body)
    assert doc["words"] > 5 and len(doc["cues"]) == 2
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        summary = save(folder, "scene.md", body)
        assert summary["cues"] == 2
        assert load(folder)["text"].startswith("01:05")
        assert load(Path(tmp) / "missing") is None
    try:
        parse("empty.txt", b"   \n  ")
        raise SystemExit("blank narration must be rejected")
    except ValueError:
        pass
    print("narration self-check ok")
