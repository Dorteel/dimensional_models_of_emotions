# Color-space experiments

This directory is self-contained: copy it into another repository without the
parent repository's files or virtual environment. No parent imports, npm packages,
CDNs, backend, or build step are required. Run the commands below from this directory.

## Install

The Python exporter requires Python 3.11 or newer, NumPy, and Plotly. Exact direct
dependencies are pinned in `requirements.txt`:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The browser applications need only a modern browser; they include local Plotly
bundles. Node.js is needed only for JavaScript tests, with no npm installation.

## Run

| Experiment | Command or page |
| --- | --- |
| Linked RGB cube / HSL double cone | Open `docs/index.html` |
| Offline RGB/HSL HTML export | `.venv/bin/python rgb_cube_hexagon.py` |
| Original RGB perpendicular-plane explorer | `.venv/bin/python rgb_cube_hexagon.py --legacy` |
| HSV hexcone with personal emotion labels | Open `emotional_color_space/index.html` |

Both Python modes write `rgb_cube.html` and open a browser. Use `--no-open` for
headless export, `--output path.html` to choose the output, and `--samples N` to
choose resolution. The laboratory supports 3–30 samples per channel; `--size`
scales the legacy cube. Relative output paths refer to the current working directory.

For HTTP access to both applications (recommended for persistent HSV labels):

```bash
python3 -m http.server 8000
```

Visit `http://localhost:8000/docs/` or
`http://localhost:8000/emotional_color_space/`. Labels remain local to the browser
origin; export JSON before changing the server origin to retain your assignments.

See [RGB/HSL details](RGB_HSL.md) and
[HSV controls and model](emotional_color_space/README.md). `notes.md` and the HSV
notes retain historical implementation records. `rgb-hsv.py` is an empty,
unimplemented placeholder preserved from the original repository.

## Verify

```bash
.venv/bin/python -m unittest discover -s . -v
.venv/bin/python -m pip check
node test_color_space.js
node test_lab.js
node emotional_color_space/test.js
node --check docs/lab.js
node --check emotional_color_space/main.js
```

The Python smoke tests copy the source/assets into a temporary directory and run
both export modes there. Tests also check that both static pages' assets exist
inside this directory. JavaScript controller tests use DOM/Plotly stubs; actual
WebGL appearance and mouse/camera behavior still need a browser check.

## Extraction and hosting

There are no remaining runtime dependencies on the parent repository. Create a
fresh virtual environment after copying; the parent's `.venv` is only a development
convenience and is not portable. Keep the included `.gitignore` when extracting.

Existing GitHub Pages settings that serve the parent's `/docs` need to be changed
when publishing this layout. After extraction, `docs/` can again be served by
branch-based Pages. In the current repository, deployment can upload
`color_spaces/docs/` (RGB/HSL) or `color_spaces/` (both applications) using a Pages
workflow. No hosting configuration or deployment has been performed here.

Each browser application keeps its own existing Plotly bundle so it remains
individually portable. To update them intentionally, write
`plotly.offline.get_plotlyjs()` to each `plotly.min.js`; the Python exporter embeds
the installed Plotly directly. No extra bundle copies were introduced.
