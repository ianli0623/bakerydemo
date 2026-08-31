import assert from 'node:assert/strict'
import test from 'node:test'
import {
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
