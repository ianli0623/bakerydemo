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
  full_url?: string
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

export interface BakeryContentLink {
  label: string
  kind: 'internal' | 'external' | 'disabled'
  href: string | null
  new_tab: boolean
}

export interface BakeryCard {
  number: string
  eyebrow: string
  title: string
  summary: string
  link: BakeryContentLink | null
}

export interface BakeryCardGridBlock {
  id: string
  type: 'card_grid'
  value: {
    eyebrow: string
    heading: string
    introduction: string
    layout: 'two' | 'three' | 'four'
    cards: BakeryCard[]
  }
}

export interface BakeryDocumentRow {
  number: string
  title: string
  summary: string
  status: string
  link: BakeryContentLink | null
}

export interface BakeryDocumentTableBlock {
  id: string
  type: 'document_table'
  value: {
    heading: string
    caption: string
    anchor_id: string
    rows: BakeryDocumentRow[]
  }
}

export interface BakeryProcessStep {
  number: string
  title: string
  summary: string
  checklist: string[]
  resource_links: BakeryContentLink[]
}

export interface BakeryProcessStepsBlock {
  id: string
  type: 'process_steps'
  value: {
    heading: string
    introduction: string
    steps: BakeryProcessStep[]
  }
}

export interface BakeryCaseStudyBlock {
  id: string
  type: 'case_study'
  value: {
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
    security_controls_heading: string
    security_controls: Array<{ title: string; summary: string }>
    outcome_image: BakeryImage
    outcome_caption: string
  }
}

export type BakeryStreamBlock =
  | {
      id: string
      type: 'heading_block'
      value: {
        heading_text: string
        size: 'h2' | 'h3' | 'h4' | ''
      }
    }
  | { id: string; type: 'paragraph_block'; value: string }
  | {
      id: string
      type: 'image_block'
      value: {
        image: BakeryImage
        caption: string
        attribution: string
      }
    }
  | {
      id: string
      type: 'block_quote'
      value: {
        text: string
        attribute_name: string
        settings?: {
          theme?: string
          text_size?: string
        }
      }
    }
  | BakeryCardGridBlock
  | BakeryDocumentTableBlock
  | BakeryProcessStepsBlock
  | BakeryCaseStudyBlock
  | { id: string; type: 'embed_block'; value: string }

export type BakeryPageReference = BakeryPageSummary

export interface BakeryHomePage extends BakeryPageSummary {
  hero_badge: string
  hero_text: string
  hero_cta: string
  hero_cta_link: BakeryPageReference | null
  secondary_hero_cta: string
  secondary_hero_cta_link: BakeryPageReference | null
  secondary_hero_cta_fragment: string
  body: BakeryStreamBlock[]
  lead_title: string
  lead_text: string | null
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
  section_kicker: string
  section_heading: string
  secondary_section_kicker: string
  secondary_section_heading: string
  secondary_section_introduction: string
  body: BakeryStreamBlock[]
  image_hero: BakeryRendition | null
}

export interface BakeryNavigationItem {
  id: number
  title: string
  slug: string
  path: string
}

export interface BakerySiteSettings {
  locale: BakeryLocale
  home_page_id: number
  home_path: string
  brand_label: string
  title_suffix: string
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
  footer_introduction: string
  organisation_text: string
  footer_logo: BakeryImage | null
  navigation: BakeryNavigationItem[]
}

export interface BakeryFeaturedSection {
  id: number
  title: string
  url: string
}

export interface BakeryHomeViewModel extends BakeryHomePage {
  featuredSections: BakeryFeaturedSection[]
  heroCtaPath: string | null
  secondaryHeroCtaPath: string | null
}
import type { BakeryLocale } from '../utils/locale.ts'
