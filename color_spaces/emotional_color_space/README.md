# Emotional Color Space Explorer

An independent, static browser laboratory for exploring **personal hypotheses**:
hue as emotional direction, saturation as energy, and value as love / positive
orientation. These are philosophical metaphors, not established scientific
correlations, measurements, or psychological assessments. No emotion names are
preassigned to colors. The existing RGB/HSL application is unchanged.

## Launch

Open `index.html` in a desktop browser. All assets, including Plotly, are local;
there is no Python backend or internet requirement. Alternatively, from the
`color_spaces/` (or the root of an extracted copy):

```bash
python3 -m http.server 8000 --directory emotional_color_space
```

Visit `http://localhost:8000`. Python is optional and only serves static files.
Local storage behavior for `file://` pages varies by browser; using a local server
provides a stable origin. Labels always remain available for the current session,
and JSON export provides an independent backup.

## Controls

- Drag to rotate, scroll to zoom, and right-drag to pan.
- Value selects a horizontal, translucent hexagonal slice.
- Saturation selects the dark hexagonal contour within that slice.
- Hue selects the colored ray from the grayscale axis to the slice boundary.
- The colored marker is the selected HSV point; the swatch shows its RGB color.
- The surface checkbox hides the outer hexcone surface while keeping guides visible.
- Sliders support keyboard arrow keys. Updates retain the camera revision and do
  not supply a replacement camera.

At zero saturation, hue is invisible in the gray color; at zero value, all HSV
positions collapse to black. Hue labels can still be explored at these positions.

## Personal emotion labels

Choose a hue (integer degrees 0–359), enter a name, and select **Save label**.
Names apply to that exact hue, independently of saturation and value. Remove a
label with **Remove label**. Names are rendered as text, never interpreted as HTML.
Assignments persist in local storage under `emotional-color-space.labels.v1` when
storage is available. Storage failures are reported; session operation continues.

**Export JSON** downloads a versioned label file. **Import JSON** uses the file
picker and replaces the labels only after the whole file passes validation.
Files must be at most 100 KB; names must be 1–120 characters. Invalid files leave
existing labels intact. Example format (an illustrative user assignment):

```json
{"version": 1, "labels": {"120": "My own emotion name"}}
```

Labels are local to the browser origin; no data is transmitted or synchronized.

## Mathematical model

Let the six unit-hexagon corners be
`q_k = (cos(kπ/3), sin(kπ/3))`, with k = 0,…,5. For normalized hue H,
let `u=H/60`, `k=floor(u)`, and `f=u−k`. The embedding is

```text
(x,y) = S V ((1−f) q_k + f q_(k+1))
z = V
```

Wrap corner indices modulo six. Linear edge interpolation makes the boundary
hexagonal rather than circular. Within each sector, hue is an edge parameter;
its Euclidean polar angle differs slightly from H. Saturation is the fractional
distance from the axis to that hue's boundary, and value scales the cross-section.
Corner radii are V; side-midpoint radii are √3 V / 2. At S=1 a point lies exactly
on the boundary, and at S=0 it lies at `(0,0,V)`.

The outer surface uses six side triangles from black to the top hexagon and six
top triangles from white to its corners. Vertex RGB colors interpolate across
these triangles. The top grayscale center is white; the bottom apex is black.
Transparency mixes surface colors with the background; the opaque swatch gives
the selected RGB color directly. This is an idealized HSV embedding, not a
perceptually uniform color space. Unlike HSL, it has no upper white apex. Unlike
the RGB cube section `R+G+B=constant`, it is an embedding of HSV coordinates with
hexagonal constant-value sections.

## Verification

```bash
node emotional_color_space/test.js
```

Run from `color_spaces/` (or `node test.js` inside this directory). No npm
packages are needed. Tests check HSV→RGB, all 360 integer hue directions, grayscale,
apex collapse, boundary membership, regular hexagon edges, saturation scaling,
marker/swatch consistency, label serialization and validation, label persistence,
controller interactions, and camera revision stability.

Controller checks use a DOM/Plotly stub, so they verify update configuration and
state rather than actual WebGL appearance or camera interaction. Browser rendering
has not been verified in this environment.

## GitHub Pages

Publish the **contents of this directory**, including `plotly.min.js`, as a static
Pages site. All asset URLs are relative. No build step or runtime service is needed.
For a branch configured to serve the repository root, the application is available
at `<repository-pages-url>/emotional_color_space/` after extraction. See the
[parent README](../README.md#extraction-and-hosting) for publishing the current
layout. Deployment was not performed.

## Files

- `color_spaces.js`: pure HSV conversion, geometry, and label JSON validation.
- `main.js`: visualization, controls, label persistence and file handling.
- `index.html`, `style.css`: independent interface with the lab's design conventions.
- `plotly.min.js`: locally bundled Plotly copied from the existing lab.
- `test.js`: lightweight mathematical and controller regression checks.
