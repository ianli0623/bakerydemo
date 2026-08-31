<script setup lang="ts">
import type { BakeryContentLink } from '#shared/types/bakery'
import { getLinkPresentation } from '~/utils/stream-field'

const props = defineProps<{
  link: BakeryContentLink
}>()

const presentation = computed(() => getLinkPresentation(props.link))
</script>

<template>
  <NuxtLink
    v-if="presentation.kind === 'internal'"
    :to="presentation.to"
    class="content-link"
  >
    {{ presentation.label }}
  </NuxtLink>

  <a
    v-else-if="presentation.kind === 'external'"
    :href="presentation.href"
    :target="presentation.newTab ? '_blank' : undefined"
    rel="noopener noreferrer"
    class="content-link"
  >
    {{ presentation.label }}
  </a>

  <span v-else class="content-link content-link--disabled" aria-disabled="true">
    {{ presentation.label }}
    <small>{{ presentation.status }}</small>
  </span>
</template>
