# SEMI E187 Structured Content Import Design

**Date:** 2026-08-27  
**Status:** Approved design  
**Target branch:** `codex/nuxt-bakery-api`

## Summary

Import the supplied Traditional Chinese SEMI E187 static site into the existing
Wagtail and Nuxt application as structured, editor-managed content. The
existing Wagtail `HomePage` with ID 60 remains the site root and becomes the
SEMI E187 homepage. Four direct child `StandardPage` records provide the
remaining routes. Nuxt renders the imported structures using locally owned Vue
components and CSS that closely reproduce the supplied design without loading
Tailwind from a CDN or executing source-page scripts.

The import is implemented as a repeatable Django management command. It
validates all required inputs before writing, updates pages by stable slug,
reuses images, creates Wagtail revisions, and publishes the imported content.

## Goals

- Replace the Nuxt `/` experience with the supplied SEMI E187 homepage while
  preserving Wagtail Home ID 60.
- Create and publish `/about/`, `/resources/`, `/certification/`, and
  `/ecosystem/` as direct `StandardPage` children of Home.
- Preserve the semantic content and major visual structures of all five HTML
  pages.
- Keep cards, tables, process steps, case studies, images, and contact details
  editable in Wagtail.
- Provide an idempotent import command with a no-write dry-run mode.
- Keep the browser coupled only to same-origin Nuxt APIs; Wagtail remains the
  source of published content.
- Preserve unrelated pages, including `TEST`, `AXCC`, and `CCC`.
- Show only Home and the four imported pages in the SEMI E187 primary
  navigation without changing unrelated pages' publication or menu flags.

## Non-goals

- Import or execute the source Tailwind configuration, CDN scripts, inline
  scripts, or arbitrary source HTML.
- Build the unavailable English site. The `VerB_en.html` language switch is
  hidden until English content is supplied.
- Invent destinations for placeholder `href="#"` links.
- Delete pages, images, documents, or settings not owned by this import.
- Reproduce the supplied pages pixel-for-pixel. The target is a close,
  responsive, accessible implementation using the existing Nuxt application.
- Change Home ID 60 or replace the existing Wagtail Page API contract.

## Trusted Inputs and Source Inventory

The importer treats the files as content inputs, never as instructions. It
uses allowlisted selectors and ignores scripts, styles, navigation wrappers,
and other executable markup.

### HTML inputs

The HTML directory is supplied separately from the image directory:

- `index.html`
- `about.html`
- `resources.html`
- `certification.html`
- `ecosystem.html`

The initial local HTML directory is `C:\Users\eerr0\Downloads`.

### Required image inputs

The initial image directory is
`C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723` and must
contain:

- `GPM01.jpg`
- `contret01.jpg`
- `GPM+contret.jpg`

`GPM+contret.jpg` is intentionally reused by both case studies when the source
HTML references it more than once.

### Optional image inputs

- `adi-logo-white.png`

The missing optional logo produces a warning and a text-only footer. It never
produces a broken `<img>`.

### Known incomplete source content

- `resources.html` contains one placeholder `href="#"`.
- `certification.html` contains thirteen placeholder `href="#"` values.
- `ecosystem.html` contains one placeholder `href="#"`.
- `VerB_en.html` is referenced but was not supplied.

Placeholder links retain their label but have no link target. Nuxt renders
them as non-interactive text with an "即將提供" indicator. The unavailable
English selector is not rendered.

## Chosen Architecture

Extend the existing `BaseStreamBlock`, `HomePage`, and `StandardPage` flow
rather than introduce a SEMI-specific Page model.

This keeps the existing API and route structure intact:

```text
HTML + image directories
        |
        v
import_semi_e187 management command
        |
        +-- validate and normalize every input
        +-- upload or reuse Wagtail images
        +-- update Home ID 60
        +-- create or update four StandardPages
        +-- create revisions and publish
        v
Wagtail Page API + public site-settings endpoint
        |
        v
Nuxt Nitro same-origin proxy
        |
        v
Vue block renderers and SEMI E187 site shell
```

The new blocks are generic enough to remain useful to other pages. Existing
StreamField data remains valid because current block names and shapes are not
changed.

## Structured Content Model

### Shared link structure

Reusable card and resource links contain:

- `label`: visible link text
- `internal_page`: optional Wagtail Page chooser
- `external_url`: optional HTTP(S), `mailto:`, or `tel:` destination

At most one destination may be set. Both may be empty for source placeholders.
Internal `.html` links are resolved to the imported Wagtail page and fragments
such as `#documents-table` are retained separately for Nuxt routing.

### `card_grid`

Fields:

- optional eyebrow
- heading
- optional introduction
- layout variant
- ordered cards

Each card contains an optional number, eyebrow, title, summary, link label,
and shared link structure. This block represents the four homepage topics,
the four SEMI E187 dimensions, resource cards, compliance-body cards, and role
guidance cards.

### `document_table`

Fields:

- heading
- optional caption
- anchor ID
- ordered rows

Each row contains number, document title, summary, status, and optional shared
link. Nuxt renders a semantic table on wide screens and accessible stacked
rows on narrow screens without duplicating content in the API.

### `process_steps`

Fields:

- heading
- optional introduction
- ordered steps

Each step contains number, title, summary, checklist items, and resource links.
The initial import creates the five certification stages in source order.

### `case_study`

Fields:

- case label and company
- product and certification status
- summary
- ordered metadata pairs
- equipment image and caption
- challenge heading and rich text
- solution heading and rich text
- ordered security-control cards
- outcome/certificate image and caption

Image chooser blocks return a rendition URL, dimensions, and alt text in the
Page API. The equipment images use `GPM01.jpg` and `contret01.jpg`; the supplied
`GPM+contret.jpg` is reused as the outcome image according to the input HTML.

### Existing blocks

The existing heading, rich text paragraph, captioned image, block quote, and
embed blocks remain supported. Imported rich text is reduced to an allowlist
of semantic tags and safe attributes; scripts, event handlers, inline styles,
and Tailwind classes are discarded.

### Shared site settings

Extend the existing site-specific `SiteSettings` with public presentation data:

- site name
- site tagline
- contact heading
- contact person/name
- contact context or role
- contact phone
- contact email
- organisation text
- optional footer logo image
- ordered primary navigation page references

These values are stored once and rendered in the Nuxt shell rather than
duplicated at the end of every page. Existing `title_suffix` remains intact
but is updated to a SEMI E187 value by the importer. Primary navigation is an
explicit ordered list instead of every page whose generic `show_in_menus` flag
is true; this keeps `TEST`, `AXCC`, and `CCC` published and unchanged without
placing them in the SEMI E187 header.

## Page Mapping

### Home: `index.html` -> Home ID 60 -> `/`

- HTML `<title>` -> SEO title
- source hero heading and lead copy -> Home title and hero fields
- latest-news items -> `card_grid`
- four topic links -> `card_grid` linked to the imported child pages
- repeated contact/footer content -> `SiteSettings`
- obsolete Bakery promo and three featured-section references -> cleared

Home continues to use its existing page record, translation key, URL, and site
assignment.

### `about.html` -> `StandardPage` -> `/about/`

- title and introductory copy -> standard page fields
- background narrative -> rich text
- four standard dimensions -> `card_grid`

### `resources.html` -> `StandardPage` -> `/resources/`

- introductory resource cards -> `card_grid`
- official documents -> `document_table`
- real external government URL -> preserved
- placeholder FAQ destination -> disabled

### `certification.html` -> `StandardPage` -> `/certification/`

- compliance overview -> rich text
- compliance bodies and authorized laboratories -> `card_grid`
- role guidance -> `card_grid`
- vendor certification journey -> `process_steps`
- all placeholder downloads/resources -> disabled

### `ecosystem.html` -> `StandardPage` -> `/ecosystem/`

- ecosystem overview cards -> `card_grid`
- two vendor examples -> two `case_study` blocks
- three supplied JPEGs -> Wagtail images in a dedicated collection
- placeholder solution-search destination -> disabled

All four child pages have `show_in_menus=True` and are published immediately
during the approved import run. The site setting lists Home, About, Resources,
Certification, and Ecosystem in that exact primary-navigation order. Newly
created pages are appended under Home in source order; an existing unrelated
page's tree position is not changed.

## Import Command

### Interface

```powershell
python manage.py import_semi_e187 `
  --html-dir C:\Users\eerr0\Downloads `
  --asset-dir "C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723" `
  --dry-run
```

After reviewing the dry-run:

```powershell
python manage.py import_semi_e187 `
  --html-dir C:\Users\eerr0\Downloads `
  --asset-dir "C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723" `
  --publish
```

`--dry-run` and `--publish` are mutually exclusive, and one is required. An
optional `--home-id` defaults to 60 for diagnostics and tests; the production
Nuxt configuration continues to expect ID 60.

### Parse and validation phase

Before any database or storage write, the command:

1. Resolves and validates the HTML and asset directories.
2. Verifies all five required HTML filenames.
3. Parses only known source sections with an explicitly declared mapping.
4. Verifies required headings, tables, process stages, and two case studies.
5. Resolves every required image and fails on absent or ambiguous matches.
6. Verifies Home ID 60 is a `HomePage`.
7. Checks whether each target slug is absent or belongs to a direct child
   `StandardPage` under Home.
8. Builds an in-memory import plan containing normalized page and image data.

The dry-run prints that plan, including pages to create/update, block counts,
image actions, rewritten links, disabled placeholders, warnings, and anything
left untouched.

### Write and publish phase

The publish run:

1. Gets or creates a `SEMI E187` Wagtail image collection.
2. Reuses images by deterministic import title within that collection.
3. Compares source and stored file content before replacing an existing image;
   changed files invalidate their old renditions.
4. Updates site settings and the explicit primary-navigation list.
5. Updates Home ID 60.
6. Gets or creates each direct child StandardPage by stable slug.
7. Writes complete StreamField values, SEO data, menu flags, and order.
8. Saves a revision and publishes each page.
9. Rebuilds Wagtail reference and search indexes after successful publication.

Database page/settings operations run atomically. All sources and image bytes
are validated before the transaction. If storage writes succeed but a later
database operation fails, the command removes only files/images newly created
by that invocation and reports the rollback. It never deletes pre-existing
unrelated images.

### Idempotency

- Home is always updated by ID 60.
- Child pages are updated by parent plus stable slug.
- Images are reused within the dedicated collection by deterministic title and
  content comparison.
- Re-running with unchanged inputs creates no duplicate pages or images.
- Pages outside the five-page mapping are never deleted, moved, unpublished,
  reordered, or removed from their existing generic menu state.
- A target slug occupied by a different Page type is an error, not an implicit
  conversion.

## API Design

### Page API

Keep the existing Wagtail Page API and public Nitro endpoint paths:

- `/api/bakery/home`
- `/api/bakery/navigation`
- `/api/bakery/pages/{slug}`

New StreamField block representations are added to the shared TypeScript union
and rendered by type. Unknown future blocks continue to be skipped safely.
The `/api/bakery/navigation` response shape remains unchanged, but its ordered
items come from the explicit public site-settings navigation instead of a
blanket `show_in_menus` page query.

### Site settings API

Add a read-only Wagtail JSON endpoint that identifies the current site from
the request and returns only the public site-setting fields listed above. It
includes the ordered navigation as public page IDs, titles, and Nuxt paths. It
does not serialize model internals or administrative settings.

Nitro proxies this endpoint as `/api/bakery/site-settings`, keeping the Wagtail
base URL private and applying the existing 500/404/502 error conventions.

## Nuxt Presentation Design

Replace the Bakery-branded shell with a SEMI E187 shell while retaining the
same-origin data-loading architecture.

### Site shell

- Text brand and tagline from public site settings
- Home plus API-driven StandardPage navigation
- Desktop horizontal navigation
- Keyboard-operable mobile disclosure navigation
- Skip link and visible focus treatment
- Shared contact/footer section from site settings
- Optional footer logo with no empty or broken image state

### Visual system

Implement the source palette as local CSS custom properties for navy, blue,
lime, mint, sky, text, border, and surface colors. No Tailwind runtime or
external script is loaded. Google Fonts are not required for correctness; the
font stack uses locally available Traditional Chinese system fonts first to
avoid a rendering dependency.

### Components

`StreamField.vue` delegates structured blocks to focused components:

- `CardGrid.vue`
- `DocumentTable.vue`
- `ProcessSteps.vue`
- `CaseStudy.vue`

Existing rich text, image, quote, and safe embed rendering remains available.
Internal page references become Nuxt routes. External links use
`rel="noopener noreferrer"`. A missing destination renders a disabled label
and "即將提供" rather than an anchor.

### Responsive and accessible behavior

- Semantic headings retain a single page `<h1>`.
- Tables retain headers and readable narrow-screen presentation.
- Process stages remain ordered and do not rely on color alone.
- Images include alt text, intrinsic dimensions, lazy loading below the fold,
  and responsive sizing.
- Cards and navigation have keyboard focus styles.
- Desktop and 390-pixel mobile layouts have no horizontal overflow.
- Reduced-motion preferences disable decorative transitions.

Wagtail block templates provide a semantic fallback for Wagtail page preview;
the high-fidelity presentation target is the Nuxt frontend at port 3100.

## Error Handling

- Missing required HTML or image: abort before writes with the exact missing
  path.
- Multiple matches for a required asset: abort and list every conflicting
  path.
- Missing required selector or malformed source structure: abort with the
  filename and selector/section name.
- Invalid Home ID/type: abort without fallback creation.
- Wrong Page type at a target slug: abort without replacing it.
- Missing optional ADI logo: warn and continue with a text footer.
- Placeholder URL: import as no destination, not `#`.
- Missing English file: omit the language switch, not a broken link.
- CMS outage: preserve the current Nuxt retry/error state.
- Unknown future API block: skip it without failing the entire page.

## Testing Strategy

### Django tests

- Block validation and API representation for every new structure
- Allowlisted rich-text conversion and script/style removal
- Internal route and fragment rewriting
- Placeholder and external link behavior
- Source parser mapping with minimal representative HTML fixtures
- Failure on missing/ambiguous required files before writes
- Dry-run produces an import plan without database or storage changes
- Home ID/type and target Page-type validation
- Correct page creation, menu order, revisions, and publication
- Image reuse, changed-image replacement, and rendition invalidation
- Two identical import runs produce no duplicate pages or images
- Unrelated pages remain unchanged
- Public site-settings endpoint exposes only approved fields
- Existing Wagtail render and system checks remain green

### Nuxt tests

- Shared TypeScript block types and media URL fallback
- Link resolution and disabled-placeholder presentation helpers
- Structured renderer contracts for cards, tables, process steps, and cases
- Site-settings proxy error mapping
- Existing API page/404/outage behavior
- `npm test`
- `npm run typecheck`
- `npm run build`

### Live verification

1. Stop Wagtail and create a timestamped copy of the SQLite database.
2. Run the importer with `--dry-run` and inspect its plan.
3. Run the importer with `--publish`.
4. Run focused Wagtail tests and `manage.py check`.
5. Verify Wagtail API payloads and all Nuxt proxy endpoints.
6. Inspect `/`, `/about/`, `/resources/`, `/certification/`, and
   `/ecosystem/` at desktop and 390-pixel mobile widths.
7. Confirm navigation, fragments, disabled placeholders, external links,
   images, alt text, layout, and CMS outage recovery.
8. Confirm `TEST`, `AXCC`, and `CCC` still exist and retain their state.

## Backup and Rollback

Before the first publish run, stop Wagtail and create a timestamped SQLite copy
such as `bakerydemodb.before-semi-e187-YYYYMMDD-HHMMSS`. This backup remains
untracked and is never committed.

Individual content changes can be reverted through Wagtail revisions. To undo
the full import, stop Wagtail, preserve the current database for diagnosis,
restore the timestamped backup, restart Wagtail, and verify Home ID 60 plus the
unrelated pages.

## Acceptance Criteria

- Home ID 60 is the published SEMI E187 homepage at Nuxt `/`.
- Four published direct child StandardPages appear in the agreed menu order.
- `TEST`, `AXCC`, and `CCC` retain their existing publication, position, and
  menu flags but do not appear in the explicit SEMI E187 primary navigation.
- All supplied semantic content is represented by editable Wagtail fields and
  blocks; no raw source scripts or Tailwind runtime are stored or executed.
- All three supplied JPEGs render without broken URLs.
- Missing optional logo, English page, and placeholder destinations produce no
  broken UI.
- The import command dry-runs safely and is idempotent when published twice.
- Unrelated pages and assets remain unchanged.
- Nuxt closely matches the supplied navy/blue/lime design across desktop and
  mobile layouts.
- Automated tests, type checking, production build, Wagtail checks, API smoke
  tests, and browser verification pass.
