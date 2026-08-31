<script setup lang="ts">
import type { BakeryProcessStepsBlock } from '#shared/types/bakery'
import ContentLink from './ContentLink.vue'

defineProps<{
  value: BakeryProcessStepsBlock['value']
}>()
</script>

<template>
  <section class="content-section process-section">
    <h2 v-if="value.heading" class="section-title">
      {{ value.heading }}
    </h2>
    <p v-if="value.introduction" class="section-introduction">
      {{ value.introduction }}
    </p>

    <ol class="process-steps">
      <li
        v-for="(step, index) in value.steps"
        :key="`${step.number}-${step.title}-${index}`"
        class="process-step"
      >
        <span class="process-step__number" aria-hidden="true">
          {{ step.number || String(index + 1).padStart(2, '0') }}
        </span>
        <div class="process-step__content">
          <h3>{{ step.title }}</h3>
          <p>{{ step.summary }}</p>

          <ul v-if="step.checklist.length" class="process-step__checklist">
            <li v-for="item in step.checklist" :key="item">
              {{ item }}
            </li>
          </ul>

          <div
            v-if="step.resource_links.length"
            class="process-step__resources"
          >
            <ContentLink
              v-for="(link, linkIndex) in step.resource_links"
              :key="`${link.label}-${linkIndex}`"
              :link="link"
            />
          </div>
        </div>
      </li>
    </ol>
  </section>
</template>
