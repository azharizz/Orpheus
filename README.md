# Orpheus

A local Foley workbench: prepare picture and independent sound, explicitly run fitting, audition alternatives, inspect evidence, and retain human judgments. Fit, Record and Review share one workspace.

## Run locally

Requires Python 3.11, FFmpeg/FFprobe, and Node.js 22.12 or newer.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m orpheus.web
```

Open http://127.0.0.1:8766. Set your OpenRouter key in `.env` before requesting paid fitting. Uploading prepares local media without starting inference. Runtime settings live in `orpheus/config.py`; project media and sessions live under `data/` (or `ORPHEUS_DATA_DIR`). The lab is not a runtime dependency.

The interface serves two routes: `/` and `/workspace`. Inputs are clipped to the configured opening window; fitted output replaces the whole soundtrack. Originals remain private. Browser microphone capture requires explicit permission and does not save until you choose Save.

## Check

```sh
.venv/bin/python -m unittest discover -s tests
npm test --prefix frontend
npm run build --prefix frontend
```

The default tests use synthetic media and scripted model responses. They establish processing and workflow wiring, not autonomous perceptual quality. The optional real Grafana MCP check requires running services and `ORPHEUS_LIVE_MCP=1`.

## Grafana

Provisioning, dashboards and Docker Compose are in `observability/`; the official MCP service is read-only. See `python -m orpheus.grafana --help` for setup and collector commands. Credentials and the evidence outbox belong in runtime storage and must not be committed.

## Status

Implementation and acceptance remain in progress. Read `docs/STATUS.md` for verified checks and remaining work. GCP deployment is outside this local delivery scope.
