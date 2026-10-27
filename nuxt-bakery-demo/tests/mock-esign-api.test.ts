import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  DEFAULT_MOCK_ESIGN_API_KEY,
  MOCK_ESIGN_HOST,
  MOCK_ESIGN_PORT,
  parseMockScenario,
  resolveMockESignResponse,
} from '../scripts/mock-esign-api.ts';

const authorizedRequest = {
  method: 'GET',
  pathname: '/api/v1/external/certificates',
  apiKey: DEFAULT_MOCK_ESIGN_API_KEY,
  expectedApiKey: DEFAULT_MOCK_ESIGN_API_KEY,
  scenario: 'success' as const,
};

test('mock server is restricted to the loopback host and documented port', () => {
  assert.equal(MOCK_ESIGN_HOST, '127.0.0.1');
  assert.equal(MOCK_ESIGN_PORT, 8011);
  assert.equal(DEFAULT_MOCK_ESIGN_API_KEY, 'local-esign-test-key');
});

test('success response matches the external certificate contract and all statuses', () => {
  const response = resolveMockESignResponse(authorizedRequest);

  assert.equal(response.statusCode, 200);
  assert.equal(response.delayMs, 0);
  assert.deepEqual(response.body, {
    success: true,
    code: 200,
    message: 'OK',
    data: [
      {
        certificateNo: 'LOCAL-PENDING-001',
        currentVersionNo: 'V1',
        status: 'PENDING',
        expiresAt: '2027-01-31',
      },
      {
        certificateNo: 'LOCAL-VALID-001',
        currentVersionNo: 'V2',
        status: 'VALID',
        expiresAt: '2027-02-28',
      },
      {
        certificateNo: 'LOCAL-SUSPENDED-001',
        currentVersionNo: 'V3',
        status: 'SUSPENDED',
        expiresAt: '2027-03-31',
      },
      {
        certificateNo: 'LOCAL-REVOKED-001',
        currentVersionNo: 'V4',
        status: 'REVOKED',
        expiresAt: '2027-04-30',
      },
    ],
  });
});

test('missing or incorrect API keys return 401 without echoing credentials', () => {
  for (const apiKey of [undefined, 'wrong-secret-value']) {
    const response = resolveMockESignResponse({
      ...authorizedRequest,
      apiKey,
    });

    assert.equal(response.statusCode, 401);
    assert.deepEqual(response.body, {
      success: false,
      code: 401,
      message: 'Unauthorized',
      data: [],
    });
    assert.doesNotMatch(JSON.stringify(response.body), /wrong-secret-value/);
  }
});

test('unsupported methods and paths return 404', () => {
  for (const request of [
    { ...authorizedRequest, method: 'POST' },
    { ...authorizedRequest, pathname: '/api/v1/external/unknown' },
  ]) {
    const response = resolveMockESignResponse(request);

    assert.equal(response.statusCode, 404);
    assert.deepEqual(response.body, {
      success: false,
      code: 404,
      message: 'Not Found',
      data: [],
    });
  }
});

test('empty, error, malformed, and slow scenarios are deterministic', () => {
  const empty = resolveMockESignResponse({
    ...authorizedRequest,
    scenario: 'empty',
  });
  assert.equal(empty.statusCode, 200);
  assert.deepEqual(empty.body, {
    success: true,
    code: 200,
    message: 'OK',
    data: [],
  });

  const error = resolveMockESignResponse({
    ...authorizedRequest,
    scenario: 'error',
  });
  assert.equal(error.statusCode, 500);
  assert.deepEqual(error.body, {
    success: false,
    code: 500,
    message: 'Mock service error',
    data: [],
  });

  const malformed = resolveMockESignResponse({
    ...authorizedRequest,
    scenario: 'malformed',
  });
  assert.equal(malformed.statusCode, 200);
  assert.deepEqual(malformed.body, {
    success: true,
    code: 200,
    message: 'OK',
    data: 'malformed',
  });

  const slow = resolveMockESignResponse({
    ...authorizedRequest,
    scenario: 'slow',
  });
  assert.equal(slow.statusCode, 200);
  assert.equal(slow.delayMs, 11_000);
  assert.deepEqual(slow.body, resolveMockESignResponse(authorizedRequest).body);
});

test('unsupported scenarios are rejected with a clear error', () => {
  assert.equal(parseMockScenario(undefined), 'success');
  assert.equal(parseMockScenario('empty'), 'empty');
  assert.throws(
    () => parseMockScenario('sometimes'),
    /ESIGN_MOCK_SCENARIO.*sometimes/,
  );
});

test('local mock commands and environment use safe loopback settings', async () => {
  const [packageSource, environmentSource] = await Promise.all([
    readFile(new URL('../package.json', import.meta.url), 'utf8'),
    readFile(new URL('../.env.mock', import.meta.url), 'utf8'),
  ]);
  const packageJson = JSON.parse(packageSource) as {
    scripts?: Record<string, string>;
  };

  assert.equal(
    packageJson.scripts?.['mock:esign'],
    'node --experimental-strip-types scripts/mock-esign-api.ts',
  );
  assert.equal(
    packageJson.scripts?.['dev:mock'],
    'nuxt dev --dotenv .env.mock',
  );
  assert.deepEqual(environmentSource.trim().split(/\r?\n/), [
    'NUXT_BAKERY_BASE_URL=http://127.0.0.1:8000',
    'ESIGN_API_BASE_URL=http://127.0.0.1:8011',
    'ESIGN_API_KEY=local-esign-test-key',
  ]);
  assert.doesNotMatch(environmentSource, /192\.168\.1\.123|customer/i);
});

test('safe local mock environment is available to other checkouts', () => {
  const projectRoot = fileURLToPath(new URL('..', import.meta.url));
  const result = spawnSync('git', ['check-ignore', '--quiet', '.env.mock'], {
    cwd: projectRoot,
  });

  assert.equal(result.status, 1, '.env.mock must not be ignored by Git');
});
