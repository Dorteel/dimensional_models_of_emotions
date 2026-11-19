// Presentation of a domain comparison for the Compare Domain Models tab. Pure functions (no DOM, no fetching).
//
// The comparison is computed by the server (GET /api/compare → gui/ontology_service/compare.py) from the
// SPARQL results; this module only reads it: which prototypes are linked across the two plots, and the
// text that accompanies an exported figure.
//
//   comparison {sameDomain, a, b (domain summaries), dimensions {pairs, equivalence, numeric, distance, ...},
//               emotions {shared, onlyA, onlyB, unclassifiedA, unclassifiedB}, rows, links, warnings, provenance}

export const SIDES = ["a", "b"];
export const other = (side) => (side === "a" ? "b" : "a");

// Prototypes in the other domain that share an emotion class (class IRI) with prototype `id` of `side`.
export function counterparts(comparison, side, id) {
  return (comparison.links[`${side}:${id}`] || []).map((key) => key.slice(2));
}

// Why a selected prototype has no counterpart, for the status line.
export function selectionNote(comparison, side, id) {
  const summary = comparison[side];
  const row = comparison.rows.find((r) => r[side]?.id === id);
  const label = row?.[side]?.label ?? id;
  const ids = counterparts(comparison, side, id);
  const there = comparison[other(side)].label;
  if (ids.length) {
    const names = comparison.rows.filter((r) => r.status === "shared" && r[side].id === id).map((r) => r[other(side)].label);
    return `${label} (${summary.label}) ↔ ${[...new Set(names)].join(", ")} (${there}): same emotion class`;
  }
  if (row && !row.class) return `${label} (${summary.label}) has no emotion class, so it cannot be matched.`;
  return `${label} (${summary.label}): its emotion class does not occur in ${there}.`;
}

// Status of each comparison row, keyed by "<side>:<prototype id>", for highlighting table rows.
export function rowKeys(row) {
  return SIDES.filter((s) => row[s]).map((s) => `${s}:${row[s].id}`);
}

const rangeText = (d) => (d.rangeStated ? `[${d.min}, ${d.max}]` : `(${d.rangeState})`);

// Lines placed above and below an exported figure: model identifier, plotted axes and missing information.
// `plot` is the plotted data {axes, points, omitted} for this side.
export function figureText(comparison, side, plot) {
  const s = comparison[side];
  const shown = new Set(plot.axes.map((a) => a.id));
  const title = [
    `${side.toUpperCase()}: ${s.label} — ${s.id}`,
    plot.axes.length
      ? `Axes: ${plot.axes.map((a, i) => { const d = s.dimensions.find((x) => x.id === a.id);
          return `${"XYZ"[i]} = ${d.label} ${rangeText(d)}`; }).join(" · ")}`
      : "No axes (no quality dimensions).",
    `Source: ${comparison.provenance.file} · sha256 ${comparison.provenance.sha256.slice(0, 16)}…`,
  ];
  const footer = [];
  const hidden = s.dimensions.filter((d) => !shown.has(d.id));
  if (hidden.length) footer.push(`Projection: ${hidden.map((d) => d.label).join(", ")} not shown.`);
  for (const a of plot.axes) {
    const d = s.dimensions.find((x) => x.id === a.id);
    if (!d.rangeStated) footer.push(`${d.label}: ${d.rangeState}; axis spans the data extent.`);
  }
  if (!s.prototypes) footer.push(`${s.label} has no prototypical instances in the ontology.`);
  if (plot.omitted?.length) {
    footer.push(`Not plotted (${plot.omitted.length}): ${plot.omitted.map((o) => `${o.label} (${o.reason})`).join(", ")}.`);
  }
  const scope = side.toUpperCase();
  for (const w of comparison.warnings) {
    if (w.scope === scope || (comparison.sameDomain && w.scope === "A")) footer.push(`Warning: ${w.text}`);
  }
  return { title, footer };
}

export function exportName(comparison, suffix) {
  const safe = (name) => String(name).replace(/[^A-Za-z0-9_-]+/g, "_");   // names may be prefixed (ecs:x)
  return `compare_${safe(comparison.a.name)}_vs_${safe(comparison.b.name)}_${safe(suffix)}`;
}
