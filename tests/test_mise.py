"""mise adapter contracts; a fake executable observes real process boundaries."""
import importlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestMise(unittest.TestCase):
    def setUp(self):
        global olnm
        olnm = importlib.import_module('olnm')
        self.tmp = tempfile.TemporaryDirectory(prefix='olnm mise ')
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.bin = self.work / 'bin'; self.bin.mkdir()
        self.fake = self.bin / 'mise'
        self.fake.write_text('#!' + sys.executable + '\n' + '''import json,os,sys
if os.environ.get("FAKE_MISE_STDERR"):
    print("mise diagnostic", file=sys.stderr)
print(json.dumps({"argv":sys.argv[1:], "cwd":os.getcwd(), "stdin":sys.stdin.read(),
                  "auto":os.environ.get("MISE_AUTO_INSTALL"),
                  "exec_auto":os.environ.get("MISE_EXEC_AUTO_INSTALL")}))
sys.exit(int(os.environ.get("FAKE_MISE_EXIT", "0")))
''')
        self.fake.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin)+os.pathsep+os.environ['PATH'],
                        PYTHONPATH=str(ROOT), OLNM_PY=str(ROOT/'olnm.py'),
                        OLNM_HOME=str(self.work/'state'), DIAL_FILE=str(self.work/'dial'),
                        GIT_CONFIG_GLOBAL=str(self.work/'gitconfig'))

    def cli(self, *args, input='payload\n', env=None):
        return subprocess.run([sys.executable, ROOT/'olnm.py', *args], cwd=self.work,
                              input=input, text=True, capture_output=True, env=env or self.env, timeout=15)

    def test_direct_cli_preserves_argv_streams_cwd_and_exit(self):
        args = ('exec', 'node@26', '--', 'node', '-e', 'console.log("hello world")', '日本語', '$(touch INJECTED)', "a'b")
        result = self.cli('mise', *args, env=dict(self.env, FAKE_MISE_EXIT='7', FAKE_MISE_STDERR='1'))
        self.assertEqual(result.returncode, 7)
        observed = json.loads(result.stdout)
        self.assertEqual(observed['argv'], list(args))
        self.assertEqual(observed['cwd'], str(self.work))
        self.assertEqual(observed['stdin'], 'payload\n')
        self.assertIn('mise diagnostic', result.stderr)
        self.assertFalse((self.work/'INJECTED').exists())
        self.assertEqual(json.loads(self.cli('mise', '--', '--version').stdout)['argv'], ['--version'])

    def test_python_api_works_without_bash(self):
        # No bash or other runtime is on PATH; both Python executable paths are absolute.
        proc = subprocess.run([sys.executable, '-c',
            'import olnm,sys;sys.exit(olnm.mise("exec","--","uv","run","python","-V"))'],
            cwd=self.work, env=dict(self.env, PATH=str(self.bin)), input='', text=True, capture_output=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['argv'], ['exec','--','uv','run','python','-V'])

    def test_shell_wrappers_from_bash_zsh_and_run(self):
        cases = {'miseuse': ['use'], 'miseglobal':['use','--global'], 'miseinstall':['install'],
                 'miseexec':['exec'], 'miseoffline':['exec'], 'misels':['ls'],
                 'miselock':['lock'], 'misedoctor':['doctor']}
        for name, prefix in cases.items():
            with self.subTest(name=name):
                result = self.cli('run', name, 'node@26', '--', 'node', 'arg with spaces')
                self.assertEqual(result.returncode, 0, result.stderr)
                observed = json.loads(result.stdout)
                self.assertEqual(observed['argv'], prefix+['node@26','--','node','arg with spaces'])
                if name == 'miseoffline':
                    self.assertEqual((observed['auto'], observed['exec_auto']), ('false','false'))
                self.assertEqual(observed['stdin'], 'payload\n')
        for shell in ['bash'] + (['zsh'] if shutil.which('zsh') else []):
            result = subprocess.run([shell,'-c', 'eval "$(python3 "$OLNM_PY" init '+shell+')"; miseexec node@26 -- node -v'],
                                    cwd=self.work, env=self.env, input='', capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['argv'], ['exec','node@26','--','node','-v'])

    def test_missing_mise_is_actionable_and_installs_nothing(self):
        self.fake.unlink()
        # Isolate PATH rather than depending on whether the host has mise installed.
        (self.bin/'python3').symlink_to(sys.executable)
        (self.bin/'bash').symlink_to(shutil.which('bash'))
        env = dict(self.env, PATH=str(self.bin))
        for args in [('mise','exec','--','node','-v'), ('run','miseexec','--','node','-v')]:
            result = self.cli(*args, env=env)
            self.assertEqual(result.returncode, 127, result.stderr)
            self.assertIn('mise.jdx.dev', result.stderr)
            self.assertEqual(result.stdout, '')
        self.assertFalse((self.work/'mise.toml').exists())
        self.assertFalse((self.work/'state').exists())

    def test_dial_gates_known_network_wrappers_and_keeps_local_route(self):
        (self.work/'dial').write_text('0\n')
        result = self.cli('run','miseexec','--','node','-v')
        self.assertEqual(result.returncode, 1)
        self.assertIn('needs dial', result.stderr)
        local = self.cli('run','miseoffline','--','node','-v')
        self.assertEqual(local.returncode, 0, local.stderr)
        self.assertEqual(json.loads(local.stdout)['auto'], 'false')
        for name in ['misels','misedoctor']:
            self.assertEqual(self.cli('run',name).returncode, 0)

    def test_completion_and_public_api_catalog(self):
        self.assertEqual(olnm._completion(['olnm','mise','ex']), ['exec'])
        self.assertEqual(olnm._completion(['miseglobal','no']), ['node@26'])
        self.assertEqual(olnm._completion(['miseexec','node@26','--','node','x']), [])
        self.assertIn('mise',olnm.public())

    def test_readme_python_invocation_as_written(self):
        commands = [line for block in re.findall(r'```sh\n(.*?)\n```', (ROOT/'README.md').read_text(), re.S)
                    for line in block.splitlines() if line.startswith('python3 -c ') and 'olnm.mise(' in line]
        self.assertTrue(commands)
        for command in commands:
            result = subprocess.run(['bash','-c',command],cwd=self.work,env=self.env,
                                    input='',capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['argv'],['exec','node@26','--','node','--version'])

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
    def test_node_execfile_invokes_python_adapter(self):
        js = next(block for block in re.findall(r'```js\n(.*?)\n```', (ROOT/'README.md').read_text(), re.S)
                  if block.startswith("const { spawnSync }"))
        result = subprocess.run(['node','-e',js],cwd=self.work,
                                env=self.env,input='node stdin',text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        observed=json.loads(result.stdout)
        self.assertEqual(observed['argv'],['exec','node@26','--','node','--version'])
        self.assertEqual(observed['stdin'],'node stdin')


if __name__ == '__main__':
    unittest.main()
