export function isValidStandardPageSlug(value: unknown): value is string {
  return typeof value === 'string' && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value);
}

export function isMissingBakeryPageError(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const error = value as { statusCode?: number; status?: number };
  const status = error.statusCode ?? error.status;
  return status === 400 || status === 404;
}
