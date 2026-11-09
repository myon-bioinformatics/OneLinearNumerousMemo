"""🧪 olnm tests — `python -m unittest discover`."""
import json, os, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="olnm-"))
os.environ["DIAL_FILE"] = str(TMP / "dial")
sys.path.insert(0, str(ROOT))
import olnm  # noqa: E402

PY = str(ROOT / "olnm.py")


def bash(script: str, path_extra: str = "") -> subprocess.CompletedProcess:
    env = dict(os.environ, PATH=f"{path_extra}:{os.environ['PATH']}" if path_extra else os.environ["PATH"])
    return subprocess.run(["bash", "-c", f'eval "$(python3 {PY} init bash)"\n{script}'], text=True, capture_output=True, env=env)


class TestStructure(unittest.TestCase):
    def test_init_is_valid_bash(self):
        code = subprocess.run([sys.executable, PY, "init", "bash"], text=True, capture_output=True, check=True).stdout
        self.assertEqual(subprocess.run(["bash", "-n"], input=code, text=True).returncode, 0)

    def test_every_help_line_defines_a_function_and_names_are_unique(self):
        r = bash('for f in $(python3 "$OLNM_PY" call names | tr -d \'[]",\'); do declare -F "$f" >/dev/null || echo "MISSING $f"; done')
        self.assertNotIn("MISSING", r.stdout + r.stderr)
        defined = re.findall(r"^([A-Za-z_0-9]+)\(\)", olnm.META + olnm.SHELL, re.M)
        self.assertEqual(len(defined), len(set(defined)))

    def test_sections_and_marks(self):
        self.assertEqual(olnm._sections()[:3], ["meta", "uv", "python"])
        net = {e["name"] for e in olnm.entries() if e["net"]}
        self.assertIn("myip", net)
        self.assertNotIn("ghpr", net)   # 🎛️ routed, never stubbed
        self.assertNotIn("gp", net)     # origin follows the dial


class TestHelpers(unittest.TestCase):
    def test_like_and_grep(self):
        self.assertEqual(olnm.like("uvtets")[0], "uvtest")
        self.assertTrue(olnm.like("hash"))
        self.assertEqual(olnm.like("zzzzqqq"), [])
        self.assertTrue(all("json" in (e["name"] + e["desc"]).lower() for e in olnm.grep("json")))

    def test_command_not_found_hint(self):
        r = bash("uvtets")
        self.assertEqual(r.returncode, 127)
        self.assertIn("did you mean: uvtest", r.stderr)

    def test_one_liners_work(self):
        cases = {"pycalc '2**10'": "1024", "ncalc '2**10'": "1024", "printf '1\\n2\\n' | nums": "n=2 sum=3 avg=1.5 min=1 max=2",
                 "echo 'x a@b.co 10.0.0.1' | redact": "x <email> <ip>", "printf 'x=1\\n' | t2j | tr -d ' \\n'": '{"x":1}'}
        for cmd, want in cases.items():
            with self.subTest(cmd):
                self.assertEqual(bash(cmd).stdout.strip(), want)

    def test_hashdir_verifydir(self):
        d = TMP / "hd"; d.mkdir(exist_ok=True); (d / "a").write_text("hi")
        self.assertIn("✅", bash(f"hashdir {d} >/dev/null && verifydir {d}").stdout)


class TestDial(unittest.TestCase):
    def setUp(self):
        olnm.DIAL_FILE.unlink(missing_ok=True)

    def test_default_dial_is_3_and_net_allowed(self):
        self.assertEqual(olnm.read_dial(), 3)
        self.assertNotIn("needs dial", bash("declare -f myip").stdout)

    def test_dial_0_stubs_net_one_liners(self):
        olnm.dial(0)
        r = bash("myip; echo rc=$?")
        self.assertIn("needs dial ≥2", r.stderr); self.assertIn("rc=1", r.stdout)
        self.assertEqual(bash("pycalc 1+1").stdout.strip(), "2")  # offline ones untouched
        olnm.dial(2)
        self.assertNotIn("needs dial", bash("declare -f myip").stdout)

    def test_gh_routes_to_hubdial_at_dial_le_2(self):
        fake = TMP / "bin"; fake.mkdir(exist_ok=True)
        (fake / "hubdial").write_text('#!/bin/sh\necho "HUBDIAL $*"\n'); (fake / "hubdial").chmod(0o755)
        olnm.DIAL_FILE.write_text("1\n")
        self.assertEqual(bash("ghisn crash bug", str(fake)).stdout.strip(), "HUBDIAL issue new crash --label bug")
        self.assertEqual(bash("ghprs", str(fake)).stdout.strip(), "HUBDIAL pr ls")
        olnm.DIAL_FILE.write_text("3\n")
        self.assertEqual(bash("_olnm_hub && echo HUBDIAL || echo GH", str(fake)).stdout.strip(), "GH")


class TestInterop(unittest.TestCase):
    def test_cli_call_json(self):
        out = subprocess.run([sys.executable, PY, "call", "like", '["uvtets"]'], text=True, capture_output=True, check=True).stdout
        self.assertEqual(json.loads(out)[0], "uvtest")

    def test_node_and_bun_run(self):
        js = 'const {execFileSync}=require("child_process");process.stdout.write(execFileSync("python3",[process.argv[1],"run","pycalc","6*7"]).toString())'
        for rt in ("node", "bun"):
            if shutil.which(rt):
                with self.subTest(rt):
                    self.assertEqual(subprocess.run([rt, "-e", js, PY], text=True, capture_output=True, check=True).stdout.strip(), "42")


if __name__ == "__main__":
    unittest.main()
