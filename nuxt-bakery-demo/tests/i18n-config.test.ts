import assert from 'node:assert/strict';
import test from 'node:test';

(
  globalThis as typeof globalThis & {
    defineNuxtConfig?: (config: unknown) => unknown;
  }
).defineNuxtConfig = (config) => config;

const { default: config } = await import('../nuxt.config.ts');

test('the root permanently redirects to the prefixed English default locale', () => {
  assert.equal(config.i18n.strategy, 'prefix');
  assert.equal(config.i18n.defaultLocale, 'en');
  assert.deepEqual(config.i18n.rootRedirect, {
    path: '/en/',
    statusCode: 301,
  });
  assert.deepEqual(
    config.i18n.locales.map((locale) => locale.code),
    ['zh-tw', 'en'],
  );
  assert.equal(config.i18n.detectBrowserLanguage, false);
});

test('accessibility scans exclude Nuxt developer tool styles', () => {
  assert.equal(config.devtools.enabled, false);
});
