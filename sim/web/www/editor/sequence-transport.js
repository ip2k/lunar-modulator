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

// Selection belongs to the editor; these counters and destinations belong to
// native playback. Grouped arrangement entries count repeated presses once.
export function transportNavigation(model, transport = {}, track = 0) {
  const followingSong = model.song.length > 0 && transport.songFollow !== false;
  const entries = followingSong ? arrangementEntries(model) : [];
  const songScenes = new Set(model.song);
  const slots = model.tracks[track].clips.flatMap((clip, scene) =>
    clip && (!followingSong || songScenes.has(scene)) ? [scene] : []);
  const liveTrack = transport.tracks?.[track];
  const liveClip = transport.playing || transport.paused ? liveTrack?.playing : liveTrack?.active ?? model.tracks[track].active;
  const sceneSlots = model.sceneNames.flatMap((_, scene) => model.tracks.some(t => t.clips[scene]) ? [scene] : []);
  const songIndex = transport.songIndex ?? 0;
  const section = entries.findIndex(e => songIndex >= e.songIndex && songIndex < e.songIndex + e.presses);
  const sceneIndex = sceneSlots.indexOf(transport.scene ?? liveClip);
  const maxBar = barLimit(model, transport);
  const clipDestination = scene => scene === null ? null : { scene };
  const entryDestination = index => entries[index] ? { scene: entries[index].scene, bar: entries[index].startBar } : null;
  return {
    bar: { current: Math.min(maxBar + 1, Math.floor(Math.max(0, transport.master_tick || 0) / 384) + 1), total: maxBar + 1,
      description: followingSong ? 'Current bar / total song bars' : 'Current bar / longest playing clip' },
    clip: { current: slots.indexOf(liveClip) + 1, total: slots.length,
      previous: clipDestination(neighboringSlot(slots, liveClip ?? -1, -1)), next: clipDestination(neighboringSlot(slots, liveClip ?? -1, 1)),
      description: `Playing clip / clips on track ${track + 1}${followingSong ? ' used in this song' : ''}` },
    scene: entries.length ? { current: section + 1, total: entries.length,
      previous: entryDestination(section - 1), next: entryDestination(section + 1),
      description: 'Playing arrangement section / total sections (repeats grouped)' }
      : { current: sceneIndex + 1, total: sceneSlots.length,
        previous: clipDestination(neighboringSlot(sceneSlots, transport.scene ?? liveClip ?? -1, -1)),
        next: clipDestination(neighboringSlot(sceneSlots, transport.scene ?? liveClip ?? -1, 1)),
        description: 'Playing scene / populated scenes' },
  };
}
