import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

// Exercise the actual consumers of the scoped glob/minimatch security overrides.
const require = createRequire(import.meta.url);
const { nodeFileTrace } = require('@vercel/nft');
const readdirGlob = require('readdir-glob');

test('Nitro file tracing includes dynamically required modules', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'e187-trace-'));
  try {
    await mkdir(join(directory, 'plugins'));
    await writeFile(
      join(directory, 'entry.cjs'),
      "module.exports = require('./plugins/' + process.env.PLUGIN + '.cjs');",
    );
    await writeFile(
      join(directory, 'plugins', 'one.cjs'),
      'module.exports = 1;',
    );
    await writeFile(
      join(directory, 'plugins', 'two.cjs'),
      'module.exports = 2;',
    );
    await writeFile(
      join(directory, 'plugins', 'unrelated.txt'),
      'not a module',
    );

    const { fileList } = await nodeFileTrace([join(directory, 'entry.cjs')], {
      base: directory,
      processCwd: directory,
    });
    const files = [...fileList].map((file: string) =>
      file.replaceAll('\\', '/'),
    );
    assert(files.includes('plugins/one.cjs'));
    assert(files.includes('plugins/two.cjs'));
    assert(!files.includes('plugins/unrelated.txt'));
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('archive directory traversal respects include and ignore patterns', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'e187-directory-'));
  try {
    await mkdir(join(directory, 'nested'));
    await writeFile(join(directory, 'entry.ts'), 'export {};');
    await writeFile(join(directory, 'nested', 'keep.ts'), 'export {};');
    await writeFile(join(directory, 'nested', 'skip.ts'), 'export {};');
    await writeFile(join(directory, 'nested', 'readme.txt'), 'text');

    const walker = readdirGlob(directory, {
      pattern: '**/*.ts',
      ignore: '**/skip.ts',
      nodir: true,
    });
    const files: string[] = [];
    walker.on('match', (entry: { relative: string }) => {
      files.push(entry.relative.replaceAll('\\', '/'));
    });
    await once(walker, 'end');
    assert.deepEqual(files.sort(), ['entry.ts', 'nested/keep.ts']);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
