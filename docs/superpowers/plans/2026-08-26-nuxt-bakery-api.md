# Nuxt Bakery API Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Umbraco integration in `nuxt-bakery-demo` with a tested Nuxt server proxy and Vue UI that renders Bakery/Wagtail home and standard pages at `http://localhost:3100/`.

**Architecture:** The browser calls same-origin `/api/bakery/*` routes. Nitro validates the private Bakery origin, requests the Wagtail v2 page API, maps published page data into typed view models, and returns it to SSR-compatible Vue pages. Pure URL, error, query, and page-mapping functions carry the behavior and are covered by Node tests; the thin framework adapters are verified by Nuxt type checking, production build, live API checks, and browser QA.

**Tech Stack:** Nuxt 4.5.2, Vue 3.5, TypeScript 5.9, Nitro/H3, ofetch, Node.js 22+ built-in test runner, Wagtail API v2.

**Spec:** `docs/superpowers/specs/2026-08-26-nuxt-bakery-api-design.md`

## Global Constraints

- Keep the existing `nuxt-bakery-demo` directory name.
- Run the Nuxt development server at exactly `http://localhost:3100/`.
- Configure the CMS through `NUXT_BAKERY_BASE_URL`; use `http://127.0.0.1:8000` locally.
- Do not add an API key or expose the Bakery origin through `runtimeConfig.public`.
- Do not modify Python/Wagtail backend code.
- Render only `base.HomePage` and top-level `base.StandardPage` routes in Nuxt.
- Route unsupported featured page types to their published Wagtail `html_url`.
- Support heading, paragraph, image, block quote, and embed StreamField blocks; silently skip unknown block types.
- Remove all Umbraco UI copy, runtime configuration, source filenames, shared types, endpoints, and documentation from `nuxt-bakery-demo`.
- Preserve editor-controlled rich text as HTML; do not render visitor-controlled HTML.
- Use test-first red/green cycles for every new executable helper.

---

## File Map

- `nuxt-bakery-demo/server/utils/bakery-core.ts`: URL normalization, media URL resolution, upstream status extraction, and stable error mapping.
- `nuxt-bakery-demo/server/utils/bakery.ts`: tested, dependency-injectable Wagtail HTTP client used by Nitro routes.
- `nuxt-bakery-demo/server/utils/bakery-pages.ts`: page query construction, navigation mapping, featured-link enrichment, and single-page selection.
- `nuxt-bakery-demo/shared/types/bakery.ts`: all Wagtail payload and Nuxt view-model types.
- `nuxt-bakery-demo/server/api/bakery/home.get.ts`: home payload plus enriched featured links.
- `nuxt-bakery-demo/server/api/bakery/navigation.get.ts`: published top-level StandardPage navigation.
- `nuxt-bakery-demo/server/api/bakery/pages/[slug].get.ts`: published StandardPage lookup by slug.
- `nuxt-bakery-demo/app/utils/stream-field.ts`: tested heading and media helpers used by the renderer.
- `nuxt-bakery-demo/app/components/StreamField.vue`: supported StreamField block renderer.
- `nuxt-bakery-demo/app/pages/index.vue`: Wagtail home page.
- `nuxt-bakery-demo/app/pages/[slug].vue`: dynamic Wagtail StandardPage.
- `nuxt-bakery-demo/app/app.vue`: Bakery brand, API-backed navigation, footer, and navigation failure fallback.
- `nuxt-bakery-demo/app/assets/css/main.css`: responsive Bakery home, standard-page, StreamField, state, header, and footer styling.
- `nuxt-bakery-demo/nuxt.config.ts`: Bakery runtime config and port 3100.
- `nuxt-bakery-demo/.env.example`: local Bakery origin example.
- `nuxt-bakery-demo/.env`: local ignored configuration used only for verification.
- `nuxt-bakery-demo/package.json`, `package-lock.json`: Bakery package name and unchanged dependency graph.
- `nuxt-bakery-demo/README.md`: Bakery/Wagtail setup, architecture, routes, testing, and troubleshooting.

---

### Task 1: Bakery URL and HTTP client foundation

**Files:**

- Create: `nuxt-bakery-demo/tests/bakery-core.test.ts`
- Create: `nuxt-bakery-demo/server/utils/bakery-core.ts`
- Create: `nuxt-bakery-demo/server/utils/bakery.ts`

**Interfaces:**

- Produces: `normalizeBaseUrl(value: string): string`
- Produces: `resolveMediaUrl(baseUrl: string, value: string | null | undefined): string | null`
- Produces: `getUpstreamStatus(error: unknown): number | undefined`
- Produces: `toBakeryErrorDetails(error: unknown): { statusCode: number; statusMessage: string }`
- Produces: `fetchBakery<T>(event: H3Event, path: string, query?: Record<string, string>, dependencies?: BakeryDependencies): Promise<T>`

- [ ] **Step 1: Write the failing URL and error tests**

Create `tests/bakery-core.test.ts` with these initial assertions:

```ts
import assert from 'node:assert/strict'
import test from 'node:test'
import type { H3Event } from 'h3'
import {
  getUpstreamStatus,
  normalizeBaseUrl,
  resolveMediaUrl,
  toBakeryErrorDetails
} from '../server/utils/bakery-core.ts'
import { fetchBakery } from '../server/utils/bakery.ts'

test('normalizeBaseUrl accepts HTTP origins and removes trailing slashes', () => {
  assert.equal(
    normalizeBaseUrl(' http://127.0.0.1:8000/// '),
    'http://127.0.0.1:8000'
  )
  assert.equal(
    normalizeBaseUrl('https://cms.example.com/tenant/'),
    'https://cms.example.com/tenant'
  )
})

test('normalizeBaseUrl rejects empty and non-HTTP values', () => {
  assert.throws(() => normalizeBaseUrl(''), /NUXT_BAKERY_BASE_URL/)
  assert.throws(() => normalizeBaseUrl('file:///tmp/cms'), /HTTP/)
})

test('resolveMediaUrl preserves absolute URLs and joins relative media paths', () => {
  assert.equal(
    resolveMediaUrl('http://127.0.0.1:8000', 'http://localhost:8000/media/a.jpg'),
    'http://localhost:8000/media/a.jpg'
  )
  assert.equal(
    resolveMediaUrl('http://127.0.0.1:8000', '/media/a.jpg'),
    'http://127.0.0.1:8000/media/a.jpg'
  )
  assert.equal(resolveMediaUrl('http://127.0.0.1:8000', null), null)
})

test('getUpstreamStatus reads fetch and H3 error shapes', () => {
  assert.equal(getUpstreamStatus({ response: { status: 404 } }), 404)
  assert.equal(getUpstreamStatus({ statusCode: 400 }), 400)
  assert.equal(getUpstreamStatus(new Error('offline')), undefined)
})

test('toBakeryErrorDetails preserves known statuses and maps outages to 502', () => {
  assert.deepEqual(toBakeryErrorDetails({ response: { status: 404 } }), {
    statusCode: 404,
    statusMessage: '找不到指定的已發布頁面。'
  })
  assert.deepEqual(toBakeryErrorDetails({ response: { status: 400 } }), {
    statusCode: 400,
    statusMessage: 'Bakery API 查詢參數不正確。'
  })
  assert.deepEqual(toBakeryErrorDetails(new Error('offline')), {
    statusCode: 502,
    statusMessage: '目前無法連線到 Bakery CMS。'
  })
})

test('fetchBakery normalizes the base URL and forwards the query', async () => {
  const result = await fetchBakery<{ ok: boolean }>(
    {} as H3Event,
    '/api/v2/pages/',
    { limit: '20' },
    {
      baseUrl: ' http://127.0.0.1:8000/ ',
      request: async (path, options) => {
        assert.equal(path, '/api/v2/pages/')
        assert.equal(options.baseURL, 'http://127.0.0.1:8000')
        assert.deepEqual(options.query, { limit: '20' })
        return { ok: true }
      }
    }
  )

  assert.deepEqual(result, { ok: true })
})

test('fetchBakery reports invalid config as 500 and upstream failures as 502', async () => {
  await assert.rejects(
    fetchBakery({} as H3Event, '/api/v2/pages/', undefined, {
      baseUrl: '',
      request: async () => ({})
    }),
    (error: { statusCode?: number }) => error.statusCode === 500
  )

  await assert.rejects(
    fetchBakery({} as H3Event, '/api/v2/pages/', undefined, {
      baseUrl: 'http://127.0.0.1:8000',
      request: async () => {
        throw new Error('offline')
      }
    }),
    (error: { statusCode?: number }) => error.statusCode === 502
  )
})
```

- [ ] **Step 2: Run the tests and verify the new modules are missing**

Run: `cd nuxt-bakery-demo; npm test`

Expected: FAIL because `server/utils/bakery-core.ts` and `server/utils/bakery.ts` do not exist.

- [ ] **Step 3: Implement the pure Bakery helpers**

Create `server/utils/bakery-core.ts`:

```ts
export function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) {
    throw new Error('尚未設定 NUXT_BAKERY_BASE_URL。')
  }

  const url = new URL(trimmed)
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error('Bakery Base URL 必須使用 HTTP 或 HTTPS。')
  }

  return url.toString().replace(/\/+$/, '')
}

export function resolveMediaUrl(
  baseUrl: string,
  value: string | null | undefined
): string | null {
  if (!value) return null
  if (/^https?:\/\//i.test(value)) return value
  return new URL(value, `${normalizeBaseUrl(baseUrl)}/`).toString()
}

export function getUpstreamStatus(error: unknown): number | undefined {
  if (typeof error !== 'object' || error === null) return undefined
  const value = error as {
    response?: { status?: number }
    statusCode?: number
    status?: number
  }
  return value.response?.status ?? value.statusCode ?? value.status
}

export interface BakeryErrorDetails {
  statusCode: number
  statusMessage: string
}

export function toBakeryErrorDetails(error: unknown): BakeryErrorDetails {
  const status = getUpstreamStatus(error)
  if (status === 400) {
    return { statusCode: 400, statusMessage: 'Bakery API 查詢參數不正確。' }
  }
  if (status === 404) {
    return { statusCode: 404, statusMessage: '找不到指定的已發布頁面。' }
  }
  return { statusCode: 502, statusMessage: '目前無法連線到 Bakery CMS。' }
}
```

- [ ] **Step 4: Implement the dependency-injectable Nitro client**

Create `server/utils/bakery.ts`:

```ts
import type { H3Event } from 'h3'
import { createError } from 'h3'
import { ofetch } from 'ofetch'
import { normalizeBaseUrl, toBakeryErrorDetails } from './bakery-core'

interface BakeryRequestOptions {
  baseURL: string
  query?: Record<string, string>
}

type BakeryRequest = (
  path: string,
  options: BakeryRequestOptions
) => Promise<unknown>

export interface BakeryDependencies {
  baseUrl: string
  request: BakeryRequest
}

export async function fetchBakery<T>(
  event: H3Event,
  path: string,
  query?: Record<string, string>,
  dependencies?: BakeryDependencies
): Promise<T> {
  const config = dependencies ? null : useRuntimeConfig(event)
  const configuredBaseUrl = dependencies?.baseUrl ?? config?.bakeryBaseUrl ?? ''

  let baseURL: string
  try {
    baseURL = normalizeBaseUrl(configuredBaseUrl)
  } catch (error) {
    throw createError({
      statusCode: 500,
      statusMessage: error instanceof Error ? error.message : 'Bakery 設定錯誤。'
    })
  }

  const request = dependencies?.request ?? (ofetch as BakeryRequest)
  try {
    return await request(path, { baseURL, query }) as T
  } catch (error) {
    throw createError(toBakeryErrorDetails(error))
  }
}
```

- [ ] **Step 5: Run the focused tests and verify green**

Run: `cd nuxt-bakery-demo; node --test --experimental-strip-types tests/bakery-core.test.ts`

Expected: all Bakery core and client tests PASS.

- [ ] **Step 6: Commit the foundation**

```powershell
git add -- nuxt-bakery-demo/tests/bakery-core.test.ts nuxt-bakery-demo/server/utils/bakery-core.ts nuxt-bakery-demo/server/utils/bakery.ts
git commit -m "feat: add Bakery API client foundation"
```

---

### Task 2: Wagtail page types, mappings, and Nitro routes

**Files:**

- Create: `nuxt-bakery-demo/tests/bakery-pages.test.ts`
- Create: `nuxt-bakery-demo/shared/types/bakery.ts`
- Create: `nuxt-bakery-demo/server/utils/bakery-pages.ts`
- Create: `nuxt-bakery-demo/server/api/bakery/home.get.ts`
- Create: `nuxt-bakery-demo/server/api/bakery/navigation.get.ts`
- Create: `nuxt-bakery-demo/server/api/bakery/pages/[slug].get.ts`
- Modify: `nuxt-bakery-demo/nuxt.config.ts`

**Interfaces:**

- Consumes: `fetchBakery<T>()` from Task 1.
- Produces: `BakeryHomePage`, `BakeryStandardPage`, `BakeryPageList<T>`, `BakeryNavigationItem`, and `BakeryHomeViewModel`.
- Produces: `createTopLevelQuery()`, `createStandardPageQuery(slug)`, `validateSlug(value)`, `toNavigationItems(items)`, `enrichHomePage(home, topLevelPages)`, and `firstPage(items)`.
- Produces: `GET /api/bakery/home`, `GET /api/bakery/navigation`, and `GET /api/bakery/pages/:slug`.

- [ ] **Step 1: Write failing page-mapping tests**

Create `tests/bakery-pages.test.ts` with fixtures representing Home, About, TEST, and an unsupported Blog page. Assert these exact behaviors:

```ts
import assert from 'node:assert/strict'
import test from 'node:test'
import type { BakeryHomePage } from '../shared/types/bakery.ts'
import {
  createStandardPageQuery,
  createTopLevelQuery,
  enrichHomePage,
  firstPage,
  toNavigationItems,
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

test('query builders restrict Wagtail requests to the approved scope', () => {
  assert.deepEqual(createTopLevelQuery(), {
    child_of: '60',
    show_in_menus: 'true',
    limit: '20'
  })
  assert.deepEqual(createStandardPageQuery('test-page'), {
    type: 'base.StandardPage',
    child_of: '60',
    slug: 'test-page',
    fields: '*',
    limit: '1'
  })
})

test('validateSlug trims safe slugs and rejects missing or unsafe values', () => {
  assert.equal(validateSlug(' test-page '), 'test-page')
  assert.throws(() => validateSlug(''), /slug/)
  assert.throws(() => validateSlug('../admin'), /slug/)
})

test('toNavigationItems keeps only supported StandardPage routes', () => {
  assert.deepEqual(toNavigationItems([about, blog, testPage]), [
    { id: 76, title: 'About', path: '/about/' },
    { id: 86, title: 'TEST', path: '/test-page/' }
  ])
})

test('enrichHomePage attaches published URLs to featured references', () => {
  const home = {
    featured_section_1: { id: 61, title: 'Blog', meta: { type: 'blog.BlogIndexPage' } },
    featured_section_1_title: 'Blog',
    featured_section_2: null,
    featured_section_2_title: '',
    featured_section_3: null,
    featured_section_3_title: ''
  } as BakeryHomePage

  assert.deepEqual(enrichHomePage(home, [about, blog, testPage]).featuredSections, [
    { id: 61, title: 'Blog', url: 'http://127.0.0.1:8000/blog/' }
  ])
})

test('firstPage returns the first match or undefined', () => {
  assert.equal(firstPage([testPage]), testPage)
  assert.equal(firstPage([]), undefined)
})
```

- [ ] **Step 2: Run the mapping test and verify red**

Run: `cd nuxt-bakery-demo; node --test --experimental-strip-types tests/bakery-pages.test.ts`

Expected: FAIL because `server/utils/bakery-pages.ts` does not exist.

- [ ] **Step 3: Add the shared API types**

Create `shared/types/bakery.ts` with explicit interfaces for:

```ts
export interface BakeryPageMeta {
  type: string
  detail_url?: string
  html_url?: string
  slug?: string
  show_in_menus?: boolean
  seo_title?: string
  search_description?: string
  first_published_at?: string
}

export interface BakeryPageSummary {
  id: number
  meta: BakeryPageMeta
  title: string
}

export interface BakeryPageList<T> {
  meta: { total_count: number }
  items: T[]
}

export interface BakeryRendition {
  url: string
  full_url: string
  width: number
  height: number
  alt: string
}

export interface BakeryImage {
  id: number
  title: string
  meta: {
    download_url: string
    rendition?: BakeryRendition
  }
}

export type BakeryStreamBlock =
  | { id: string; type: 'heading_block'; value: { heading_text: string; size: 'h2' | 'h3' | 'h4' | '' } }
  | { id: string; type: 'paragraph_block'; value: string }
  | { id: string; type: 'image_block'; value: { image: BakeryImage; caption: string; attribution: string } }
  | { id: string; type: 'block_quote'; value: { text: string; attribute_name: string; settings?: { theme?: string; text_size?: string } } }
  | { id: string; type: 'embed_block'; value: string }

export type BakeryPageReference = BakeryPageSummary

export interface BakeryHomePage extends BakeryPageSummary {
  hero_text: string
  hero_cta: string
  hero_cta_link: BakeryPageReference | null
  body: BakeryStreamBlock[]
  lead_title: string
  lead_text: string
  image_hero: BakeryRendition | null
  lead_image_promo: BakeryRendition | null
  featured_section_1_title: string
  featured_section_1: BakeryPageReference | null
  featured_section_2_title: string
  featured_section_2: BakeryPageReference | null
  featured_section_3_title: string
  featured_section_3: BakeryPageReference | null
}

export interface BakeryStandardPage extends BakeryPageSummary {
  introduction: string
  body: BakeryStreamBlock[]
  image_hero: BakeryRendition | null
}

export interface BakeryNavigationItem {
  id: number
  title: string
  path: string
}

export interface BakeryFeaturedSection {
  id: number
  title: string
  url: string
}

export interface BakeryHomeViewModel extends BakeryHomePage {
  featuredSections: BakeryFeaturedSection[]
}
```

- [ ] **Step 4: Implement page query and mapping helpers**

Create `server/utils/bakery-pages.ts`. Use `BAKERY_HOME_PAGE_ID = 60`, allow slugs matching `/^[a-z0-9]+(?:-[a-z0-9]+)*$/`, generate the exact query objects asserted above, filter navigation by `meta.type === 'base.StandardPage'`, map each path to `/${slug}/`, enrich only non-null featured references that have a matching `html_url`, and return `items[0]` from `firstPage`.

The public signatures must be:

```ts
export const BAKERY_HOME_PAGE_ID = 60
export function createTopLevelQuery(): Record<string, string>
export function createStandardPageQuery(slug: string): Record<string, string>
export function validateSlug(value: string | undefined): string
export function toNavigationItems(items: BakeryPageSummary[]): BakeryNavigationItem[]
export function enrichHomePage(home: BakeryHomePage, topLevelPages: BakeryPageSummary[]): BakeryHomeViewModel
export function firstPage<T>(items: T[]): T | undefined
```

- [ ] **Step 5: Run mapping tests and verify green**

Run: `cd nuxt-bakery-demo; node --test --experimental-strip-types tests/bakery-pages.test.ts`

Expected: all mapping tests PASS.

- [ ] **Step 6: Create the three Nitro routes**

Implement the routes with explicit H3 imports and the Task 1/2 helpers:

```ts
// server/api/bakery/home.get.ts
import type {
  BakeryHomePage,
  BakeryHomeViewModel,
  BakeryPageList,
  BakeryPageSummary
} from '#shared/types/bakery'
import { defineEventHandler } from 'h3'
import { fetchBakery } from '../../utils/bakery'
import {
  BAKERY_HOME_PAGE_ID,
  createTopLevelQuery,
  enrichHomePage
} from '../../utils/bakery-pages'

export default defineEventHandler(async (event): Promise<BakeryHomeViewModel> => {
  const [home, topLevel] = await Promise.all([
    fetchBakery<BakeryHomePage>(event, `/api/v2/pages/${BAKERY_HOME_PAGE_ID}/`, { fields: '*' }),
    fetchBakery<BakeryPageList<BakeryPageSummary>>(event, '/api/v2/pages/', createTopLevelQuery())
  ])
  return enrichHomePage(home, topLevel.items)
})
```

```ts
// server/api/bakery/navigation.get.ts
import type { BakeryNavigationItem, BakeryPageList, BakeryPageSummary } from '#shared/types/bakery'
import { defineEventHandler } from 'h3'
import { fetchBakery } from '../../utils/bakery'
import { createTopLevelQuery, toNavigationItems } from '../../utils/bakery-pages'

export default defineEventHandler(async (event): Promise<BakeryNavigationItem[]> => {
  const response = await fetchBakery<BakeryPageList<BakeryPageSummary>>(
    event,
    '/api/v2/pages/',
    createTopLevelQuery()
  )
  return toNavigationItems(response.items)
})
```

```ts
// server/api/bakery/pages/[slug].get.ts
import type { BakeryPageList, BakeryStandardPage } from '#shared/types/bakery'
import { createError, defineEventHandler, getRouterParam } from 'h3'
import { fetchBakery } from '../../../utils/bakery'
import {
  createStandardPageQuery,
  firstPage,
  validateSlug
} from '../../../utils/bakery-pages'

export default defineEventHandler(async (event): Promise<BakeryStandardPage> => {
  let slug: string
  try {
    slug = validateSlug(getRouterParam(event, 'slug'))
  } catch (error) {
    throw createError({
      statusCode: 400,
      statusMessage: error instanceof Error ? error.message : '頁面 slug 不正確。'
    })
  }

  const response = await fetchBakery<BakeryPageList<BakeryStandardPage>>(
    event,
    '/api/v2/pages/',
    createStandardPageQuery(slug)
  )
  const page = firstPage(response.items)
  if (!page) {
    throw createError({ statusCode: 404, statusMessage: '找不到指定的已發布頁面。' })
  }
  return page
})
```

- [ ] **Step 7: Expose Bakery runtime config to Nuxt types**

Add `devServer: { port: 3100 }` and `bakeryBaseUrl: ''` to `nuxt.config.ts` while temporarily retaining the two Umbraco keys required by the still-present legacy files. Task 4 removes the legacy keys and files together. The transitional runtime block is:

```ts
runtimeConfig: {
  bakeryBaseUrl: '',
  umbracoBaseUrl: '',
  umbracoApiKey: ''
}
```

- [ ] **Step 8: Run all unit tests and Nuxt type checking**

Run: `cd nuxt-bakery-demo; npm test; npm run typecheck`

Expected: all tests PASS and Nuxt reports no TypeScript errors.

- [ ] **Step 9: Commit the API routes**

```powershell
git add -- nuxt-bakery-demo/tests/bakery-pages.test.ts nuxt-bakery-demo/shared/types/bakery.ts nuxt-bakery-demo/server/utils/bakery-pages.ts nuxt-bakery-demo/server/api/bakery nuxt-bakery-demo/nuxt.config.ts
git commit -m "feat: proxy published Bakery pages"
```

---

### Task 3: StreamField renderer and Wagtail pages

**Files:**

- Create: `nuxt-bakery-demo/tests/stream-field.test.ts`
- Create: `nuxt-bakery-demo/app/utils/stream-field.ts`
- Create: `nuxt-bakery-demo/app/components/StreamField.vue`
- Modify: `nuxt-bakery-demo/app/pages/index.vue`
- Create: `nuxt-bakery-demo/app/pages/[slug].vue`
- Modify: `nuxt-bakery-demo/app/app.vue`
- Modify: `nuxt-bakery-demo/app/assets/css/main.css`

**Interfaces:**

- Consumes: `BakeryStreamBlock`, `BakeryHomeViewModel`, `BakeryStandardPage`, and `BakeryNavigationItem` from Task 2.
- Consumes: `/api/bakery/home`, `/api/bakery/navigation`, and `/api/bakery/pages/:slug` from Task 2.
- Produces: `getHeadingTag(size): 'h2' | 'h3' | 'h4'` and `getImageRendition(block): BakeryRendition | null`.
- Produces: `<StreamField :blocks="home.body" />`, `/`, and `/:slug` UI behavior.

- [ ] **Step 1: Write failing StreamField helper tests**

Create `tests/stream-field.test.ts`:

```ts
import assert from 'node:assert/strict'
import test from 'node:test'
import { getHeadingTag, getImageRendition } from '../app/utils/stream-field.ts'

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
        image: { id: 56, title: '測試', meta: { download_url: '/media/original.jpg', rendition } },
        caption: 'DD',
        attribution: 'AA'
      }
    }),
    rendition
  )
})
```

- [ ] **Step 2: Run the helper test and verify red**

Run: `cd nuxt-bakery-demo; node --test --experimental-strip-types tests/stream-field.test.ts`

Expected: FAIL because `app/utils/stream-field.ts` does not exist.

- [ ] **Step 3: Implement StreamField helpers**

Create `app/utils/stream-field.ts`:

```ts
import type { BakeryRendition, BakeryStreamBlock } from '#shared/types/bakery'

export function getHeadingTag(size: string): 'h2' | 'h3' | 'h4' {
  return size === 'h3' || size === 'h4' ? size : 'h2'
}

export function getImageRendition(block: BakeryStreamBlock): BakeryRendition | null {
  return block.type === 'image_block' ? block.value.image.meta.rendition ?? null : null
}
```

- [ ] **Step 4: Run the helper test and verify green**

Run: `cd nuxt-bakery-demo; node --test --experimental-strip-types tests/stream-field.test.ts`

Expected: both helper tests PASS.

- [ ] **Step 5: Create the StreamField Vue renderer**

Create `app/components/StreamField.vue` with a required `blocks: BakeryStreamBlock[]` prop. Iterate by `block.id` and render:

```vue
<template>
  <div class="stream-field">
    <template v-for="block in blocks" :key="block.id">
      <component
        :is="getHeadingTag(block.value.size)"
        v-if="block.type === 'heading_block'"
        class="stream-heading"
      >
        {{ block.value.heading_text }}
      </component>
      <div
        v-else-if="block.type === 'paragraph_block'"
        class="rich-text"
        v-html="block.value"
      />
      <figure v-else-if="block.type === 'image_block'" class="stream-image">
        <img
          v-if="getImageRendition(block)"
          :src="getImageRendition(block)?.full_url"
          :width="getImageRendition(block)?.width"
          :height="getImageRendition(block)?.height"
          :alt="getImageRendition(block)?.alt || block.value.image.title"
          loading="lazy"
        >
        <figcaption v-if="block.value.caption || block.value.attribution">
          <span>{{ block.value.caption }}</span>
          <cite v-if="block.value.attribution">{{ block.value.attribution }}</cite>
        </figcaption>
      </figure>
      <blockquote v-else-if="block.type === 'block_quote'" class="stream-quote">
        <p>{{ block.value.text }}</p>
        <cite v-if="block.value.attribute_name">{{ block.value.attribute_name }}</cite>
      </blockquote>
      <div v-else-if="block.type === 'embed_block'" class="stream-embed">
        <iframe
          :src="block.value"
          title="嵌入內容"
          loading="lazy"
          allowfullscreen
        />
      </div>
    </template>
  </div>
</template>
```

The `<script setup>` imports `BakeryStreamBlock`, `getHeadingTag`, and `getImageRendition`; no final `v-else` is added, so unknown runtime block types are skipped.

- [ ] **Step 6: Replace the home page with the Bakery payload**

In `app/pages/index.vue`, fetch `BakeryHomeViewModel` from `/api/bakery/home`. Render these concrete sections:

- Hero: `image_hero.full_url`, `title`, `hero_text`, and an About CTA using `/about/` when `hero_cta_link` is present.
- Body: `<StreamField :blocks="home.body" />`.
- Lead promotion: `lead_image_promo.full_url`, `lead_title || 'Fresh from the bakery'`, and trusted `lead_text` through `v-html`.
- Featured cards: `home.featuredSections`, using normal `<a :href="section.url">` links because those page types remain on Wagtail.
- Pending skeleton, retryable 500/502 state, and a missing-data state with Chinese copy.
- SEO: `home.meta.seo_title || home.title` and `home.meta.search_description || home.hero_text`.

Use the following fetch and error contract:

```ts
const { data: home, status, error, refresh } = await useFetch<BakeryHomeViewModel>(
  '/api/bakery/home'
)

const errorMessage = computed(() =>
  error.value?.statusCode === 500
    ? 'Bakery API 尚未設定，請檢查 NUXT_BAKERY_BASE_URL。'
    : '目前無法連線到 Bakery CMS，請確認 Wagtail 已啟動。'
)
```

- [ ] **Step 7: Create the dynamic StandardPage route**

Create `app/pages/[slug].vue`. Read `route.params.slug`, fetch `/api/bakery/pages/${encodeURIComponent(slug)}`, convert an initial 404 into `createError({ statusCode: 404, statusMessage: '找不到指定的已發布頁面。' })`, and render:

- A Home back link.
- `page.image_hero.full_url` as the hero when present.
- `page.title` and `page.introduction`.
- `<StreamField :blocks="page.body" />`.
- SEO title from `meta.seo_title || title` and description from `meta.search_description || introduction`.
- Pending and retryable connection states using Bakery wording.

- [ ] **Step 8: Replace the application shell**

In `app/app.vue`, fetch `BakeryNavigationItem[]` from `/api/bakery/navigation`, render the brand as `Wagtail Bakery` with a `B` mark, always include Home, then render API menu links with `NuxtLink`. If navigation fails, keep Home usable and render `選單暫時無法載入` in a status element. Change the footer to `Nuxt Server API × Wagtail Bakery API`.

- [ ] **Step 9: Replace Umbraco/news CSS with Bakery page styles**

Keep the existing reset, accessible skip link, focus rings, responsive header, skeleton animation, and reduced-motion rules. Replace news/profile selectors with these page responsibilities and exact layout targets:

```css
:root {
  --color-ink: #2f2118;
  --color-muted: #75665b;
  --color-brand: #a14919;
  --color-brand-dark: #71300f;
  --color-brand-soft: #f7e2cb;
  --color-warm: #fbf6ee;
  --color-surface: #fffdf9;
  --color-border: #e4d7c8;
  --color-error: #9e2d2d;
  --radius-small: 0.65rem;
  --radius-large: 1.35rem;
  --shadow-card: 0 18px 44px rgb(47 33 24 / 10%);
}

.home-hero {
  display: grid;
  min-height: 32rem;
  align-items: end;
  padding: clamp(2rem, 7vw, 5rem);
  border-radius: var(--radius-large);
  background-position: center;
  background-size: cover;
}

.home-lead,
.standard-page-card {
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-large);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.stream-field {
  display: grid;
  gap: 1.5rem;
}

.stream-image img,
.standard-hero img {
  width: 100%;
  height: auto;
  border-radius: var(--radius-small);
}

.stream-embed {
  overflow: hidden;
  aspect-ratio: 16 / 9;
  border-radius: var(--radius-small);
}

.stream-embed iframe {
  width: 100%;
  height: 100%;
  border: 0;
}
```

At `max-width: 700px`, stack header navigation, home lead media/text, and featured cards into one column; keep all content within `calc(100% - 2rem)`.

- [ ] **Step 10: Run tests and compile the Vue application**

Run: `cd nuxt-bakery-demo; npm test; npm run typecheck; npm run build`

Expected: unit tests PASS, type checking has no errors, and Nuxt creates `.output` successfully.

- [ ] **Step 11: Commit the rendered pages**

```powershell
git add -- nuxt-bakery-demo/tests/stream-field.test.ts nuxt-bakery-demo/app/utils/stream-field.ts nuxt-bakery-demo/app/components/StreamField.vue nuxt-bakery-demo/app/pages/index.vue nuxt-bakery-demo/app/pages/[slug].vue nuxt-bakery-demo/app/app.vue nuxt-bakery-demo/app/assets/css/main.css
git commit -m "feat: render Bakery pages in Nuxt"
```

---

### Task 4: Remove Umbraco integration and document Bakery setup

**Files:**

- Modify: `nuxt-bakery-demo/nuxt.config.ts`
- Modify: `nuxt-bakery-demo/.env.example`
- Modify locally, do not commit: `nuxt-bakery-demo/.env`
- Modify: `nuxt-bakery-demo/package.json`
- Modify: `nuxt-bakery-demo/package-lock.json`
- Modify: `nuxt-bakery-demo/README.md`
- Modify: `nuxt-bakery-demo/.gitignore`
- Delete: `nuxt-bakery-demo/tests/umbraco-core.test.ts`
- Delete: `nuxt-bakery-demo/server/utils/umbraco-core.ts`
- Delete: `nuxt-bakery-demo/server/utils/umbraco.ts`
- Delete: `nuxt-bakery-demo/server/api/news/index.get.ts`
- Delete: `nuxt-bakery-demo/server/api/news/[slug].get.ts`
- Delete: `nuxt-bakery-demo/server/api/company-profile.get.ts`
- Delete: `nuxt-bakery-demo/shared/types/news.ts`
- Delete: `nuxt-bakery-demo/shared/types/company-profile.ts`
- Delete: `nuxt-bakery-demo/app/pages/news/[slug].vue`
- Delete: `nuxt-bakery-demo/app/pages/company-profile.vue`

**Interfaces:**

- Consumes: the Bakery API and Vue implementation from Tasks 1-3.
- Produces: a Nuxt project with no Umbraco runtime surface and documented Bakery commands.

- [ ] **Step 1: Record the expected failing cleanup check**

Run: `rg -n -i "umbraco|news api key|company profile" nuxt-bakery-demo -g "!node_modules/**" -g "!.nuxt/**" -g "!.output/**" -g "!.vs/**"`

Expected: matches in the old tests, utilities, endpoints, types, pages, package metadata, environment files, and README.

- [ ] **Step 2: Switch Nuxt runtime configuration and port**

Replace `nuxt.config.ts` with:

```ts
export default defineNuxtConfig({
  compatibilityDate: '2026-08-21',
  css: ['~/assets/css/main.css'],
  devServer: { port: 3100 },
  devtools: { enabled: true },
  runtimeConfig: {
    bakeryBaseUrl: ''
  }
})
```

Set `.env.example` to:

```dotenv
# Bakery/Wagtail 開發伺服器與 Wagtail API v2 的來源網址。
NUXT_BAKERY_BASE_URL=http://127.0.0.1:8000
```

Set the ignored local `.env` to the same single variable so live verification uses the running Bakery server.

- [ ] **Step 3: Rename package metadata without changing dependencies**

Change `package.json` name to `nuxt-bakery-demo`, keep every existing script and dependency version, and run:

`cd nuxt-bakery-demo; npm install --package-lock-only --ignore-scripts`

Expected: the root package name in `package-lock.json` becomes `nuxt-bakery-demo`; dependency versions remain locked.

- [ ] **Step 4: Delete the obsolete Umbraco files**

Delete exactly the files listed in this task's Delete section. Do not delete `.nuxt`, `.output`, `node_modules`, or the new Bakery files.

Add `.vs` to `nuxt-bakery-demo/.gitignore` so Visual Studio's generated local state cannot be staged with the project.

- [ ] **Step 5: Replace README with Bakery instructions**

Write `README.md` in Traditional Chinese with these concrete sections:

- Architecture: Browser → Nuxt `/api/bakery/*` → Wagtail `/api/v2/pages/*`.
- Requirements: Node.js 22+, npm, Python 3.10+, running Bakery demo.
- Wagtail startup:

```powershell
cd D:\Ian\github\bakerydemo
.\.venv\Scripts\Activate.ps1
python manage.py runserver 8000
```

- Nuxt setup and startup:

```powershell
cd D:\Ian\github\bakerydemo\nuxt-bakery-demo
Copy-Item .env.example .env
npm install
npm run dev
```

- Frontend routes: `/`, `/about/`, `/test-page/`.
- Nuxt proxy routes: `/api/bakery/home`, `/api/bakery/navigation`, `/api/bakery/pages/{slug}`.
- Wagtail publishing workflow: publish a direct child StandardPage under Home and enable Show in menus.
- Tests: `npm test`, `npm run typecheck`, `npm run build`.
- Troubleshooting: Wagtail port 8000, Nuxt port 3100, published status, StandardPage type, top-level placement, and environment restart.
- Rich-text trust warning: only published editor-managed Wagtail HTML is rendered with `v-html`.

- [ ] **Step 6: Verify all Umbraco references are gone**

Run: `rg -n -i "umbraco|news api key|company profile" nuxt-bakery-demo -g "!node_modules/**" -g "!.nuxt/**" -g "!.output/**" -g "!.vs/**"`

Expected: exit code 1 with no matches.

- [ ] **Step 7: Run the complete static verification suite**

Run: `cd nuxt-bakery-demo; npm test; npm run typecheck; npm run build`

Expected: all commands succeed without warnings attributable to the changed files.

- [ ] **Step 8: Commit cleanup and documentation**

Do not stage the ignored `.env`. Stage all other project files and confirm `.nuxt`, `.output`, and `node_modules` remain ignored:

```powershell
git add -- nuxt-bakery-demo
git status --short
git commit -m "docs: switch Nuxt demo to Bakery CMS"
```

Expected: the commit contains source, tests, lockfile, and README; it does not contain `.env`, `.nuxt`, `.output`, `.vs`, or `node_modules`.

---

### Task 5: Live API and browser acceptance verification

**Files:**

- No source files are expected to change unless verification exposes a defect; any defect must first receive a failing regression test in the closest test file.

**Interfaces:**

- Consumes: running Wagtail at port 8000 and Nuxt at port 3100.
- Verifies: every acceptance criterion in the design spec.

- [ ] **Step 1: Confirm Bakery/Wagtail is serving the required content**

Run:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v2/pages/60/?fields=*'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v2/pages/?slug=test-page&type=base.StandardPage&fields=*'
```

Expected: home page ID `60` and one published StandardPage titled `TEST` with slug `test-page`.

- [ ] **Step 2: Start Nuxt at the configured port**

Run from `nuxt-bakery-demo`: `npm run dev`

Expected: Nuxt reports `http://localhost:3100/`. Keep the process in a reusable terminal session for the remaining checks.

- [ ] **Step 3: Verify Nitro proxy responses**

Run:

```powershell
Invoke-RestMethod -Uri 'http://localhost:3100/api/bakery/home'
Invoke-RestMethod -Uri 'http://localhost:3100/api/bakery/navigation'
Invoke-RestMethod -Uri 'http://localhost:3100/api/bakery/pages/test-page'
```

Expected: the home response has ID `60`; navigation includes About and TEST; the standard page response has title `TEST`, introduction `AAAAAAAAAAAAAA`, and its image StreamField block.

- [ ] **Step 4: Perform desktop browser QA**

Open `http://localhost:3100/` with the in-app browser and verify:

- Bakery branding and no Umbraco text.
- The Wagtail hero image, title, hero text, body, lead content, and three featured cards.
- Home, About, and TEST navigation.
- No console errors or broken images.

Open `http://localhost:3100/test-page/` and verify the title `TEST`, introduction `AAAAAAAAAAAAAA`, hero image, content image, caption `DD`, and attribution `AA`.

- [ ] **Step 5: Perform narrow viewport and failure-state QA**

Resize the in-app browser to a narrow mobile viewport and confirm the header, navigation, hero, images, and body do not overflow horizontally. Then stop Wagtail, refresh Nuxt once to confirm the Chinese 502 state, restart Wagtail, and use the retry control to confirm recovery.

- [ ] **Step 6: Re-run final verification after live QA**

Run: `cd nuxt-bakery-demo; npm test; npm run typecheck; npm run build; git status --short`

Expected: all checks pass. Git status contains no unexpected generated or unrelated files; the intentionally ignored local `.env` remains uncommitted.

- [ ] **Step 7: Commit only if QA required a regression fix**

If a defect was found, add its failing test before the fix, rerun the full suite, then commit only the regression test and fix:

```powershell
git add -- nuxt-bakery-demo
git commit -m "fix: correct Bakery frontend integration"
```

If QA found no defect, do not create an empty commit.
