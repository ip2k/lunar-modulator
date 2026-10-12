// Initial workspace choice follows canonical content once per project. MIT.
import { parseSet } from './sequence-model.js';

export function hasSequenceContent(doc) {
  if (!doc?.set) return false;
  try {
    const set = parseSet(doc.set);
    return set.song.length > 0 || set.tracks.some(track => track.clips.some(clip => clip !== null));
  } catch { return false; } // A malformed/unsupported set must not break the editor shell.
}

export function makeInitialView(projectId) {
  let id = projectId, settled = false, chosen = false;
  return {
    project(next) {
      if (next === id) return false;
      id = next; settled = chosen = false;
      return true;
    },
    choose() { chosen = true; },
    fromProject(current, doc) {
      if (current !== id || settled) return null;
      settled = true;
      return chosen ? null : hasSequenceContent(doc) ? 'sequencer' : 'flow';
    },
    get pending() { return !settled; },
  };
}
