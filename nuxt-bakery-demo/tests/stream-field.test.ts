import assert from 'node:assert/strict'
import test from 'node:test'
import type {
  BakeryContentLink,
  BakeryImage
} from '../shared/types/bakery.ts'
import * as streamField from '../app/utils/stream-field.ts'
import {
  getEmbedPresentation,
  getHeadingTag,
  getImagePresentation,
  getImageRendition,
  getLinkPresentation,
  getStructuredBlockAnchor,
  getDocumentRowAnchor,
  getRenditionSource
} from '../app/utils/stream-field.ts'

test('cards become h2 when their section heading is promoted elsewhere', () => {
  const getCardHeadingTag = Reflect.get(streamField, 'getCardHeadingTag')
  assert.equal(typeof getCardHeadingTag, 'function')
  assert.equal(getCardHeadingTag(''), 'h2')
  assert.equal(getCardHeadingTag('標準導入資源專區'), 'h3')
})

test('getHeadingTag permits h2 through h4 and defaults to h2', () => {
  assert.equal(getHeadingTag('h3'), 'h3')
  assert.equal(getHeadingTag('h4'), 'h4')
  assert.equal(getHeadingTag(''), 'h2')
  assert.equal(getHeadingTag('h1'), 'h2')
})

test('getImageRendition returns the API rendition or null', () => {
  const rendition = {
    url: '/media/image.jpg',
    full_url: 'http://localhost:8000/media/image.jpg',
    width: 600,
    height: 338,
    alt: '測試'
  }

  assert.deepEqual(
    getImageRendition({
      id: 'block-1',
      type: 'image_block',
      value: {
        image: {
          id: 56,
          title: '測試',
          meta: {
            download_url: '/media/original.jpg',
            rendition
          }
        },
        caption: 'DD',
        attribution: 'AA'
      }
    }),
    rendition
  )

  assert.equal(
    getImageRendition({
      id: 'block-2',
      type: 'paragraph_block',
      value: '<p>Text</p>'
    }),
    null
  )
})

test('getRenditionSource falls back to the rendition URL', () => {
  assert.equal(
    getRenditionSource({
      url: '/media/image.jpg',
      width: 600,
      height: 338,
      alt: '測試'
    }),
    '/media/image.jpg'
  )
})

test('getImagePresentation supplies intrinsic dimensions and useful alt text', () => {
  const image: BakeryImage = {
    id: 56,
    title: '自動光學檢測設備',
    meta: {
      download_url: '/media/original.jpg',
      rendition: {
        url: '/media/image.jpg',
        full_url: 'http://localhost:8000/media/image.jpg',
        width: 960,
        height: 540,
        alt: ''
      }
    }
  }

  assert.deepEqual(getImagePresentation(image, '均豪 AOI 設備'), {
    src: 'http://localhost:8000/media/image.jpg',
    width: 960,
    height: 540,
    alt: '均豪 AOI 設備'
  })
  assert.equal(
    getImagePresentation({ ...image, meta: { download_url: '/x.jpg' } }, ''),
    null
  )
})

test('getLinkPresentation renders safe internal links including fragments', () => {
  assert.deepEqual(
    getLinkPresentation({
      label: '查看驗證流程',
      kind: 'internal',
      href: '/certification/#process',
      new_tab: false
    }),
    {
      kind: 'internal',
      to: '/certification/#process',
      label: '查看驗證流程'
    }
  )
})

test('getLinkPresentation preserves safe external link behavior', () => {
  assert.deepEqual(
    getLinkPresentation({
      label: 'SEMI E187 標準',
      kind: 'external',
      href: 'https://www.semi.org/en/standards',
      new_tab: true
    }),
    {
      kind: 'external',
      href: 'https://www.semi.org/en/standards',
      label: 'SEMI E187 標準',
      newTab: true
    }
  )
})

test('getLinkPresentation makes unavailable and unsafe links non-interactive', () => {
  const disabled = {
    kind: 'disabled',
    label: '下載文件',
    status: '即將提供'
  }

  assert.deepEqual(
    getLinkPresentation({
      label: '下載文件',
      kind: 'disabled',
      href: null,
      new_tab: false
    }),
    disabled
  )

  for (const link of [
    { kind: 'internal', href: '//example.com/steal' },
    { kind: 'internal', href: 'javascript:alert(1)' },
    { kind: 'external', href: 'javascript:alert(1)' },
    { kind: 'external', href: 'not a URL' }
  ] as const) {
    assert.deepEqual(
      getLinkPresentation({
        label: '下載文件',
        new_tab: false,
        ...link
      }),
      disabled
    )
  }
})

test('link presentations preserve the editorial order', () => {
  const links: BakeryContentLink[] = [
    {
      label: '第一步',
      kind: 'internal',
      href: '/first/',
      new_tab: false
    },
    {
      label: '第二步',
      kind: 'internal',
      href: '/second/',
      new_tab: false
    },
    {
      label: '第三步',
      kind: 'disabled',
      href: null,
      new_tab: false
    }
  ]

  assert.deepEqual(
    links.map(getLinkPresentation).map(link => link.label),
    ['第一步', '第二步', '第三步']
  )
})

test('structured SEMI sections expose the source fragment targets once', () => {
  const blocks = [
    {
      id: 'certified-cards',
      type: 'card_grid',
      value: { heading: '驗證機構與合規名單' }
    },
    { id: 'cards', type: 'card_grid', value: { heading: '其他卡片' } },
    { id: 'process-a', type: 'process_steps' },
    { id: 'process-b', type: 'process_steps' },
    { id: 'case-a', type: 'case_study' },
    { id: 'case-b', type: 'case_study' }
  ]

  assert.equal(getStructuredBlockAnchor(blocks[0]!, blocks), 'certified-list')
  assert.equal(getStructuredBlockAnchor(blocks[1]!, blocks), undefined)
  assert.equal(getStructuredBlockAnchor(blocks[2]!, blocks), 'vendor-process')
  assert.equal(getStructuredBlockAnchor(blocks[3]!, blocks), undefined)
  assert.equal(getStructuredBlockAnchor(blocks[4]!, blocks), 'case-studies')
  assert.equal(getStructuredBlockAnchor(blocks[5]!, blocks), undefined)
})

test('structured blocks defer an anchor already owned by their containing section', () => {
  const blocks = [
    { id: 'case-a', type: 'case_study' },
    { id: 'case-b', type: 'case_study' }
  ]

  assert.equal(
    getStructuredBlockAnchor(blocks[0]!, blocks, ['case-studies']),
    undefined
  )

  const certifiedBlocks = [{
    id: 'certified-cards',
    type: 'card_grid',
    value: { heading: '驗證機構與合規名單' }
  }]
  assert.equal(
    getStructuredBlockAnchor(
      certifiedBlocks[0]!,
      certifiedBlocks,
      ['certified-list']
    ),
    undefined
  )
})

test('document row numbers become safe source anchors', () => {
  assert.equal(getDocumentRowAnchor('02'), 'doc-02')
  assert.equal(getDocumentRowAnchor('2'), 'doc-2')
  assert.equal(getDocumentRowAnchor('../admin'), undefined)
  assert.equal(getDocumentRowAnchor(''), undefined)
})

test('getEmbedPresentation converts supported video URLs to embed players', () => {
  assert.deepEqual(
    getEmbedPresentation('https://www.youtube.com/watch?v=SGJFWirQ3ks'),
    {
      kind: 'iframe',
      url: 'https://www.youtube-nocookie.com/embed/SGJFWirQ3ks'
    }
  )
  assert.deepEqual(
    getEmbedPresentation('https://vimeo.com/76979871'),
    {
      kind: 'iframe',
      url: 'https://player.vimeo.com/video/76979871'
    }
  )
})

test('getEmbedPresentation falls back to a safe link for other providers', () => {
  assert.deepEqual(
    getEmbedPresentation('https://example.com/media/123'),
    { kind: 'link', url: 'https://example.com/media/123' }
  )
  assert.equal(getEmbedPresentation('javascript:alert(1)'), null)
  assert.equal(getEmbedPresentation('not a URL'), null)
})
