import type {
  CertificateRegistryRecord,
  CertificateStatus,
} from '../../shared/types/esign.ts';

const statusMap: Record<string, CertificateStatus> = {
  PENDING: 'pending',
  VALID: 'valid',
  SUSPENDED: 'suspended',
  REVOKED: 'revoked',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isDateString(value: unknown): value is string {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function invalidPayload(): Error {
  return new Error('電子證書 API 回傳格式不正確。');
}

export function normalizeESignBaseUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error('尚未設定 ESIGN_API_BASE_URL。');
  }

  const url = new URL(trimmed);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error('電子證書 API Base URL 必須使用 HTTP 或 HTTPS。');
  }

  return url.toString().replace(/\/+$/, '');
}

export function toCertificateRegistryRecords(
  payload: unknown,
): CertificateRegistryRecord[] {
  if (
    !isRecord(payload) ||
    payload.success !== true ||
    payload.code !== 200 ||
    typeof payload.message !== 'string' ||
    !Array.isArray(payload.data)
  ) {
    throw invalidPayload();
  }

  return payload.data.map((item) => {
    if (!isRecord(item)) {
      throw invalidPayload();
    }

    const status =
      typeof item.status === 'string' ? statusMap[item.status] : undefined;
    if (
      !isNonEmptyString(item.certificateNo) ||
      !isNonEmptyString(item.currentVersionNo) ||
      !status ||
      !isDateString(item.expiresAt)
    ) {
      throw invalidPayload();
    }

    return {
      certificateNumber: item.certificateNo,
      currentVersion: item.currentVersionNo,
      issuedOn: '-',
      expiresOn: item.expiresAt,
      certificateStatus: status,
      workflowStatus: 'none',
    };
  });
}

export interface ESignErrorDetails {
  statusCode: number;
  statusMessage: string;
}

export function toESignErrorDetails(_error: unknown): ESignErrorDetails {
  return {
    statusCode: 502,
    statusMessage: '目前無法連線到電子證書服務。',
  };
}
