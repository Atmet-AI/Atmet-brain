import * as fs from 'node:fs/promises';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { constants } from 'node:os';
import { runtimeHome, resolveUv } from './bootstrap.mjs';

export function runtimeEnvironment(cache, version, env = process.env) {
  // Project/user Python package configuration must not change the pinned engine.
  const result = Object.fromEntries(Object.entries(env).filter(([key]) => !key.startsWith('UV_') && !key.startsWith('PIP_')
    && !['PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'].includes(key)));
  const root = path.join(cache, 'engines', version);
  return {...result, PATH: path.join(root, 'bin') + path.delimiter + (result.PATH || ''),
    UV_TOOL_DIR: path.join(root, 'tools'), UV_TOOL_BIN_DIR: path.join(root, 'bin'),
    UV_CACHE_DIR: path.join(cache, 'packages'), UV_PYTHON_INSTALL_DIR: path.join(cache, 'python'), UV_NO_PROGRESS: '1'};
}

export async function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {stdio: 'inherit', ...options, shell: false});
    const interrupt = () => child.kill('SIGINT');
    const terminate = () => child.kill('SIGTERM');
    process.on('SIGINT', interrupt);
    process.on('SIGTERM', terminate);
    const cleanup = () => {process.off('SIGINT', interrupt); process.off('SIGTERM', terminate);};
    child.once('error', () => {cleanup(); reject(new Error('Cannot start the Atmet runtime. Check its installation and executable permissions.'));});
    child.once('close', (code, signal) => {cleanup(); resolve(code ?? (128 + (constants.signals[signal] || 1)));});
  });
}

export async function launch(args, metadata, env = process.env) {
  const version = metadata.atmetBrain.engineVersion;
  if (!/^\d+\.\d+\.\d+$/.test(version) || version !== metadata.version) throw new Error('Launcher and engine versions do not match.');
  const cache = runtimeHome(env);
  const environment = runtimeEnvironment(cache, version, env);
  const executable = path.join(environment.UV_TOOL_BIN_DIR, 'atmet-brain');
  await fs.mkdir(cache, {recursive: true, mode: 0o700});
  const expected = `Atmet Brain ${version}`;
  let ready = false;
  try {
    const info = await fs.lstat(executable);
    if (info.isFile() || info.isSymbolicLink()) {
      const probe = spawnSync(executable, ['--version'], {encoding: 'utf8', env: environment, timeout: 15_000});
      ready = !probe.error && probe.status === 0 && probe.stdout.trim() === expected;
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  if (!ready) {
    const uv = await resolveUv(cache, env);
    process.stderr.write(`Atmet Brain: installing core ${version} from PyPI into a private environment...\n`);
    const status = await run(uv, ['--no-config', 'tool', 'install', '--python', metadata.atmetBrain.python,
      '--default-index', 'https://pypi.org/simple', `atmet-brain==${version}`], {env: environment, stdio: ['ignore', 2, 2]});
    if (status !== 0) {
      process.stderr.write('Atmet Brain: core installation failed. Check the official PyPI release and network access. No GitHub-wheel fallback is used.\n');
      return status;
    }
    const probe = spawnSync(executable, ['--version'], {encoding: 'utf8', env: environment, timeout: 15_000});
    if (probe.error || probe.status !== 0 || probe.stdout.trim() !== expected) throw new Error('Installed engine did not match the launcher version.');
  }
  return run(executable, args, {env: environment});
}
