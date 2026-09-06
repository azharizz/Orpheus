# Orpheus Folder Restructure Implementation Plan

> **For agentic workers:** Execute this plan inline in the current task. Keep the existing v2 behavior and run the named checks after each boundary.

**Goal:** Group the standalone Orpheus backend, tests, and frontend by responsibility while preserving every current runtime behavior and entry point through the new canonical package layout.

**Architecture:** Keep `orpheus/config.py` as the package-wide settings boundary. Put media/project logic in `orpheus/domain/`, ADK workflow code and prompts in `orpheus/agent/`, the loopback server and worker in `orpheus/server/`, and telemetry/Grafana helpers in `orpheus/ops/`. Group frontend code into `app`, `features`, `media`, `state`, `styles`, `assets`, and `tests`.

**Tech Stack:** Python package with `unittest`, Google ADK, FFmpeg; Vite/React frontend with Node's built-in test runner.

**Spec:** `PRODUCT.md`, `DESIGN.md`, and the owner request to restructure `orpheus/`, `tests/`, and `frontend/src/` without changing v2 behavior.

## Global Constraints

- Preserve all current v2 workflow tools, receipts, routes, and provider failover.
- Keep the application local and single-user.
- Keep only `/` and `/workspace` as application routes.
- Keep every source file below 800 lines.
- Keep frontend declarative with zero `useEffect` and no imperative DOM selection.
- Keep the isolated top-level `observability/` Grafana assets.

### Task 1: Backend package boundaries

**Files:**
- Move domain modules to `orpheus/domain/`: `projects.py`, `media.py`, `fitting.py`, `texture.py`, `arrangement.py`, `takes.py`, `review.py`.
- Move workflow modules and prompts to `orpheus/agent/` and `orpheus/agent/prompts/`.
- Move service modules to `orpheus/server/`: `http.py`, `web.py`, `worker.py`.
- Move telemetry modules to `orpheus/ops/`: `observability.py`, `grafana.py`.
- Create package markers for each new directory.
- Update all relative imports, worker subprocess module path, prompt discovery, code hashing, README commands, and test patch targets.

**Check:** `../foley-agent-lab/.venv/bin/python -m unittest discover -s tests -t .`.

### Task 2: Test package boundaries

**Files:**
- Move core tests to `tests/core/`.
- Move workflow tests to `tests/workflow/`.
- Move HTTP tests to `tests/server/`.
- Move Grafana/telemetry tests to `tests/ops/`.
- Keep `tests/support.py` as the shared fixture module and add package markers for test subdirectories.

**Check:** `../foley-agent-lab/.venv/bin/python -m unittest discover -s tests -t .`.

### Task 3: Frontend package boundaries

**Files:**
- Move `main.jsx` and `workspace.jsx` to `frontend/src/app/`.
- Move `review.jsx`, `evidence.jsx`, and `takes.jsx` to `frontend/src/features/`.
- Move `audio-focus.js`, `recording.js`, and `transport.js` to `frontend/src/media/`.
- Move `domain.js` and `store.js` to `frontend/src/state/`.
- Move `style.css` to `frontend/src/styles/` and fonts to `frontend/src/assets/fonts/`.
- Move frontend tests to `frontend/src/tests/`.
- Update imports, Vite entry, CSS font URLs, and the `npm test` glob.

**Checks:** `npm test`, `npm run build`, and static scans for `useEffect`, imperative DOM APIs, and files over 800 lines.

### Task 4: Repository verification

**Files:** `README.md`, `docs/STATUS.md`, and the moved source/test files as needed.

- Update all documented commands and source layout references.
- Run formatting, unused-import checks, backend/frontend tests, and `git diff --check`.
- Confirm the working tree is clean after committing the restructure.
