<script setup lang="ts">
import type { BakeryCaseStudyBlock } from '#shared/types/bakery'
import { getImagePresentation } from '~/utils/stream-field'

const props = defineProps<{
  value: BakeryCaseStudyBlock['value']
}>()

const equipmentImage = computed(() =>
  getImagePresentation(
    props.value.equipment_image,
    props.value.equipment_caption || `${props.value.company} ${props.value.product}`
  )
)
const outcomeImage = computed(() =>
  getImagePresentation(
    props.value.outcome_image,
    props.value.outcome_caption || `${props.value.company} SEMI E187`
  )
)
</script>

<template>
  <article class="content-section case-study">
    <div class="case-study__overview">
      <div class="case-study__overview-copy">
        <header class="case-study__header">
          <p v-if="value.case_label" class="section-eyebrow">
            {{ value.case_label }}
          </p>
          <h2>{{ value.company }}</h2>
          <p class="case-study__product">{{ value.product }}</p>
          <p v-if="value.certification_status" class="case-study__status">
            {{ value.certification_status }}
          </p>
          <p class="section-introduction">{{ value.summary }}</p>
        </header>

        <dl v-if="value.metadata.length" class="case-study__metadata">
          <div
            v-for="(item, index) in value.metadata"
            :key="`${item.label}-${index}`"
          >
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </div>

      <figure v-if="equipmentImage" class="case-study__figure case-study__figure--equipment">
        <img
          :src="equipmentImage.src"
          :width="equipmentImage.width"
          :height="equipmentImage.height"
          :alt="equipmentImage.alt"
          loading="lazy"
        >
        <figcaption v-if="value.equipment_caption">
          {{ value.equipment_caption }}
        </figcaption>
      </figure>
    </div>

    <div class="case-study__details">
      <div>
        <div class="case-study__columns">
          <section>
            <h3>{{ value.challenge_heading }}</h3>
            <!-- Published editor-managed Wagtail rich text is trusted here. -->
            <div class="rich-text" v-html="value.challenge" />
          </section>
          <section>
            <h3>{{ value.solution_heading }}</h3>
            <!-- Published editor-managed Wagtail rich text is trusted here. -->
            <div class="rich-text" v-html="value.solution" />
          </section>
        </div>

        <section v-if="value.security_controls.length" class="case-study__controls">
          <h3>{{ value.security_controls_heading }}</h3>
          <ul>
            <li
              v-for="(control, index) in value.security_controls"
              :key="`${control.title}-${index}`"
            >
              <strong>{{ control.title }}</strong>
              <span>{{ control.summary }}</span>
            </li>
          </ul>
        </section>
      </div>

      <figure v-if="outcomeImage" class="case-study__figure case-study__figure--outcome">
        <img
          :src="outcomeImage.src"
          :width="outcomeImage.width"
          :height="outcomeImage.height"
          :alt="outcomeImage.alt"
          loading="lazy"
        >
        <figcaption v-if="value.outcome_caption">
          {{ value.outcome_caption }}
        </figcaption>
      </figure>
    </div>
  </article>
</template>
