"""Small artifact utilities. No scheduler, model client or workflow state database."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

class ContractError(ValueError):
    pass

def require(ok: object, message: str) -> None:
    if not ok:
        raise ContractError(message)

def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip().lower() not in {'todo', 'tbd', 'unknown', '待补充'}

def resolve(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and relative and '\\' not in relative, 'Path must be a nonempty repository-relative POSIX path')
    p = (root / relative).resolve()
    require(not Path(relative).is_absolute() and p.is_relative_to(root.resolve()), f'Path escapes repository: {relative}')
    return p

def read(root: Path, relative: str) -> Any:
    p = resolve(root, relative)
    require(p.is_file(), f'Missing artifact: {relative}')
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError) as exc:
        raise ContractError(f'Invalid JSON in {relative}: {exc}') from exc

def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def digest(root: Path, relative: str) -> str:
    p = resolve(root, relative)
    require(p.is_file(), f'Missing artifact: {relative}')
    return digest_bytes(p.read_bytes())

def stable(value: Any) -> str:
    return digest_bytes(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())

def write(root: Path, relative: str, value: Any) -> None:
    """Replace one JSON artifact atomically; never a multi-writer transaction."""
    p = resolve(root, relative)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    fd, name = tempfile.mkstemp(prefix='.loop-', dir=p.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, p)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def git(root: Path, *args: str, optional: bool = False) -> str:
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, timeout=30)
    if result.returncode and not optional:
        raise ContractError(result.stderr.strip() or 'Git failed')
    return result.stdout.strip() if result.returncode == 0 else ''

def file_set(root: Path) -> dict[str, str]:
    """Track application, rules, skills and tests; omit only known generated/state roots.

    Git's file list includes new nonignored files. Evidence excludes .planning to
    avoid self-reference; intent/spec/plan hashes are validated separately.
    """
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-co', '--exclude-standard', '-z'], capture_output=True, timeout=30)
    require(result.returncode == 0, 'A Git workspace is required for source-bound evidence')
    excluded = ('.planning/', '.loop-cache/', '_bmad/', '_bmad-output/', 'node_modules/', '.claude/', '.codex/', '.opencode/', '.gemini/')
    names = set(result.stdout.decode('utf-8').split('\0')) - {''}
    files = {}
    for name in sorted(names):
        if name.startswith(excluded) or '/__pycache__/' in '/'+name or name.endswith(('.pyc', '.pyo')):
            continue
        if name.startswith(('.agents/skills/bmad-', '.agents/skills/gsd-')):
            continue
        p = resolve(root, name)
        if p.is_file():
            files[name] = digest_bytes(p.read_bytes())
    require(files, 'Empty source set cannot support verification')
    return files

def source_digest(root: Path) -> str:
    return stable(file_set(root))

def target_dir(target: str) -> str:
    require(bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', target)), 'Invalid intent ID')
    return '.planning/intents/' + target

def unique(items: list[dict], label: str) -> set[str]:
    require(isinstance(items, list) and bool(items), f'{label} must be a nonempty list')
    ids = [i.get('id') for i in items if isinstance(i, dict)]
    require(len(ids) == len(items) and all(nonempty(i) for i in ids), f'{label} need IDs')
    require(len(set(ids)) == len(ids), f'Duplicate {label} IDs')
    return set(ids)


def contract_files(root: Path, base: str) -> list[str]:
    """Upstream inputs only: exclude evidence indexes/checkpoints to avoid cycles."""
    refs={base+'/'+name for name in ('intent.json','spec.json','design.json','plan-map.json') if resolve(root,base+'/'+name).is_file()}
    if base+'/design.json' in refs:
        design=read(root,base+'/design.json')
        for key in ('architecture','journeys','failure_recovery','test_strategy','preview'):
            ref=design.get(key,{})
            if ref.get('path'): refs.add(ref['path'])
    if base+'/plan-map.json' in refs:
        for plan in read(root,base+'/plan-map.json').get('plans',[]):
            if plan.get('path'): refs.add(plan['path'])
    return sorted(refs)

def contract_digest(root: Path, base: str) -> str:
    refs=contract_files(root,base)
    require(base+'/intent.json' in refs,'Intent is required for contract-bound evidence')
    return stable({p:digest(root,p) for p in refs})
