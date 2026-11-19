// Domain models as stated in the ontology. Pure functions over the ontology JSON produced by
// gui/owl_loader (no DOM, no fetching). Everything is read by following the ontology's own links:
//
//   Domain --hasQualityDimension--> QualityDimension (rdfs:label, hasRange, isCircular, hasMeasurementLevel,
//                                                     hasNotes, hasDefinition --> Definition)
//   Domain --hasDomainPrototype--> PrototypicalInstance <--belongsToDomain-- (either direction is accepted)
//   PrototypicalInstance: rdf:type <EmotionClass>, hasNotes, hasDefinition, hasPoint --> Point
//   Point --hasCoordinate--> Coordinate (numericValue, onQualityDimension --> QualityDimension)
//   Definition: hasValue (text), hasSource --> KnowledgeRepository (rdfs:label)
//
// Terms are matched by local name, so the functions do not depend on the ontology's namespace IRI.
// Nothing is filled in: missing statements are reported as missing.

export const PLACEHOLDER_DEFINITIONS = ["no known definitions", "undefined"];

const local = (iri) => String(iri).replace(/^.*[#/]/, "");
const assertedTypes = (e) => e.types.filter((t) => !t.builtin);
const isA = (e, cls) => assertedTypes(e).some((t) => local(t.id) === cls);
const objects = (e, pred) => e.out.filter((o) => local(o.predicate) === pred).map((o) => o.target);
const subjects = (e, pred) => e.in.filter((o) => local(o.predicate) === pred).map((o) => o.source);
const values = (e, pred) => e.literals.filter((l) => local(l.predicate) === pred);
const unique = (xs) => [...new Set(xs)];

export const isPlaceholder = (text) => PLACEHOLDER_DEFINITIONS.includes(String(text).trim().toLowerCase());

function definitionsOf(model, entity, pred = "hasDefinition") {
  return objects(entity, pred).map((defId) => {
    const def = model.entities[defId];
    const texts = def ? values(def, "hasValue") : [];
    return {
      id: defId,
      texts: texts.map((l) => ({ value: l.value, datatype: l.datatype_name, lang: l.lang,
                                 placeholder: isPlaceholder(l.value) })),
      sources: def ? objects(def, "hasSource").map((s) => ({ id: s, label: model.entities[s]?.label ?? local(s) })) : [],
    };
  });
}

export function parseRange(raw) {
  // hasRange is stored as text such as "min=-1,max=1"; anything else is kept raw and not interpreted.
  const m = /^\s*min\s*=\s*([^,]*),\s*max\s*=\s*(.*)$/.exec(raw);
  if (!m) return { raw, min: null, max: null, parsed: false };
  const num = (s) => (/^\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\s*$/.test(s) ? Number(s) : null);
  return { raw, min: num(m[1]), max: num(m[2]), parsed: true };
}

const NUMERIC = /^\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\s*$/;

function dimensionInfo(model, id) {
  const e = model.entities[id];
  const ranges = values(e, "hasRange").map((l) => parseRange(l.value));
  return {
    id, label: e.label, name: e.name,
    ranges,
    range: ranges.length === 1 ? ranges[0] : null,
    circular: values(e, "isCircular").map((l) => l.value),
    measurementLevel: values(e, "hasMeasurementLevel").map((l) => l.value),
    notes: values(e, "hasNotes").map((l) => l.value),
    definitions: definitionsOf(model, e),
  };
}

function prototypeInfo(model, id, dimIds) {
  const e = model.entities[id];
  const issues = [];
  const emotionClasses = assertedTypes(e).filter((t) => local(t.id) !== "PrototypicalInstance")
    .map((t) => ({ id: t.id, label: model.entities[t.id]?.label ?? t.name,
                   definitions: model.entities[t.id] ? definitionsOf(model, model.entities[t.id], "hasClassDefinition") : [] }));
  const points = objects(e, "hasPoint");
  if (points.length > 1) issues.push(`${points.length} points (hasPoint) are stated for this prototype`);
  const coordinates = [];   // every Coordinate reached from the prototype, verbatim
  for (const pointId of points) {
    const point = model.entities[pointId];
    for (const coordId of point ? objects(point, "hasCoordinate") : []) {
      const c = model.entities[coordId];
      const raw = c ? values(c, "numericValue") : [];
      const dims = c ? objects(c, "onQualityDimension") : [];
      coordinates.push({ id: coordId, pointId, dimensions: dims, raw: raw.map((l) => l.value),
                         datatype: raw[0]?.datatype_name ?? null });
      if (raw.length !== 1) issues.push(`${local(coordId)} has ${raw.length} numericValue statements`);
      if (dims.length !== 1) issues.push(`${local(coordId)} has ${dims.length} onQualityDimension statements`);
      for (const d of dims) {
        if (!dimIds.includes(d)) issues.push(`${local(coordId)} is on ${local(d)}, which is not a dimension of this domain`);
      }
    }
  }
  // One value per domain dimension, only when the ontology states exactly one numeric value for it.
  const byDim = {};
  for (const dimId of dimIds) {
    const found = coordinates.filter((c) => c.dimensions.includes(dimId)).flatMap((c) => c.raw.map((raw) => ({ raw, c })));
    let value = null, raw = null, status = "missing";
    if (found.length === 1 && NUMERIC.test(found[0].raw)) {
      raw = found[0].raw; value = Number(raw); status = "ok";
    } else if (found.length === 1) {
      raw = found[0].raw; status = "not numeric";
      issues.push(`value '${raw}' on ${local(dimId)} is not numeric`);
    } else if (found.length > 1) {
      raw = found.map((f) => f.raw).join(" | "); status = "conflicting";
      issues.push(`${found.length} values on ${local(dimId)}: ${raw}`);
    }
    byDim[dimId] = { value, raw, status, coordinateId: found[0]?.c.id ?? null };
  }
  return {
    id, label: e.label, name: e.name, emotionClasses, points, coordinates, byDim,
    definitions: definitionsOf(model, e),
    notes: values(e, "hasNotes").map((l) => l.value),
    issues,
  };
}

export function extractDomains(model) {
  const domains = Object.values(model.entities).filter((e) => isA(e, "Domain"))
    .sort((a, b) => a.label.localeCompare(b.label));
  return domains.map((e) => {
    const dimIds = unique(objects(e, "hasQualityDimension")).filter((d) => model.entities[d]);
    const protoIds = unique([...objects(e, "hasDomainPrototype"), ...subjects(e, "belongsToDomain")])
      .filter((p) => model.entities[p]);
    const issues = [];
    const viaDomain = new Set(objects(e, "hasDomainPrototype")), viaProto = new Set(subjects(e, "belongsToDomain"));
    for (const p of protoIds) {
      if (!viaDomain.has(p)) issues.push(`${local(p)} states belongsToDomain, but the domain has no hasDomainPrototype to it`);
      if (!viaProto.has(p)) issues.push(`${local(p)} is a hasDomainPrototype of the domain, but has no belongsToDomain back`);
    }
    const prototypes = protoIds.map((p) => prototypeInfo(model, p, dimIds));
    return {
      id: e.id, label: e.label, name: e.name,
      modelTypes: values(e, "hasModelType").map((l) => l.value),
      notes: values(e, "hasNotes").map((l) => l.value),
      description: definitionsOf(model, e),
      dimensions: dimIds.map((d) => dimensionInfo(model, d)),
      prototypes,
      issues,
    };
  });
}

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

export function describeDomain(domain) {
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
