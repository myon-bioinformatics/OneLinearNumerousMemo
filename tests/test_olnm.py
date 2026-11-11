"""🧪 olnm tests — `python -m unittest discover`."""
import json, os, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="olnm-"))
os.environ.update(OLNM_HOME=str(TMP / "home"), DIAL_FILE=str(TMP / "dial"), GIT_CONFIG_GLOBAL=str(TMP / "gitconfig"))
sys.path.insert(0, str(ROOT))
import olnm  # noqa: E402

PY = str(ROOT / "olnm.py")


def reset_forge():
    shutil.rmtree(olnm.FORGE_STATE.parent, ignore_errors=True)
    olnm.DIAL_FILE.unlink(missing_ok=True)


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
        cases = {"calc '2**10'": "1024", "calc --engine node '2**10'": "1024", "printf '1\\n2\\n' | nums": "n=2 sum=3 avg=1.5 min=1 max=2",
                 "echo 'x a@b.co 10.0.0.1' | redact": "x <email> <ip>", "printf 'x=1\\n' | t2j | tr -d ' \\n'": '{"x":1}'}
        for cmd, want in cases.items():
            with self.subTest(cmd):
                self.assertEqual(bash(cmd).stdout.strip(), want)

    def test_hashdir_verifydir(self):
        d = TMP / "hd"; d.mkdir(exist_ok=True); (d / "a").write_text("hi")
        self.assertIn("✅", bash(f"hashdir {d} >/dev/null && verifydir {d}").stdout)


class TestDial(unittest.TestCase):
    def setUp(self):
        reset_forge()

    def test_default_dial_is_3_and_net_allowed(self):
        self.assertEqual(olnm.read_dial(), 3)
        self.assertNotIn("needs dial", bash("declare -f myip").stdout)

    def test_dial_0_stubs_net_one_liners(self):
        olnm.dial(0)
        r = bash("myip; echo rc=$?")
        self.assertIn("needs dial mirror or github (now 🔌 offline)", r.stderr); self.assertIn("rc=1", r.stdout)
        self.assertEqual(bash("calc 1+1").stdout.strip(), "2")  # offline ones untouched
        olnm.dial(2)
        self.assertNotIn("needs dial", bash("declare -f myip").stdout)

    def test_names_are_accepted_and_shown_first_but_the_file_keeps_the_digit(self):
        for given, level in (("offline", 0), ("Local", 1), ("mirror", 2), ("github", 3), ("2", 2), (1, 1)):
            with self.subTest(given=given):
                self.assertEqual(olnm.dial_level(given), level)
        for bad in ("4", "mirorr", "", True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                olnm.dial_level(bad)
        self.assertEqual(olnm.dial("mirror"), 2)
        self.assertEqual(olnm.DIAL_FILE.read_text(), "2\n")
        self.assertEqual(olnm.dial_label(2), "🔁 mirror (2)")
        with self.assertRaises(SystemExit):
            olnm.dial("mirorr")
        self.assertEqual(olnm.read_dial(), 2)

    def test_cli_dial_names_and_typo_hint(self):
        env = dict(os.environ)
        r = subprocess.run([sys.executable, PY, "dial", "offline"], text=True, capture_output=True, env=env)
        self.assertEqual(r.stdout, "🎛️  → 🔌 offline (0)  🌍 one-liners stubbed\n")
        r = subprocess.run([sys.executable, PY, "dial", "mirorr"], text=True, capture_output=True, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("did you mean: mirror", r.stderr)
        self.assertEqual(olnm.DIAL_FILE.read_text(), "0\n")

    def test_existing_forge_without_nagoyaction_refuses_to_move_the_dial(self):
        # Origins follow the dial; changing only the file would leave pushes going to the old place.
        olnm.FORGE_STATE.parent.mkdir(parents=True); olnm.FORGE_STATE.write_text('{"port": 3123}')
        olnm._write_dial(3)
        with mock.patch.object(olnm, "_nagoyaction", return_value=None), self.assertRaises(SystemExit) as e:
            olnm.dial("offline")
        self.assertEqual(e.exception.code, 127)
        self.assertEqual(olnm.read_dial(), 3)
        self.assertEqual(olnm.hub_url(), "http://localhost:3123/")

    def test_cli_parser(self):
        ap = olnm.build_parser()
        self.assertEqual(ap.parse_args(["dial", "mirror"]).level, "mirror")
        self.assertEqual(ap.parse_args(["hub", "issue", "new", "t", "--label", "bug"]).args, ["new", "t", "--label", "bug"])
        for bad in (["dial", "9"], ["hub"], ["hub", "isue"]):
            with self.assertRaises(SystemExit):
                ap.parse_args(bad)


class TestInterop(unittest.TestCase):
    def test_call_rejects_private(self):
        for name in ("_forge", "main", "nope"):
            with self.assertRaises(SystemExit):
                olnm.call(name)

    def test_cli_call_json(self):
        out = subprocess.run([sys.executable, PY, "call", "like", '["uvtets"]'], text=True, capture_output=True, check=True).stdout
        self.assertEqual(json.loads(out)[0], "uvtest")

    def test_node_and_bun_run(self):
        js = 'const {execFileSync}=require("child_process");process.stdout.write(execFileSync("python3",[process.argv[1],"run","calc","6*7"]).toString())'
        for rt in ("node", "bun"):
            if shutil.which(rt):
                with self.subTest(rt):
                    self.assertEqual(subprocess.run([rt, "-e", js, PY], text=True, capture_output=True, check=True).stdout.strip(), "42")


if __name__ == "__main__":
    unittest.main()
