// Compare Domain Models tab self-test (?selftest=1&compare=1, gui/tests/test_browser.py). Drives the tab with
// DOM events. Expected values come from the Emotional Ontology tab's statement API (/api/ontology, plain link
// walking in expectedDomains), not from /api/compare. Returns the exported files so the Python test can check
// them against an independent reading of the OWL file.

import { expectedDomains, plottedPoints } from "./selftest-domains.js";

const local = (iri) => String(iri).replace(/^.*[#/]/, "");

function pointer(target, type, x, y) {
  target.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y,
                                                 pointerId: 1, button: 0, buttons: type === "pointerup" ? 0 : 1 }));
}

function clickPoint(svg, id) {
  const pt = plottedPoints(svg).find((p) => p.id === id);
  const r = pt.c.getBoundingClientRect();
  pointer(pt.c, "pointerdown", r.x + r.width / 2, r.y + r.height / 2);
  pointer(pt.c, "pointerup", r.x + r.width / 2, r.y + r.height / 2);
}

const ids = (svg, cls) => [...svg.querySelectorAll(`.pt.${cls}`)].map((g) => g.dataset.id).sort();
const blobText = (b) => (typeof b === "string" ? Promise.resolve(b) : b.text());

export async function runCompareChecks(dashboard, check) {
  document.querySelector("#tab-compare").click();
  const tab = dashboard.tabs.compare;
  await tab.ready;
  const list = await (await fetch("/api/ontologies")).json();
  const api = await (await fetch(`/api/ontology?file=${encodeURIComponent(list.domain_source)}`)).json();
  const E = api.entities;
  const expected = Object.fromEntries(expectedDomains(api).map((d) => [local(d.id), d]));
  const classesOf = (p) => E[p].types.filter((t) => !t.builtin && local(t.id) !== "PrototypicalInstance").map((t) => t.id);
  const domainClasses = (d) => new Set(d.protos.flatMap(classesOf));
  const svgA = tab.plots.a.svg, svgB = tab.plots.b.svg;
  const circ = expected.domain_circumplex, pad = expected.domain_pad;

  // ---------------------------------------------------------------- selection and default view
  check("Compare: the dashboard has a fourth tab 'Compare Domain Models'",
        document.querySelector("#tab-compare")?.textContent === "Compare Domain Models");
  const options = [...tab.ui.a.options].map((o) => o.value).sort();
  check("Compare: any domain of the populated ontology can be chosen as A or B",
        JSON.stringify(options) === JSON.stringify(Object.values(expected).map((d) => d.id).sort()) &&
        JSON.stringify([...tab.ui.b.options].map((o) => o.value).sort()) === JSON.stringify(options), options.map(local).join());
  await tab.compare(circ.id, pad.id);
  const plotted = (svg, d) => {
    const pts = plottedPoints(svg);
    return pts.length === d.protos.length && pts.every((p) => JSON.stringify(p.raw) ===
      JSON.stringify(tab.pickers[svg === svgA ? "a" : "b"].value.map((dim) => d.coords[p.id][dim])));
  };
  check("Compare: both domains are plotted side by side with their own coordinates (2D circumplex, 3D PAD)",
        svgA.dataset.mode === "2d" && svgB.dataset.mode === "3d" && plotted(svgA, circ) && plotted(svgB, pad),
        `${svgA.dataset.mode}/${svgB.dataset.mode}`);
  const titles = (svg) => [...svg.querySelectorAll(".axis-title")].map((t) => t.textContent);
  check("Compare: each plot keeps its own axis labels and ranges (PAD's are marked as not stated)",
        titles(svgA).join() === "valence,arousal" &&
        titles(svgB).every((t) => t.endsWith("(range not stated)")) && titles(svgB).length === 3, titles(svgB).join(" | "));
  const chips = (s) => [...tab.sides[s].chips.children].map((c) => c.title);
  check("Compare: the dimension chips show each dimension's IRI, range and definition",
        chips("a").length === 2 && chips("a").every((t) => /range: min=-1,max=1/.test(t) && /definition: /.test(t)) &&
        chips("b").every((t) => /range: range not stated/.test(t)) && chips("b").length === 3);

  // ---------------------------------------------------------------- linked selection by emotion class
  const shared = [...domainClasses(circ)].filter((c) => domainClasses(pad).has(c));
  const protoOf = (d, cls) => d.protos.filter((p) => classesOf(p).includes(cls)).sort();
  const cls = shared[0];
  clickPoint(svgA, protoOf(circ, cls)[0]);
  check("Compare: selecting an emotion in A highlights the prototype of the same emotion class in B",
        ids(svgA, "selected").join() === protoOf(circ, cls)[0] && ids(svgB, "linked").join() === protoOf(pad, cls).join() &&
        tab.ui.selection.textContent.includes("same emotion class"), `${local(cls)}: ${tab.ui.selection.textContent}`);
  check("Compare: the matching row of the comparison table is highlighted",
        tab.ui.summary.querySelectorAll("tr.selected").length === protoOf(pad, cls).length);
  clickPoint(svgB, protoOf(pad, shared[1] ?? cls)[0]);
  check("Compare: selecting in B highlights the counterpart in A (and clears the selection in A)",
        ids(svgB, "selected").join() === protoOf(pad, shared[1] ?? cls)[0] &&
        ids(svgA, "linked").join() === protoOf(circ, shared[1] ?? cls).join() && !ids(svgA, "selected").length);
  const onlyA = circ.protos.find((p) => !classesOf(p).some((c) => domainClasses(pad).has(c)));
  clickPoint(svgA, onlyA);
  check("Compare: an emotion whose class is not in the other domain highlights nothing there",
        ids(svgA, "selected").join() === onlyA && !ids(svgB, "linked").length && /does not occur in/.test(tab.ui.selection.textContent),
        tab.ui.selection.textContent);
  // Same label is not enough: a PAD prototype's label matching a circumplex prototype's label with another class
  // would be a lexical match; links only follow class IRIs.
  const links = Object.entries(tab.comparison.links).every(([k, v]) => v.every((x) => {
    const [s, p] = [k.slice(0, 1), k.slice(2)];
    const q = x.slice(2);
    return classesOf(p).some((c) => classesOf(q).includes(c)) && s !== x.slice(0, 1);
  }));
  const linkedProtos = new Set(shared.flatMap((c) => [...protoOf(circ, c).map((p) => `a:${p}`), ...protoOf(pad, c).map((p) => `b:${p}`)]));
  check("Compare: links are made only between prototypes sharing an emotion class IRI", links &&
        Object.keys(tab.comparison.links).sort().join() === [...linkedProtos].sort().join());

  // ---------------------------------------------------------------- summary panel
  const sum = tab.ui.summary;
  const sharedText = sum.querySelector('[data-role="shared"]').textContent;
  check("Compare: the summary lists the shared emotions (by class IRI) and counts",
        shared.every((c) => sharedText.includes(E[c]?.label ?? local(c))) &&
        sum.textContent.includes(`${shared.length} shared`) &&
        sum.textContent.includes(`${circ.dims.length}: `) && sum.textContent.includes(`${pad.dims.length}: `), sharedText);
  const header = [...sum.querySelectorAll(".table-scroll .compare-table thead th")].map((t) => t.textContent);
  check("Compare: non-equivalent domains get a structural comparison only (no differences or distances)",
        /None established/.test(sum.querySelector('[data-role="equivalence"]').textContent) &&
        !header.some((h) => h.startsWith("B − A") || h.includes("distance")));
  const firstShared = tab.comparison.rows.findIndex((r) => r.status === "shared");
  const tr = sum.querySelector(`tr[data-row="${firstShared}"]`);
  const cells = [...tr.children].map((td) => td.textContent);
  const row = tab.comparison.rows[firstShared];
  check("Compare: the table shows the coordinates of matching emotions in both domains",
        circ.dims.every((d) => cells.includes(String(circ.coords[row.a.id][d]))) &&
        pad.dims.every((d) => cells.includes(String(pad.coords[row.b.id][d]))), cells.join(" | "));
  tr.click();
  check("Compare: clicking a table row selects that emotion in both plots",
        ids(svgA, "selected").join() === row.a.id && ids(svgB, "linked").includes(row.b.id));
  check("Compare: missing ranges and placeholder definitions are listed as warnings",
        [...sum.querySelectorAll(".warnings li")].some((li) => /pad \/ pleasure: range not stated/.test(li.textContent)) &&
        [...sum.querySelectorAll(".warnings li")].some((li) => /definition is a placeholder only/.test(li.textContent)));

  // ---------------------------------------------------------------- projections
  tab.setAxes("b", [pad.dims[2]]);
  const oneD = svgB.dataset.mode;
  tab.setAxes("b", [pad.dims[0], pad.dims[2]]);
  const twoD = svgB.dataset.mode === "2d" && plotted(svgB, pad);
  tab.setAxes("a", [circ.dims[1]]);
  const oneA = svgA.dataset.mode === "1d" && plotted(svgA, circ);
  check("Compare: 1D, 2D and 3D projections can be chosen per plot", oneD === "1d" && twoD && oneA,
        `${oneD} ${svgB.dataset.mode} ${svgA.dataset.mode}`);
  tab.setAxes("a", circ.dims);
  tab.setAxes("b", pad.dims);

  // ---------------------------------------------------------------- exports (captured, not downloaded)
  const files = {};
  let captured = null;
  tab.download = (f) => { captured = f; };
  for (const kind of ["svg-a", "svg-b", "png-a", "csv", "html", "md"]) {
    captured = null;
    tab.el.querySelector(`[data-export="${kind}"]`).click();
    for (let i = 0; i < 400 && !captured; i++) await new Promise((r) => setTimeout(r, 25));
    files[kind.replace(/-(a|b)$/, (m, s) => `-${s.toUpperCase()}`)] = captured;
  }
  check("Compare: every export button produces a file with the model names in its file name",
        Object.values(files).every((f) => f && f.filename.startsWith("compare_domain_circumplex_vs_domain_pad_")),
        Object.values(files).map((f) => f?.filename).join(", "));
  const parse = (text) => new DOMParser().parseFromString(text, "image/svg+xml");
  const svgOk = (key, s, d, svg) => {
    const doc = parse(files[key].data);
    if (doc.querySelector("parsererror")) return false;
    const pts = [...doc.querySelectorAll(".pt")];
    const onScreen = plottedPoints(svg);
    const text = doc.documentElement.textContent;
    return pts.length === onScreen.length && pts.every((g, i) => {
      const c = g.querySelector("circle"), o = onScreen[i];
      return g.getAttribute("data-id") === o.id && +c.getAttribute("cx") === o.x && +c.getAttribute("cy") === o.y &&
             (c.getAttribute("style") || "").includes("fill:");
    }) && text.includes(d.id) && tab.comparison[s].dimensions.every((x) => text.includes(x.label));
  };
  check("Compare: the SVG exports are standalone (styles inlined) and identical in content to the plots",
        svgOk("svg-A", "a", circ, svgA) && svgOk("svg-B", "b", pad, svgB));
  check("Compare: the SVG export includes the model IRI, axis labels and missing-information warnings",
        files["svg-B"].data.includes("range not stated; axis spans the data extent") && files["svg-B"].data.includes(pad.id) &&
        files["svg-A"].data.includes("Axes: X = valence [-1, 1]"));
  const png = files["png-A"].data;
  const bitmap = png instanceof Blob ? await createImageBitmap(png) : null;
  const svgW = Number(parse(files["svg-A"].data).documentElement.getAttribute("width"));
  check("Compare: the PNG export is a PNG image at twice the figure size",
        png.type === "image/png" && bitmap && bitmap.width === Math.round(svgW * 2), `${bitmap?.width} vs ${svgW}`);
  const url = (fmt) => `/api/compare?a=${encodeURIComponent(circ.id)}&b=${encodeURIComponent(pad.id)}&format=${fmt}`;
  const [csvServer, mdServer] = await Promise.all([fetch(url("csv")).then((r) => r.text()), fetch(url("md")).then((r) => r.text())]);
  check("Compare: the CSV and Markdown exports are the server's comparison exports, unchanged",
        (await blobText(files.csv.data)) === csvServer && (await blobText(files.md.data)) === mdServer);
  const html = await blobText(files.html.data);
  const htmlDoc = new DOMParser().parseFromString(html, "text/html");
  check("Compare: the HTML summary is self-contained and embeds both figures",
        htmlDoc.querySelectorAll("figure > svg").length === 2 && !html.includes("<!-- figures -->") &&
        !/(src|href)=["']https?:/.test(html) && htmlDoc.querySelectorAll("figure .pt").length ===
          plottedPoints(svgA).length + plottedPoints(svgB).length);
  const exports = { svgA: files["svg-A"].data, svgB: files["svg-B"].data, csv: await blobText(files.csv.data), html,
                    pngWidth: bitmap?.width, a: circ.id, b: pad.id };

  // ---------------------------------------------------------------- the same domain twice
  await tab.compare(circ.id, circ.id);
  const head2 = [...sum.querySelectorAll(".table-scroll .compare-table thead th")].map((t) => t.textContent);
  const diffCols = head2.map((h, i) => (h.startsWith("B − A") || h === "Euclidean distance" ? i : -1)).filter((i) => i >= 0);
  const zero = [...sum.querySelectorAll(".table-scroll .compare-table tbody tr[data-row]")]
    .every((r) => diffCols.every((i) => r.children[i].textContent === "0"));
  check("Compare: the same domain twice is fully equivalent; all differences and distances are 0",
        /^Full/.test(sum.querySelector('[data-role="equivalence"]').textContent) && diffCols.length === circ.dims.length + 1 &&
        zero && tab.comparison.rows.length === circ.protos.length, head2.join(" | "));
  clickPoint(svgA, circ.protos[0]);
  check("Compare: with the same domain twice, a selection highlights the same prototype in B",
        ids(svgB, "linked").join() === circ.protos[0]);

  // ---------------------------------------------------------------- domains without prototypes, different dimensionality
  const empty = Object.values(expected).filter((d) => !d.protos.length);
  if (empty.length >= 2) {
    await tab.compare(empty[0].id, empty[1].id);
    const li = [...sum.querySelectorAll(".warnings li")].map((x) => x.textContent);
    check("Compare: domains without prototypes show an explanation instead of a plot, and a warning",
          svgA.dataset.mode === "empty" && svgB.dataset.mode === "empty" &&
          /No prototypical instances/.test(svgA.textContent) && !sum.querySelector("tr[data-row]") &&
          li.filter((t) => /no prototypical instances are linked/.test(t)).length === 2, li.join(" | "));
    const svgE = (await tab.exportFile("svg-a")).data;
    check("Compare: an empty plot still exports, with the missing-prototype warning",
          svgE.includes("has no prototypical instances in the ontology") && !parse(svgE).querySelector("parsererror"));
  }
  const oneDim = Object.values(expected).find((d) => d.dims.length === 1);
  if (oneDim) {
    await tab.compare(oneDim.id, pad.id);
    check("Compare: domains with different numbers of dimensions are compared (1 vs 3)",
          tab.comparison.a.dimensions.length === 1 && tab.comparison.b.dimensions.length === 3 &&
          tab.pickers.a.el.hidden && !tab.pickers.b.el.hidden);
  }
  await tab.compare(circ.id, pad.id);
  return exports;
}
