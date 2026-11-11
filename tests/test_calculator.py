"""Real shell expansion, arithmetic compatibility, and numeric input boundaries."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'olnm.py'


class TestCalculator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='olnm calculator ')
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.env = dict(os.environ, OLNM_PY=str(SOURCE), PYTHONPATH=str(ROOT),
                        OLNM_HOME=str(self.work / 'state'), DIAL_FILE=str(self.work / 'dial'))
        # Wildcards must actually match: do not test only an empty directory.
        for name in ('alpha', 'two words', '2**10'):
            (self.work / name).touch()

    def execute(self, argv):
        return subprocess.run(argv, cwd=self.work, env=self.env, text=True,
                              capture_output=True, timeout=30)

    def shell(self, shell, command):
        if not shutil.which(shell):
            self.skipTest(f'{shell} unavailable')
        return self.execute([shell, '-f' if shell == 'zsh' else '--noprofile', '-c',
                             f'eval "$(python3 "$OLNM_PY" init {shell})"\n{command}'])

    def check(self, result, output, code=0):
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertEqual(result.stdout.strip(), output, result.stderr)

    def matrix(self, shell):
        cases = [('6 + 7', '13'), ('6 mul 7', '42'), ('6 div 4', None),
                 ('2 pow 10', '1024'), ('-6 mul 7', '-42'),
                 ('6 minus -7', '13'), ('lpar 6 plus 7 rpar mul 2', '26'),
                 ('1.5e2 div 3', None), ('7 mod 4', '3'), ('6mul7', None)]
        for engine in ('calc', 'calc --engine node'):
            if engine == 'calc --engine node' and not shutil.which('node'):
                continue
            for expression, want in cases:
                with self.subTest(shell=shell, engine=engine, expression=expression):
                    result = self.shell(shell, f'{engine} {expression}')
                    if expression == '6mul7':
                        self.assertEqual(result.returncode, 1)
                    elif want is None:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(float(result.stdout), 1.5 if expression == '6 div 4' else 50)
                    else:
                        self.check(result, want)

    def test_bash_word_matrix(self):
        self.matrix('bash')

    def test_zsh_word_matrix(self):
        self.matrix('zsh')

    def test_quoted_space_expression(self):
        for shell in ('bash', 'zsh'):
            self.check(self.shell(shell, "calc '6 mul 7'"), '42')

    def test_glob_failure_is_before_function_entry(self):
        for shell in ('bash', 'zsh'):
            for engine in ('calc', 'calc --engine node'):
                with self.subTest(shell=shell, engine=engine):
                    result = self.shell(shell, f'{engine} 6 * 7')
                    self.assertNotEqual(result.returncode, 0)
                    self.assertTrue(result.stderr.startswith('calc:'), result.stderr)
            result = self.shell(shell, 'calc 8 *nomatch* 7')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('no matches found' if shell == 'zsh' else 'calc:', result.stderr)

    def test_python_results_and_exit_codes(self):
        for expression in ('6*7', '6 + 7', '2**10', '-6*7', '1/0', '1 +'):
            with self.subTest(expression=expression):
                old = self.execute([sys.executable, '-c', f'from math import *; print({expression})'])
                new = self.execute([sys.executable, str(SOURCE), 'calc', expression])
                self.assertEqual((new.returncode, new.stdout), (old.returncode, old.stdout))

    @unittest.skipUnless(shutil.which('node'), 'requires node')
    def test_node_results_and_exit_codes(self):
        for expression in ('6*7', '6 + 7', '2**10', '1/0', '1 +', '-6*7'):
            with self.subTest(expression=expression):
                old = self.execute(['node', '-p', '(' + expression + ')'])
                new = self.execute([sys.executable, str(SOURCE), 'calc', '--engine', 'node', expression])
                self.assertEqual((new.returncode, new.stdout), (old.returncode, old.stdout))

    def test_numeric_mode_rejects_code_and_non_arithmetic(self):
        for engine in ('python', 'node'):
            for expression in ('', '__import__("os").system("touch owned")',
                               'process.exit(0)', '1; 2', '1 # comment', 'True',
                               '"hello"', '[1]', '(1,2)', '1j', '2 ^ 3',
                               '2 << 3', '1 if 1 else 2', '1+' * 3000):
                with self.subTest(engine=engine, expression=expression):
                    result = self.execute([sys.executable, str(SOURCE), 'calc', '--engine', engine, expression])
                    self.check(result, '', 1)
                    self.assertTrue(result.stderr.startswith('calc:'))
        self.assertFalse((self.work / 'owned').exists())

    def test_received_shell_metacharacters_are_not_re_evaluated(self):
        for shell in ('bash', 'zsh'):
            result = self.shell(shell, "calc '$(touch owned)'")
            self.check(result, '', 1)
            self.assertFalse((self.work / 'owned').exists())

    def test_floor_division_and_runtime_semantics(self):
        self.check(self.shell('bash', 'calc -7 floordiv 2'), '-4')
        self.check(self.shell('bash', 'calc -7 mod 4'), '1')
        self.check(self.shell('bash', 'calc --engine node -7 mod 4'), '-3')
        self.check(self.shell('bash', 'calc --engine node 7 floordiv 2'), '', 1)
        self.check(self.shell('bash', 'calc 1 div 0'), '', 1)
        self.check(self.shell('bash', 'calc --engine node 1 div 0'), 'Infinity')
        self.check(self.shell('bash', 'calc -2 pow 2'), '-4')
        self.check(self.shell('bash', 'calc --engine node -2 pow 2'), '', 1)
        self.check(self.shell('bash', 'calc --engine node lpar -2 rpar pow 2'), '4')

    def test_python_one_liner_without_formula_quotes(self):
        self.check(self.execute([sys.executable, '-c',
            'import olnm,sys; sys.exit(olnm.calculate(*sys.argv[1:]))',
            '6', 'mul', '7']), '42')

    def test_run_arguments_are_not_globbed_again(self):
        self.check(self.execute([sys.executable, str(SOURCE), 'run', 'calc', '6', '*', '7']), '42')

    @unittest.skipUnless(shutil.which('node'), 'requires node')
    def test_node_caller_uses_argument_array(self):
        self.check(self.execute(['node', '-e',
            'const {execFileSync}=require("node:child_process"); process.stdout.write(execFileSync(process.argv[1],[process.env.OLNM_PY,"calc","6","*","7"],{encoding:"utf8"}))',
            sys.executable]), '42')

    def test_engine_options_help_and_missing_node(self):
        self.check(self.execute([sys.executable, str(SOURCE), 'calc', '--engine=python', '-6*7']), '-42')
        self.check(self.execute([sys.executable, str(SOURCE), 'calc', '--', '-6*7']), '-42')
        self.assertEqual(self.execute([sys.executable, str(SOURCE), 'calc', '--engine']).returncode, 2)
        self.assertEqual(self.execute([sys.executable, str(SOURCE), 'calc', '--engine', 'bad', '1']).returncode, 2)
        self.assertIn('usage:', self.execute([sys.executable, str(SOURCE), 'calc', '--help']).stdout)
        import olnm
        from unittest import mock
        with mock.patch.object(olnm.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertEqual(olnm.calculate('1', engine='node'), 127)
        self.assertEqual(olnm.calculate('1', engine='bad'), 1)

    def test_words_backend_needs_no_bash(self):
        self.check(self.execute([sys.executable, str(SOURCE), 'calc', '-6', 'mul', '7']), '-42')


if __name__ == '__main__':
    unittest.main()
