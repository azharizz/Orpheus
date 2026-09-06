import React, { useState } from "react";
import { action, post, media, update } from "./store.js";
import { editRow } from "./domain.js";
const Json = ({ value }) => <pre>{JSON.stringify(value, null, 2)}</pre>;
export function Review({ p, c, rows, selected, locked, onCandidate }) {
  const [note, setNote] = useState("");
  const [draft, setDraft] = useState(null);
  const [jsonDraft, setJsonDraft] = useState(null);
  const row = (draft || rows)[selected];
  const verdict = async (value) =>
    action(
      () =>
        post("/api/review", {
          project_id: p.id,
          candidate_id: c.id,
          verdict: value,
          note,
        }),
      `Your ${value} judgment was saved for ${c.id}.`,
    );
  function change(field, value) {
    try {
      setDraft(editRow(draft || rows, selected, field, value));
    } catch (error) {
      update({ error: error.message });
    }
  }
  return (
    <section className="review" key={c.id}>
      <h3>Human review · {c.id}</h3>
      <p>
        {c.engineering_pass
          ? "Export measured. Timing and naturalness need your judgment."
          : `Technical flags: ${(c.flags || []).join(", ") || "Measurement not confirmed."}`}
      </p>
      <label>
        Review note <span className="muted">Optional</span>
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength="500"
        />
      </label>
      <div className="actions">
        <button disabled={locked} onClick={() => verdict("approve")}>
          Approve this sound
        </button>
        <button disabled={locked} onClick={() => verdict("reject")}>
          Reject this sound
        </button>
        <a href={media(p.id, c.id + ".wav")} download>
          Export WAV
        </a>
        <a href={media(p.id, c.id + ".mp4")} download>
          Export video
        </a>
        <a href={media(p.id, c.id + ".json")} download>
          Export receipt
        </a>
      </div>
      <details>
        <summary>Assisted correction · creates a new revision</summary>
        {row ? (
          <>
            <p>
              Selected action: {row.id}. Edits must remain inside its evidence
              windows.
            </p>
            <div className="numeric-grid">
              {[
                ["target_anchor_s", "Target anchor (s)"],
                ["source_anchor_s", "Source anchor (s)"],
                ["target_range_s.0", "Target start (s)"],
                ["target_range_s.1", "Target end (s)"],
                ["source_range_s.0", "Source start (s)"],
                ["source_range_s.1", "Source end (s)"],
                ["gain_db", "Gain (dB)"],
              ]
                .filter(([field]) => field.includes(".") || row[field] != null)
                .map(([field, label]) => (
                  <label key={field}>
                    {label}
                    <input
                      type="number"
                      step="0.01"
                      value={
                        field.includes(".")
                          ? row[field.split(".")[0]][field.split(".")[1]]
                          : row[field]
                      }
                      onChange={(e) => change(field, e.target.value)}
                    />
                  </label>
                ))}
            </div>
            <details>
              <summary>Edit complete mapping</summary>
              <p>
                Adjust dispositions, fades, repetition and evidence references.
                All edits are validated before rendering.
              </p>
              <label>
                Arrangement rows (JSON)
                <textarea
                  rows={14}
                  spellCheck={false}
                  value={jsonDraft ?? JSON.stringify(draft || rows, null, 2)}
                  onChange={(event) => setJsonDraft(event.target.value)}
                />
              </label>
              {jsonDraft !== null && (
                <p>
                  Complete mapping edits take precedence over numeric fields.
                </p>
              )}
            </details>
            <button
              disabled={locked || (!draft && jsonDraft === null)}
              onClick={async () => {
                const result = await action(
                  () =>
                    post("/api/assist", {
                      project_id: p.id,
                      candidate_id: c.id,
                      rows: jsonDraft === null ? draft : JSON.parse(jsonDraft),
                    }),
                  "Assisted revision rendered. New human review required.",
                );
                if (result) {
                  setDraft(null);
                  setJsonDraft(null);
                  onCandidate(result.id);
                }
              }}
            >
              Render assisted revision
            </button>
            <button
              onClick={() => {
                setDraft(null);
                setJsonDraft(null);
              }}
            >
              Reset edits
            </button>
          </>
        ) : (
          <p>This candidate has no editable arrangement.</p>
        )}
      </details>
      <details>
        <summary>Human judgments and exact audio identity</summary>
        <Json
          value={{
            candidate_id: c.id,
            audio_sha256: c.audio_sha256,
            reviews: (p.human_reviews || []).filter(
              (r) => r.candidate_id === c.id,
            ),
          }}
        />
      </details>
    </section>
  );
}
