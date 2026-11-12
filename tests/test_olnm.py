"""🧪 olnm tests — `python -m unittest discover`."""
import contextlib, io, json, os, re, shutil, subprocess, sys, tempfile, unittest
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


def bare_bash(script: str, bindir: Path, **env) -> subprocess.CompletedProcess:
    """bash with PATH limited to `bindir` (+ python3), to prove what a one-liner needs."""
    bindir.mkdir(parents=True, exist_ok=True)
    if not (bindir / "python3").exists():
        (bindir / "python3").symlink_to(sys.executable)
    return subprocess.run([shutil.which("bash"), "-c", f'eval "$(python3 {PY} init bash)"\n{script}'], text=True, capture_output=True,
                          env=dict(os.environ, PATH=str(bindir), **env))


def fake_tool(bindir: Path, name: str, body: str = 'echo "$(basename "$0") $*"') -> None:
    bindir.mkdir(parents=True, exist_ok=True)
    (bindir / name).write_text(f"#!/bin/sh\n{body}\n")
    (bindir / name).chmod(0o755)


class TestOneNamePerJob(unittest.TestCase):
    """🧹 Functions that did the same job were merged; the survivor covers what the removed names did."""

    def setUp(self):
        reset_forge()

    def test_removed_names_are_gone_and_the_hint_names_the_replacement(self):
        for old, new in olnm._MOVED.items():
            with self.subTest(old=old):
                self.assertNotIn(old, olnm.names())
                self.assertIn(new.split()[0], olnm.names())
        r = bash("pyjson; echo rc=$?")
        self.assertIn("pyjson was merged → use: jsonf", r.stderr)
        self.assertIn("rc=127", r.stdout)
        r = subprocess.run([sys.executable, PY, "run", "dpsa"], text=True, capture_output=True)
        self.assertEqual((r.returncode, r.stderr.strip()), (127, "🤔 dpsa was merged → use: dps -a"))

    def test_jsonf_output_is_the_same_with_and_without_jq(self):
        want = '{\n  "あ": [\n    1\n  ]\n}\n'
        doc = TMP / "doc with space.json"
        doc.write_text('{"あ":[1]}')
        without_jq = bare_bash(f'printf \'{{"あ":[1]}}\' | jsonf; jsonf "{doc}"', TMP / "only-python")
        self.assertEqual(without_jq.stdout, want * 2, without_jq.stderr)
        if shutil.which("jq"):
            self.assertEqual(bash(f'jsonf "{doc}"').stdout, want)

    def test_ver_shows_version_and_path_and_marks_what_is_missing(self):
        for shell in ["bash"] + (["zsh"] if shutil.which("zsh") else []):
            with self.subTest(shell=shell):
                r = subprocess.run([shell, "-c", f'eval "$(python3 {PY} init {shell})"\nver python3 no-such-tool; ver | wc -l'], text=True, capture_output=True)
                first, missing, count = r.stdout.splitlines()
                self.assertRegex(first, r"^python3  Python \d+\.\d+")
                self.assertTrue(first.endswith("  " + shutil.which("python3")), first)
                self.assertEqual(missing, "no-such-tool ❌ not on PATH")
                self.assertEqual(int(count), 7)  # the default list is not word-split away in zsh

    def test_epoch_is_now_or_a_conversion(self):
        r = subprocess.run(["bash", "-c", f'eval "$(python3 {PY} init bash)"\nepoch; epoch 1700000000'], text=True, capture_output=True, env=dict(os.environ, TZ="UTC"))
        now, converted = r.stdout.splitlines()
        self.assertTrue(now.isdigit())
        self.assertEqual(converted, "2023-11-14T22:13:20+00:00")

    def test_shell_olnm_routes_every_cli_command_from_the_parser(self):
        code = subprocess.run([sys.executable, PY, "init", "bash"], text=True, capture_output=True, check=True).stdout
        self.assertIn(f"_OLNM_COMMANDS='{' '.join(olnm._commands())}'", code)
        self.assertIn("gp() {", bash("olnm show gp").stdout)                     # a command added later needs no second list
        self.assertIn("gs ", bash("olnm git").stdout)                             # one word that is a section still lists it
        self.assertIn("no section", bash("olnm nope").stdout)                     # anything else is a section name
        self.assertEqual(bash("olnm calc 6 mul 7").stdout.strip(), "42")

    def test_reload_follows_the_running_shell_not_the_login_shell(self):
        for shell, login in [("bash", "/bin/zsh")] + ([("zsh", "/bin/bash")] if shutil.which("zsh") else []):
            with self.subTest(shell=shell):
                r = subprocess.run([shell, "-c", f'eval "$(python3 {PY} init {shell})"\nolnm_reload && uvtets'], text=True, capture_output=True,
                                   env=dict(os.environ, SHELL=login))
                self.assertIn("🔄", r.stdout)
                self.assertTrue(r.stderr.startswith("🤔 uvtets → did you mean: uvtest"), r.stderr)  # no syntax error, typo hook still installed

    def test_readme_tables_match_the_code(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("update_readme", ROOT / "scripts" / "update_readme.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        readme = (ROOT / "README.md").read_text()
        self.assertEqual(module.updated(readme), readme, "run: python3 scripts/update_readme.py")
        api = readme.split("<!-- python-api:start -->")[1].split("<!-- python-api:end -->")[0]
        self.assertEqual(sorted(re.findall(r"^\| `([a-z_0-9]+)\(", api, re.M)), olnm.public())
        self.assertIn(f"**{len(olnm.names())} 個のシェル関数**", readme)
        self.assertIn(f"**{len(olnm.public())} 個の Python API**", readme)
        self.assertIn(f"全 {len(olnm.names())} 関数", readme)


class TestShow(unittest.TestCase):
    """👁️ Read a one-liner before running it."""

    def test_python_cli_and_unknown_name(self):
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            text = olnm.show("gp")
        self.assertEqual(printed.getvalue(), text + "\n")
        self.assertTrue(text.startswith("# 🚀 gp: push current branch"))
        self.assertIn('\ngp() { git push -u origin', text)
        r = subprocess.run([sys.executable, PY, "show", "uvtets"], text=True, capture_output=True)
        self.assertEqual((r.returncode, r.stdout), (127, ""))
        self.assertIn("did you mean: uvtest", r.stderr)
        called = json.loads(subprocess.run([sys.executable, PY, "call", "show", '["mkcd"]'], text=True, capture_output=True).stdout)
        self.assertTrue(called.startswith("# 📁 mkcd: "))

    def test_every_name_can_be_shown_and_completed(self):
        with contextlib.redirect_stdout(io.StringIO()):
            for name in olnm.names():
                with self.subTest(name=name):
                    self.assertIn(f"\n{name}() {{ ", olnm.show(name))
            self.assertEqual(olnm.complete("olnm_show", "uvte"), ["uvtest"])
            self.assertEqual(olnm.complete("olnm", "show", "uvte"), ["uvtest"])
        self.assertIn("olnm_show", bash("olnm_show olnm_show").stdout)


class TestOfflineDial(unittest.TestCase):
    """🔌 offline / local: uv and npm use only their caches; the way back undoes only what olnm set."""

    def setUp(self):
        reset_forge()
        self.addCleanup(reset_forge)

    def test_exports_and_undo(self):
        olnm.dial(0)
        r = bash('echo "[$UV_OFFLINE][$npm_config_offline]"; olnm_dial github >/dev/null; echo "[${UV_OFFLINE-}][${npm_config_offline-}][${_OLNM_OFFLINE-}]"')
        self.assertEqual(r.stdout.splitlines(), ["[1][true]", "[][][]"], r.stderr)
        r = bash('echo "[${UV_OFFLINE-}]"; export UV_OFFLINE=1; olnm_reload >/dev/null; echo "[$UV_OFFLINE]"')  # github: a value the user set stays
        self.assertEqual(r.stdout.splitlines(), ["[]", "[1]"])

    @unittest.skipUnless(shutil.which("uv"), "requires uv")
    def test_uv_refuses_the_network_at_once(self):
        olnm.dial("local")
        r = bash("uv pip install --dry-run --system olnm-no-such-package-xyz")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("network was disabled", r.stderr)

    def test_nclean_does_not_delete_what_it_cannot_reinstall(self):
        project = TMP / "node project"
        (project / "node_modules").mkdir(parents=True)
        self.assertIn("nclean", olnm.net())
        olnm.dial(0)
        r = bash(f'cd "{project}" && nclean; echo rc=$?')
        self.assertIn("rc=1", r.stdout)
        self.assertIn("needs dial mirror or github", r.stderr)
        self.assertTrue((project / "node_modules").is_dir())


class TestAddedOneLiners(unittest.TestCase):
    def setUp(self):
        reset_forge()

    def test_jget_reads_values_without_jq(self):
        doc = '{"a":{"b":[10,{"c":"あ"}]},"n":null}'
        for path, want in (("a.b.1.c", "あ"), ("a.b.0", "10"), ("a.b", '[10, {"c": "あ"}]'), ("n", "null"), ("", doc.replace(":", ": ").replace(",", ", "))):
            with self.subTest(path=path):
                r = bare_bash(f"printf '%s' '{doc}' | jget {path}", TMP / "only-python")
                self.assertEqual(r.stdout.strip(), want, r.stderr)
        self.assertNotEqual(bare_bash(f"printf '%s' '{doc}' | jget a.zz", TMP / "only-python").returncode, 0)

    def test_thin_wrappers_pass_arguments_through(self):
        tools = TMP / "echo-tools"
        for name in ("uv", "npm", "systemctl", "journalctl"):
            fake_tool(tools, name)
        cases = {"uvsync --no-dev": "uv sync --locked --no-dev", "uvout": "uv tree --outdated --depth 1", "ni 'left pad'": "npm install left pad",
                 "nt -- --watch": "npm test -- --watch", "svc ssh": "systemctl status --no-pager ssh", "jlog ssh 5": "journalctl -u ssh -n 5 -f",
                 "jlog ssh": "journalctl -u ssh -n 100 -f"}
        for command, want in cases.items():
            with self.subTest(command=command):
                self.assertEqual(bash(command, str(tools)).stdout.strip(), want)

    def test_gsync_rebases_onto_the_default_branch_of_origin_and_gpop_restores(self):
        base = TMP / "gsync"
        identity = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")

        def git(*args, cwd):
            return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True, env=identity).stdout.strip()

        def commit(repo, name):
            (repo / name).write_text(name)
            git("add", "-A", cwd=repo)
            git("commit", "-qm", name, cwd=repo)

        base.mkdir()
        git("init", "-q", "--bare", "-b", "trunk", "origin.git", cwd=base)  # not `main`: the default branch is read, not assumed
        git("clone", "-q", "origin.git", "seed", cwd=base)
        git("switch", "-qc", "trunk", cwd=base / "seed")
        commit(base / "seed", "c1")
        git("push", "-q", "origin", "trunk", cwd=base / "seed")
        git("clone", "-q", "origin.git", "work", cwd=base)
        work = base / "work"
        git("switch", "-qc", "feat", cwd=work)
        commit(work, "f1")
        commit(base / "seed", "c2")
        git("push", "-q", "origin", "trunk", cwd=base / "seed")
        (work / "f1").write_text("edited, not committed")  # autostash keeps it
        r = subprocess.run(["bash", "-c", f'eval "$(python3 {PY} init bash)"\ncd "{work}" && gsync && gstash later >/dev/null && git status --short | wc -l && gpop >/dev/null'],
                           text=True, capture_output=True, env=identity)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(git("log", "--format=%s", cwd=work).splitlines(), ["f1", "c2", "c1"])
        self.assertEqual(r.stdout.strip().splitlines()[-1], "0")                    # gstash left a clean tree …
        self.assertEqual((work / "f1").read_text(), "edited, not committed")       # … and gpop brought the edit back

    def test_dsave_names_the_archive_and_reports_a_failed_save(self):
        tools, out = TMP / "docker-tools", TMP / "images"
        out.mkdir()
        fake_tool(tools, "docker", '[ -z "$FAIL" ] || exit 1\ncase "$1" in save) printf "image:%s" "$2" > "$4";; load) echo "docker $*";; esac')
        r = bash(f'cd "{out}" && dsave reg.local/team/app:1.2 >/dev/null && gunzip -c reg.local_team_app_1.2.tar.gz && dsave x:y "my file.tar.gz" >/dev/null && ls', str(tools))
        self.assertEqual(r.stdout.splitlines(), ["image:reg.local/team/app:1.2my file.tar.gz", "reg.local_team_app_1.2.tar.gz"], r.stderr)
        r = bash(f'cd "{out}" && FAIL=1 dsave bad:1; echo "rc=$?"; ls', str(tools))
        self.assertIn("rc=1", r.stdout)
        self.assertNotIn("bad_1", r.stdout)                                         # a failed save leaves no archive that looks complete
        self.assertEqual(bash('dload "a b.tar.gz"', str(tools)).stdout.strip(), "docker load -i a b.tar.gz")

    def test_ghchecks_and_ghrerun_ask_gh_for_this_branch(self):
        tools, repo, log = TMP / "gh-tools", TMP / "gh repo", TMP / "gh.log"
        fake_tool(tools, "gh", f'echo "$*" >> "{log}"\nif [ "$1 $2" = "run list" ]; then echo 777; fi')
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "feat/x", str(repo)], check=True)
        r = bash(f'cd "{repo}" && ghchecks 12 && ghrerun', str(tools))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(log.read_text().splitlines(), ["pr checks 12", "run list --branch feat/x --limit 1 --json databaseId -q .[0].databaseId", "run rerun 777 --failed"])


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
