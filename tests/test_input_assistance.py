"""Real argv, shell completion, PTY input and missing-runtime regressions."""
import os
import importlib
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestInputAssistance(unittest.TestCase):
    def setUp(self):
        # Let test_olnm finish its isolated environment setup during discovery.
        # Importing olnm at collection time would capture the caller's real HOME.
        global olnm
        olnm = importlib.import_module('olnm')
        self.tmp = tempfile.TemporaryDirectory(prefix="olnm assist ")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.env = dict(os.environ, OLNM_HOME=str(self.work / "state"),
                        DIAL_FILE=str(self.work / "dial"), GIT_CONFIG_GLOBAL=str(self.work / "gitconfig"))
        self.source = ROOT / "olnm.py"

    def cli(self, *args, input=None):
        return subprocess.run([sys.executable, str(self.source), *args], input=input,
                              text=True, capture_output=True, env=self.env, cwd=self.work, timeout=15)

    def shell(self, script, shell="bash", env=None):
        env = dict(env or self.env, OLNM_PY=str(self.source))
        return subprocess.run([shell, "-c", 'eval "$(python3 "$OLNM_PY" init ' + shell + ')"\n' + script],
                              text=True, capture_output=True, env=env, cwd=self.work, timeout=15)

    def test_completion_context_and_prefix(self):
        cases = [
            (("olnm", "ru"), ["run"]),
            (("olnm", "run", "pyc"), ["pycalc", "pyclean", "pycsv"]),
            (("olnm", "hub", "issue", ""), ["ls", "new"]),
            (("hubdial", "install", "--flavor", ""), ["forgejo", "gitea"]),
            (("olnm", "hub", "install", "--flavor", "gi"), ["gitea"]),
            (("olnm_dial", ""), ["0", "1", "2", "3"]),
            (("olnm_offline", "py"), ["python"]),
            (("olnm_like", "pyc"), ["pycalc", "pyclean", "pycsv"]),
            (("olnm", "tools", "ru"), ["rust", "rustc", "rustup"]),
            (("olnm", "call", "read_"), ["read_dial"]),
        ]
        for words, expected in cases:
            with self.subTest(words=words):
                with mock.patch.object(olnm.subprocess, "run", side_effect=AssertionError("completion executed a command")):
                    self.assertEqual(olnm._completion(list(words)), expected)
                result = self.cli("complete", "--", *words)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), expected)
        result = self.cli("complete", "--", "olnm", "hub", "issue", "ls", "--st")
        self.assertEqual(result.stdout.strip(), "--state")
        self.assertEqual(self.cli("complete", "--", "olnm", "run", "pycalc", "x").stdout, "")

    def test_bash_completion_registration_and_replies(self):
        result = self.shell('complete -p olnm; COMP_WORDS=(olnm hub install --flavor ""); COMP_CWORD=4; _olnm_complete_bash; printf "%s\\n" "${COMPREPLY[@]}"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-F _olnm_complete_bash", result.stdout)
        self.assertEqual(result.stdout.splitlines()[-2:], ["forgejo", "gitea"])

    @unittest.skipUnless(shutil.which("zsh"), "zsh unavailable")
    def test_zsh_completion_registration_and_replies(self):
        result = self.shell('autoload -Uz compinit; compinit -D; eval "$(python3 "$OLNM_PY" init zsh)"; '
                            'print -r -- "${_comps[olnm]}"; words=(olnm hub install --flavor ""); CURRENT=5; '
                            'compadd() { printf "%s\\n" "$@"; }; _olnm_complete_zsh', shell="zsh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["_olnm_complete_zsh", "--", "forgejo", "gitea"])

    def test_hybrid_shell_preserves_every_section_and_supports_cli(self):
        for section in olnm._sections():
            result = self.shell('olnm ' + section)
            expected = self.cli("ls", section)
            self.assertEqual(result.stdout, expected.stdout, section)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = self.shell("olnm calc 6 + 7; olnm run pycalc '6*7'")
        self.assertEqual(result.stdout.splitlines(), ["13", "42"])
        self.assertIn('arithmetic', self.shell('olnm --help').stdout)

    def test_typos_suggest_without_executing_or_changing_input(self):
        for args, suggestion in [(('rn',), 'run'), (('hub', 'isue'), 'issue'),
                                 (('hub', 'install', '--flavr', 'gitea'), '--flavor')]:
            result = self.cli(*args)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(suggestion, result.stderr)
            self.assertIn("did you mean", result.stderr)
            self.assertFalse((self.work / "state").exists())
        result = self.shell('olnm rn')
        self.assertEqual(result.returncode, 2)
        self.assertIn('run', result.stderr)
        self.assertIn('did you mean', result.stderr)
        result = self.cli('call', 'read_dail')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('read_dial', result.stderr)
        self.assertIn('did you mean', result.stderr)

    def test_arithmetic_and_resource_limits(self):
        for expression, expected in [('6*7', 42), ('(6+7)*2', 26), ('sqrt(81)', 9), ('-2**3', -8),
                                     ('round(pi,2)', 3.14), ('7//2 + 7%2', 4)]:
            self.assertEqual(olnm.calc(expression), expected)
        for bad in ['__import__("os")', '(1).__class__', '[1]', 'True', '2**1001', '0.0/0', '"hello"',
                    '2**-1001', '1e999', 'sqrt(-1)', '(2**1000)**1000', '1+'*100+'1', '1'*1001]:
            with self.subTest(expression=bad), self.assertRaises((ValueError, SyntaxError, ArithmeticError)):
                olnm.calc(bad)

    def test_calculator_stdin_quotes_globs_and_errors(self):
        (self.work / "6x7").touch()
        self.assertEqual(self.cli('calc', input='6*7\n').stdout.strip(), '42')
        self.assertEqual(self.cli('calc', '--', '-2', '*', '3').stdout.strip(), '-6')
        error = self.cli('calc', input='6*\n')
        self.assertEqual(error.returncode, 2)
        self.assertIn('Try: olnm calc', error.stderr)
        # No-arg pycalc uses the input route. Existing string-evaluation calls stay compatible.
        result = subprocess.run(['bash', '-c', 'printf "%s\\n" "(6+7)*2" | python3 "$OLNM_PY" run pycalc'],
                                env=dict(self.env, OLNM_PY=str(self.source)), cwd=self.work,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.stdout.strip(), '26', result.stderr)
        self.assertEqual(self.cli('run', 'pycalc', '"hello world"').stdout.strip(), 'hello world')

    def test_tty_prompt_does_not_require_shell_quoting(self):
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen([sys.executable, self.source, 'calc'], stdin=slave,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    cwd=self.work, env=self.env, text=True)
            os.close(slave)
            slave = None
            os.write(master, b'(6+7)*2\n')
            out, err = proc.communicate(timeout=15)
            self.assertEqual(proc.returncode, 0, err)
            self.assertEqual(out.strip(), '26')
            self.assertIn('no surrounding quotes', err)
        finally:
            os.close(master)
            if slave is not None:
                os.close(slave)

    def test_real_terminal_tab_completes_calculator_input(self):
        try:
            import readline  # noqa: F401
        except ImportError:
            self.skipTest('optional readline unavailable')
        master, slave = pty.openpty()
        proc = subprocess.Popen([sys.executable, self.source, 'calc'], stdin=slave,
                                stdout=slave, stderr=slave, cwd=self.work,
                                env=dict(self.env, INPUTRC='/dev/null'))
        os.close(slave)
        output = b''
        try:
            while b'no surrounding quotes' not in output:
                self.assertTrue(select.select([master], [], [], 10)[0], output)
                output += os.read(master, 8192)
            os.write(master, b'sq\t81)\n')
            proc.wait(timeout=10)
            while select.select([master], [], [], 1)[0]:
                try:
                    chunk = os.read(master, 8192)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
            self.assertEqual(proc.returncode, 0, output)
            self.assertIn(b'sqrt(81)', output)
            self.assertIn(b'9.0', output)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            os.close(master)

    def test_invalid_json_has_actionable_message_and_no_traceback(self):
        for args in [('call', 'like', 'broken'), ('call', 'like', '{}'),
                     ('call', 'like', '[]', '--kwargs', '[]')]:
            result = self.cli(*args)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('JSON', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_missing_runtimes_and_install_after_init(self):
        bindir = self.work / 'bin'; bindir.mkdir()
        (bindir / 'python3').symlink_to(sys.executable)
        bash = shutil.which('bash')
        (bindir / 'bash').symlink_to(bash)
        env = dict(self.env, PATH=str(bindir), OLNM_PY=str(self.source))
        for shell in ['bash'] + (['zsh'] if shutil.which('zsh') else []):
            executable = shutil.which(shell)
            for name, expected in [('ncalc', 'nodejs.org'), ('bi', 'bun.sh')]:
                result = subprocess.run([executable, '-c', 'eval "$(python3 "$OLNM_PY" init ' + shell + ')"; ' + name],
                                        cwd=self.work, env=env, text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 127, result.stderr)
                self.assertIn(expected, result.stderr)
                self.assertIn('not found on PATH', result.stderr)
        # Missing npm must be detected before a cleanup removes project files.
        modules = self.work / 'node_modules'; modules.mkdir()
        result = subprocess.run([bash, '-c', 'eval "$(python3 "$OLNM_PY" init bash)"; nclean'],
                                env=env, cwd=self.work, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 127, result.stderr)
        self.assertTrue(modules.is_dir())
        # Runtime checks happen per call: installation after init requires no reload.
        result = subprocess.run([bash, '-c', 'eval "$(python3 "$OLNM_PY" init bash)"; '
                                 'ncalc 1 >/dev/null 2>&1; '
                                 'printf \'#!/bin/sh\\nprintf "42\\\\n"\\n\' > "$1/node"; '
                                 '/bin/chmod +x "$1/node"; ncalc 6*7', 'test', str(bindir)],
                                cwd=self.work, env=env, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '42')
        rust = self.cli('tools', 'rust')
        self.assertIn('rustup', rust.stdout)
        self.assertIn('rust-toolchain.toml', rust.stdout)

    def test_init_and_run_handle_shell_metacharacters_in_source_path(self):
        folder = self.work / 'literal $(touch INJECTED) " quote'; folder.mkdir()
        source = folder / 'olnm.py'; shutil.copyfile(self.source, source)
        result = subprocess.run([sys.executable, source, 'run', 'pycalc', '6*7'],
                                cwd=self.work, env=self.env, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '42')
        self.assertFalse((self.work / 'INJECTED').exists())

    def test_update_without_source_explains_each_install_route(self):
        result = self.shell('unset OLNM_URL; olnm_update')
        self.assertEqual(result.returncode, 1)
        self.assertIn('File install', result.stderr)
        self.assertIn('uv tool upgrade', result.stderr)


if __name__ == '__main__':
    unittest.main()
