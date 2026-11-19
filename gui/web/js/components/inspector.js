// Detail panel. Generic: shows a description object; rows with `ref` become navigation links.
//
//   show({title, subtitle?, badges?: [string], breadcrumbs?: [[{label, ref?}]],
//         sections: [{title, rows: [{key?, value, ref?, note?, mono?}], empty?}]})
//
// Events: "navigate" {detail: {id}}.

export class Inspector extends EventTarget {
  constructor(container) {
    super();
    this.container = container;
    this.container.classList.add("inspector");
    this.clear();
  }

  clear(message = "Select a node in the graph or an item in the hierarchy to inspect it.") {
    const p = document.createElement("p");
    p.className = "inspector-empty";
    p.textContent = message;
    this.container.replaceChildren(p);
  }

  _link(label, ref) {
    const a = document.createElement("a");
    a.href = "#";
    a.className = "inspector-link";
    a.dataset.ref = ref;
    a.textContent = label;
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      this.dispatchEvent(new CustomEvent("navigate", { detail: { id: ref } }));
    });
    return a;
  }

  show(desc) {
    const frag = document.createDocumentFragment();
    const h = document.createElement("h2");
    h.className = "inspector-title";
    h.textContent = desc.title;
    frag.append(h);
    if (desc.subtitle) {
      const s = document.createElement("div");
      s.className = "inspector-subtitle";
      s.textContent = desc.subtitle;
      frag.append(s);
    }
    if (desc.badges?.length) {
      const b = document.createElement("div");
      b.className = "inspector-badges";
      for (const text of desc.badges) {
        const span = document.createElement("span");
        span.className = "badge";
        span.textContent = text;
        b.append(span);
      }
      frag.append(b);
    }
    for (const crumbs of desc.breadcrumbs || []) {
      const nav = document.createElement("nav");
      nav.className = "breadcrumbs";
      crumbs.forEach((c, i) => {
        if (i) nav.append(" › ");
        nav.append(c.ref ? this._link(c.label, c.ref) : Object.assign(document.createElement("span"), { textContent: c.label }));
      });
      frag.append(nav);
    }
    for (const section of desc.sections) {
      if (!section.rows.length && !section.empty) continue;
      const sec = document.createElement("section");
      sec.className = "inspector-section";
      sec.dataset.section = section.title;
      const h3 = document.createElement("h3");
      h3.textContent = `${section.title}${section.rows.length > 1 ? ` (${section.rows.length})` : ""}`;
      sec.append(h3);
      if (!section.rows.length) {
        const p = document.createElement("p");
        p.className = "muted";
        p.textContent = section.empty;
        sec.append(p);
      } else {
        const dl = document.createElement("dl");
        for (const row of section.rows) {
          const dt = document.createElement("dt");
          dt.textContent = row.key ?? "";
          const dd = document.createElement("dd");
          if (row.mono) dd.classList.add("mono");
          dd.append(row.ref ? this._link(row.value, row.ref) : document.createTextNode(row.value));
          if (row.note) {
            const note = document.createElement("span");
            note.className = "note";
            note.textContent = ` ${row.note}`;
            dd.append(note);
          }
          dl.append(dt, dd);
        }
        sec.append(dl);
      }
      frag.append(sec);
    }
    this.container.replaceChildren(frag);
    this.container.scrollTop = 0;
  }
}
