import { fetchJson } from './client';
import { AuditLog } from '../types';

export interface GetAuditLogsResponse {
  total: number;
  items: AuditLog[];
}

export async function getAuditLogs(
  orgId: string,
  action?: string,
  outcome?: string,
  offset = 0,
  limit = 100
): Promise<GetAuditLogsResponse> {
  const query = new URLSearchParams();
  if (action && action !== 'ALL') query.set('action', action);
  if (outcome && outcome !== 'ALL') query.set('outcome', outcome);
  query.set('offset', String(offset));
  query.set('limit', String(limit));

  return fetchJson<GetAuditLogsResponse>(`/organizations/${orgId}/audit-logs?${query.toString()}`);
}
