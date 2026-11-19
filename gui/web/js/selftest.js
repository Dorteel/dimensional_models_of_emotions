// End-to-end self-test, loaded only with ?selftest=1 (used by gui/tests/test_browser.py).
// Drives the real UI with DOM events and compares what is shown with the API data,
// which it fetches independently. Expected values are derived from the ontology file, not hard-coded.

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// requestAnimationFrame may not fire in headless/background pages; fall back to a timer.
const frame = () => Promise.race([new Promise((r) => requestAnimationFrame(() => r())), sleep(50)]);

function pointer(target, type, x, y) {
  target.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y,
                                                 pointerId: 1, button: 0, buttons: type === "pointerup" ? 0 : 1 }));
}

function clickNode(view, id) {
  const n = view.nodes.get(id);
  const r = n.el.getBoundingClientRect();
  const target = n.el.querySelector("rect, circle");
  pointer(target, "pointerdown", r.x + r.width / 2, r.y + r.height / 2);
  pointer(target, "pointerup", r.x + r.width / 2, r.y + r.height / 2);
}

export async function run(dashboard) {
  const checks = [];
  const check = (name, ok, detail = "") => {
    checks.push({ name, ok: !!ok, detail: String(detail) });
    console.log(`[selftest] ${ok ? "PASS" : "FAIL"} ${name}`);
  };
  const out = document.createElement("pre");
  out.id = "selftest-result";
  try {
    const tab = dashboard.tabs.ontology;
    await tab.ready;
    await frame();
    const view = tab.graph;
    const svg = view.svg;
    const inspectorTitle = () => tab.inspector.container.querySelector(".inspector-title")?.textContent;
    const sectionRows = (title) => tab.inspector.container
      .querySelectorAll(`.inspector-section[data-section="${title}"] dd`).length;

    // ---------------------------------------------------------------- dashboard + loading
    const tabs = [...document.querySelectorAll('.tabbar [role="tab"]')].map((b) => b.textContent);
    check("Dashboard has exactly one tab, 'Emotional Ontology'", tabs.length === 1 && tabs[0] === "Emotional Ontology",
          JSON.stringify(tabs));
    const list = await (await fetch("/api/ontologies")).json();
    const wantedFile = new URLSearchParams(location.search).get("file") || list.default;
    const api = await (await fetch(`/api/ontology?file=${encodeURIComponent(wantedFile)}`)).json();
    check("Ontology loaded from disk via the API (requested file shown)", tab.model?.meta.file === wantedFile &&
          tab.model.meta.sha256 === api.meta.sha256, `${wantedFile} sha256 ${api.meta.sha256.slice(0, 12)}`);
    check("Status bar shows the file's sha256",
          tab.ui.status.textContent.includes(api.meta.sha256.slice(0, 12)), tab.ui.status.textContent);

    // ---------------------------------------------------------------- graph content
    const ents = Object.values(api.entities);
    const graphEnts = ents.filter((e) => e.kind === "class" || e.kind === "individual" ||
                                         (e.kind === "resource" && !e.declared));
    const ids = new Set(graphEnts.map((e) => e.id));
    const nClass = ents.filter((e) => e.kind === "class").length;
    const nInd = ents.filter((e) => e.kind === "individual").length;
    check("Every class is drawn as a class node (rect)",
          svg.querySelectorAll(".node.k-class").length === nClass &&
          svg.querySelectorAll(".node.k-class > rect").length === nClass, `${nClass} classes`);
    check("Every individual is drawn as an individual node (circle)",
          svg.querySelectorAll(".node.k-individual").length === nInd &&
          svg.querySelectorAll(".node.k-individual > circle").length === nInd, `${nInd} individuals`);
    check("Graph has exactly the ontology's classes, individuals and referenced terms",
          svg.querySelectorAll(".node").length === ids.size, `${ids.size} nodes`);
    const apiEdges = api.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    check("Every relationship between drawn nodes is drawn as an edge",
          svg.querySelectorAll(".edge").length === apiEdges.length, `${apiEdges.length} edges`);
    for (const kind of ["subclass", "type", "relation", "domain_range"]) {
      const n = apiEdges.filter((e) => e.kind === kind).length;
      check(`Edge kind '${kind}' drawn (${n} in file)`, svg.querySelectorAll(`.edge.e-${kind}`).length === n, n);
    }
    if (nInd) {
      check("Classes and individuals are visually distinct (different shape and colour)", (() => {
        const c = svg.querySelector(".node.k-class > rect"), i = svg.querySelector(".node.k-individual > circle");
        return c && i && getComputedStyle(c).fill !== getComputedStyle(i).fill &&
               getComputedStyle(c).stroke !== getComputedStyle(i).stroke;
      })());
    }

    // ---------------------------------------------------------------- node inspection (class)
    const cls = ents.filter((e) => e.kind === "class" && e.declared)
      .sort((a, b) => b.subclasses.length - a.subclasses.length)[0];
    clickNode(view, cls.id);
    await frame();
    check(`Clicking class node '${cls.label}' selects it and shows it in the inspector`,
          view.selected === cls.id && inspectorTitle() === cls.label, inspectorTitle());
    check("Inspector lists the class's subclasses and superclasses from the file",
          sectionRows("Subclasses") === cls.subclasses.length && sectionRows("Superclasses") === cls.superclasses.length,
          `${cls.subclasses.length} subclasses, ${cls.superclasses.length} superclasses`);
    check("Hierarchy tree highlights the selected class",
          tab.tree.root.querySelector(".tree-row.selected")?.dataset.id === cls.id);
    check("Selected node and its neighbours are highlighted",
          view.nodes.get(cls.id).el.classList.contains("selected") && svg.classList.contains("has-selection"));

    // ---------------------------------------------------------------- node inspection (individual) + link navigation
    const ind = ents.filter((e) => e.kind === "individual" && e.out.length && e.literals.length)
      .sort((a, b) => b.out.length - a.out.length)[0] || ents.find((e) => e.kind === "individual" && e.out.length);
    if (ind) {
      clickNode(view, ind.id);
      await frame();
      check(`Clicking individual node '${ind.label}' shows its properties and relationships`,
            inspectorTitle() === ind.label && sectionRows("Outgoing relations") === ind.out.length &&
            sectionRows("Data values") === ind.literals.length && sectionRows("Incoming relations") === ind.in.length,
            `${ind.out.length} out, ${ind.in.length} in, ${ind.literals.length} data values`);
      const firstValue = ind.literals[0]?.value;
      check("Data values are shown verbatim", !firstValue ||
            [...tab.inspector.container.querySelectorAll('.inspector-section[data-section="Data values"] dd')]
              .some((dd) => dd.firstChild?.textContent === firstValue), firstValue?.slice(0, 60));
      const link = tab.inspector.container.querySelector('.inspector-section[data-section="Outgoing relations"] a');
      const target = link.dataset.ref;
      link.click();
      await frame();
      check("Following a relationship link in the inspector navigates to the related node",
            view.selected === target && inspectorTitle() === api.entities[target].label, api.entities[target].label);
    } else {
      check("File has no individuals with relations; individual inspection not applicable", nInd === 0 ||
            !ents.some((e) => e.kind === "individual" && e.out.length), `${nInd} individuals`);
    }

    // ---------------------------------------------------------------- zoom
    let k0 = view.transform.k;
    const box = svg.getBoundingClientRect();
    svg.dispatchEvent(new WheelEvent("wheel", { deltaY: -400, clientX: box.x + box.width / 2,
                                                clientY: box.y + box.height / 2, bubbles: true, cancelable: true }));
    check("Mouse wheel zooms in", view.transform.k > k0, `${k0.toFixed(3)} -> ${view.transform.k.toFixed(3)}`);
    k0 = view.transform.k;
    tab.el.querySelector('[data-role="zoom-out"]').click();
    check("Zoom-out button zooms out", view.transform.k < k0, `${k0.toFixed(3)} -> ${view.transform.k.toFixed(3)}`);
    k0 = view.transform.k;
    tab.el.querySelector('[data-role="zoom-in"]').click();
    check("Zoom-in button zooms in", view.transform.k > k0);
    check("Viewport transform is applied to the SVG",
          view.viewport.getAttribute("transform").includes(`scale(${view.transform.k})`));

    // ---------------------------------------------------------------- pan
    const before = view.transform, sel = view.selected;
    pointer(svg, "pointerdown", box.x + 5, box.y + 5);
    pointer(svg, "pointermove", box.x + 55, box.y + 30);
    pointer(svg, "pointermove", box.x + 105, box.y + 55);
    pointer(svg, "pointerup", box.x + 105, box.y + 55);
    const after = view.transform;
    check("Dragging the background pans the graph",
          Math.abs(after.x - before.x - 100) < 1e-6 && Math.abs(after.y - before.y - 50) < 1e-6 && after.k === before.k,
          `dx=${(after.x - before.x).toFixed(1)}, dy=${(after.y - before.y).toFixed(1)}`);
    check("Panning does not change the selection", view.selected === sel);

    // ---------------------------------------------------------------- node drag
    const dragId = view.selected;
    const n0 = { ...view.nodes.get(dragId) };
    const nr = view.nodes.get(dragId).el.getBoundingClientRect();
    const shape = view.nodes.get(dragId).el.querySelector("rect, circle");
    pointer(shape, "pointerdown", nr.x + 3, nr.y + 3);
    pointer(shape, "pointermove", nr.x + 43, nr.y + 3);
    pointer(shape, "pointerup", nr.x + 43, nr.y + 3);
    check("Dragging a node moves it", view.nodes.get(dragId).x > n0.x, `${n0.x.toFixed(1)} -> ${view.nodes.get(dragId).x.toFixed(1)}`);

    // ---------------------------------------------------------------- hierarchy navigation
    const deep = ents.find((e) => e.kind === "class" && e.declared && e.superclasses.some((s) =>
      api.entities[s]?.superclasses.length)) ||
      ents.find((e) => e.kind === "class" && e.declared && e.superclasses.length);
    const parent = deep.superclasses[0];
    const parentRow = tab.tree.root.querySelector(`.tree-row[data-id="${CSS.escape(parent)}"]`);
    parentRow.closest("li")._setOpen(false);
    parentRow.querySelector(".tree-toggle").click();     // expand the parent in the tree
    const childRow = parentRow.closest("li").querySelector(`:scope > ul > li > .tree-row[data-id="${CSS.escape(deep.id)}"]`);
    check("Expanding a class in the hierarchy tree shows its subclasses",
          !!childRow && childRow.offsetParent !== null, api.entities[parent].label);
    childRow.click();
    await frame();
    const pos = view.screenPosition(deep.id), vb = svg.getBoundingClientRect();
    check(`Selecting '${deep.label}' in the tree selects and centres it in the graph`,
          view.selected === deep.id && Math.abs(pos.x - vb.width / 2) < 1 && Math.abs(pos.y - vb.height / 2) < 1,
          `at (${pos.x.toFixed(0)}, ${pos.y.toFixed(0)}) of ${vb.width.toFixed(0)}×${vb.height.toFixed(0)}`);
    const crumb = [...tab.inspector.container.querySelectorAll(".breadcrumbs a")].find((a) => a.dataset.ref === parent);
    check("Inspector shows the class's path in the hierarchy", !!crumb);
    crumb.click();
    await frame();
    check("Clicking a hierarchy breadcrumb navigates up to the superclass",
          view.selected === parent && tab.tree.root.querySelector(".tree-row.selected")?.dataset.id === parent);

    // ---------------------------------------------------------------- focus mode
    const neighbours = new Set([parent]);
    for (const e of apiEdges) {
      if (e.source === parent) neighbours.add(e.target);
      if (e.target === parent) neighbours.add(e.source);
    }
    const focus = tab.el.querySelector('[data-role="focus"]');
    focus.checked = true;
    focus.dispatchEvent(new Event("change", { bubbles: true }));
    const visible = new Set(view.visibleNodeIds());
    check("Focus mode shows only the selected node and its direct neighbours",
          visible.size === neighbours.size && [...neighbours].every((id) => visible.has(id)), `${visible.size} nodes`);
    focus.checked = false;
    focus.dispatchEvent(new Event("change", { bubbles: true }));
    check("Leaving focus mode shows the whole graph again", view.visibleNodeIds().length === ids.size);

    // ---------------------------------------------------------------- filters
    const indBox = tab.el.querySelector('input[data-node="individual"]');
    indBox.checked = false;
    indBox.dispatchEvent(new Event("change", { bubbles: true }));
    const shownInd = [...svg.querySelectorAll(".node.k-individual")].filter((g) => !g.classList.contains("hidden")).length;
    check("Hiding individuals leaves only classes (and the selection) visible", shownInd <= 1, `${shownInd} visible`);
    indBox.checked = true;
    indBox.dispatchEvent(new Event("change", { bubbles: true }));

    // ---------------------------------------------------------------- search
    const prop = ents.find((e) => e.kind === "property");
    const entry = tab.index.find((x) => x.id === prop.id);
    tab.ui.search.value = entry.text;
    tab.ui.search.dispatchEvent(new Event("change", { bubbles: true }));
    check("Search finds a property and shows its definition in the inspector",
          inspectorTitle() === prop.label && sectionRows("Property definition") === prop.domain.length + prop.range.length + 1,
          prop.label);
  } catch (err) {
    check("Self-test ran without errors", false, `${err.message}\n${err.stack}`);
  }
  const failed = checks.filter((c) => !c.ok).length;
  out.dataset.status = failed ? "fail" : "pass";
  out.textContent = JSON.stringify({ passed: checks.length - failed, failed, checks }, null, 1);
  document.body.append(out);
  document.title = failed ? "SELFTEST FAIL" : "SELFTEST PASS";
  await sleep(0);
}
