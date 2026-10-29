import assert from 'node:assert/strict';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

// Run against a running local Nuxt dev server; production tests are separate.
const origin = new URL(
  process.env.NUXT_DEV_TEST_ORIGIN ?? 'http://localhost:3100',
);
assert(['localhost', '127.0.0.1', '[::1]'].includes(origin.hostname));
const root = fileURLToPath(new URL('../../', import.meta.url)).replaceAll(
  '\\',
  '/',
);
const errorComponent = `${root}node_modules/nuxt/dist/app/components/error-404.vue`;
const styleQuery = '?vue&type=style&index=0&lang.css';
const paths = [
  `/_nuxt/@fs/${errorComponent}${styleQuery}`,
  '/_nuxt/@vite/client',
  `/_nuxt/${errorComponent}${styleQuery}`,
  `/_nuxt/${root}node_modules/nuxt/dist/app/entry.async.js`,
  '/_nuxt/assets/css/main.css',
];

test('development resources stay same-origin and declare their content type', async (t) => {
  for (const path of paths) {
    for (const requestOrigin of [
      undefined,
      origin.origin,
      'https://untrusted.example',
      'null',
    ]) {
      await t.test(
        `${path}; Origin=${requestOrigin ?? '(absent)'}`,
        async () => {
          const response = await fetch(new URL(path, origin), {
            headers: requestOrigin ? { Origin: requestOrigin } : undefined,
            signal: AbortSignal.timeout(15_000),
          });
          await response.body?.cancel();
          assert.equal(response.status, 200);
          assert.equal(
            response.headers.get('access-control-allow-origin'),
            null,
          );
          assert.equal(
            response.headers.get('x-content-type-options'),
            'nosniff',
          );
        },
      );
    }
  }
});
