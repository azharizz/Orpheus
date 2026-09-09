"""Capture a bounded window of a live stream as an importable picture."""

import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

MAX_SECONDS = 30
DEFAULT_SECONDS = 15
SCHEMES = ("http", "https", "rtsp", "rtmp", "srt", "udp")
BLOCKED = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "169.254.169.254",
    "metadata.google.internal",
)


def check(url):
    """Reject anything that is not a remote stream before ffmpeg is handed the string."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Give the stream address.")
    url = url.strip()
    if len(url) > 2000:
        raise ValueError("That stream address is too long.")
    parsed = urlparse(url)
    if parsed.scheme not in SCHEMES:
        raise ValueError("Use an http, https, rtsp, rtmp, srt or udp address.")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("That stream address has no host.")
    if host in BLOCKED or host.endswith(".internal"):
        raise ValueError("That address is not a public stream.")
    if re.fullmatch(r"(10|127)\..*", host) or re.fullmatch(r"192\.168\..*", host):
        raise ValueError("That address is not a public stream.")
    if re.fullmatch(r"172\.(1[6-9]|2[0-9]|3[01])\..*", host):
        raise ValueError("That address is not a public stream.")
    return url


def seconds_of(value):
    try:
        seconds = int(value or DEFAULT_SECONDS)
    except (TypeError, ValueError):
        seconds = DEFAULT_SECONDS
    return max(5, min(MAX_SECONDS, seconds))


def command(url, seconds, destination):
    return [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-i",
        url,
        "-t",
        str(seconds),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(destination),
    ]


def capture(url, seconds=DEFAULT_SECONDS):
    """Pull the opening window of a stream into an mp4 the intake path already accepts."""
    url = check(url)
    seconds = seconds_of(seconds)
    folder = Path(tempfile.mkdtemp(prefix="orpheus-stream-"))
    target = folder / "stream.mp4"
    try:
        subprocess.run(
            command(url, seconds, target),
            check=True,
            capture_output=True,
            timeout=seconds + 20,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("The stream did not deliver in time.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode(errors="replace").strip().splitlines()
        raise ValueError(
            "The stream could not be read" + (f": {detail[-1][:160]}" if detail else ".")
        ) from exc
    if not target.exists() or target.stat().st_size == 0:
        raise ValueError("The stream produced no picture.")
    return target


def limits():
    return {
        "max_seconds": MAX_SECONDS,
        "default_seconds": DEFAULT_SECONDS,
        "schemes": list(SCHEMES),
    }


if __name__ == "__main__":
    assert check("https://example.com/live.m3u8").startswith("https://")
    assert check("rtsp://cam.example.org/stream")
    for bad in (
        "",
        "   ",
        None,
        "file:///etc/passwd",
        "https://127.0.0.1/x.m3u8",
        "http://169.254.169.254/latest/meta-data",
        "https://metadata.google.internal/x",
        "https://10.0.0.4/live",
        "https://192.168.1.9/live",
        "https://172.16.0.2/live",
        "https://" + "a" * 2100,
    ):
        try:
            check(bad)
            raise SystemExit(f"must reject {bad!r}")
        except ValueError:
            pass
    assert seconds_of(1) == 5 and seconds_of(99999) == MAX_SECONDS
    assert MAX_SECONDS + 20 < 60, 'capture must finish inside the socket timeout'
    assert seconds_of(0) == DEFAULT_SECONDS
    assert seconds_of(None) == DEFAULT_SECONDS and seconds_of("abc") == DEFAULT_SECONDS
    line = command("https://example.com/a.m3u8", 30, Path("/tmp/x.mp4"))
    assert "-t" in line and line[line.index("-t") + 1] == "30"
    print("livestream self-check ok")
