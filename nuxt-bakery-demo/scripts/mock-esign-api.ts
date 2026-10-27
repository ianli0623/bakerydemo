import { createServer, type Server } from 'node:http';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const MOCK_ESIGN_HOST = '127.0.0.1';
export const MOCK_ESIGN_PORT = 8011;
export const DEFAULT_MOCK_ESIGN_API_KEY = 'local-esign-test-key';

export type MockScenario = 'success' | 'empty' | 'error' | 'malformed' | 'slow';

export interface MockESignRequest {
  method: string;
  pathname: string;
  apiKey: string | string[] | undefined;
  expectedApiKey: string;
  scenario: MockScenario;
}

export interface MockESignResponse {
  statusCode: number;
  body: unknown;
  delayMs: number;
}

export interface MockServerOptions {
  apiKey?: string;
  port?: number;
  scenario?: MockScenario;
}

const successData = [
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
];

const scenarios = new Set<MockScenario>([
  'success',
  'empty',
  'error',
  'malformed',
  'slow',
]);

function response(statusCode: number, body: unknown, delayMs = 0) {
  return { statusCode, body, delayMs };
}

function successBody(data: unknown = successData) {
  return {
    success: true,
    code: 200,
    message: 'OK',
    data,
  };
}

export function parseMockScenario(value: string | undefined): MockScenario {
  const normalized = value?.trim() || 'success';
  if (!scenarios.has(normalized as MockScenario)) {
    throw new Error(`ESIGN_MOCK_SCENARIO 不支援「${normalized}」。`);
  }

  return normalized as MockScenario;
}

export function resolveMockESignResponse(
  request: MockESignRequest,
): MockESignResponse {
  if (
    request.method !== 'GET' ||
    request.pathname !== '/api/v1/external/certificates'
  ) {
    return response(404, {
      success: false,
      code: 404,
      message: 'Not Found',
      data: [],
    });
  }

  if (
    typeof request.apiKey !== 'string' ||
    request.apiKey !== request.expectedApiKey
  ) {
    return response(401, {
      success: false,
      code: 401,
      message: 'Unauthorized',
      data: [],
    });
  }

  if (request.scenario === 'empty') {
    return response(200, successBody([]));
  }

  if (request.scenario === 'error') {
    return response(500, {
      success: false,
      code: 500,
      message: 'Mock service error',
      data: [],
    });
  }

  if (request.scenario === 'malformed') {
    return response(200, successBody('malformed'));
  }

  return response(200, successBody(), request.scenario === 'slow' ? 11_000 : 0);
}

export function startMockESignServer(
  options: MockServerOptions = {},
): Promise<Server> {
  const expectedApiKey = options.apiKey ?? DEFAULT_MOCK_ESIGN_API_KEY;
  const scenario = options.scenario ?? 'success';
  const port = options.port ?? MOCK_ESIGN_PORT;
  const server = createServer((request, serverResponse) => {
    const url = new URL(request.url ?? '/', 'http://127.0.0.1');
    const mockResponse = resolveMockESignResponse({
      method: request.method ?? '',
      pathname: url.pathname,
      apiKey: request.headers['x-api-key'],
      expectedApiKey,
      scenario,
    });
    const send = () => {
      serverResponse.statusCode = mockResponse.statusCode;
      serverResponse.setHeader(
        'Content-Type',
        'application/json; charset=utf-8',
      );
      serverResponse.end(JSON.stringify(mockResponse.body));
    };

    if (mockResponse.delayMs > 0) {
      setTimeout(send, mockResponse.delayMs);
    } else {
      send();
    }
  });

  return new Promise((resolveServer, reject) => {
    server.once('error', reject);
    server.listen(port, MOCK_ESIGN_HOST, () => {
      server.off('error', reject);
      resolveServer(server);
    });
  });
}

const isDirectExecution =
  process.argv[1] !== undefined &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (isDirectExecution) {
  const scenario = parseMockScenario(process.env.ESIGN_MOCK_SCENARIO);
  const apiKey =
    process.env.ESIGN_MOCK_API_KEY?.trim() || DEFAULT_MOCK_ESIGN_API_KEY;

  startMockESignServer({ apiKey, scenario })
    .then((server) => {
      console.log(
        `電子證書 Mock API 已啟動：http://${MOCK_ESIGN_HOST}:${MOCK_ESIGN_PORT}（情境：${scenario}）`,
      );

      const shutdown = () => server.close();
      process.once('SIGINT', shutdown);
      process.once('SIGTERM', shutdown);
    })
    .catch((error: unknown) => {
      console.error(error instanceof Error ? error.message : String(error));
      process.exitCode = 1;
    });
}
