import type { H3Event } from 'h3';
import { createError } from 'h3';
import { ofetch } from 'ofetch';
import {
  normalizeBaseUrl,
  resolvePayloadMediaUrls,
  toBakeryErrorDetails,
} from './bakery-core.ts';

interface BakeryRequestOptions {
  baseURL: string;
  query?: Record<string, string>;
}

type BakeryRequest = (
  path: string,
  options: BakeryRequestOptions,
) => Promise<unknown>;

export interface BakeryDependencies {
  baseUrl: string;
  request: BakeryRequest;
}

export async function fetchBakery<T>(
  event: H3Event,
  path: string,
  query?: Record<string, string>,
  dependencies?: BakeryDependencies,
): Promise<T> {
  const config = dependencies ? null : useRuntimeConfig(event);
  const configuredBaseUrl =
    dependencies?.baseUrl ?? config?.bakeryBaseUrl ?? '';

  let baseURL: string;
  try {
    baseURL = normalizeBaseUrl(configuredBaseUrl);
  } catch (error) {
    throw createError({
      statusCode: 500,
      message: error instanceof Error ? error.message : 'Bakery 設定錯誤。',
    });
  }

  const request = dependencies?.request ?? (ofetch as BakeryRequest);

  try {
    const response = await request(path, { baseURL, query });
    return resolvePayloadMediaUrls(response, baseURL) as T;
  } catch (error) {
    const details = toBakeryErrorDetails(error);
    throw createError({
      statusCode: details.statusCode,
      message: details.statusMessage,
    });
  }
}
