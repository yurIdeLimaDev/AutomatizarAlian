import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
const localPython = resolve(
  '..',
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
);
const python =
  process.env.PYTHON ||
  (existsSync(localPython) ? localPython : process.platform === 'win32' ? 'python' : 'python3');
function run(command, args) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
run(python, ['-B', 'tests/oracle.py']);
run(python, ['-B', '-m', 'pytest', 'tests/test_adapter.py', '-q']);
run(process.execPath, ['scripts/prepare-runtime.mjs']);
run(process.execPath, ['node_modules/typescript/bin/tsc', '--noEmit']);
run(process.execPath, ['node_modules/vite/bin/vite.js', 'build']);
run(process.execPath, ['scripts/check-dist.mjs']);
run(process.execPath, ['--test', 'tests/runtime.test.mjs']);
