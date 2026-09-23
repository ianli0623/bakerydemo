export type ComplianceCertificateStatus = 'notEffective';

export type ComplianceWorkflowStatus =
  | 'processing'
  | 'failed'
  | 'none'
  | 'pendingAssignment';

export interface ComplianceRegistryRecord {
  certificateNumber: string;
  currentVersion: string;
  issuedOn: string;
  expiresOn: string;
  certificateStatus: ComplianceCertificateStatus;
  workflowStatus: ComplianceWorkflowStatus;
}

export interface ComplianceRegistryFilters {
  query: string;
  certificateStatus: ComplianceCertificateStatus | '';
  workflowStatus: ComplianceWorkflowStatus | '';
}

const sampleRecords: Array<
  [
    certificateNumber: string,
    issuedOn: string,
    workflowStatus: ComplianceWorkflowStatus,
  ]
> = [
  ['5555', '2026/09/02', 'processing'],
  ['222ss', '2026/09/15', 'failed'],
  ['wwwww', '2026/09/09', 'failed'],
  ['2222444', '2026/09/10', 'failed'],
  ['2222222', '2026/09/08', 'none'],
  ['11111111', '2026/09/10', 'none'],
  ['sdfghj', '2026/09/08', 'failed'],
  ['2345678', '2026/09/09', 'failed'],
  ['qqqq', '2026/09/02', 'failed'],
  ['sssss', '2026/09/08', 'failed'],
  ['ddddd', '2026/09/02', 'failed'],
  ['8888222', '2026/09/08', 'failed'],
  ['8888', '2026/09/02', 'failed'],
  ['12345', '2026/09/20', 'failed'],
  ['77777', '2026/09/09', 'failed'],
  ['22223', '2026/09/16', 'failed'],
  ['789654', '2026/09/09', 'failed'],
  ['123456', '2026/09/16', 'pendingAssignment'],
];

export const complianceRegistryRecords: ComplianceRegistryRecord[] =
  sampleRecords.map(([certificateNumber, issuedOn, workflowStatus]) => ({
    certificateNumber,
    currentVersion: '-',
    issuedOn,
    expiresOn: '-',
    certificateStatus: 'notEffective',
    workflowStatus,
  }));

export function filterComplianceRegistryRecords(
  records: ComplianceRegistryRecord[],
  filters: ComplianceRegistryFilters,
): ComplianceRegistryRecord[] {
  const query = filters.query.trim().toLocaleLowerCase();

  return records.filter(
    (record) =>
      (!query ||
        record.certificateNumber.toLocaleLowerCase().includes(query)) &&
      (!filters.certificateStatus ||
        record.certificateStatus === filters.certificateStatus) &&
      (!filters.workflowStatus ||
        record.workflowStatus === filters.workflowStatus),
  );
}
