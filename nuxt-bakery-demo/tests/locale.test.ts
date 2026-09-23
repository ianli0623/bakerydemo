import assert from 'node:assert/strict';
import test from 'node:test';
import * as localeUtils from '../shared/utils/locale.ts';
import {
  localizedPagePath,
  normalizeBakeryLocale,
} from '../shared/utils/locale.ts';

test('locale normalization accepts only the public locales', () => {
  assert.equal(normalizeBakeryLocale('zh-tw'), 'zh-hant');
  assert.equal(normalizeBakeryLocale('zh-hant'), 'zh-hant');
  assert.equal(normalizeBakeryLocale('en'), 'en');
  assert.throws(() => normalizeBakeryLocale('de'), /locale/i);
  assert.throws(() => normalizeBakeryLocale(['en']), /locale/i);
});

test('localized paths prefix both English and Traditional Chinese', () => {
  assert.equal(localizedPagePath('zh-hant'), '/zh-tw/');
  assert.equal(localizedPagePath('zh-hant', 'about'), '/zh-tw/about/');
  assert.equal(localizedPagePath('en'), '/en/');
  assert.equal(localizedPagePath('en', 'about'), '/en/about/');
  assert.throws(() => localizedPagePath('en', '../admin'), /slug/i);
});

test('static export starts from the root and both localized home pages', () => {
  const getStaticSiteSeedRoutes = Reflect.get(
    localeUtils,
    'getStaticSiteSeedRoutes',
  );

  assert.equal(typeof getStaticSiteSeedRoutes, 'function');
  assert.deepEqual(getStaticSiteSeedRoutes(), ['/', '/en/', '/zh-tw/']);
});

test('SSR builds do not prerender CMS-backed pages', () => {
  const getStaticPrerenderOptions = Reflect.get(
    localeUtils,
    'getStaticPrerenderOptions',
  );

  assert.equal(typeof getStaticPrerenderOptions, 'function');
  assert.equal(getStaticPrerenderOptions(false), undefined);
  assert.deepEqual(getStaticPrerenderOptions(true), {
    routes: ['/', '/en/', '/zh-tw/'],
    crawlLinks: true,
    concurrency: 1,
    failOnError: true,
  });
});
