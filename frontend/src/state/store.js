import { useSyncExternalStore } from "react";
let state = {
  projects: [],
  running: false,
  config: null,
  observability: null,
  loading: true,
  error: "",
  busy: false,
  message: "",
  waveforms: {},
  takes: {},
  families: {},
};
const listeners = new Set();
export function update(patch) {
  state = { ...state, ...patch };
  listeners.forEach((fn) => fn());
}
export const snapshot = () => state;
let timer;
function subscribe(fn) {
  listeners.add(fn);
  if (listeners.size === 1) {
    refresh();
    timer = setInterval(refresh, 4000);
  }
  return () => {
    listeners.delete(fn);
    if (!listeners.size) clearInterval(timer);
  };
}
export const useStore = () => useSyncExternalStore(subscribe, snapshot);
export async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok)
    throw Error(data.error || `Request failed (${response.status})`);
  return data;
}
export const post = (path, data) =>
  api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
let refreshing = false;
let familyProject = "";
export async function refresh() {
  if (refreshing) return;
  refreshing = true;
  const activeFamilyProject = familyProject;
  try {
    const data = await api("/api/projects");
    update({ ...data, loading: false });
  } catch (error) {
    update({ error: `Projects unavailable: ${error.message}`, loading: false });
  }
  const results = await Promise.allSettled([
    api("/api/config"),
    api("/api/observability"),
    activeFamilyProject
      ? api(`/api/families?project_id=${encodeURIComponent(activeFamilyProject)}`)
      : Promise.resolve(null),
  ]);
  if (results[0].status === "fulfilled") update({ config: results[0].value });
  if (results[1].status === "fulfilled")
    update({ observability: results[1].value });
  else update({ observability: { error: results[1].reason.message } });
  if (activeFamilyProject && results[2].status === "fulfilled") {
    update({
      families: { ...state.families, [activeFamilyProject]: results[2].value },
    });
  }
  refreshing = false;
}
export async function action(work, message) {
  if (state.busy) return;
  update({ busy: true, message: "", error: "" });
  try {
    const result = await work();
    await refresh();
    update({ message: message || "Saved to project." });
    return result;
  } catch (error) {
    update({ error: error.message });
    return undefined;
  } finally {
    update({ busy: false });
  }
}
export const media = (pid, name) =>
  `/projects/${encodeURIComponent(pid)}/${name}`;
export function watchFamilies(pid) {
  familyProject = pid;
  if (!state.families[pid]) loadFamilies(pid);
  return () => {
    if (familyProject === pid) familyProject = "";
  };
}
export async function loadFamilies(pid) {
  try {
    const data = await api(
      `/api/families?project_id=${encodeURIComponent(pid)}`,
    );
    update({ families: { ...state.families, [pid]: data } });
    return data;
  } catch (error) {
    update({
      families: {
        ...state.families,
        [pid]: { families: [], error: error.message },
      },
    });
    return undefined;
  }
}
export async function loadTakes(pid) {
  try {
    const data = await api(`/api/takes?project_id=${encodeURIComponent(pid)}`);
    update({ takes: { ...state.takes, [pid]: data } });
  } catch (error) {
    update({ error: error.message });
  }
}
const pending = new Set();
export async function loadWave(pid, role, cid = "") {
  const key = [pid, role, cid].join(":");
  if (state.waveforms[key] || pending.has(key)) return;
  pending.add(key);
  try {
    const data = await api(
      "/api/waveform?" +
        new URLSearchParams({
          project_id: pid,
          role,
          ...(cid ? { candidate_id: cid } : {}),
        }),
    );
    update({ waveforms: { ...state.waveforms, [key]: data } });
  } catch (error) {
    update({
      waveforms: { ...state.waveforms, [key]: { error: error.message } },
    });
  } finally {
    pending.delete(key);
  }
}
