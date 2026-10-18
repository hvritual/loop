"""Regressions from actual packaging/native CI. No native execution is simulated as proof."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from distribution import installer as m
from distribution import native

SOURCE=Path(__file__).resolve().parents[1]

class DistributionRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'项目';self.root.mkdir()
        subprocess.run(['git','init','-q',str(self.root)],check=True)

    def test_git_root_decodes_utf8_explicitly(self):
        original=m.subprocess.run
        with patch.object(m.subprocess,'run',wraps=original) as spy:
            self.assertEqual(m.project_root(self.root),self.root.resolve())
            self.assertEqual(spy.call_args.kwargs.get('encoding'),'utf-8')

    def test_failed_post_install_validation_rolls_back(self):
        (self.root/'AGENTS.md').write_text('KEEP',encoding='utf-8')
        with patch.object(m,'doctor',return_value={'result':'fail','integrity_errors':['injected native failure']}):
            with self.assertRaisesRegex(m.InstallError,'Post-install validation'):
                m.install(self.root,SOURCE,skip_upstreams=True)
        self.assertEqual((self.root/'AGENTS.md').read_text(),'KEEP')
        self.assertFalse((self.root/m.MANIFEST).exists())
        self.assertFalse((self.root/'.loop/core/scripts/loop.py').exists())
        self.assertFalse((self.root/m.JOURNAL).exists())

    def test_windows_mode_is_stable_across_first_and_repeat(self):
        for before,actual in ((0o644,0o666),(0o755,0o666),(0o444,0o444)):
            self.assertEqual(m.recorded_mode(before,'nt'),m.recorded_mode(actual,'nt'))
        self.assertEqual(m.recorded_mode(0o755,'posix'),0o755)

    def test_current_process_is_alive(self):
        import os
        self.assertTrue(m.pid_alive(os.getpid()))

    def test_dead_child_process_not_alive(self):
        import sys
        child=subprocess.Popen([sys.executable,'-c','pass']);child.wait()
        self.assertFalse(m.pid_alive(child.pid))

    def test_transaction_validation_runs_on_noop(self):
        with patch.object(m,'doctor',return_value={'result':'fail','integrity_errors':['x']}) as spy:
            with self.assertRaises(m.InstallError):
                m.transaction(self.root,[],lambda:m.check(spy(self.root)['result']=='pass','recheck failed'))

if __name__=='__main__':unittest.main()
