import assert from 'node:assert/strict';
import test from 'node:test';
import type { H3Event } from 'h3';
import {
  normalizeESignBaseUrl,
  toCertificateRegistryRecords,
  toESignErrorDetails,
} from '../server/utils/esign-certificates-core.ts';
import { fetchESignCertificates } from '../server/utils/esign-certificates.ts';

test('normalizeESignBaseUrl accepts HTTP origins and removes trailing slashes', () => {
  assert.equal(
    normalizeESignBaseUrl(' http://192.168.1.123:8011/// '),
    'http://192.168.1.123:8011',
  );
  assert.equal(
    normalizeESignBaseUrl('https://esign.example.com/root/'),
    'https://esign.example.com/root',
  );
});

test('normalizeESignBaseUrl rejects missing and non-HTTP values', () => {
  assert.throws(() => normalizeESignBaseUrl(''), /ESIGN_API_BASE_URL/);
  assert.throws(() => normalizeESignBaseUrl('file:///tmp/esign'), /HTTP/);
});

test('toCertificateRegistryRecords maps every supported certificate status', () => {
  const records = toCertificateRegistryRecords({
    success: true,
    code: 200,
    message: 'OK',
    data: [
      {
        certificateNo: 'pending-001',
        currentVersionNo: 'V1',
        status: 'PENDING',
        expiresAt: '2027-01-01',
      },
      {
        certificateNo: 'valid-001',
        currentVersionNo: 'V2',
        status: 'VALID',
        expiresAt: '2027-02-02',
      },
      {
        certificateNo: 'suspended-001',
        currentVersionNo: 'V3',
        status: 'SUSPENDED',
        expiresAt: '2027-03-03',
      },
      {
        certificateNo: 'revoked-001',
        currentVersionNo: 'V4',
        status: 'REVOKED',
        expiresAt: '2027-04-04',
      },
    ],
  });

  assert.deepEqual(records, [
    {
      certificateNumber: 'pending-001',
      currentVersion: 'V1',
      issuedOn: '-',
      expiresOn: '2027-01-01',
      certificateStatus: 'pending',
      workflowStatus: 'none',
    },
    {
      certificateNumber: 'valid-001',
      currentVersion: 'V2',
      issuedOn: '-',
      expiresOn: '2027-02-02',
      certificateStatus: 'valid',
      workflowStatus: 'none',
    },
    {
      certificateNumber: 'suspended-001',
      currentVersion: 'V3',
      issuedOn: '-',
      expiresOn: '2027-03-03',
      certificateStatus: 'suspended',
      workflowStatus: 'none',
    },
    {
      certificateNumber: 'revoked-001',
      currentVersion: 'V4',
      issuedOn: '-',
      expiresOn: '2027-04-04',
      certificateStatus: 'revoked',
      workflowStatus: 'none',
    },
  ]);
});

test('toCertificateRegistryRecords accepts an empty successful list', () => {
  assert.deepEqual(
    toCertificateRegistryRecords({
      success: true,
      code: 200,
      message: 'OK',
      data: [],
    }),
    [],
  );
});

test('toCertificateRegistryRecords rejects unsuccessful and malformed payloads', () => {
  assert.throws(
    () =>
      toCertificateRegistryRecords({
        success: false,
        code: 500,
        message: 'failed',
        data: [],
      }),
    /格式不正確/,
  );
  assert.throws(
    () =>
      toCertificateRegistryRecords({
        success: true,
        code: 500,
        message: 'unexpected status',
        data: [],
      }),
    /格式不正確/,
  );
  assert.throws(
    () =>
      toCertificateRegistryRecords({
        success: true,
        code: 200,
        message: 'OK',
        data: [
          {
            certificateNo: '',
            currentVersionNo: 'V1',
            status: 'VALID',
            expiresAt: '2027-01-01',
          },
        ],
      }),
    /格式不正確/,
  );
  assert.throws(
    () =>
      toCertificateRegistryRecords({
        success: true,
        code: 200,
        message: 'OK',
        data: [
          {
            certificateNo: 'unknown-001',
            currentVersionNo: 'V1',
            status: 'UNKNOWN',
            expiresAt: '2027-01-01',
          },
        ],
      }),
    /格式不正確/,
  );
});

test('toESignErrorDetails does not expose upstream error content', () => {
  assert.deepEqual(toESignErrorDetails(new Error('secret upstream detail')), {
    statusCode: 502,
    statusMessage: '目前無法連線到電子證書服務。',
  });
});

test('fetchESignCertificates sends the API key only in the upstream header', async () => {
  const result = await fetchESignCertificates({} as H3Event, {
    baseUrl: ' http://192.168.1.123:8011/ ',
    apiKey: 'customer-api-key',
    request: async (path, options) => {
      assert.equal(path, '/api/v1/external/certificates');
      assert.equal(options.baseURL, 'http://192.168.1.123:8011');
      assert.deepEqual(options.headers, {
        'X-API-Key': 'customer-api-key',
      });
      assert.equal(options.timeout, 10_000);
      return {
        success: true,
        code: 200,
        message: 'OK',
        data: [
          {
            certificateNo: 'CERT-001',
            currentVersionNo: 'V2',
            status: 'VALID',
            expiresAt: '2027-12-31',
          },
        ],
      };
    },
  });

  assert.deepEqual(result, {
    success: true,
    code: 200,
    message: 'OK',
    data: [
      {
        certificateNumber: 'CERT-001',
        currentVersion: 'V2',
        issuedOn: '-',
        expiresOn: '2027-12-31',
        certificateStatus: 'valid',
        workflowStatus: 'none',
      },
    ],
  });
});

test('fetchESignCertificates reports missing private configuration as 500', async () => {
  await assert.rejects(
    fetchESignCertificates({} as H3Event, {
      baseUrl: '',
      apiKey: 'customer-api-key',
      request: async () => ({}),
    }),
    (error: { statusCode?: number; message?: string }) =>
      error.statusCode === 500 &&
      Boolean(error.message?.includes('ESIGN_API_BASE_URL')),
  );

  await assert.rejects(
    fetchESignCertificates({} as H3Event, {
      baseUrl: 'http://192.168.1.123:8011',
      apiKey: '',
      request: async () => ({}),
    }),
    (error: { statusCode?: number; message?: string }) =>
      error.statusCode === 500 && Boolean(error.message?.includes('API Key')),
  );
});

test('fetchESignCertificates maps upstream and malformed responses to 502', async () => {
  await assert.rejects(
    fetchESignCertificates({} as H3Event, {
      baseUrl: 'http://192.168.1.123:8011',
      apiKey: 'customer-api-key',
      request: async () => {
        throw new Error('upstream includes sensitive diagnostics');
      },
    }),
    (error: { statusCode?: number; message?: string }) =>
      error.statusCode === 502 &&
      error.message === '目前無法連線到電子證書服務。',
  );

  await assert.rejects(
    fetchESignCertificates({} as H3Event, {
      baseUrl: 'http://192.168.1.123:8011',
      apiKey: 'customer-api-key',
      request: async () => ({ success: true, data: 'not-an-array' }),
    }),
    (error: { statusCode?: number; message?: string }) =>
      error.statusCode === 502 &&
      error.message === '目前無法連線到電子證書服務。',
  );
});
