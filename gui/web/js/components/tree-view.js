// Collapsible tree navigator. Generic: renders items {id, label, badge?, className?, children?}.
// Events: "select" {detail: {id}}.

export class TreeView extends EventTarget {
  constructor(container) {
    super();
    this.container = container;
    this.root = document.createElement("ul");
    this.root.className = "tree";
    this.root.setAttribute("role", "tree");
    container.append(this.root);
    this.items = new Map();   // id -> [{li, row, item, parentLi}]  (an id may occur more than once)
    this.selected = null;
  }

  setData(roots, { expandDepth = 1 } = {}) {
    this.root.replaceChildren();
    this.items = new Map();
    this.selected = null;
    for (const item of roots) this.root.append(this._render(item, 0, expandDepth, null));
  }

  _render(item, depth, expandDepth, parentLi) {
    const li = document.createElement("li");
    li.setAttribute("role", "treeitem");
    const hasChildren = !!(item.children && item.children.length);
    const row = document.createElement("div");
    row.className = `tree-row ${item.className || ""}`.trim();
    row.dataset.id = item.id;
    row.tabIndex = -1;
    const toggle = document.createElement("button");
    toggle.className = "tree-toggle";
    toggle.type = "button";
    toggle.setAttribute("aria-label", "Expand or collapse");
    toggle.disabled = !hasChildren;
    const label = document.createElement("span");
    label.className = "tree-label";
    label.textContent = item.label;
    row.append(toggle, label);
    if (item.badge !== undefined && item.badge !== "") {
      const badge = document.createElement("span");
      badge.className = "tree-badge";
      badge.textContent = item.badge;
      row.append(badge);
    }
    if (item.title) row.title = item.title;
    li.append(row);
    if (!this.items.has(item.id)) this.items.set(item.id, []);
    this.items.get(item.id).push({ li, row, item, parentLi });

    if (hasChildren) {
      li.classList.add("has-children");
      const ul = document.createElement("ul");
      ul.setAttribute("role", "group");
      li.append(ul);
      let rendered = false;
      const renderChildren = () => {   // lazily, so large branches cost nothing until opened
        if (rendered) return;
        rendered = true;
        for (const child of item.children) ul.append(this._render(child, depth + 1, expandDepth, li));
      };
      li._renderChildren = renderChildren;
      const setOpen = (open) => {
        if (open) renderChildren();
        li.classList.toggle("open", open);
        li.setAttribute("aria-expanded", String(open));
      };
      li._setOpen = setOpen;
      setOpen(depth < expandDepth);
      toggle.addEventListener("click", (ev) => { ev.stopPropagation(); setOpen(!li.classList.contains("open")); });
    }
    row.addEventListener("click", () => this.select(item.id));
    return li;
  }

  // Expand the path to an item (searching unrendered branches too), highlight it and scroll to it.
  reveal(id) {
    if (!this.items.has(id)) this._renderPathTo(id);
    const entries = this.items.get(id);
    if (!entries) return false;
    const { li, row } = entries[0];
    for (let p = li.parentElement?.closest("li"); p; p = p.parentElement?.closest("li")) p._setOpen?.(true);
    row.scrollIntoView({ block: "nearest" });
    return true;
  }

  _renderPathTo(id) {
    // Breadth-first: open rendered-but-collapsed branches until the id appears.
    const queue = [...this.root.children];
    while (queue.length) {
      const li = queue.shift();
      if (li._renderChildren) {
        li._renderChildren();
        if (this.items.has(id)) return;
        queue.push(...li.querySelector(":scope > ul").children);
      }
    }
  }

  select(id, { emit = true } = {}) {
    for (const entries of this.items.values()) entries.forEach((e) => e.row.classList.remove("selected"));
    this.selected = id;
    if (id !== null && this.reveal(id)) this.items.get(id).forEach((e) => e.row.classList.add("selected"));
    if (emit) this.dispatchEvent(new CustomEvent("select", { detail: { id } }));
  }
}
