#!/usr/bin/env python3
"""Loop distribution lifecycle entry. Run explicitly; never an npm lifecycle hook."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from distribution.installer import InstallError, install, doctor, uninstall, recover


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('install','update','doctor','uninstall','recover'))
    parser.add_argument('--project',type=Path,default=Path.cwd())
    parser.add_argument('--runtime',choices=('codex','claude','opencode'))
    parser.add_argument('--skip-upstreams',action='store_true',help='Offline core-only install; NOT native-ready')
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--checks',type=Path,help='Reviewed checks JSON; seeds only a missing project registry')
    parser.add_argument('--require-native',action='store_true',help='doctor: fail unless all selected native adapters validate')
    parser.add_argument('--require-project-checks',action='store_true',help='doctor: fail when no real project check is configured')
    args=parser.parse_args()
    try:
        if args.command in ('install','update'):
            result=install(args.project,SOURCE,runtime=args.runtime,skip_upstreams=args.skip_upstreams,dry_run=args.dry_run,checks_file=args.checks,mode=args.command)
        elif args.command=='doctor':
            result=doctor(args.project)
            if args.require_native and any(v['status']!='installed' for v in result['native'].values()):result['result']='fail'
            if args.require_project_checks and result['project_acceptance']=='needs_configuration':result['result']='fail'
        elif args.command=='uninstall':result=uninstall(args.project,dry_run=args.dry_run)
        else:
            if args.dry_run:raise InstallError('recover requires explicit execution; inspect the local journal first')
            result=recover(args.project)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['result']=='pass' else 1
    except (InstallError,OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'result':'fail','reason':str(exc)},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
