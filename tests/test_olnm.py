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
PORT = 3777


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def reset_forge():
    olnm.hub_down()
    shutil.rmtree(olnm.FORGE, ignore_errors=True)
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
        reset_forge()

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

class HubBase(unittest.TestCase):
    def setUp(self):
        reset_forge()
        olnm.BIN.parent.mkdir(parents=True)
        shutil.copy(ROOT / "tests" / "fake_forgejo.py", olnm.BIN); olnm.BIN.chmod(0o755)
        self.wt = TMP / "wt"; shutil.rmtree(self.wt, ignore_errors=True); self.wt.mkdir()
        git("init", "-q", "-b", "main", cwd=self.wt)
        (self.wt / "a").write_text("a"); git("add", ".", cwd=self.wt)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init", cwd=self.wt)

    def tearDown(self):
        olnm.hub_down()


class TestHubInit(HubBase):
    def test_init_writes_ini_token_dial_and_git_auth(self):
        st = olnm.hub_init(port=PORT, password="pw")
        ini = olnm.INI.read_text()
        for line in (f"HTTP_PORT = {PORT}", "HTTP_ADDR = 127.0.0.1", "DISABLE_SSH = true", "OFFLINE_MODE = true", "DB_TYPE = sqlite3"):
            self.assertIn(line, ini)
        self.assertTrue(st["token"].startswith("fake-token"))
        self.assertEqual(oct(olnm.FSTATE.stat().st_mode)[-3:], "600")
        self.assertEqual(olnm.read_dial(), 1)
        self.assertIn("Authorization: Basic", git("config", "--global", f"http.http://localhost:{PORT}/.extraHeader", cwd=TMP))

    def test_up_down_idempotent(self):
        olnm.hub_init(port=PORT, password="pw")
        pid = olnm.hub_up(); self.assertTrue(olnm._running())
        self.assertEqual(olnm.hub_up(), pid)
        olnm.hub_down(); self.assertFalse(olnm._running())

    def test_install_from_carried_file_checks_sidecar(self):
        src = TMP / "forgejo-9.9.9-linux-amd64"; src.write_bytes(b"binary")
        side = TMP / "forgejo-9.9.9-linux-amd64.sha256"
        side.write_text("deadbeef  x\n")
        with self.assertRaises(SystemExit):
            olnm.hub_install(src=str(src))
        side.write_text(olnm._sha256(src) + "  x\n")
        olnm.hub_install(src=str(src)); self.assertEqual(olnm.BIN.read_bytes(), b"binary")


    def test_bundle_flavor_urls_and_sha_check(self):
        seen = []
        def fake_fetch(url, dest=None, timeout=0):
            seen.append(url)
            data = b"bin" if not url.endswith(".sha256") else (olnm.hashlib.sha256(b"bin").hexdigest() + "  x\n").encode()
            if dest:
                dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
            return data
        with mock.patch.object(olnm, "_fetch", fake_fetch):
            path = olnm.hub_bundle(str(TMP / "carry"), version="1.2.3", flavor="gitea")
        self.assertEqual(seen[0], "https://github.com/go-gitea/gitea/releases/download/v1.2.3/gitea-1.2.3-linux-amd64")
        self.assertEqual(path.name, "gitea-1.2.3-linux-amd64")
        self.assertTrue((TMP / "carry" / "olnm.py").exists())
        with mock.patch.object(olnm, "_fetch", lambda url, dest=None, timeout=0: b"bin" if not url.endswith(".sha256") else b"bad  x"):
            with self.assertRaises(SystemExit):
                olnm.hub_bundle(str(TMP / "carry2"), version="1.2.3")


    def test_latest_falls_back_to_verified(self):
        def blocked(*a, **k):
            raise olnm.urllib.error.URLError("blocked")
        with mock.patch.object(olnm, "_fetch", blocked), mock.patch.object(olnm, "_open", blocked):
            self.assertEqual(olnm._latest_version("gitea"), olnm.VERIFIED["gitea"])
            with self.assertRaises(SystemExit):
                olnm._latest_version("forgejo")

    def test_ini_pins_public_url(self):
        olnm.hub_init(port=PORT, password="pw")
        self.assertIn("PUBLIC_URL_DETECTION = legacy", olnm.INI.read_text())


class TestHub(HubBase):
    def setUp(self):
        super().setUp(); olnm.hub_init(port=PORT, password="pw"); olnm.hub_up()

    def test_repo_add_creates_forge_repo_and_remotes(self):
        olnm.hub_repo_add(str(self.wt), github="me/wt")
        self.assertEqual(set(git("remote", cwd=self.wt).split()), {"origin", "local", "bare", "github"})
        self.assertEqual([r["name"] for r in olnm.hub_api("GET", "/user/repos")], ["wt"])
        olnm.hub_repo_add(str(self.wt), github="me/wt")
        self.assertEqual(len(olnm.hub_api("GET", "/user/repos")), 1)

    def test_dial_moves_origin_and_forge(self):
        olnm.hub_repo_add(str(self.wt), github="me/wt")
        origin = lambda: git("remote", "get-url", "origin", cwd=self.wt)
        olnm.dial(0); self.assertEqual(origin(), str(olnm.BARE / "wt.git")); self.assertFalse(olnm._running())
        olnm.dial(1); self.assertIn(f"localhost:{PORT}/admin/wt.git", origin()); self.assertTrue(olnm._running())
        olnm.dial(3); self.assertEqual(origin(), "https://github.com/me/wt.git")
        self.assertEqual(olnm.read_dial(), 3)

    @mock.patch.object(olnm, "_github_token", return_value="ghtok")
    def test_dial2_push_mirror_once(self, _tok):
        olnm.hub_repo_add(str(self.wt), github="me/wt")
        olnm.dial(2); olnm.dial(2)
        mirrors = olnm.hub_api("GET", "/repos/admin/wt/push_mirrors")
        self.assertEqual(len(mirrors), 1)
        self.assertEqual(mirrors[0]["remote_address"], "https://github.com/me/wt.git")

    def test_labels_and_issues(self):
        olnm.hub_repo_add(str(self.wt))
        olnm.hub_labels(str(self.wt)); olnm.hub_labels(str(self.wt))
        names = [l["name"] for l in olnm.hub_api("GET", "/repos/admin/wt/labels")]
        self.assertIn("bug", names); self.assertEqual(len(names), len(set(names)))
        it = olnm.hub_issue_new("crash", labels=["bug", "nope"], path=str(self.wt))
        self.assertEqual([l["name"] for l in it["labels"]], ["bug"])
        self.assertEqual([i["title"] for i in olnm.hub_issue_ls(str(self.wt))], ["crash"])

    def test_pr_waits_for_branch_then_opens(self):
        olnm.hub_repo_add(str(self.wt))
        git("switch", "-qc", "fix", cwd=self.wt)
        bare = olnm.BARE / "wt.git"
        git("remote", "set-url", "local", str(bare), cwd=self.wt)  # fake forge has no git transport; push lands in bare
        pr = olnm.hub_pr_new("fix crash", path=str(self.wt))
        self.assertEqual((pr["number"], pr["head"]["ref"], pr["base"]["ref"]), (1, "fix", "main"))
        self.assertEqual([p["title"] for p in olnm.hub_pr_ls(str(self.wt))], ["fix crash"])

    def test_sync_bare_and_skip_github_below_dial2(self):
        olnm.hub_repo_add(str(self.wt), github="me/wt")
        res = olnm.hub_sync()
        self.assertTrue(res["wt:bare"]); self.assertNotIn("wt:github", res)
        self.assertEqual(git("--git-dir", str(olnm.BARE / "wt.git"), "rev-parse", "main", cwd=TMP), git("rev-parse", "main", cwd=self.wt))

    def test_bad_token(self):
        with self.assertRaises(SystemExit) as e:
            olnm.hub_api("GET", "/user/repos", token="wrong")
        self.assertIn("401", str(e.exception))

    def test_shell_gh_routes_to_forge_at_dial_le_2(self):
        olnm.hub_repo_add(str(self.wt))
        r = bash(f"cd {self.wt} && ghisn crash bug && ghis && hubopen")
        self.assertIn("🐛 #1", r.stdout); self.assertIn("crash", r.stdout); self.assertIn(f"localhost:{PORT}/", r.stdout)
        olnm.DIAL_FILE.write_text("3\n")
        self.assertEqual(bash("_olnm_hub && echo HUB || echo GH").stdout.strip(), "GH")

    def test_cli_parser(self):
        ap = olnm.build_parser()
        self.assertEqual(ap.parse_args(["hub", "dial", "2"]).level, 2)
        self.assertEqual(ap.parse_args(["hub", "issue", "new", "t", "--label", "bug"]).label, ["bug"])
        self.assertEqual(ap.parse_args(["hub", "install", "--flavor", "gitea"]).flavor, "gitea")
        for bad in (["dial", "9"], ["hub", "api", "FETCH", "/x"], ["hub"], ["hub", "install", "--flavor", "gitlab"]):
            with self.assertRaises(SystemExit):
                ap.parse_args(bad)


class TestInterop(unittest.TestCase):
    def test_call_rejects_private(self):
        for name in ("_hub_apply", "main", "nope"):
            with self.assertRaises(SystemExit):
                olnm.call(name)

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
