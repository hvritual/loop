#!/usr/bin/env python3
"""Install reviewed upstream releases, restrict BMAD discovery, expose Loop skills.

This runs the OFFICIAL installers. It does not copy raw GSD agent definitions or
implement a model adapter. Needs network/npm; no model login is performed here.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.common import ContractError, require, read, write, resolve, digest

ROOTS=('.agents/skills','.claude/skills','.codex/skills','.opencode/skills')

def commands(root: Path, runtime: str, npx: str='npx') -> list[list[str]]:
    lock=read(root,'.loop/upstreams.lock.json')
    require(runtime in lock['runtimes'],'Unsupported runtime')
    adapter=lock['runtimes'][runtime]
    return [
        [npx,'--yes',lock['gsd']['package']+'@'+lock['gsd']['version'],adapter['gsd_flag'],'--local'],
        [npx,'--yes',lock['bmad']['package']+'@'+lock['bmad']['version'],'install','--directory',str(root),'--modules','bmm','--tools',adapter['bmad_tool'],'--no-shims','--yes','--communication-language','Chinese','--document-output-language','Chinese','--output-folder','_bmad-output'],
    ]

def skill_files(root: Path, prefix: str) -> list[Path]:
    return sorted({p for folder in ROOTS for p in (root/folder).glob(prefix+'*/SKILL.md')})

def constrain_bmad(root: Path) -> list[str]:
    """Move only generated disallowed BMAD skills out of native discovery roots.

    Never modify their upstream definitions. This reduces accidental dispatch;
    it is NOT a security boundary against a principal with filesystem access.
    """
    allowed=set(read(root,'.loop/upstreams.lock.json')['bmad_allowlist'])
    disabled=[]
    for skill in skill_files(root,'bmad-'):
        if skill.parent.name in allowed: continue
        relative=skill.parent.relative_to(root)
        dest=root/'.loop-cache/disabled-bmad'/relative
        require(not dest.exists(),'Existing disabled skill backup; review before replacing: '+str(dest))
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(skill.parent),str(dest))
        disabled.append(relative.as_posix())
    # OpenCode's BMAD installer may also expose shortcut commands.
    for command in (root/'.opencode/commands').glob('bmad*.md'):
        if command.stem not in allowed:
            dest=root/'.loop-cache/disabled-bmad'/command.relative_to(root)
            dest.parent.mkdir(parents=True,exist_ok=True)
            require(not dest.exists(),'Existing command backup requires review')
            shutil.move(str(command),str(dest)); disabled.append(command.relative_to(root).as_posix())
    return disabled

def wrappers(root: Path, runtime: str) -> list[str]:
    lock=read(root,'.loop/upstreams.lock.json')
    native=root/lock['runtimes'][runtime]['skill_root']
    canonical=root/'.agents/skills'
    written=[]
    if native==canonical: return written
    for skill in sorted(canonical.glob('loop*/SKILL.md')):
        target=native/skill.parent.name/'SKILL.md'
        marker='<!-- loop-generated-wrapper -->'
        if target.exists():
            require(marker in target.read_text(encoding='utf-8'),'Refusing to overwrite a user-owned skill: '+str(target))
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text('---\nname: '+skill.parent.name+'\ndescription: Load the canonical '+skill.parent.name+' delivery skill for this repository.\n---\n\n'+marker+'\nRead `'+skill.relative_to(root).as_posix()+'` in full from the repository root, then follow it. Resolve its relative resources against that canonical skill directory. Do not maintain a duplicate workflow here.\n',encoding='utf-8')
        written.append(target.relative_to(root).as_posix())
    return written

def doctor(root: Path, runtime: str) -> dict:
    lock=read(root,'.loop/upstreams.lock.json')
    require(runtime in lock['runtimes'],'Unsupported runtime')
    # Check the runtime selected, not an unrelated globally-installed copy.
    gsd_root={'codex':'.codex','claude':'.claude','opencode':'.opencode'}[runtime]
    gsd=list((root/gsd_root).glob('skills/gsd-*/SKILL.md'))
    commands_found=list((root/gsd_root).glob('commands/**/plan-phase.md'))+list((root/gsd_root).glob('commands/gsd-plan-phase.md'))
    require(gsd or commands_found,'GSD native surface is missing for '+runtime)
    bmad_root=root/lock['runtimes'][runtime]['skill_root']
    found={p.parent.name for p in bmad_root.glob('bmad-*/SKILL.md')}
    missing=set(lock['bmad_required'])-found
    require(not missing,'Required BMAD capabilities missing: '+', '.join(sorted(missing)))
    require(found <= set(lock['bmad_allowlist']),'Second BMAD execution surface remains enabled')
    for name in ('resolve_config.py','resolve_customization.py'):
        require((root/'_bmad/scripts'/name).is_file(),'BMAD shared support script missing: '+name)
    for name in ('loop','loop-intent','loop-resume','loop-verify'):
        require((bmad_root/name/'SKILL.md').is_file(),'Loop native entry missing: '+name)
    return {'result':'pass','runtime':runtime,'gsd_native_entries':len(gsd)+len(commands_found),'bmad_advisory_skills':sorted(found),'boundary':'Installed artifact compatibility only; no live model execution or authenticated deployment has been tested.'}

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path.cwd())
    p.add_argument('--runtime',choices=['codex','claude','opencode'],required=True)
    p.add_argument('--print-only',action='store_true')
    p.add_argument('--doctor',action='store_true')
    args=p.parse_args(); root=args.root.resolve()
    try:
        if args.print_only:
            print(json.dumps(commands(root,args.runtime),indent=2)); return 0
        if args.doctor:
            print(json.dumps(doctor(root,args.runtime),ensure_ascii=False,indent=2)); return 0
        npx=shutil.which('npx.cmd' if sys.platform=='win32' else 'npx')
        require(npx,'Node.js/npm is required. Install Node 22+ and retry.')
        require(shutil.which('uv'),'BMAD needs uv on PATH; install uv through its official instructions first.')
        cache=root/'.loop-cache'; cache.mkdir(exist_ok=True)
        protected=['AGENTS.md','CLAUDE.md','GEMINI.md','.loop/rules.json']
        protected += [p.relative_to(root).as_posix() for p in (root/'.planning').rglob('*') if p.is_file()]
        before={ref:digest(root,ref) for ref in protected if resolve(root,ref).is_file()}
        for index,argv in enumerate(commands(root,args.runtime,npx)):
            log=cache/f'install-{args.runtime}-{index}.log'
            with log.open('wb') as stream:
                result=subprocess.run(argv,cwd=root,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=900,shell=False)
            require(result.returncode==0,'Official installer failed; inspect '+str(log))
        changed=[ref for ref,sha in before.items() if not resolve(root,ref).is_file() or digest(root,ref)!=sha]
        require(not changed,'Installer changed protected context; stop and reconcile: '+', '.join(changed))
        disabled=constrain_bmad(root)
        exposed=wrappers(root,args.runtime)
        report={**doctor(root,args.runtime),'disabled':disabled,'wrappers':exposed,'verified_at':datetime.now(timezone.utc).isoformat(),'lock_sha256':digest(root,'.loop/upstreams.lock.json')}
        write(root,'.loop-cache/install-'+args.runtime+'.json',report)
        print(json.dumps(report,ensure_ascii=False,indent=2)); return 0
    except (ContractError,ValueError,OSError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'result':'fail','reason':str(exc)}),file=sys.stderr); return 1

if __name__=='__main__': raise SystemExit(main())
