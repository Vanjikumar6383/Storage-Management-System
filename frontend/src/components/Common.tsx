import React from 'react';
import { RefreshCw, AlertCircle, Inbox } from 'lucide-react';

export const LoadingSpinner: React.FC<{ message?: string }> = ({ message = 'Loading storage inventory...' }) => (
  <div className="state-container" role="status" aria-label={message}>
    <RefreshCw className="spinner-icon" />
    <p className="state-message">{message}</p>
  </div>
);

export const EmptyState: React.FC<{ title?: string; message?: string }> = ({
  title = 'No records found',
  message = 'There are no items matching your current filters.',
}) => (
  <div className="state-container" role="region" aria-label={title}>
    <Inbox className="state-icon text-muted" />
    <h4 className="state-title">{title}</h4>
    <p className="state-subtext">{message}</p>
  </div>
);

export const ErrorState: React.FC<{ message?: string; onRetry?: () => void }> = ({
  message = 'Unable to load recommendations.',
  onRetry,
}) => (
  <div className="state-container state-error" role="alert">
    <AlertCircle className="state-icon text-danger" />
    <h4 className="state-title">Error Loading Data</h4>
    <p className="state-subtext">{message}</p>
    {onRetry && (
      <button className="btn btn-secondary btn-sm mt-3" onClick={onRetry} aria-label="Retry loading data">
        <RefreshCw className="btn-icon" /> Retry
      </button>
    )}
  </div>
);

export interface KPICardProps {
  title: string;
  value: string | number;
  subtext?: string;
  variant?: 'primary' | 'success' | 'warning' | 'danger' | 'neutral';
  icon?: React.ReactNode;
}

export const KPICard: React.FC<KPICardProps> = ({ title, value, subtext, variant = 'neutral', icon }) => (
  <div className={`kpi-card kpi-${variant}`} tabIndex={0} aria-label={`${title}: ${value}`}>
    <div className="kpi-header">
      <span className="kpi-title">{title}</span>
      {icon && <span className="kpi-icon-wrapper">{icon}</span>}
    </div>
    <div className="kpi-value">{value}</div>
    {subtext && <div className="kpi-subtext">{subtext}</div>}
  </div>
);

export const SafetyBanner: React.FC = () => (
  <div className="safety-banner" role="region" aria-label="Safety Boundary Notice">
    <div className="safety-badge">SAFETY MODE ACTIVE</div>
    <div className="safety-text">
      <strong>Prototype Execution Boundary:</strong> Recommendations never modify storage automatically. Physical deletion is strictly disabled in dry-run safety mode. Human approval is required for all tier migrations.
    </div>
  </div>
);
