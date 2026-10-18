#!/usr/bin/env python3
"""Public CLI: artifact checks, evidence and handoff only. GSD does the scheduling."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.common import ContractError, read, require, resolve
from scripts.gates import gate, learning, STAGES
from scripts.evidence import capture
from scripts.context import checkpoint, resume

def lint(root: Path) -> dict:
    rules=read(root,'.loop/rules.json')['rules']
    require(len({r['id'] for r in rules})==len(rules),'Duplicate rule IDs')
    require(len(rules)<=20,'Rule budget exceeded; consolidate instead of appending')
    for r in rules:
        require(r.get('enforcement') in {'instruction','check','platform'},'Declare the actual enforcement level')
        require(r.get('scope') and r.get('failure_action') and r.get('origin'),'Rules need scope, failure route and origin')
    skills=list((root/'.agents/skills').glob('loop*/SKILL.md'))
    require(len(skills)>=8,'Missing Loop skills')
    for p in skills:
        text=p.read_text(encoding='utf-8')
        require(text.startswith('---\n') and f'name: {p.parent.name}\n' in text,'Invalid skill name/frontmatter: '+str(p))
        require('description: ' in text,'Missing skill description')
        require(len(text.splitlines())<=250,'Skill too large: use progressive disclosure')
    require(read(root,'.loop/upstreams.lock.json')['gsd']['version']=='1.17.0','Unexpected GSD pin: review compatibility before upgrade')
    require(read(root,'.loop/upstreams.lock.json')['bmad']['version']=='6.12.4','Unexpected BMAD pin: review compatibility before upgrade')
    return {'result':'pass','rules':len(rules),'skills':len(skills)}

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('lint')
    g=sub.add_parser('gate'); g.add_argument('target'); g.add_argument('stage',choices=STAGES)
    e=sub.add_parser('evidence'); e.add_argument('check'); e.add_argument('--intent')
    r=sub.add_parser('resume'); r.add_argument('target')
    c=sub.add_parser('checkpoint'); c.add_argument('target'); c.add_argument('--next',required=True)
    l=sub.add_parser('learning'); l.add_argument('path')
    args=parser.parse_args(); root=args.root.resolve()
    try:
        if args.command=='lint': result=lint(root)
        elif args.command=='gate': result=gate(root,args.target,args.stage)
        elif args.command=='evidence':
            result=capture(root,args.check,args.intent)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0 if result['exit_code']==0 and result['source_unchanged'] and result['contract_unchanged'] else 1
        elif args.command=='resume': result=resume(root,args.target)
        elif args.command=='checkpoint': result=checkpoint(root,args.target,args.next)
        else:
            learning(root,args.path); result={'result':'pass'}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ContractError,KeyError,TypeError,ValueError,OSError) as exc:
        print(json.dumps({'result':'fail','reason':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
