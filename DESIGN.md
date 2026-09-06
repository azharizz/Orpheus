---
version: alpha
name: Orpheus
description: "A cinematic Foley workbench linking picture, sound, and evidence."
colors:
  primary: "#FF6844"
  surface-base: "#0C0E10"
  surface-raised: "#171A1D"
  surface-active: "#252A2F"
  text-primary: "#EFEFE8"
  text-secondary: "#ABB2B7"
  rule-subtle: "#343B42"
  control-edge: "#718089"
  on-accent: "#0C0E10"
  focus: "#FFD39B"
  status-warning: "#EAC17C"
  status-error: "#FF8790"
  status-confirmed: "#9DCFAD"
typography:
  caption:
    fontFamily: '"Source Sans 3", system-ui, sans-serif'
    fontSize: 12px
    fontWeight: 400
    lineHeight: 16px
  data:
    fontFamily: 'ui-monospace, "SFMono-Regular", Consolas, monospace'
    fontSize: 14px
    fontWeight: 400
    lineHeight: 20px
    fontFeature: '"tnum"'
  body:
    fontFamily: '"Source Sans 3", system-ui, sans-serif'
    fontSize: 16px
    fontWeight: 400
    lineHeight: 24px
  label:
    fontFamily: '"Source Sans 3", system-ui, sans-serif'
    fontSize: 16px
    fontWeight: 600
    lineHeight: 24px
  section:
    fontFamily: '"Source Sans 3", system-ui, sans-serif'
    fontSize: 20px
    fontWeight: 600
    lineHeight: 28px
  title:
    fontFamily: '"Source Sans 3", system-ui, sans-serif'
    fontSize: 32px
    fontWeight: 600
    lineHeight: 36px
  wordmark:
    fontFamily: '"Barlow Condensed", "Arial Narrow", sans-serif'
    fontSize: 24px
    fontWeight: 600
    lineHeight: 28px
  display:
    fontFamily: '"Barlow Condensed", "Arial Narrow", sans-serif'
    fontSize: 112px
    fontWeight: 700
    lineHeight: 0.95
    letterSpacing: -0.01em
rounded:
  none: 0px
  sm: 4px
spacing:
  xs: 4px
  sm: 8px
  compact: 12px
  md: 16px
  gutter: 24px
  lg: 32px
  xl: 48px
  xxl: 64px
components:
  text-action:
    backgroundColor: "{colors.surface-base}"
    textColor: "{colors.primary}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "{spacing.sm}"
  text-action-hover:
    backgroundColor: "{colors.surface-active}"
    textColor: "{colors.primary}"
  text-action-focus:
    backgroundColor: "{colors.surface-base}"
    textColor: "{colors.focus}"
  solid-action:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-accent}"
    typography: "{typography.label}"
    padding: "{spacing.compact}"
    rounded: "{rounded.sm}"
  input:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    padding: "{spacing.compact}"
    rounded: "{rounded.sm}"
  ledger-row:
    backgroundColor: "{colors.surface-base}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body}"
    padding: "{spacing.compact}"
    rounded: "{rounded.none}"
  ledger-row-selected:
    backgroundColor: "{colors.surface-active}"
    textColor: "{colors.text-primary}"
  evidence-rail:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.body}"
    padding: "{spacing.md}"
  evidence-warning:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.status-warning}"
  evidence-error:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.status-error}"
  evidence-confirmed:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.status-confirmed}"
---

<!-- Authored design contract, not extracted implementation evidence. Reconcile with the built UI using Impeccable document after implementation. -->

# Design System: Orpheus

## Overview

**Creative North Star: "Picture, sound, evidence"**

Version 1 · 2026-09-06 · Intended visual system for the clean application. Not a description of a finished UI.

Read [PRODUCT.md](PRODUCT.md) first. It owns behavior, permissions, data, limits and truth. This document owns visual hierarchy, component presentation, tokens, motion, and interaction affordances. Both workflows—independent fitting and recorded takes—share one system.

The intended deployment is **GCP**, as confirmed by the owner; local V2 is only the current prototype. Preserve the visual system across environments, but adapt upload/save/connectivity wording to the real destination. Never present cloud-persisted media as local-only.

**An editing bench with the identity of a film title—not a dashboard dressed as a cinema website.**

Picture occupies the focal plane. Real sound occupies the timeline. An adjacent evidence rail explains the current uncertainty and next useful correction. The recognizable gesture is following one selected action from picture frame to target anchor, source landmark, rendered sound and measured receipt.

Use near-black neutral surfaces, chalk text, restrained vermilion action accents, condensed display typography and clean operational text. The owner supplied dark, cinematic references; this is a brief-led choice, not a default assumption that all audio software must be dark. A neutral surround supports picture evaluation; never tint or grade the video itself.

### Reference synthesis

The four user-supplied screenshots are the visual references. The linked live pages were also consulted on 2026-09-06; this document does not infer hidden interactions or exact fonts from them.

| Reference | Carry into Orpheus | Do not carry into the editing bench |
| --- | --- | --- |
| [Knockouts](https://knockouts.com/) | Confident condensed letterforms, sparse red emphasis, imagery that owns the composition | Promotional stamps, scratch effects over controls, huge outlined sentences blocking the task |
| [Echelon](https://echelon.framer.media/) | Image-led project browsing, generous gutters, navigation that recedes | Unrelated stock gallery, endless moving tiles, portfolio interactions that hide project state |
| [Did Global Cinema](https://www.dg-cinema.com/en) | Filmstrip sequencing and precise framing; cinematic scale at the project entrance | Permanent red haze, perspective distortion of editing footage, artificial viewfinder ornaments |
| [BYLD](https://byld.dev/) | Typographic confidence, numbered sections where sequence matters, terse instrument readouts | Neon bloom, decorative coordinate grids, unreadable blue text, fake Japanese/specification labels |

The mix happens through **type, framing, image rhythm and control restraint**, not by stacking four sites' visual effects. Reference logos, portraits, artwork and proprietary assets are not licensed Orpheus assets. Do not reuse them as product content.

**Key Characteristics:**

- Picture-led working surface with a restrained cinematic identity.
- Confident display type; readable operational typography.
- Low-chrome controls with explicit, accessible actions.
- Evidence, uncertainty and human judgment remain visually distinct.

This file follows the [Google DESIGN.md format](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md): YAML tokens are the normative values; the eight ordered Markdown sections explain their use. These are authored implementation requirements, not tokens extracted from a built application. A component sidecar is not required by this format and is not created here. `version: alpha` identifies the format version, not the application's maturity.

### Motion grammar

- `--motion-fast: 120ms`, `--motion-normal: 180ms`, `--motion-panel: 240ms`; transitions use `cubic-bezier(0.2, 0, 0, 1)`.
- Signature interaction: selecting an event updates picture position, selected source crop and evidence together; a short emphasis locates the related marks. Do not animate them through invented intermediate timestamps.
- Animate opacity/transform for context changes, not layout during playback. Playhead movement follows real media time, never an easing animation.
- No entrance choreography before the user can work, infinite marquees, cursor followers, parallax footage, pulsing “AI” decoration, or sound on hover.
- Honor `prefers-reduced-motion`: remove spatial transitions and decorative emphasis; retain functional playback and visible state changes. No strobing recording indicator.
- Optional project-entry filmstrip movement must be user-driven. Actual media, not chrome, provides energy.

## Colors

Restrained color strategy: neutral working planes, one primary action accent, separate semantic feedback colors. Chart roles require labels and line styles; color is supplementary.

| Token | Value | Use |
| --- | --- | --- |
| `--surface-base` | `#0C0E10` | App ground and neutral picture surround |
| `--surface-raised` | `#171A1D` | Context rail, menus, editable fields when separation is necessary |
| `--surface-active` | `#252A2F` | Selected row/tab or hover background; no floating card shell |
| `--text-primary` | `#EFEFE8` | Main copy, labels, measurements |
| `--text-secondary` | `#ABB2B7` | Supporting copy, units and provenance |
| `--rule-subtle` | `#343B42` | Nonessential separators; not the sole outline of an interactive field |
| `--control-edge` | `#718089` | Input/slider edges that must be visible |
| `--accent` | `#FF6844` | Current user action, selection cue and playhead emphasis |
| `--on-accent` | `#0C0E10` | Text on the rare solid accent surface; not white |
| `--focus` | `#FFD39B` | Dedicated keyboard focus ring |
| `--status-warning` | `#EAC17C` | Provisional/stale/degraded evidence with text |
| `--status-error` | `#FF8790` | Failed operation or invalid input with text |
| `--status-confirmed` | `#9DCFAD` | Human-approved or explicitly completed technical check, always qualified |

The table's CSS aliases map to the same-named YAML color keys, except `--accent`, which maps to `colors.primary`. YAML is authoritative; update this table together with it. No extra color literals without updating the contract. Data media are exempt from palette restrictions. Use primary/secondary strokes and dashed lines for target/source/candidate distinction; do not invent one saturated color per tool.

Check final computed contrast: body/action text at least 4.5:1, large text and essential non-text controls at least 3:1. Never lower text opacity to make it “subtle.” Scope confirmation: **Export measured** is not **Sound approved**.

## Typography

These are chosen type directions, not claims about installed font assets or the reference sites' font names. Before shipping, acquire appropriate licensed font files, retain licenses, and self-host only the required weights. If unavailable, use the documented fallbacks without blocking the app.

| Token | Family and fallback | Usage |
| --- | --- | --- |
| `--font-display` | `"Barlow Condensed", "Arial Narrow", sans-serif` | Orpheus wordmark treatment and short entrance titles, weight 600/700 |
| `--font-ui` | `"Source Sans 3", system-ui, sans-serif` | Body, controls, navigation, headings in the workspace, weights 400/600 |
| `--font-data` | `ui-monospace, "SFMono-Regular", Consolas, monospace` | Timecodes, units, hashes, aligned measurement columns only |

| Token | Size / line height | Usage |
| --- | --- | --- |
| `--type-caption` | 12px / 16px | Supplementary provenance, never the only label of a critical control |
| `--type-data` | 14px / 20px | Readable timecodes and table data |
| `--type-body` | 16px / 24px | Controls, body, field labels |
| `--type-section` | 20px / 28px | Contextual section headings |
| `--type-title` | 32px / 36px | Scene/library title |
| `--type-display` | `clamp(48px, 7vw, 112px)` / 0.95 | Entrance wordmark only; one or two short words |

Use tabular numerals for time and measurements. Do not use condensed fonts for tables, all-caps paragraphs, tiny tracked eyebrow labels, or monospace everywhere. Display tracking may be -0.01em to 0; body tracking stays normal. Functional copy is sentence case. Long filenames wrap or truncate with a keyboard-accessible full-name disclosure; they never widen the whole app.

The YAML defines concrete type roles. `display.fontSize` is the 112px upper bound; apply the table's responsive clamp at the entrance only. The format accepts px/em/rem dimensions, so the CSS clamp is intentionally described here rather than stored as an invalid dimension token. `label` is the semibold body-size action role; `wordmark` is the compact 24px in-project identity. Do not create a second independent type scale from the CSS aliases.

## Layout

- Spacing scale: `4, 8, 12, 16, 24, 32, 48, 64` px. Primary gap 24px; dense row gap 8–12px. Use more space before a new section than between its heading and content.

This file temporarily contains the surface-specific contract because the requested deliverable is exactly two Markdown files. A later implementation may extract surface briefs without changing these decisions.

| Surface | Mode | Primary composition |
| --- | --- | --- |
| Project library/entrance | Experience leading into Operate | Real scene stills in an open filmstrip/gallery; name, duration and honest status per project |
| Fitting workspace | Operate | Large neutral picture stage, timeline below, contextual source/evidence rail |
| Recording workspace | Operate | Picture, cue, persistent recording transport, then take ledger |
| Compare/review | Operate | Same picture position with explicit original/candidate audio selection and focused differences |
| Evidence detail | Read within Operate | Selected observation, provenance and linked Grafana receipt; raw logs behind disclosure |

No separate marketing site is required by this contract. If a landing page is later commissioned, its Persuade mode needs a separate brief and real proof; do not insert a sales hero before every editing session.

### Desktop first viewport

At 1440 × 900: 24px outer gutters; 56px top rail; main area uses the remaining height without hiding critical actions. Allocate roughly 3:1 width to picture/work and the 300–360px contextual rail. Timeline begins within the first viewport; details may continue below. Avoid rigid height arithmetic that clips at zoom or on shorter displays.

```text
Orpheus       Projects / Scene name          Fit · Record · Review    Run state
─────────────────────────────────────────────────────────────────────────────
                                                    │ Selected action
                PICTURE / SHARED PLAYHEAD            │ source crop / audition
                                                    │ uncertainty / evidence
────────────────────────────────────────────────────┤
 Play  00:03.240    Original / Candidate A / B        │ Current comparison
 Target activity    ────────┆─────────────────        │ timing / level / scope
 Fitted effects     ───────◆┆───────────────           │ measured / hypothesized
 Source selection          ┆                         │ Open Grafana ↗
─────────────────────────────────────────────────────────────────────────────
Relevant next action as a text command       Saved revision / measurement age
```

The diagram sets hierarchy, not immutable pixels or an already working route. The source recording has its own ruler: visually aligning the source lane below the target must not imply their timestamps share a clock.

Project-entry composition can use a large one-word **Orpheus** treatment beside real imagery. Once inside a project, reduce the mark to 24px. No giant statement above the player, repeated dashboard-card grid, or long onboarding text pushing the working surface below the fold.

### Responsive and accessible behavior

- At 1200px and above: picture/timeline plus contextual rail. At 768–1199px: rail becomes an inline expandable region below the stage. At 767px and below: stack picture, transport, selected event/take and evidence; use a contained timeline scroller or event list.
- At 390px width and 200% zoom: primary task, recording stop, errors and focus remain reachable. No compulsory horizontal scrolling of the entire page. Expanded logs may scroll within a labelled region.
- Pointer targets at least 24 × 24px with adequate spacing; use 44 × 44px for touch transport and primary commands even when the visible glyph/text is smaller.
- Focus ring: 2px `--focus`, 3px offset; it is not removed for aesthetic reasons. Focus must not be hidden by sticky rails.
- Shortcuts do not fire while typing. Publish shortcuts in help; support Escape for reversible menus/drawers. Do not make a shortcut silently stop or save an agent run without a supported backend contract.
- Label sliders, waveform selections, playback track and units. Keyboard and numeric alternatives must exist for timing/crop edits. Announce completed operations/failures in a restrained live region, not every meter sample.
- Represent status with words and shape as well as color. Never require hearing alone to know whether a file loaded, a run failed, or capture is active. Perceptual sound approval still requires suitable human evaluation; visual metrics are not a substitute.

## Elevation & Depth

Use flat surfaces and tonal separation; no shadow vocabulary is defined.

- Elevation: use surface contrast, not diffuse shadows or glass blur. Opaque popovers; no permanent fog, vignette or bloom over working content.
- Layer order: base 0, timeline overlays 10, sticky transport 20, menu/drawer 30, explicit confirmation overlay 40. Never cover the stop-recording control with a tooltip or toast.

**The Quiet Surround Rule.** UI depth must never tint footage, obscure sound evidence or cover transport controls.

## Shapes

- Radius scale: `0px` for rails, footage, rows and timeline clips; `4px` for fields, menus and popovers. A circle is reserved for a recording indicator/transport glyph, not every tag or action.
- Border widths: `1px` separators/control edges, `2px` selected timeline boundary or focus ring. Avoid thick accent strips on card sides.
- The only measurement grid is a real time/level ruler. No decorative blueprint background.

**The Functional Geometry Rule.** Frames, rulers and handles describe an actual crop, interval or measurement; they are not background decoration.

## Components

The YAML defines component atoms and sibling state variants. These are specifications, not a claim that component code exists. Use the base variant properties for shared styling; state variants change only their stated properties. Borders and focus outlines remain prose rules because the current format does not define those component property tokens. Use `colors.control-edge` for essential control outlines and `colors.rule-subtle` only for nonessential dividers.

Text actions are the default. `solid-action` is a rare emphasis variant, not a requirement to add a filled button to every pane. Keep selected-row and focus states distinct: selected rows use the active surface; keyboard focus always adds the defined outline. Invalid fields use the error color for their outline plus a written error; disabled actions retain readable text and explain the prerequisite without reducing opacity. Menus use the raised surface and small radius. Transport controls retain visible labels, touch sizing and conventional icons.

### Low-chrome interaction requirements

**Remove button clutter, not the user's ability to act.** The owner's dislike is implemented as low visual chrome, direct manipulation, selectable rows, text commands, and contextual controls. Actions still use semantic `<button>` elements when appropriate; navigation uses links. Never replace an accessible button with an unlabelled clickable `div`.

| Task | Preferred presentation | Accessible/explicit behavior |
| --- | --- | --- |
| Open project | Selectable real-thumbnail row or title link | Keyboard focus, meaningful name, status included as text |
| Add media | Open drop surface with underlined “Choose video” / “Choose sound” | Native file picker alternative; importing does not spend credit |
| Switch Fit/Record/Review | Text tabs with underline and selected state | Correct tab/link semantics according to routing; predictable focus |
| Start agent | One contextual “Run fitting · uses API credit” text command | Explicit activation; visible while ready; never auto-run on field blur |
| Play/pause | Compact conventional transport icon with label/tooltip | Semantic button, Space outside text inputs; no autoplay audio |
| Set timing/crop | Direct timeline handle/scrubbing | Focusable control plus numeric field or stepper equivalent |
| Choose/compare take | Selectable ledger row; inline audition control | Separate selection from playback and paid fitting |
| Record | Labelled record transport plus elapsed time | Explicit microphone gesture; persistent stop action when recording |
| Compare audio | Text selector “Original / A / B” | One audible path at a time; selected track named, not color-only |
| Inspect evidence | Expandable inline finding and “Open Grafana ↗” link | User opens detail; no automatic context switches |
| Approve/reject | Two quiet text actions beside the reviewed candidate | Exact candidate/hash association; approval never hidden in a gesture |
| More actions | One labelled overflow menu when needed | Not a dumping ground for the primary task or failure recovery |

At most one visually dominant action per active pane; no repeated “Generate” controls on every card. No mandatory hover, drag, long press, double-click, context menu or shortcut. A visible fallback always exists. No global unmodified letter shortcut for a paid or destructive action. A command palette is optional future work, not the sole path through the app.

Show disabled controls only when the user can understand how to enable them. Use concise adjacent explanation, not a disabled mystery. Unknown/deferred capabilities appear as explanatory text, not fake working controls.

### Workspace components — intended behavior

#### Picture stage and transport

Preserve native aspect ratio, color and sharpness; letterbox on the neutral base. Do not perspective-transform or darken picture to match the brand. Metadata sits outside the image. Overlay only useful playhead/review marks, hideable without losing accessible alternatives. Decorative frame brackets are prohibited; actual crop/review handles may use corners because they perform a task.

The intended compare transport holds the same media time when switching original/A/B. Until synchronization is implemented and verified, label independent players honestly rather than imply sync. Browser buffering and decode failures show their own state; they are not “agent thinking.”

#### Timeline and selected action

Use separate target, fitted-output and source rulers. Show source-to-target alignment as a selected mapping, not a shared false clock. Render anchors as distinct labelled landmarks; show uncertainty as a bracketed range, not a falsely precise dot. Use real waveform data; never decorative waveform bars.

Selection reveals a single relevant evidence story in the rail: observed frame/range → chosen source crop → fitted landmark → decoded output → unresolved issue. Unmapped, omitted, unmatched and unknown must be distinct text states; silence is not automatically a defect.

Allow zoom and contained horizontal scrolling without page-wide overflow. An ordered event list is the accessible alternative. Numeric precision must follow the measurement: exact sample placement does not make an approximate human annotation millisecond-accurate.

#### Take ledger

Use rows separated by spacing/rules, not nested cards. Show take name/brief, actual duration, cue/clock uncertainty, audition, and comparison state. Put expanded measurements under the selected row. Retain identity when sorting. No star ranking or “best take” badge from a spectral heuristic.

During capture show **Recording**, elapsed time, active microphone, picture cue and **Stop**. A red dot without words is insufficient. At completion say **Captured in this browser — audition before saving** when that is true. On GCP, distinguish **Uploading**, **Saved to project**, **Upload failed — recording retained in this browser**, and an actual inference request. Do not suggest capture was persisted or sent to a model unless it was.

#### Evidence rail and Grafana handoff

Default to the selected decision, not every available metric. Start with at most three relevant findings; allow full measurements and raw receipts in disclosure. Compare values with units, candidate identity, scope and freshness. Graphs need labelled axes, honest ranges, and distinction between wall-clock and media time.

For example: **Peak lands 42 ms before the proposed contact** is useful; **Timing score 97%** without independent calibration is not. Synthetic example numbers must be labelled as illustrative outside a real receipt.

Show `Fresh`, `Pending export`, `Stale`, `Unavailable`, or `No observations` with last-observed/queried times where available. A configured endpoint is not proof of live connectivity. Deep links should carry the selected project/candidate and time range where supported. Grafana remains a separate operational interface using its native theme; do not promise that these tokens reskin Grafana OSS or hide its provenance behind a decorative imitation.

#### Run state and feedback

| State | Visual/wording contract |
| --- | --- |
| Empty | Direct import instruction and real file controls; no fake demo project presented as user work |
| Preparing | File/phase name and indeterminate progress unless actual completion is known |
| Agent running | Current operation, elapsed time, calls used/limit when known; no fabricated percent complete |
| Recoverable row error | Keep successful rows visible and mark the failed row/reason inline |
| Provider failure | Name the failed capability and available fallback; no wall of raw exceptions |
| Grafana unavailable | Keep candidate accessible with degraded evidence notice and safe retry path |
| Review required | Candidate visible, unapproved status, measured changes and unresolved issue |
| Human approved | Exact reviewed candidate identified; no transfer of the badge to a new revision |
| Unsuitable | State what is missing and the next possible source/take action; no fake preview |

Persistent problems remain inline. Toasts may acknowledge a confirmed save to its actual destination, but must not be the only place a failure, paid run, recording state, or approval appears. Show interrupted uploads and expired access explicitly; never discard a browser take merely because cloud persistence failed. Raw JSON belongs behind disclosure, not in the default editing experience.

## Do's and Don'ts

### Do

- **Do** use real scene stills, measured waveforms and visible evidence provenance.
- **Do** preserve the four-reference synthesis, GCP direction and low-button preference.
- **Do** retain keyboard paths, explicit recording/paid-run consent and labelled uncertainty.
- **Do** re-run document in scan mode once Orpheus has a real implementation.

### Don't

- **Don't** replace semantic actions with inaccessible clickable text or hidden gestures.
- **Don't** fabricate accuracy, progress, approval, live telemetry or implemented capabilities.
- **Don't** copy reference assets or add decorative dashboard chrome.
- **Don't** treat this seed as an extracted token/component library.

### Anti-slop rules and justified expression

[Impeccable's slop catalog](https://impeccable.style/slop/) identifies recurring generated-interface defaults and quality defects. Use its detector and human critique together: a clean automated result is not proof of good hierarchy or useful interaction.

For Orpheus, reject generic feature-card grids, glass panels, ornamental glows, fake measurement grids, pill-heavy controls, gradient headlines, decorative statistics, redundant helper copy, undersized labels and stock “AI magic” imagery. Prefer real media, decisive typography, open rails and explicit states. These rules are informed by the catalog; the concrete component and token decisions above are Orpheus-specific.

The brief intentionally permits dark cinematic presentation and a large short entrance wordmark. These exceptions belong at the entrance, not above every task. Never use anti-slop guidance as a reason to discard the owner's reference direction; remove ornamental interference rather than drain its confidence.

### Asset, performance, and content rules

Use actual user scene stills and source-derived waveforms. Label fixtures as examples. Confirm reuse rights before publishing benchmark media. The four supplied reference screenshots guide design; their temporary attachment paths are not production dependencies.

No font/icon library or animation framework is mandated by these Markdown contracts. Prefer existing/native controls where they satisfy the visual and functional contract. Use a small consistent set of simple SVG transport/navigation icons; no improvised cinematic illustrations.

Lazy-load library thumbnails and unselected media, keep only selected playback active, and stop capture tracks promptly. Do not download every candidate audio file to draw a gallery. Decorative images, textures and video backgrounds are unnecessary in the workspace. Font loading must not block labels or change timeline time measurements.

Voice examples: **Inspect source**, **Review this contact**, **Saved to project**, **Audio observer unavailable**, **Needs listening review**. Use **Saved locally** only for an actual local save. Avoid **Perfect**, **Magic**, **Optimized 100%**, **Studio-grade**, or **Success** without its specific scope.

### Implementation and Impeccable handoff

The owner explicitly requested a design contract before implementation. Therefore these are **intended tokens and component rules**, not extracted production styles or an approved pixel-perfect comp. No new app framework, cloud deployment, generated mockup, sidecar configuration or asset package is created by this task.

When building in this directory:

1. Load PRODUCT.md and DESIGN.md as the local authorities. Use Impeccable context at the Orpheus project boundary; do not inherit the old V2 card styling as the new visual authority.
2. Preserve the single reference synthesis above. The owner delegated the mix; do not reopen a choice of four unrelated themes unless requested.
3. Implement one complete working path first: import → explicit run → selected event/source/evidence → compare → review. Recording must share its player, transport and evidence language.
4. Validate desktop and mobile in a bounded visual pass, plus keyboard navigation, errors, empty data, long filenames, 100-event content, stale Grafana and permission denial. Check contrast on rendered states, not just the palette table.
5. Run the locally installed Impeccable audit/critique/detection workflow supported by that version; verify commands rather than inventing a `slop` command. Record real findings, not a fabricated all-clear.
6. Update this document when implementation evidence requires a deliberate revision. Document exceptions and acceptance gaps. Add any machine-readable sidecar/surface brief only as a later explicit implementation step; do not claim one exists now.

#### Design acceptance checklist

- [ ] Picture, timeline and current next action are understandable in the first working viewport.
- [ ] All four references contribute through the documented synthesis; no copied logos/assets or conflicting effect stack.
- [ ] Low-button presentation retains semantic controls, visible actions, keyboard paths and explicit paid/microphone consent.
- [ ] Source time, target time, wall-clock time and uncertainty remain distinct.
- [ ] Selected rows, audible track, recording state and human approval cannot be confused.
- [ ] Relevant sound findings are visible; full data and Grafana receipts are accessible without occupying the entire default layout.
- [ ] No-data, stale, provider failure and unmeasured output are distinguishable from success.
- [ ] Real media and accessible evidence carry the identity; decorative dashboard chrome does not.
- [ ] Responsive, contrast, keyboard, reduced-motion and microphone error paths are checked in the actual build.
- [ ] Backend capability gaps remain visible; no design-only interaction is advertised as working.

These boxes intentionally remain unchecked until the clean application is built and examined.
