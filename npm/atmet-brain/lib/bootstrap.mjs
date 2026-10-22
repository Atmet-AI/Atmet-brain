import { createHash } from 'node:crypto';
import { createWriteStream } from 'node:fs';
import * as fs from 'node:fs/promises';
import https from 'node:https';
import os from 'node:os';
import path from 'node:path';
import { pipeline } from 'node:stream/promises';
import { Transform } from 'node:stream';
import { spawnSync } from 'node:child_process';

export const UV_VERSION = '0.13.5';
export const ASSETS = {
  'darwin-arm64': ['aarch64-apple-darwin', '743f85035a1996ecb350659e01cd9faea9709829be09b1b4b03c73eaf3c9cd73'],
  'darwin-x64': ['x86_64-apple-darwin', 'b0f52b0e3945b4107d89024ea38e625683011fbfc05a0d98f9fa2d6dcee28c66'],
  'linux-arm64': ['aarch64-unknown-linux-gnu', '4bb69cf95ed13f23713bb7bc09f241896ea0c75b7c557e615a20604b82f9c403'],
  'linux-x64': ['x86_64-unknown-linux-gnu', 'f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f'],
};

export function runtimeHome(env = process.env) {
  if (env.ATMET_LAUNCHER_HOME) {
    if (!path.isAbsolute(env.ATMET_LAUNCHER_HOME)) throw new Error('ATMET_LAUNCHER_HOME must be an absolute path.');
    return env.ATMET_LAUNCHER_HOME;
  }
  const base = process.platform === 'darwin' ? path.join(os.homedir(), 'Library', 'Application Support')
    : (env.XDG_DATA_HOME && path.isAbsolute(env.XDG_DATA_HOME) ? env.XDG_DATA_HOME : path.join(os.homedir(), '.local', 'share'));
  return path.join(base, 'atmet-brain', 'runtime');
}

export async function digest(file) {
  const hash = createHash('sha256');
  const handle = await fs.open(file, 'r');
  try {
    for await (const chunk of handle.createReadStream()) hash.update(chunk);
  } finally {
    await handle.close();
  }
  return hash.digest('hex');
}

export function validDownloadUrl(value) {
  const url = new URL(value);
  const hosts = new Set(['github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com']);
  if (url.protocol !== 'https:' || !hosts.has(url.hostname) || url.username || url.password || (url.port && url.port !== '443')) {
    throw new Error('Unexpected uv download destination.');
  }
  return url;
}

export async function download(url, output, redirects = 0) {
  if (redirects > 5) throw new Error('Too many uv download redirects.');
  const response = await new Promise((resolve, reject) => {
    const request = https.get(validDownloadUrl(url), {rejectUnauthorized: true}, resolve);
    request.setTimeout(30_000, () => request.destroy(new Error('uv download timed out.')));
    request.on('error', reject);
  });
  if ([301, 302, 303, 307, 308].includes(response.statusCode)) {
    response.resume();
    if (!response.headers.location) throw new Error('Invalid uv download redirect.');
    return download(new URL(response.headers.location, url).href, output, redirects + 1);
  }
  if (response.statusCode !== 200) {
    response.resume();
    throw new Error('The official uv runtime download failed. Check network access or supply ATMET_UV_BIN.');
  }
  response.setTimeout(30_000, () => response.destroy(new Error('uv download timed out.')));
  let size = 0;
  const bound = new Transform({transform(chunk, encoding, callback) {
    size += chunk.length;
    callback(size > 100 * 1024 * 1024 ? new Error('uv archive exceeds the download limit.') : null, chunk);
  }});
  await pipeline(response, bound, createWriteStream(output, {flags: 'wx', mode: 0o600}));
}

export async function cachedUv(directory) {
  try {
    const executable = path.join(directory, 'uv');
    const [binary, metadata] = await Promise.all([fs.lstat(executable), fs.lstat(path.join(directory, 'integrity.json'))]);
    if (!binary.isFile() || !metadata.isFile()) throw new Error('Unsafe cached runtime.');
    const saved = JSON.parse(await fs.readFile(path.join(directory, 'integrity.json'), 'utf8'));
    if (saved.version !== UV_VERSION || await digest(executable) !== saved.sha256) throw new Error('Cached uv failed its integrity check.');
    return executable;
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

export async function installUv(cache, target, expected, fetchArchive = download) {
  const parent = path.join(cache, 'uv', UV_VERSION);
  const directory = path.join(parent, target);
  const existing = await cachedUv(directory);
  if (existing) return existing;
  await fs.mkdir(parent, {recursive: true, mode: 0o700});
  const temporary = await fs.mkdtemp(path.join(parent, '.install-'));
  try {
    const archive = path.join(temporary, 'uv.tar.gz');
    await fetchArchive(`https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${target}.tar.gz`, archive);
    if (await digest(archive) !== expected) throw new Error('uv archive checksum verification failed. Nothing executed.');
    const extracted = spawnSync('tar', ['-xzf', archive, '-C', temporary, `uv-${target}/uv`], {encoding: 'utf8', timeout: 30_000});
    if (extracted.error || extracted.status !== 0) throw new Error('Cannot unpack uv. Install tar or supply ATMET_UV_BIN.');
    const source = path.join(temporary, `uv-${target}`, 'uv');
    if (!(await fs.lstat(source)).isFile()) throw new Error('uv archive did not contain a regular executable.');
    const ready = path.join(temporary, 'ready');
    await fs.mkdir(ready, {mode: 0o700});
    await fs.rename(source, path.join(ready, 'uv'));
    await fs.chmod(path.join(ready, 'uv'), 0o700);
    await fs.writeFile(path.join(ready, 'integrity.json'), JSON.stringify({version: UV_VERSION, sha256: await digest(path.join(ready, 'uv'))}), {mode: 0o600});
    try {
      await fs.rename(ready, directory);
    } catch (error) {
      if (!['EEXIST', 'ENOTEMPTY'].includes(error.code) || !(await cachedUv(directory))) throw error;
    }
    return await cachedUv(directory);
  } finally {
    await fs.rm(temporary, {recursive: true, force: true});
  }
}

export async function resolveUv(cache, env = process.env) {
  const asset = ASSETS[`${process.platform}-${process.arch}`];
  if (!asset) throw new Error('This launcher supports macOS and Linux x64/arm64. Windows is not yet validated.');
  if (env.ATMET_UV_BIN) {
    if (!path.isAbsolute(env.ATMET_UV_BIN)) throw new Error('ATMET_UV_BIN must be an absolute path to a trusted uv executable.');
    return env.ATMET_UV_BIN;
  }
  if (process.platform === 'linux' && !process.report.getReport().header.glibcVersionRuntime) {
    throw new Error('Automatic Linux bootstrap requires glibc. Supply a compatible uv through ATMET_UV_BIN on other systems.');
  }
  process.stderr.write('Atmet Brain: preparing the verified Python package manager...\n');
  return installUv(cache, ...asset);
}
