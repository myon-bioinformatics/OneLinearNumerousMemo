import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class DoctorMigrationTest(unittest.TestCase):
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
