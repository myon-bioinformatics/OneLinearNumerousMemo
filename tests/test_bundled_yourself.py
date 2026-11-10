"""Default yourself command works from a standalone copy, without installation."""
import contextlib
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestBundledYourself(unittest.TestCase):
    def setUp(self):
        global olnm
        olnm = importlib.import_module('olnm')
        self.tmp = tempfile.TemporaryDirectory(prefix='olnm yourself ')
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        # Only olnm.py is carried to a different directory. No source clone on sys.path.
        self.source = self.work / 'olnm.py'
        shutil.copyfile(ROOT / 'olnm.py', self.source)
        self.env = dict(os.environ, OLNM_PY=str(self.source),
                        OLNM_HOME=str(self.work/'state'), DIAL_FILE=str(self.work/'dial'),
                        GIT_CONFIG_GLOBAL=str(self.work/'gitconfig'))
        self.env.pop('PYTHONPATH',None)

    def cli(self,*args):
        return subprocess.run([sys.executable,self.source,*args],cwd=self.work,env=self.env,
                              text=True,capture_output=True,timeout=20)

    def test_snapshot_integrity_license_and_inert_import(self):
        self.assertEqual(hashlib.sha256(olnm._YOURSELF_SOURCE.encode()).hexdigest(),olnm._YOURSELF_SHA256)
        self.assertEqual(len(olnm._YOURSELF_COMMIT),40)
        self.assertIn('MIT License',olnm._YOURSELF_LICENSE)
        self.assertIn('Copyright (c) 2026 myon',olnm._YOURSELF_LICENSE)
        # Loading the pinned definitions performs no process execution or socket access.
        import socket
        with mock.patch.object(olnm.subprocess,'run',side_effect=AssertionError('unexpected subprocess')), \
             mock.patch.object(socket,'socket',side_effect=AssertionError('unexpected socket')):
            namespace=olnm._yourself_namespace()
        self.assertTrue(callable(namespace['main']))

    def test_cli_equals_pinned_upstream_on_minimal_report(self):
        result=self.cli('yourself','--minimal','--format','json')
        self.assertEqual(result.returncode,0,result.stderr)
        upstream=self.work/'reference.py';upstream.write_text(olnm._YOURSELF_SOURCE)
        expected=subprocess.run([sys.executable,upstream,'--minimal','--format','json'],
                                cwd=self.work,env=self.env,text=True,capture_output=True,timeout=20)
        self.assertEqual(json.loads(result.stdout),json.loads(expected.stdout))
        self.assertEqual(json.loads(result.stdout)['schema_version'],1)
        self.assertFalse((self.work/'state').exists())

    def test_api_without_args_is_default_upstream_main_and_returns_exit_code(self):
        entry=mock.Mock(return_value=0)
        with mock.patch.object(olnm,'_yourself_namespace',return_value={'main':entry}):
            self.assertEqual(olnm.yourself(),0)
        entry.assert_called_once_with([])
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(olnm.yourself('--minimal','--format','json'),0)
        self.assertEqual(json.loads(out.getvalue())['schema_version'],1)

    def test_api_help_and_argument_error_return_codes(self):
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            self.assertEqual(olnm.yourself('--help'),0)
            self.assertEqual(olnm.yourself('--format','invalid'),2)
        self.assertIn('--minimal',out.getvalue())
        self.assertIn('invalid',err.getvalue())
        self.assertEqual(self.cli('yourself','--format','invalid').returncode,2)
        self.assertEqual(self.cli('yourself','--runner-env-json').returncode,2)

    def test_shell_run_and_uv_file_entrypoints(self):
        for args in [('run','yourself','--minimal','--format','json'),
                     ('yourself','--','--minimal','--format','json')]:
            result=self.cli(*args)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['schema_version'],1)
        for shell in ['bash']+(['zsh'] if shutil.which('zsh') else []):
            result=subprocess.run([shell,'-c','eval "$(python3 "$OLNM_PY" init '+shell+')"; yourself --minimal --format json'],
                                  cwd=self.work,env=self.env,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['schema_version'],1)
        if shutil.which('uv'):
            result=subprocess.run(['uv','run','--offline','--no-project',self.source,'yourself','--minimal','--format','json'],
                                  cwd=self.work,env=self.env,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['schema_version'],1)

    def test_default_completion_uses_upstream_declarations(self):
        for words in [['yourself','--fo'],['olnm','yourself','--fo'],['olnm','run','yourself','--fo']]:
            self.assertEqual(olnm._completion(words),['--format'])
        self.assertEqual(olnm._completion(['yourself','--format','']),['json','markdown','text'])
        self.assertIn('yourself',olnm.names())
        self.assertIn('yourself',olnm.public())

    def test_report_stdout_has_no_wrapper_messages_even_when_mise_is_missing(self):
        bindir=self.work/'bin';bindir.mkdir();(bindir/'python3').symlink_to(sys.executable)
        env=dict(self.env,PATH=str(bindir))
        result=subprocess.run([sys.executable,self.source,'yourself','--minimal','--format','json'],
                              cwd=self.work,env=env,text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stderr,'')
        json.loads(result.stdout)

    def test_snapshot_refresh_is_idempotent_and_rejects_uncommitted_source(self):
        upstream=self.work/'upstream';upstream.mkdir()
        (upstream/'yourself.py').write_text('def main(argv=None):\n    return 0\n')
        (upstream/'LICENSE').write_text('MIT License\n')
        def git(*args):
            return subprocess.run(['git',*args],cwd=upstream,env=self.env,text=True,capture_output=True,check=True)
        git('init','-q');git('add','yourself.py','LICENSE')
        git('-c','user.name=test','-c','user.email=test@example.invalid','commit','-qm','snapshot')
        target=self.work/'target.py';target.write_text('if __name__ == "__main__":\n    pass\n')
        command=[sys.executable,ROOT/'scripts/update_yourself.py',upstream,'--target',target]
        result=subprocess.run(command,env=self.env,text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        expected=target.read_bytes()
        self.assertEqual(subprocess.run(command,env=self.env,capture_output=True).returncode,0)
        self.assertEqual(target.read_bytes(),expected)
        (upstream/'yourself.py').write_text('def main(argv=None):\n    return 1\n')
        result=subprocess.run(command,env=self.env,text=True,capture_output=True,timeout=15)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('differs from the pinned',result.stderr)
        self.assertEqual(target.read_bytes(),expected)


if __name__=='__main__':
    unittest.main()
