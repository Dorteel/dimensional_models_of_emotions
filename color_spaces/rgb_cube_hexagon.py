"""Interactive browser RGB/HSL laboratory with a legacy RGB plane explorer.

Install: pip install numpy plotly
Run: python rgb_cube_hexagon.py --samples 18

Open the generated rgb_cube.html in a browser. Drag to rotate, scroll to
zoom, and right-drag to pan. Increase --size to scale the cube's coordinates.
"""

import argparse
import webbrowser
from itertools import product
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs


def generate_rgb_points(samples: int = 18) -> np.ndarray:
    """Sample the unit cube uniformly; each channel has ``samples`` values."""
    if samples < 2:
        raise ValueError("samples must be >= 2")
    values = np.linspace(0.0, 1.0, samples)
    channels = np.meshgrid(values, values, values, indexing="ij")
    return np.column_stack([channel.ravel() for channel in channels])


def grayscale_diagonal(samples: int = 65) -> np.ndarray:
    """Return points with R = G = B, including black and white."""
    if samples < 2:
        raise ValueError("samples must be >= 2")
    return np.repeat(np.linspace(0.0, 1.0, samples)[:, None], 3, axis=1)


def section_vertices(t: float) -> np.ndarray:
    """Intersect R + G + B = 3t with the cube's twelve axis-aligned edges."""
    if not np.isfinite(t) or not 0 <= t <= 1:
        raise ValueError("t must be finite and between 0 and 1")
    vertices = []
    for axis in range(3):
        fixed_axes = [index for index in range(3) if index != axis]
        for fixed in product((0.0, 1.0), repeat=2):
            coordinate = 3 * t - sum(fixed)
            if 0 <= coordinate <= 1:
                vertex = np.zeros(3)
                vertex[fixed_axes] = fixed
                vertex[axis] = coordinate
                # Several edges meet at each cube corner at the transitions.
                if not any(np.array_equal(vertex, other) for other in vertices):
                    vertices.append(vertex)
    vertices = np.array(vertices)
    normal = np.ones(3) / np.sqrt(3)
    basis_u = np.array([1.0, -1.0, 0.0]) / np.sqrt(2)
    basis_v = np.cross(normal, basis_u)
    offsets = vertices - vertices.mean(axis=0)
    angles = np.arctan2(offsets @ basis_v, offsets @ basis_u)
    return vertices[np.argsort(angles)]


def hexagon_vertices() -> np.ndarray:
    """Return the central section, retained for existing callers."""
    return section_vertices(0.5)


def rgb_colors(points: np.ndarray) -> list[str]:
    """Convert normalized coordinates to CSS colors."""
    return [f"rgb({r},{g},{b})" for r, g, b in np.rint(points * 255).astype(int)]


def section_traces(t: float, size: float) -> list:
    """Use explicit fan triangles and vertex RGB colors for the planar surface."""
    vertices = section_vertices(t)
    count = len(vertices)
    center = np.full(3, t)
    surface = np.vstack((center, vertices))
    scaled = surface * size
    # Explicit connectivity avoids automatic triangulation of a coplanar mesh.
    triangles = [(0, index + 1, (index + 1) % count + 1)
                 for index in range(count)] if count >= 3 else []
    mesh = go.Mesh3d(
        x=scaled[:, 0], y=scaled[:, 1], z=scaled[:, 2],
        i=[face[0] for face in triangles], j=[face[1] for face in triangles],
        k=[face[2] for face in triangles], vertexcolor=rgb_colors(surface),
        opacity=0.45, lighting=dict(ambient=1, diffuse=0, specular=0),
        hoverinfo="skip", showlegend=False, name="Cross-section",
    )
    boundary = np.vstack((vertices, vertices[0])) * size
    edges = go.Scatter3d(
        x=boundary[:, 0], y=boundary[:, 1], z=boundary[:, 2],
        mode="lines", line=dict(color="#333333", width=6),
        hoverinfo="skip", showlegend=False,
    )
    scaled_vertices = vertices * size
    corners = go.Scatter3d(
        x=scaled_vertices[:, 0], y=scaled_vertices[:, 1], z=scaled_vertices[:, 2],
        mode="markers", marker=dict(size=7, color=rgb_colors(vertices)),
        text=[f"({r:.6g}, {g:.6g}, {b:.6g})" for r, g, b in vertices],
        hovertemplate="RGB %{text}<extra></extra>", showlegend=False,
    )
    position = go.Scatter3d(
        x=[t * size], y=[t * size], z=[t * size], mode="markers+text",
        marker=dict(size=9, color=rgb_colors(center[None, :]),
                    line=dict(color="#333333", width=2)),
        text=[f"t = {t:.6g}"], textposition="bottom center",
        hoverinfo="text", showlegend=False,
    )
    # Keep spokes in one trace, separated by missing values.
    spokes = np.array([point for vertex in vertices
                       for point in (center * size, vertex * size, [np.nan] * 3)])
    return [mesh, edges, corners, position, go.Scatter3d(
        x=spokes[:, 0], y=spokes[:, 1], z=spokes[:, 2], mode="lines",
        line=dict(color="#888888", width=2), hoverinfo="skip", showlegend=False,
    )]


def section_annotation(t: float) -> dict:
    vertices = section_vertices(t)
    kind = {1: "Point", 3: "Triangle", 6: "Hexagon"}[len(vertices)]
    coordinates = "<br>".join(
        f"({r:.6g}, {g:.6g}, {b:.6g})" for r, g, b in vertices)
    return dict(
        x=1.01, y=1, xref="paper", yref="paper", xanchor="left", yanchor="top",
        showarrow=False, align="left",
        text=f"t = {t:.6g}<br>R + G + B = {3 * t:.6g}<br>{kind}<br>"
             f"Normalized vertices:<br>{coordinates}",
    )


def make_cube(samples: int = 18, size: float = 1.0) -> go.Figure:
    """Build a point cloud spanning RGB space, including its boundaries.

    Rendering cost grows cubically: samples=20 means 20³ = 8,000 points.
    """
    if samples < 2 or not np.isfinite(size) or size <= 0:
        raise ValueError("samples must be >= 2 and size must be positive")

    points = generate_rgb_points(samples) * size
    rgb = np.rint(points / size * 255).astype(int)
    colors = [f"rgb({red},{green},{blue})" for red, green, blue in rgb]

    fig = go.Figure(go.Scatter3d(
        x=points[:, 0], y=points[:, 1], z=points[:, 2],
        mode="markers",
        marker=dict(size=3, color=colors, opacity=0.8),
        text=[f"RGB({red}, {green}, {blue})" for red, green, blue in rgb],
        hovertemplate="%{text}<extra></extra>",
    ))
    # The achromatic axis has R = G = B: black (0,0,0) to white (1,1,1).
    # Numeric line colors give the diagonal a grayscale gradient.
    diagonal = grayscale_diagonal()
    fig.add_trace(go.Scatter3d(
        x=diagonal[:, 0] * size, y=diagonal[:, 1] * size,
        z=diagonal[:, 2] * size, mode="lines",
        line=dict(color=diagonal[:, 0], colorscale="Greys",
                  reversescale=True, cmin=0, cmax=1, width=11),
        hoverinfo="skip", showlegend=False,
    ))

    # Give the vector an arrowhead at its white endpoint.
    # The cone points in direction (+R, +G, +B).
    fig.add_trace(go.Cone(
        x=[size], y=[size], z=[size],
        u=[1], v=[1], w=[1],
        anchor="tip", sizemode="absolute", sizeref=0.15 * size,
        colorscale=[[0, "#f0f0f0"], [1, "#f0f0f0"]],
        showscale=False, hovertemplate="White (255, 255, 255)<extra></extra>",
        name="Black → white vector",
    ))
    fig.add_trace(go.Scatter3d(
        x=[0, size], y=[0, size], z=[0, size],
        mode="markers+text",
        marker=dict(size=7, color=["black", "white"],
                    line=dict(color="#888888", width=2)),
        text=["Black (0,0,0)", "White (255,255,255)"],
        textposition="top center",
        hoverinfo="text",
        showlegend=False,
    ))

    # Only these five lightweight traces are replaced by the slider.
    section_indices = list(range(len(fig.data), len(fig.data) + 5))
    fig.add_traces(section_traces(0.5, size))
    # Include both exact transitions alongside 0.01-spaced positions.
    positions = sorted(set(np.linspace(0, 1, 101)) | {1 / 3, 2 / 3})
    steps = []
    frames = []
    for t in positions:
        name = str(t)
        frames.append(go.Frame(
            name=name, data=section_traces(t, size), traces=section_indices,
            layout=dict(annotations=[section_annotation(t)]),
        ))
        steps.append(dict(
            label=f"{t:.6g}", method="animate",
            args=[[name], dict(mode="immediate", transition=dict(duration=0),
                              frame=dict(duration=0, redraw=True))],
        ))

    fig.frames = frames
    fig.update_layout(
        title=f"RGB cube with movable perpendicular cross-section ({samples}³ points)",
        uirevision="rgb-cube",
        annotations=[section_annotation(0.5)],
        sliders=[dict(active=positions.index(0.5), steps=steps,
                      currentvalue=dict(prefix="t = "), pad=dict(t=30))],
        scene=dict(
            xaxis=dict(title="Red", range=[0, size]),
            yaxis=dict(title="Green", range=[0, size]),
            zaxis=dict(title="Blue", range=[0, size]),
            uirevision="rgb-cube-camera",
            aspectmode="cube",
            dragmode="turntable",
        ),
        margin=dict(l=0, r=260, b=100, t=45),
    )
    return fig


def write_laboratory(output: Path, samples: int = 18) -> None:
    """Export the browser laboratory as one portable, offline HTML file."""
    if not 3 <= samples <= 30:
        raise ValueError("laboratory samples must be between 3 and 30")
    assets = Path(__file__).parent / "docs"
    html = (assets / "index.html").read_text()
    html = html.replace('id="resolution-value">18', f'id="resolution-value">{samples}')
    html = html.replace('value="18" step="1"', f'value="{samples}" step="1"')
    html = html.replace('<link rel="stylesheet" href="style.css">',
                        f"<style>{(assets / 'style.css').read_text()}</style>")
    scripts = {"plotly.min.js": get_plotlyjs(),
               "color-space.js": (assets / "color-space.js").read_text(),
               "lab.js": (assets / "lab.js").read_text()}
    # Inline scripts after the DOM so the same code works offline and on Pages.
    for name in scripts:
        html = html.replace(f'<script defer src="{name}"></script>', '')
    inline = ''.join('<script>' + code.replace('</script', '<\\/script') + '</script>'
                     for code in scripts.values())
    output.write_text(html.replace('</body>', inline + '</body>'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=18,
                        help="Points per color channel (total = samples³)")
    parser.add_argument("--size", type=float, default=1.0,
                        help="Geometric size of each cube edge in --legacy mode")
    parser.add_argument("--output", type=Path, default=Path("rgb_cube.html"))
    parser.add_argument("--no-open", action="store_true",
                        help="Write HTML without opening a browser")
    parser.add_argument("--legacy", action="store_true",
                        help="Show the original perpendicular-plane RGB explorer")
    args = parser.parse_args()

    if args.legacy:
        figure = make_cube(args.samples, args.size)
        figure.write_html(str(args.output), auto_open=not args.no_open)
    else:
        write_laboratory(args.output, args.samples)
        if not args.no_open:
            webbrowser.open(args.output.resolve().as_uri())
    print(f"Saved interactive visualization to {args.output}")


if __name__ == "__main__":
    main()
