"""Geometry and headless figure checks using the standard library runner."""
import unittest
import tempfile
from pathlib import Path

import numpy as np

from rgb_cube_hexagon import (
    generate_rgb_points, grayscale_diagonal, hexagon_vertices, make_cube, section_vertices, section_traces,
    write_laboratory,
)


class GeometryTests(unittest.TestCase):
    def test_offline_laboratory_export(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "lab.html"
            write_laboratory(output, samples=12)
            html = output.read_text()
            self.assertIn('id="resolution-value">12', html)
            self.assertIn('value="12" step="1"', html)
            self.assertIn('id="rgb"', html)
            self.assertIn('id="hsl"', html)
            self.assertNotIn('<script defer src=', html)
            self.assertNotIn('href="style.css"', html)
            self.assertGreater(html.index('initialize();'), html.index('id="rgb"'))
        with self.assertRaises(ValueError):
            write_laboratory(Path('unused.html'), samples=31)

    def test_section_types_and_transitions(self):
        for t, count in ((0, 1), (0.2, 3), (1 / 3, 3), (0.5, 6),
                         (2 / 3, 3), (0.8, 3), (1, 1),
                         (1 / 3 - 1e-8, 3), (1 / 3 + 1e-8, 6),
                         (2 / 3 - 1e-8, 6), (2 / 3 + 1e-8, 3)):
            with self.subTest(t=t):
                self.assertEqual(len(section_vertices(t)), count)

    def test_all_section_vertices_and_order(self):
        positions = list(np.linspace(0, 1, 101)) + [1 / 3, 2 / 3]
        for t in positions:
            with self.subTest(t=t):
                vertices = section_vertices(t)
                self.assertEqual(len(np.unique(vertices, axis=0)), len(vertices))
                self.assertTrue(np.all((vertices >= 0) & (vertices <= 1)))
                np.testing.assert_allclose(vertices.sum(axis=1), 3 * t, atol=1e-14)
                np.testing.assert_allclose(vertices.mean(axis=0), [t] * 3, atol=1e-14)
                if len(vertices) > 1:
                    edges = np.roll(vertices, -1, axis=0) - vertices
                    turns = np.cross(edges, np.roll(edges, -1, axis=0)) @ np.ones(3)
                    self.assertTrue(np.all(turns > 0))

    def test_invalid_section_positions(self):
        for t in (-0.1, 1.1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                section_vertices(t)

    def test_section_mesh_connectivity(self):
        for t in (0, 0.2, 1 / 3, 0.5, 2 / 3, 0.8, 1):
            vertices = section_vertices(t)
            mesh = section_traces(t, 2)[0]
            self.assertEqual(len(mesh.i), len(vertices) if len(vertices) > 1 else 0)
            for i, j, k in zip(mesh.i, mesh.j, mesh.k):
                self.assertEqual(i, 0)
                self.assertTrue(1 <= j <= len(vertices))
                self.assertTrue(1 <= k <= len(vertices))
                points = np.column_stack((mesh.x, mesh.y, mesh.z))
                self.assertGreater(np.cross(points[j] - points[i],
                                            points[k] - points[i]) @ np.ones(3), 0)

    def test_slider_updates_only_section(self):
        figure = make_cube(samples=2)
        self.assertEqual(len(figure.frames), 103)
        self.assertEqual(figure.layout.scene.uirevision, 'rgb-cube-camera')
        for frame in figure.frames:
            self.assertEqual(tuple(frame.traces), (4, 5, 6, 7, 8))
            self.assertEqual(len(frame.data), 5)
            self.assertIn('Normalized vertices', frame.layout.annotations[0].text)
        names = {frame.name for frame in figure.frames}
        self.assertIn(str(1 / 3), names)
        self.assertIn(str(2 / 3), names)
        self.assertTrue(all(step.args[0][0] in names
                            for step in figure.layout.sliders[0].steps))

    def test_six_unique_vertices(self):
        self.assertEqual(len(np.unique(hexagon_vertices(), axis=0)), 6)

    def test_vertices_within_cube(self):
        vertices = hexagon_vertices()
        self.assertTrue(np.all((vertices >= 0) & (vertices <= 1)))

    def test_vertices_on_plane(self):
        np.testing.assert_allclose(hexagon_vertices().sum(axis=1), 1.5)

    def test_vertex_permutations(self):
        for vertex in hexagon_vertices():
            np.testing.assert_array_equal(np.sort(vertex), [0, 0.5, 1])

    def test_cyclic_order(self):
        vertices = hexagon_vertices()
        edges = np.roll(vertices, -1, axis=0) - vertices
        np.testing.assert_allclose(np.linalg.norm(edges, axis=1), np.sqrt(0.5))
        turns = np.cross(edges, np.roll(edges, -1, axis=0)) @ np.ones(3)
        self.assertTrue(np.all(turns > 0) or np.all(turns < 0))

    def test_grayscale_diagonal(self):
        points = grayscale_diagonal()
        np.testing.assert_array_equal(points[0], [0, 0, 0])
        np.testing.assert_array_equal(points[-1], [1, 1, 1])
        np.testing.assert_array_equal(points[:, 0], points[:, 1])
        np.testing.assert_array_equal(points[:, 1], points[:, 2])

    def test_resolution(self):
        for samples in (2, 3, 18, 30):
            with self.subTest(samples=samples):
                points = generate_rgb_points(samples)
                self.assertEqual(points.shape, (samples ** 3, 3))
                np.testing.assert_allclose(
                    np.unique(points[:, 0]), np.linspace(0, 1, samples))

    def test_invalid_parameters(self):
        for size in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                make_cube(size=size)
        for function in (generate_rgb_points, grayscale_diagonal, make_cube):
            with self.assertRaises(ValueError):
                function(1)

    def test_figure_serialization_and_scaling(self):
        figure = make_cube(samples=3, size=2)
        self.assertEqual(len(figure.data[0].x), 27)
        self.assertEqual(max(figure.data[0].x), 2)
        self.assertIn('scatter3d', figure.to_json())
        self.assertIn('Plotly.newPlot', figure.to_html())


if __name__ == '__main__':
    unittest.main()
