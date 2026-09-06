"""Stateful ADK perception -> plan -> render -> evaluate -> revise loop."""

from pathlib import Path

from google.genai import types

from ..domain import arrangement
from . import perception

COMPLETION_WARNING_CALL = 25
INSPECTION_STOP_CALL = 30
MAX_REVIEW_BATCH_CENTERS = 5
MAX_REVIEW_CENTERS_PER_CYCLE = 20
MAX_REVIEW_CENTERS_PER_TURN = 100
MAX_ADAPTIVE_FRAMES_PER_CALL = 24
MAX_ADAPTIVE_FRAMES_PER_TURN = 96
MAX_AUDIO_REVIEWS = 20
MAX_WAVEFORM_CALLS = 20
MAX_BATCH_MAPPING_ROWS = 12
PROMPT_DIR = Path(__file__).with_name("prompts")


def _read_prompt(name):
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


INSTRUCTION = _read_prompt("controller-fallback.md")
MAPPED_INSTRUCTION = _read_prompt("controller-mapped.md")
PERCEPTION_INSTRUCTION = _read_prompt("perception.md")


def _read_prompt_sections(name):
    sections = {}
    current = None
    for line in _read_prompt(name).splitlines(keepends=True):
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {key: "".join(lines).rstrip("\n") for key, lines in sections.items()}


RUNTIME_PROMPTS = _read_prompt_sections("runtime.md")


def runtime_prompt(name, **values):
    return RUNTIME_PROMPTS[name].format(**values)


def frame_parts(frames):
    parts = []
    for timestamp, path in frames:
        parts.extend(
            [
                types.Part(
                    text=runtime_prompt("frame_label", timestamp=f"{timestamp:.4f}")
                ),
                types.Part.from_bytes(data=path.read_bytes(), mime_type="image/jpeg"),
            ]
        )
    return parts


def inspection_scope(event_count, source_count, previous_count, note_count):
    """Disclose bounded views without presenting a capped count as complete."""
    return {
        "detector_cap": 180,
        "audio_event_cap": perception.MAX_INVENTORY_EVENTS,
        "source_option_cap": arrangement.MAX_SOURCE_OPTIONS,
        "candidate_cap_may_have_omitted_events": max(event_count, source_count) >= 180,
        "previous_candidates_omitted_from_view": max(0, previous_count - 8),
        "project_notes_in_view": note_count,
        "note_window_limit": 12,
        "plan_row_limit": 100,
        "review_centers_per_cycle": 20,
        "review_centers_per_turn": 100,
        "warning": "Candidates are acoustic hypotheses, not an exhaustive inventory. Notes are a rolling view; full events remain in the session/log. Reaching a cap is not full-clip completion.",
    }


def perception_gate(state, enabled):
    """Require inspection attempts, never semantic agreement, before a preview."""
    if not enabled:
        return None
    if set(state.get("audio_attempts", {})) != {"target", "source"}:
        return {
            "error": "Attempt independent target and source inspect_audio before rendering."
        }
    return None
