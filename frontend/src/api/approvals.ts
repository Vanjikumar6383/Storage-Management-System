import { fetchJson } from './client';
import { ApprovalRequest } from '../types';

export async function submitApprovalDecision(
  recommendationId: string,
  decision: 'APPROVE' | 'REJECT',
  reason: string,
  orgId: string
): Promise<ApprovalRequest> {
  return fetchJson<ApprovalRequest>(
    `/recommendations/${recommendationId}/approval`,
    {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    },
    orgId
  );
}

export async function getApprovalStatus(
  recommendationId: string,
  orgId: string
): Promise<ApprovalRequest> {
  return fetchJson<ApprovalRequest>(
    `/recommendations/${recommendationId}/approval`,
    {},
    orgId
  );
}
