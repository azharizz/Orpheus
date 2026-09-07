# Orpheus

Orpheus is a local, single-user Foley workbench for finding repeated sound events in a complete video and replacing only the occurrences a human accepts.

## Workflow

1. Import one short video or full film. Orpheus preserves the source, creates a browser preview, extracts analysis audio, and builds a cached local sound index.
2. Open a bounded **Part**, name the sound family, and add up to eight visibly and audibly confirmed examples when the same event varies across the film.
3. Record or upload its replacement SFX. Render a 15-second deterministic Part preview or explicitly authorize the family agent. Paid inference never receives or renders the full movie.
4. Compare the original and replacement against the same picture, then approve or reject that exact part render.
5. After approval, search the cached index across **Full Movie**. Review the ranked matches in batches; unclassified contact suggestions and possible noise only navigate back to a Part and never edit audio.
6. Render accepted ranges. Every rejected, pending, unclassified, and untouched range keeps its original PCM.

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

Generate the deterministic 30-minute long-form validation movie outside Git:

```sh
.venv/bin/python tools/generate_movie_fixture.py
```

The output lives at `data/fixtures/synthetic-30-minute/` and includes five non-identical walking sections, impact/cloth/noise/voice/music/quiet distractors, replacement SFX, and `ground-truth.json`. Pass `--duration 30` for a quick smoke fixture. Run the complete offline proof with:

```sh
ORPHEUS_DATA_DIR=/tmp/orpheus-a1 .venv/bin/python -m tools.validate_a1 data/fixtures/synthetic-30-minute
```

## Structure

- `orpheus/domain/`: movie analysis, media, sound-family, take, render, and review logic.
- `orpheus/agent/`: bounded ADK fitting workflow and provider failover.
- `orpheus/server/`: loopback API, streamed uploads, and the family fitting worker.
- `orpheus/ops/`: redacted telemetry, benchmark CLI, and Grafana helpers.
- `frontend/src/`: two-page React interface using an external store and callback refs; no `useEffect`.
- `observability/`: isolated Grafana, Loki, Tempo, and Prometheus assets.

See [PRODUCT.md](PRODUCT.md), [DESIGN.md](DESIGN.md), [benchmark results](docs/SIMILARITY_BENCHMARK.md), and [verified status](docs/STATUS.md).
