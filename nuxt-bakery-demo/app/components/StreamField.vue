<script setup lang="ts">
import type { BakeryStreamBlock } from '#shared/types/bakery'
import CardGrid from '~/components/blocks/CardGrid.vue'
import CaseStudy from '~/components/blocks/CaseStudy.vue'
import DocumentTable from '~/components/blocks/DocumentTable.vue'
import ProcessSteps from '~/components/blocks/ProcessSteps.vue'
import {
  getEmbedPresentation,
  getHeadingTag,
  getImageRendition,
  getRenditionSource,
  getStructuredBlockAnchor
} from '~/utils/stream-field'

const props = defineProps<{
  blocks: BakeryStreamBlock[]
  reservedAnchors?: string[]
  pageSlug?: string
}>()

const { t } = useI18n()
</script>

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

      <!-- Published editor-managed Wagtail rich text is trusted here. -->
      <div
        v-else-if="block.type === 'paragraph_block'"
        class="rich-text"
        v-html="block.value"
      />

      <figure v-else-if="block.type === 'image_block'" class="stream-image">
        <img
          v-if="getImageRendition(block)"
          :src="getRenditionSource(getImageRendition(block)!)"
          :width="getImageRendition(block)?.width"
          :height="getImageRendition(block)?.height"
          :alt="getImageRendition(block)?.alt || block.value.image.title"
          loading="lazy"
        >
        <figcaption v-if="block.value.caption || block.value.attribution">
          <span>{{ block.value.caption }}</span>
          <cite v-if="block.value.attribution">
            {{ block.value.attribution }}
          </cite>
        </figcaption>
      </figure>

      <blockquote
        v-else-if="block.type === 'block_quote'"
        class="stream-quote"
      >
        <p>{{ block.value.text }}</p>
        <cite v-if="block.value.attribute_name">
          {{ block.value.attribute_name }}
        </cite>
      </blockquote>

      <CardGrid
        v-else-if="block.type === 'card_grid'"
        :id="getStructuredBlockAnchor(
          block,
          props.blocks,
          props.reservedAnchors,
          props.pageSlug
        )"
        :value="block.value"
      />

      <DocumentTable
        v-else-if="block.type === 'document_table'"
        :value="block.value"
      />

      <ProcessSteps
        v-else-if="block.type === 'process_steps'"
        :id="getStructuredBlockAnchor(
          block,
          props.blocks,
          props.reservedAnchors,
          props.pageSlug
        )"
        :value="block.value"
      />

      <CaseStudy
        v-else-if="block.type === 'case_study'"
        :id="getStructuredBlockAnchor(
          block,
          props.blocks,
          props.reservedAnchors,
          props.pageSlug
        )"
        :value="block.value"
      />

      <div
        v-else-if="block.type === 'embed_block' && getEmbedPresentation(block.value)"
        class="stream-embed"
      >
        <iframe
          v-if="getEmbedPresentation(block.value)?.kind === 'iframe'"
          :src="getEmbedPresentation(block.value)?.url"
          :title="t('embed.videoTitle')"
          loading="lazy"
          allowfullscreen
        />
        <a
          v-else
          :href="getEmbedPresentation(block.value)?.url"
          target="_blank"
          rel="noopener noreferrer"
        >
          {{ t('embed.openMedia') }}
        </a>
      </div>
    </template>
  </div>
</template>
