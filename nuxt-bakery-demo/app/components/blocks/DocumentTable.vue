<script setup lang="ts">
import type { BakeryDocumentTableBlock } from '#shared/types/bakery'
import { getDocumentRowAnchor } from '~/utils/stream-field'
import ContentLink from './ContentLink.vue'

defineProps<{
  value: BakeryDocumentTableBlock['value']
}>()
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
            <th scope="col">編號</th>
            <th scope="col">文件</th>
            <th scope="col">說明</th>
            <th scope="col">狀態／連結</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in value.rows"
            :key="`${row.number}-${row.title}-${index}`"
            :id="getDocumentRowAnchor(row.number)"
          >
            <td data-label="編號">{{ row.number }}</td>
            <th scope="row" data-label="文件">{{ row.title }}</th>
            <td data-label="說明">{{ row.summary }}</td>
            <td data-label="狀態／連結">
              <ContentLink v-if="row.link" :link="row.link" />
              <span v-else class="document-status">
                {{ row.status || '即將提供' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
