---
version: current
name: Orpheus
description: "A cinematic, picture-led Foley workbench."
colors:
  primary: "#FF5A36"
  surface-base: "#0C0E10"
  surface-raised: "#171A1D"
  surface-active: "#252A2F"
  text-primary: "#EFEFE8"
  text-secondary: "#ABB2B7"
  rule-subtle: "#343B42"
  control-edge: "#718089"
  focus: "#FFD39B"
  status-warning: "#EAC17C"
  status-error: "#FF8790"
  status-confirmed: "#9DCFAD"
typography:
  display: '700 112px/0.95 "Barlow Condensed", "Arial Narrow", sans-serif'
  body: '400 16px/1.5 "Source Sans 3", system-ui, sans-serif'
  label: '600 16px/1.5 "Source Sans 3", system-ui, sans-serif'
  data: '400 14px/20px ui-monospace, monospace'
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  gutter: 24px
  lg: 32px
  xl: 48px
  xxl: 64px
---

# Orpheus design contract

## Direction

Orpheus is an editing bench with the identity of a film title. Picture owns the focal plane; sound occupies a measured timeline; evidence stays adjacent and subordinate. The interface uses near-black grain, chalk text, restrained orange action accents, condensed display typography, and plain operational type.

The workspace must feel precise rather than ornamental. Never tint or grade user video. Grain belongs to the application surround and landing photographs, not over waveform data or footage.

## Reference synthesis

The four screenshots supplied by the owner define the visual standard. Their assets are references only and must not be copied.

| Reference | Carry into Orpheus | Exclude |
| --- | --- | --- |
| [Knockouts](https://knockouts.com/) | Confident condensed lettering, sparse red/orange emphasis, image-led composition | Promotional stamps and scratch effects over controls |
| [Echelon](https://echelon.framer.media/) | Generous gutters, photographic rhythm, navigation that recedes | Stock-gallery repetition and hidden project state |
| [Did Global Cinema](https://www.dg-cinema.com/en) | Filmstrip sequencing, precise framing, cinematic entrance scale | Permanent haze, distorted footage, fake viewfinder chrome |
| [BYLD](https://byld.dev/) | Numbered sequences, typographic confidence, terse instrument readouts | Neon bloom, fake technical labels, decorative grids |

The synthesis is visible in the large photographic ORPHEUS shutters, framed image sequence, quiet top navigation, numbered workspace steps, narrow readouts, and restrained orange. It must not become four effects stacked together.

## Pages

### Landing

- Header has no separator line. Use the serif Orpheus wordmark, centered Projects/New project navigation, and a quiet local-workspace status.
- The hero is a fixed typographic mask spelling ORPHEUS. Three original cinematic photographs move vertically inside the letters and change every three seconds.
- A long TV-grain transition bridges photographs. Text remains fixed while only the photographic layer moves.
- Keep the letters legible with sufficient image exposure and surrounding contrast; never add an unrelated glow or card.
- Below the mask, use one centered statement and a small balanced calibration mark, followed by the project entrance.
- Decorative motion has a visible pause control and stops under `prefers-reduced-motion`.

### Workspace

- Use the same header treatment as the landing page. Grain repeats through the full document height.
- Lead with picture and shared transport. Never duplicate competing playback controls.
- Keep Part and Full Movie as deep-linkable scale states behind one continuous review desk. The desk always shows the picture, shared transport, Original/Replacement switch, one narrow full-film spine, active-family status, and one next action.
- The film spine uses orange accepted marks, subdued pending marks, grouped nearby cues, and a real playhead. It replaces the permanent full-film waveform, density chart, lane stack, and review list.
- Selecting a cue opens one bottom Cue Sheet. It contains the bounded 5/15/30/60-second waveform, family creation, SFX performance, agent fitting, A/B audition, exact approval, and evidence relevant to that cue.
- Never stretch an hour-long waveform into a detail editor. Request only the visible audio interval at a bounded resolution.
- Keep contact, noise, loudness, Grafana receipts, and raw evidence under on-demand details rather than beside every decision.
- Present one sequential family workflow: mark, review one related moment at a time, perform, render/listen.
- Candidate audition clearly states the audible track, exact render identity, warnings, and approval status.

## Components and hierarchy

- **Wordmark:** recognizable but quiet; never a generic app-logo badge.
- **Text actions:** underlined orange text for secondary navigation and utility actions.
- **Primary action:** orange emphasis without oversized filled pills.
- **Inputs:** square or 4 px radius, dark raised surface, visible labels, 44 px minimum target.
- **Film spine:** compact full-picture navigation with grouped event markers and tabular time. The detailed source-derived waveform belongs in the Cue Sheet with its visible accepted/pending legend and keyboard range input.
- **Match queue:** one ruled cue at a time with time, evidence, rank, Keep, Exclude, and Previous/Next. Rank is visually secondary.
- **Family selector:** plain select plus Mark another sound. Current counts show kept and excluded decisions.
- **Recording:** explicit microphone permission, visible state, retained unsaved capture on upload failure.
- **Review:** original/replacement comparison followed by exact approve/reject controls; approval never appears inferred.
- **Evidence:** processing facts, hypotheses, warnings, and human decisions use distinct labels and semantic colors.

## Typography and color

Use self-hosted Barlow Condensed for display and Source Sans 3 for working text. Display type can be large at the entrance and family title; labels and evidence remain readable at ordinary scale. Do not use all-caps body paragraphs, condensed type for long copy, gradient text, tiny uppercase eyebrow labels, or arbitrary font changes.

Orange means action and brand emphasis. Green means confirmed, amber means warning, and rose means error. Status never relies on color alone. Neutral rules separate workflow rows without card grids.

## Motion and interaction

- Landing image drift is slow and continuous. Plate changes use an extended analog-static wipe rather than a crossfade.
- Functional media time always follows the real player; never ease or fake playhead progress.
- Selecting a match seeks the picture to its refined anchor and visibly retains the selected decision.
- Animate opacity and transform only. Avoid layout movement during playback.
- No cursor followers, parallax footage, magnetic buttons, hover sound, infinite marquees, auto-scroll, or strobing indicators.
- Under reduced motion, keep a static hero plate and all functional state changes.

## Responsive behavior

Desktop uses the picture, transport, and film spine as one desk, with a bottom Cue Sheet for local work. Mobile keeps that order in one readable column; the Cue Sheet becomes a bounded vertical drawer. Match actions remain adjacent to their event, headers wrap without clipping, and no horizontal page scroll is allowed.

## Accessibility and truth

- Every icon-only control has a label; every field has a persistent label.
- Keyboard focus uses the warm focus token and is never removed.
- Transport, recording, paid inference, and approval require explicit semantic controls.
- Errors persist inline until resolved. A toast may acknowledge a save but cannot be the only failure location.
- Similarity is described as ranking evidence. Do not show percent accuracy or imply semantic recognition.
- Disclose paid inference destinations and call cap before the run.
- Respect user media rights; use generated/original landing art and actual project stills only.

## Anti-slop constraints

Apply [Impeccable’s slop catalog](https://impeccable.style/slop/) and human visual review. Reject feature-card grids, glass panels, ornamental glows, excessive pills, gradient headlines, fake metrics, dashboard sidebars, generic AI symbols, repeated helper copy, decorative coordinates, and stock “magic” language.

The dark cinematic treatment and large masked title are deliberate reference-led exceptions. Confine them to the entrance; the editing workspace remains restrained and readable.

## Acceptance

- The first workspace viewport makes picture, film spine, selected family, and next action understandable.
- Landing and workspace share one header and full-height grain surround.
- All four references contribute through the synthesis without copied assets.
- 100 match rows, a long filename, empty state, errors, indexing, and stale evidence remain usable.
- Desktop and mobile passes show no clipping, hidden actions, illegible status, or accidental double playback.
- Reduced motion, keyboard navigation, microphone denial, upload failure, and paid-run consent have coherent states.
- Impeccable detection runs on the final changed frontend, followed by human browser review.
