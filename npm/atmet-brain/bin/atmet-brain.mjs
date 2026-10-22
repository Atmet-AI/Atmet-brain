#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { launch } from '../lib/launcher.mjs';

try {
  const [major, minor] = process.versions.node.split('.').map(Number);
  if (major < 22 || (major === 22 && minor < 14)) throw new Error('Use Node.js 22.14 or newer.');
  const metadata = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));
  process.exitCode = await launch(process.argv.slice(2), metadata);
} catch (error) {
  const message = String(error.message || 'Launcher failed.').replace(/[\x00-\x1f\x7f-\x9f]/g, ' ');
  process.stderr.write(`Atmet Brain: ${message}\n`);
  process.exitCode = 1;
}
