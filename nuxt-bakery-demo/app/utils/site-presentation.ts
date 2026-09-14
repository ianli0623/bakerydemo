import type {
  BakeryCardGridBlock,
  BakeryImage,
  BakerySiteSettings,
  BakeryStandardPage,
  BakeryStreamBlock,
} from '../../shared/types/bakery.ts';

export interface FooterLogoPresentation {
  src: string;
  alt: string;
  width: number;
  height: number;
}

export interface HomeBlockPartition {
  newsBlock: BakeryCardGridBlock | null;
  remainingBlocks: BakeryStreamBlock[];
}

export interface StandardPageSectionPresentation {
  anchorId: string;
  headingId: string;
  kicker: string;
  title: string;
  introduction: string;
  introductionHtml: string;
  layout: 'split' | 'stacked';
  surface: 'white' | 'muted';
  body: BakeryStreamBlock[];
}

export interface StandardPagePresentation {
  sections: StandardPageSectionPresentation[];
}

const referenceStandardSections: Record<
  string,
  Pick<
    StandardPageSectionPresentation,
    'anchorId' | 'headingId' | 'layout' | 'surface'
  >
> = {
  about: {
    anchorId: 'about',
    headingId: 'about-heading',
    layout: 'split',
    surface: 'white',
  },
  resources: {
    anchorId: 'resources',
    headingId: 'resources-heading',
    layout: 'stacked',
    surface: 'muted',
  },
  certification: {
    anchorId: 'certification',
    headingId: 'certification-heading',
    layout: 'stacked',
    surface: 'white',
  },
};

function withoutCardGridHeading(
  block: BakeryCardGridBlock,
): BakeryCardGridBlock {
  return {
    ...block,
    value: {
      ...block.value,
      heading: '',
      introduction: '',
    },
  };
}

export function getStandardPagePresentation(
  slug: string,
  page: BakeryStandardPage,
): StandardPagePresentation {
  const referenceSection = referenceStandardSections[slug];
  const section: StandardPageSectionPresentation = {
    anchorId: referenceSection?.anchorId || slug,
    headingId: referenceSection?.headingId || `${slug}-heading`,
    kicker: page.section_kicker || 'SEMI E187',
    title: page.section_heading || page.title,
    introduction: page.introduction,
    introductionHtml: '',
    layout: referenceSection?.layout || 'stacked',
    surface: referenceSection?.surface || 'white',
    body: page.body,
  };

  const firstBlock = page.body[0];
  if (
    (slug === 'about' || slug === 'certification') &&
    firstBlock?.type === 'paragraph_block'
  ) {
    const introduction = page.introduction.trim();

    return {
      sections: [
        {
          ...section,
          introduction,
          introductionHtml: introduction ? '' : firstBlock.value,
          body: page.body.slice(1),
        },
      ],
    };
  }

  if (slug === 'resources' && firstBlock?.type === 'card_grid') {
    return {
      sections: [
        {
          ...section,
          introduction: page.introduction || firstBlock.value.introduction,
          body: [withoutCardGridHeading(firstBlock), ...page.body.slice(1)],
        },
      ],
    };
  }

  if (slug === 'ecosystem') {
    const overviewBlock = firstBlock?.type === 'card_grid' ? firstBlock : null;
    const caseStudyBlocks = overviewBlock ? page.body.slice(1) : page.body;

    return {
      sections: [
        {
          anchorId: 'ecosystem',
          headingId: 'ecosystem-heading',
          kicker: page.section_kicker || 'SEMI E187',
          title:
            page.section_heading || overviewBlock?.value.heading || page.title,
          introduction: overviewBlock?.value.introduction || page.introduction,
          introductionHtml: '',
          layout: 'stacked',
          surface: 'muted',
          body: overviewBlock ? [withoutCardGridHeading(overviewBlock)] : [],
        },
        {
          anchorId: 'case-studies',
          headingId: 'cases-heading',
          kicker: page.secondary_section_kicker,
          title: page.secondary_section_heading,
          introduction: page.secondary_section_introduction,
          introductionHtml: '',
          layout: 'stacked',
          surface: 'muted',
          body: caseStudyBlocks,
        },
      ],
    };
  }

  return { sections: [section] };
}

export function partitionHomeBlocks(
  blocks: BakeryStreamBlock[],
): HomeBlockPartition {
  const newsIndex = blocks.findIndex((block) => block.type === 'card_grid');

  if (newsIndex < 0) {
    return { newsBlock: null, remainingBlocks: blocks };
  }

  return {
    newsBlock: blocks[newsIndex] as BakeryCardGridBlock,
    remainingBlocks: blocks.filter((_, index) => index !== newsIndex),
  };
}

function normalizePath(value: string): string {
  const pathname = value.split(/[?#]/, 1)[0] || '/';
  return pathname === '/'
    ? '/'
    : `/${pathname.split('/').filter(Boolean).join('/')}/`;
}

export function reduceNavigationOpen(
  open: boolean,
  event: 'toggle' | 'escape' | 'route',
): boolean {
  return event === 'toggle' ? !open : false;
}

export function isNavigationItemActive(
  itemPath: string,
  currentPath: string,
): boolean {
  return normalizePath(itemPath) === normalizePath(currentPath);
}

export function getNavigationItemLabel(
  item: Pick<BakerySiteSettings['navigation'][number], 'slug' | 'title'>,
  homeLabel: string,
): string {
  return item.slug ? item.title : homeLabel;
}

export function getContactLinks(contact: BakerySiteSettings['contact']): {
  phone: string | null;
  email: string | null;
} {
  return {
    phone: contact.phone_href || null,
    email: contact.email ? `mailto:${contact.email}` : null,
  };
}

export function getFooterLogoPresentation(
  logo: BakeryImage | null,
): FooterLogoPresentation | null {
  const rendition = logo?.meta.rendition;
  if (!logo || !rendition) {
    return null;
  }

  return {
    src: rendition.full_url || rendition.url,
    alt: rendition.alt || logo.title,
    width: rendition.width,
    height: rendition.height,
  };
}
