// Presentation of domain models for the Domain Models tab. Pure functions (no DOM, no fetching).
//
// The data comes from GET /api/domains, which the server assembles from the SPARQL queries in
// gui/sparql/domains/*.rq (see gui/sparql/README.md). This module does not read ontology triples: it only
// turns that JSON into plot data, tree items and inspector descriptions.
//
//   domain     {id, label, name, modelTypes[], notes[], description[definition], dimensions[], prototypes[], issues[]}
//   dimension  {id, label, name, ranges[{raw, min, max, parsed}], range, circular[], measurementLevel[], notes[], definitions[]}
//   prototype  {id, label, name, emotionClasses[{id, label, definitions[]}], points[], coordinates[],
//               byDim{dimensionId: {value, raw, status: ok|missing|not numeric|conflicting, coordinateId}},
//               definitions[], notes[], issues[]}
//   definition {id, texts[{value, datatype, lang, placeholder}], sources[{id, label}]}

const local = (iri) => String(iri).replace(/^.*[#/]/, "");

// ------------------------------------------------------------------ plot data (generic shape)

export function axisBounds(dim) {
  const r = dim.range;
  return r && r.min !== null && r.max !== null && r.min < r.max ? { min: r.min, max: r.max, stated: true }
                                                                 : { min: null, max: null, stated: false };
}

export function toPlotData(domain, axisIds) {
  const dims = axisIds.map((id) => domain.dimensions.find((d) => d.id === id));
  const axes = dims.map((d) => ({ id: d.id, label: d.label, ...axisBounds(d) }));
  const points = [], omitted = [];
  for (const p of domain.prototypes) {
    const vals = dims.map((d) => p.byDim[d.id]);
    if (vals.every((v) => v.status === "ok")) {
      points.push({ id: p.id, label: p.label, values: vals.map((v) => v.value), raw: vals.map((v) => v.raw) });
    } else {
      const bad = dims.map((d, i) => (vals[i].status === "ok" ? null : `${d.label}: ${vals[i].status}`)).filter(Boolean);
      omitted.push({ id: p.id, label: p.label, reason: bad.join(", ") });
    }
  }
  return { axes, points, omitted };
}

// ------------------------------------------------------------------ inspector descriptions

const MISSING = "not stated in the ontology";
const ONTO = (id) => `ontology:${id}`;

function definitionRows(defs, emptyText) {
  const rows = [];
  for (const d of defs) {
    for (const t of d.texts) {
      rows.push({ value: t.value, note: [t.placeholder ? "(placeholder — no definition documented)" : "",
        d.sources.length ? `source: ${d.sources.map((s) => s.label).join(", ")}` : "source: not stated"]
        .filter(Boolean).join(" · ") });
    }
    if (!d.texts.length) rows.push({ value: `${local(d.id)} has no hasValue`, note: "missing" });
  }
  return { rows, empty: emptyText };
}

function citedSources(domain) {
  const defs = [...domain.description, ...domain.dimensions.flatMap((d) => d.definitions),
                ...domain.prototypes.flatMap((p) => [...p.definitions, ...p.emotionClasses.flatMap((c) => c.definitions)])];
  const ids = new Set(defs.flatMap((d) => d.sources.map((s) => s.id)));
  return [...ids];
}

export function describeDomain(domain, sources = []) {
  const byId = new Map(sources.map((s) => [s.id, s]));
  const plotted = domain.prototypes.filter((p) => Object.values(p.byDim).every((v) => v.status === "ok")).length;
  return {
    title: domain.label, subtitle: domain.name, badges: ["Domain", ...domain.modelTypes],
    sections: [
      { title: "Description", ...definitionRows(domain.description, `Description ${MISSING} (no hasDefinition on this domain).`) },
      { title: "Notes", rows: domain.notes.map((n) => ({ value: n })), empty: `No notes (no hasNotes).` },
      { title: "Quality dimensions", rows: domain.dimensions.map((d) => ({
        key: d.label, value: d.label, ref: d.id,
        note: d.range ? (d.range.min !== null && d.range.max !== null ? `[${d.range.min}, ${d.range.max}]` : `range '${d.range.raw}'`)
                      : "range not stated" })), empty: `No quality dimensions (no hasQualityDimension).` },
      { title: "Prototypes", rows: domain.prototypes.map((p) => ({ value: p.label, ref: p.id,
        note: Object.values(p.byDim).every((v) => v.status === "ok") ? "" : "no complete coordinates" })),
        empty: "No prototypical instances are linked to this domain." },
      { title: "Coverage", rows: [{ key: "plotted", value: `${plotted} of ${domain.prototypes.length} prototypes have a value on every dimension` }] },
      { title: "Sources cited", rows: citedSources(domain).map((id) => ({ value: byId.get(id)?.label ?? local(id), ref: ONTO(id),
        note: byId.has(id) ? `cited by ${byId.get(id).definitions} definition(s) in the ontology` : "" })),
        empty: "No definition of this domain, its dimensions or prototypes cites a source." },
      { title: "Issues in the ontology", rows: domain.issues.map((i) => ({ value: i })) },
      { title: "Ontology", rows: [{ value: "Open this domain in the ontology inspector", ref: ONTO(domain.id) }] },
    ],
  };
}

export function describeDimension(domain, dim) {
  const vals = domain.prototypes.map((p) => p.byDim[dim.id]).filter((v) => v?.status === "ok").map((v) => v.value);
  return {
    title: dim.label, subtitle: dim.name, badges: ["Quality dimension", `domain: ${domain.label}`],
    sections: [
      { title: "Definition", ...definitionRows(dim.definitions, `Definition ${MISSING} (no hasDefinition).`) },
      { title: "Range", rows: dim.ranges.map((r) => ({ value: r.raw, note: r.parsed ? `min ${r.min ?? "?"}, max ${r.max ?? "?"}` : "not in min=…,max=… form" })),
        empty: `Range ${MISSING} (no hasRange); plot axes use the data extent.` },
      { title: "Circular", rows: dim.circular.map((v) => ({ value: v })), empty: `Circularity ${MISSING} (no isCircular).` },
      { title: "Measurement level", rows: dim.measurementLevel.map((v) => ({ value: v })), empty: `Measurement level ${MISSING}.` },
      { title: "Notes", rows: dim.notes.map((n) => ({ value: n })), empty: "No notes (no hasNotes)." },
      { title: "Values in this domain", rows: [{ key: "prototypes", value: `${vals.length} with a value` },
        ...(vals.length ? [{ key: "observed", value: `${Math.min(...vals)} … ${Math.max(...vals)}` }] : [])] },
      { title: "Ontology", rows: [{ value: "Open in the ontology inspector", ref: ONTO(dim.id) }] },
    ],
  };
}

export function describePrototype(domain, proto) {
  return {
    title: proto.label, subtitle: proto.name, badges: ["Prototypical instance", `domain: ${domain.label}`],
    sections: [
      { title: "Emotion class", rows: proto.emotionClasses.map((c) => ({ value: c.label, ref: ONTO(c.id), note: "open in ontology inspector" })),
        empty: `Emotion class ${MISSING} (only typed as PrototypicalInstance).` },
      { title: "Dimensional values", rows: domain.dimensions.map((d) => {
        const v = proto.byDim[d.id];
        return { key: d.label, value: v.status === "ok" ? v.raw : v.status === "missing" ? "missing — no coordinate on this dimension" : `${v.status}: ${v.raw}`,
                 mono: v.status === "ok", ...(v.coordinateId ? { note: `(${local(v.coordinateId)})` } : {}) };
      }), empty: "This domain has no quality dimensions." },
      { title: "Prototype definition", ...definitionRows(proto.definitions, `Definition ${MISSING} (no hasDefinition).`) },
      ...proto.emotionClasses.map((c) => ({ title: `Definitions of class ${c.label}`,
        ...definitionRows(c.definitions, `No definitions stated for ${c.label} (no hasClassDefinition).`) })),
      { title: "Notes", rows: proto.notes.map((n) => ({ value: n })), empty: "No notes (no hasNotes)." },
      { title: "Issues in the ontology", rows: proto.issues.map((i) => ({ value: i })) },
      { title: "Ontology", rows: [
        { value: "Open this prototype in the ontology inspector", ref: ONTO(proto.id) },
        ...proto.points.map((p) => ({ value: `Open point ${local(p)}`, ref: ONTO(p) })),
      ] },
    ],
  };
}

export function toDomainTree(domains) {
  return domains.map((d) => ({
    id: d.id, label: d.label, className: "k-domain", badge: String(d.prototypes.length),
    title: `${d.dimensions.length} dimensions, ${d.prototypes.length} prototypes`,
    children: [
      { id: `group:dims:${d.id}`, label: `Dimensions (${d.dimensions.length})`, className: "k-group",
        children: d.dimensions.map((x) => ({ id: x.id, label: x.label, className: "k-dimension",
                                             badge: x.range ? "" : "range ?" })) },
      { id: `group:protos:${d.id}`, label: `Prototypes (${d.prototypes.length})`, className: "k-group",
        children: d.prototypes.map((p) => ({ id: p.id, label: p.label, className: "k-individual",
          badge: Object.values(p.byDim).every((v) => v.status === "ok") ? "" : "no coords" })) },
    ],
  }));
}
