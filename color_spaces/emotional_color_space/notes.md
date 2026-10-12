# Design and verification notes

## Scope

Created a separate browser application. Existing RGB/HSL source, Python entry
point, tests, and dependency requirements were not changed. Reused its system
font, blue controls, pale page background, white panels, border treatment, and
local Plotly bundle; there are no imports from the original application at runtime.
The user requested GitHub Pages readiness, so no Sites hosting or deployment was
introduced. Extra files are the local Plotly bundle and a dependency-free test.

## Geometry decisions

Use linear interpolation between consecutive regular-hexagon corners for hue,
then scale by S×V. This matches HSV's piecewise hue sectors and makes every
intermediate full-saturation hue lie on a straight edge. A trigonometric circle
would violate the hexcone requirement. Hue is a sector parameter, not exactly
the Euclidean angle between corners; the UI and README make that distinction.

Constant-value guides are horizontal regular hexagons. Saturation is a fraction
of the hue-specific boundary distance, not a fixed Euclidean radius. The selected
hue ray spans the axis to S=1 at the selected value. The marker lies at fraction S
on that ray. Black collapses all positions at V=0; white is at the top axis point,
not an upper apex. The value slice has empty triangle connectivity at V=0.

Outer surface and value-slice meshes use explicit triangle connectivity and RGB
vertex colors under ambient-only lighting. Alpha blending is illustrative; the
opaque swatch and numeric RGB values show the selected color unambiguously.

## Interaction and labels

Plotly.react runs on at most one scheduled animation frame with updates serialized
and the latest pending slider state retained. Only nine lightweight traces are
rendered; there is no point cloud to rebuild and no click-driven redraw handler.
The UI values and swatch update synchronously with slider input. Stable layout
and scene uirevision values retain camera orientation; no explicit camera reset
is included. The surface toggle changes only mesh visibility in the next update.

User labels apply to exact integer hue positions, with no preset emotion taxonomy.
Names are trimmed and restricted to 120 characters. Local storage has a versioned
key; failures leave session functionality available. JSON imports validate the
entire versioned document before replacing current assignments. Invalid imports
leave labels untouched. A 100 KB limit avoids oversized files. All names are
inserted through textContent, with null-prototype label maps and strict hue keys.
Exports contain only the version and user label map.

## Test results

`node emotional_color_space/test.js` passed geometry and controller checks:
canonical six hue colors, mixed HSV color, hue wraparound, 360 hue directions,
black apex, grayscale, all boundary sectors at three values, saturation scaling,
regular hexagons, label round trips, malformed label rejection, exact selected
marker/color, slider updates, stable camera revisions, surface toggle, local label
save/remove, export/import, and preservation after invalid import.

JavaScript syntax checks passed. Existing Python and JavaScript suites were also
run to check the original application. Controller tests use DOM/Plotly stubs and
cannot establish real WebGL camera preservation or visual appearance. Actual
browser rendering remains unverified; native headless Chrome failed to start in
the sandbox during earlier work on this repository. No deployment was performed.
