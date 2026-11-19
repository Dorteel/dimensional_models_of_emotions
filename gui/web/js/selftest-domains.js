// Domain Models tab self-test (part of ?selftest=1). Drives the tab with DOM events and checks the
// display against the populated ontology as returned by the API. Returns the adapter's extraction so
// gui/tests/test_browser.py can compare it with an independent reading of the OWL file.

import { CoordinatePlot } from "./components/coordinate-plot.js";
import { toPlotData } from "./ontology/domains.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const local = (iri) => String(iri).replace(/^.*[#/]/, "");

function pointer(target, type, x, y) {
  target.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y,
                                                 pointerId: 1, button: 0, buttons: type === "pointerup" ? 0 : 1 }));
}

// Expected structure, read from the API JSON with plain link walking (independent of domains.js).
function expectedDomains(api) {
  const E = api.entities;
  const typed = (e, cls) => e.types.some((t) => !t.builtin && local(t.id) === cls);
  const out = (e, p) => e.out.filter((o) => local(o.predicate) === p).map((o) => o.target);
  return Object.values(E).filter((e) => typed(e, "Domain")).map((d) => {
    const dims = [...new Set(out(d, "hasQualityDimension"))];
    const protos = [...new Set([...out(d, "hasDomainPrototype"),
      ...d.in.filter((i) => local(i.predicate) === "belongsToDomain").map((i) => i.source)])];
    const coords = {};
    for (const p of protos) {
      coords[p] = {};
      for (const pt of out(E[p], "hasPoint")) {
        for (const c of out(E[pt], "hasCoordinate")) {
          const dim = out(E[c], "onQualityDimension")[0];
          const raw = E[c].literals.filter((l) => local(l.predicate) === "numericValue").map((l) => l.value);
          coords[p][dim] = raw.length === 1 ? raw[0] : raw;
        }
      }
    }
    return { id: d.id, label: d.label, dims, protos, coords };
  });
}

// Fit pixel = a + b * value through two points with different values; return max deviation of all points.
function linearDeviation(pairs) {
  const sorted = [...pairs].sort((p, q) => p.v - q.v);
  const lo = sorted[0], hi = sorted[sorted.length - 1];
  if (!lo || hi.v === lo.v) return { dev: 0, slope: 0 };
  const b = (hi.px - lo.px) / (hi.v - lo.v), a = lo.px - b * lo.v;
  return { dev: Math.max(...pairs.map((p) => Math.abs(a + b * p.v - p.px))), slope: b };
}

function plottedPoints(svg) {
  return [...svg.querySelectorAll(".pt")].map((g) => {
    const c = g.querySelector("circle");
    return { id: g.dataset.id, raw: JSON.parse(g.dataset.values), x: +c.getAttribute("cx"), y: +c.getAttribute("cy"), g, c };
  });
}

export async function runDomainChecks(dashboard, check) {
  // ---------------------------------------------------------------- open the tab
  document.querySelector("#tab-domains").click();
  const tab = dashboard.tabs.domains;
  await tab.ready;
  await sleep(50);
  const list = await (await fetch("/api/ontologies")).json();
  check("Domain Models tab reads only the populated ontology (via /api/domains)", tab.meta.file === list.domain_source &&
        list.domain_source === "emotional_ontology_populated.owl",
        `${list.directory_relative}/${list.domain_source}${list.fallback ? " (fallback location)" : ""}`);
  const api = await (await fetch(`/api/ontology?file=${list.domain_source}`)).json();
  const expected = expectedDomains(api);
  const sel = tab.ui.domain;
  check("Every Domain individual is listed for selection",
        sel.options.length === expected.length && expected.every((d) => [...sel.options].some((o) => o.value === d.id)),
        expected.map((d) => d.label).join(", "));
  check("Domain tree lists every domain", expected.every((d) => tab.tree.items.has(d.id)));

  const choose = async (id) => {
    sel.value = id;
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(30);
  };
  const svg = tab.plot.svg;
  const title = () => tab.inspector.container.querySelector(".inspector-title")?.textContent;
  const section = (t) => tab.inspector.container.querySelector(`.inspector-section[data-section="${t}"]`);

  // ---------------------------------------------------------------- every domain: mode and coordinate fidelity
  for (const d of expected) {
    await choose(d.id);
    const complete = d.protos.filter((p) => d.dims.every((dim) => typeof d.coords[p][dim] === "string"));
    const mode = !d.dims.length || !complete.length ? "empty" : d.dims.length === 1 ? "1d" : d.dims.length === 2 ? "2d" : "3d";
    check(`${d.label}: summary shows name and every quality dimension`,
          tab.ui.summary.querySelector("h2")?.textContent === d.label &&
          tab.ui.summary.querySelectorAll(".chip").length === d.dims.length, `${d.dims.length} dimensions`);
    check(`${d.label}: inspector shows name, description, notes and dimensions`,
          title() === d.label && section("Description") && section("Notes") && section("Quality dimensions"));
    check(`${d.label}: plot mode is ${mode} (${d.dims.length} dimensions, ${complete.length} prototypes with coordinates)`,
          svg.dataset.mode === mode && (d.dims.length <= 3) === tab.ui.axes.hidden, svg.dataset.mode);
    if (mode === "empty") {
      check(`${d.label}: informative empty state`, svg.querySelector(".plot-empty")?.textContent.length > 10,
            [...svg.querySelectorAll(".plot-empty")].map((t) => t.textContent).join(" "));
      continue;
    }
    // Axis order is the domain JSON's dimension order (file order; checked in test_sparql.py). Here: the axes
    // must be exactly the domain's dimensions, and each point must carry the value stated for each axis.
    const tabDims = tab.domain.dimensions.map((x) => x.id);
    check(`${d.label}: plotted axes are the domain's quality dimensions`,
          tabDims.length === d.dims.length && d.dims.every((x) => tabDims.includes(x)), tabDims.map(local).join(", "));
    const pts = plottedPoints(svg);
    const axes = tabDims.slice(0, 3);
    const wrong = pts.filter((p) => JSON.stringify(p.raw) !== JSON.stringify(axes.map((dim) => d.coords[p.id][dim])));
    check(`${d.label}: every prototype with coordinates is plotted with its ontology values verbatim`,
          pts.length === complete.length && !wrong.length && complete.every((id) => pts.some((p) => p.id === id)),
          `${pts.length} points; mismatches: ${wrong.map((p) => local(p.id)).join(", ")}`);
    if (mode === "3d") tab.plot.setView({ yaw: 0, pitch: 0, zoom: 1 });   // front view: x <- axis 0, y <- axis 2
    const fresh = plottedPoints(svg);
    const xs = linearDeviation(fresh.map((p) => ({ v: Number(p.raw[0]), px: p.x })));
    const yAxis = mode === "3d" ? 2 : 1;
    const ys = mode === "1d" ? { dev: 0, slope: -1 } : linearDeviation(fresh.map((p) => ({ v: Number(p.raw[yAxis]), px: p.y })));
    check(`${d.label}: point positions are a linear function of the coordinates (x increases, y up)`,
          xs.dev < 0.01 && ys.dev < 0.01 && xs.slope > 0 && ys.slope < 0,
          `max deviation x ${xs.dev.toFixed(4)} px, y ${ys.dev.toFixed(4)} px`);
    if (mode === "3d") tab.plot.resetView();
  }

  // ---------------------------------------------------------------- selection + inspection (domain with most plotted points)
  const best = [...expected].sort((a, b) => b.protos.length - a.protos.length)[0];
  await choose(best.id);
  const target = plottedPoints(svg).find((p) => p.id === best.protos.find((id) => api.entities[id]));
  const r = target.c.getBoundingClientRect();
  pointer(target.c, "pointerdown", r.x + r.width / 2, r.y + r.height / 2);
  pointer(target.c, "pointerup", r.x + r.width / 2, r.y + r.height / 2);
  await sleep(20);
  const protoEnt = api.entities[target.id];
  check("Clicking a plotted prototype selects it and opens it in the inspector",
        title() === protoEnt.label && svg.querySelector(".pt.selected")?.dataset.id === target.id &&
        tab.tree.root.querySelector(".tree-row.selected")?.dataset.id === target.id, protoEnt.label);
  const valueCells = [...section("Dimensional values").querySelectorAll("dd")].map((dd) => dd.firstChild.textContent);
  const bestDims = tab.domain.dimensions.map((x) => x.id);
  check("Inspector shows the prototype's dimensional values verbatim",
        JSON.stringify(valueCells) === JSON.stringify(bestDims.map((dim) => best.coords[target.id][dim])), valueCells.join(", "));
  const classes = protoEnt.types.filter((t) => !t.builtin && local(t.id) !== "PrototypicalInstance");
  const classLink = section("Emotion class")?.querySelector("a");
  check("Inspector shows the prototype's emotion class", classes.length && classLink?.textContent === api.entities[classes[0].id].label,
        classLink?.textContent);
  check("Inspector shows definitions and notes of the prototype",
        section("Prototype definition") && section("Notes") && [...tab.inspector.container.querySelectorAll(".inspector-section")]
          .some((s) => s.dataset.section.startsWith("Definitions of class")));

  // missing information is explicit
  const noRange = expected.flatMap((d) => d.dims).find((dim) => !api.entities[dim].literals.some((l) => local(l.predicate) === "hasRange"));
  if (noRange) {
    tab.select(noRange, "test");
    check("Missing range/circularity are stated explicitly for a dimension",
          /not stated/.test(section("Range")?.textContent) && /not stated/.test(section("Circular")?.textContent),
          api.entities[noRange].label);
  }
  const placeholder = expected.flatMap((d) => d.protos).find((p) => api.entities[p].out.some((o) =>
    local(o.predicate) === "hasDefinition" && api.entities[o.target]?.literals.some((l) => /^(no known definitions|undefined)$/i.test(l.value))));
  if (placeholder) {
    tab.select(placeholder, "test");
    check("A placeholder definition is shown verbatim and marked as missing",
          /placeholder/.test(section("Prototype definition")?.textContent), api.entities[placeholder].label);
  }

  // tree navigation
  await choose(best.id);
  const dimRow = tab.tree.root.querySelector(`.tree-row[data-id="${CSS.escape(`group:dims:${best.id}`)}"]`);
  dimRow.querySelector(".tree-toggle").click();
  const firstDim = dimRow.closest("li").querySelector(`.tree-row[data-id="${CSS.escape(bestDims[0])}"]`);
  firstDim.click();
  check("Selecting a dimension in the tree shows it in the inspector", title() === api.entities[bestDims[0]].label);

  // link to the ontology inspector
  tab.select(target.id, "test");
  section("Emotion class").querySelector("a").click();
  await dashboard.tabs.ontology.ready;
  await sleep(300);
  const onto = dashboard.tabs.ontology;
  check("Emotion-class link opens the class in the Emotional Ontology inspector",
        !document.querySelector("#panel-ontology").hidden && onto.graph.selected === classes[0].id &&
        onto.inspector.container.querySelector(".inspector-title")?.textContent === api.entities[classes[0].id].label);
  document.querySelector("#tab-domains").click();
  await sleep(30);

  // ---------------------------------------------------------------- 3D interaction
  const three = expected.find((d) => d.dims.length === 3 && d.protos.length);
  if (three) {
    await choose(three.id);
    const v0 = { ...tab.plot.view };
    const box = svg.getBoundingClientRect();
    pointer(svg, "pointerdown", box.x + 20, box.y + 20);
    pointer(svg, "pointermove", box.x + 80, box.y + 50);
    pointer(svg, "pointerup", box.x + 80, box.y + 50);
    const v1 = { ...tab.plot.view };
    check("3D view rotates when dragged", v1.yaw !== v0.yaw && v1.pitch !== v0.pitch,
          `yaw ${v0.yaw.toFixed(2)}→${v1.yaw.toFixed(2)}, pitch ${v0.pitch.toFixed(2)}→${v1.pitch.toFixed(2)}`);
    svg.dispatchEvent(new WheelEvent("wheel", { deltaY: -300, bubbles: true, cancelable: true }));
    check("3D view zooms with the wheel", tab.plot.view.zoom > v1.zoom, tab.plot.view.zoom.toFixed(2));
    tab.el.querySelector('[data-role="reset-view"]').click();
    check("Reset view restores the default 3D view", tab.plot.view.yaw === v0.yaw && tab.plot.view.zoom === v0.zoom);
  }

  // ---------------------------------------------------------------- 1D number line (component check; no 1D domain has coordinates)
  const two = expected.find((d) => d.dims.length >= 2 && d.protos.length);
  const host = document.createElement("div");
  host.style.cssText = "position:fixed;left:0;top:0;width:800px;height:300px;visibility:hidden";
  document.body.append(host);
  const line = new CoordinatePlot(host);
  const realPts = two.protos.filter((p) => typeof two.coords[p][two.dims[0]] === "string")
    .map((p) => ({ id: p, label: api.entities[p].label, values: [Number(two.coords[p][two.dims[0]])], raw: [two.coords[p][two.dims[0]]] }));
  line.setData({ axes: [{ id: two.dims[0], label: api.entities[two.dims[0]].label }], points: realPts });
  const lp = plottedPoints(line.svg);
  const lx = linearDeviation(lp.map((p) => ({ v: Number(p.raw[0]), px: p.x })));
  check("1D number line places points linearly on one line (component, real values of one dimension)",
        line.svg.dataset.mode === "1d" && lp.length === realPts.length && lx.dev < 0.01 && lx.slope > 0 &&
        new Set(lp.map((p) => p.y)).size === 1, `${lp.length} points`);
  host.remove();

  // ---------------------------------------------------------------- > 3 dimensions: axis pickers (synthetic 4-D domain, test only)
  const base = tab.domains.find((d) => d.id === two.id);
  const synthDims = [0, 1, 2, 3].map((i) => ({ ...base.dimensions[i % base.dimensions.length], id: `test:dim${i}`, label: `test-dim-${i}` }));
  const synth = { ...base, id: "test:synthetic-4d", label: "TEST synthetic 4-D (not in ontology)", dimensions: synthDims,
    prototypes: base.prototypes.map((p) => ({ ...p, byDim: Object.fromEntries(synthDims.map((sd, i) =>
      [sd.id, p.byDim[base.dimensions[i % base.dimensions.length].id]])) })) };
  tab.domains.push(synth);
  tab.showDomain(synth.id);
  check(">3 dimensions: axis pickers appear and a 3-D projection is drawn", !tab.ui.axes.hidden && svg.dataset.mode === "3d");
  const [xSel, ySel, zSel] = tab.ui.axisSelects;
  zSel.value = ""; zSel.dispatchEvent(new Event("change"));
  xSel.value = "test:dim3"; xSel.dispatchEvent(new Event("change"));
  const proj = plottedPoints(svg);
  const expect = toPlotData(synth, ["test:dim3", ySel.value]).points;
  check(">3 dimensions: choosing X and no Z projects onto the selected dimensions",
        svg.dataset.mode === "2d" && proj.length === expect.length &&
        proj.every((p) => JSON.stringify(p.raw) === JSON.stringify(expect.find((e) => e.id === p.id).raw)));
  await tab.load(best.id);   // restore the real ontology content
  check("Tab returns to the ontology's domains after the synthetic check",
        !tab.domains.some((d) => d.id.startsWith("test:")) && tab.ui.domain.options.length === expected.length);

  return {
    source: `${list.directory_relative}/${list.domain_source}`,
    domains: tab.domains.map((d) => ({
      id: d.id, label: d.label, dimensions: d.dimensions.map((x) => x.id),
      prototypes: Object.fromEntries(d.prototypes.map((p) => [p.id, Object.fromEntries(
        Object.entries(p.byDim).map(([dim, v]) => [dim, v.raw]))])),
    })),
  };
}
