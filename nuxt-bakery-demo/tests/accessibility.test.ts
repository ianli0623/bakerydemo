import assert from 'node:assert/strict'
import test from 'node:test'
import {
  getLanguageLinkLang,
  readStoredFontScale,
  reduceFontScale,
  writeStoredFontScale
} from '../app/utils/accessibility.ts'

test('font scale controls clamp to three supported values', () => {
  assert.equal(reduceFontScale('default', 'increase'), 'large')
  assert.equal(reduceFontScale('large', 'increase'), 'large')
  assert.equal(reduceFontScale('default', 'decrease'), 'small')
  assert.equal(reduceFontScale('small', 'decrease'), 'small')
  assert.equal(reduceFontScale('small', 'reset'), 'default')
  assert.equal(reduceFontScale('large', 'reset'), 'default')
})

test('invalid or unavailable stored values fall back without throwing', () => {
  assert.equal(readStoredFontScale({ getItem: () => 'huge' }), 'default')
  assert.equal(readStoredFontScale({ getItem: () => 'large' }), 'large')
  assert.equal(
    readStoredFontScale({
      getItem: () => {
        throw new Error('blocked')
      }
    }),
    'default'
  )
  assert.doesNotThrow(() => writeStoredFontScale({
    setItem: () => {
      throw new Error('blocked')
    }
  }, 'large'))
})

test('language links declare only a language different from the current page', () => {
  assert.equal(getLanguageLinkLang('en', 'en'), undefined)
  assert.equal(getLanguageLinkLang('en', 'zh-tw'), 'zh-Hant')
  assert.equal(getLanguageLinkLang('zh-tw', 'zh-tw'), undefined)
  assert.equal(getLanguageLinkLang('zh-tw', 'en'), 'en')
})
