import assert from 'node:assert/strict'
import test from 'node:test'
import type { BakeryHomePage } from '../shared/types/bakery.ts'
import {
  isMissingBakeryPageError,
  isValidStandardPageSlug
} from '../shared/utils/bakery.ts'
import {
  collectPaginatedItems,
  createStandardPageQuery,
  enrichHomePage,
  firstPage,
  getFeaturedPageIds,
  getHomeReferenceIds,
  toNuxtPagePath,
  validateSlug
} from '../server/utils/bakery-pages.ts'

const about = {
  id: 76,
  meta: {
    type: 'base.StandardPage',
    html_url: 'http://127.0.0.1:8000/about/',
    slug: 'about'
  },
  title: 'About'
}

const testPage = {
  id: 86,
  meta: {
    type: 'base.StandardPage',
    html_url: 'http://127.0.0.1:8000/test-page/',
    slug: 'test-page'
  },
  title: 'TEST'
}

const blog = {
  id: 61,
  meta: {
    type: 'blog.BlogIndexPage',
    html_url: 'http://127.0.0.1:8000/blog/',
    slug: 'blog'
  },
  title: 'Blog'
}

test('standard page queries restrict Wagtail requests to the approved scope', () => {
  assert.deepEqual(createStandardPageQuery('test-page'), {
    type: 'base.StandardPage',
    child_of: '60',
    slug: 'test-page',
    fields: '*',
    limit: '1'
  })
})

test('collectPaginatedItems requests every page without truncation', async () => {
  const items = Array.from({ length: 21 }, (_, index) => ({ id: index + 1 }))
  const offsets: number[] = []

  const result = await collectPaginatedItems(async (offset) => {
    offsets.push(offset)
    return {
      meta: { total_count: items.length },
      items: items.slice(offset, offset + 20)
    }
  })

  assert.deepEqual(offsets, [0, 20])
  assert.deepEqual(result, items)
})

test('getFeaturedPageIds returns unique references without menu filtering', () => {
  const home = {
    featured_section_1: { id: 61, title: 'Blog' },
    featured_section_2: { id: 76, title: 'About' },
    featured_section_3: { id: 61, title: 'Blog' }
  } as BakeryHomePage

  assert.deepEqual(getFeaturedPageIds(home), [61, 76])
})

test('getHomeReferenceIds includes the hero CTA and de-duplicates page lookups', () => {
  const home = {
    hero_cta_link: { id: 93, title: '驗證與合規' },
    featured_section_1: { id: 61, title: 'Blog' },
    featured_section_2: { id: 93, title: '驗證與合規' },
    featured_section_3: null
  } as BakeryHomePage

  assert.deepEqual(getHomeReferenceIds(home), [93, 61])
})

test('validateSlug trims safe slugs and rejects missing or unsafe values', () => {
  assert.equal(validateSlug(' test-page '), 'test-page')
  assert.throws(() => validateSlug(''), /slug/)
  assert.throws(() => validateSlug('../admin'), /slug/)
})

test('isValidStandardPageSlug is shared by client and server routing', () => {
  assert.equal(isValidStandardPageSlug('test-page'), true)
  assert.equal(isValidStandardPageSlug('INVALID'), false)
  assert.equal(isValidStandardPageSlug('../admin'), false)
  assert.equal(isValidStandardPageSlug(['test-page']), false)
})

test('isMissingBakeryPageError recognizes client fetch error shapes', () => {
  assert.equal(isMissingBakeryPageError({ statusCode: 404 }), true)
  assert.equal(isMissingBakeryPageError({ status: 400 }), true)
  assert.equal(isMissingBakeryPageError({ statusCode: 502 }), false)
  assert.equal(isMissingBakeryPageError(new Error('offline')), false)
})

test('enrichHomePage attaches published URLs to featured references', () => {
  const home = {
    featured_section_1: {
      id: 61,
      title: 'Blog',
      meta: { type: 'blog.BlogIndexPage' }
    },
    featured_section_1_title: 'Blog',
    featured_section_2: null,
    featured_section_2_title: '',
    featured_section_3: null,
    featured_section_3_title: ''
  } as BakeryHomePage

  assert.deepEqual(
    enrichHomePage(home, [about, blog, testPage]).featuredSections,
    [{ id: 61, title: 'Blog', url: 'http://127.0.0.1:8000/blog/' }]
  )
})

test('toNuxtPagePath localizes Wagtail page URLs and rejects unsafe schemes', () => {
  assert.equal(
    toNuxtPagePath({
      id: 91,
      title: '驗證與合規',
      meta: {
        type: 'base.StandardPage',
        html_url:
          'http://127.0.0.1:8000/certification/?from=hero#vendor-process'
      }
    }),
    '/certification/?from=hero#vendor-process'
  )
  assert.equal(
    toNuxtPagePath({
      id: 92,
      title: 'Unsafe',
      meta: { type: 'base.StandardPage', html_url: 'javascript:alert(1)' }
    }),
    null
  )
  assert.equal(toNuxtPagePath(null), null)
})

test('enrichHomePage exposes a localized hero CTA path', () => {
  const home = {
    hero_cta_link: {
      id: 91,
      title: '驗證與合規',
      meta: {
        type: 'base.StandardPage',
        html_url: 'http://127.0.0.1:8000/certification/'
      }
    },
    featured_section_1: null,
    featured_section_1_title: '',
    featured_section_2: null,
    featured_section_2_title: '',
    featured_section_3: null,
    featured_section_3_title: ''
  } as BakeryHomePage

  assert.equal(enrichHomePage(home, []).heroCtaPath, '/certification/')
})

test('enrichHomePage resolves a hero CTA whose compact reference has no URL', () => {
  const home = {
    hero_cta_link: {
      id: 91,
      title: '驗證與合規',
      meta: { type: 'base.StandardPage' }
    },
    featured_section_1: null,
    featured_section_1_title: '',
    featured_section_2: null,
    featured_section_2_title: '',
    featured_section_3: null,
    featured_section_3_title: ''
  } as BakeryHomePage

  assert.equal(
    enrichHomePage(home, [{
      id: 91,
      title: '驗證與合規',
      meta: {
        type: 'base.StandardPage',
        html_url: 'http://127.0.0.1:8000/certification/'
      }
    }]).heroCtaPath,
    '/certification/'
  )
})

test('firstPage returns the first match or undefined', () => {
  assert.equal(firstPage([testPage]), testPage)
  assert.equal(firstPage([]), undefined)
})
