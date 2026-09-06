# Paid single-walker UI test

The paid run below is a historical record of the original silent-picture fixture. It has not been rewritten as a success.

Run: 2026-09-07, project `aed508f11aff4024`, family `e93113e582fd`.

## Fixture

- Picture: [Pixabay 160975](https://pixabay.com/videos/man-walking-alone-hiking-morning-160975/), one person walking in one continuous forest shot, offered under the Pixabay Content License.
- Search soundtrack: [Walking on gravel](https://commons.wikimedia.org/wiki/File:Walkingongravel.ogg), repeated to picture duration for a focused functional fixture.
- Replacement take: [Walking on gravel 38827](https://commons.wikimedia.org/wiki/File:Walking-on-gravel-38827.ogg).

The downloaded picture contained silent audio, so the search soundtrack was muxed locally. The composite is test data, not a claim that the independent recording is synchronized production sound.

## UI result

- Full 27.794-second media imported and all 273 acoustic windows indexed.
- One seed produced 46 pending matches. Eight matches plus the seed were accepted in one batch.
- Match 01 preview started at 25.146 seconds and stopped after its 25.786-second range.
- One replacement take was assigned to the family.

## Paid fitting result

The run did not produce a final selected render.

- Muse Spark rejected the first structured request with HTTP 400.
- Qwen returned HTTP 429.
- DeepSeek served 20 controller responses, then returned an unusable response during cycle 2.
- Gemini served five bounded audio analyses.
- Known Gemini usage: 6,210 input tokens, 5,778 output tokens, and $0.0031222.
- Reported DeepSeek usage: 1,475,420 input tokens and 29,966 output tokens. The provider receipt did not include controller cost, so cost is unknown rather than zero.

Orpheus withheld approval and the final family render. It retained one intermediate fitted layer with nine family-scoped rows. Its measured preview was -29.8 LUFS, -10.6 dBTP, zero clipped samples, and unchanged picture. Because the agent never selected it, this layer is diagnostic evidence rather than a deliverable.

## Findings

1. The requested model priority is active, but Muse Spark is not currently compatible with this tool schema and Qwen availability is unstable.
2. Controller context growth is excessive for a 28-second, nine-event job. Reduce repeated frames, tool receipts, and schema payloads before another paid benchmark.
3. Preserve and expose valid intermediate candidates after a late provider failure as clearly labelled drafts; keep approval disabled.
4. Show provider readiness before consent and surface the sanitized failure category in the workspace.
5. Limit the initial review queue and reveal more matches on demand. Forty-six rows for 28 seconds is operationally noisy even with per-row auditioning.

## Selected successor fixture

The user selected [man walking alone at morning with sound](https://www.youtube.com/watch?v=6VyMrePXqfs) for subsequent validation. It is a 28.212-second, 1920×1080 continuous shot of one walker with embedded stereo AAC audio. Unlike the original Pixabay fixture, its soundtrack was used directly.

Waveform inspection measured -44.0 dB mean volume and -17.8 dB peak. Repeated transients occur predominantly every 0.92–0.98 seconds, providing enough events for family matching. YouTube exposes no Creative Commons license metadata, and the uploader description provides no reuse grant. The download and derived project therefore remain ignored local QA data and must not be bundled or represented as reusable media.

Local Orpheus validation created project `37f76d82b1bb47c0` under `/tmp/orpheus-youtube-walker.vbcwIV`:

- all 277 acoustic windows indexed;
- nine waveform-aligned footstep events retained;
- 24 proposals remained pending after rescoring;
- [Walking through grass](https://pixabay.com/sound-effects/film-special-effects-walking-through-grass-80308/), a 12.33-second CC0 mono recording by vgraham1, replaced the earlier gravel take;
- replacement render `65f136f43ea0` preserved the picture and measured -26.2 LUFS / -0.5 dBTP;
- PCM outside accepted ranges remained byte-for-byte unchanged;
- 269,472 frames changed inside accepted ranges;
- zero samples clipped;
- browser QA exposed the original/replacement waveforms, family queue, take, render, evidence, and exports;
- bounded preview stopped on the first native `timeupdate` after the requested end, approximately 93 ms late in the observed run.

No paid inference was triggered during successor-fixture validation.
