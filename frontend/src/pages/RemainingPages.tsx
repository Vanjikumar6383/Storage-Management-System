import React, { useEffect, useState } from 'react';
import { useOrganization } from '../context/OrganizationContext';
import { getMigrations, rollbackMigration } from '../api/migrations';
import { getStorageObjects } from '../api/objects';
import { getEnvironments } from '../api/organizations';
import { getPolicies } from '../api/policies';
import { getAuditLogs } from '../api/audit';
import { MigrationEvent, StorageObject, Environment, RetentionPolicy, LegalHold, AuditLog } from '../types';
import { LoadingSpinner, ErrorState, EmptyState } from '../components/Common';
import { RotateCcw, Search, ShieldAlert, FolderOpen } from 'lucide-react';
import { LinkLocalStorageModal } from '../components/LinkLocalStorageModal';

export const MigrationsPage: React.FC = () => {
  const { selectedOrg } = useOrganization();
  const [migrations, setMigrations] = useState<MigrationEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    if (!selectedOrg) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getMigrations(selectedOrg.id);
      setMigrations(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load migration history.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedOrg?.id]);

  const handleRollback = async (mig: MigrationEvent) => {
    if (!selectedOrg) return;
    const reason = prompt('Reason for rollback:', 'Operator requested rollback');
    if (!reason) return;
    try {
      await rollbackMigration(mig.id, reason, selectedOrg.id);
      await loadData();
    } catch (err: any) {
      alert(`Rollback failed: ${err.message}`);
    }
  };

  return (
    <div className="page-container space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Migration Log & Rollback Manager</h1>
          <p className="page-subtitle">Provider-side storage class tiering events with automated rollback lineage.</p>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Loading migration history..." />
      ) : error ? (
        <ErrorState message={error} onRetry={loadData} />
      ) : migrations.length === 0 ? (
        <EmptyState title="No Migrations Recorded" message="No storage tier migrations have been executed yet." />
      ) : (
        <div className="card p-0">
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Object</th>
                  <th>Source Class</th>
                  <th>Target Class</th>
                  <th>Status</th>
                  <th>Requested At</th>
                  <th>Rollback Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {migrations.map((mig) => {
                  const isSuccess = mig.status === 'SUCCESS';
                  const isRolledBack = mig.rollback_status === 'ROLLED_BACK';

                  return (
                    <tr key={mig.id}>
                      <td className="font-mono text-xs font-semibold">{mig.object_key}</td>
                      <td><span className="badge badge-neutral">{mig.source_storage_class}</span></td>
                      <td><span className="badge badge-primary">{mig.destination_storage_class}</span></td>
                      <td><span className={`badge ${isSuccess ? 'badge-success' : 'badge-danger'}`}>{mig.status}</span></td>
                      <td className="text-xs text-muted">{new Date(mig.requested_at).toLocaleString()}</td>
                      <td>
                        <span className={`badge ${isRolledBack ? 'badge-warning' : 'badge-neutral'}`}>
                          {mig.rollback_status}
                        </span>
                      </td>
                      <td>
                        {isSuccess && !isRolledBack ? (
                          <button className="btn btn-warning btn-sm" onClick={() => handleRollback(mig)}>
                            <RotateCcw className="btn-icon" /> Rollback
                          </button>
                        ) : (
                          <button className="btn btn-secondary btn-sm" disabled>
                            Disabled
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export const ObjectsPage: React.FC = () => {
  const { selectedOrg } = useOrganization();
  const [objects, setObjects] = useState<StorageObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [storageClass, setStorageClass] = useState('ALL');
  const [showLinkLocalModal, setShowLinkLocalModal] = useState(false);

  const loadData = async () => {
    if (!selectedOrg) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getStorageObjects(selectedOrg.id, search, storageClass);
      setObjects(res.items);
    } catch (err: any) {
      setError(err.message || 'Failed to load storage objects.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedOrg?.id, storageClass]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadData();
  };

  return (
    <div className="page-container space-y-6">
      <LinkLocalStorageModal
        isOpen={showLinkLocalModal}
        onClose={() => setShowLinkLocalModal(false)}
        onSuccess={loadData}
      />

      <div className="page-header flex-between">
        <div>
          <h1 className="page-title">Objects Explorer</h1>
          <p className="page-subtitle">Indexed object metadata inventory across tenant storage environments.</p>
        </div>
        <div>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setShowLinkLocalModal(true)}
          >
            <FolderOpen size={14} />
            <span>Link Local Storage</span>
          </button>
        </div>
      </div>

      <div className="card filter-bar flex-wrap gap-4">
        <form onSubmit={handleSearchSubmit} className="flex-align gap-2 flex-grow">
          <Search className="text-muted" size={18} />
          <input
            type="text"
            className="form-input"
            placeholder="Search object key..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit" className="btn btn-secondary">Search</button>
        </form>

        <div className="filter-group">
          <label className="label">Storage Class:</label>
          <select className="form-select" value={storageClass} onChange={(e) => setStorageClass(e.target.value)}>
            <option value="ALL">ALL CLASSES</option>
            <option value="STANDARD">STANDARD</option>
            <option value="INFREQUENT_ACCESS">INFREQUENT_ACCESS</option>
            <option value="ARCHIVE">ARCHIVE</option>
          </select>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Searching indexed storage objects..." />
      ) : error ? (
        <ErrorState message={error} onRetry={loadData} />
      ) : objects.length === 0 ? (
        <div className="card p-6 text-center space-y-3">
          <EmptyState title="No Objects Found" message={search ? "No storage objects matched your search filter." : "This organization has 0 storage objects. Link a local directory to index file metadata (zero content read) and run ML recommendations."} />
          {!search && (
            <div>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setShowLinkLocalModal(true)}
              >
                <FolderOpen size={14} />
                <span>Link Local Storage Folder</span>
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="card p-0">
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Object Key</th>
                  <th>Size</th>
                  <th>Age</th>
                  <th>Storage Class</th>
                  <th>Created At</th>
                  <th>Last Access</th>
                </tr>
              </thead>
              <tbody>
                {objects.map((o) => (
                  <tr key={o.id}>
                    <td className="font-mono text-xs font-semibold">{o.object_key}</td>
                    <td>{(o.object_size_bytes / (1024 * 1024)).toFixed(2)} MB</td>
                    <td>{o.age_days}d</td>
                    <td><span className="badge badge-neutral">{o.storage_class}</span></td>
                    <td className="text-xs text-muted">{new Date(o.created_at).toLocaleDateString()}</td>
                    <td className="text-xs text-muted">{o.last_accessed_at ? new Date(o.last_accessed_at).toLocaleDateString() : 'Never'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export const EnvironmentsPage: React.FC = () => {
  const { selectedOrg } = useOrganization();
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    if (!selectedOrg) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getEnvironments(selectedOrg.id);
      setEnvironments(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load environments.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedOrg?.id]);

  return (
    <div className="page-container space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Development & Production Environments</h1>
          <p className="page-subtitle">Storage inventory and cost allocation broken down by environment context.</p>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Loading environment storage breakdown..." />
      ) : error ? (
        <ErrorState message={error} onRetry={loadData} />
      ) : environments.length === 0 ? (
        <EmptyState title="No Environments Configured" message="No storage environments found for this organization." />
      ) : (
        <div className="grid-3">
          {environments.map((e) => {
            const sizeGb = (e.total_size_bytes / (1024 * 1024 * 1024)).toFixed(2);
            return (
              <div key={e.id} className="card env-card">
                <div className="flex-between mb-3">
                  <span className="badge badge-primary font-bold">{e.environment_type}</span>
                  <span className="text-sm font-semibold">{e.name}</span>
                </div>
                <div className="text-2xl font-bold">{sizeGb} GB</div>
                <div className="text-sm text-muted mt-1">{e.object_count.toLocaleString()} objects</div>
                <div className="mt-4 pt-3 border-top flex-between">
                  <span className="text-xs text-muted">Est. Monthly Cost:</span>
                  <span className="font-semibold text-primary">${e.estimated_monthly_cost_usd.toFixed(2)}/mo</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export const PoliciesPage: React.FC = () => {
  const { selectedOrg } = useOrganization();
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [legalHolds, setLegalHolds] = useState<LegalHold[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    if (!selectedOrg) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getPolicies(selectedOrg.id);
      setPolicies(res.policies);
      setLegalHolds(res.legal_holds);
    } catch (err: any) {
      setError(err.message || 'Failed to load policy engine records.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedOrg?.id]);

  return (
    <div className="page-container space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Retention Policies & Legal Holds</h1>
          <p className="page-subtitle">Governance governance boundary enforcing retention durations and absolute legal hold overrides.</p>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Loading policy and compliance data..." />
      ) : error ? (
        <ErrorState message={error} onRetry={loadData} />
      ) : (
        <div className="space-y-6">
          {/* LEGAL HOLDS SECTION */}
          <section className="card border-danger">
            <div className="flex-between mb-4">
              <div className="flex-align gap-2">
                <ShieldAlert className="text-danger" />
                <h3 className="card-title">Active Legal Holds ({legalHolds.length})</h3>
              </div>
              <span className="badge badge-danger">Absolute Override Active</span>
            </div>

            {legalHolds.length === 0 ? (
              <p className="text-muted text-sm">No active legal holds recorded.</p>
            ) : (
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Object Key</th>
                      <th>Status</th>
                      <th>Reason Reference</th>
                      <th>Created At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {legalHolds.map((h) => (
                      <tr key={h.id}>
                        <td className="font-mono text-xs font-semibold">{h.object_key}</td>
                        <td><span className="badge badge-danger">{h.status}</span></td>
                        <td><span className="font-semibold text-xs">{h.reason_reference}</span></td>
                        <td className="text-xs text-muted">{new Date(h.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* RETENTION POLICIES SECTION */}
          <section className="card">
            <h3 className="card-title mb-4">Configured Retention Policies ({policies.length})</h3>
            {policies.length === 0 ? (
              <p className="text-muted text-sm">No retention policies active.</p>
            ) : (
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Policy Name</th>
                      <th>Scope</th>
                      <th>Retention Duration</th>
                      <th>Priority</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {policies.map((p) => (
                      <tr key={p.id}>
                        <td className="font-semibold">{p.name}</td>
                        <td><span className="badge badge-neutral">{p.scope}</span></td>
                        <td>{p.retention_duration_days} days</td>
                        <td>Priority {p.priority}</td>
                        <td><span className="badge badge-success">{p.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
};

export const AuditLogPage: React.FC = () => {
  const { selectedOrg } = useOrganization();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    if (!selectedOrg) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getAuditLogs(selectedOrg.id);
      setLogs(res.items);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit logs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedOrg?.id]);

  return (
    <div className="page-container space-y-6">
      <div className="page-header">
        <div>
          <h1 className="page-title">Governance Audit Log</h1>
          <p className="page-subtitle">Immutable audit trail of all approval decisions, safety gate checks, and lifecycle executions.</p>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner message="Loading audit logs..." />
      ) : error ? (
        <ErrorState message={error} onRetry={loadData} />
      ) : logs.length === 0 ? (
        <EmptyState title="No Audit Records" message="No governance events logged." />
      ) : (
        <div className="card p-0">
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>Outcome</th>
                  <th>Metadata</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id}>
                    <td className="text-xs text-muted">{new Date(l.timestamp).toLocaleString()}</td>
                    <td className="font-semibold text-sm">{l.action}</td>
                    <td className="font-mono text-xs">{l.resource_type} ({l.resource_id.slice(0, 8)}...)</td>
                    <td>
                      <span className={`badge ${l.outcome === 'SUCCESS' || l.outcome === 'APPROVED' ? 'badge-success' : 'badge-neutral'}`}>
                        {l.outcome}
                      </span>
                    </td>
                    <td className="font-mono text-xs text-muted">
                      {JSON.stringify(l.metadata || {})}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
