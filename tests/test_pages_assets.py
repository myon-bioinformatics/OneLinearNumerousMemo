"""Check the Pages artifact, not paths in the full repository checkout."""
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Icons(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') == 'icon':
            self.hrefs.append(attrs['href'])


class PagesAssetsTests(unittest.TestCase):
    def test_deployed_icons_resolve_to_canonical_bytes(self):
        workflow = (ROOT / '.github/workflows/pages.yml').read_text()
        self.assertIn('path: docs', workflow)
        match = re.search(r'- name: Stage Pages brand assets\n        run: \|\n((?:          [^\n]+\n)+)', workflow)
        self.assertIsNotNone(match)
        commands = '\n'.join(line[10:] for line in match.group(1).splitlines())
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            shutil.copytree(ROOT / 'docs', stage / 'docs')
            shutil.copytree(ROOT / 'assets/brand', stage / 'assets/brand')
            subprocess.run(['sh', '-eu', '-c', commands], cwd=stage, check=True)
            icons = Icons()
            icons.feed((stage / 'docs/index.html').read_text())
            self.assertEqual(len(icons.hrefs), 2)
            for base in ('https://example.test/', 'https://example.test/OneLinearNumerousMemo/'):
                for href in icons.hrefs:
                    with self.subTest(base=base, href=href):
                        resolved = urljoin(base, href)
                        self.assertTrue(resolved.startswith(base))
                        relative = urlsplit(resolved).path[len(urlsplit(base).path):]
                        deployed = stage / 'docs' / relative
                        self.assertEqual(deployed.read_bytes(), (ROOT / 'assets/brand' / Path(relative).name).read_bytes())


if __name__ == '__main__':
    unittest.main()
