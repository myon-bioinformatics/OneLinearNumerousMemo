"""Default stdlib commands delegate to pinned uv tools without registration."""
import importlib,json,os,re,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class StdlibCommands(unittest.TestCase):
 def setUp(self):
  global olnm
  olnm=importlib.import_module('olnm')
  self.tmp=tempfile.TemporaryDirectory(prefix='olnm stdlib ');self.addCleanup(self.tmp.cleanup)
  self.work=Path(self.tmp.name);self.bin=self.work/'bin';self.bin.mkdir()
  self.uv=self.bin/'uv';self.uv.write_text('#!'+sys.executable+'\nimport os,json,sys\nprint(json.dumps({"argv":sys.argv[1:],"stdin":sys.stdin.read(),"cwd":os.getcwd()}))\nprint("backend diagnostic",file=sys.stderr)\nsys.exit(int(os.environ.get("BACKEND_EXIT","0")))\n');self.uv.chmod(0o755)
  self.env=dict(os.environ,PATH=str(self.bin)+os.pathsep+os.environ['PATH'],PYTHONPATH=str(ROOT),OLNM_PY=str(ROOT/'olnm.py'),DIAL_FILE=str(self.work/'dial'),OLNM_HOME=str(self.work/'state'))
 def cli(self,*args,env=None):
  return subprocess.run([sys.executable,ROOT/'olnm.py',*args],cwd=self.work,env=env or self.env,input='stdin text',text=True,capture_output=True,timeout=15)
 def test_default_cli_commands_preserve_process_contract(self):
  for name,tool in olnm._STDLIB_TOOLS.items():
   r=self.cli(name,'--help','arg with spaces','$(touch INJECTED)',env=dict(self.env,BACKEND_EXIT='7'))
   self.assertEqual(r.returncode,7,r.stderr)
   d=json.loads(r.stdout);self.assertEqual(d['stdin'],'stdin text');self.assertEqual(d['cwd'],str(self.work))
   self.assertEqual(d['argv'][:3],['tool','run','--from'])
   self.assertTrue(d['argv'][3].endswith('@'+tool['commit']))
   self.assertEqual(d['argv'][4:],[tool['command'],'--help','arg with spaces','$(touch INJECTED)'])
   self.assertIn('backend diagnostic',r.stderr);self.assertFalse((self.work/'INJECTED').exists())
 def test_default_python_api(self):
  for name,tool in olnm._STDLIB_TOOLS.items():
   r=subprocess.run([sys.executable,'-c',f'import olnm,sys;sys.exit(olnm.{name}("--help"))'],cwd=self.work,env=self.env,input='',text=True,capture_output=True,timeout=15)
   self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['argv'][-2:],[tool['command'],'--help'])
 def test_bash_zsh_and_run_entrypoints(self):
  for name in olnm._STDLIB_TOOLS:
   self.assertEqual(self.cli('run',name,'--help').returncode,0)
  for shell in ['bash']+(['zsh'] if shutil.which('zsh') else []):
   r=subprocess.run([shell,'-c','eval "$(python3 "$OLNM_PY" init '+shell+')"; xprobe --help'],cwd=self.work,env=self.env,input='',text=True,capture_output=True,timeout=15)
   self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['argv'][-2:],['xprobe','--help'])
 def test_dial_zero_uses_uv_offline_cache_mode(self):
  (self.work/'dial').write_text('0\n');r=self.cli('xprobe','--help')
  self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['argv'][0],'--offline')
 def test_missing_uv_gives_next_step_and_no_registration(self):
  self.uv.unlink();env=dict(self.env,PATH=str(self.bin));r=self.cli('xprobe','--help',env=env)
  self.assertEqual(r.returncode,127);self.assertIn('docs.astral.sh/uv',r.stderr);self.assertEqual(r.stdout,'')
  self.assertFalse((self.work/'state').exists())
 def test_catalog_has_only_fixed_user_repository_sources(self):
  self.assertEqual(set(olnm._STDLIB_TOOLS),{'xprobe','cli_args','ghi','markdown','ascii_artist'})
  for name,t in olnm._STDLIB_TOOLS.items():
   self.assertRegex(t['commit'],r'^[a-f0-9]{40}$');self.assertIn(name,olnm.names());self.assertIn(name,olnm.public())
if __name__=='__main__':unittest.main()
