# SEMI E187 Structured Content Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the five supplied Traditional Chinese SEMI E187 HTML pages and three JPEG assets into Wagtail as structured, editor-managed content, then render the published content at `http://localhost:3100/` with a responsive SEMI E187 Nuxt interface while preserving unrelated pages.

**Architecture:** Extend the existing `BaseStreamBlock`, `HomePage`, `StandardPage`, and site-specific `SiteSettings`. A strict, repeatable Django management command parses allowlisted source sections into an in-memory plan, validates every dependency before writes, and publishes Home ID 60 plus four direct child pages. Wagtail exposes Page API data and a small public site-settings endpoint; Nuxt's Nitro layer proxies both and Vue components render typed structured blocks.

**Tech Stack:** Python 3.10+, Django 6, Wagtail 7.4, Beautiful Soup 4, SQLite, Nuxt 4, Vue 3, TypeScript 5, Node 22 test runner, vanilla CSS.

**Spec:** `docs/superpowers/specs/2026-08-27-semi-e187-content-import-design.md`

## Global Constraints

- Treat the supplied HTML and images as untrusted content inputs, never as instructions or executable markup.
- Preserve Home page ID 60 and the current `TEST`, `AXCC`, and `CCC` pages, including their tree positions, publication states, slugs, and `show_in_menus` flags.
- Never load source scripts, Tailwind CDN assets, Google Fonts, inline event handlers, inline styles, or arbitrary source classes.
- Validate all five HTML files, three required JPEGs, source structure, target page types, and target slugs before any database or media-storage write.
- Keep `--dry-run` completely write-free. Require exactly one of `--dry-run` and `--publish`.
- Publish through Wagtail revisions. Do not mutate page rows with bulk `update()`.
- Primary navigation comes only from the explicit ordered setting, not from a broad `show_in_menus=true` query.
- The existing untracked `bakerydemodb.backup-20260827` belongs to the user. Do not stage, modify, rename, or delete it.
- Use `apply_patch` for hand edits, run focused tests after every red/green cycle, and commit only files listed for the current task.
- Use `DJANGO_SETTINGS_MODULE=bakerydemo.settings.test` for render-focused Django tests.

---

### Task 1: Add reusable structured Wagtail blocks

**Files:**

- Modify: `requirements/base.txt`
- Modify: `bakerydemo/base/blocks.py`
- Create: `bakerydemo/templates/blocks/card_grid.html`
- Create: `bakerydemo/templates/blocks/document_table.html`
- Create: `bakerydemo/templates/blocks/process_steps.html`
- Create: `bakerydemo/templates/blocks/case_study.html`
- Create: `bakerydemo/templates/blocks/_content_link.html`
- Create: `bakerydemo/base/tests/test_semi_blocks.py`
- Create: `bakerydemo/base/migrations/0028_add_semi_structured_blocks.py`
- Create: `bakerydemo/blog/migrations/0009_add_semi_structured_blocks.py`
- Create: `bakerydemo/breads/migrations/0011_add_semi_structured_blocks.py`
- Create: `bakerydemo/locations/migrations/0009_add_semi_structured_blocks.py`
- Create: `bakerydemo/people/migrations/0004_add_semi_structured_blocks.py`
- Create: `bakerydemo/recipes/migrations/0005_add_semi_structured_blocks.py`

**Interfaces:**

- `ContentLinkBlock`: `label`, optional `internal_page`, optional `external_url`, optional `fragment`; exactly zero or one destination. A separate `fragment` is allowed only with `internal_page` and must match the safe anchor pattern `[A-Za-z][A-Za-z0-9_-]*`.
- Private helpers: `validate_content_link(value: StructValue) -> None` and `resolve_content_link(value: StructValue) -> tuple[str | None, Literal["internal", "external", "disabled"]]`.
- `CardBlock`: optional `number`, optional `eyebrow`, required `title`, required `summary`, optional `link`; `CardGridBlock`: optional `eyebrow`, required `heading`, optional `introduction`, `layout` (`two`/`three`/`four`), and ordered `cards`.
- `DocumentRowBlock`: required `number`, `title`, `summary`, `status`, optional `link`; `DocumentTableBlock`: required `heading`, optional `caption`, safe required `anchor_id`, ordered `rows`.
- `ProcessStepBlock`: required `number`, `title`, `summary`, ordered string `checklist`, and ordered `resource_links`; `ProcessStepsBlock`: required `heading`, optional `introduction`, ordered `steps`.
- `MetadataPairBlock`: `label` and `value`; `SecurityControlBlock`: `title` and `summary`; `CaseStudyBlock`: `case_label`, `company`, `product`, `certification_status`, `summary`, ordered `metadata`, `equipment_image`, optional `equipment_caption`, `challenge_heading`, `challenge`, `solution_heading`, `solution`, ordered `security_controls`, `outcome_image`, and optional `outcome_caption`.
- Public link representation:

  ```json
  {
    "label": "認識標準",
    "kind": "internal",
    "href": "/about/#background",
    "new_tab": false
  }
  ```

  A placeholder becomes `{"label": "下載", "kind": "disabled", "href": null, "new_tab": false}`.

- Image values use the existing `get_image_api_representation()` helper and include a rendition with URL, dimensions, and alt text.

- [ ] Add failing block validation and API representation tests in `test_semi_blocks.py`. Cover mutually exclusive link destinations, HTTP(S)/`mailto:`/`tel:` schemes, rejected `javascript:` URLs, safe fragments, fragment-without-page rejection, disabled links, anchor IDs, list minimums, and both case-study images. Core examples:

  ```python
  def test_content_link_rejects_two_destinations(self):
      block = ContentLinkBlock()
      value = block.to_python(
          {
              "label": "錯誤連結",
              "internal_page": self.page.pk,
              "external_url": "https://example.com",
              "fragment": "",
          }
      )
      with self.assertRaises(StructBlockValidationError):
          block.clean(value)

  def test_content_link_api_marks_placeholder_disabled(self):
      value = ContentLinkBlock().to_python(
          {"label": "下載 FAQ", "internal_page": None, "external_url": ""}
      )
      self.assertEqual(
          ContentLinkBlock().get_api_representation(value),
          {
              "label": "下載 FAQ",
              "kind": "disabled",
              "href": None,
              "new_tab": False,
          },
      )
  ```

- [ ] Run the focused test and confirm RED because the block classes do not exist:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.base.tests.test_semi_blocks
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  ```

- [ ] Add `beautifulsoup4>=4.12,<5` to `requirements/base.txt`. Install the updated development requirements only if the current environment cannot import `bs4`:

  ```powershell
  .\.venv\Scripts\python.exe -c "import bs4"
  .\.venv\Scripts\python.exe -m pip install -r requirements/development.txt
  ```

- [ ] Implement small nested `StructBlock`/`ListBlock` types in `blocks.py`. Put URL/fragment validation in `ContentLinkBlock.clean()`, and centralize link serialization in its `get_api_representation()` rather than duplicating link rules in parent blocks.

  Start from this concrete shape and add the declared child fields to the four parent blocks:

  ```python
  class ContentLinkBlock(StructBlock):
      label = CharBlock(required=True)
      internal_page = PageChooserBlock(required=False)
      external_url = CharBlock(required=False)
      fragment = CharBlock(required=False)

      def clean(self, value):
          result = super().clean(value)
          validate_content_link(result)
          return result

      def get_api_representation(self, value, context=None):
          href, kind = resolve_content_link(value)
          return {
              "label": value["label"],
              "kind": kind,
              "href": href,
              "new_tab": kind == "external"
              and urlsplit(href).scheme in {"http", "https"},
          }


  class CardGridBlock(StructBlock):
      eyebrow = CharBlock(required=False)
      heading = CharBlock(required=True)
      introduction = TextBlock(required=False)
      layout = ChoiceBlock(
          choices=[("two", "Two columns"), ("three", "Three columns"),
                   ("four", "Four columns")],
          default="three",
      )
      cards = ListBlock(CardBlock(), min_num=1)


  class DocumentTableBlock(StructBlock):
      heading = CharBlock(required=True)
      caption = CharBlock(required=False)
      anchor_id = CharBlock(required=True)
      rows = ListBlock(DocumentRowBlock(), min_num=1)


  class ProcessStepsBlock(StructBlock):
      heading = CharBlock(required=True)
      introduction = TextBlock(required=False)
      steps = ListBlock(ProcessStepBlock(), min_num=1)


  class CaseStudyBlock(StructBlock):
      case_label = CharBlock(required=True)
      company = CharBlock(required=True)
      product = CharBlock(required=True)
      certification_status = CharBlock(required=True)
      summary = TextBlock(required=True)
      metadata = ListBlock(MetadataPairBlock(), min_num=1)
      equipment_image = ImageChooserBlock(required=True)
      equipment_caption = CharBlock(required=False)
      challenge_heading = CharBlock(required=True)
      challenge = RichTextBlock(required=True)
      solution_heading = CharBlock(required=True)
      solution = RichTextBlock(required=True)
      security_controls = ListBlock(SecurityControlBlock(), min_num=1)
      outcome_image = ImageChooserBlock(required=True)
      outcome_caption = CharBlock(required=False)

      def get_api_representation(self, value, context=None):
          data = super().get_api_representation(value, context)
          data["equipment_image"] = get_image_api_representation(
              value["equipment_image"], "max-1200x800"
          )
          data["outcome_image"] = get_image_api_representation(
              value["outcome_image"], "max-1200x800"
          )
          return data
  ```

- [ ] Add the four blocks to `BaseStreamBlock` without renaming or changing any existing block. Assign semantic fallback templates and Wagtail editor icons/descriptions.

- [ ] Implement semantic Wagtail fallback templates. Use `<section>`, `<article>`, `<table>`, `<ol>`, headings, lists, figures, and the shared `_content_link.html`. Never render an `<a>` when `kind == "disabled"`.

- [ ] Generate the explicit migration and inspect it to ensure it only records the altered StreamField definitions:

  ```powershell
  .\.venv\Scripts\python.exe manage.py makemigrations base blog breads locations people recipes --name add_semi_structured_blocks
  .\.venv\Scripts\python.exe manage.py makemigrations --check
  ```

- [ ] Run the focused test and existing Home render test; confirm GREEN:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.base.tests.test_semi_blocks bakerydemo.base.tests.test_home_page
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  ```

- [ ] Commit only Task 1 files:

  ```powershell
  git add requirements/base.txt bakerydemo/base/blocks.py bakerydemo/templates/blocks bakerydemo/base/tests/test_semi_blocks.py bakerydemo/base/migrations/0028_add_semi_structured_blocks.py bakerydemo/blog/migrations/0009_add_semi_structured_blocks.py bakerydemo/breads/migrations/0011_add_semi_structured_blocks.py bakerydemo/locations/migrations/0009_add_semi_structured_blocks.py bakerydemo/people/migrations/0004_add_semi_structured_blocks.py bakerydemo/recipes/migrations/0005_add_semi_structured_blocks.py
  git commit -m "feat: add structured SEMI content blocks"
  ```

---

### Task 2: Add public site settings and explicit navigation API

**Files:**

- Modify: `bakerydemo/base/models.py`
- Create: `bakerydemo/base/public_api.py`
- Modify: `bakerydemo/urls.py`
- Create: `bakerydemo/base/tests/test_site_settings_api.py`
- Create: `bakerydemo/base/migrations/0029_add_semi_site_settings.py`

**Interfaces:**

- Extend `SiteSettings` with `CharField(max_length=255)` fields `site_name`, `site_tagline`, and `contact_heading`; `CharField(max_length=100)` `contact_name`; `CharField(max_length=255)` `contact_context`; `CharField(max_length=64)` `contact_phone`; `EmailField` `contact_email`; `TextField` `organisation_text`; optional `footer_logo`; and ordered `primary_navigation` page references. Every new text/email field uses `blank=True, default=""` so the migration is safe for the existing settings row.
- `GET /api/site-settings/` identifies `Site.find_for_request(request)` and returns only:

  ```json
  {
    "site_name": "SEMI E187 半導體設備資安標準",
    "site_tagline": "推動半導體設備資安",
    "contact": {
      "heading": "半導體智慧製造資安合規諮詢",
      "name": "李先生",
      "context": "認驗證制度與流程",
      "phone": "02-23116228 #202",
      "phone_href": "tel:+886223116228,202",
      "email": "MaxYCLee@itri.org.tw"
    },
    "organisation_text": "© SEMI E187 Semiconductor Equipment Cybersecurity Certification Scheme. 內容經由 ACW 官方指南編修。",
    "footer_logo": null,
    "navigation": [
      {"id": 60, "title": "首頁", "path": "/"},
      {"id": 91, "title": "認識標準", "path": "/about/"}
    ]
  }
  ```

- Only live pages in `primary_navigation` are serialized. Order is the StreamField order. The endpoint never falls back to `show_in_menus`.
- Private serializers: `phone_to_href(value: str) -> str`, `serialize_navigation_page(page: Page, site_root_id: int) -> dict[str, object]`, and `serialize_public_settings(settings: SiteSettings, navigation: list[dict[str, object]]) -> dict[str, object]`. `phone_to_href("02-23116228 #202")` returns `tel:+886223116228,202` and rejects rather than guessing when the value contains no digits. The root-page navigation label is explicitly `首頁`; child labels use their editor-managed page titles.

- [ ] Add failing endpoint tests. Build a Site, settings, Home, two configured pages, and one unrelated `show_in_menus=True` page. Assert configured order, omission of the unrelated page, media representation for a logo, and absence of `title_suffix`, model IDs, and administrative fields.

  ```python
  response = self.client.get("/api/site-settings/", HTTP_HOST="localhost")
  self.assertEqual(response.status_code, 200)
  self.assertEqual(
      response.json()["navigation"],
      [
          {"id": self.home.pk, "title": "首頁", "path": "/"},
          {"id": self.about.pk, "title": "認識標準", "path": "/about/"},
      ],
  )
  self.assertNotIn(self.unrelated.pk, {
      item["id"] for item in response.json()["navigation"]
  })
  self.assertNotIn("title_suffix", response.json())
  ```

- [ ] Add failing tests for POST returning 405, no matching site returning 404, no existing settings row returning field defaults without creating a row, and an unpublished page reference being omitted rather than exposed.

- [ ] Run and confirm RED:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.base.tests.test_site_settings_api
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  ```

- [ ] Add the settings fields and panels. Use a `StreamField` containing one `PageChooserBlock` child named `page` for ordered navigation. Retain the existing `title_suffix` field and panel.

  ```python
  footer_logo = models.ForeignKey(
      "wagtailimages.Image",
      null=True,
      blank=True,
      on_delete=models.SET_NULL,
      related_name="+",
  )
  primary_navigation = StreamField(
      [("page", PageChooserBlock())],
      blank=True,
      use_json_field=True,
  )
  ```

- [ ] Implement `public_site_settings(request)` in `public_api.py`. Serialize a footer logo with `get_image_api_representation(settings.footer_logo, "max-320x96")`. Convert page URLs to Nuxt path-only routes, keeping `/` for Home.

  ```python
  @require_GET
  def public_site_settings(request):
      site = Site.find_for_request(request)
      if site is None:
          raise Http404
      settings = SiteSettings.objects.filter(site=site).first()
      if settings is None:
          settings = SiteSettings(site=site)
      navigation = [
          serialize_navigation_page(child.value.specific, site.root_page_id)
          for child in settings.primary_navigation
          if child.block_type == "page" and child.value.live
      ]
      return JsonResponse(serialize_public_settings(settings, navigation))
  ```

- [ ] Register `path("api/site-settings/", public_site_settings, name="public_site_settings")` before the final Wagtail catch-all in `bakerydemo/urls.py`.

- [ ] Generate and inspect the settings migration:

  ```powershell
  .\.venv\Scripts\python.exe manage.py makemigrations base --name add_semi_site_settings
  .\.venv\Scripts\python.exe manage.py makemigrations --check
  ```

- [ ] Run focused tests and Django checks; confirm GREEN:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.base.tests.test_site_settings_api bakerydemo.base.tests.test_semi_blocks
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  .\.venv\Scripts\python.exe manage.py check
  ```

- [ ] Commit only Task 2 files:

  ```powershell
  git add bakerydemo/base/models.py bakerydemo/base/public_api.py bakerydemo/urls.py bakerydemo/base/tests/test_site_settings_api.py bakerydemo/base/migrations/0029_add_semi_site_settings.py
  git commit -m "feat: expose public SEMI site settings"
  ```

---

### Task 3: Build a strict, pure HTML-to-import-plan parser

**Files:**

- Create: `bakerydemo/base/semi_e187/__init__.py`
- Create: `bakerydemo/base/semi_e187/schema.py`
- Create: `bakerydemo/base/semi_e187/links.py`
- Create: `bakerydemo/base/semi_e187/html.py`
- Create: `bakerydemo/base/semi_e187/parser.py`
- Create: `bakerydemo/base/tests/test_semi_import_parser.py`
- Create: `bakerydemo/base/tests/fixtures/semi_e187/index.html`
- Create: `bakerydemo/base/tests/fixtures/semi_e187/about.html`
- Create: `bakerydemo/base/tests/fixtures/semi_e187/resources.html`
- Create: `bakerydemo/base/tests/fixtures/semi_e187/certification.html`
- Create: `bakerydemo/base/tests/fixtures/semi_e187/ecosystem.html`

**Interfaces:**

- Immutable schema types: `SourceAsset`, `SourceLink`, `BlockImport`, `HomeImport`, `PageImport`, `SiteSettingsImport`, `ImportPlan`, `ImportWarning`, `ImportCounts`, and private `LoadedSources`.
- `ImportPlan.home` contains the Home update, while `ImportPlan.pages` contains only the four ordered child pages. `ImportPlan.page(slug: str) -> PageImport` raises `KeyError` for unknown slugs.
- Link helpers: `normalize_source_link(label: str, href: str, current_slug: str) -> SourceLink` and `validate_fragment(value: str) -> str`; both raise `SourceValidationError` for unsafe input.
- HTML helpers: `parse_html(source_html: str) -> BeautifulSoup`, `require_one(root: Tag, selector: str, source_name: str) -> Tag`, `require_text(root: Tag, selector: str, source_name: str) -> str`, `require_count(items: Sequence[Tag], expected: int, source_name: str, section: str) -> None`, and `sanitize_rich_text(nodes: Iterable[Tag | NavigableString]) -> str`.
- Parser helpers: `load_and_validate_sources(html_dir: Path, asset_dir: Path) -> LoadedSources`, `parse_home(html: str) -> HomeImport`, `parse_about(html: str) -> PageImport`, `parse_resources(html: str) -> PageImport`, `parse_certification(html: str) -> PageImport`, `parse_ecosystem(html: str, assets: Mapping[str, SourceAsset]) -> PageImport`, and `assemble_import_plan(home: HomeImport, pages: Sequence[PageImport], sources: LoadedSources) -> ImportPlan`.
- Public entry point:

  ```python
  def parse_source_site(html_dir: Path, asset_dir: Path) -> ImportPlan:
      """Validate and parse all supplied files without database/storage writes."""
  ```

- Dedicated page parsers use stable semantic boundaries:
  - Home: source title/hero, latest-news cards, `#site-sections` topic cards, and `#contact`; clear legacy promo/featured values during publication.
  - About: `#about`, background narrative, and exactly four standard-dimension cards.
  - Resources: `#resources` resource cards and the semantic table under `#documents-table`.
  - Certification: `#certification` overview, compliance-body cards, role-guidance cards, and exactly five stages under `#vendor-process`.
  - Ecosystem: `#ecosystem` overview cards and exactly two cases under `#case-studies`.
- The rich-text sanitizer allows only `p`, `br`, `strong`, `b`, `em`, `i`, `ul`, `ol`, `li`, and safe `a[href]`; it strips scripts, styles, event handlers, `class`, and `style`.
- Link normalization rules:
  - `index.html` -> `/`
  - `about.html#background` -> `/about/#background`
  - `#documents-table` -> current route plus the fragment
  - HTTP(S), `mailto:`, and `tel:` remain external
  - `#` -> no destination plus a placeholder warning
  - `VerB_en.html` -> omitted language-switch warning, never content

- [ ] Create minimal representative fixture pages containing only the semantic structures the parser supports. Include one source `<script>`, inline style/class/event handler, one external government link, the known placeholder counts (1/13/1), two case studies, and the three required image filenames. Do not copy source CDN scripts or full visual boilerplate into fixtures.

- [ ] In parser-test setup, copy those text fixtures into a temporary HTML directory and create three tiny valid JPEGs named `GPM01.jpg`, `contret01.jpg`, and `GPM+contret.jpg` with Pillow in a temporary asset directory. Tests must never depend on the user's Downloads folder.

- [ ] Add failing tests for the exact page order and block sequence. Representative assertions:

  ```python
  plan = parse_source_site(self.html_dir, self.asset_dir)
  self.assertEqual([page.slug for page in plan.pages], [
      "about", "resources", "certification", "ecosystem"
  ])
  self.assertEqual(
      [block.type for block in plan.page("ecosystem").body],
      ["card_grid", "case_study", "case_study"],
  )
  self.assertEqual(plan.counts.disabled_links, 15)
  ```

- [ ] Add failing security tests asserting sanitized rich text contains semantic tags but no `<script>`, `<style>`, `onclick`, `class=`, `style=`, or `javascript:`.

- [ ] Add failing input tests for each missing HTML file, a missing required JPEG, duplicate case section, malformed document table, fewer/more than five process stages, and fewer/more than two case studies. Assert errors include the filename and failed section name/path.

- [ ] Run and confirm RED because the parser package does not exist:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.base.tests.test_semi_import_parser
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  ```

- [ ] Implement `schema.py` with frozen dataclasses and tuple collections so the parsed plan cannot be mutated accidentally during validation.

  ```python
  @dataclass(frozen=True)
  class SourceLink:
      label: str
      target_slug: str | None
      external_url: str | None
      fragment: str


  @dataclass(frozen=True)
  class BlockImport:
      type: str
      value: Mapping[str, object] | str


  @dataclass(frozen=True)
  class HomeImport:
      title: str
      seo_title: str
      search_description: str
      hero_text: str
      hero_cta: str
      hero_cta_link: SourceLink
      body: tuple[BlockImport, ...]


  @dataclass(frozen=True)
  class PageImport:
      slug: str
      title: str
      seo_title: str
      search_description: str
      introduction: str
      body: tuple[BlockImport, ...]


  @dataclass(frozen=True)
  class ImportPlan:
      home: HomeImport
      pages: tuple[PageImport, ...]
      settings: SiteSettingsImport
      assets: tuple[SourceAsset, ...]
      warnings: tuple[ImportWarning, ...]
      counts: ImportCounts

      def page(self, slug: str) -> PageImport:
          for page in self.pages:
              if page.slug == slug:
                  return page
          raise KeyError(slug)
  ```

- [ ] Implement `links.py` with `urllib.parse`, a fixed filename-to-slug map, fragment validation, and an allowlist for external schemes. Keep link normalization independent of Beautiful Soup and database models.

  ```python
  PAGE_SLUGS = {
      "index.html": "",
      "about.html": "about",
      "resources.html": "resources",
      "certification.html": "certification",
      "ecosystem.html": "ecosystem",
  }
  EXTERNAL_SCHEMES = {"http", "https", "mailto", "tel"}


  def normalize_source_link(label: str, href: str, current_slug: str) -> SourceLink:
      if href == "#":
          return SourceLink(label, None, None, "")
      parsed = urlsplit(href)
      if parsed.scheme:
          if parsed.scheme.lower() not in EXTERNAL_SCHEMES:
              raise SourceValidationError(f"不允許的連結協定：{parsed.scheme}")
          return SourceLink(label, None, href, "")
      if not parsed.path:
          target_slug = current_slug
      else:
          filename = Path(parsed.path).name
          if filename not in PAGE_SLUGS:
              raise SourceValidationError(f"未知的站內頁面：{filename}")
          target_slug = PAGE_SLUGS[filename]
      return SourceLink(label, target_slug, None, validate_fragment(parsed.fragment))
  ```

- [ ] Implement `html.py` with the strict selector/count helpers and allowlisted sanitizer. This file owns DOM safety; page-specific parsers may call its helpers but may not inspect scripts, styles, event handlers, or source CSS classes.

  ```python
  ALLOWED_TAGS = {"p", "br", "strong", "b", "em", "i", "ul", "ol", "li", "a"}
  ALLOWED_ATTRIBUTES = {"a": {"href"}}


  def require_one(root: Tag, selector: str, source_name: str) -> Tag:
      matches = root.select(selector)
      if len(matches) != 1:
          raise SourceValidationError(
              f"{source_name}：{selector} 預期 1 個，實際 {len(matches)} 個"
          )
      return matches[0]
  ```

- [ ] Implement `parser.py` with `BeautifulSoup(source_html, "html.parser")`. Require named semantic sections with helpers such as `require_one()`, `require_text()`, and `require_count()`. Extract data with page-specific functions; never use `eval`, execute scripts, fetch external URLs, or ingest source styling.

  ```python
  REQUIRED_HTML = (
      "index.html", "about.html", "resources.html",
      "certification.html", "ecosystem.html",
  )
  REQUIRED_ASSETS = ("GPM01.jpg", "contret01.jpg", "GPM+contret.jpg")


  def parse_source_site(html_dir: Path, asset_dir: Path) -> ImportPlan:
      sources = load_and_validate_sources(html_dir, asset_dir)
      home = parse_home(sources.html["index.html"])
      pages = (
          parse_about(sources.html["about.html"]),
          parse_resources(sources.html["resources.html"]),
          parse_certification(sources.html["certification.html"]),
          parse_ecosystem(sources.html["ecosystem.html"], sources.assets),
      )
      return assemble_import_plan(home, pages, sources)
  ```

- [ ] Render sanitized fragments by reconstructing only allowlisted tags/attributes. Normalize whitespace and deterministic ordering so repeated parses produce equal `ImportPlan` values.

  Recursively freeze every block mapping with `MappingProxyType` and every list as a tuple before constructing `BlockImport`; `publisher.py` is the only layer that thaws these values into Wagtail StreamField dictionaries.

- [ ] Run parser tests and Ruff; confirm GREEN:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.base.tests.test_semi_import_parser
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  .\.venv\Scripts\ruff.exe check bakerydemo/base/semi_e187 bakerydemo/base/tests/test_semi_import_parser.py
  ```

- [ ] Commit only Task 3 files:

  ```powershell
  git add bakerydemo/base/semi_e187 bakerydemo/base/tests/test_semi_import_parser.py bakerydemo/base/tests/fixtures/semi_e187
  git commit -m "feat: parse SEMI source content safely"
  ```

---

### Task 4: Add a write-free management-command dry run

**Files:**

- Create: `bakerydemo/base/semi_e187/targets.py`
- Create: `bakerydemo/base/management/commands/import_semi_e187.py`
- Create: `bakerydemo/base/tests/test_import_semi_e187.py`

**Interfaces:**

- Command arguments: required `--html-dir`, required `--asset-dir`, optional integer `--home-id` defaulting to 60, and a required mutually exclusive group containing `--dry-run` or `--publish`.
- `PageSnapshot(id, path, depth, live, show_in_menus, slug, title, parent_id)`, `TargetAction(action: Literal["create", "update"], slug: str, page_id: int | None)`, and `TargetSummary(home: HomePage, pages: tuple[TargetAction, ...], untouched: tuple[PageSnapshot, ...])` are immutable dataclasses.
- `validate_targets(plan: ImportPlan, home_id: int) -> TargetSummary` performs read-only checks. It fails when Home is missing/wrong type, when a target slug is occupied by a non-`StandardPage`, or when an existing target is not a direct child of Home.
- `TargetValidationError` is the single target-validation exception translated to Django `CommandError` by the command.
- `format_dry_run(plan: ImportPlan, targets: TargetSummary) -> str` creates stable plain-text output and performs no queries or writes.
- Dry-run output has stable sections: inputs, Home action, page actions, block counts, image actions, rewritten links, disabled placeholders, warnings, and untouched pages. It ends with `DRY RUN：未寫入資料庫或媒體檔案。`

- [ ] Add failing CLI tests for omitted mode, both modes, missing directories, invalid Home ID/type, conflicting page type, and a same-slug `StandardPage` outside Home.

- [ ] Add a write-safety test that snapshots page/settings/image/collection counts and the media directory, calls `--dry-run`, and asserts all snapshots are identical afterward. Assert `TEST`, `AXCC`, and `CCC` are reported as untouched when present.

- [ ] Add a successful dry-run output test:

  ```python
  output = StringIO()
  call_command(
      "import_semi_e187",
      html_dir=self.html_dir,
      asset_dir=self.asset_dir,
      dry_run=True,
      stdout=output,
  )
  self.assertIn("Home ID 60：更新", output.getvalue())
  self.assertIn("about：建立", output.getvalue())
  self.assertIn("停用連結：15", output.getvalue())
  self.assertIn("未寫入資料庫或媒體檔案", output.getvalue())
  ```

- [ ] Run and confirm RED:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.base.tests.test_import_semi_e187
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  ```

- [ ] Implement the mutually exclusive parser group in `add_arguments()`. Parse and validate sources first, then validate database targets, then print. Do not import the publish service on the dry-run path until after validation succeeds.

  ```python
  class Command(BaseCommand):
      def add_arguments(self, parser):
          parser.add_argument("--html-dir", type=Path, required=True)
          parser.add_argument("--asset-dir", type=Path, required=True)
          parser.add_argument("--home-id", type=int, default=60)
          mode = parser.add_mutually_exclusive_group(required=True)
          mode.add_argument("--dry-run", action="store_true")
          mode.add_argument("--publish", action="store_true")

      def handle(self, *args, **options):
          try:
              plan = parse_source_site(options["html_dir"], options["asset_dir"])
              targets = validate_targets(plan, options["home_id"])
          except (SourceValidationError, TargetValidationError) as error:
              raise CommandError(str(error)) from error
          if options["dry_run"]:
              self.stdout.write(format_dry_run(plan, targets))
              return
          raise CommandError("發佈功能尚未實作")
  ```

- [ ] Keep presentation of the dry-run report in small deterministic formatting functions so tests do not depend on terminal width or colors.

- [ ] Make `--publish` fail with an explicit `CommandError("發佈功能尚未實作")` in this task; tests must prove it cannot silently perform a partial write before Task 5.

- [ ] Run the focused command/parser tests and confirm GREEN:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.base.tests.test_import_semi_e187 bakerydemo.base.tests.test_semi_import_parser
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  ```

- [ ] Commit only Task 4 files:

  ```powershell
  git add bakerydemo/base/semi_e187/targets.py bakerydemo/base/management/commands/import_semi_e187.py bakerydemo/base/tests/test_import_semi_e187.py
  git commit -m "feat: add SEMI import dry run"
  ```

---

### Task 5: Publish the import idempotently and safely

**Files:**

- Create: `bakerydemo/base/semi_e187/publisher.py`
- Modify: `bakerydemo/base/management/commands/import_semi_e187.py`
- Modify: `bakerydemo/base/tests/test_import_semi_e187.py`

**Interfaces:**

- `PublishResult(created_pages: int, updated_pages: int, created_images: int, updated_images: int, reused_images: int, page_ids: Mapping[str, int], image_ids: Mapping[str, int], warnings: tuple[str, ...])` is immutable.
- `publish_import(plan: ImportPlan, targets: TargetSummary) -> PublishResult` owns all writes.
- `format_publish_result(result: PublishResult) -> str` returns deterministic plain text for the command.
- `StorageWriteTracker.created_names: list[str]` records only new storage names from this invocation and `remove_created_files() -> None` deletes only those names on transaction failure.
- Private write phases have exact signatures: `get_or_create_import_collection() -> Collection` (using the Wagtail collection tree API), `upsert_import_images(plan: ImportPlan, collection: Collection, tracker: StorageWriteTracker) -> dict[str, Image]`, `upsert_page_shells(plan: ImportPlan, targets: TargetSummary) -> dict[str, Page]` (the Home key is the empty slug), `apply_page_content(plan: ImportPlan, pages: Mapping[str, Page], images: Mapping[str, Image]) -> None`, `apply_site_settings(plan: ImportPlan, pages: Mapping[str, Page], images: Mapping[str, Image]) -> None`, `refresh_import_indexes(pages: Iterable[Page]) -> None`, and `build_publish_result(plan: ImportPlan, targets: TargetSummary, pages: Mapping[str, Page], images: Mapping[str, Image]) -> PublishResult`.
- Dedicated image collection: `SEMI E187`.
- Deterministic imported image titles: `SEMI E187 — GPM01`, `SEMI E187 — contret01`, `SEMI E187 — GPM+contret`, and optional `SEMI E187 — ADI logo`.
- Image equality uses SHA-256 of source bytes and stored original bytes. Changed bytes update the same Wagtail image record with a content-hash filename and delete that image's renditions; unchanged bytes do not create a revision/file.
- The two case studies use `GPM01.jpg` and `contret01.jpg` as equipment images and reuse the single `GPM+contret.jpg` image record as both outcome images.
- Stable child slug order: `about`, `resources`, `certification`, `ecosystem`.
- Imported primary navigation order: Home, About, Resources, Certification, Ecosystem.

- [ ] Extend tests with a successful publish case. Assert Home ID remains 60, four target pages are direct children in source order when newly created, all five pages are live and have revisions, imported child pages have `show_in_menus=True`, obsolete Home promo/featured fields are cleared, `title_suffix` is updated to `SEMI E187`, settings/contact/navigation are populated, and the image collection contains exactly three required images when the optional logo is absent.

  ```python
  call_command(
      "import_semi_e187",
      html_dir=self.html_dir,
      asset_dir=self.asset_dir,
      publish=True,
  )
  home = HomePage.objects.get(pk=60)
  imported = list(
      home.get_children().type(StandardPage).specific().filter(
          slug__in=("about", "resources", "certification", "ecosystem")
      )
  )
  self.assertEqual([page.slug for page in imported], [
      "about", "resources", "certification", "ecosystem"
  ])
  self.assertTrue(all(page.live and page.latest_revision_id for page in imported))
  self.assertEqual(
      Image.objects.filter(collection__name="SEMI E187").count(),
      3,
  )
  ```

- [ ] Add an idempotency test that invokes the publish command twice with unchanged sources. Assert stable page IDs, stable image IDs, identical page/image counts, no duplicate collection, and the second result reports updates/reuse rather than creates.

- [ ] Add changed-image tests: overwrite a temporary copy of `GPM01.jpg`, rerun, assert its Wagtail image ID is unchanged, stored content checksum changes, and old renditions are gone/recreated only on demand.

- [ ] Add rollback tests that inject a failure after media writes and before page publication. Assert database state rolls back, newly created storage files are removed, pre-existing image files remain, and no unrelated page/image is deleted.

- [ ] Add an unrelated-page preservation test that snapshots each unrelated page's `id`, `path`, `depth`, `live`, `show_in_menus`, `slug`, `title`, and parent before import and compares the same tuple after two imports.

- [ ] Run the expanded test and confirm RED because `publish_import()` does not exist:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.base.tests.test_import_semi_e187
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  ```

- [ ] Implement image byte loading before `transaction.atomic()`. Resolve required images case-sensitively and fail on zero/multiple matches. Track only storage names created by this invocation for exception cleanup.

- [ ] Inside one database transaction: get/create the collection and upsert images; then create/update all four child page shells before resolving internal links. In a second pass, assign complete StreamField values and SEO/menu fields, update Home and `SiteSettings`, save revisions, and publish. This two-pass order guarantees that cross-page links always resolve to real Wagtail page IDs.

  ```python
  def publish_import(plan: ImportPlan, targets: TargetSummary) -> PublishResult:
      tracker = StorageWriteTracker()
      try:
          with transaction.atomic():
              collection = get_or_create_import_collection()
              images = upsert_import_images(plan, collection, tracker)
              pages = upsert_page_shells(plan, targets)
              apply_page_content(plan, pages, images)
              apply_site_settings(plan, pages, images)
              revisions = [page.save_revision() for page in pages.values()]
              for revision in revisions:
                  revision.publish()
      except Exception:
          tracker.remove_created_files()
          raise
      refresh_import_indexes(pages.values())
      return build_publish_result(plan, targets, pages, images)
  ```

- [ ] Never move an existing target page or any unrelated page. Append only newly created pages in source order. Navigation ordering is independent of tree ordering.

- [ ] Refresh Wagtail references for written settings/pages and update the configured search backend after successful publication. Return a structured result for the command report.

- [ ] Replace the temporary `--publish` error with a call to `publish_import()`. Print created/updated/reused counts and all warnings. A missing optional logo remains a warning and produces `footer_logo=None`.

  ```python
  if options["dry_run"]:
      self.stdout.write(format_dry_run(plan, targets))
      return
  result = publish_import(plan, targets)
  self.stdout.write(format_publish_result(result))
  ```

- [ ] Run importer, block, settings, and existing Home tests; confirm GREEN:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test bakerydemo.base.tests.test_import_semi_e187 bakerydemo.base.tests.test_semi_import_parser bakerydemo.base.tests.test_semi_blocks bakerydemo.base.tests.test_site_settings_api bakerydemo.base.tests.test_home_page
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  .\.venv\Scripts\python.exe manage.py check
  ```

- [ ] Commit only Task 5 files:

  ```powershell
  git add bakerydemo/base/semi_e187/publisher.py bakerydemo/base/management/commands/import_semi_e187.py bakerydemo/base/tests/test_import_semi_e187.py
  git commit -m "feat: publish SEMI content idempotently"
  ```

---

### Task 6: Add Nuxt site-settings proxy and structured API contracts

**Files:**

- Modify: `nuxt-bakery-demo/shared/types/bakery.ts`
- Modify: `nuxt-bakery-demo/server/utils/bakery-pages.ts`
- Create: `nuxt-bakery-demo/server/utils/bakery-settings.ts`
- Create: `nuxt-bakery-demo/server/api/bakery/site-settings.get.ts`
- Modify: `nuxt-bakery-demo/server/api/bakery/navigation.get.ts`
- Modify: `nuxt-bakery-demo/tests/bakery-pages.test.ts`
- Create: `nuxt-bakery-demo/tests/bakery-settings.test.ts`

**Interfaces:**

- Add discriminated TypeScript types for `BakeryContentLink`, `BakeryCardGridBlock`, `BakeryDocumentTableBlock`, `BakeryProcessStepsBlock`, `BakeryCaseStudyBlock`, and `BakerySiteSettings`.
- `BakeryStreamBlock` remains a discriminated union; existing block members remain unchanged.
- `isBakerySiteSettings(input: unknown): input is BakerySiteSettings` is the private guard. `parseBakerySiteSettings(input: unknown): BakerySiteSettings` rejects malformed public settings payloads, while `toBakerySiteSettings(input: unknown): BakerySiteSettings` maps that validation failure to an H3 502 error. `toNavigationItems(settings: BakerySiteSettings): BakeryNavigationItem[]` returns a defensive copy in configured order.
- `GET /api/bakery/site-settings` proxies Wagtail `GET /api/site-settings/` through `fetchBakery()`.
- `GET /api/bakery/navigation` keeps returning `BakeryNavigationItem[]`, but maps `settings.navigation`; it no longer queries pages by `show_in_menus`.
- `toNuxtPagePath(reference: BakeryPageReference | null): string | null` extracts only a safe local pathname from Wagtail `meta.html_url`. `enrichHomePage()` adds `heroCtaPath` to `BakeryHomeViewModel`, so the imported Home CTA never links browsers directly to port 8000.

- [ ] Update `bakery-pages.test.ts` first. Remove expectations for `createNavigationQuery()` and `toNavigationItems()`. Add a regression assertion that generic `show_in_menus` pages cannot enter navigation because the navigation transformer accepts only settings data.

  Also assert Home CTA localization:

  ```typescript
  const home = {
    hero_cta_link: {
      id: 93,
      title: '驗證與合規',
      meta: {
        type: 'base.StandardPage',
        html_url: 'http://127.0.0.1:8000/certification/'
      }
    }
  } as BakeryHomePage
  assert.equal(enrichHomePage(home, []).heroCtaPath, '/certification/')
  ```

- [ ] Add failing tests for settings validation/normalization, ordered navigation, relative logo media URL resolution through `fetchBakery()`, and 404/502 error mapping.

  ```typescript
  function makeSiteSettings(
    overrides: Partial<BakerySiteSettings> = {}
  ): BakerySiteSettings {
    return {
      site_name: 'SEMI E187',
      site_tagline: '推動半導體設備資安',
      contact: {
        heading: '合規諮詢', name: '李先生', context: '認驗證制度與流程',
        phone: '02-23116228 #202', phone_href: 'tel:+886223116228,202',
        email: 'MaxYCLee@itri.org.tw'
      },
      organisation_text: 'SEMI E187',
      footer_logo: null,
      navigation: [],
      ...overrides
    }
  }

  test('navigation uses only the ordered public settings list', () => {
    const settings = makeSiteSettings({
      navigation: [
        { id: 60, title: '首頁', path: '/' },
        { id: 91, title: '認識標準', path: '/about/' }
      ]
    })
    assert.deepEqual(toNavigationItems(settings), settings.navigation)
  })

  test('settings parser rejects malformed navigation paths', () => {
    assert.throws(
      () => parseBakerySiteSettings(makeSiteSettings({
        navigation: [{ id: 86, title: 'TEST', path: 'javascript:alert(1)' }]
      })),
      /navigation/
    )
    assert.throws(
      () => toBakerySiteSettings({ navigation: [] }),
      (error: { statusCode?: number }) => error.statusCode === 502
    )
  })
  ```

- [ ] Run and confirm RED:

  ```powershell
  Set-Location nuxt-bakery-demo
  npm test
  Set-Location ..
  ```

- [ ] Extend `bakery.ts` with exact backend response shapes. Use `kind: 'internal' | 'external' | 'disabled'` for links and `href: string | null`; do not use `any`.

  ```typescript
  export interface BakeryContentLink {
    label: string
    kind: 'internal' | 'external' | 'disabled'
    href: string | null
    new_tab: boolean
  }

  export interface BakerySiteSettings {
    site_name: string
    site_tagline: string
    contact: {
      heading: string
      name: string
      context: string
      phone: string
      phone_href: string
      email: string
    }
    organisation_text: string
    footer_logo: BakeryImage | null
    navigation: BakeryNavigationItem[]
  }

  export interface BakeryHomeViewModel extends BakeryHomePage {
    featuredSections: BakeryFeaturedSection[]
    heroCtaPath: string | null
  }

  export interface BakeryCard {
    number: string
    eyebrow: string
    title: string
    summary: string
    link: BakeryContentLink | null
  }

  export interface BakeryDocumentRow {
    number: string
    title: string
    summary: string
    status: string
    link: BakeryContentLink | null
  }

  export interface BakeryProcessStep {
    number: string
    title: string
    summary: string
    checklist: string[]
    resource_links: BakeryContentLink[]
  }

  export interface BakeryCaseStudyValue {
    case_label: string
    company: string
    product: string
    certification_status: string
    summary: string
    metadata: Array<{ label: string; value: string }>
    equipment_image: BakeryImage
    equipment_caption: string
    challenge_heading: string
    challenge: string
    solution_heading: string
    solution: string
    security_controls: Array<{ title: string; summary: string }>
    outcome_image: BakeryImage
    outcome_caption: string
  }

  type StreamBlock<TType extends string, TValue> = {
    id: string
    type: TType
    value: TValue
  }

  export type BakeryCardGridBlock = StreamBlock<'card_grid', {
    eyebrow: string
    heading: string
    introduction: string
    layout: 'two' | 'three' | 'four'
    cards: BakeryCard[]
  }>
  export type BakeryDocumentTableBlock = StreamBlock<'document_table', {
    heading: string
    caption: string
    anchor_id: string
    rows: BakeryDocumentRow[]
  }>
  export type BakeryProcessStepsBlock = StreamBlock<'process_steps', {
    heading: string
    introduction: string
    steps: BakeryProcessStep[]
  }>
  export type BakeryCaseStudyBlock = StreamBlock<
    'case_study', BakeryCaseStudyValue
  >
  ```

- [ ] Implement `bakery-settings.ts` with a pure `toNavigationItems(settings)` function and runtime shape guards for the public settings payload.

  ```typescript
  export function toNavigationItems(
    settings: BakerySiteSettings
  ): BakeryNavigationItem[] {
    return settings.navigation.map(item => ({ ...item }))
  }

  export function parseBakerySiteSettings(input: unknown): BakerySiteSettings {
    if (!isBakerySiteSettings(input)) {
      throw new Error('Bakery site settings 格式不正確。')
    }
    return input
  }

  export function toBakerySiteSettings(input: unknown): BakerySiteSettings {
    try {
      return parseBakerySiteSettings(input)
    } catch {
      throw createError({
        statusCode: 502,
        statusMessage: 'Bakery site settings 回應格式不正確。'
      })
    }
  }
  ```

- [ ] Update `enrichHomePage()` in `bakery-pages.ts` to return `heroCtaPath: toNuxtPagePath(home.hero_cta_link)`. `toNuxtPagePath()` accepts only HTTP(S) page URLs and returns their pathname plus search/fragment; malformed or non-HTTP references return `null`.

  ```typescript
  export function toNuxtPagePath(
    reference: BakeryPageReference | null
  ): string | null {
    if (!reference?.meta.html_url) return null
    try {
      const url = new URL(reference.meta.html_url)
      return ['http:', 'https:'].includes(url.protocol)
        ? `${url.pathname}${url.search}${url.hash}`
        : null
    } catch {
      return null
    }
  }
  ```

- [ ] Add the site-settings Nitro route and change navigation to fetch `/api/site-settings/` then return the explicit list. Preserve the current same-origin browser architecture and existing `fetchBakery()` error conventions.

  ```typescript
  // server/api/bakery/site-settings.get.ts
  export default defineEventHandler(async (event): Promise<BakerySiteSettings> =>
    toBakerySiteSettings(
      await fetchBakery<unknown>(event, '/api/site-settings/')
    )
  )

  // server/api/bakery/navigation.get.ts
  export default defineEventHandler(async (event): Promise<BakeryNavigationItem[]> => {
    const settings = toBakerySiteSettings(
      await fetchBakery<unknown>(event, '/api/site-settings/')
    )
    return toNavigationItems(settings)
  })
  ```

- [ ] Run tests, typecheck, and confirm GREEN:

  ```powershell
  Set-Location nuxt-bakery-demo
  npm test
  npm run typecheck
  Set-Location ..
  ```

- [ ] Commit only Task 6 files:

  ```powershell
  git add nuxt-bakery-demo/shared/types/bakery.ts nuxt-bakery-demo/server/utils/bakery-pages.ts nuxt-bakery-demo/server/utils/bakery-settings.ts nuxt-bakery-demo/server/api/bakery/site-settings.get.ts nuxt-bakery-demo/server/api/bakery/navigation.get.ts nuxt-bakery-demo/tests/bakery-pages.test.ts nuxt-bakery-demo/tests/bakery-settings.test.ts
  git commit -m "feat: proxy SEMI site settings to Nuxt"
  ```

---

### Task 7: Render every structured block with safe link behavior

**Files:**

- Modify: `nuxt-bakery-demo/app/utils/stream-field.ts`
- Create: `nuxt-bakery-demo/app/components/blocks/ContentLink.vue`
- Create: `nuxt-bakery-demo/app/components/blocks/CardGrid.vue`
- Create: `nuxt-bakery-demo/app/components/blocks/DocumentTable.vue`
- Create: `nuxt-bakery-demo/app/components/blocks/ProcessSteps.vue`
- Create: `nuxt-bakery-demo/app/components/blocks/CaseStudy.vue`
- Modify: `nuxt-bakery-demo/app/components/StreamField.vue`
- Modify: `nuxt-bakery-demo/tests/stream-field.test.ts`

**Interfaces:**

- Pure helper:

  ```typescript
  export type LinkPresentation =
    | { kind: 'internal'; to: string; label: string }
    | { kind: 'external'; href: string; label: string; newTab: boolean }
    | { kind: 'disabled'; label: string; status: '即將提供' }

  export function getLinkPresentation(link: BakeryContentLink): LinkPresentation
  ```

- `ContentLink.vue` renders `NuxtLink`, external `<a rel="noopener noreferrer">`, or non-interactive text plus `即將提供`, according to that pure result.
- `StreamField.vue` delegates `card_grid`, `document_table`, `process_steps`, and `case_study` to one focused component each and still skips unknown block types.

- [ ] Add failing helper tests for internal fragments, external links/new tabs, disabled placeholders, unsafe/malformed API hrefs, image source fallback, and stable ordered content. Include:

  ```typescript
  assert.deepEqual(
    getLinkPresentation({
      label: '下載 FAQ', kind: 'disabled', href: null, new_tab: false
    }),
    { kind: 'disabled', label: '下載 FAQ', status: '即將提供' }
  )
  ```

- [ ] Run and confirm RED:

  ```powershell
  Set-Location nuxt-bakery-demo
  npm test
  Set-Location ..
  ```

- [ ] Implement helpers with scheme checks even though Wagtail already validates links. Treat an unexpected/unsafe href as disabled so a malformed future API payload cannot create a dangerous anchor.

  ```typescript
  export function getLinkPresentation(
    link: BakeryContentLink
  ): LinkPresentation {
    if (link.kind === 'internal' && link.href?.startsWith('/')) {
      return { kind: 'internal', to: link.href, label: link.label }
    }
    if (link.kind === 'external' && link.href) {
      try {
        const scheme = new URL(link.href).protocol
        if (['http:', 'https:', 'mailto:', 'tel:'].includes(scheme)) {
          return {
            kind: 'external', href: link.href, label: link.label,
            newTab: link.new_tab
          }
        }
      } catch {
        // Fall through to the disabled presentation.
      }
    }
    return { kind: 'disabled', label: link.label, status: '即將提供' }
  }
  ```

- [ ] Build `ContentLink.vue`, then the four semantic renderers. Requirements: table headers via `<th scope="col">`, process steps via `<ol>`, case metadata via `<dl>`, intrinsic image dimensions, useful alt fallback, and lazy loading below the fold.

  ```vue
  <script setup lang="ts">
  import type { BakeryContentLink } from '#shared/types/bakery'
  import { getLinkPresentation } from '~/utils/stream-field'

  const props = defineProps<{ link: BakeryContentLink }>()
  const presentation = computed(() => getLinkPresentation(props.link))
  </script>

  <template>
    <NuxtLink v-if="presentation.kind === 'internal'" :to="presentation.to">
      {{ presentation.label }}
    </NuxtLink>
    <a
      v-else-if="presentation.kind === 'external'"
      :href="presentation.href"
      :target="presentation.newTab ? '_blank' : undefined"
      rel="noopener noreferrer"
    >
      {{ presentation.label }}
    </a>
    <span v-else class="content-link-disabled">
      {{ presentation.label }} <small>{{ presentation.status }}</small>
    </span>
  </template>
  ```

- [ ] Refactor `StreamField.vue` to delegate new types. Keep the existing rich-text trust comment and safe embed behavior. Unknown types render nothing and do not throw.

  ```vue
  <CardGrid
    v-if="block.type === 'card_grid'"
    :value="block.value"
  />
  <DocumentTable
    v-else-if="block.type === 'document_table'"
    :value="block.value"
  />
  <ProcessSteps
    v-else-if="block.type === 'process_steps'"
    :value="block.value"
  />
  <CaseStudy
    v-else-if="block.type === 'case_study'"
    :value="block.value"
  />
  ```

- [ ] Run tests and typecheck; confirm GREEN:

  ```powershell
  Set-Location nuxt-bakery-demo
  npm test
  npm run typecheck
  Set-Location ..
  ```

- [ ] Commit only Task 7 files:

  ```powershell
  git add nuxt-bakery-demo/app/utils/stream-field.ts nuxt-bakery-demo/app/components/blocks nuxt-bakery-demo/app/components/StreamField.vue nuxt-bakery-demo/tests/stream-field.test.ts
  git commit -m "feat: render structured SEMI blocks"
  ```

---

### Task 8: Replace the Bakery shell with the responsive SEMI E187 presentation

**Files:**

- Modify: `nuxt-bakery-demo/app/app.vue`
- Modify: `nuxt-bakery-demo/app/pages/index.vue`
- Modify: `nuxt-bakery-demo/app/pages/[slug].vue`
- Modify: `nuxt-bakery-demo/app/assets/css/main.css`
- Create: `nuxt-bakery-demo/app/utils/site-presentation.ts`
- Create: `nuxt-bakery-demo/tests/semi-presentation.test.ts`

**Interfaces:**

- `app.vue` loads `/api/bakery/site-settings`, renders the settings-provided brand, ordered navigation, contact/footer content, and optional logo.
- Mobile navigation button exposes `aria-expanded`, `aria-controls`, supports Escape, closes after route navigation, and never removes desktop keyboard access.
- Home and StandardPage routes retain existing pending/error/retry/404 behavior.
- Local CSS tokens: navy, blue, lime, mint, sky, text, muted text, border, surface, focus ring, and image overlays. Use Traditional Chinese system fonts and no network font dependency.
- Pure helpers: `reduceNavigationOpen(open: boolean, event: 'toggle' | 'escape' | 'route'): boolean`, `isNavigationItemActive(itemPath: string, currentPath: string): boolean`, `getContactLinks(contact: BakerySiteSettings['contact']): { phone: string; email: string }`, and `getFooterLogoPresentation(logo: BakeryImage | null): { src: string; alt: string; width: number; height: number } | null`.

- [ ] Add failing pure contract tests in `semi-presentation.test.ts` for navigation state transitions, Home-vs-child active route matching, contact `tel:`/`mailto:` generation, and optional-logo fallback. Keep these behaviors in exported helpers rather than coupling tests to DOM internals.

  ```typescript
  test('mobile navigation closes on escape and route changes', () => {
    assert.equal(reduceNavigationOpen(false, 'toggle'), true)
    assert.equal(reduceNavigationOpen(true, 'escape'), false)
    assert.equal(reduceNavigationOpen(true, 'route'), false)
  })

  test('missing footer logo has no image presentation', () => {
    assert.equal(getFooterLogoPresentation(null), null)
  })
  ```

- [ ] Run and confirm RED:

  ```powershell
  Set-Location nuxt-bakery-demo
  npm test
  Set-Location ..
  ```

- [ ] Implement `site-presentation.ts` as dependency-free pure functions. Normalize only local pathnames for active-state comparison and return `null` when the optional logo lacks a rendition.

  ```typescript
  export interface FooterLogoPresentation {
    src: string
    alt: string
    width: number
    height: number
  }

  function normalizePath(value: string): string {
    const pathname = value.split(/[?#]/, 1)[0] || '/'
    return pathname === '/' ? '/' : `/${pathname.split('/').filter(Boolean).join('/')}/`
  }

  export function reduceNavigationOpen(
    open: boolean,
    event: 'toggle' | 'escape' | 'route'
  ): boolean {
    return event === 'toggle' ? !open : false
  }

  export function isNavigationItemActive(
    itemPath: string,
    currentPath: string
  ): boolean {
    return normalizePath(itemPath) === normalizePath(currentPath)
  }

  export function getContactLinks(
    contact: BakerySiteSettings['contact']
  ): { phone: string; email: string } {
    return {
      phone: contact.phone_href,
      email: `mailto:${contact.email}`
    }
  }

  export function getFooterLogoPresentation(
    logo: BakeryImage | null
  ): FooterLogoPresentation | null {
    const rendition = logo?.meta.rendition
    return rendition ? {
      src: rendition.full_url || rendition.url,
      alt: rendition.alt || logo.title,
      width: rendition.width,
      height: rendition.height
    } : null
  }
  ```

- [ ] Refactor `app.vue`: remove Bakery branding, remove the hardcoded Home link, render all configured navigation entries, add the accessible mobile disclosure, and render one shared contact/footer section. If settings fail, keep a small text fallback and a status message; never render a broken logo.

  Use the helpers from `site-presentation.ts` for the stateful shell:

  ```typescript
  const route = useRoute()
  const navigationOpen = ref(false)
  const toggleNavigation = () => {
    navigationOpen.value = reduceNavigationOpen(navigationOpen.value, 'toggle')
  }
  const closeNavigation = (event: 'escape' | 'route') => {
    navigationOpen.value = reduceNavigationOpen(navigationOpen.value, event)
  }
  watch(() => route.path, () => closeNavigation('route'))
  const onWindowKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') closeNavigation('escape')
  }
  onMounted(() => window.addEventListener('keydown', onWindowKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onWindowKeydown))
  ```

  ```vue
  <button
    type="button"
    class="nav-toggle"
    aria-controls="primary-navigation"
    :aria-expanded="navigationOpen"
    @click="toggleNavigation"
  >
    選單
  </button>
  <nav id="primary-navigation" :data-open="navigationOpen">
    <NuxtLink
      v-for="item in settings?.navigation || []"
      :key="item.id"
      :to="item.path"
      :aria-current="isNavigationItemActive(item.path, route.path) ? 'page' : undefined"
    >
      {{ item.title }}
    </NuxtLink>
  </nav>
  ```

- [ ] Refactor `index.vue` to use the imported hero fields, `home.heroCtaPath`, and structured Home body. Remove old Bakery-specific promo and featured-section presentation. Keep exactly one page `<h1>` and the existing retry state. Render the CTA only when both `hero_cta` and `heroCtaPath` exist; never hardcode `/about/` or expose the Wagtail `html_url`.

- [ ] Refactor `[slug].vue` headings/eyebrows for SEMI content while retaining safe slug validation, 404 behavior, SEO metadata, and the generic `StreamField` renderer.

- [ ] Rework `main.css` into the approved navy/blue/lime visual system. Cover shell, desktop/mobile nav, hero, each structured block, contact/footer, error/loading states, focus-visible, 390px table/card behavior, `prefers-reduced-motion`, and overflow prevention. Do not add Tailwind, Sass, runtime theme JavaScript, or remote font imports.

- [ ] Run the complete frontend verification; confirm GREEN:

  ```powershell
  Set-Location nuxt-bakery-demo
  npm test
  npm run typecheck
  npm run build
  Set-Location ..
  ```

- [ ] Commit only Task 8 files:

  ```powershell
  git add nuxt-bakery-demo/app/app.vue nuxt-bakery-demo/app/pages/index.vue 'nuxt-bakery-demo/app/pages/[slug].vue' nuxt-bakery-demo/app/assets/css/main.css nuxt-bakery-demo/app/utils/site-presentation.ts nuxt-bakery-demo/tests/semi-presentation.test.ts
  git commit -m "feat: present the SEMI E187 site in Nuxt"
  ```

---

### Task 9: Document the import and run the real approved content publication

**Files:**

- Modify: `nuxt-bakery-demo/README.md`
- Create outside Git: the timestamped `bakerydemodb.before-semi-e187-*` path assigned to `$semiBackup`
- Modify outside Git through the command: `bakerydemodb`
- Create outside Git through Wagtail storage: imported media files under the configured media root

**Interfaces:**

- Consumes the completed `import_semi_e187` command, both migrations, the approved source directory, the approved asset directory, and the existing local SQLite database.
- Produces one timestamped pre-import backup, a migrated/published local database, three Wagtail image records (plus the optional logo only when supplied), and an updated operator README. Database/media outputs remain outside Git.

- [ ] Update the README architecture, public APIs, supported structured blocks, explicit navigation behavior, import prerequisites, dry-run/publish commands, startup commands, and backup/rollback instructions. Replace the obsolete About/TEST route table and `show_in_menus` navigation explanation.

- [ ] Run documentation-sensitive checks and inspect the diff:

  ```powershell
  git diff --check
  git diff -- nuxt-bakery-demo/README.md
  ```

- [ ] Commit only the README before modifying the ignored local database/media:

  ```powershell
  git add nuxt-bakery-demo/README.md
  git commit -m "docs: explain the SEMI import workflow"
  ```

- [ ] Confirm no Wagtail server process is writing to `bakerydemodb`. Capture a deterministic pre-import JSON snapshot of `TEST`, `AXCC`, and `CCC`, then create a new timestamped backup with `Copy-Item`; never overwrite or reuse `bakerydemodb.backup-20260827`. Record the resolved source/destination paths and byte sizes.

  ```powershell
  $semiUnrelatedBefore = .\.venv\Scripts\python.exe manage.py shell -c "import json; from wagtail.models import Page; print(json.dumps(list(Page.objects.filter(slug__in=['test-page','axcc','ccc']).order_by('pk').values('id','path','depth','live','show_in_menus','slug','title')),ensure_ascii=False,sort_keys=True))"
  $semiTimestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $semiDatabase = (Resolve-Path -LiteralPath '.\bakerydemodb').Path
  $semiBackup = Join-Path (Get-Location) "bakerydemodb.before-semi-e187-$semiTimestamp"
  Copy-Item -LiteralPath $semiDatabase -Destination $semiBackup
  Get-Item -LiteralPath $semiDatabase, $semiBackup | Select-Object FullName, Length
  ```

- [ ] Apply migrations to the local database:

  ```powershell
  .\.venv\Scripts\python.exe manage.py migrate
  ```

- [ ] Run the real dry-run with the supplied paths and capture the report for review:

  ```powershell
  .\.venv\Scripts\python.exe manage.py import_semi_e187 `
    --html-dir 'C:\Users\eerr0\Downloads' `
    --asset-dir 'C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723' `
    --dry-run
  ```

- [ ] Verify the dry-run reports Home ID 60, four target pages, three required images, 15 disabled placeholders, missing optional logo and English-page warnings, and explicitly lists `TEST`, `AXCC`, and `CCC` as untouched. Stop if any action exceeds the approved scope.

- [ ] Run the real publish command, then immediately run it a second time to prove idempotency:

  ```powershell
  .\.venv\Scripts\python.exe manage.py import_semi_e187 `
    --html-dir 'C:\Users\eerr0\Downloads' `
    --asset-dir 'C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723' `
    --publish
  .\.venv\Scripts\python.exe manage.py import_semi_e187 `
    --html-dir 'C:\Users\eerr0\Downloads' `
    --asset-dir 'C:\Users\eerr0\Downloads\SEMI_E187_SITE_0723\SEMI E187 SITE 0723' `
    --publish
  ```

- [ ] Query the database through Django and verify: Home ID/type/live, target IDs/parent/order/live/menu flags, explicit navigation order, exact imported-image count, and unchanged snapshots for `TEST`, `AXCC`, and `CCC`. Do not use the unavailable `sqlite3` CLI.

  ```powershell
  .\.venv\Scripts\python.exe manage.py shell -c "from bakerydemo.base.models import HomePage,SiteSettings; from wagtail.images import get_image_model; from wagtail.models import Page,Site; h=HomePage.objects.get(pk=60); print('HOME',h.pk,h.live); print('TARGETS',[(p.pk,p.slug,p.live,p.show_in_menus,p.get_parent().pk) for p in h.get_children().specific().filter(slug__in=['about','resources','certification','ecosystem'])]); print('UNTOUCHED',[(p.pk,p.slug,p.live,p.show_in_menus,p.path) for p in Page.objects.filter(slug__in=['test-page','axcc','ccc']).order_by('pk')]); s=SiteSettings.for_site(Site.objects.get(root_page_id=60)); print('NAV',[(b.value.pk,b.value.slug) for b in s.primary_navigation]); print('IMAGES',get_image_model().objects.filter(collection__name='SEMI E187').count())"
  $semiUnrelatedAfter = .\.venv\Scripts\python.exe manage.py shell -c "import json; from wagtail.models import Page; print(json.dumps(list(Page.objects.filter(slug__in=['test-page','axcc','ccc']).order_by('pk').values('id','path','depth','live','show_in_menus','slug','title')),ensure_ascii=False,sort_keys=True))"
  if ($semiUnrelatedAfter -ne $semiUnrelatedBefore) { throw 'Unrelated page state changed.' }
  ```

- [ ] Ensure `git status --short` shows the pre-existing `bakerydemodb.backup-20260827` and the new timestamped path stored in `$semiBackup` as untracked local backups, with no database, media, or generated file accidentally staged.

---

### Task 10: Run full automated, API, and browser verification

**Files:**

- Modify only if verification exposes a scoped defect: files from Tasks 1-8 and their corresponding tests.
- Do not modify source HTML files or the user's supplied JPEGs.

**Interfaces:**

- Consumes the published Wagtail database, Wagtail port 8000, Nuxt port 3100, all automated test suites, and the five accepted frontend routes.
- Produces fresh test/lint/build/API/browser evidence, a scoped regression fix only when a failure is reproduced, and the final branch-integration choices. It does not merge, push, restore a database, or delete a branch by itself.

- [ ] Read and apply `superpowers:verification-before-completion` before making any completion claim.

- [ ] Run all focused Django tests plus full system checks:

  ```powershell
  $env:DJANGO_SETTINGS_MODULE='bakerydemo.settings.test'
  .\.venv\Scripts\python.exe manage.py test
  Remove-Item Env:DJANGO_SETTINGS_MODULE
  .\.venv\Scripts\python.exe manage.py check
  .\.venv\Scripts\python.exe manage.py makemigrations --check
  ```

- [ ] Run Python/template lint for changed backend files. If repository-wide lint is blocked by unrelated existing migration/tooling work, run focused Ruff and template checks and report the exact limitation rather than changing unrelated files.

- [ ] Run all Nuxt checks from a clean dependency state:

  ```powershell
  Set-Location nuxt-bakery-demo
  npm ci
  npm test
  npm run typecheck
  npm run build
  Set-Location ..
  ```

- [ ] Start Wagtail on port 8000 and Nuxt on port 3100 in separate reusable terminal sessions. Smoke-test:
  - Wagtail `/api/v2/pages/60/?fields=*`
  - Wagtail `/api/site-settings/`
  - Nuxt `/api/bakery/home`
  - Nuxt `/api/bakery/site-settings`
  - Nuxt `/api/bakery/navigation`
  - Nuxt `/api/bakery/pages/about`
  - Nuxt `/api/bakery/pages/resources`
  - Nuxt `/api/bakery/pages/certification`
  - Nuxt `/api/bakery/pages/ecosystem`

- [ ] Read and apply `browser:control-in-app-browser`, then inspect `/`, `/about/`, `/resources/`, `/certification/`, and `/ecosystem/` at desktop and 390-pixel mobile widths. Verify navigation, hero hierarchy, card grids, semantic document table, five process stages, two case studies, all three JPEGs, footer/contact data, focus states, disabled `即將提供` labels, internal fragments, external government link, no English switch, and no horizontal overflow.

- [ ] Simulate the CMS outage by stopping Wagtail while Nuxt remains running. Confirm existing route error/retry states remain understandable and no sensitive Wagtail base URL appears in browser payloads. Restart Wagtail and confirm retry recovers.

- [ ] Inspect browser console/network errors and accessibility basics. Fix only scoped failures, add a regression test first, rerun the smallest failing verification, then rerun the complete relevant suite.

- [ ] Run `git diff --check`, `git status --short --branch`, and inspect the branch diff. Confirm the user-owned `bakerydemodb.backup-20260827` and the new timestamped database backup are not committed.

- [ ] If verification requires a code change, return to the originating task's red/green test and exact-file commit steps. Do not bundle unrelated fixes into a generic verification commit.

- [ ] Read and apply `superpowers:requesting-code-review`. Address only verified findings, rerun affected tests, and record final evidence: Django test count, Nuxt test count, typecheck/build result, API endpoint results, browser routes/viewports, imported page/image IDs, and backup path.

- [ ] After review and verification are clean, read and apply `superpowers:finishing-a-development-branch` to offer the user the supported integration choices. Do not merge, push, or delete the branch without the user's explicit selection.
