import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import health_watchdog as hw
class HealthWatchdogTests(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.TemporaryDirectory();self.root=Path(self.d.name);(self.root/'pipeline').mkdir();self.state=self.root/'pipeline/state.json';self.mem=self.root/'health.json';self.old=(hw.ROOT,hw.STATE,hw.MEM);hw.ROOT=self.root;hw.STATE=self.state;hw.MEM=self.mem
 def tearDown(self):hw.ROOT,hw.STATE,hw.MEM=self.old;self.d.cleanup()
 def put(self,updated='2026-07-10T12:00:00+00:00',runs={}):self.state.write_text(json.dumps({'goal':{'status':'ACTIVE'},'updated_at':updated,'runs':runs}))
 def monitor(self):
  o=io.StringIO()
  with contextlib.redirect_stdout(o),patch('health_watchdog.now',return_value=__import__('datetime').datetime.fromisoformat('2026-07-10T12:10:00+00:00')),patch('health_watchdog.alive',return_value=False):hw.main()
  return o.getvalue()
 def test_healthy_silent(self):self.put();self.assertEqual(self.monitor(),'')
 def test_new_incident_once_repeat_silent_recovery_once(self):
  self.put(updated='2026-07-10T10:00:00+00:00');self.assertIn('HEALTH INCIDENT:',self.monitor());self.assertEqual(self.monitor(),'');self.put();self.assertIn('HEALTH RECOVERED:',self.monitor())
 def test_paused_goal_is_not_state_stale(self):
  self.put(updated='2026-07-10T10:00:00+00:00');data=json.loads(self.state.read_text());data['goal']['status']='PAUSED';self.state.write_text(json.dumps(data));self.assertNotIn('state older',self.monitor())
 def test_missing_state_reports_without_initializing(self):
  self.assertIn('state.json is missing',self.monitor());self.assertFalse(self.state.exists())
 def test_never_calls_dispatch_or_spawn(self):
  self.put()
  with patch('subprocess.Popen',side_effect=AssertionError('spawn')),patch('dispatch.reconcile',side_effect=AssertionError('dispatch')):self.assertEqual(self.monitor(),'')
if __name__=='__main__':unittest.main()
