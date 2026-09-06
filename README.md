# Orpheus

Orpheus is a local, single-user Foley workbench for finding repeated sound events in a complete video and replacing only the occurrences a human accepts.

## Workflow

1. Import one short video or full film. Orpheus preserves the source, creates a browser preview, extracts analysis audio, and builds a cached local sound index.
2. Mark one clear occurrence of a weak or unwanted sound.
3. Review acoustically similar moments. Similarity ranks candidates; it never changes audio automatically.
4. Record or upload one replacement take for that sound family.
5. Render locally, or explicitly authorize an optional paid agent-fitting pass.
6. Compare the original and replacement, then approve or reject the exact rendered candidate.

Accepted windows receive bounded gain ramps and the fitted replacement. Every unaccepted part of the soundtrack stays unchanged. Final masters reuse the untouched source video stream.

## Run locally

Requires Python 3.11+, FFmpeg/FFprobe, and Node.js 22.12+.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m orpheus
```

Open `http://127.0.0.1:8766`. The app has two routes: `/` and `/workspace`. Importing and local matching make no paid model calls. Configure OpenRouter in `.env` only for optional agent fitting; every run requires explicit consent and retains provider failover receipts.

Runtime limits live in `orpheus/config.py`. Media and sessions live under `data/`, or `ORPHEUS_DATA_DIR`. The reference lab is not a runtime dependency.

## Verify

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
npm test --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m orpheus.ops.benchmark_similarity \
  ../foley-agent-lab/assets/shoes-original.wav \
  ../foley-lab/fixtures/platform-contacts.json
```

Default tests use generated media and scripted provider responses. The annotated benchmark measures the local retrieval queue; neither check certifies artistic quality. Set `ORPHEUS_LIVE_MCP=1` to run the optional local Grafana MCP integration check.

## Structure

- `orpheus/domain/`: media, sound-family, take, render, and review logic.
- `orpheus/agent/`: bounded ADK fitting workflow and provider failover.
- `orpheus/server/`: loopback API, streamed uploads, and one background worker.
- `orpheus/ops/`: redacted telemetry, benchmark CLI, and Grafana helpers.
- `frontend/src/`: two-page React interface using an external store and callback refs; no `useEffect`.
- `observability/`: isolated Grafana, Loki, Tempo, and Prometheus assets.

See [PRODUCT.md](PRODUCT.md), [DESIGN.md](DESIGN.md), [benchmark results](docs/SIMILARITY_BENCHMARK.md), and [verified status](docs/STATUS.md).
