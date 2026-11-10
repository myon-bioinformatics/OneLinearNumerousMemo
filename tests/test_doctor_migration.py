import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class DoctorMigrationTest(unittest.TestCase):
    def test_reports_running_and_uv_managed_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            uv = home / 'uv'
            uv.write_text('#!/bin/sh\nif [ "$1 $2" = "python list" ]; then printf "cpython-3.12.7 /managed/python\\n"; fi\n')
            uv.chmod(0o755)
            node = home / 'node'
            node.write_text('#!/bin/sh\nprintf "v26.0.0\\n"\n')
            node.chmod(0o755)
            env = dict(os.environ, HOME=tmp, PATH=tmp, OLNM_HOME=str(home / 'state'), DIAL_FILE=str(home / 'dial'))
            source = Path(__file__).resolve().parents[1] / 'olnm.py'
            result = subprocess.run([sys.executable, str(source), 'doctor'], env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Python running olnm: ' + sys.version.split()[0], result.stdout)
            self.assertIn('python3 on PATH: not found', result.stdout)
            self.assertIn('cpython-3.12.7 /managed/python', result.stdout)
            self.assertIn('node: v26.0.0 (' + str(node) + ')', result.stdout)
            self.assertIn('bun: not found on PATH', result.stdout)

    def test_uv_tool_registration_changes_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            uv = home / 'uv'
            uv.write_text('#!/bin/sh\nprintf "one-linear-numerous-memo v0.1.0\\n"\n')
            uv.chmod(0o755)
            env = dict(os.environ, HOME=tmp, PATH=tmp, OLNM_HOME=str(home / 'state'),
                       DIAL_FILE=str(home / 'dial'))
            source = Path(__file__).resolve().parents[1] / 'olnm.py'
            result = subprocess.run([sys.executable, str(source), 'doctor'], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('uv tool upgrade one-linear-numerous-memo', result.stdout)
            self.assertNotIn('uv tool install --force', result.stdout)

    def test_detects_old_settings_without_disclosure_or_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            startup = home / '.bashrc'
            original = '# olnm comment\nexport OLNM_URL=secret-value\neval "$(python3 ~/.olnm.py init)"\n'
            startup.write_text(original)
            (home / '.olnm.py').write_text('old file')
            env = dict(os.environ, HOME=tmp, OLNM_HOME=str(home / 'state'),
                       DIAL_FILE=str(home / 'dial'), OLNM_URL='another-secret')
            source = Path(__file__).resolve().parents[1] / 'olnm.py'
            result = subprocess.run([sys.executable, str(source), 'doctor'], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('.bashrc:2', result.stdout)
            self.assertIn('.bashrc:3', result.stdout)
            self.assertNotIn('.bashrc:1 ', result.stdout)
            self.assertIn('OLNM_URL', result.stdout)
            self.assertIn('.olnm.py', result.stdout)
            self.assertNotIn('secret-value', result.stdout)
            self.assertNotIn('another-secret', result.stdout)
            self.assertEqual(startup.read_text(), original)
            self.assertTrue((home / '.olnm.py').exists())
