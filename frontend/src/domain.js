export const candidates = (p) => [
  ...(p.turn_details || []).flatMap((t) => t.candidates || []),
  ...(p.assisted_candidates || []),
];
export function cue(value, duration) {
  const n = Number(value);
  if (value === "" || !Number.isFinite(n) || n < 0 || n >= duration)
    throw Error("Picture cue must be within the prepared scene.");
  return n;
}
export function validateFile(file, limit) {
  if (!file || !file.size) throw Error("Choose a non-empty media file.");
  if (file.size > limit)
    throw Error(`File exceeds ${Math.round(limit / 1048576)} MiB.`);
  return file;
}
export const time = (n) =>
  `${Math.floor((Number(n) || 0) / 60)
    .toString()
    .padStart(2, "0")}:${((Number(n) || 0) % 60).toFixed(3).padStart(6, "0")}`;
export function label(value) {
  const known = {
    review_required: "Review required",
    whole_soundtrack_replacement: "Whole soundtrack replacement",
    mono_analysis_copy: "Mono analysis copy",
    source_near_full_scale_samples: "Source near full scale",
  };
  return known[value] || String(value).replaceAll("_", " ");
}
export function matchVolume(level, levels) {
  const finite = levels.filter(Number.isFinite);
  return Number.isFinite(level) && finite.length
    ? Math.min(1, 10 ** ((Math.min(...finite) - level) / 20))
    : 1;
}
export function editRow(rows, index, field, value) {
  const numeric = Number(value);
  if (value === "" || !Number.isFinite(numeric))
    throw Error("Timing and gain need finite numeric values.");
  return rows.map((row, i) =>
    i !== index
      ? row
      : field.includes(".")
        ? {
            ...row,
            [field.split(".")[0]]: row[field.split(".")[0]].map((n, j) =>
              j === Number(field.split(".")[1]) ? numeric : n,
            ),
          }
        : { ...row, [field]: numeric },
  );
}
