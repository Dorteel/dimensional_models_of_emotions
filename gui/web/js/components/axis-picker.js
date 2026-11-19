// Projection picker: choose up to three of a list of axes (X, Y, Z) for a CoordinatePlot. Generic.
//
//   setOptions([{id, label}])   1 option: hidden, that axis; 2 or more: X required, Y and Z optional ("none").
//                               Default: the first three options in order.
//   value                       chosen ids in X, Y, Z order, without "none" and without repeats
//   Events: "change".

export class AxisPicker extends EventTarget {
  constructor(container) {
    super();
    this.el = document.createElement("span");
    this.el.className = "axis-pickers";
    this.selects = ["X", "Y", "Z"].map((name, i) => {
      const label = document.createElement("label");
      const select = document.createElement("select");
      select.dataset.axis = String(i);
      select.addEventListener("change", () => this.dispatchEvent(new Event("change")));
      label.append(`${name} `, select);
      this.el.append(label);
      return select;
    });
    container.append(this.el);
    this.options = [];
  }

  setOptions(options) {
    this.options = options;
    this.el.hidden = options.length < 2;
    this.selects.forEach((s, i) => {
      const opts = options.map((o) => new Option(o.label, o.id));
      if (i > 0) opts.unshift(new Option("— none", ""));
      s.replaceChildren(...opts);
      s.value = options[i]?.id ?? "";
    });
  }

  set(ids) {
    this.selects.forEach((s, i) => { s.value = ids[i] ?? ""; });
  }

  get value() {
    if (this.options.length < 2) return this.options.map((o) => o.id);
    return [...new Set(this.selects.map((s) => s.value).filter(Boolean))];
  }
}
