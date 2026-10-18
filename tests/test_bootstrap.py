"""Installer contract tests using synthetic file layouts, not live installs."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from scripts.bootstrap import commands, constrain_bmad, wrappers, doctor
from scripts.common import ContractError
from scripts.loop import lint
from tests.support import text

PROJECT=Path(__file__).resolve().parents[1]

class Bootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        shutil.copytree(PROJECT/'.loop',self.root/'.loop')
        shutil.copytree(PROJECT/'.agents',self.root/'.agents')
    def test_pinned_commands_for_three_runtimes(self):
        for runtime in ('codex','claude','opencode'):
            c=commands(self.root,runtime)
            self.assertIn('@opengsd/gsd-core@1.17.0',c[0]); self.assertIn('bmad-method@6.12.4',c[1])
            self.assertNotIn('@latest',json.dumps(c)); self.assertIn('--local',c[0]); self.assertIn('--no-shims',c[1])
    def test_disallowed_scheduler_removed_from_discovery(self):
        for name in ('bmad-build-auto','bmad-sprint-planning','bmad-forge-idea'):
            text(self.root,'.agents/skills/'+name+'/SKILL.md','# synthetic upstream fixture')
        moved=constrain_bmad(self.root)
        self.assertEqual(len(moved),2)
        self.assertTrue((self.root/'.agents/skills/bmad-forge-idea/SKILL.md').exists())
        self.assertFalse((self.root/'.agents/skills/bmad-build-auto/SKILL.md').exists())
    def test_claude_wrappers_are_thin_references(self):
        files=wrappers(self.root,'claude'); self.assertGreaterEqual(len(files),8)
        self.assertIn('.agents/skills/loop/SKILL.md',(self.root/'.claude/skills/loop/SKILL.md').read_text())
    def test_wrapper_rerun_safe(self):
        first=wrappers(self.root,'claude'); self.assertEqual(first,wrappers(self.root,'claude'))
    def test_do_not_overwrite_custom_wrapper(self):
        text(self.root,'.claude/skills/loop/SKILL.md','# user content')
        with self.assertRaisesRegex(ContractError,'user-owned'): wrappers(self.root,'claude')
    def test_doctor_fails_without_upstreams(self):
        with self.assertRaisesRegex(ContractError,'GSD native'): doctor(self.root,'codex')
    def test_loop_package_lints(self): self.assertEqual(lint(PROJECT)['result'],'pass')

if __name__=='__main__': unittest.main()
