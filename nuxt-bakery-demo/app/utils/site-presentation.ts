import type {
  BakeryCardGridBlock,
  BakeryImage,
  BakerySiteSettings,
  BakeryStandardPage,
  BakeryStreamBlock
} from '../../shared/types/bakery.ts'

export interface FooterLogoPresentation {
  src: string
  alt: string
  width: number
  height: number
}

export interface HomeBlockPartition {
  newsBlock: BakeryCardGridBlock | null
  remainingBlocks: BakeryStreamBlock[]
}

export interface StandardPageSectionPresentation {
  anchorId: string
  headingId: string
  kicker: string
  title: string
  introduction: string
  introductionHtml: string
  layout: 'split' | 'stacked'
  surface: 'white' | 'muted'
  body: BakeryStreamBlock[]
}

export interface StandardPagePresentation {
  sections: StandardPageSectionPresentation[]
}

const referenceStandardSections: Record<
  string,
  Pick<
    StandardPageSectionPresentation,
    'anchorId' | 'headingId' | 'kicker' | 'title' | 'layout' | 'surface'
  >
> = {
  about: {
    anchorId: 'about',
    headingId: 'about-heading',
    kicker: 'ABOUT SEMI E187',
    title: '關於標準與背景介紹',
    layout: 'split',
    surface: 'white'
  },
  resources: {
    anchorId: 'resources',
    headingId: 'resources-heading',
    kicker: 'IMPLEMENTATION RESOURCES',
    title: '標準導入資源專區',
    layout: 'stacked',
    surface: 'muted'
  },
  certification: {
    anchorId: 'certification',
    headingId: 'certification-heading',
    kicker: 'CERTIFICATION & COMPLIANCE',
    title: '驗證與合規專區',
    layout: 'stacked',
    surface: 'white'
  }
}

function withoutCardGridHeading(block: BakeryCardGridBlock): BakeryCardGridBlock {
  return {
    ...block,
    value: {
      ...block.value,
      heading: '',
      introduction: ''
    }
  }
}

export function getStandardPagePresentation(
  slug: string,
  page: BakeryStandardPage
): StandardPagePresentation {
  const referenceSection = referenceStandardSections[slug]
  const section: StandardPageSectionPresentation = {
    anchorId: referenceSection?.anchorId || slug,
    headingId: referenceSection?.headingId || `${slug}-heading`,
    kicker: referenceSection?.kicker || 'SEMI E187',
    title: referenceSection?.title || page.title,
    introduction: page.introduction,
    introductionHtml: '',
    layout: referenceSection?.layout || 'stacked',
    surface: referenceSection?.surface || 'white',
    body: page.body
  }

  const firstBlock = page.body[0]
  if (
    (slug === 'about' || slug === 'certification')
    && firstBlock?.type === 'paragraph_block'
  ) {
    return {
      sections: [{
        ...section,
        introduction: '',
        introductionHtml: firstBlock.value,
        body: page.body.slice(1)
      }]
    }
  }

  if (slug === 'resources' && firstBlock?.type === 'card_grid') {
    return {
      sections: [{
        ...section,
        title: firstBlock.value.heading || section.title,
        introduction: firstBlock.value.introduction || page.introduction,
        body: [withoutCardGridHeading(firstBlock), ...page.body.slice(1)]
      }]
    }
  }

  if (slug === 'ecosystem') {
    const overviewBlock = firstBlock?.type === 'card_grid' ? firstBlock : null
    const caseStudyBlocks = overviewBlock ? page.body.slice(1) : page.body

    return {
      sections: [
        {
          anchorId: 'ecosystem',
          headingId: 'ecosystem-heading',
          kicker: 'CASE SHARING & ECOSYSTEM',
          title: overviewBlock?.value.heading || '案例與生態系推動',
          introduction: overviewBlock?.value.introduction || page.introduction,
          introductionHtml: '',
          layout: 'stacked',
          surface: 'muted',
          body: overviewBlock ? [withoutCardGridHeading(overviewBlock)] : []
        },
        {
          anchorId: 'case-studies',
          headingId: 'cases-heading',
          kicker: 'DEMONSTRATION SITES',
          title: '設備廠商導入應用案例',
          introduction: '提供半導體設備製造業者實施 SEMI E187 導入與驗證之實務場域示範標竿。',
          introductionHtml: '',
          layout: 'stacked',
          surface: 'muted',
          body: caseStudyBlocks
        }
      ]
    }
  }

  return { sections: [section] }
}

export function partitionHomeBlocks(
  blocks: BakeryStreamBlock[]
): HomeBlockPartition {
  const newsIndex = blocks.findIndex(
    block => block.type === 'card_grid' && block.value.heading.trim() === '最新消息'
  )

  if (newsIndex < 0) {
    return { newsBlock: null, remainingBlocks: blocks }
  }

  return {
    newsBlock: blocks[newsIndex] as BakeryCardGridBlock,
    remainingBlocks: blocks.filter((_, index) => index !== newsIndex)
  }
}

function normalizePath(value: string): string {
  const pathname = value.split(/[?#]/, 1)[0] || '/'
  return pathname === '/'
    ? '/'
    : `/${pathname.split('/').filter(Boolean).join('/')}/`
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
): { phone: string | null; email: string | null } {
  return {
    phone: contact.phone_href || null,
    email: contact.email ? `mailto:${contact.email}` : null
  }
}

export function getFooterLogoPresentation(
  logo: BakeryImage | null
): FooterLogoPresentation | null {
  const rendition = logo?.meta.rendition
  if (!logo || !rendition) {
    return null
  }

  return {
    src: rendition.full_url || rendition.url,
    alt: rendition.alt || logo.title,
    width: rendition.width,
    height: rendition.height
  }
}
