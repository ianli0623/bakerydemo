import type { CertificateListResponse } from '#shared/types/esign';
import { defineEventHandler } from 'h3';
import { fetchESignCertificates } from '../../utils/esign-certificates.ts';

export default defineEventHandler(
  async (event): Promise<CertificateListResponse> =>
    fetchESignCertificates(event),
);
