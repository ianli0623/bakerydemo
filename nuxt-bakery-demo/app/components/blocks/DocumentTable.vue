<script setup lang="ts">
import type { BakeryDocumentTableBlock } from '#shared/types/bakery'
import { getDocumentRowAnchor } from '~/utils/stream-field'
import ContentLink from './ContentLink.vue'

defineProps<{
  value: BakeryDocumentTableBlock['value']
}>()

const { t } = useI18n()
</script>

<template>
  <section
    :id="value.anchor_id || undefined"
    class="content-section document-section"
  >
    <h2 v-if="value.heading" class="section-title">
      {{ value.heading }}
    </h2>

    <div class="document-table-wrap">
      <table class="document-table">
        <caption>{{ value.caption || value.heading }}</caption>
        <thead>
          <tr>
            <th scope="col">{{ t('documents.number') }}</th>
            <th scope="col">{{ t('documents.title') }}</th>
            <th scope="col">{{ t('documents.summary') }}</th>
            <th scope="col">{{ t('documents.status') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in value.rows"
            :key="`${row.number}-${row.title}-${index}`"
            :id="getDocumentRowAnchor(row.number)"
          >
            <td :data-label="t('documents.number')">{{ row.number }}</td>
            <th scope="row" :data-label="t('documents.title')">
              {{ row.title }}
            </th>
            <td :data-label="t('documents.summary')">{{ row.summary }}</td>
            <td :data-label="t('documents.status')">
              <ContentLink v-if="row.link" :link="row.link" />
              <span v-else class="document-status">
                {{ row.status || t('status.unavailable') }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
