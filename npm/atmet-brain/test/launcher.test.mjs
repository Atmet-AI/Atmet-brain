import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { ASSETS, UV_VERSION, runtimeHome, cachedUv, digest, installUv, validDownloadUrl } from '../lib/bootstrap.mjs';
import { bundledEngine, runtimeEnvironment } from '../lib/launcher.mjs';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const metadata = JSON.parse(await fs.readFile(path.join(root, 'package.json'), 'utf8'));
const version = metadata.version;
async function fakePackage(directory) {
  const packageRoot = path.join(directory, 'package');
  await fs.mkdir(packageRoot);
  for (const name of ['bin', 'lib']) await fs.cp(path.join(root, name), path.join(packageRoot, name), {recursive: true});
  await fs.copyFile(path.join(root, 'package.json'), path.join(packageRoot, 'package.json'));
  const vendor = path.join(packageRoot, 'vendor');
  await fs.mkdir(vendor);
  const file = `atmet_brain-${version}-py3-none-any.whl`;
  await fs.writeFile(path.join(vendor, file), 'fixture wheel, never installed by real uv');
  await fs.writeFile(path.join(vendor, 'engine.json'), JSON.stringify({schemaVersion: 1, version, file,
    sha256: await digest(path.join(vendor, file))}));
  return path.join(packageRoot, 'bin', 'atmet-brain.mjs');
}

async function temporary(t) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'atmet-launcher-'));
  t.after(() => fs.rm(directory, {recursive: true, force: true}));
  return directory;
}

async function fakeUv(directory, exitCode = 0) {
  const source = path.join(directory, 'fake-uv.mjs');
  const engine = `#!/usr/bin/env node\nif(process.argv.includes('--version')) console.log('Atmet Brain ${version}');
else if(process.argv.includes('mcp')) process.stdin.pipe(process.stdout);
else {console.log(JSON.stringify({args:process.argv.slice(2),home:process.env.ATMET_HOME}));process.exitCode=Number(process.env.FAKE_CORE_EXIT||0);}`;
  await fs.writeFile(source, `#!/usr/bin/env node
import fs from 'node:fs'; import path from 'node:path';
fs.writeFileSync(process.env.FAKE_CAPTURE,JSON.stringify({args:process.argv.slice(2),stdin:process.env.FAKE_DRAIN_STDIN?fs.readFileSync(0,'utf8'):null,env:{UV_TOOL_DIR:process.env.UV_TOOL_DIR,UV_INDEX_URL:process.env.UV_INDEX_URL,PYTHONPATH:process.env.PYTHONPATH}}));
if(${exitCode}) process.exit(${exitCode});
fs.mkdirSync(process.env.UV_TOOL_BIN_DIR,{recursive:true});
fs.writeFileSync(path.join(process.env.UV_TOOL_BIN_DIR,'atmet-brain'),${JSON.stringify(engine)},{mode:0o700});
console.log('installer message redirected away from protocol stdout');
`, {mode: 0o700});
  return source;
}

test('private cache paths and environment cannot inject package configuration', () => {
  assert.throws(() => runtimeHome({ATMET_LAUNCHER_HOME: 'relative'}));
  const env = runtimeEnvironment('/private/cache', version, {UV_INDEX_URL: 'https://wrong.example', UV_TOOL_DIR: '/wrong',
    PIP_EXTRA_INDEX_URL: 'https://wrong.example', PYTHONPATH: '/wrong', ATMET_HOME: '/company', ATMET_TOKEN: 'fixture'});
  assert.equal(env.UV_INDEX_URL, undefined);
  assert.equal(env.PIP_EXTRA_INDEX_URL, undefined);
  assert.equal(env.PYTHONPATH, undefined);
  assert.equal(env.ATMET_HOME, '/company');
  assert.equal(env.ATMET_TOKEN, 'fixture');
  assert.equal(env.UV_TOOL_DIR, path.join('/private/cache', 'engines', version, 'tools'));
  assert.equal(Object.keys(ASSETS).length, 4);
  assert.equal(metadata.atmetBrain.uv, UV_VERSION);
});

test('uv download redirects stay on HTTPS release hosts', () => {
  for (const url of ['http://github.com/file', 'https://attacker.example/file', 'https://user:pass@github.com/file', 'https://github.com:444/file']) {
    assert.throws(() => validDownloadUrl(url));
  }
  assert.equal(validDownloadUrl('https://release-assets.githubusercontent.com/file').protocol, 'https:');
});

test('uv checksum verified before extraction; cache checked before reuse', async t => {
  const directory = await temporary(t);
  const target = 'fixture-platform';
  const archiveRoot = path.join(directory, 'archive');
  await fs.mkdir(path.join(archiveRoot, 'uv-' + target), {recursive: true});
  await fs.writeFile(path.join(archiveRoot, 'uv-' + target, 'uv'), 'fixture runtime');
  const archive = path.join(directory, 'fixture.tar.gz');
  assert.equal(spawnSync('tar', ['-czf', archive, '-C', archiveRoot, 'uv-' + target]).status, 0);
  const fetchArchive = async (url, destination) => fs.copyFile(archive, destination);
  await assert.rejects(installUv(path.join(directory, 'bad'), target, '0'.repeat(64), fetchArchive), /checksum/);
  const cache = path.join(directory, 'good');
  const executable = await installUv(cache, target, await digest(archive), fetchArchive);
  assert.equal((await fs.stat(executable)).mode & 0o777, 0o700);
  assert.equal(await installUv(cache, target, await digest(archive), () => {throw new Error('must use cache');}), executable);
  await fs.writeFile(executable, 'modified');
  await assert.rejects(cachedUv(path.dirname(executable)), /integrity/);
});

test('launcher installs the bundled wheel, forwards args literally and reuses engine', async t => {
  const directory = await temporary(t);
  const entry = await fakePackage(directory);
  const uv = await fakeUv(directory);
  const capture = path.join(directory, 'capture.json');
  const env = {...process.env, ATMET_LAUNCHER_HOME: path.join(directory, 'cache'), ATMET_UV_BIN: uv,
    FAKE_CAPTURE: capture, ATMET_HOME: '/private/company', UV_INDEX_URL: 'https://wrong.example', PYTHONPATH: '/wrong'};
  const args = ['--home', '/a path/with spaces', 'context', 'text; $(do-not-execute)', '--space', 'sales'];
  const result = spawnSync(process.execPath, [entry, ...args], {env, encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), {args, home: '/private/company'});
  const saved = JSON.parse(await fs.readFile(capture, 'utf8'));
  assert.ok(saved.args.includes(await fs.realpath(path.join(directory, 'package', 'vendor', `atmet_brain-${version}-py3-none-any.whl`))));
  assert.ok(!saved.args.includes(`atmet-brain==${version}`));
  assert.ok(saved.args.includes('https://pypi.org/simple'));
  assert.ok(saved.args.includes('--no-config'));
  assert.equal(saved.env.UV_INDEX_URL, undefined);
  assert.equal(saved.env.PYTHONPATH, undefined);
  await fs.unlink(uv);
  const cached = spawnSync(process.execPath, [entry, '--version'], {env, encoding: 'utf8'});
  assert.equal(cached.status, 0, cached.stderr);
  assert.equal(cached.stdout.trim(), `Atmet Brain ${version}`);
});

test('bootstrap output stays on stderr and MCP input/output stays untouched', async t => {
  const directory = await temporary(t);
  const entry = await fakePackage(directory);
  const uv = await fakeUv(directory);
  const env = {...process.env, ATMET_LAUNCHER_HOME: path.join(directory, 'cache'), ATMET_UV_BIN: uv, FAKE_CAPTURE: path.join(directory, 'capture.json'), FAKE_DRAIN_STDIN: '1'};
  const protocol = '{"jsonrpc":"2.0","id":1,"method":"initialize"}\n';
  const result = spawnSync(process.execPath, [entry, 'mcp'], {env, encoding: 'utf8', input: protocol});
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout, protocol);
  assert.match(result.stderr, /installer message/);
  assert.equal(JSON.parse(await fs.readFile(env.FAKE_CAPTURE, 'utf8')).stdin, '');
});

test('install failures do not fall back to a registry or run a different engine', async t => {
  const directory = await temporary(t);
  const entry = await fakePackage(directory);
  const uv = await fakeUv(directory, 7);
  const result = spawnSync(process.execPath, [entry, 'setup'], {encoding: 'utf8', env: {...process.env,
    ATMET_LAUNCHER_HOME: path.join(directory, 'cache'), ATMET_UV_BIN: uv, FAKE_CAPTURE: path.join(directory, 'capture.json')}});
  assert.equal(result.status, 7);
  assert.equal(result.stdout, '');
  assert.match(result.stderr, /No registry or GitHub core fallback/);
});

test('core exit codes are preserved', async t => {
  const directory = await temporary(t);
  const entry = await fakePackage(directory);
  const uv = await fakeUv(directory);
  const result = spawnSync(process.execPath, [entry, 'status'], {encoding: 'utf8', env: {...process.env,
    ATMET_LAUNCHER_HOME: path.join(directory, 'cache'), ATMET_UV_BIN: uv, FAKE_CAPTURE: path.join(directory, 'capture.json'), FAKE_CORE_EXIT: '9'}});
  assert.equal(result.status, 9);
});


test('missing, modified or wrong-version bundled engines fail before execution', async t => {
  const directory = await temporary(t);
  const entry = await fakePackage(directory);
  const packageRoot = path.dirname(path.dirname(entry));
  const vendor = path.join(packageRoot, 'vendor');
  const wheel = path.join(vendor, `atmet_brain-${version}-py3-none-any.whl`);
  await fs.writeFile(wheel, 'modified wheel');
  await assert.rejects(bundledEngine(metadata, packageRoot), /checksum/);
  await fs.unlink(wheel);
  await assert.rejects(bundledEngine(metadata, packageRoot), /Missing bundled core/);
  const manifest = JSON.parse(await fs.readFile(path.join(vendor, 'engine.json'), 'utf8'));
  manifest.version = '0.0.0';
  await fs.writeFile(path.join(vendor, 'engine.json'), JSON.stringify(manifest));
  await assert.rejects(bundledEngine(metadata, packageRoot), /metadata/);
  const result = spawnSync(process.execPath, [entry, '--version'], {encoding: 'utf8',
    env: {...process.env, ATMET_LAUNCHER_HOME: path.join(directory, 'must-not-exist')}});
  assert.equal(result.status, 1);
  assert.equal(result.stdout, '');
  await assert.rejects(fs.access(path.join(directory, 'must-not-exist')));
});
