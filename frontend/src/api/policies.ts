import { fetchJson } from './client';
import { RetentionPolicy, LegalHold } from '../types';

export interface GetPoliciesResponse {
  policies: RetentionPolicy[];
  legal_holds: LegalHold[];
}

export async function getPolicies(orgId: string): Promise<GetPoliciesResponse> {
  return fetchJson<GetPoliciesResponse>(`/organizations/${orgId}/policies`);
}
