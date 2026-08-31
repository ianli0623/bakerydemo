import assert from 'node:assert/strict'
import test from 'node:test'
import {
  localizedPagePath,
  normalizeBakeryLocale
} from '../shared/utils/locale.ts'

test('locale normalization accepts only the public locales', () => {
  assert.equal(normalizeBakeryLocale('zh-hant'), 'zh-hant')
  assert.equal(normalizeBakeryLocale('en'), 'en')
  assert.throws(() => normalizeBakeryLocale('de'), /locale/i)
  assert.throws(() => normalizeBakeryLocale(['en']), /locale/i)
})

test('localized paths keep Chinese unprefixed and prefix English', () => {
  assert.equal(localizedPagePath('zh-hant'), '/')
  assert.equal(localizedPagePath('zh-hant', 'about'), '/about/')
  assert.equal(localizedPagePath('en'), '/en/')
  assert.equal(localizedPagePath('en', 'about'), '/en/about/')
  assert.throws(() => localizedPagePath('en', '../admin'), /slug/i)
})
