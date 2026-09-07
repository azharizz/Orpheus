export const candidates = (p) => [
  ...(p.turn_details || []).flatMap((t) => t.candidates || []),
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
export function seedRange(start, end, duration) {
  const range = [Number(start), Number(end)];
  if (
    range.some((value) => !Number.isFinite(value)) ||
    range[0] < 0 ||
    range[1] > duration ||
    range[1] <= range[0]
  )
    throw Error("Sound example needs a start before its end, inside the film.");
  return range;
}
export const pendingMatches = (family) =>
  (family?.pending_matches || family?.matches || []).filter(
    (match) => !match.decision || match.decision === "pending",
  );
export const matchRange = (match) =>
  match.range_s || match.target_range_s || [match.start_s, match.end_s];
export function pageWindow(items, page, size = 5) {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const current = Math.min(Math.max(0, page), pages - 1);
  const start = current * size;
  return { items: items.slice(start, start + size), page: current, pages, start };
}
export const time = (n) =>
  `${Math.floor((Number(n) || 0) / 60)
    .toString()
    .padStart(2, "0")}:${((Number(n) || 0) % 60).toFixed(3).padStart(6, "0")}`;
export function label(value) {
  const known = {
    review_required: "Review required",
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

function spineRange(item = {}) {
  const range = matchRange(item) || [];
  const start = Number(range[0] ?? item.time_s ?? item.anchor_s);
  const end = Number(range[1]);
  if (!Number.isFinite(start)) return null;
  return [start, Number.isFinite(end) && end > start ? end : start + 0.08];
}

export function movieSpineMarkers(movie = {}, families = [], activeFamilyId = "", duration = 0, maxMarks = 96) {
  const family = families.find((item) => item.id === activeFamilyId) || families[0];
  const source = family
    ? [
      ...(family.accepted_ranges || []).map((item) => ({ ...(Array.isArray(item) ? { range_s: item } : item), family_id: family.id, kind: "accepted" })),
      ...pendingMatches(family).map((item) => ({ ...item, family_id: family.id, kind: "pending" })),
    ]
    : (movie.review_queue || []).filter((item) => item.status === "unreviewed" || item.status === "review_required").map((item) => ({ ...item, kind: item.kind === "noise" ? "noise" : "pending" }));
  const span = Math.max(1, Number(duration) || 1);
  const buckets = Math.max(1, Math.min(120, Math.floor(Number(maxMarks) || 96)));
  const grouped = new Map();
  // ponytail: cap permanent marks; selecting a cluster opens its full local detail.
  for (const item of source) {
    const range = spineRange(item);
    if (!range) continue;
    const index = Math.min(buckets - 1, Math.max(0, Math.floor(range[0] / span * buckets)));
    const key = `${item.kind}:${index}`;
    const current = grouped.get(key);
    if (current) {
      current.count += 1;
      current.range_s[0] = Math.min(current.range_s[0], range[0]);
      current.range_s[1] = Math.max(current.range_s[1], range[1]);
      continue;
    }
    grouped.set(key, { ...item, id: item.id || key, range_s: range, time_s: range[0], count: 1 });
  }
  return [...grouped.values()].sort((a, b) => a.range_s[0] - b.range_s[0]);
}

export function workspaceTarget(search = window.location.search) {
  const params = new URLSearchParams(search);
  const at = Number(params.get("time"));
  return {
    time: Number.isFinite(at) && at >= 0 ? at : 0,
    family: params.get("family") || "",
    event: params.get("event") || "",
    view: params.get("view") === "movie" ? "movie" : "part",
  };
}

export function partWindow(center, duration, span = 15) {
  const width = Math.min(duration, Math.max(5, Number(span) || 15));
  const start = Math.max(0, Math.min(duration - width, Number(center) - width / 2));
  return [Number(start.toFixed(3)), Number((start + width).toFixed(3))];
}
