import assert from 'node:assert/strict';
import test from 'node:test';
import { getEmbedPresentation } from '../app/utils/stream-field.ts';

(
  globalThis as typeof globalThis & {
    defineNuxtConfig?: (config: unknown) => unknown;
  }
).defineNuxtConfig = (config) => config;
const { default: config } = await import('../nuxt.config.ts');

test('the enforced policy permits the existing supported video players', () => {
  const policy = config.security.headers.contentSecurityPolicy;
  for (const source of [
    'https://youtu.be/abcdef12345',
    'https://vimeo.com/1234567',
  ]) {
    const embed = getEmbedPresentation(source);
    assert.equal(embed?.kind, 'iframe');
    const origin = new URL(embed!.url).origin;
    assert(policy['frame-src'].includes(origin), `${origin} is blocked by CSP`);
    assert(
      config.security.headers.permissionsPolicy.fullscreen.includes(origin),
    );
  }
  assert.equal(config.security.headers.crossOriginEmbedderPolicy, false);
});
