export type CertificateStatus = 'pending' | 'valid' | 'suspended' | 'revoked';

export type CertificateWorkflowStatus = 'none';

export interface CertificateRegistryRecord {
  certificateNumber: string;
  currentVersion: string;
  issuedOn: string;
  expiresOn: string;
  certificateStatus: CertificateStatus;
  workflowStatus: CertificateWorkflowStatus;
}

export interface CertificateListResponse {
  success: true;
  code: number;
  message: string;
  data: CertificateRegistryRecord[];
}
