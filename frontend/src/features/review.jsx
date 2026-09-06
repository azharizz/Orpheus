import React, { useState } from "react";
import { action, post, media } from "../state/store.js";

export function Review({ p, c, locked }) {
  const [note, setNote] = useState("");
  const verdict = (value) =>
    action(
      () => post("/api/review", {
        project_id: p.id,
        candidate_id: c.id,
        verdict: value,
        note,
      }),
      `Your ${value} judgment was saved for ${c.id}.`,
    );
  return (
    <section className="review" key={c.id}>
      <h3>Human review · {c.id}</h3>
      <p>Export measured. Timing and naturalness still need your judgment.</p>
      {c.warning && <p className="warning">{c.warning}</p>}
      {c.mix?.possible_dialogue_or_music_overlap_ids?.length > 0 && (
        <p className="warning">
          Possible dialogue or music overlaps at{" "}
          {c.mix.possible_dialogue_or_music_overlap_ids.length} accepted moments.
          Listen before approval; no source separation was applied.
        </p>
      )}
      <label>
        Review note <span className="muted">Optional</span>
        <input value={note} onChange={(event) => setNote(event.target.value)} maxLength="500" />
      </label>
      <div className="actions">
        <button className="primary" disabled={locked} onClick={() => verdict("approve")}>Approve this preview</button>
        <button disabled={locked} onClick={() => verdict("reject")}>Reject this preview</button>
        <a className="button-link" href={media(p.id, c.id + ".wav")} download>Export WAV</a>
        <a className="button-link" href={media(p.id, c.master || c.id + ".mp4")} download>Export picture master</a>
        <a className="button-link" href={media(p.id, c.id + ".json")} download>Export receipt</a>
      </div>
      <details>
        <summary>Exact audio identity</summary>
        <pre>{JSON.stringify({ candidate_id: c.id, audio_sha256: c.audio_sha256 }, null, 2)}</pre>
      </details>
    </section>
  );
}
