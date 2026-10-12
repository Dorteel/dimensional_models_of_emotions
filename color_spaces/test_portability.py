"""Check local static assets and execute exports from an isolated source copy."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and "src" in attrs:
            self.urls.append(attrs["src"])
        elif tag == "link" and "href" in attrs:
            self.urls.append(attrs["href"])


class PortabilityTests(unittest.TestCase):
    def test_static_assets_are_local(self):
        for page in (ROOT / "docs/index.html",
                     ROOT / "emotional_color_space/index.html"):
            with self.subTest(page=page):
                parser = AssetParser()
                parser.feed(page.read_text())
                self.assertTrue(parser.urls)
                for url in parser.urls:
                    if url.startswith("data:"):
                        continue
                    parts = urlsplit(url)
                    self.assertFalse(parts.scheme or parts.netloc, url)
                    asset = (page.parent / parts.path).resolve()
                    self.assertTrue(asset.is_relative_to(ROOT), url)
                    self.assertTrue(asset.is_file(), url)

    def test_exports_from_extracted_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            extracted = Path(directory) / "experiments"
            shutil.copytree(ROOT, extracted, ignore=shutil.ignore_patterns(
                ".venv", "__pycache__", "rgb_cube.html"))
            for legacy in (False, True):
                with self.subTest(legacy=legacy):
                    output = "legacy.html" if legacy else "laboratory.html"
                    command = [sys.executable, "rgb_cube_hexagon.py", "--no-open",
                               "--samples", "3", "--output", output]
                    if legacy:
                        command.append("--legacy")
                    result = subprocess.run(command, cwd=extracted, check=True,
                                            capture_output=True, text=True, timeout=60)
                    self.assertIn(output, result.stdout)
                    html = (extracted / output).read_text()
                    self.assertIn("plotly", html.lower())
                    parser = AssetParser()
                    parser.feed(html)
                    self.assertEqual(parser.urls, [url for url in parser.urls
                                                  if url.startswith("data:")])
                    self.assertIn("RGB cube" if legacy else 'id="hsl"', html)


if __name__ == "__main__":
    unittest.main()
