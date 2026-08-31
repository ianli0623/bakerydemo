# SEMI E187 Multilingual Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver editable, published Traditional Chinese and English versions of all five SEMI E187 pages, with locale-aware Bakery APIs, `/en/` Nuxt routes, and the accessible toolbar from the supplied HTML.

**Architecture:** Wagtail locale-linked pages and a translatable `LocalizedSiteContent` snippet remain the sole source of editorial content. A guarded management command converts the current pages to `zh-hant`, creates English translations from a version-controlled catalog, relinks translated page references, and publishes atomically. Nuxt i18n owns route prefixes and fixed interface messages while forwarding the selected locale to the Bakery API.

**Tech Stack:** Python 3.13, Django 6, Wagtail 7.4, SQLite, Nuxt 4, Vue 3, TypeScript, `@nuxtjs/i18n`, Node test runner, vanilla CSS.

**Spec:** `docs/superpowers/specs/2026-08-31-semi-e187-multilingual-design.md`

## Global Constraints

- Supported content locales are exactly `zh-hant` and `en`; `zh-hant` is the default.
- Existing Chinese public URLs remain unchanged; English URLs use `/en/`.
- All page/editorial copy lives in Wagtail; Nuxt locale files contain interface copy only.
- The English import creates and publishes once, and must never overwrite an existing English translation.
- Images, phone numbers, email addresses, and the footer logo are shared across locales.
- Any locale or translation write runs inside a database transaction and requires a database backup first.
- JavaScript remains framework-free beyond the existing Nuxt/Vue stack; CSS remains plain CSS.
- Tests use `DJANGO_SETTINGS_MODULE=bakerydemo.settings.test` for Django rendering/model work.

## File Responsibility Map

### Wagtail

- `bakerydemo/settings/base.py`: enabled locales and simple translation admin.
- `bakerydemo/base/models.py`: editable page copy fields and `LocalizedSiteContent`.
- `bakerydemo/base/blocks.py`: editor-managed case-study labels.
- `bakerydemo/base/wagtail_hooks.py`: translated site-content snippet administration.
- `bakerydemo/base/i18n.py`: locale validation and translated-page lookup.
- `bakerydemo/base/public_api.py`: localized settings/navigation response.
- `bakerydemo/base/semi_e187/schema.py`: import schema for every visible page heading.
- `bakerydemo/base/semi_e187/parser.py`: extract the added editable copy from supplied HTML.
- `bakerydemo/base/semi_e187/publisher.py`: publish Chinese content into the localized model.
- `bakerydemo/base/semi_e187/english.py`: complete English catalog and catalog coverage validation.
- `bakerydemo/base/semi_e187/translation_publisher.py`: atomic locale conversion, translation creation, relinking, and publishing.
- `bakerydemo/base/management/commands/import_semi_e187_translations.py`: dry-run/publish CLI.
- `bakerydemo/base/migrations/0030_add_semi_editorial_fields.py`: page/block schema.
- `bakerydemo/base/migrations/0031_localizedsitecontent.py`: translated global content schema and existing-value migration.

### Nuxt

- `nuxt-bakery-demo/nuxt.config.ts`: Nuxt i18n registration and route strategy.
- `nuxt-bakery-demo/i18n/locales/zh-hant.json`: fixed Traditional Chinese interface labels.
- `nuxt-bakery-demo/i18n/locales/en.json`: fixed English interface labels.
- `nuxt-bakery-demo/shared/utils/locale.ts`: pure locale/path helpers shared by client and server.
- `nuxt-bakery-demo/server/utils/bakery-locale.ts`: validates the locale query on Nitro requests.
- `nuxt-bakery-demo/server/utils/bakery-pages.ts`: locale-aware home/page lookup without ID `60`.
- `nuxt-bakery-demo/server/utils/bakery-settings.ts`: validates the expanded localized settings payload.
- `nuxt-bakery-demo/shared/types/bakery.ts`: localized API/page fields.
- `nuxt-bakery-demo/app/utils/accessibility.ts`: pure font-scale reducer/storage guard.
- `nuxt-bakery-demo/app/components/AccessibilityToolbar.vue`: desktop toolbar and language links.
- `nuxt-bakery-demo/app/app.vue`: localized shell, footer, mobile language switch.
- `nuxt-bakery-demo/app/pages/index.vue`: localized home fetch and CMS-managed hero copy.
- `nuxt-bakery-demo/app/pages/[slug].vue`: localized standard-page fetch and error copy.
- `nuxt-bakery-demo/app/utils/site-presentation.ts`: present CMS fields without hard-coded Chinese headings.
- `nuxt-bakery-demo/app/utils/stream-field.ts` and block components: localized fixed labels and internal links.
- `nuxt-bakery-demo/app/assets/css/main.css`: 36px toolbar, active locale, and font scale styles.

---

### Task 1: Make every visible page heading editable in Wagtail

**Files:**
- Modify: `bakerydemo/base/models.py:235-455`
- Modify: `bakerydemo/base/blocks.py:210-248`
- Modify: `bakerydemo/base/semi_e187/schema.py`
- Modify: `bakerydemo/base/semi_e187/parser.py`
- Modify: `bakerydemo/base/semi_e187/publisher.py`
- Create: `bakerydemo/base/migrations/0030_add_semi_editorial_fields.py`
- Test: `bakerydemo/base/tests/test_home_page.py`
- Test: `bakerydemo/base/tests/test_semi_blocks.py`
- Test: `bakerydemo/base/tests/test_semi_import_parser.py`
- Test: `bakerydemo/base/tests/test_import_semi_e187.py`

**Interfaces:**
- Produces: `HomePage.hero_badge`, `secondary_hero_cta`, `secondary_hero_cta_link`, `secondary_hero_cta_fragment`.
- Produces: `StandardPage.section_kicker`, `section_heading`, `secondary_section_kicker`, `secondary_section_heading`, `secondary_section_introduction`.
- Produces: `CaseStudyBlock.security_controls_heading` and matching `BakeryCaseStudyBlock` API field.
- Consumes: the existing five-page parser and publisher flow.

- [ ] **Step 1: Write failing model/API-field tests**

```python
def test_semi_editorial_fields_are_exposed_to_the_api(self):
    home_fields = {field.field_name for field in HomePage.api_fields}
    page_fields = {field.field_name for field in StandardPage.api_fields}
    self.assertTrue({
        "hero_badge",
        "secondary_hero_cta",
        "secondary_hero_cta_link",
        "secondary_hero_cta_fragment",
    } <= home_fields)
    self.assertTrue({
        "section_kicker",
        "section_heading",
        "secondary_section_kicker",
        "secondary_section_heading",
        "secondary_section_introduction",
    } <= page_fields)
```

- [ ] **Step 2: Write failing parser tests for source headings**

```python
def test_parser_preserves_visible_section_copy(self):
    plan = parse_source_site(self.html_dir, self.asset_dir)
    self.assertEqual(plan.home.hero_badge, "標準認知 × 技術資源 × 驗證合規")
    self.assertEqual(plan.page("about").section_kicker, "ABOUT SEMI E187")
    self.assertEqual(plan.page("ecosystem").secondary_section_heading, "設備廠商導入應用案例")
    case = next(block for block in plan.page("ecosystem").body if block.type == "case_study")
    self.assertEqual(case.value["security_controls_heading"], "資安控制重點")
```

- [ ] **Step 3: Run focused tests and confirm they fail**

Run:

```powershell
$env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
./manage.py test bakerydemo.base.tests.test_home_page bakerydemo.base.tests.test_semi_blocks bakerydemo.base.tests.test_semi_import_parser
```

Expected: failures identify the missing page fields, schema attributes, and `security_controls_heading` block key.

- [ ] **Step 4: Add the fields, panels, API fields, schema properties, and parser extraction**

Use explicit Wagtail fields:

```python
hero_badge = models.CharField(max_length=255, blank=True, default="")
secondary_hero_cta = models.CharField(max_length=255, blank=True, default="")
secondary_hero_cta_link = models.ForeignKey(
    "wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL,
    related_name="+",
)
secondary_hero_cta_fragment = models.CharField(max_length=100, blank=True, default="")

section_kicker = models.CharField(max_length=100, blank=True, default="")
section_heading = models.CharField(max_length=255, blank=True, default="")
secondary_section_kicker = models.CharField(max_length=100, blank=True, default="")
secondary_section_heading = models.CharField(max_length=255, blank=True, default="")
secondary_section_introduction = models.TextField(blank=True, default="")
```

Add `security_controls_heading = CharBlock(required=True)` before `security_controls`. Extend `HomeImport` and `PageImport` with the same names, parse the supplied DOM headings, and assign every value in `apply_page_content()`. Set the home secondary CTA target to the certification page and save `certified-list` in `secondary_hero_cta_fragment` so Nuxt can construct the editable link without a hard-coded fragment.

- [ ] **Step 5: Generate and inspect the schema migration**

Run:

```powershell
./manage.py makemigrations base --name add_semi_editorial_fields
./manage.py makemigrations --check
```

Add a `RunPython` operation to the generated migration that inserts `security_controls_heading: "資安控制重點"` into each existing `case_study` block before the `AlterField` operation makes the child required. Expected: only `0030_add_semi_editorial_fields.py` is generated and `makemigrations --check` reports no pending changes.

- [ ] **Step 6: Run parser, block, model, and importer tests**

Run:

```powershell
$env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
./manage.py test bakerydemo.base.tests.test_home_page bakerydemo.base.tests.test_semi_blocks bakerydemo.base.tests.test_semi_import_parser bakerydemo.base.tests.test_import_semi_e187
```

Expected: PASS.

- [ ] **Step 7: Commit the editable content contract**

```powershell
git add bakerydemo/base/models.py bakerydemo/base/blocks.py bakerydemo/base/semi_e187/schema.py bakerydemo/base/semi_e187/parser.py bakerydemo/base/semi_e187/publisher.py bakerydemo/base/migrations/0030_add_semi_editorial_fields.py bakerydemo/base/tests
git commit -m "feat: make SEMI editorial headings editable"
```

### Task 2: Add translated global site content and Wagtail editing UI

**Files:**
- Modify: `bakerydemo/settings/base.py:45-60,159-274`
- Modify: `bakerydemo/base/models.py:603-650`
- Modify: `bakerydemo/base/wagtail_hooks.py`
- Modify: `bakerydemo/base/semi_e187/schema.py`
- Modify: `bakerydemo/base/semi_e187/parser.py`
- Modify: `bakerydemo/base/semi_e187/publisher.py`
- Create: `bakerydemo/base/migrations/0031_localizedsitecontent.py`
- Create: `bakerydemo/base/tests/test_localized_site_content.py`
- Modify: `bakerydemo/base/tests/test_import_semi_e187.py`

**Interfaces:**
- Produces: `LocalizedSiteContent.for_site_and_locale(site, locale)` returning one live localized record or `None`.
- Produces: shared `SiteSettings.contact_phone`, `contact_email`, `footer_logo`, and `primary_navigation`.
- Consumes: Task 1 parser/schema output.

- [ ] **Step 1: Write failing translated-snippet tests**

```python
def test_site_content_is_unique_per_site_and_locale(self):
    zh = Locale.objects.get_or_create(language_code="zh-hant")[0]
    LocalizedSiteContent.objects.create(site=self.site, locale=zh, site_name="SEMI E187")
    with self.assertRaises(IntegrityError):
        with transaction.atomic():
            LocalizedSiteContent.objects.create(site=self.site, locale=zh, site_name="Duplicate")

def test_published_translation_can_be_edited_independently(self):
    english = self.zh_content.copy_for_translation(self.en_locale)
    english.site_name = "SEMI E187 Cybersecurity Certification"
    english.save_revision().publish()
    self.assertEqual(self.zh_content.site_name, "SEMI E187 半導體設備資安標準")
```

- [ ] **Step 2: Run the focused test and confirm the model is missing**

Run:

```powershell
$env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
./manage.py test bakerydemo.base.tests.test_localized_site_content
```

Expected: import failure for `LocalizedSiteContent`.

- [ ] **Step 3: Implement the translatable snippet and locale settings**

Model inheritance and constraints:

```python
class LocalizedSiteContent(
    DraftStateMixin,
    RevisionMixin,
    PreviewableMixin,
    TranslatableMixin,
    models.Model,
):
    site = models.ForeignKey("wagtailcore.Site", on_delete=models.CASCADE)
    brand_label = models.CharField(max_length=100, blank=True, default="")
    title_suffix = models.CharField(max_length=255, blank=True, default="")
    site_name = models.CharField(max_length=255, blank=True, default="")
    site_tagline = models.CharField(max_length=255, blank=True, default="")
    contact_heading = models.CharField(max_length=255, blank=True, default="")
    contact_name = models.CharField(max_length=100, blank=True, default="")
    contact_context = models.CharField(max_length=255, blank=True, default="")
    footer_introduction = models.TextField(blank=True, default="")
    organisation_text = models.TextField(blank=True, default="")

    @classmethod
    def for_site_and_locale(cls, site, locale):
        return cls.objects.filter(site=site, locale=locale, live=True).first()

    class Meta(TranslatableMixin.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=("site", "locale"),
                name="unique_site_content_per_site_locale",
            )
        ]
```

Add a revisions `GenericRelation`, publishing panels, and a `SnippetViewSet` in the existing Bakery group. Enable `wagtail.contrib.simple_translation`; set `LANGUAGE_CODE = "zh-hant"` and set both `LANGUAGES` and `WAGTAIL_CONTENT_LANGUAGES` to `zh-hant` and `en` only.

- [ ] **Step 4: Move translated fields out of `SiteSettings` and generate a data migration**

Keep `contact_phone`, `contact_email`, `footer_logo`, and `primary_navigation` on `SiteSettings`. The migration creates `zh-hant`, copies existing site name/tagline/contact/organisation values into one published `LocalizedSiteContent` per site, then removes those translated columns from `SiteSettings`. Seed `brand_label` as `認驗證制度` and seed the existing footer paragraph as `footer_introduction` for the SEMI site.

Run:

```powershell
./manage.py makemigrations base --name localizedsitecontent
./manage.py makemigrations --check
```

Expected: `0031_localizedsitecontent.py` contains create, copy, and remove operations with no pending model changes.

- [ ] **Step 5: Update the Chinese publisher to create/update localized site content**

`apply_site_settings()` must write shared fields to `SiteSettings`, then update the live `zh-hant` `LocalizedSiteContent`. Add `brand_label` and `footer_introduction` to `SiteSettingsImport` so a fresh SEMI import produces the same editable content as the migrated database.

- [ ] **Step 6: Run snippet and importer tests**

Run:

```powershell
$env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
./manage.py test bakerydemo.base.tests.test_localized_site_content bakerydemo.base.tests.test_import_semi_e187
```

Expected: PASS, including a published Chinese site-content revision.

- [ ] **Step 7: Commit translated global content**

```powershell
git add bakerydemo/settings/base.py bakerydemo/base/models.py bakerydemo/base/wagtail_hooks.py bakerydemo/base/semi_e187 bakerydemo/base/migrations/0031_localizedsitecontent.py bakerydemo/base/tests
git commit -m "feat: add editable localized site content"
```

### Task 3: Make Bakery settings and navigation APIs locale-aware

**Files:**
- Create: `bakerydemo/base/i18n.py`
- Modify: `bakerydemo/base/public_api.py`
- Modify: `bakerydemo/base/tests/test_site_settings_api.py`

**Interfaces:**
- Produces: `SUPPORTED_LOCALES = ("zh-hant", "en")`.
- Produces: `resolve_locale(code: str) -> Locale` raising `UnsupportedLocale`.
- Produces: `translated_page(page: Page, locale: Locale) -> Page` raising `TranslationUnavailable` unless live/public.
- Produces settings JSON fields `locale`, `home_page_id`, `home_path`, `footer_introduction`.
- Consumes: `LocalizedSiteContent.for_site_and_locale()` from Task 2.

- [ ] **Step 1: Add failing API tests for locale selection and rejection**

```python
def test_english_settings_return_english_navigation_paths(self):
    response = self.client.get("/api/site-settings/?locale=en", HTTP_HOST="localhost")
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["locale"], "en")
    self.assertEqual(response.json()["home_path"], "/en/")
    self.assertEqual(response.json()["navigation"][1]["path"], "/en/about/")

def test_unsupported_locale_is_rejected(self):
    response = self.client.get("/api/site-settings/?locale=de", HTTP_HOST="localhost")
    self.assertEqual(response.status_code, 400)
    self.assertEqual(response.json(), {"error": "Unsupported locale: de"})
```

Also test missing/unpublished site content and missing/unpublished translated pages return 404 without falling back to Chinese.

- [ ] **Step 2: Run the API tests and confirm locale behavior fails**

Run:

```powershell
$env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
./manage.py test bakerydemo.base.tests.test_site_settings_api
```

Expected: the old endpoint ignores `locale` and omits new response fields.

- [ ] **Step 3: Implement locale resolution and translated page lookup**

```python
SUPPORTED_LOCALES = ("zh-hant", "en")

def resolve_locale(code: str) -> Locale:
    if code not in SUPPORTED_LOCALES:
        raise UnsupportedLocale(code)
    return Locale.objects.get(language_code=code)

def translated_page(page: Page, locale: Locale) -> Page:
    candidate = page if page.locale_id == locale.pk else page.get_translation(locale)
    if not candidate.live or candidate.get_view_restrictions().exists():
        raise TranslationUnavailable
    return candidate.specific
```

Use the helper for the site root and every selected navigation page. Catch Wagtail's translation lookup exception and raise `TranslationUnavailable` so the endpoint returns a localized-content 404 instead of a server error.

- [ ] **Step 4: Return deterministic Nuxt paths**

Build `/` or `/<slug>/` relative to the localized home and prefix English with `/en`. Include `slug` in every navigation item. Never use backend `html_url` to construct Nuxt routes.

- [ ] **Step 5: Run API tests and Django checks**

Run:

```powershell
$env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
./manage.py test bakerydemo.base.tests.test_site_settings_api
./manage.py check
```

Expected: PASS.

- [ ] **Step 6: Commit locale-aware public APIs**

```powershell
git add bakerydemo/base/i18n.py bakerydemo/base/public_api.py bakerydemo/base/tests/test_site_settings_api.py
git commit -m "feat: localize Bakery public settings API"
```

### Task 4: Create and publish the complete English content catalog

**Files:**
- Create: `bakerydemo/base/semi_e187/english.py`
- Create: `bakerydemo/base/semi_e187/translation_publisher.py`
- Create: `bakerydemo/base/management/commands/import_semi_e187_translations.py`
- Create: `bakerydemo/base/tests/test_semi_english_catalog.py`
- Create: `bakerydemo/base/tests/test_import_semi_e187_translations.py`

**Interfaces:**
- Produces: `translate_import_plan(source: ImportPlan) -> ImportPlan`.
- Produces: `find_untranslated_paths(source: ImportPlan, catalog: Mapping[str, str]) -> tuple[str, ...]`.
- Produces: `publish_translations(source_plan, translated_plan, home_id: int) -> TranslationPublishResult`.
- Produces command arguments `--html-dir`, `--asset-dir`, `--home-id`, and exactly one of `--dry-run`/`--publish`.
- Consumes: Tasks 1–3 page fields, locale helpers, and localized global content.

- [ ] **Step 1: Write failing catalog coverage tests**

```python
def test_english_catalog_covers_every_editorial_string(self):
    source = parse_source_site(self.html_dir, self.asset_dir)
    missing = find_untranslated_paths(source, ENGLISH_CATALOG)
    self.assertEqual(missing, ())

def test_translated_plan_contains_no_unapproved_han_copy(self):
    translated = translate_import_plan(parse_source_site(self.html_dir, self.asset_dir))
    self.assertEqual(find_han_editorial_paths(translated), ())
```

Exclude stable technical values only: slugs, anchor IDs, layout values, URLs, filenames, company legal names explicitly retained by editorial decision, and numeric labels.

- [ ] **Step 2: Implement path-based immutable catalog translation**

```python
ENGLISH_CATALOG = MappingProxyType({
    "home.title": "SEMI E187 Semiconductor Equipment Cybersecurity Certification",
    "home.hero_badge": "STANDARD AWARENESS × IMPLEMENTATION RESOURCES × CERTIFICATION",
    "home.hero_cta": "Learn About the Standard",
    "settings.brand_label": "Certification Scheme",
    "pages.about.title": "About the Standard",
    "pages.resources.title": "Implementation Resources",
    "pages.certification.title": "Certification and Compliance",
    "pages.ecosystem.title": "Case Studies and Ecosystem",
})
```

The committed catalog must contain the final professional English translation for every path returned by the source-plan walker, including all rich-text HTML, cards, table rows, process steps, cases, captions, SEO fields, and global site content. Preserve HTML tags while translating their text nodes.

- [ ] **Step 3: Translate and editorially review one page at a time**

Add catalog entries in this order and run the coverage test after each group:

```powershell
$env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
./manage.py test bakerydemo.base.tests.test_semi_english_catalog
```

Order: homepage/global settings, about, resources, certification, ecosystem/case studies. Expected after the final group: PASS with zero missing editorial paths and zero unapproved Han copy.

- [ ] **Step 4: Write failing publisher/command tests**

Cover these exact behaviors: dry-run performs no writes; the five source pages are changed to `zh-hant`; five `en` pages share each source `translation_key`; English page references point only to English pages; images are reused; English site content is live; all five pages are live; a second publish raises `CommandError`; a missing target translation rolls back all created English records.

- [ ] **Step 5: Implement the atomic translation publisher**

```python
@transaction.atomic
def publish_translations(source_plan, translated_plan, home_id):
    zh = resolve_locale("zh-hant")
    en = resolve_locale("en")
    source_pages = load_exact_semi_pages(home_id)
    assert_no_existing_translations(source_pages, en)
    set_source_locale(source_pages, zh)
    translated_pages = copy_translation_tree(source_pages, en)
    apply_page_content(translated_plan, translated_pages, existing_images(source_plan))
    relink_page_references(translated_pages)
    publish_localized_site_content(translated_plan.settings, en)
    publish_all(translated_pages)
    return build_translation_result(translated_pages)
```

Wrap command errors as `CommandError`, validate the full catalog before entering the transaction, and run reference/search index updates after successful commit.

- [ ] **Step 6: Run catalog, publisher, and existing importer tests**

Run:

```powershell
$env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
./manage.py test bakerydemo.base.tests.test_semi_english_catalog bakerydemo.base.tests.test_import_semi_e187_translations bakerydemo.base.tests.test_import_semi_e187
```

Expected: PASS.

- [ ] **Step 7: Commit the English content publisher**

```powershell
git add bakerydemo/base/semi_e187/english.py bakerydemo/base/semi_e187/translation_publisher.py bakerydemo/base/management/commands/import_semi_e187_translations.py bakerydemo/base/tests
git commit -m "feat: publish editable SEMI English translations"
```

### Task 5: Add Nuxt i18n and locale-aware server APIs

**Files:**
- Modify: `nuxt-bakery-demo/package.json`
- Modify: `nuxt-bakery-demo/package-lock.json`
- Modify: `nuxt-bakery-demo/nuxt.config.ts`
- Create: `nuxt-bakery-demo/i18n/locales/zh-hant.json`
- Create: `nuxt-bakery-demo/i18n/locales/en.json`
- Create: `nuxt-bakery-demo/shared/utils/locale.ts`
- Create: `nuxt-bakery-demo/server/utils/bakery-locale.ts`
- Modify: `nuxt-bakery-demo/shared/types/bakery.ts`
- Modify: `nuxt-bakery-demo/server/utils/bakery-pages.ts`
- Modify: `nuxt-bakery-demo/server/utils/bakery-settings.ts`
- Modify: `nuxt-bakery-demo/server/api/bakery/home.get.ts`
- Modify: `nuxt-bakery-demo/server/api/bakery/site-settings.get.ts`
- Modify: `nuxt-bakery-demo/server/api/bakery/navigation.get.ts`
- Modify: `nuxt-bakery-demo/server/api/bakery/pages/[slug].get.ts`
- Create: `nuxt-bakery-demo/tests/locale.test.ts`
- Modify: `nuxt-bakery-demo/tests/bakery-pages.test.ts`
- Modify: `nuxt-bakery-demo/tests/bakery-settings.test.ts`

**Interfaces:**
- Produces: `type BakeryLocale = 'zh-hant' | 'en'`.
- Produces: `normalizeBakeryLocale(value: unknown): BakeryLocale`.
- Produces: `getBakeryLocale(event: H3Event): BakeryLocale`.
- Produces: `createStandardPageQuery(slug, homePageId, locale)` with no global home ID.
- Consumes: Task 3 settings payload.

- [ ] **Step 1: Write failing pure locale/API-query tests**

```typescript
test('locale normalization accepts only the public locales', () => {
  assert.equal(normalizeBakeryLocale('zh-hant'), 'zh-hant')
  assert.equal(normalizeBakeryLocale('en'), 'en')
  assert.throws(() => normalizeBakeryLocale('de'), /locale/i)
})

test('page query uses the localized home instead of ID 60', () => {
  assert.deepEqual(createStandardPageQuery('about', 160, 'en'), {
    type: 'base.StandardPage', child_of: '160', locale: 'en',
    slug: 'about', fields: '*', limit: '1'
  })
})
```

- [ ] **Step 2: Run Nuxt tests and confirm the helpers are missing**

Run:

```powershell
Set-Location nuxt-bakery-demo
npm test
```

Expected: the new imports/functions fail before implementation.

- [ ] **Step 3: Install and configure Nuxt i18n**

Run:

```powershell
Set-Location nuxt-bakery-demo
npm install @nuxtjs/i18n
```

Configure:

```typescript
modules: ['@nuxtjs/i18n'],
i18n: {
  strategy: 'prefix_except_default',
  defaultLocale: 'zh-hant',
  langDir: 'locales',
  locales: [
    { code: 'zh-hant', language: 'zh-Hant', name: '繁體中文', file: 'zh-hant.json' },
    { code: 'en', language: 'en', name: 'English', file: 'en.json' }
  ]
}
```

Put fixed labels such as skip link, font controls, navigation, contact field labels, loading/errors, retry, document-table columns, unavailable status, embed labels, and mobile menu labels in both locale JSON files.

- [ ] **Step 4: Expand types and settings validation**

Add `locale`, `home_page_id`, `home_path`, `footer_introduction`, and navigation `slug`. Add the Task 1 CMS fields to home/standard page and `security_controls_heading` to case-study types. Reject payloads with an unsupported locale or unsafe localized path.

- [ ] **Step 5: Forward locale through every Nitro endpoint**

Each endpoint calls `getBakeryLocale(event)`. Settings requests call `/api/site-settings/` with `{ locale }`. Home first obtains localized settings, fetches `/api/v2/pages/<home_page_id>/`, then enriches links with that locale. Standard page queries use `settings.home_page_id` and include `locale`.

- [ ] **Step 6: Run Nuxt unit tests, typecheck, and build**

Run:

```powershell
Set-Location nuxt-bakery-demo
npm test
npm run typecheck
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit locale infrastructure**

```powershell
git add nuxt-bakery-demo
git commit -m "feat: add locale-aware Nuxt Bakery APIs"
```

### Task 6: Localize routes, page presentation, and all fixed interface copy

**Files:**
- Modify: `nuxt-bakery-demo/app/app.vue`
- Modify: `nuxt-bakery-demo/app/pages/index.vue`
- Modify: `nuxt-bakery-demo/app/pages/[slug].vue`
- Modify: `nuxt-bakery-demo/app/utils/site-presentation.ts`
- Modify: `nuxt-bakery-demo/app/utils/stream-field.ts`
- Modify: `nuxt-bakery-demo/app/components/StreamField.vue`
- Modify: `nuxt-bakery-demo/app/components/blocks/ContentLink.vue`
- Modify: `nuxt-bakery-demo/app/components/blocks/DocumentTable.vue`
- Modify: `nuxt-bakery-demo/app/components/blocks/CaseStudy.vue`
- Modify: `nuxt-bakery-demo/app/assets/css/main.css`
- Modify: `nuxt-bakery-demo/tests/semi-presentation.test.ts`
- Modify: `nuxt-bakery-demo/tests/stream-field.test.ts`

**Interfaces:**
- Produces: `getStandardPagePresentation(slug, page)` using only CMS editorial fields for headings/descriptions.
- Produces: localized internal content links through `useLocalePath()`.
- Consumes: Task 5 Nuxt i18n composables, locale messages, and page types.

- [ ] **Step 1: Replace presentation tests that expect hard-coded Chinese**

```typescript
test('standard page presentation uses translated CMS headings', () => {
  const page = standardPage('about', 'About the Standard', '', [])
  page.section_kicker = 'ABOUT SEMI E187'
  page.section_heading = 'Background and Purpose'
  const presentation = getStandardPagePresentation('about', page)
  assert.equal(presentation.sections[0]!.title, 'Background and Purpose')
})
```

Add an ecosystem assertion that the secondary heading/introduction come from `page.secondary_section_*`, and a home assertion that news selection no longer compares against `最新消息`.

- [ ] **Step 2: Run focused tests and confirm old presentation behavior fails**

Run:

```powershell
Set-Location nuxt-bakery-demo
node --test --experimental-strip-types tests/semi-presentation.test.ts tests/stream-field.test.ts
```

Expected: assertions fail while titles and detection remain hard-coded.

- [ ] **Step 3: Make presentation functions content-driven**

Use `section_kicker`/`section_heading` for the primary section and `secondary_section_*` for the ecosystem case section. Detect the home news card as the first `card_grid` in the validated home structure, not by translated heading. Render `security_controls_heading` from the case block. Remove the localized CSS string `content: '查看公告 →'`; render link label/arrow in markup.

- [ ] **Step 4: Localize shell and route-aware fetches**

In each page:

```typescript
const { locale, t } = useI18n()
const localeQuery = computed(() => ({ locale: locale.value }))
await useFetch('/api/bakery/home', { query: localeQuery })
```

Use `useLocalePath()` for brand, navigation, footer, CTA, and internal block links. Use `useSwitchLocalePath()` for the mobile language links. Replace all interface-facing literal Chinese text found by `rg -n "[\p{Han}]" nuxt-bakery-demo/app` with `$t(...)`, except content received from Bakery and the literal language name `繁體中文`.

- [ ] **Step 5: Add locale SEO metadata**

Set `useHead({ htmlAttrs: { lang } })`, canonical URL, and `link` alternates for `zh-Hant` and `en`. Titles/descriptions come from the localized CMS response; error and empty states come from locale messages.

- [ ] **Step 6: Run tests and scan for accidental fixed Chinese**

Run:

```powershell
Set-Location nuxt-bakery-demo
npm test
npm run typecheck
rg -n "[\p{Han}]" app --glob '*.vue' --glob '*.ts' --glob '*.css'
```

Expected: tests PASS; remaining Han text is limited to the displayed locale name or explicit test fixtures, not English-route interface copy.

- [ ] **Step 7: Commit localized page rendering**

```powershell
git add nuxt-bakery-demo/app nuxt-bakery-demo/tests nuxt-bakery-demo/i18n
git commit -m "feat: render localized SEMI pages and interface"
```

### Task 7: Add the accessible toolbar and persistent font controls

**Files:**
- Create: `nuxt-bakery-demo/app/utils/accessibility.ts`
- Create: `nuxt-bakery-demo/app/components/AccessibilityToolbar.vue`
- Modify: `nuxt-bakery-demo/app/app.vue`
- Modify: `nuxt-bakery-demo/app/assets/css/main.css`
- Create: `nuxt-bakery-demo/tests/accessibility.test.ts`

**Interfaces:**
- Produces: `type FontScale = 'small' | 'default' | 'large'`.
- Produces: `reduceFontScale(current, action) -> FontScale`.
- Produces: `readStoredFontScale(storage) -> FontScale` and `writeStoredFontScale(storage, value) -> void`, both tolerant of unavailable storage.
- Consumes: Task 5 locale messages and Nuxt locale-switch routes.

- [ ] **Step 1: Write failing font-control tests**

```typescript
test('font scale controls clamp to three supported values', () => {
  assert.equal(reduceFontScale('default', 'increase'), 'large')
  assert.equal(reduceFontScale('large', 'increase'), 'large')
  assert.equal(reduceFontScale('default', 'decrease'), 'small')
  assert.equal(reduceFontScale('small', 'reset'), 'default')
})

test('invalid stored values fall back without throwing', () => {
  assert.equal(readStoredFontScale({ getItem: () => 'huge' }), 'default')
  assert.doesNotThrow(() => writeStoredFontScale({ setItem: () => { throw new Error('blocked') } }, 'large'))
})
```

- [ ] **Step 2: Run the focused test and confirm helpers are missing**

Run:

```powershell
Set-Location nuxt-bakery-demo
node --test --experimental-strip-types tests/accessibility.test.ts
```

Expected: module/function import failure.

- [ ] **Step 3: Implement pure font-scale logic and client mounting behavior**

Use localStorage key `semi-e187-font-scale`. On mount, read it and set `document.documentElement.dataset.fontScale`. The three controls set `small`, `default`, or `large`; no storage access occurs during SSR.

- [ ] **Step 4: Build the toolbar component**

Render the source layout semantics:

```vue
<aside class="accessibility-toolbar" :aria-label="t('accessibility.toolbar')">
  <div class="accessibility-toolbar__inner">
    <div class="accessibility-toolbar__controls">
      <a href="#main-content">{{ t('accessibility.skip') }}</a>
      <span aria-hidden="true">|</span>
      <span>{{ t('accessibility.fontSize') }}</span>
      <button type="button" @click="increase">A+</button>
      <button type="button" @click="reset">A</button>
      <button type="button" @click="decrease">A-</button>
    </div>
    <div class="accessibility-toolbar__locales">
      <NuxtLink :to="switchLocalePath('zh-hant')" lang="zh-Hant">繁體中文</NuxtLink>
      <NuxtLink :to="switchLocalePath('en')" lang="en">English</NuxtLink>
    </div>
  </div>
</aside>
```

Add `aria-pressed` to the active font scale and `aria-current="page"` to the active locale.

- [ ] **Step 5: Add responsive styles and mobile language entry**

The desktop toolbar is 36px, navy, white text, and uses the same max-width as the header. Hide it below 900px and render both locale choices inside the existing mobile navigation. Define `html[data-font-scale='small'] { font-size: 93.75%; }` and `large` at `112.5%`; preserve the browser zoom and responsive layout.

- [ ] **Step 6: Run accessibility tests, full Nuxt verification, and build**

Run:

```powershell
Set-Location nuxt-bakery-demo
npm test
npm run typecheck
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit the toolbar**

```powershell
git add nuxt-bakery-demo/app/components/AccessibilityToolbar.vue nuxt-bakery-demo/app/utils/accessibility.ts nuxt-bakery-demo/app/app.vue nuxt-bakery-demo/app/assets/css/main.css nuxt-bakery-demo/tests/accessibility.test.ts
git commit -m "feat: add accessible language and font toolbar"
```

### Task 8: Back up, migrate, import, and verify the complete site

**Files:**
- Modify only if verification exposes an in-scope defect: files owned by Tasks 1–7
- Verify data file: `bakerydemodb`
- Create local backup: `bakerydemodb.before-i18n-20260831`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: migrated local database with five live `zh-hant` pages, five live `en` translations, and two live localized site-content records.

- [ ] **Step 1: Confirm a clean worktree and create a recoverable database backup**

Run:

```powershell
git status --short
if (Test-Path -LiteralPath 'bakerydemodb.before-i18n-20260831') { throw 'Backup already exists; choose a new dated filename instead of overwriting it.' }
Copy-Item -LiteralPath 'bakerydemodb' -Destination 'bakerydemodb.before-i18n-20260831' -ErrorAction Stop
```

Expected: only intentionally ignored/local database files are outside Git, and the backup has the same byte length as `bakerydemodb`.

- [ ] **Step 2: Apply schema migrations and Django checks**

Run:

```powershell
./manage.py migrate
./manage.py check
```

Expected: migrations `0030` and `0031` apply and system checks report no issues.

- [ ] **Step 3: Dry-run the complete English import**

Run:

```powershell
./manage.py import_semi_e187_translations --html-dir 'C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723' --asset-dir 'C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723' --home-id 60 --dry-run
```

Expected: reports five source pages, five English translations, zero missing catalog paths, reused images, localized links, and no database writes.

- [ ] **Step 4: Publish the English translations once**

Run:

```powershell
./manage.py import_semi_e187_translations --html-dir 'C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723' --asset-dir 'C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723' --home-id 60 --publish
```

Expected: five English pages and English localized site content are created and published. Immediately rerun with `--dry-run`; it must report that translations already exist and would not be overwritten.

- [ ] **Step 5: Run the full automated verification suite**

Run:

```powershell
$env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
./manage.py test
Set-Location nuxt-bakery-demo
npm test
npm run typecheck
npm run build
Set-Location ..
make lint
```

Expected: all commands PASS. If the repository's known frontend-tooling migration prevents `make lint`, run the targeted Django/Nuxt checks above, record the exact lint limitation, and do not mask unrelated failures.

- [ ] **Step 6: Start both applications and verify ten public routes**

Backend:

```powershell
./manage.py runserver 8000
```

Frontend in a second terminal:

```powershell
Set-Location nuxt-bakery-demo
npm run dev
```

Verify `/`, `/about/`, `/resources/`, `/certification/`, `/ecosystem/` and their `/en/` equivalents at `http://localhost:3100`. Check matching translated navigation, internal links, `<html lang>`, canonical/hreflang, desktop toolbar, mobile language menu, keyboard focus, and persisted font size.

- [ ] **Step 7: Verify direct Wagtail editing**

At `http://localhost:8000/admin/`, edit one English paragraph and the English footer introduction, preview each, publish, confirm the changes at `http://localhost:3100/en/`, then restore the approved English wording and publish again.

- [ ] **Step 8: Commit any verification-only fixes and record final status**

If verification required changes:

```powershell
git add bakerydemo nuxt-bakery-demo
git commit -m "fix: complete multilingual integration verification"
```

Finish with `git status --short`, `git log -8 --oneline`, and a concise report of migrations, imported page IDs, tests, build, manual routes, and the backup path.
