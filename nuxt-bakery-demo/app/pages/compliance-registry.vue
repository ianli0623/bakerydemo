<script setup lang="ts">
import type {
  CertificateListResponse,
  CertificateRegistryRecord,
  CertificateStatus,
} from '#shared/types/esign';
import type { ComplianceRegistryFilters } from '~/utils/compliance-registry';
import { filterComplianceRegistryRecords } from '~/utils/compliance-registry';

const { t } = useI18n();

const queryInput = ref('');
const certificateStatusInput = ref<CertificateStatus | ''>('');
const filters = ref<ComplianceRegistryFilters>({
  query: '',
  certificateStatus: '',
});
const selectedRecord = ref<CertificateRegistryRecord | null>(null);
const detailPanel = ref<HTMLElement | null>(null);
const {
  data: certificateResponse,
  status: certificateLoadStatus,
  error: certificateLoadError,
  refresh: refreshCertificates,
} = await useFetch<CertificateListResponse>('/api/esign/certificates');

const certificateRecords = computed(
  () => certificateResponse.value?.data ?? [],
);

const filteredRecords = computed(() =>
  filterComplianceRegistryRecords(certificateRecords.value, filters.value),
);

const loadErrorMessage = computed(() =>
  certificateLoadError.value?.statusCode === 500
    ? t('complianceRegistry.configurationError')
    : t('complianceRegistry.serviceUnavailable'),
);

function applyFilters() {
  filters.value = {
    query: queryInput.value,
    certificateStatus: certificateStatusInput.value,
  };
  selectedRecord.value = null;
}

function resetFilters() {
  queryInput.value = '';
  certificateStatusInput.value = '';
  filters.value = {
    query: '',
    certificateStatus: '',
  };
  selectedRecord.value = null;
}

async function retryLoad() {
  selectedRecord.value = null;
  await refreshCertificates();
}

async function showDetails(record: CertificateRegistryRecord) {
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
          <option value="pending">
            {{ t('complianceRegistry.certificateStatuses.pending') }}
          </option>
          <option value="valid">
            {{ t('complianceRegistry.certificateStatuses.valid') }}
          </option>
          <option value="suspended">
            {{ t('complianceRegistry.certificateStatuses.suspended') }}
          </option>
          <option value="revoked">
            {{ t('complianceRegistry.certificateStatuses.revoked') }}
          </option>
        </select>
      </div>

      <div class="registry-filter">
        <label for="registry-workflow-status">
          {{ t('complianceRegistry.workflowStatusLabel') }}
        </label>
        <select id="registry-workflow-status" disabled>
          <option value="">{{ t('complianceRegistry.allStatuses') }}</option>
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

    <div
      v-if="certificateLoadStatus === 'pending'"
      class="state-panel"
      role="status"
      aria-live="polite"
    >
      <div>
        <strong>{{ t('complianceRegistry.loading') }}</strong>
      </div>
    </div>

    <div
      v-else-if="certificateLoadError"
      class="state-panel state-error"
      role="alert"
    >
      <div>
        <strong>{{ t('complianceRegistry.loadError') }}</strong>
        <p>{{ loadErrorMessage }}</p>
      </div>
      <button class="button button-secondary" type="button" @click="retryLoad">
        {{ t('status.retry') }}
      </button>
    </div>

    <p v-else class="registry-result-count" role="status" aria-live="polite">
      {{
        t('complianceRegistry.results', {
          count: filteredRecords.length,
        })
      }}
    </p>

    <div
      v-if="
        certificateLoadStatus !== 'pending' &&
        !certificateLoadError &&
        filteredRecords.length
      "
      class="registry-table-wrap"
    >
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
              <span
                class="registry-status registry-status--certificate"
                :class="`registry-status--${record.certificateStatus}`"
              >
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

    <p
      v-else-if="certificateLoadStatus !== 'pending' && !certificateLoadError"
      class="registry-empty"
      role="status"
    >
      {{ t('complianceRegistry.noResults') }}
    </p>

    <section
      v-if="
        selectedRecord &&
        certificateLoadStatus !== 'pending' &&
        !certificateLoadError
      "
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
