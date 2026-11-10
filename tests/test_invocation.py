"""Executable README examples and isolated uv installation smoke tests."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "olnm.py"


class IsolatedInvocation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="olnm examples ")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.env = dict(os.environ)
        self.env.update(
            OLNM_PY=str(SOURCE),
            OLNM_HOME=str(self.work / "state"),
            DIAL_FILE=str(self.work / "state" / "dial"),
            GIT_CONFIG_GLOBAL=str(self.work / "gitconfig"),
        )

    def execute(self, *args, cwd=None, input=None, expected=0):
        result = subprocess.run(
            [str(arg) for arg in args], cwd=cwd or self.work,
            env=self.env, input=input, text=True, capture_output=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def cli(self, *args, **kwargs):
        return self.execute(sys.executable, SOURCE, *args, **kwargs)


class TestReadmeInvocation(IsolatedInvocation):
    def test_python_one_liners_as_written_in_readme(self):
        # Test the actual copied text, including quoting, not a retyped equivalent.
        self.env["PYTHONPATH"] = str(ROOT)
        (self.work / "candidates.json").write_text('["uvtest"]')
        readme = (ROOT / "README.md").read_text()
        commands = [
            line for block in re.findall(r"```sh\n(.*?)\n```", readme, re.S)
            for line in block.splitlines()
            if line.startswith("python3 -c ") and "hub_issue_new" not in line
        ]
        self.assertGreaterEqual(len(commands), 10)
        for command in commands:
            with self.subTest(command=command):
                result = self.execute("bash", "-c", command)
                self.assertTrue(result.stdout.strip(), command)
                if '"6*7"' in command:
                    self.assertEqual(result.stdout.strip(), "42")

    def test_call_json_separates_progress_and_supports_kwargs(self):
        result = self.cli("call", "like", '["uvtets"]', "--kwargs", '{"n":2}')
        self.assertEqual(json.loads(result.stdout)[0], "uvtest")
        self.assertLessEqual(len(json.loads(result.stdout)), 2)
        self.assertIn("uvtest", result.stderr)
        result = self.cli("call", "ls", '["python"]', "--kwargs", '{"offline":true}')
        rows = json.loads(result.stdout)
        self.assertTrue(rows)
        self.assertTrue(all(row["section"] == "python" and not row["net"] for row in rows))

    def test_run_inherits_stdin_cwd_and_preserves_space_arguments(self):
        result = self.cli("run", "pyjson", input='{"answer":42}')
        self.assertEqual(json.loads(result.stdout), {"answer": 42})
        (self.work / "file with spaces.json").write_text('{"answer":42}')
        result = self.cli("run", "pyjson", "file with spaces.json")
        self.assertEqual(json.loads(result.stdout), {"answer": 42})
        result = self.cli("run", "pycalc", '"hello world"')
        self.assertEqual(result.stdout.strip(), "hello world")

    def test_source_file_with_spaces_and_hidden_filename(self):
        source = self.work / ".olnm.py"
        shutil.copyfile(SOURCE, source)
        self.env["OLNM_PY"] = str(source)
        result = self.execute(sys.executable, source, "run", "pycalc", "6*7")
        self.assertEqual(result.stdout.strip(), "42")
        result = self.execute(
            sys.executable, "-c",
            'import os, runpy; m = runpy.run_path(os.environ["OLNM_PY"]); m["like"]("uvtets")',
        )
        self.assertEqual(result.stdout.splitlines()[0], "uvtest")

    def test_run_exit_codes_and_offline_stubs(self):
        self.cli("run", "zzzzqqq", expected=127)
        self.cli("like", "zzzzqqq")
        self.cli("like", "zzzzqqq", "--hint", expected=127)
        self.cli("dial", "9", expected=2)
        self.cli("dial", "0")
        result = self.cli("run", "myip", expected=1)
        self.assertIn("needs dial", result.stderr)
        self.assertEqual(self.cli("run", "pycalc", "6*7").stdout.strip(), "42")
        self.assertEqual(json.loads(self.cli("call", "read_dial").stdout), 0)

    def test_all_cli_help_paths(self):
        # test_olnm configures module constants on import during full discovery.
        # Delay this import so these read-only tests do not pre-empt that setup.
        import olnm

        def visit(parser, prefix=()):
            yield prefix
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for name, child in action.choices.items():
                        yield from visit(child, (*prefix, name))

        for path in visit(olnm.build_parser()):
            with self.subTest(path=path):
                self.assertIn("usage:", self.cli(*path, "--help").stdout)


@unittest.skipUnless(
    os.environ.get("OLNM_TEST_UV") == "1" and shutil.which("uv"),
    "opt in with OLNM_TEST_UV=1; requires uv and the build backend",
)
class TestUvLifecycle(IsolatedInvocation):
    def test_tool_uvx_project_dependency_and_uninstall(self):
        # Do not install tools or change shell files in the user's real environment.
        self.env.update(
            UV_TOOL_DIR=str(self.work / "tools"),
            UV_TOOL_BIN_DIR=str(self.work / "bin"),
            UV_PYTHON=sys.executable,
            UV_PYTHON_DOWNLOADS="never",
        )
        self.env.pop("PYTHONPATH", None)
        self.env.pop("VIRTUAL_ENV", None)
        self.env["PATH"] = str(self.work / "bin") + os.pathsep + self.env["PATH"]

        # Build a clean copy so editable/build artefacts never alter the checkout.
        source = self.work / "source with spaces"
        source.mkdir()
        for name in ("olnm.py", "README.md", "pyproject.toml"):
            shutil.copyfile(ROOT / name, source / name)

        def uv(*args, **kwargs):
            return self.execute("uv", *args, **kwargs)

        result = uv("run", "--no-project", source / "olnm.py", "run", "pycalc", "6*7")
        self.assertEqual(result.stdout.strip(), "42")
        uv("tool", "install", ".", cwd=source)
        self.assertIn("one-linear-numerous-memo", uv("tool", "list").stdout)
        self.assertEqual(self.execute("olnm", "run", "pycalc", "6*7").stdout.strip(), "42")
        result = self.execute("olnm", "call", "like", '["uvtets"]')
        self.assertEqual(json.loads(result.stdout)[0], "uvtest")
        result = self.execute(
            "bash", "-c",
            'eval "$(olnm init bash)"; pycalc "6*7"; command olnm run pycalc "6*7"',
        )
        self.assertEqual(result.stdout.splitlines(), ["42", "42"])
        uv("tool", "install", "--force", ".", cwd=source)
        result = uv("tool", "run", "--from", str(source), "olnm", "run", "pycalc", "6*7")
        self.assertEqual(result.stdout.strip(), "42")
        result = uv(
            "run", "--no-project", "--with", str(source), "python", "-c",
            'import olnm; print(olnm.names()[0])',
        )
        self.assertEqual(result.stdout.strip(), "olnm")

        project = self.work / "consumer"
        uv("init", "--bare", "--python", sys.executable, str(project))
        uv("add", str(source), cwd=project)
        uv("sync", "--locked", cwd=project)
        result = uv(
            "run", "--locked", "python", "-c",
            'import olnm, sys; sys.exit(olnm.run("pycalc", "6*7"))', cwd=project,
        )
        self.assertEqual(result.stdout.strip(), "42")
        # The installation must work away from the source directory.
        self.assertEqual(json.loads(uv("run", "olnm", "call", "names", cwd=project).stdout)[0], "olnm")
        uv("lock", "--upgrade-package", "one-linear-numerous-memo", cwd=project)
        uv("sync", "--reinstall-package", "one-linear-numerous-memo", cwd=project)
        uv("remove", "one-linear-numerous-memo", cwd=project)
        uv("tool", "uninstall", "one-linear-numerous-memo")
        self.assertFalse((self.work / "bin" / "olnm").exists())
        self.assertNotIn("one-linear-numerous-memo", uv("tool", "list").stdout)


if __name__ == "__main__":
    unittest.main()
