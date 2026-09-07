import { fetchJson } from './client';
import { Recommendation } from '../types';

export interface GetRecommendationsResponse {
  total: number;
  items: Recommendation[];
}

export async function getRecommendations(
  orgId: string,
  typeFilter?: string,
  riskFilter?: string,
  statusFilter?: string,
  offset = 0,
  limit = 100
): Promise<GetRecommendationsResponse> {
  const query = new URLSearchParams();
  if (typeFilter && typeFilter !== 'ALL') query.set('recommendation_type', typeFilter);
  if (riskFilter && riskFilter !== 'ALL') query.set('risk_level', riskFilter);
  if (statusFilter && statusFilter !== 'ALL') query.set('status', statusFilter);
  query.set('offset', String(offset));
  query.set('limit', String(limit));

  return fetchJson<GetRecommendationsResponse>(`/organizations/${orgId}/recommendations?${query.toString()}`);
}

export async function runBatchRecommendations(orgId: string): Promise<any> {
  return fetchJson<any>(`/organizations/${orgId}/recommendations/run`, {
    method: 'POST',
  });
}
