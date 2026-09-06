# Real-media UI test

Tested 2026-09-06 through the browser UI at `/workspace`.

## Fixture

The test combines two independently sourced recordings so the result is reproducible without using Orpheus's tuned shoe fixture:

- Picture: Wikimedia Commons [Pedestrian area codec test](https://commons.wikimedia.org/wiki/File:Video_Codec_Test_pedestrian_area_1080p25.y4m.webm), CC0. Its advertised audio stream decoded to silence, so only its picture was used.
- Original soundtrack: Wikimedia Commons [Walking on gravel](https://commons.wikimedia.org/wiki/File:Walkingongravel.ogg), by Secretlondon, CC BY-SA 3.0.
- Replacement take: Wikimedia Commons [Walking-on-gravel-38827](https://commons.wikimedia.org/wiki/File:Walking-on-gravel-38827.ogg), CC0.

The 11.96-second H.264/AAC test composite is a derived QA fixture, not bundled application media. Its original soundtrack contains real recorded footsteps. The local fixture and output bundle lives under ignored `data/examples/real-ui-test/`.

## Browser workflow result

1. Imported the full composite through **New project**.
2. Confirmed all 114 acoustic windows reached `ready`.
3. Marked `01.750–02.350` as the `Gravel footfall` seed.
4. Auditioned a proposed match; picture and audio sought to `03.108` together.
5. Kept five proposals and excluded one as an atomic batch. The seven remaining proposals were re-ranked.
6. Uploaded and auditioned the independent CC0 replacement, then saved it to the family.
7. Rendered candidate `f7a0bac5a223` and switched between original and replacement while preserving picture time.
8. Approved that exact candidate with a review note.

## Export checks

| Check | Result |
| --- | --- |
| Accepted events including seed | 6 |
| Rejected events | 1 |
| Pending after re-ranking | 7 |
| Unaccepted PCM samples | Byte-for-byte unchanged |
| Changed samples inside accepted ranges | 364,512 |
| Picture stream preserved | Yes |
| Clipped samples | 0 |
| Render hash matches receipt | Yes |
| Human approval stored in render receipt | Yes |
| Conservative overlap warnings | 1 |

The first source candidate also verified that Orpheus indexes a truly silent soundtrack without fabricating high-energy events. It was rejected as a matching fixture before the complete workflow run.
