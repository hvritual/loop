#!/usr/bin/env node
'use strict';
// No install/postinstall hooks. A package download alone never mutates a project.
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const args = process.argv.slice(2);
if (args.includes('--version')) {
  console.log(require('../package.json').version);
  process.exit(0);
}
const candidates = process.env.LOOP_PYTHON
  ? [[process.env.LOOP_PYTHON]]
  : (process.platform === 'win32' ? [['py', '-3'], ['python'], ['python3']] : [['python3'], ['python']]);
const env = {...process.env, PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1'};
for (const [exe, ...prefix] of candidates) {
  const probe = spawnSync(exe, [...prefix, '-c', 'import sys;sys.exit(0 if sys.version_info >= (3,11) else 1)'], {env, stdio: 'ignore', shell: false});
  if (probe.status !== 0) continue;
  const result = spawnSync(exe, [...prefix, path.join(__dirname, '../distribution/cli.py'), ...args], {env, stdio: 'inherit', shell: false});
  if (result.error) console.error(result.error.message);
  process.exit(result.status === null ? 1 : result.status);
}
console.error('Loop requires Python 3.11+. Install it or set LOOP_PYTHON to its executable path.');
process.exit(1);
