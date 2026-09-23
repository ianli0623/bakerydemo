import assert from 'node:assert/strict';
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import {
  createOfflineRootEntry,
  replaceDirectoryContents,
  rewriteOfflineDocument,
} from '../scripts/offline-site.mjs';

test('offline HTML uses file-relative pages and assets without Nuxt hydration', () => {
  const source = `<!doctype html>
<html>
  <head>
    <link rel="stylesheet" href="/_nuxt/entry.css" crossorigin>
    <link rel="modulepreload" href="/_nuxt/app.js">
    <link rel="canonical" href="http://localhost/en/about/">
    <script type="importmap">{"imports":{"#entry":"/_nuxt/app.js"}}</script>
    <script type="module" src="/_nuxt/app.js"></script>
  </head>
  <body>
    <a href="/en/resources#documents">Resources</a>
    <a href="#main-content">Skip</a>
    <a href="mailto:test@example.com">Email</a>
    <img src="/media/logo.png" alt="Logo">
    <script>window.__NUXT__={}</script>
    <script type="application/json" data-nuxt-data="nuxt-app" data-src="/en/about/_payload.json">[]</script>
  </body>
</html>`;

  const result = rewriteOfflineDocument(source, 'en/about/index.html');

  assert.match(result, /href="\.\.\/\.\.\/_nuxt\/entry\.css"/);
  assert.match(result, /href="\.\.\/resources\/index\.html#documents"/);
  assert.match(result, /href="#main-content"/);
  assert.match(result, /href="mailto:test@example\.com"/);
  assert.match(result, /src="\.\.\/\.\.\/media\/logo\.png"/);
  assert.match(
    result,
    /<script defer src="\.\.\/\.\.\/offline\.js"><\/script>/,
  );
  assert.doesNotMatch(result, /crossorigin/i);
  assert.doesNotMatch(
    result,
    /type="module"|modulepreload|data-nuxt-data|window\.__NUXT__|canonical/,
  );
});

test('offline root entry opens the English HTML file with no web server', () => {
  const result = createOfflineRootEntry();

  assert.match(result, /url=en\/index\.html/);
  assert.match(result, /window\.location\.replace\('en\/index\.html'/);
  assert.match(result, /href="en\/index\.html"/);
  assert.doesNotMatch(result, /url=\/en\/|href="\/en\//);
});

test('export replaces stale contents without deleting the open destination directory', (t) => {
  const root = mkdtempSync(join(tmpdir(), 'semi-e187-offline-'));
  const source = join(root, 'source');
  const destination = join(root, 'destination');
  t.after(() => rmSync(root, { recursive: true, force: true }));

  mkdirSync(source);
  mkdirSync(join(destination, 'stale'), { recursive: true });
  writeFileSync(join(source, 'index.html'), 'new export');
  writeFileSync(join(destination, 'stale', 'old.txt'), 'old export');

  replaceDirectoryContents(source, destination, root);

  assert.equal(
    readFileSync(join(destination, 'index.html'), 'utf8'),
    'new export',
  );
  assert.equal(existsSync(join(destination, 'stale')), false);
});
