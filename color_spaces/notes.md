# Implementation notes

## Environment diagnosis

- The default `python3` is Python 3.8.10; `/usr/bin/python3.11` is 3.11.13.
  Python 2.7 and 3.10 executables also exist in `/usr/bin`.
- Reproduced the reported import failure with `/usr/bin/python3.11`.
  It resolves NumPy 1.17.4 from `/usr/lib/python3/dist-packages`.
  That installation contains `_multiarray_umath.cpython-38-x86_64-linux-gnu.so`,
  a Python 3.8 extension that Python 3.11 cannot load.
- Plotly was not found by the system Python 3.11 interpreter. Its pip also came
  from the system package directory. No existing project venv was found.
- The inherited PYTHONPATH includes ROS and Webots directories. Neither caused
  the reproduced NumPy failure. Explicit `.venv/bin/python` selects the intended
  interpreter; if those inherited directories cause future conflicts, use
  `env -u PYTHONPATH .venv/bin/python ...`.
- Created `.venv` with system-site-packages disabled and installed NumPy 2.4.6
  and Plotly 7.1.0 locally. requirements.txt pins these verified direct dependencies.
  No system Python packages were modified. Dependency downloads required network
  access outside the restricted sandbox.

## Changes and decisions

- Read the existing script first. Its plane, exact vertices, and angle ordering
  were mathematically correct; no syntax errors were found.
- Extracted three small geometry functions for lightweight unittest checks.
- Sample normalized floating-point coordinates directly. The previous uint8
  linspace quantized coordinates and repeated channel positions above 256 samples.
  Round only the display colors to 8-bit RGB.
- Preserve the point cloud, grayscale gradient, arrow, endpoint labels, hexagon,
  spokes, center label, scaling option, and automatic browser opening.
- Use Plotly per-point line colors and colorscales for the diagonal and boundary
  gradients, reducing 267 traces to 13 without adding dependencies. The boundary
  colorscale interpolates between each vertex's RGB color.
- Add `--no-open` for headless execution; default behavior still opens a browser.
- Reject non-finite/non-positive sizes. Rendering and memory costs remain cubic
  in sample resolution; no arbitrary upper resolution limit was imposed.
- Use standard-library unittest rather than introducing a test dependency.

## Verification

All nine tests passed using `.venv/bin/python -m unittest -v`. The default script
ran with `--no-open` and wrote self-contained HTML. NumPy and Plotly imported from
`.venv`, and `pip check` reported no broken requirements. Figure construction and
JSON/HTML serialization were verified; actual browser rendering, gradient
appearance, rotation, zoom, and panning were not tested.

## Movable section extension

- Added `section_vertices(t)` using the twelve axis-aligned cube edges. Each edge
  fixes two coordinates at 0 or 1; solve the plane equation for the remaining
  coordinate and keep it only if it lies in [0,1]. Coincident corner intersections
  are deduplicated exactly. Sorting uses the existing orthonormal plane basis,
  now centered on the computed centroid. `hexagon_vertices()` remains available
  as a wrapper for t=0.5.
- Added 103 slider stops: 101 evenly spaced positions plus the exact fractions
  1/3 and 2/3. Geometry is exact for each selected floating-point t; slider position
  is discrete. No server, JavaScript dependency, or Python environment change
  was needed.
- Mesh3d uses explicit center-fan connectivity with RGB vertex colors and ambient
  lighting. Endpoint meshes have empty connectivity. Boundary lines, vertex
  markers, the diagonal center marker, and spokes complete five section traces.
  This supersedes the earlier static hexagon gradient boundary and six separate
  spoke traces; the full figure now has nine traces.
- Animation frames target only indices 4–8. Point-cloud data is not copied into
  frames. Both layout and scene have stable uirevision values; no frame supplies
  a camera value. Updates are immediate, with redraw enabled for the 3D mesh.
- The panel reports normalized geometry regardless of --size; values are rounded
  only for presentation. Existing command-line options and automatic HTML opening
  are preserved.
- Tests cover all slider positions, requested types, exact transitions and nearby
  positions, bounds, plane membership, unique vertices, centroid, consistent turns,
  mesh winding/connectivity, and frame trace targeting. All 14 tests passed.
- Headless execution generated HTML successfully; no browser rendering or camera
  interaction was verified. Stable camera configuration is checked structurally.

## RGB ↔ HSL laboratory

- Extended the Python entry point to export the browser laboratory by default;
  `--legacy` preserves the original plane explorer and its tested `make_cube` API.
  No Python dependency changes. Static assets live in docs/ for GitHub Pages.
  The single-file exporter inlines CSS, geometry, controller, and Plotly after
  the DOM. The static version vendors Plotly from the installed Python package.
- Shared RGB arrays are the source of both clouds. RGB→HSL conversion uses
  extrema and sector hue; achromatic hue uses the explicitly documented zero
  convention. Point selection reads the original RGB customdata rather than
  matching rendered coordinates, so coincident achromatic positions are safe.
- Constant HSL lightness surfaces use six ordered-channel triangles. Triangle
  vertices are (L,L,L) and ordered permutations of (low,low,high) and
  (low,high,high), where low=L−min(L,1−L), high=L+min(L,1−L).
  The surface has no single perpendicular plane. Section samples use barycentric
  coordinates, deduplicating shared boundaries; no lightness tolerance filtering.
- The circular HSL disk requires hue subdivision (120 triangles). RGB surfaces
  have exact six-triangle geometry. RGB vertex colors use ambient-only lighting;
  alpha blending means translucent surface appearance is illustrative. Discrete
  colored points retain the same display color in each view.
- Controls operate entirely in JavaScript. Cloud samples are cached by resolution
  and section position, slider events are debounced, and updates are serialized
  with the latest pending state. Stable uirevision retains each independent camera.
  Selection updates use restyle on dedicated highlight traces and survive filters.
- GitHub Pages was explicitly requested, so no Sites hosting registration or
  publication was used. No deployment was requested or performed. No external
  CDN or new JavaScript package dependency was introduced.
- JavaScript geometry tests verify canonical hues, grayscale, 1,331 RGB/HSL round
  trips, chroma radii, nine section levels, triangle interiors, endpoint collapse,
  bounds, point counts, and invalid arguments. Existing Python tests remain intact.
- Actual WebGL rendering and camera preservation require browser verification;
  this environment has no callable browser tool. Syntax, geometry, static export,
  and existing Plotly serialization are verified separately.

- Final checks: all 15 Python tests passed, including portable HTML export.
  JavaScript geometry and DOM/Plotly-stub controller checks passed, as did JS
  syntax checks and pip check. Both default and legacy CLI exports succeeded.
  Controller checks verify linked selections, matching samples, section updates,
  resolution, axis toggles, endpoint meshes, and camera revision configuration;
  they do not test actual WebGL rendering. A native headless Chrome attempt
  failed at startup in the sandbox, so browser QA remains unverified.

## Click-freeze investigation

The click handler previously called restyle synchronously during Plotly picking,
without guarding repeat selections or serializing against slider redraws. A
replayed pick could cause repeated redraws. Browser reproduction is unavailable,
so this is a suspected cause rather than a confirmed WebGL diagnosis. Selection
now ignores identical RGB values, defers scene updates until the picking callback
returns, serializes updates with rendering, and handles rejected update promises.
The controller regression stub replays a click during restyle and verifies that
only two redraws occur (one per view), with no further redraw on repeat selection.
Regenerated the standalone HTML so the default output includes the fix.
