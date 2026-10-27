import type {
  CertificateRegistryRecord,
  CertificateStatus,
} from '../../shared/types/esign.ts';

export interface ComplianceRegistryFilters {
  query: string;
  certificateStatus: CertificateStatus | '';
}

export function filterComplianceRegistryRecords(
  records: CertificateRegistryRecord[],
  filters: ComplianceRegistryFilters,
): CertificateRegistryRecord[] {
  const query = filters.query.trim().toLocaleLowerCase();

  return records.filter(
    (record) =>
      (!query ||
        record.certificateNumber.toLocaleLowerCase().includes(query)) &&
      (!filters.certificateStatus ||
        record.certificateStatus === filters.certificateStatus),
  );
}
