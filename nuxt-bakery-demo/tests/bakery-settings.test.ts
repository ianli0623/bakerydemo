import assert from 'node:assert/strict'
import test from 'node:test'
import type { BakerySiteSettings } from '../shared/types/bakery.ts'
import {
  isBakerySiteSettings,
  parseBakerySiteSettings,
  toBakerySiteSettings,
  toNavigationItems
} from '../server/utils/bakery-settings.ts'

function makeSiteSettings(
  overrides: Partial<BakerySiteSettings> = {}
): BakerySiteSettings {
  return {
    site_name: 'SEMI E187',
    site_tagline: '推動半導體設備資安',
    contact: {
      heading: '合規諮詢',
      name: '李先生',
      context: '認驗證制度與流程',
      phone: '02-23116228 #202',
      phone_href: 'tel:+886223116228,202',
      email: 'MaxYCLee@itri.org.tw'
    },
    organisation_text: 'SEMI E187',
    footer_logo: null,
    navigation: [],
    ...overrides
  }
}

test('parseBakerySiteSettings accepts the exact public settings contract', () => {
  const settings = makeSiteSettings({
    navigation: [
      { id: 60, title: '首頁', path: '/' },
      { id: 91, title: '認識標準', path: '/about/' }
    ]
  })

  assert.equal(isBakerySiteSettings(settings), true)
  assert.deepEqual(parseBakerySiteSettings(settings), settings)
})

test('settings validation rejects malformed nested values and routes', () => {
  assert.equal(
    isBakerySiteSettings({
      ...makeSiteSettings(),
      contact: { ...makeSiteSettings().contact, phone_href: 123 }
    }),
    false
  )
  assert.equal(
    isBakerySiteSettings(
      makeSiteSettings({
        navigation: [{ id: 86, title: 'TEST', path: 'test-page' }]
      })
    ),
    false
  )
  assert.throws(
    () => parseBakerySiteSettings({ ...makeSiteSettings(), footer_logo: {} }),
    /site settings/i
  )
})

test('toNavigationItems uses only configured settings order and returns a copy', () => {
  const settings = makeSiteSettings({
    navigation: [
      { id: 60, title: '首頁', path: '/' },
      { id: 91, title: '認識標準', path: '/about/' }
    ]
  })

  const navigation = toNavigationItems(settings)
  navigation[0]!.title = 'Changed'

  assert.deepEqual(settings.navigation, [
    { id: 60, title: '首頁', path: '/' },
    { id: 91, title: '認識標準', path: '/about/' }
  ])
  assert.equal(navigation[0]!.title, 'Changed')
})

test('toBakerySiteSettings maps invalid upstream payloads to 502', () => {
  assert.throws(
    () => toBakerySiteSettings({ site_name: 'Incomplete' }),
    (error: { statusCode?: number }) => error.statusCode === 502
  )
})
