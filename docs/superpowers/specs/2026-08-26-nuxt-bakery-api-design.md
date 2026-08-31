# Nuxt Bakery API Integration Design

## Goal

Replace the Umbraco-specific integration in `nuxt-bakery-demo` with a
Bakery/Wagtail API integration. The Nuxt application will run at
`http://localhost:3100/`, render the Wagtail home page, build its navigation
from published menu pages, and render published `base.StandardPage` content
such as `/about/` and `/test-page/`.

## Scope

The first implementation supports:

- The Wagtail `base.HomePage` at Nuxt route `/`.
- Top-level, published `base.StandardPage` entries that have
  `show_in_menus` enabled.
- A dynamic Nuxt route for top-level standard pages, including `/about/` and
  `/test-page/`.
- Standard-page title, introduction, hero image, and StreamField body.
- StreamField heading, paragraph, image, block quote, and embed blocks.
- Chinese loading, empty, configuration, upstream, and not-found messages.
- Configuration through `NUXT_BAKERY_BASE_URL`.
- A Nuxt development server on port `3100`.
- Updated package metadata, environment example, and README documentation.

The implementation does not add rendering for Breads, Blog, Recipes,
Locations, Gallery, Form, or other Wagtail page types. It does not change the
Python/Wagtail backend.

## Architecture

The browser talks only to same-origin Nuxt endpoints. Nuxt Nitro acts as a
small backend-for-frontend and fetches the public Wagtail API at
`/api/v2/pages/`. This avoids browser CORS configuration and keeps the CMS
origin configurable on the server.

```text
Browser at localhost:3100
  -> Nuxt pages and components
  -> /api/bakery/*
  -> Nuxt Nitro server
  -> http://127.0.0.1:8000/api/v2/pages/*
```

No secret or API key is required because the Wagtail v2 endpoints expose only
published content.

## Components

### Shared data types

`shared/types/bakery.ts` defines the Wagtail metadata, image renditions,
StreamField blocks, home page, standard page, navigation item, and list
response shapes used by both Nitro and Vue.

### Server utilities

`server/utils/bakery-core.ts` contains pure, tested helpers that:

- Normalize and validate the configured Bakery base URL.
- Read common upstream HTTP status shapes.
- Convert upstream errors into stable Nuxt status codes and Chinese messages.
- Convert relative media paths to absolute Bakery URLs when an API response
  does not provide a full rendition URL.

`server/utils/bakery.ts` reads private runtime configuration, calls Wagtail
with `ofetch`, and applies the shared error mapping.

### Nuxt server API

- `GET /api/bakery/home` requests Wagtail page ID `60` with `fields=*` and
  returns the `base.HomePage` payload.
- `GET /api/bakery/navigation` queries direct children of page ID `60`, filters
  to published `base.StandardPage` items with `show_in_menus=true`, and returns
  navigation view models with Nuxt paths.
- `GET /api/bakery/pages/:slug` validates the slug, queries a published
  `base.StandardPage` with `fields=*`, returns the single matching item, and
  returns 404 when no item exists.

The home page ID is fixed to `60` because it is the home page in the supplied
Bakery demo fixture. This keeps the initial integration small and explicit.

### Vue application

`app/app.vue` presents Bakery branding, always links to Home, and fetches the
standard-page navigation from the Nuxt server API.

`app/pages/index.vue` renders the Wagtail home hero, call to action, body,
lead promotion, and the three featured-section titles. Links to unsupported
Wagtail page types open their existing Wagtail `html_url` rather than routing
to an unimplemented Nuxt page.

`app/pages/[slug].vue` fetches and renders a published standard page. It sets
SEO title and description from Wagtail metadata and converts an empty result
into a Nuxt 404.

`app/components/StreamField.vue` renders each supported StreamField block. It
uses CMS-provided rich text only for published editor-controlled HTML. Unknown
block types are skipped without breaking the page.

## Data Flow

1. A request reaches Nuxt at `/` or `/:slug`.
2. The page uses `useFetch` against a same-origin `/api/bakery/*` endpoint.
3. Nitro validates `NUXT_BAKERY_BASE_URL` and requests the Wagtail v2 API.
4. Nitro returns the published Wagtail JSON to the SSR-compatible Vue page.
5. Vue renders the page and StreamField blocks; image URLs use Wagtail's full
   rendition URL when available.

Navigation is loaded once by the application shell and therefore reflects
published top-level standard pages marked for menus after a refresh.

## Error Handling

- Missing or invalid `NUXT_BAKERY_BASE_URL`: HTTP 500 with a configuration
  message.
- Bakery unavailable or unexpected upstream failure: HTTP 502 with a CMS
  connection message.
- Missing or invalid slug: HTTP 400.
- No published standard page for a slug: HTTP 404.
- Navigation failure: the page remains usable with the Home link and a small
  non-blocking navigation status message.
- Unsupported StreamField block: skip the block and keep rendering the page.
- Missing optional image or text: omit that visual section rather than render
  a broken element.

## Testing

Development follows test-driven development:

1. Add failing unit tests for Bakery URL normalization, media URL handling,
   upstream status extraction, error mapping, and slug handling.
2. Implement the minimum server helpers and endpoint logic required to pass.
3. Add component/page behavior with typed payloads.
4. Run `npm test`, `npm run typecheck`, and `npm run build`.
5. Run Wagtail on port `8000` and Nuxt on port `3100`, then verify `/`,
   `/about/`, and `/test-page/` in the browser at desktop and narrow widths.

## Acceptance Criteria

- `http://localhost:3100/` displays content from Wagtail home page ID `60`.
- The navigation includes Home, About, and the published TEST page.
- `http://localhost:3100/test-page/` displays the Wagtail title `TEST`, its
  introduction, hero image, and image StreamField block.
- Publishing an updated standard page in Wagtail is reflected after refreshing
  Nuxt.
- No visible UI, runtime configuration, source filename, package metadata, or
  documentation describes the integration as Umbraco.
- The Wagtail backend code remains unchanged.
- Unit tests, Nuxt type checking, and the production build all pass.

