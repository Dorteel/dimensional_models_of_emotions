// State of the Create Domain Model form. Pure functions (no DOM, no fetching).
//
// The state mirrors the builder workbook's three steps:
//   {name, description, notes,
//    dimensions: [{name, definition, notes, min, max, circular: "no"|"yes"}],
//    emotions:   [{name, concept_id, definition, notes, coordinates: {"<dimension index>": value}}]}
//
// Coordinates are keyed by dimension position, so editing a dimension's name keeps its values; the functions
// below re-key them when dimensions are removed or reordered. Validation is done by the server
// (POST /api/models/validate), with the builder macros' rules — not here.

export const MAX_DIMENSIONS = 9;
export const MAX_EMOTIONS = 30;

export function emptyModel() {
  return { name: "", description: "", notes: "", dimensions: [], emotions: [] };
}

export function newDimension() {
  return { name: "", definition: "", notes: "", min: "", max: "", circular: "no" };
}

export function newEmotion(entry = null) {
  return entry
    ? { name: entry.name, concept_id: entry.concept_id, definition: "", notes: "", coordinates: {} }
    : { name: "", concept_id: "", definition: "", notes: "", coordinates: {} };
}

export function addDimension(state) {
  return { ...state, dimensions: [...state.dimensions, newDimension()] };
}

export function removeDimension(state, index) {
  const rekey = (coords) => {
    const out = {};
    for (const [k, v] of Object.entries(coords)) {
      const i = Number(k);
      if (i < index) out[i] = v;
      else if (i > index) out[i - 1] = v;
    }
    return out;
  };
  return { ...state, dimensions: state.dimensions.filter((_, i) => i !== index),
           emotions: state.emotions.map((e) => ({ ...e, coordinates: rekey(e.coordinates) })) };
}

export function moveDimension(state, index, delta) {
  const j = index + delta;
  if (j < 0 || j >= state.dimensions.length) return state;
  const dims = [...state.dimensions];
  [dims[index], dims[j]] = [dims[j], dims[index]];
  const swap = (coords) => {
    const out = { ...coords };
    out[index] = coords[j];
    out[j] = coords[index];
    for (const k of [index, j]) if (out[k] === undefined) delete out[k];
    return out;
  };
  return { ...state, dimensions: dims, emotions: state.emotions.map((e) => ({ ...e, coordinates: swap(e.coordinates) })) };
}

export function addEmotion(state, entry = null) {
  return { ...state, emotions: [...state.emotions, newEmotion(entry)] };
}

export function removeEmotion(state, index) {
  return { ...state, emotions: state.emotions.filter((_, i) => i !== index) };
}

// Provenance note for a definition copied verbatim from emotions/emotion_dictionary.ods.
export function definitionNote(def) {
  return `Definition: ${def.source}${def.reference ? `, ${def.reference}` : ""} (via emotions/emotion_dictionary.ods).`;
}

// Generic plot data (CoordinatePlot) for the live preview: first up to three dimensions; only emotions
// with a numeric value on each of them.
export function previewPlotData(state) {
  const axes = state.dimensions.slice(0, 3).map((d, i) => {
    const min = Number(d.min), max = Number(d.max);
    const stated = d.min !== "" && d.max !== "" && Number.isFinite(min) && Number.isFinite(max) && min < max;
    return { id: String(i), label: d.name || `dimension ${i + 1}`, min: stated ? min : null, max: stated ? max : null, stated };
  });
  const points = [];
  state.emotions.forEach((e, j) => {
    const raw = axes.map((_, i) => e.coordinates[i]);
    if (raw.every((v) => v !== undefined && String(v).trim() !== "" && Number.isFinite(Number(v)))) {
      points.push({ id: `emotion:${j}`, label: e.name || `emotion ${j + 1}`, values: raw.map(Number), raw: raw.map(String) });
    }
  });
  return { axes, points };
}
