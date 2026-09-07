import { fetchJson } from './client';
import { StorageObject } from '../types';

export interface GetObjectsResponse {
  total: number;
  items: StorageObject[];
}

export async function getStorageObjects(
  orgId: string,
  search?: string,
  storageClass?: string,
  offset = 0,
  limit = 50
): Promise<GetObjectsResponse> {
  const query = new URLSearchParams();
  if (search) query.set('search', search);
  if (storageClass && storageClass !== 'ALL') query.set('storage_class', storageClass);
  query.set('offset', String(offset));
  query.set('limit', String(limit));

  return fetchJson<GetObjectsResponse>(`/organizations/${orgId}/objects?${query.toString()}`);
}

export async function getObjectUsageProfile(objectId: string, orgId: string): Promise<any> {
  return fetchJson<any>(`/objects/${objectId}/usage-profile`, {}, orgId);
}
