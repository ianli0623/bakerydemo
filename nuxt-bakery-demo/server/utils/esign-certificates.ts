import type { H3Event } from 'h3';
import { createError } from 'h3';
import { ofetch } from 'ofetch';
import type { CertificateListResponse } from '../../shared/types/esign.ts';
import {
  normalizeESignBaseUrl,
  toCertificateRegistryRecords,
  toESignErrorDetails,
} from './esign-certificates-core.ts';

interface ESignRequestOptions {
  baseURL: string;
  headers: Record<string, string>;
  timeout: number;
}

const ESIGN_REQUEST_TIMEOUT_MS = 10_000;

type ESignRequest = (
  path: string,
  options: ESignRequestOptions,
) => Promise<unknown>;

export interface ESignDependencies {
  baseUrl: string;
  apiKey: string;
  request: ESignRequest;
}

export async function fetchESignCertificates(
  event: H3Event,
  dependencies?: ESignDependencies,
): Promise<CertificateListResponse> {
  const config = dependencies ? null : useRuntimeConfig(event);
  const configuredBaseUrl =
    dependencies?.baseUrl ?? config?.esignApiBaseUrl ?? '';
  const apiKey = (dependencies?.apiKey ?? config?.esignApiKey ?? '').trim();

  let baseURL: string;
  try {
    baseURL = normalizeESignBaseUrl(configuredBaseUrl);
  } catch (error) {
    throw createError({
      statusCode: 500,
      message:
        error instanceof Error ? error.message : '電子證書 API 設定錯誤。',
    });
  }

  if (!apiKey) {
    throw createError({
      statusCode: 500,
      message: '尚未設定電子證書 API Key。',
    });
  }

  const request = dependencies?.request ?? (ofetch as ESignRequest);

  try {
    const payload = await request('/api/v1/external/certificates', {
      baseURL,
      headers: {
        'X-API-Key': apiKey,
      },
      timeout: ESIGN_REQUEST_TIMEOUT_MS,
    });

    return {
      success: true,
      code: 200,
      message: 'OK',
      data: toCertificateRegistryRecords(payload),
    };
  } catch (error) {
    const details = toESignErrorDetails(error);
    throw createError({
      statusCode: details.statusCode,
      message: details.statusMessage,
    });
  }
}
