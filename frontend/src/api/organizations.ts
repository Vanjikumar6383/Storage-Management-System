import { fetchJson } from './client';
import {
  Organization,
  DashboardSummary,
  Environment,
  OrganizationRegistrationPayload,
  OrganizationRegistrationResult,
  OrganizationLoginPayload,
  OrganizationLoginResult,
  OrganizationServiceDetails,
} from '../types';

export async function getOrganizations(): Promise<Organization[]> {
  return fetchJson<Organization[]>('/organizations');
}

export async function getDashboardSummary(orgId: string): Promise<DashboardSummary> {
  return fetchJson<DashboardSummary>(`/organizations/${orgId}/dashboard-summary`);
}

export async function getEnvironments(orgId: string): Promise<Environment[]> {
  return fetchJson<Environment[]>(`/organizations/${orgId}/environments`);
}

export async function registerOrganization(
  payload: OrganizationRegistrationPayload
): Promise<OrganizationRegistrationResult> {
  return fetchJson<OrganizationRegistrationResult>('/organizations/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function loginOrganization(
  payload: OrganizationLoginPayload
): Promise<OrganizationLoginResult> {
  return fetchJson<OrganizationLoginResult>('/organizations/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getOrganizationServiceDetails(
  orgId: string
): Promise<OrganizationServiceDetails> {
  return fetchJson<OrganizationServiceDetails>(`/organizations/${orgId}/service-details`);
}

