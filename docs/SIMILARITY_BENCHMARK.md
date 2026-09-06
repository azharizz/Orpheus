# Similarity benchmark

## Release gate

The selected method must reach at least 90% recall, 75% review-queue precision, and 100 ms or lower median refined-onset error. A two-hour index must remain below 100 MB and 4 GB peak memory. Indexing and matching make no paid calls.

## Reviewed fixture

The benchmark uses `shoes-original.wav` and ten manually reviewed contacts in `platform-contacts.json`. The first reviewed contact is the seed. A retrieved anchor counts as correct when it lies within 100 ms of a reviewed contact. The queue size includes the confirmed seed.

Run it with:

```sh
.venv/bin/python -m orpheus.ops.benchmark_similarity \
  ../foley-agent-lab/assets/shoes-original.wav \
  ../foley-lab/fixtures/platform-contacts.json
```

## Results

| Method | Recall | Precision | F2 | Median onset error | Index | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 24×8 log-power time-frequency fingerprint, exact cosine | 90% | 75% | 0.865 | 0.052 ms | 61,244 B for 8.4 s | Qualifies |
| `laion/clap-htsat-unfused`, exact cosine over the same short crops | ≥90% target search | Below 75% for every tested qualifying-recall queue | — | — | ~618 MB model before index | Reject |

The compact index stores 192 float32 values per 100 ms hop. Two hours project to about 55.3 MB of vectors plus a small energy array and JSON receipt. Runtime indexing holds one 128-window feature batch and memory-mapped output, far below the 4 GB gate.

CLAP was evaluated because confirmed examples can benefit from reusable embeddings. Its standard ten-second input is poorly matched to sub-second contact localization: padding a 640 ms crop preserved broad acoustic context but did not separate enough rustles from footsteps at the required recall. It also imposed a large model for a result the compact method already met. No CLAP code or dependency ships.

## Interpretation

This is one tuned development fixture, not a universal accuracy claim. The queue deliberately favors recall because every match is reviewed. Accepted and rejected examples update subsequent ranking; scores are cosine-ranking evidence and are never shown as probabilities. A genuinely unseen set of materials and environments is still required before making broader product claims.

Research context: [CLAP documentation](https://huggingface.co/docs/transformers/model_doc/clap), [CLAP model card](https://huggingface.co/laion/clap-htsat-unfused/tree/main), [DCASE few-shot task](https://dcase.community/challenge2024/task-few-shot-bioacoustic-event-detection), and [noise-robust query-by-example research](https://arxiv.org/abs/2210.08624).
