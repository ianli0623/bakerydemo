import assert from 'node:assert/strict';
import test from 'node:test';

test('the Chinese root route does not redirect based on browser language', async () => {
  (
    globalThis as typeof globalThis & {
      defineNuxtConfig?: (config: unknown) => unknown;
    }
  ).defineNuxtConfig = (config) => config;

  const { default: config } = await import('../nuxt.config.ts');

  assert.equal(config.i18n.detectBrowserLanguage, false);
});
