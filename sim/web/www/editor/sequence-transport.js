// Views of native transport telemetry. No browser clock or saved transport state.
import { arrangementEntries } from './sequence-model.js';
export const positionText = tick => {
  tick = Math.max(0, Math.floor(Number(tick) || 0));
  return `${Math.floor(tick / 384)}:${Math.floor(tick / 96) % 4}:${tick % 96}`;
};
export const timeText = (frames, rate) => {
  if (!Number.isFinite(frames) || !(rate > 0)) return '—';
  const ms = Math.floor(Math.max(0, frames) * 1000 / rate);
  return `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}.${String(ms % 1000).padStart(3, '0')}`;
};
export function barLimit(model, transport = {}) {
  if (model.song.length && transport.songFollow !== false) {
    const entries = arrangementEntries(model), last = entries.at(-1);
    return Math.max(0, last.startBar + last.bars - 1);
  }
  return Math.max(0, ...model.tracks.map((t, i) => Math.ceil((t.clips[transport.tracks?.[i]?.active ?? 0]?.length || 0) / 16) - 1));
}
export const neighboringSlot = (slots, selected, direction) => direction < 0
  ? slots.filter(s => s < selected).at(-1) ?? null : slots.find(s => s > selected) ?? null;
