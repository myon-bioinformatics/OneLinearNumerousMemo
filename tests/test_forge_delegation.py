import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ForgeDelegationTest(unittest.TestCase):
    def test_hub_and_active_dial_forward_exact_arguments_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            forge = root / "local-forge"
            log = root / "arguments.json"
            forge.write_text(f"#!{sys.executable}\nimport json,sys\nfrom pathlib import Path\nPath({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\nsys.exit(7)\n")
            forge.chmod(0o755)
            home = root / "state"
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                       OLNM_HOME=str(home), DIAL_FILE=str(home / "dial"))
            cmd = [sys.executable, str(ROOT / "olnm.py")]
            result = subprocess.run([*cmd, "hub", "issue", "new", "title with spaces", "--body", "line one"],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(json.loads(log.read_text()), ["issue", "new", "title with spaces", "--body", "line one"])
            (home / "forge").mkdir(parents=True)
            (home / "forge" / "state.json").write_text("{}")
            result = subprocess.run([*cmd, "dial", "2"], env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(json.loads(log.read_text()), ["dial", "2"])
            self.assertFalse((home / "dial").exists())
