"""Cross-project lifecycle tests. Offline cases do not claim native/model execution."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from distribution import installer as m

SOURCE = Path(__file__).resolve().parents[1]

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='loop lifecycle ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'项目 with spaces'
        self.root.mkdir()
        subprocess.run(['git','init','-q',str(self.root)],check=True)

    def put(self,path,content):
        p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(content if isinstance(content,bytes) else content.encode())

    def get(self,path):return (self.root/path).read_bytes()
    def install(self,**kw):return m.install(self.root,SOURCE,skip_upstreams=True,**kw)
    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.git' not in p.parts and '.loop-cache' not in p.parts}

    def test_clean_install(self):
        r=self.install();self.assertEqual(r['result'],'pass')
        self.assertTrue((self.root/'.loop/core/scripts/loop.py').is_file())
        self.assertFalse((self.root/'scripts').exists())
        self.assertFalse((self.root/'.planning').exists())
        self.assertEqual(len(list((self.root/'.agents/skills').glob('loop*/SKILL.md'))),9)

    def test_project_preservation(self):
        for p in ('README.md','scripts/loop.py','frontend/main.ts','.planning/STATE.md','.agents/skills/my-skill/SKILL.md','.github/workflows/ci.yml'):
            self.put(p,'KEEP '+p)
        before=self.snapshot();self.install()
        for p,data in before.items():self.assertEqual(self.get(p),data)

    def test_idempotent_install(self):
        self.install();before=self.snapshot()
        r=self.install();self.assertEqual(r['changed_files'],[]);self.assertEqual(before,self.snapshot())

    def test_dry_run_does_not_write(self):
        before=self.snapshot();r=self.install(dry_run=True)
        self.assertEqual(before,self.snapshot());self.assertFalse((self.root/'.loop-cache').exists())
        self.assertTrue(r['planned_files'])

    def test_existing_crlf_entry_roundtrip(self):
        original=b'# User rules\r\nPreserve exactly.\r\n'
        self.put('AGENTS.md',original);self.install()
        self.assertTrue(self.get('AGENTS.md').startswith(original))
        m.uninstall(self.root);self.assertEqual(self.get('AGENTS.md'),original)

    def test_unowned_entry_marker_is_conflict(self):
        self.put('AGENTS.md','<!-- loop:start -->\nMine\n<!-- loop:end -->\n')
        before=self.snapshot()
        with self.assertRaises(m.InstallError):self.install()
        self.assertEqual(before,self.snapshot())

    def test_unowned_core_file_conflict(self):
        self.put('.loop/core/scripts/common.py','mine')
        with self.assertRaises(m.InstallError):self.install()
        self.assertEqual(self.get('.loop/core/scripts/common.py'),b'mine')

    def test_existing_config_not_overwritten(self):
        self.put('.loop/checks.json',json.dumps({'schema_version':1,'checks':{'unit':{'argv':['go','test','./...']}}}))
        self.put('.loop/project-rules.json','{"rules":[],"custom":true}')
        before=self.get('.loop/checks.json');self.install()
        self.assertEqual(self.get('.loop/checks.json'),before)

    def test_project_config_survives_update(self):
        self.install();self.put('.loop/project-rules.json','{"rules":[],"owner":"project"}')
        r=m.install(self.root,SOURCE,skip_upstreams=True,mode='update')
        self.assertEqual(r['result'],'pass');self.assertIn(b'project',self.get('.loop/project-rules.json'))

    def test_update_requires_prior_install(self):
        with self.assertRaises(m.InstallError):m.install(self.root,SOURCE,skip_upstreams=True,mode='update')

    def test_modified_owned_file_blocks_update(self):
        self.install();self.put('.loop/core/scripts/loop.py','# user modification')
        before=self.snapshot()
        with self.assertRaises(m.InstallError):m.install(self.root,SOURCE,skip_upstreams=True,mode='update')
        self.assertEqual(before,self.snapshot())

    def test_modified_block_blocks_update(self):
        self.install();self.put('AGENTS.md',self.get('AGENTS.md').replace(b'GSD',b'CHANGED'))
        with self.assertRaises(m.InstallError):self.install()

    def test_user_text_outside_block_survives(self):
        self.install();self.put('AGENTS.md',b'Before\n'+self.get('AGENTS.md')+b'After\n')
        self.install();m.uninstall(self.root)
        self.assertEqual(self.get('AGENTS.md'),b'Before\nAfter\n')

    def test_checks_are_suggestions_not_executed(self):
        self.put('package.json','{"scripts":{"test":"touch NEVER_EXECUTED"}}')
        self.install();c=json.loads(self.get('.loop/checks.json'))
        self.assertEqual(c['checks'],{});self.assertTrue(c['suggested_checks'])
        self.assertFalse((self.root/'NEVER_EXECUTED').exists())
        self.assertEqual(m.doctor(self.root)['project_acceptance'],'needs_configuration')

    def test_explicit_checks_seed(self):
        cfg=Path(self.tmp.name)/'checks.json';cfg.write_text(json.dumps({'schema_version':1,'checks':{'unit':{'argv':['go','test','./...']}}}))
        self.install(checks_file=cfg)
        self.assertEqual(m.doctor(self.root)['project_acceptance'],'configured_not_executed')

    def test_invalid_check_shell_text_rejected(self):
        cfg=Path(self.tmp.name)/'bad.json';cfg.write_text('{"checks":{"bad":{"argv":"rm stuff"}}}')
        with self.assertRaises(m.InstallError):self.install(checks_file=cfg)
        self.assertFalse((self.root/'.loop/core').exists())

    def test_uninstall_keeps_config_and_progress(self):
        self.install();self.put('.planning/STATE.md','keep')
        r=m.uninstall(self.root)
        self.assertEqual(r['result'],'pass');self.assertFalse((self.root/'.loop/core/scripts/loop.py').exists())
        self.assertTrue((self.root/'.loop/checks.json').exists());self.assertEqual(self.get('.planning/STATE.md'),b'keep')
        self.assertFalse((self.root/'AGENTS.md').exists())

    def test_uninstall_retains_modified_owned_file(self):
        self.install();self.put('.agents/skills/loop/SKILL.md','my customization')
        r=m.uninstall(self.root)
        self.assertIn('.agents/skills/loop/SKILL.md',r['retained_modified'])
        self.assertEqual(self.get('.agents/skills/loop/SKILL.md'),b'my customization')

    def test_uninstall_twice(self):
        self.install();m.uninstall(self.root);self.assertEqual(m.uninstall(self.root)['changed_files'],[])

    def test_doctor_detects_drift(self):
        self.install();self.put('.loop/core/scripts/loop.py','changed')
        self.assertEqual(m.doctor(self.root)['result'],'fail')

    def test_doctor_offline_native_not_run(self):
        self.install();r=m.doctor(self.root)
        self.assertEqual(r['native']['codex']['status'],'not_installed')
        self.assertEqual(r['platform_protection'],'not_verified')

    def test_non_git_root_rejected(self):
        root=Path(self.tmp.name)/'not-git';root.mkdir()
        with self.assertRaises(m.InstallError):m.install(root,SOURCE,skip_upstreams=True)

    def test_subdirectory_not_root(self):
        sub=self.root/'sub';sub.mkdir()
        with self.assertRaises(m.InstallError):m.install(sub,SOURCE,skip_upstreams=True)

    def test_symlink_target_rejected(self):
        external=Path(self.tmp.name)/'outside';external.mkdir()
        try:(self.root/'.loop').symlink_to(external,target_is_directory=True)
        except OSError:self.skipTest('symlink permission unavailable')
        with self.assertRaises(m.InstallError):self.install()
        self.assertEqual(list(external.iterdir()),[])

    def test_traversal_manifest_rejected(self):
        self.install();obj=json.loads(self.get('.loop/install-manifest.json'))
        obj['files']['../outside']={'sha256':'a'*64,'kind':'core','mode':420}
        self.put('.loop/install-manifest.json',json.dumps(obj))
        with self.assertRaises(m.InstallError):m.uninstall(self.root)

    def test_concurrent_writer_rejected(self):
        with m.project_lock(self.root):
            with self.assertRaises(m.InstallError):self.install()

    def test_write_failure_rolls_back(self):
        before=self.snapshot();original=m.write_image;count=0
        def fail_once(root,rel,img):
            nonlocal count
            count+=1
            if count==4:raise OSError('injected write failure')
            return original(root,rel,img)
        with patch.object(m,'write_image',side_effect=fail_once):
            with self.assertRaises(OSError):self.install()
        self.assertEqual(before,self.snapshot())

    def test_recovery_after_process_death(self):
        self.put('AGENTS.md','before')
        before=self.snapshot()
        code="""from pathlib import Path
import os,sys
from distribution import installer as m
r=Path(sys.argv[1]); old=m.write_image
count=0
def crash(root,rel,img):
 global count
 old(root,rel,img);count+=1
 if count==4:os._exit(86)
m.write_image=crash
m.install(r,Path(sys.argv[2]),skip_upstreams=True)
"""
        p=subprocess.run([sys.executable,'-c',code,str(self.root),str(SOURCE)],cwd=SOURCE)
        self.assertEqual(p.returncode,86)
        self.assertTrue((self.root/'.loop-cache/install-journal.json').exists())
        m.recover(self.root);self.assertEqual(before,self.snapshot());self.install()

    def test_extra_user_skill_survives(self):
        self.put('.agents/skills/bmad-user-workflow/SKILL.md','my workflow')
        self.install();m.uninstall(self.root)
        self.assertEqual(self.get('.agents/skills/bmad-user-workflow/SKILL.md'),b'my workflow')

    def test_installed_core_is_runnable(self):
        self.install()
        p=subprocess.run([sys.executable,str(self.root/'.loop/core/scripts/loop.py'),'--root',str(self.root),'lint'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_all_skill_commands_are_relocated(self):
        self.install()
        for p in (self.root/'.agents/skills').rglob('*.md'):
            self.assertNotIn('python scripts/',p.read_text())

    def test_claude_wrapper_present_offline(self):
        self.install(runtime='claude')
        self.assertTrue((self.root/'.claude/skills/loop/SKILL.md').exists())
        self.assertTrue((self.root/'CLAUDE.md').exists())

    def test_new_version_upgrade_and_retired_file(self):
        src=Path(self.tmp.name)/'release'
        shutil.copytree(SOURCE,src,ignore=shutil.ignore_patterns('.git','.planning','.loop-cache','__pycache__'))
        (src/'distribution/extra.py').write_text('# versioned helper')
        m.install(self.root,src,skip_upstreams=True)
        self.put('.planning/STATE.md','preserved')
        pkg=json.loads((src/'package.json').read_text());pkg['version']='0.2.1'
        (src/'package.json').write_text(json.dumps(pkg));(src/'distribution/extra.py').unlink()
        r=m.install(self.root,src,skip_upstreams=True,mode='update')
        self.assertEqual(r['version'],'0.2.1')
        self.assertFalse((self.root/'.loop/core/distribution/extra.py').exists())
        self.assertEqual(self.get('.planning/STATE.md'),b'preserved')

    def test_identical_unowned_file_remains_shared(self):
        self.put('.loop/core/scripts/common.py',(SOURCE/'scripts/common.py').read_bytes())
        self.install();r=m.doctor(self.root);self.assertEqual(r['result'],'pass')
        self.put('.loop/core/scripts/common.py','user edit')
        self.assertEqual(m.doctor(self.root)['result'],'fail')
        m.uninstall(self.root);self.assertEqual(self.get('.loop/core/scripts/common.py'),b'user edit')

    def test_malformed_block_manifest_rejected(self):
        import base64
        self.install();obj=json.loads(self.get('.loop/install-manifest.json'))
        obj['blocks']['AGENTS.md']=base64.b64encode(b'user owned content').decode()
        self.put('.loop/install-manifest.json',json.dumps(obj))
        with self.assertRaises(m.InstallError):m.uninstall(self.root)

    def test_recovery_refuses_later_edits(self):
        self.put('AGENTS.md','original')
        op={'path':'AGENTS.md','before':m.image(self.root,'AGENTS.md'),'after':m.bytes_image(b'installed')}
        self.put('.loop-cache/install-journal.json',json.dumps({'schema_version':1,'operations':[op]}))
        self.put('AGENTS.md','later user edit')
        with self.assertRaises(m.InstallError):m.recover(self.root)
        self.assertEqual(self.get('AGENTS.md'),b'later user edit')
        self.assertTrue((self.root/'.loop-cache/install-journal.json').exists())

    def test_missing_managed_file_is_repaired(self):
        self.install();(self.root/'.loop/core/scripts/loop.py').unlink()
        self.assertEqual(m.doctor(self.root)['result'],'fail')
        self.install();self.assertEqual(m.doctor(self.root)['result'],'pass')

    def test_installed_offline_lifecycle_launcher(self):
        self.install()
        p=subprocess.run(['node',str(self.root/'.loop/core/bin/loop.cjs'),'doctor','--project',str(self.root)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        p=subprocess.run(['node',str(self.root/'.loop/core/bin/loop.cjs'),'uninstall','--project',str(self.root)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_gitignore_roundtrip(self):
        original=b'private-output/\n.env\n'
        self.put('.gitignore',original);self.install();m.uninstall(self.root)
        self.assertEqual(self.get('.gitignore'),original)

    def test_source_approval_records_not_copied(self):
        self.install()
        for p in self.root.rglob('*'):
            if p.is_file() and '.git' not in p.parts and '.loop-cache' not in p.parts:
                self.assertNotIn(b'LOOP-BOOTSTRAP',p.read_bytes(),p)

if __name__=='__main__':unittest.main()
