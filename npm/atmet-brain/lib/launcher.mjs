import * as fs from 'node:fs/promises';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { constants } from 'node:os';
import { fileURLToPath } from 'node:url';
import { digest, runtimeHome, resolveUv } from './bootstrap.mjs';

export async function bundledEngine(metadata, root = fileURLToPath(new URL('../', import.meta.url))) {
  const version = metadata.atmetBrain.engineVersion;
  const filename = `atmet_brain-${version}-py3-none-any.whl`;
  const directory = path.join(root, 'vendor');
  try {
    const manifestPath = path.join(directory, 'engine.json');
    if (!(await fs.lstat(manifestPath)).isFile()) throw new Error('Unsafe bundled engine manifest.');
    const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
    if (manifest.schemaVersion !== 1 || manifest.version !== version || manifest.file !== filename
      || !/^[a-f0-9]{64}$/.test(manifest.sha256)) throw new Error('Bundled engine metadata does not match the launcher.');
    const wheel = path.join(directory, filename);
    if (!(await fs.lstat(wheel)).isFile() || await digest(wheel) !== manifest.sha256) {
      throw new Error('Bundled engine checksum verification failed. Nothing installed.');
    }
    return wheel;
  } catch (error) {
    if (error.code === 'ENOENT') throw new Error('Missing bundled core. Maintainers must run scripts/prepare_npm.py before npm pack.');
    throw error;
  }
}

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
  const wheel = await bundledEngine(metadata);
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
    process.stderr.write(`Atmet Brain: installing bundled core ${version} into a private environment...\n`);
    const status = await run(uv, ['--no-config', 'tool', 'install', '--python', metadata.atmetBrain.python,
      '--default-index', 'https://pypi.org/simple', wheel], {env: environment, stdio: ['ignore', 2, 2]});
    if (status !== 0) {
      process.stderr.write('Atmet Brain: bundled core installation failed. Check Python/dependency network access. No registry or GitHub core fallback is used.\n');
      return status;
    }
    const probe = spawnSync(executable, ['--version'], {encoding: 'utf8', env: environment, timeout: 15_000});
    if (probe.error || probe.status !== 0 || probe.stdout.trim() !== expected) throw new Error('Installed engine did not match the launcher version.');
  }
  return run(executable, args, {env: environment});
}
