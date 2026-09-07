#!/usr/bin/env python3
"""Run the offline A1 long-form recall and preservation check."""

import argparse
import json
from pathlib import Path

import numpy as np

from orpheus.domain import families, family_agent, projects, takes


def near_section(time_s, sections, margin=.35):
    return next((row for row in sections if row["range_s"][0] - margin <= time_s <= row["range_s"][1] + margin), None)


def main(fixture):
    truth = json.loads((fixture / "ground-truth.json").read_text())
    project = projects.create(fixture / truth["picture"], context="Controlled A1 multi-example validation")
    sections = truth["sections"]
    example_ranges = [[row["events_s"][0] - .08, row["events_s"][0] + .56] for row in sections]
    family = families.create(project["id"], "Walking variants", example_ranges[0], defer=True)
    for bounds in example_ranges[1:]:
        family = families.add_example(project["id"], family["id"], bounds)
    take = takes.add_take(project["id"], fixture / "grass-step.wav", "Controlled grass replacement", family_id=family["id"])
    preview = family_agent.render_baseline(project["id"], family["id"], persist=True)
    families.record_render_review(project["id"], family["id"], preview["id"], "approve")
    family = families.search(project["id"], family["id"])
    proposals = family["pending_matches"]
    initial_false = [row for row in proposals if near_section(row["refined_anchor_s"], sections) is None]
    if initial_false:
        family = families.review(project["id"], family["id"], [], [row["id"] for row in initial_false])
        proposals = family["pending_matches"]
    section_hits = {
        index + 1: sum(near_section(row["refined_anchor_s"], [section]) is not None for row in proposals)
        for index, section in enumerate(sections)
    }
    false_positives = [row for row in proposals if near_section(row["refined_anchor_s"], sections) is None]
    final = families.render(project["id"], family["id"], take["id"])
    original = families._read_pcm(projects.project_dir(project["id"]) / "mix.wav")
    rendered = families._read_pcm(projects.project_dir(project["id"]) / final["wav"])
    outside = np.ones(len(original), dtype=bool)
    for start, end in final["mix"]["ranges_s"]:
        outside[round(start * families.RATE):round(end * families.RATE)] = False
    report = {
        "schema": "orpheus-a1-validation.v1",
        "project_id": project["id"],
        "duration_s": project["seconds"],
        "confirmed_examples_s": example_ranges,
        "section_hits": section_hits,
        "section_recall": sum(count > 0 for count in section_hits.values()) / len(section_hits),
        "proposals": len(proposals),
        "initial_false_positives": len(initial_false),
        "false_positives": len(false_positives),
        "false_positive_anchors_s": [row["refined_anchor_s"] for row in false_positives],
        "clipped_samples": final["metrics"]["clipped_samples"],
        "picture_unchanged": final["metrics"]["picture_unchanged"],
        "outside_ranges_pcm_exact": bool(np.array_equal(original[outside], rendered[outside])),
        "paid_full_movie_calls": 0,
        "preview_duration_s": preview.get("preview_duration_s", 15),
    }
    output = projects.project_dir(project["id"]) / "a1-validation.json"
    projects.atomic(output, report)
    print(json.dumps(report, indent=2))
    if report["section_recall"] < 1 or report["clipped_samples"] or not report["picture_unchanged"] or not report["outside_ranges_pcm_exact"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path, nargs="?", default=Path("data/fixtures/a1-30-minute"))
    main(parser.parse_args().fixture)
