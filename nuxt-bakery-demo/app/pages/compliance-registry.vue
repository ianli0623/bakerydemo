<script setup lang="ts">
import type {
  ComplianceCertificateStatus,
  ComplianceRegistryFilters,
  ComplianceRegistryRecord,
  ComplianceWorkflowStatus,
} from '~/utils/compliance-registry';
import {
  complianceRegistryRecords,
  filterComplianceRegistryRecords,
} from '~/utils/compliance-registry';

const { t } = useI18n();

const queryInput = ref('');
const certificateStatusInput = ref<ComplianceCertificateStatus | ''>('');
const workflowStatusInput = ref<ComplianceWorkflowStatus | ''>('');
const filters = ref<ComplianceRegistryFilters>({
  query: '',
  certificateStatus: '',
  workflowStatus: '',
});
const selectedRecord = ref<ComplianceRegistryRecord | null>(null);
const detailPanel = ref<HTMLElement | null>(null);

const filteredRecords = computed(() =>
  filterComplianceRegistryRecords(complianceRegistryRecords, filters.value),
);

function applyFilters() {
  filters.value = {
    query: queryInput.value,
    certificateStatus: certificateStatusInput.value,
    workflowStatus: workflowStatusInput.value,
  };
  selectedRecord.value = null;
}

function resetFilters() {
  queryInput.value = '';
  certificateStatusInput.value = '';
  workflowStatusInput.value = '';
  filters.value = {
    query: '',
    certificateStatus: '',
    workflowStatus: '',
  };
  selectedRecord.value = null;
}

async function showDetails(record: ComplianceRegistryRecord) {
  selectedRecord.value = record;
  await nextTick();
  detailPanel.value?.focus();
}

useSeoMeta({
  title: () => t('complianceRegistry.title'),
  description: () => t('complianceRegistry.introduction'),
});
</script>

<template>
  <main id="main-content" class="page-container registry-page">
    <header class="registry-hero">
      <p class="section-kicker">SEMI E187 COMPLIANCE</p>
      <h1>{{ t('complianceRegistry.title') }}</h1>
      <p>{{ t('complianceRegistry.introduction') }}</p>
    </header>

    <form class="registry-filters" @submit.prevent="applyFilters">
      <div class="registry-filter registry-filter--search">
        <label for="registry-query">
          {{ t('complianceRegistry.searchLabel') }}
        </label>
        <input
          id="registry-query"
          v-model="queryInput"
          type="search"
          :placeholder="t('complianceRegistry.searchPlaceholder')"
          autocomplete="off"
        />
      </div>

      <div class="registry-filter">
        <label for="registry-certificate-status">
          {{ t('complianceRegistry.certificateStatusLabel') }}
        </label>
        <select
          id="registry-certificate-status"
          v-model="certificateStatusInput"
        >
          <option value="">{{ t('complianceRegistry.allStatuses') }}</option>
          <option value="notEffective">
            {{ t('complianceRegistry.certificateStatuses.notEffective') }}
          </option>
        </select>
      </div>

      <div class="registry-filter">
        <label for="registry-workflow-status">
          {{ t('complianceRegistry.workflowStatusLabel') }}
        </label>
        <select id="registry-workflow-status" v-model="workflowStatusInput">
          <option value="">{{ t('complianceRegistry.allStatuses') }}</option>
          <option value="processing">
            {{ t('complianceRegistry.workflowStatuses.processing') }}
          </option>
          <option value="failed">
            {{ t('complianceRegistry.workflowStatuses.failed') }}
          </option>
          <option value="none">
            {{ t('complianceRegistry.workflowStatuses.none') }}
          </option>
          <option value="pendingAssignment">
            {{ t('complianceRegistry.workflowStatuses.pendingAssignment') }}
          </option>
        </select>
      </div>

      <div class="registry-filter-actions">
        <button class="button button-dark" type="submit">
          {{ t('complianceRegistry.query') }}
        </button>
        <button
          class="button button-secondary"
          type="button"
          @click="resetFilters"
        >
          {{ t('complianceRegistry.reset') }}
        </button>
      </div>
    </form>

    <p class="registry-result-count" role="status" aria-live="polite">
      {{
        t('complianceRegistry.results', {
          count: filteredRecords.length,
        })
      }}
    </p>

    <div v-if="filteredRecords.length" class="registry-table-wrap">
      <table class="registry-table">
        <caption>
          {{
            t('complianceRegistry.tableCaption')
          }}
        </caption>
        <thead>
          <tr>
            <th scope="col">{{ t('complianceRegistry.columns.number') }}</th>
            <th scope="col">{{ t('complianceRegistry.columns.version') }}</th>
            <th scope="col">{{ t('complianceRegistry.columns.issuedOn') }}</th>
            <th scope="col">{{ t('complianceRegistry.columns.expiresOn') }}</th>
            <th scope="col">
              {{ t('complianceRegistry.columns.certificateStatus') }}
            </th>
            <th scope="col">
              {{ t('complianceRegistry.columns.workflowStatus') }}
            </th>
            <th scope="col">{{ t('complianceRegistry.columns.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="record in filteredRecords" :key="record.certificateNumber">
            <th
              scope="row"
              :data-label="t('complianceRegistry.columns.number')"
            >
              {{ record.certificateNumber }}
            </th>
            <td :data-label="t('complianceRegistry.columns.version')">
              {{ record.currentVersion }}
            </td>
            <td :data-label="t('complianceRegistry.columns.issuedOn')">
              {{ record.issuedOn }}
            </td>
            <td :data-label="t('complianceRegistry.columns.expiresOn')">
              {{ record.expiresOn }}
            </td>
            <td :data-label="t('complianceRegistry.columns.certificateStatus')">
              <span class="registry-status registry-status--certificate">
                {{
                  t(
                    `complianceRegistry.certificateStatuses.${record.certificateStatus}`,
                  )
                }}
              </span>
            </td>
            <td :data-label="t('complianceRegistry.columns.workflowStatus')">
              <span
                class="registry-status"
                :class="`registry-status--${record.workflowStatus}`"
              >
                {{
                  t(
                    `complianceRegistry.workflowStatuses.${record.workflowStatus}`,
                  )
                }}
              </span>
            </td>
            <td :data-label="t('complianceRegistry.columns.actions')">
              <button
                class="registry-view-button"
                type="button"
                aria-controls="registry-record-detail"
                :aria-expanded="
                  selectedRecord?.certificateNumber === record.certificateNumber
                "
                @click="showDetails(record)"
              >
                {{ t('complianceRegistry.view') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else class="registry-empty" role="status">
      {{ t('complianceRegistry.noResults') }}
    </p>

    <section
      v-if="selectedRecord"
      id="registry-record-detail"
      ref="detailPanel"
      class="registry-detail"
      tabindex="-1"
      :aria-labelledby="`registry-detail-${selectedRecord.certificateNumber}`"
    >
      <div class="registry-detail__header">
        <div>
          <p class="section-kicker">
            {{ t('complianceRegistry.detailEyebrow') }}
          </p>
          <h2 :id="`registry-detail-${selectedRecord.certificateNumber}`">
            {{ selectedRecord.certificateNumber }}
          </h2>
        </div>
        <button
          class="registry-view-button"
          type="button"
          @click="selectedRecord = null"
        >
          {{ t('complianceRegistry.close') }}
        </button>
      </div>
      <dl class="registry-detail__grid">
        <div>
          <dt>{{ t('complianceRegistry.columns.version') }}</dt>
          <dd>{{ selectedRecord.currentVersion }}</dd>
        </div>
        <div>
          <dt>{{ t('complianceRegistry.columns.issuedOn') }}</dt>
          <dd>{{ selectedRecord.issuedOn }}</dd>
        </div>
        <div>
          <dt>{{ t('complianceRegistry.columns.expiresOn') }}</dt>
          <dd>{{ selectedRecord.expiresOn }}</dd>
        </div>
        <div>
          <dt>{{ t('complianceRegistry.columns.certificateStatus') }}</dt>
          <dd>
            {{
              t(
                `complianceRegistry.certificateStatuses.${selectedRecord.certificateStatus}`,
              )
            }}
          </dd>
        </div>
        <div>
          <dt>{{ t('complianceRegistry.columns.workflowStatus') }}</dt>
          <dd>
            {{
              t(
                `complianceRegistry.workflowStatuses.${selectedRecord.workflowStatus}`,
              )
            }}
          </dd>
        </div>
      </dl>
    </section>
  </main>
</template>
