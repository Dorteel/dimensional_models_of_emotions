// Maps the ontology JSON produced by the server (gui/ontology_service, query explorer/statements) into the generic structures used by the
// GraphView, TreeView and Inspector components. Pure functions: no DOM, no fetching.

const KIND_LABEL = { class: "Class", individual: "Individual", property: "Property", datatype: "Datatype",
                     ontology: "Ontology", resource: "Resource" };
const PROPERTY_KIND_LABEL = { object: "Object property", datatype: "Datatype property",
                              annotation: "Annotation property", rdf: "RDF property" };
export const EDGE_KINDS = {
  subclass: { label: "subClassOf", strength: 1.0 },
  type: { label: "rdf:type", strength: 0.6 },
  relation: { label: "Relations (property assertions)", strength: 0.35 },
  domain_range: { label: "Property domain → range", strength: 0.1 },
};

export function displayName(model, id) {
  const e = model.entities[id];
  if (!e) return id === model.hierarchy.id ? model.hierarchy.label : id;
  return e.label !== e.name ? `${e.label} (${e.name})` : e.label;
}

export function isGraphNode(e) {
  return e.kind === "class" || e.kind === "individual" || (e.kind === "resource" && !e.declared);
}

export function toGraphData(model) {
  const nodes = [];
  const ids = new Set();
  for (const e of Object.values(model.entities)) {
    if (!isGraphNode(e)) continue;
    ids.add(e.id);
    nodes.push({
      id: e.id,
      label: e.label,
      kind: e.kind,
      shape: e.kind === "class" ? "rect" : "circle",
      className: `k-${e.kind}${e.declared ? "" : " undeclared"}`,
      title: `${e.label}\n${e.iri || e.id}\n${KIND_LABEL[e.kind] || e.kind}${e.declared ? "" : " (referenced, not declared)"}`,
    });
  }
  const edges = model.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e, i) => ({ id: `e${i}`, source: e.source, target: e.target, kind: e.kind, predicate: e.predicate,
                      label: e.label, className: `e-${e.kind}`, strength: EDGE_KINDS[e.kind]?.strength ?? 0.3 }));
  return { nodes, edges };
}

export function relationPredicates(model) {
  const counts = new Map();
  for (const e of model.edges) if (e.kind === "relation") counts.set(e.label, (counts.get(e.label) || 0) + 1);
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

export function toTreeItems(model) {
  const ent = model.entities;
  const individual = (id) => ({ id, label: ent[id].label, className: "k-individual",
                                title: ent[id].iri || id });
  const classItem = (node) => {
    const e = ent[node.id];
    const children = node.children.map(classItem).concat(node.instances.map(individual));
    return { id: node.id, label: e ? e.label : node.id, className: `k-class${node.cycle ? " cycle" : ""}`,
             badge: node.instances.length ? String(node.instances.length) : "",
             title: `${node.children.length} direct subclasses, ${node.instances.length} direct instances`, children };
  };
  const h = model.hierarchy;
  return [{ id: h.id, label: `${h.label}${h.implicit ? " (implicit root)" : ""}`, className: "k-root",
            children: h.children.map(classItem).concat(h.instances.map(individual)) }];
}

export function toPropertyItems(model) {
  const groups = new Map();
  for (const e of Object.values(model.entities)) {
    if (e.kind !== "property") continue;
    const key = e.property_kind || "rdf";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(e);
  }
  const usage = new Map();
  for (const e of model.edges) if (e.kind === "relation") usage.set(e.predicate, (usage.get(e.predicate) || 0) + 1);
  for (const e of Object.values(model.entities)) {
    for (const l of e.literals) usage.set(l.predicate, (usage.get(l.predicate) || 0) + 1);
  }
  return ["object", "datatype", "annotation", "rdf"].filter((k) => groups.has(k)).map((k) => ({
    id: `group:${k}`, label: `${PROPERTY_KIND_LABEL[k]}s`, badge: String(groups.get(k).length), className: "k-group",
    children: groups.get(k).sort((a, b) => a.label.localeCompare(b.label))
      .map((e) => ({ id: e.id, label: e.label, className: "k-property", badge: String(usage.get(e.id) || 0),
                     title: `${usage.get(e.id) || 0} assertions in this file` })),
  }));
}

function classPaths(model, id, limit = 4) {
  const ent = model.entities;
  const paths = [];
  const walk = (cur, path, seen) => {
    if (paths.length >= limit) return;
    const supers = (ent[cur]?.superclasses || []).filter((s) => !seen.has(s));
    if (!supers.length) {
      // Prepend the (implicit) root unless the file itself states the subclass link to it.
      paths.push(path[0] === model.hierarchy.id ? path : [model.hierarchy.id, ...path]);
      return;
    }
    for (const s of supers) walk(s, [s, ...path], new Set([...seen, s]));
  };
  walk(id, [id], new Set([id]));
  return paths;
}

const lit = (l) => {
  const note = [l.datatype_name && `[${l.datatype_name}]`, l.lang && `@${l.lang}`].filter(Boolean).join(" ");
  return { key: l.predicate_name, value: l.value, note };
};

export function describe(model, id) {
  const ent = model.entities;
  const h = model.hierarchy;
  const ref = (rid) => ({ value: displayName(model, rid), ref: rid });
  if (id === h.id && !ent[id]) {
    return {
      title: h.label, subtitle: h.implicit ? "Implicit root of the class hierarchy (not stated in the file)" : "",
      badges: ["Class"],
      sections: [
        { title: "Top-level classes", rows: h.children.map((c) => ref(c.id)) },
        { title: "Individuals without a class", rows: h.instances.map(ref) },
      ],
    };
  }
  if (id.startsWith("group:")) return null;
  const e = ent[id];
  if (!e) return { title: id, sections: [{ title: "Not found", rows: [], empty: "This term is not in the loaded file." }] };

  const kindBadge = e.kind === "property" ? PROPERTY_KIND_LABEL[e.property_kind] || "Property" : KIND_LABEL[e.kind] || e.kind;
  const badges = [kindBadge, ...e.characteristics];
  if (!e.declared) badges.push("referenced, not declared in this file");
  const crumbs = (path) => path.map((p) => ({ label: displayName(model, p), ref: p }));
  let breadcrumbs = [];
  if (e.kind === "class") breadcrumbs = classPaths(model, id).map(crumbs);
  if (e.kind === "individual") {
    breadcrumbs = e.types.filter((t) => !t.builtin).flatMap((t) => classPaths(model, t.id, 2))
      .map((p) => crumbs([...p, id]));
  }
  const schemaUse = [];
  if (e.kind === "class") {
    for (const p of Object.values(ent)) {
      if (p.kind !== "property") continue;
      if (p.domain.includes(id)) schemaUse.push({ key: "domain of", ...ref(p.id) });
      if (p.range.includes(id)) schemaUse.push({ key: "range of", ...ref(p.id) });
    }
  }
  const usage = e.kind === "property"
    ? model.edges.filter((x) => x.kind === "relation" && x.predicate === id).length +
      Object.values(ent).reduce((n, x) => n + x.literals.filter((l) => l.predicate === id).length, 0)
    : 0;

  return {
    title: e.label,
    subtitle: e.label !== e.name ? e.name : "",
    badges,
    breadcrumbs,
    sections: [
      { title: "Identity", rows: [
        { key: "IRI", value: e.iri || "(blank node)", mono: true },
        { key: "Defined at", value: e.declared ? `${model.meta.file}, line ${e.line}` :
          `not declared; first used at line ${e.line ?? "?"}`, mono: true },
      ] },
      { title: "Annotations", rows: [...e.labels, ...e.comments].map(lit) },
      { title: "Types", rows: e.types.map((t) => (t.builtin ? { value: t.name } : ref(t.id))) },
      { title: "Superclasses", rows: e.superclasses.map(ref) },
      { title: "Subclasses", rows: e.subclasses.map(ref) },
      { title: "Direct instances", rows: e.instances.map(ref) },
      { title: "Property definition", rows: e.kind !== "property" ? [] : [
        ...e.domain.map((d) => ({ key: "domain", ...ref(d) })),
        ...e.range.map((r) => ({ key: "range", ...ref(r) })),
        { key: "used", value: `${usage} assertion${usage === 1 ? "" : "s"} in this file` },
      ] },
      { title: "Used in property schema", rows: schemaUse },
      { title: "Data values", rows: e.literals.map(lit) },
      { title: "Outgoing relations", rows: e.out.map((r) => ({ key: r.predicate_name, ...ref(r.target) })) },
      { title: "Incoming relations", rows: e.in.map((r) => ({ key: r.predicate_name, ...ref(r.source) })) },
    ],
  };
}

export function searchIndex(model) {
  return Object.values(model.entities)
    .filter((e) => ["class", "individual", "property"].includes(e.kind))
    .map((e) => ({ id: e.id, text: `${e.label}${e.label !== e.name ? ` — ${e.name}` : ""} (${KIND_LABEL[e.kind]})` }))
    .sort((a, b) => a.text.localeCompare(b.text));
}
