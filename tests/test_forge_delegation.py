"""🏠 The local forge lives in NagoyAction: olnm hands `hub` (and a dial move with a forge) to `nagoyaction hub`."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE = "#!{py}\nimport json,sys\nfrom pathlib import Path\nPath({log!r}).write_text(json.dumps(sys.argv[1:]))\nsys.exit(7)\n"


class ForgeDelegationTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.log = self.root / "arguments.json"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "nagoyaction"
        fake.write_text(FAKE.format(py=sys.executable, log=str(self.log)))
        fake.chmod(0o755)
        self.home = self.root / "state"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        OLNM_HOME=str(self.home), DIAL_FILE=str(self.home / "dial"))
        self.env.pop("NAGOYACTION", None)

    def olnm(self, *args, **env):
        return subprocess.run([sys.executable, str(ROOT / "olnm.py"), *args], env=dict(self.env, **env),
                              text=True, capture_output=True)

    def forwarded(self):
        return json.loads(self.log.read_text())

    def with_forge(self, port=3123):
        (self.home / "forge").mkdir(parents=True)
        (self.home / "forge" / "state.json").write_text(json.dumps({"port": port}))

    def test_hub_forwards_exact_arguments_and_exit_code(self):
        result = self.olnm("hub", "issue", "new", "title with spaces", "--body", "line one")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(self.forwarded(), ["hub", "issue", "new", "title with spaces", "--body", "line one"])
        self.assertEqual(self.olnm("hub", "--help").returncode, 7)
        self.assertEqual(self.forwarded(), ["hub", "--help"])

    def test_dial_with_a_forge_is_moved_by_nagoyaction(self):
        self.with_forge()
        result = self.olnm("dial", "mirror")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(self.forwarded(), ["hub", "dial", "2"])
        self.assertFalse((self.home / "dial").exists())  # NagoyAction writes it after moving the origins

    def test_dial_without_a_forge_stays_in_olnm(self):
        result = self.olnm("dial", "local")
        self.assertEqual(result.stdout, "🎛️  → 🏠 local (1)  🌍 one-liners stubbed\n")
        self.assertEqual((self.home / "dial").read_text(), "1\n")
        self.assertFalse(self.log.exists())

    def test_nagoyaction_py_checkout_can_be_named(self):
        script = self.root / "nagoyaction.py"
        script.write_text(FAKE.format(py=sys.executable, log=str(self.log)))
        result = self.olnm("hub", "status", NAGOYACTION=str(script), PATH="/usr/bin:/bin")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(self.forwarded(), ["hub", "status"])

    def test_carried_local_forge_py_takes_sub_directly(self):
        # `hub bundle` carries local_forge.py into a closed network; it has no `forge` subcommand.
        script = self.root / "carry" / "local_forge.py"
        script.parent.mkdir()
        script.write_text(FAKE.format(py=sys.executable, log=str(self.log)))
        result = self.olnm("hub", "repo", "ls", NAGOYACTION=str(script), PATH="/usr/bin:/bin")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(self.forwarded(), ["repo", "ls"])

    def test_missing_nagoyaction_explains_how_to_install(self):
        result = self.olnm("hub", "status", PATH="/usr/bin:/bin")
        self.assertEqual(result.returncode, 127)
        self.assertIn("nagoyaction hub", result.stderr)
        self.assertIn("uv tool install", result.stderr)
        self.with_forge()
        (self.home / "dial").write_text("3\n")
        result = self.olnm("dial", "offline", PATH="/usr/bin:/bin")
        self.assertEqual(result.returncode, 127)
        self.assertIn("dial unchanged", result.stderr)
        self.assertEqual((self.home / "dial").read_text(), "3\n")

    def test_shell_routes_gh_one_liners_to_the_forge_at_mirror_and_below(self):
        self.with_forge()
        (self.home / "dial").write_text("2\n")
        (self.bin / "xdg-open").write_text("#!/bin/sh\nexit 1\n")  # no browser here: hubopen prints the URL
        (self.bin / "xdg-open").chmod(0o755)
        script = f'eval "$(python3 {ROOT / "olnm.py"} init bash)"\nghisn crash bug; echo "rc=$?"; hubopen'
        result = subprocess.run(["bash", "-c", script], env=self.env, text=True, capture_output=True)
        self.assertIn("rc=7", result.stdout, result.stderr)
        self.assertEqual(self.forwarded(), ["hub", "issue", "new", "crash", "--label", "bug"])
        self.assertIn("http://localhost:3123/", result.stdout)
        (self.home / "dial").write_text("3\n")
        result = subprocess.run(["bash", "-c", f'eval "$(python3 {ROOT / "olnm.py"} init bash)"\n_olnm_hub && echo HUB || echo GH'],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.stdout.strip(), "GH")


if __name__ == "__main__":
    unittest.main()
