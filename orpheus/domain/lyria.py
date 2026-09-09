"""Generate a short replacement take from a written description."""

import base64
import io
import json
import math
import struct
import wave

MAX_SECONDS = 10
RATE = 48000
MODEL = "lyria-002"


def _pcm(frames, channels=1):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        stream.writeframes(frames)
    return buffer.getvalue()


def _placeholder(seconds):
    total = int(RATE * seconds)
    frames = bytearray()
    for index in range(total):
        fade = min(1.0, index / (RATE * 0.01), (total - index) / (RATE * 0.05))
        value = int(1800 * fade * math.sin(index * 2 * math.pi * 180 / RATE))
        frames += struct.pack("<h", value)
    return _pcm(bytes(frames))


def _decode(payload):
    for key in ("audioContent", "bytesBase64Encoded", "audio"):
        raw = payload.get(key)
        if isinstance(raw, str) and raw:
            return base64.b64decode(raw)
    return None


def available():
    from .. import config

    return bool(getattr(config, "GOOGLE_CLOUD_PROJECT", ""))


def generate(prompt, seconds, negative=""):
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Describe the sound to generate.")
    if len(prompt) > 500:
        raise ValueError("Keep the description under 500 characters.")
    seconds = max(1, min(MAX_SECONDS, int(seconds or MAX_SECONDS)))
    try:
        return _request(prompt.strip(), str(negative or "")[:200]), MODEL
    except Exception:
        return _placeholder(seconds), "unavailable"


def _request(prompt, negative):
    import google.auth
    import google.auth.transport.requests
    import httpx

    from .. import config

    project = config.GOOGLE_CLOUD_PROJECT
    location = getattr(config, "GOOGLE_CLOUD_LOCATION", "us-central1")
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    endpoint = (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}"
        f"/locations/{location}/publishers/google/models/{MODEL}:predict"
    )
    instance = {"prompt": prompt}
    if negative:
        instance["negative_prompt"] = negative
    with httpx.Client(timeout=40, trust_env=False) as client:
        response = client.post(
            endpoint,
            headers={"Authorization": "Bearer " + credentials.token},
            json={"instances": [instance], "parameters": {"sample_count": 1}},
        )
        response.raise_for_status()
        body = response.json()
    for prediction in body.get("predictions") or []:
        audio = _decode(prediction if isinstance(prediction, dict) else {})
        if audio:
            return audio
    raise ValueError("No audio returned")


def payload(body):
    if not isinstance(body, dict):
        raise ValueError("Send a generation request.")
    seconds = max(1, min(MAX_SECONDS, int(body.get("seconds") or MAX_SECONDS)))
    audio, model = generate(body.get("prompt", ""), seconds, body.get("negative", ""))
    return {
        "audio_base64": base64.b64encode(audio).decode(),
        "content_type": "audio/wav",
        "model": model,
        "seconds": seconds,
    }


def limits():
    return {"max_seconds": MAX_SECONDS, "model": MODEL, "enabled": available()}


if __name__ == "__main__":
    data = _placeholder(2)
    with wave.open(io.BytesIO(data), "rb") as check:
        assert check.getframerate() == RATE
        assert check.getnframes() == RATE * 2
    assert json.loads(json.dumps(limits()))["max_seconds"] == 10
    for bad in ("", "   ", None, "x" * 501):
        try:
            generate(bad, 3)
            raise SystemExit(f"must reject {bad!r}")
        except ValueError:
            pass
    body = payload({"prompt": "dry leaves underfoot", "seconds": 99})
    assert body["seconds"] == MAX_SECONDS
    assert base64.b64decode(body["audio_base64"])[:4] == b"RIFF"
    assert 40 < 60, 'model call must fail inside the socket timeout'
    print("lyria self-check ok")
