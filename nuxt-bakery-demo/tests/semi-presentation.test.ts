import assert from 'node:assert/strict';
import test from 'node:test';
import type {
  BakeryImage,
  BakerySiteSettings,
  BakeryStandardPage,
  BakeryStreamBlock,
} from '../shared/types/bakery.ts';
import * as sitePresentation from '../app/utils/site-presentation.ts';
import {
  getContactLinks,
  getFooterLogoPresentation,
  getNavigationItemLabel,
  isNavigationItemActive,
  reduceNavigationOpen,
} from '../app/utils/site-presentation.ts';

test('mobile navigation toggles and closes on escape and route changes', () => {
  assert.equal(reduceNavigationOpen(false, 'toggle'), true);
  assert.equal(reduceNavigationOpen(true, 'toggle'), false);
  assert.equal(reduceNavigationOpen(true, 'escape'), false);
  assert.equal(reduceNavigationOpen(true, 'route'), false);
});

test('navigation active state matches normalized routes exactly', () => {
  assert.equal(isNavigationItemActive('/', '/'), true);
  assert.equal(isNavigationItemActive('/', '/about/'), false);
  assert.equal(isNavigationItemActive('/about', '/about/?from=home'), true);
  assert.equal(isNavigationItemActive('/about/', '/about/team/'), false);
});

test('navigation uses the localized interface label for the home item', () => {
  assert.equal(
    getNavigationItemLabel(
      {
        title:
          'SEMI E187 Semiconductor Equipment Cybersecurity Standard and Certification Scheme',
        slug: '',
      },
      'Home',
    ),
    'Home',
  );
  assert.equal(
    getNavigationItemLabel(
      { title: 'Implementation Resources', slug: 'resources' },
      'Home',
    ),
    'Implementation Resources',
  );
});

test('contact links use the settings phone href and email address', () => {
  const contact: BakerySiteSettings['contact'] = {
    heading: '聯絡窗口',
    name: '王小明',
    context: 'SEMI E187 諮詢',
    phone: '03-123-4567',
    phone_href: 'tel:+88631234567',
    email: 'semi@example.com',
  };

  assert.deepEqual(getContactLinks(contact), {
    phone: 'tel:+88631234567',
    email: 'mailto:semi@example.com',
  });
});

test('empty contact values do not produce interactive links', () => {
  const contact: BakerySiteSettings['contact'] = {
    heading: '',
    name: '',
    context: '',
    phone: '',
    phone_href: '',
    email: '',
  };

  assert.deepEqual(getContactLinks(contact), {
    phone: null,
    email: null,
  });
});

test('footer logo presentation uses its rendition and title fallback', () => {
  assert.equal(getFooterLogoPresentation(null), null);
  assert.deepEqual(
    getFooterLogoPresentation({
      id: 42,
      title: 'SEMI E187 推動平台',
      meta: {
        download_url: '/media/original.png',
        rendition: {
          url: '/media/logo.png',
          full_url: 'http://localhost:8000/media/logo.png',
          width: 320,
          height: 96,
          alt: '',
        },
      },
    }),
    {
      src: 'http://localhost:8000/media/logo.png',
      alt: 'SEMI E187 推動平台',
      width: 320,
      height: 96,
    },
  );
});

test('homepage presentation promotes the news grid without duplicating it', () => {
  const partitionHomeBlocks = Reflect.get(
    sitePresentation,
    'partitionHomeBlocks',
  );
  assert.equal(typeof partitionHomeBlocks, 'function');

  const introduction = {
    id: 'intro',
    type: 'paragraph_block',
    value: '<p>首頁介紹</p>',
  } satisfies BakeryStreamBlock;
  const news = {
    id: 'news',
    type: 'card_grid',
    value: {
      eyebrow: '',
      heading: 'Latest News',
      introduction: '',
      layout: 'two',
      cards: [],
    },
  } satisfies BakeryStreamBlock;
  const topics = {
    id: 'topics',
    type: 'card_grid',
    value: {
      eyebrow: 'EXPLORE THE SITE',
      heading: '網站主題專區',
      introduction: '',
      layout: 'four',
      cards: [],
    },
  } satisfies BakeryStreamBlock;

  assert.deepEqual(partitionHomeBlocks([introduction, news, topics]), {
    newsBlock: news,
    remainingBlocks: [introduction, topics],
  });
});

test('homepage presentation leaves content intact when no news grid exists', () => {
  const partitionHomeBlocks = Reflect.get(
    sitePresentation,
    'partitionHomeBlocks',
  );
  assert.equal(typeof partitionHomeBlocks, 'function');

  const body = [
    {
      id: 'intro',
      type: 'paragraph_block',
      value: '<p>首頁介紹</p>',
    },
  ] satisfies BakeryStreamBlock[];

  assert.deepEqual(partitionHomeBlocks(body), {
    newsBlock: null,
    remainingBlocks: body,
  });
});

function standardPage(
  slug: string,
  title: string,
  introduction: string,
  body: BakeryStreamBlock[],
): BakeryStandardPage {
  return {
    id: 1,
    meta: { type: 'base.StandardPage', slug },
    title,
    introduction,
    section_kicker: '',
    section_heading: '',
    secondary_section_kicker: '',
    secondary_section_heading: '',
    secondary_section_introduction: '',
    body,
    image_hero: null,
  };
}

test('about and certification become reference-style content sections without duplicated lead copy', () => {
  const getStandardPagePresentation = Reflect.get(
    sitePresentation,
    'getStandardPagePresentation',
  );
  assert.equal(typeof getStandardPagePresentation, 'function');

  const scenarios = [
    {
      slug: 'about',
      title: 'About the Standard and Its Background',
      kicker: 'UNDERSTANDING SEMI E187',
      html: '<p>標準背景第一段</p><p>標準背景第二段</p>',
    },
    {
      slug: 'certification',
      title: 'Certification and Compliance',
      kicker: 'ASSURANCE & COMPLIANCE',
      html: '<p>落實 <strong>公正性</strong> 與無歧視原則。</p>',
    },
  ];

  for (const scenario of scenarios) {
    const lead = {
      id: `${scenario.slug}-lead`,
      type: 'paragraph_block',
      value: scenario.html,
    } satisfies BakeryStreamBlock;
    const content = {
      id: `${scenario.slug}-content`,
      type: 'heading_block',
      value: { heading_text: '後續內容', size: 'h2' },
    } satisfies BakeryStreamBlock;

    const page = standardPage(
      scenario.slug,
      'Original page title',
      'Original introduction',
      [lead, content],
    );
    page.section_kicker = scenario.kicker;
    page.section_heading = scenario.title;
    const presentation = getStandardPagePresentation(scenario.slug, page);

    assert.deepEqual(presentation.sections, [
      {
        anchorId: scenario.slug,
        headingId: `${scenario.slug}-heading`,
        kicker: scenario.kicker,
        title: scenario.title,
        introduction: '',
        introductionHtml: scenario.html,
        layout: scenario.slug === 'about' ? 'split' : 'stacked',
        surface: 'white',
        body: [content],
      },
    ]);
  }
});

test('resources becomes one muted reference-style section while preserving its cards', () => {
  const getStandardPagePresentation = Reflect.get(
    sitePresentation,
    'getStandardPagePresentation',
  );
  assert.equal(typeof getStandardPagePresentation, 'function');

  const resources = {
    id: 'resources',
    type: 'card_grid',
    value: {
      eyebrow: '',
      heading: '標準導入資源專區',
      introduction:
        '為認驗證相關機構、技術實驗室及設備廠商提供核心指引與支援資源。',
      layout: 'three',
      cards: [],
    },
  } satisfies BakeryStreamBlock;

  const page = standardPage(
    'resources',
    'Implementation Resources',
    'Resources selected for organizations adopting the standard.',
    [resources],
  );
  page.section_kicker = 'IMPLEMENTATION TOOLKIT';
  page.section_heading = 'SEMI E187 Implementation Resources';
  const presentation = getStandardPagePresentation('resources', page);

  assert.deepEqual(presentation.sections, [
    {
      anchorId: 'resources',
      headingId: 'resources-heading',
      kicker: 'IMPLEMENTATION TOOLKIT',
      title: 'SEMI E187 Implementation Resources',
      introduction:
        'Resources selected for organizations adopting the standard.',
      introductionHtml: '',
      layout: 'stacked',
      surface: 'muted',
      body: [
        {
          ...resources,
          value: {
            ...resources.value,
            heading: '',
            introduction: '',
          },
        },
      ],
    },
  ]);
});

test('ecosystem follows the reference order with overview and demonstration sections', () => {
  const getStandardPagePresentation = Reflect.get(
    sitePresentation,
    'getStandardPagePresentation',
  );
  assert.equal(typeof getStandardPagePresentation, 'function');

  const overview = {
    id: 'ecosystem-cards',
    type: 'card_grid',
    value: {
      eyebrow: '',
      heading: '案例與生態系推動',
      introduction: '生態鏈結介紹',
      layout: 'two',
      cards: [],
    },
  } satisfies BakeryStreamBlock;
  const caseImage = {
    id: 42,
    title: '案例測試圖片',
    meta: {
      download_url: '/media/case.jpg',
      rendition: {
        url: '/media/case.1200x800.jpg',
        width: 1200,
        height: 800,
        alt: '案例測試圖片',
      },
    },
  } satisfies BakeryImage;
  const caseStudy = {
    id: 'case-study',
    type: 'case_study',
    value: {
      case_label: 'CASE STUDY 01',
      company: '均豪精密',
      product: 'AOI 自動光學檢測設備',
      certification_status: '通過驗證',
      summary: '案例摘要',
      metadata: [],
      equipment_image: caseImage,
      equipment_caption: '',
      challenge_heading: '挑戰',
      challenge: '<p>挑戰內容</p>',
      solution_heading: '解決方案',
      solution: '<p>解決方案內容</p>',
      security_controls_heading: 'Security Controls',
      security_controls: [],
      outcome_image: caseImage,
      outcome_caption: '',
    },
  } satisfies BakeryStreamBlock;

  const page = standardPage(
    'ecosystem',
    'Cases and Ecosystem',
    'Original introduction',
    [overview, caseStudy],
  );
  page.section_kicker = 'PARTNER ECOSYSTEM';
  page.section_heading = 'Building the SEMI E187 Ecosystem';
  page.secondary_section_kicker = 'DEMONSTRATION SITES';
  page.secondary_section_heading = 'Implementation Case Studies';
  page.secondary_section_introduction =
    'See how equipment makers adopt and validate SEMI E187 in practice.';
  const presentation = getStandardPagePresentation('ecosystem', page);

  assert.deepEqual(presentation.sections, [
    {
      anchorId: 'ecosystem',
      headingId: 'ecosystem-heading',
      kicker: 'PARTNER ECOSYSTEM',
      title: 'Building the SEMI E187 Ecosystem',
      introduction: '生態鏈結介紹',
      introductionHtml: '',
      layout: 'stacked',
      surface: 'muted',
      body: [
        {
          ...overview,
          value: {
            ...overview.value,
            heading: '',
            introduction: '',
          },
        },
      ],
    },
    {
      anchorId: 'case-studies',
      headingId: 'cases-heading',
      kicker: 'DEMONSTRATION SITES',
      title: 'Implementation Case Studies',
      introduction:
        'See how equipment makers adopt and validate SEMI E187 in practice.',
      introductionHtml: '',
      layout: 'stacked',
      surface: 'muted',
      body: [caseStudy],
    },
  ]);
});
