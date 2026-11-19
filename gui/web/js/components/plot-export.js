// Export a rendered SVG figure as a standalone SVG (styles inlined, title and footer lines added) or PNG.
// Generic: works on any SVG element in the page; the caller supplies the title and footer text.

const SVG_NS = "http://www.w3.org/2000/svg";
const PROPS = ["fill", "fill-opacity", "stroke", "stroke-width", "stroke-dasharray", "stroke-opacity", "opacity",
               "font-family", "font-size", "font-weight", "text-anchor", "paint-order", "stroke-linejoin", "display",
               "visibility"];
const LINE = 16;

function node(name, attrs = {}, text) {
  const n = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
}

function wrap(text, width) {
  const max = Math.max(20, Math.floor(width / 6.2));
  const out = [];
  let line = "";
  for (const word of String(text).split(/\s+/)) {
    if (line && (line + " " + word).length > max) { out.push(line); line = word; } else line = line ? `${line} ${word}` : word;
  }
  if (line) out.push(line);
  return out;
}

// Copy the computed presentation of every element into inline attributes, so the SVG looks the same
// without the page's stylesheet.
function inlineStyles(source, copy) {
  const from = [source, ...source.querySelectorAll("*")];
  const to = [copy, ...copy.querySelectorAll("*")];
  from.forEach((el, i) => {
    const cs = getComputedStyle(el);
    const style = PROPS.map((p) => `${p}:${cs.getPropertyValue(p)}`).filter((s) => !s.endsWith(":")).join(";");
    to[i].setAttribute("style", style);
  });
}

// Standalone SVG text: title lines above the figure, footer lines (wrapped) below it, opaque background.
// `omit`: selectors of on-screen-only elements to leave out (e.g. interaction hints).
export function standaloneSvg(svg, { title = [], footer = [], background, omit = [] } = {}) {
  const vb = svg.viewBox.baseVal;
  const w = vb && vb.width ? vb.width : svg.clientWidth, h = vb && vb.height ? vb.height : svg.clientHeight;
  const css = getComputedStyle(svg);
  const bg = background || getComputedStyle(document.body).backgroundColor || "#ffffff";
  const titleLines = title.flatMap((t) => wrap(t, w - 24));
  const footLines = footer.flatMap((t) => wrap(t, w - 24));
  const top = titleLines.length ? titleLines.length * LINE + 14 : 0;
  const bottom = footLines.length ? footLines.length * LINE + 14 : 0;
  const out = node("svg", { xmlns: SVG_NS, width: w, height: top + h + bottom, viewBox: `0 0 ${w} ${top + h + bottom}` });
  out.append(node("rect", { x: 0, y: 0, width: w, height: top + h + bottom, fill: bg }));
  const ink = css.color || "#000";
  titleLines.forEach((t, i) => out.append(node("text", { x: 12, y: 20 + i * LINE, "font-family": css.fontFamily,
    "font-size": i ? 12 : 14, "font-weight": i ? 400 : 700, fill: ink, class: "export-title" }, t)));
  const figure = svg.cloneNode(true);
  inlineStyles(svg, figure);
  figure.removeAttribute("tabindex");
  for (const sel of omit) figure.querySelectorAll(sel).forEach((n) => n.remove());
  for (const [k, v] of Object.entries({ x: 0, y: top, width: w, height: h, viewBox: `0 0 ${w} ${h}` })) figure.setAttribute(k, v);
  out.append(figure);
  footLines.forEach((t, i) => out.append(node("text", { x: 12, y: top + h + 18 + i * LINE, "font-family": css.fontFamily,
    "font-size": 11, fill: ink, class: "export-footer" }, t)));
  return `<?xml version="1.0" encoding="UTF-8"?>\n${new XMLSerializer().serializeToString(out)}`;
}

// PNG of a standalone SVG text, at `scale` × its size.
export async function svgToPng(svgText, scale = 2) {
  const doc = new DOMParser().parseFromString(svgText, "image/svg+xml").documentElement;
  const w = Number(doc.getAttribute("width")), h = Number(doc.getAttribute("height"));
  const url = URL.createObjectURL(new Blob([svgText], { type: "image/svg+xml" }));
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    const ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0, w, h);
    return await new Promise((resolve, reject) =>
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("PNG encoding failed"))), "image/png"));
  } finally {
    URL.revokeObjectURL(url);
  }
}

// Save a file in the browser.
export function download({ filename, type, data }) {
  const blob = data instanceof Blob ? data : new Blob([data], { type });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
