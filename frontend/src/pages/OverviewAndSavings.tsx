import React, { useEffect, useState } from 'react';
import { useOrganization } from '../context/OrganizationContext';
import { getDashboardSummary } from '../api/organizations';
import { fetchJson } from '../api/client';
import { DashboardSummary } from '../types';
import { LoadingSpinner, ErrorState, KPICard } from '../components/Common';
import { HardDrive, DollarSign, PiggyBank, CheckSquare, TrendingUp, BarChart2, AlertCircle, ShieldCheck, Activity, FolderOpen } from 'lucide-react';
import { LinkLocalStorageModal } from '../components/LinkLocalStorageModal';

export const OverviewPage: React.FC<{ onSelectRecommendation: (recId: string) => void }> = () => {
  const { selectedOrg } = useOrganization();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showLinkLocalModal, setShowLinkLocalModal] = useState(false);

  const loadData = async () => {
    if (!selectedOrg) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getDashboardSummary(selectedOrg.id);
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard overview data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedOrg?.id]);

  if (loading) return <LoadingSpinner message="Loading storage optimizer metrics..." />;
  if (error) return <ErrorState message={error} onRetry={loadData} />;
  if (!summary) return null;

  const storageGb = (summary.total_storage_bytes / (1024 * 1024 * 1024)).toFixed(2);
  const isAwsMode = summary.storage_provider === 'AWS_S3';

  return (
    <div className="page-container space-y-6">
      <LinkLocalStorageModal
        isOpen={showLinkLocalModal}
        onClose={() => setShowLinkLocalModal(false)}
        onSuccess={loadData}
      />

      <div className="page-header flex-between">
        <div>
          <h1 className="page-title">Storage Control Plane Overview</h1>
          <p className="page-subtitle">Multi-tenant storage inventory, cost analytics, and lifecycle opportunities.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setShowLinkLocalModal(true)}
          >
            <FolderOpen size={14} />
            <span>Link Local Storage</span>
          </button>
          <span className={`badge ${isAwsMode ? 'badge-primary' : 'badge-success'}`}>
            STORAGE: {summary.storage_mode_label || (isAwsMode ? 'AWS S3' : 'DEMO STORAGE')}
          </span>
          <span className="badge badge-warning">Demo Pricing — Not Provider Billing</span>
        </div>
      </div>

      {/* ZERO DATA ONBOARDING BANNER */}
      {summary.total_objects === 0 && (
        <div className="card p-6 border-dashed border-cyan-500/40 bg-cyan-950/20 text-center space-y-4">
          <div className="flex justify-center">
            <div className="w-14 h-14 rounded-full bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <FolderOpen size={28} />
            </div>
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Clean Slate: 0 Storage Objects Indexed</h3>
            <p className="text-sm text-slate-400 max-w-xl mx-auto mt-1">
              This organization is initialized with 0 data. Link your local storage folder to scan file metadata (filename, size, timestamps) and evaluate Machine Learning lifecycle recommendations.
            </p>
          </div>
          <div>
            <button
              className="btn btn-primary btn-glow"
              onClick={() => setShowLinkLocalModal(true)}
            >
              <FolderOpen size={16} />
              <span>Link Local Storage Folder</span>
            </button>
          </div>
        </div>
      )}

      {/* STORAGE MODE & SAFETY BANNER */}

      <div className={`p-4 rounded-lg border-l-4 ${isAwsMode ? 'border-blue-500 bg-blue-500/10' : 'border-emerald-500 bg-emerald-500/10'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-medium">
            <ShieldCheck className={isAwsMode ? 'text-blue-400' : 'text-emerald-400'} size={18} />
            <span>{summary.safety_banner_text || (isAwsMode ? 'Production Cloud Mode — lifecycle actions can modify real AWS S3 objects.' : 'Demo Storage Mode — lifecycle actions operate on demo storage only.')}</span>
          </div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            {summary.storage_mode_description || (isAwsMode ? 'Connected to configured AWS provider.' : 'Demo environment — no real cloud storage connected.')}
          </span>
        </div>
      </div>

      {/* TOP KPI CARDS */}
      <div className="grid-4">
        <KPICard
          title="TOTAL STORAGE"
          value={`${storageGb} GB`}
          subtext={`${summary.total_objects.toLocaleString()} indexed objects`}
          icon={<HardDrive className="text-primary" />}
        />
        <KPICard
          title="TOTAL OBJECTS"
          value={summary.total_objects.toLocaleString()}
          subtext="Active object metadata items"
          icon={<HardDrive className="text-info" />}
        />
        <KPICard
          title="ESTIMATED MONTHLY COST"
          value={`$${summary.estimated_monthly_cost_usd.toFixed(2)}`}
          subtext="Based on current storage classes"
          variant="primary"
          icon={<DollarSign className="text-primary" />}
        />
        <KPICard
          title="POTENTIAL MONTHLY SAVINGS"
          value={`$${summary.potential_monthly_savings_usd.toFixed(2)}`}
          subtext="Awaiting lifecycle optimization"
          variant="success"
          icon={<PiggyBank className="text-success" />}
        />
      </div>

      {/* SYSTEM HEALTH OBSERVABILITY AREA */}
      {summary.system_health && (
        <section className="card bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
          <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Activity className="text-emerald-400 w-4 h-4" /> System Health & Status
            </h3>
            <span className="text-xs text-slate-500 font-mono">Environment: {summary.system_health.environment || 'DEMO'}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div className="flex justify-between items-center bg-slate-800/40 p-2.5 rounded-lg">
              <span className="text-slate-400">Application</span>
              <span className="px-2 py-0.5 rounded font-bold bg-emerald-500/20 text-emerald-300">
                {summary.system_health.application || 'HEALTHY'}
              </span>
            </div>
            <div className="flex justify-between items-center bg-slate-800/40 p-2.5 rounded-lg">
              <span className="text-slate-400">PostgreSQL DB</span>
              <span className="px-2 py-0.5 rounded font-bold bg-emerald-500/20 text-emerald-300">
                {summary.system_health.database || 'HEALTHY'}
              </span>
            </div>
            <div className="flex justify-between items-center bg-slate-800/40 p-2.5 rounded-lg">
              <span className="text-slate-400">Storage Provider</span>
              <span className="px-2 py-0.5 rounded font-bold bg-blue-500/20 text-blue-300">
                {summary.system_health.storage_provider || (isAwsMode ? 'AWS S3' : 'DEMO')}
              </span>
            </div>
            <div className="flex justify-between items-center bg-slate-800/40 p-2.5 rounded-lg">
              <span className="text-slate-400">API Health</span>
              <span className="px-2 py-0.5 rounded font-bold bg-emerald-500/20 text-emerald-300">
                {summary.system_health.api_health || 'HEALTHY'}
              </span>
            </div>
          </div>
        </section>
      )}

      {/* STORAGE BY CLASS */}
      <section className="card">
        <div className="flex-between mb-4">
          <h3 className="card-title">Storage Breakdown by Class</h3>
          <span className="text-xs text-muted">Rates: STANDARD ($0.023/GB) | IA ($0.0125/GB) | ARCHIVE ($0.004/GB)</span>
        </div>
        <div className="grid-3">
          {summary.storage_by_class.map((c) => {
            const sizeGb = (c.size_bytes / (1024 * 1024 * 1024)).toFixed(2);
            return (
              <div key={c.storage_class} className="storage-class-card">
                <div className="flex-between mb-2">
                  <span className="badge badge-neutral font-bold">{c.storage_class}</span>
                  <span className="text-muted text-sm">{c.percentage}% of total</span>
                </div>
                <div className="text-2xl font-bold">{sizeGb} GB</div>
                <div className="text-sm text-muted mt-1">{c.object_count.toLocaleString()} objects</div>
                <div className="mt-3 pt-3 border-top flex-between">
                  <span className="text-xs text-muted">Est. Cost:</span>
                  <span className="font-semibold">${c.estimated_monthly_cost_usd.toFixed(2)}/mo</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* OPPORTUNITIES & APPROVALS */}
      <div className="grid-2">
        {/* LIFECYCLE OPPORTUNITIES */}
        <section className="card">
          <h3 className="card-title mb-4">Lifecycle Opportunities</h3>
          <div className="space-y-3">
            {Object.entries(summary.opportunities_by_type).map(([type, count]) => (
              <div key={type} className="opportunity-row">
                <span className="badge badge-primary">{type}</span>
                <span className="font-bold text-lg">{count} objects</span>
              </div>
            ))}
          </div>
        </section>

        {/* PENDING APPROVALS SUMMARY */}
        <section className="card">
          <h3 className="card-title mb-4">Pending Approvals Queue</h3>
          <div className="space-y-4">
            <div className="kpi-card kpi-warning">
              <div className="kpi-title">AWAITING REVIEW</div>
              <div className="kpi-value">{summary.pending_approvals_count} Recommendations</div>
              <div className="kpi-subtext">Requires explicit human approval</div>
            </div>
            <div className="flex-between pt-2">
              <span className="text-sm text-muted">High-Impact Approvals (ARCHIVE / DELETE):</span>
              <span className="badge badge-danger">{summary.high_impact_approvals_count} High Impact</span>
            </div>
            <div className="flex-between pt-1">
              <span className="text-sm text-muted">Active Legal Holds (Blocking):</span>
              <span className="badge badge-warning">{summary.active_legal_holds_count} Legal Holds</span>
            </div>
          </div>
        </section>
      </div>

      {/* RECENT ACTIVITY */}
      <section className="card">
        <h3 className="card-title mb-4">Recent Audit Activity</h3>
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Outcome</th>
                <th>Resource ID</th>
              </tr>
            </thead>
            <tbody>
              {summary.recent_activity.map((act) => (
                <tr key={act.id}>
                  <td className="text-muted text-xs">{new Date(act.timestamp).toLocaleString()}</td>
                  <td><span className="font-semibold text-sm">{act.action}</span></td>
                  <td>
                    <span className={`badge ${act.outcome === 'SUCCESS' || act.outcome === 'APPROVED' ? 'badge-success' : 'badge-neutral'}`}>
                      {act.outcome}
                    </span>
                  </td>
                  <td className="font-mono text-xs">{act.resource_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

export const SavingsPage: React.FC = () => {
  const { selectedOrg } = useOrganization();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [experiment, setExperiment] = useState<any | null>(null);
  const [errorAnalysis, setErrorAnalysis] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    if (!selectedOrg) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getDashboardSummary(selectedOrg.id);
      setSummary(data);

      const exp = await fetchJson<any>('/costs/experiment', {}, selectedOrg.id);
      setExperiment(exp);

      const errs = await fetchJson<any>('/costs/error-analysis', {}, selectedOrg.id);
      setErrorAnalysis(errs);
    } catch (err: any) {
      setError(err.message || 'Failed to load savings view metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedOrg?.id]);

  if (loading) return <LoadingSpinner message="Calculating storage cost & counterfactual experiment metrics..." />;
  if (error) return <ErrorState message={error} onRetry={loadData} />;
  if (!summary || !experiment) return null;

  const annualPotential = (summary.potential_monthly_savings_usd * 12).toFixed(2);
  const savRate = experiment.estimated_savings_percentage ?? 0.0;

  return (
    <div className="page-container space-y-6">
      <div className="page-header flex-between">
        <div>
          <h1 className="page-title">Organization Storage Savings Analysis & Experiment</h1>
          <p className="page-subtitle">Explicit distinction between Estimated, Approved, and Realized cost savings with counterfactual experiment metrics.</p>
        </div>
        <span className="badge badge-warning">Demo Pricing — Not Provider Billing</span>
      </div>

      <div className="grid-4">
        <KPICard
          title="POTENTIAL MONTHLY SAVINGS"
          value={`$${summary.potential_monthly_savings_usd.toFixed(2)}/mo`}
          subtext={`Est. Annual: $${annualPotential}/yr`}
          variant="primary"
          icon={<PiggyBank className="text-primary" />}
        />
        <KPICard
          title="SAVINGS RATE"
          value={`${savRate.toFixed(1)}%`}
          subtext="Potential optimization reduction"
          variant="success"
          icon={<TrendingUp className="text-success" />}
        />
        <KPICard
          title="APPROVED SAVINGS"
          value={`$${summary.approved_monthly_savings_usd.toFixed(2)}/mo`}
          subtext="Approved by operator, ready for execution"
          variant="warning"
          icon={<CheckSquare className="text-warning" />}
        />
        <KPICard
          title="REALIZED SAVINGS"
          value={`$${summary.realized_monthly_savings_usd.toFixed(2)}/mo`}
          subtext="Successfully executed migrations in ledger"
          variant="success"
          icon={<DollarSign className="text-success" />}
        />
      </div>

      {/* BASELINE VS OPTIMIZED EXPERIMENT COMPONENT */}
      <section className="card highlight-box">
        <div className="flex-between mb-4">
          <div className="flex-align gap-2">
            <BarChart2 className="text-primary" />
            <h3 className="card-title">Counterfactual Experiment: Baseline vs. Optimized</h3>
          </div>
          <span className="badge badge-primary">Seed Random 42 Dataset</span>
        </div>

        <div className="grid-3 mb-6">
          <div className="kpi-card kpi-neutral">
            <div className="kpi-title">BASELINE MONTHLY COST</div>
            <div className="kpi-value">${experiment.baseline_monthly_cost_usd.toFixed(2)} / mo</div>
            <div className="kpi-subtext">Assuming zero storage class transitions</div>
          </div>
          <div className="kpi-card kpi-success">
            <div className="kpi-title">OPTIMIZED MONTHLY COST</div>
            <div className="kpi-value">${experiment.optimized_monthly_cost_usd.toFixed(2)} / mo</div>
            <div className="kpi-subtext">If all eligible recommendations execute</div>
          </div>
          <div className="kpi-card kpi-primary">
            <div className="kpi-title">COUNTERFACTUAL SAVINGS</div>
            <div className="kpi-value text-success">+${experiment.estimated_monthly_savings_usd.toFixed(2)} / mo</div>
            <div className="kpi-subtext">{experiment.estimated_savings_percentage}% cost reduction</div>
          </div>
        </div>

        <div className="grid-4 border-top pt-4">
          <div>
            <span className="label">Eligible for Optimization:</span>
            <p className="font-bold text-lg text-primary">{experiment.objects_eligible_for_optimization} objects</p>
          </div>
          <div>
            <span className="label">Kept in Standard:</span>
            <p className="font-bold text-lg">{experiment.objects_kept} objects</p>
          </div>
          <div>
            <span className="label">Recommended for Archive:</span>
            <p className="font-bold text-lg text-success">{experiment.objects_archived} objects</p>
          </div>
          <div>
            <span className="label">Moved to Infrequent Access:</span>
            <p className="font-bold text-lg text-info">{experiment.objects_moved_to_infrequent_access} objects</p>
          </div>
        </div>
      </section>

      {/* COST BREAKDOWN COMPONENT */}
      <section className="card">
        <h3 className="card-title mb-4">Cost Breakdown by Storage Class</h3>
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th>Storage Class</th>
                <th>Storage Volume</th>
                <th>Percentage</th>
                <th>Unit Rate ($/GB-month)</th>
                <th>Monthly Cost</th>
              </tr>
            </thead>
            <tbody>
              {summary.storage_by_class.map((c) => {
                const sizeGb = (c.size_bytes / (1024 * 1024 * 1024)).toFixed(2);
                const rate = c.storage_class === 'STANDARD' ? '$0.0230' : (c.storage_class === 'INFREQUENT_ACCESS' ? '$0.0125' : '$0.0040');
                return (
                  <tr key={c.storage_class}>
                    <td><span className="badge badge-neutral">{c.storage_class}</span></td>
                    <td className="font-bold">{sizeGb} GB</td>
                    <td>{c.percentage}%</td>
                    <td className="font-mono text-xs">{rate}</td>
                    <td className="font-semibold text-primary">${c.estimated_monthly_cost_usd.toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* ERROR ANALYSIS */}
      {errorAnalysis && (
        <section className="card">
          <div className="flex-align gap-2 mb-4">
            <AlertCircle className="text-warning" />
            <h3 className="card-title">Recommendation Error Analysis</h3>
          </div>
          <p className="text-sm text-muted mb-4">Unexecuted recommendation classification breakdown explaining why recommendations remain pending or blocked:</p>
          <div className="grid-3">
            {Object.entries(errorAnalysis.category_breakdown || {}).map(([cat, cnt]: [string, any]) => (
              <div key={cat} className="flex-between p-3 border-rounded bg-surface">
                <span className="text-xs font-semibold">{cat}</span>
                <span className="badge badge-neutral">{cnt}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};
