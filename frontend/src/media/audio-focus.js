// Native media ownership: changing audition pauses the other audible paths.
const players = new Set();
export function registerMedia(node) {
  if (!node) return;
  players.add(node);
  return () => {
    node.pause();
    players.delete(node);
  };
}
export function claimMedia(...active) {
  for (const player of players) if (!active.includes(player)) player.pause();
}
