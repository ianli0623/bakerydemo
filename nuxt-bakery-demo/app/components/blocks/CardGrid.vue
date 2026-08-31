<script setup lang="ts">
import type { BakeryCardGridBlock } from '#shared/types/bakery'
import { getCardHeadingTag } from '~/utils/stream-field'
import ContentLink from './ContentLink.vue'

defineProps<{
  value: BakeryCardGridBlock['value']
}>()
</script>

<template>
  <section class="content-section card-grid-section">
    <p v-if="value.eyebrow" class="section-eyebrow">
      {{ value.eyebrow }}
    </p>
    <h2 v-if="value.heading" class="section-title">
      {{ value.heading }}
    </h2>
    <p v-if="value.introduction" class="section-introduction">
      {{ value.introduction }}
    </p>

    <div class="card-grid" :class="`card-grid--${value.layout}`">
      <article
        v-for="(card, index) in value.cards"
        :key="`${card.number}-${card.title}-${index}`"
        class="content-card"
      >
        <p v-if="card.number" class="content-card__number">
          {{ card.number }}
        </p>
        <p v-if="card.eyebrow" class="content-card__eyebrow">
          {{ card.eyebrow }}
        </p>
        <component :is="getCardHeadingTag(value.heading)">
          {{ card.title }}
        </component>
        <p>{{ card.summary }}</p>
        <ContentLink v-if="card.link" :link="card.link" />
      </article>
    </div>
  </section>
</template>
