import { fetchJson } from './client';
import { ExecutionResult, RollbackResult, MigrationEvent } from '../types';

export async function executeRecommendation(
  recommendationId: string,
  orgId: string
): Promise<ExecutionResult> {
  return fetchJson<ExecutionResult>(
    `/recommendations/${recommendationId}/execute`,
    {
      method: 'POST',
    },
    orgId
  );
}

export async function rollbackMigration(
  migrationId: string,
  reason: string,
  orgId: string
): Promise<RollbackResult> {
  return fetchJson<RollbackResult>(
    `/migrations/${migrationId}/rollback`,
    {
      method: 'POST',
      body: JSON.stringify({ reason }),
    },
    orgId
  );
}

export async function getMigrations(orgId: string): Promise<MigrationEvent[]> {
  return fetchJson<MigrationEvent[]>(`/organizations/${orgId}/migrations`);
}
