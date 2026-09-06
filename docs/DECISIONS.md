# Implementation decisions

## 2026-09-06 · Current product boundary

Orpheus is a local, single-user application with two pages: landing and workspace. The earlier GCP direction and legacy/v1/v2 compatibility are retired. Explicit controller-provider failover remains part of optional paid fitting.

## 2026-09-06 · Query-by-example retrieval

Two approaches were tested: compact FFmpeg/NumPy acoustic fingerprints and CLAP embeddings. The compact method met the annotated release gate; CLAP did not localize these short Foley contacts reliably enough and added a large model. The losing prototype and dependency are absent from the product. See [SIMILARITY_BENCHMARK.md](SIMILARITY_BENCHMARK.md).

Direct NumPy cosine search is sufficient for one film. A vector database and Faiss would add operating cost without changing the result at this scale.

## 2026-09-06 · Selective replacement

Accepted family ranges become explicit arrangement rows. Rendering applies bounded duck ramps and overlays the family take only in those ranges. Neural source separation is excluded because it adds a large model and possible isolation artifacts to a workflow that must remain deterministic and reviewable.

The local deterministic render and optional agent-fitted render are both retained. They share the same accepted-window confinement and human approval gate; the agent path exists when crop, timing, and gain need a bounded iterative pass.
