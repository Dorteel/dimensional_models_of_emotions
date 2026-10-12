# Interactive RGB Color Space Visualization

Run all commands below from `color_spaces/` (or the root of an extracted copy).
See [the portability README](README.md) for installation, all experiments, and
hosting changes in the current parent repository.

Explore RGB as a cube with colored samples, a black-to-white grayscale diagonal,
and its exact central hexagonal cross-section. This is an educational starting
point for studying the relationship between RGB geometry and HSV hue, saturation,
and value; HSV controls and alternative hue orderings are future experiments.

## Installation

Use Python 3.11 and a local environment; do not replace system Python packages.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Only NumPy and Plotly are direct dependencies. Select `.venv/bin/python` as the
interpreter in your IDE. If `venv` or `ensurepip` is missing, install the matching
Python 3.11 venv package through your operating system's package manager (on
Debian/Ubuntu systems providing it, `sudo apt install python3.11-venv`), then retry.
The venv module was available in the environment used for this project.

## Running

```bash
.venv/bin/python rgb_cube_hexagon.py
```

This writes a self-contained `rgb_cube.html` and opens it in your browser.
For a headless environment:

```bash
.venv/bin/python rgb_cube_hexagon.py --no-open
```

Open the resulting HTML manually. Optional arguments include `--samples 30`
(points per channel), `--size 2` (coordinate scale), and `--output cube.html`.
Sampling produces `samples³` points, so larger resolutions increase memory,
HTML size, and browser rendering cost rapidly. The default is 18³ = 5,832 points.

Drag to rotate, scroll to zoom, and right-drag to pan. Hover over points for their
RGB colors. The Plotly toolbar also provides camera controls and image export.
Browser interaction has not been verified in the headless development environment.

## Geometry

Each normalized RGB channel independently ranges from 0 to 1, giving a unit cube.
Color labels use rounded 8-bit channel values (0–255); coordinates retain full
floating-point precision. `--size` scales all geometry uniformly.

Grayscale has equal channels, R = G = B. Points `(t,t,t)` therefore form the
body diagonal from black `(0,0,0)` to white `(1,1,1)`. Its line has a grayscale
gradient and an arrow at the white endpoint.

The plane R + G + B = 1.5 passes through `(0.5,0.5,0.5)` and has normal
`(1,1,1)`, so it is perpendicular to the grayscale diagonal. Its intersection
with the cube is a regular hexagon whose six vertices are the permutations of
`(0,0.5,1)`. Projecting these vertices onto an orthonormal basis in the plane
and sorting their angles gives a cyclic boundary without crossing edges.
Colored edges and spokes connect the vertices and middle gray.

This exact slice is distinct from the hexagonal silhouette obtained by projecting
the whole cube along its diagonal. Its vertices have HSV saturation 1 and value 1,
with hues 30°, 90°, 150°, 210°, 270°, and 330°. Angle around the grayscale axis
and HSV hue need not agree at every point; the plane fixes the channel sum,
whereas HSV value is the largest channel.

## Verification

```bash
.venv/bin/python -m unittest -v
.venv/bin/python -m pip check
```

Tests check vertices, cyclic ordering, grayscale endpoints, sample counts and
spacing, invalid parameters, coordinate scaling, and figure JSON/HTML serialization.

## Movable cross-section

The slider selects `t` on the grayscale diagonal, placing the plane's center at
`(t,t,t)` and setting its normalized equation to `R + G + B = 3t`.
It has 0.01-spaced positions and additional exact stops at `1/3` and `2/3`;
the initial position is `0.5`. The panel beside the cube shows `t`, the equation,
the section type, and normalized vertex coordinates (displayed to six significant
figures). The center marker follows the selected position.

| Position | Section |
| --- | --- |
| `t = 0` | Black point |
| `0 < t ≤ 1/3` | Triangle |
| `1/3 < t < 2/3` | Hexagon |
| `2/3 ≤ t < 1` | Triangle |
| `t = 1` | White point |

Each section is calculated by intersecting the plane with all twelve cube edges,
deduplicating shared corners, and sorting the vertices around their centroid in
a consistent plane basis. The central hexagon is regular; other hexagonal slices
usually have alternating edge lengths. There is no fixed polygon approximation.

The translucent surface uses explicit triangles from the center to consecutive
vertices. Plotly's Mesh3d vertex colors interpolate the RGB coordinates across
these triangles. Neutral ambient lighting avoids directional color shading;
transparency still blends colors with the scene behind the surface. Visible edges,
colored vertex markers, and spokes clarify the geometry. Point sections have no
surface triangles.

Slider updates replace only the section traces and information panel. Stable
`uirevision` values request preservation of camera rotation and zoom. The large
point cloud is stored once, keeping slider data small. Camera preservation and
color appearance still require a manual browser check in this headless environment.

## RGB ↔ HSL browser laboratory

The default Python command now exports a self-contained, offline HTML laboratory:

```bash
.venv/bin/python rgb_cube_hexagon.py
```

The left panel is the normalized RGB cube; the right panel embeds the same colors
in a circular HSL double cone. Resolution (3–30 samples per channel), lightness,
grayscale-axis visibility, and all-colors/section mode are shared controls. Click
a sample in either view to highlight its RGB counterpart in both, show normalized
RGB and HSL coordinates, and display a large color swatch. Hover also shows both
coordinate systems. Selection survives control changes, even when the selected
color lies outside the current section. Cameras remain independent and have
stable revision identifiers across updates. Drag to rotate, scroll to zoom, and
right-drag to pan.

The section slider now means **HSL lightness**, not channel sum:

```text
L = (max(R,G,B) + min(R,G,B)) / 2
radius = S × (1 − |2L − 1|)
x = radius × cos(H), y = radius × sin(H), z = L
```

For fixed L and chroma C, min = L − C/2 and max = L + C/2,
with 0 ≤ C ≤ 2 min(L,1−L). For each of the six channel orderings, the middle
channel varies between min and max. Each ordering therefore forms one exact
planar triangle, giving a folded surface of six triangles in RGB. It is not the
previous perpendicular plane. In the HSL embedding these same colors form a disk
at height L; black and white collapse to points. Section mode samples these exact
triangles with a barycentric grid, rather than choosing cube samples with nearly
matching lightness. All-colors mode uses the same n³ RGB samples in both panels.

Radius equals chroma; saturation is radius divided by the maximum radius at that
lightness. Hue is undefined for gray and displayed as 0° by convention. The
circular double-cone embedding follows the requested trigonometric equations;
it is not a hexagonal bihexcone or a perceptually uniform space. The HSL surface
uses 120 triangles to approximate the circular disk; the RGB surface is exact.
Surface colors interpolate vertex RGB values and blend with the background due
to transparency.

The original perpendicular-plane explorer remains available:

```bash
.venv/bin/python rgb_cube_hexagon.py --legacy
```

Earlier plane-slider instructions in this README apply to `--legacy`.
`--size` also applies to the legacy view; the laboratory always uses normalized RGB.
Both modes support `--output` and `--no-open`.

### GitHub Pages

The complete static site is in `docs/`, with relative paths and a local Plotly
bundle. No runtime Python, CDN, build step, or backend is required. Commit these
files in an extracted repository and select its branch and `/docs` directory in **Settings →
Pages → Deploy from a branch**. Publishing was not performed by this change.
For local use, open `docs/index.html`, or serve it with:

```bash
.venv/bin/python -m http.server 8000 --directory docs
```

Open `http://localhost:8000`. Regenerate `docs/plotly.min.js` after an intentional
Plotly upgrade using `plotly.offline.get_plotlyjs()`; the Python HTML exporter
embeds the installed Plotly version directly.

Additional dependency-free JavaScript checks:

```bash
node test_color_space.js
node test_lab.js
node --check docs/lab.js
```
