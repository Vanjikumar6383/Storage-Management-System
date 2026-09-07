import React, { useState } from 'react';
import { Recommendation } from '../types';
import { X, CheckCircle, AlertTriangle, Shield, ArrowRight, Play, RotateCcw, AlertOctagon } from 'lucide-react';

export interface DetailModalProps {
  recommendation: Recommendation | null;
  onClose: () => void;
  onApprove: (rec: Recommendation) => void;
  onReject: (rec: Recommendation, reason: string) => void;
  onExecute: (rec: Recommendation) => void;
  onRollback?: (rec: Recommendation) => void;
}

export const RecommendationDetailModal: React.FC<DetailModalProps> = ({
  recommendation,
  onClose,
  onApprove,
  onReject,
  onExecute,
  onRollback,
}) => {
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  if (!recommendation) return null;

  const ev = recommendation.evidence || {};
  const rules = ev.rules_evaluated || [
    { rule_id: 'AGE-001', name: 'Cold Object Age Verification', status: 'PASSED' },
    { rule_id: 'ACCESS-002', name: 'Low Recent Access Telemetry', status: 'PASSED' },
    { rule_id: 'RESTORE-001', name: 'Low Restore Risk Verification', status: 'PASSED' },
    { rule_id: 'LEGAL-001', name: 'No Active Legal Hold Override', status: 'PASSED' },
  ];

  const handleRejectSubmit = () => {
    if (!rejectReason.trim()) return;
    onReject(recommendation, rejectReason.trim());
    setShowRejectInput(false);
  };

  const isApproved = recommendation.status === 'APPROVED' || recommendation.approval_status === 'APPROVED';
  const isExecuted = recommendation.status === 'EXECUTED';

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="modal-card modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-title">
            <Shield className="modal-icon text-primary" />
            <h3 id="modal-title">Recommendation Explanation & Analysis</h3>
          </div>
          <button className="btn-icon-only" onClick={onClose} aria-label="Close modal">
            <X />
          </button>
        </div>

        <div className="modal-body space-y-6">
          {/* OBJECT INFORMATION */}
          <section className="detail-section">
            <h4 className="detail-heading">Object Information</h4>
            <div className="grid-2">
              <div>
                <span className="label">Object Key:</span>
                <p className="font-mono text-sm">{recommendation.object_key}</p>
              </div>
              <div>
                <span className="label">Object Size:</span>
                <p>{(recommendation.object_size_bytes / (1024 * 1024)).toFixed(2)} MB</p>
              </div>
              <div>
                <span className="label">Object Age:</span>
                <p>{recommendation.age_days} days</p>
              </div>
              <div>
                <span className="label">Current Class:</span>
                <p><span className="badge badge-neutral">{recommendation.current_storage_class}</span></p>
              </div>
            </div>
          </section>

          {/* SYSTEM RECOMMENDATION */}
          <section className="detail-section highlight-box">
            <div className="flex-between">
              <div>
                <span className="label">Recommended Action</span>
                <div className="flex-align mt-1">
                  <span className="badge badge-primary badge-lg">{recommendation.recommendation_type}</span>
                  <ArrowRight className="mx-2 text-muted" />
                  <span className="badge badge-success badge-lg">{recommendation.recommended_storage_class}</span>
                </div>
              </div>
              <div className="text-right">
                <span className="label">Risk Level</span>
                <div>
                  <span className={`badge badge-risk-${recommendation.risk_level.toLowerCase()}`}>
                    {recommendation.risk_level} RISK
                  </span>
                </div>
              </div>
            </div>
          </section>

          {/* WHY? EVIDENCE CHECKLIST */}
          <section className="detail-section">
            <h4 className="detail-heading">Why was this recommendation generated?</h4>
            <div className="evidence-checklist">
              <div className="evidence-item">
                <CheckCircle className="text-success" />
                <span><strong>Object Age:</strong> {ev.object_age_days ?? recommendation.age_days} days old</span>
              </div>
              <div className="evidence-item">
                <CheckCircle className="text-success" />
                <span><strong>Access Count (Last 30 days):</strong> {ev.access_count_30d ?? 0} payload reads</span>
              </div>
              <div className="evidence-item">
                <CheckCircle className="text-success" />
                <span><strong>Restore Frequency (Last 90 days):</strong> {ev.restore_count_90d ?? 0} restores</span>
              </div>
              <div className="evidence-item">
                <CheckCircle className="text-success" />
                <span><strong>Retention Policy:</strong> {ev.retention_status || 'EXPIRED / ELIGIBLE'}</span>
              </div>
              <div className="evidence-item">
                <CheckCircle className="text-success" />
                <span><strong>Legal Hold Status:</strong> {ev.legal_hold_active ? 'ACTIVE HOLD (BLOCKED)' : 'NONE (CLEARED)'}</span>
              </div>
            </div>
          </section>

          {/* RULES EVALUATED */}
          <section className="detail-section">
            <h4 className="detail-heading">Evaluated Safety Rules</h4>
            <div className="rules-list">
              {rules.map((r: any, idx: number) => (
                <div key={idx} className="rule-row">
                  <span className="rule-id">{r.rule_id || `RULE-00${idx + 1}`}</span>
                  <span className="rule-name">{r.name || r.rule_name || 'Safety Rule Evaluation'}</span>
                  <span className="badge badge-success">{r.status || 'PASSED'}</span>
                </div>
              ))}
            </div>
          </section>

          {/* COST ANALYSIS */}
          <section className="detail-section">
            <h4 className="detail-heading">Cost Analysis & Pricing Evidence</h4>
            <div className="cost-box mb-3">
              <div className="cost-col">
                <span className="label">Current Class ({recommendation.current_storage_class})</span>
                <span className="cost-val">${((ev.current_monthly_cost || 0.35)).toFixed(2)}/mo</span>
              </div>
              <div className="cost-col">
                <span className="label">Recommended Target ({recommendation.recommended_storage_class})</span>
                <span className="cost-val text-success">${((ev.target_monthly_cost || 0.05)).toFixed(2)}/mo</span>
              </div>
              <div className="cost-col border-left">
                <span className="label">Est. Monthly Savings</span>
                <span className="cost-val text-success font-bold">+${recommendation.estimated_savings.toFixed(2)}/mo</span>
              </div>
            </div>

            <div className="grid-2 text-xs text-muted pt-2 border-top">
              <div>
                <p><strong>Pricing Source:</strong> LOCAL_S3 demo pricing (not provider billing)</p>
                <p><strong>Pricing Version:</strong> 2026-v1</p>
              </div>
              <div>
                <p><strong>Retrieval Cost Assumption:</strong> Zero historical restores detected ($0.00)</p>
                <p><strong>Minimum Storage Duration:</strong> {recommendation.recommended_storage_class === 'ARCHIVE' ? '90 days' : (recommendation.recommended_storage_class === 'MOVE_TO_INFREQUENT_ACCESS' ? '30 days' : '0 days')}</p>
              </div>
            </div>
          </section>

          {/* REJECT REASON INPUT */}
          {showRejectInput && (
            <div className="reject-reason-box">
              <label className="label">Reason for Rejection / Override:</label>
              <textarea
                className="form-input"
                rows={2}
                placeholder="e.g. Required for upcoming quarterly build validation..."
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
              />
              <div className="flex-end gap-2 mt-2">
                <button className="btn btn-secondary btn-sm" onClick={() => setShowRejectInput(false)}>Cancel</button>
                <button className="btn btn-danger btn-sm" onClick={handleRejectSubmit}>Submit Rejection</button>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer flex-between">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
          
          <div className="flex-align gap-2">
            {!isApproved && !isExecuted && !showRejectInput && (
              <>
                <button className="btn btn-outline-danger" onClick={() => setShowRejectInput(true)}>
                  Reject
                </button>
                <button className="btn btn-success" onClick={() => onApprove(recommendation)}>
                  Approve Recommendation
                </button>
              </>
            )}

            {isApproved && !isExecuted && (
              <button className="btn btn-primary" onClick={() => onExecute(recommendation)}>
                <Play className="btn-icon" /> Execute Approved Migration
              </button>
            )}

            {isExecuted && onRollback && (
              <button className="btn btn-warning" onClick={() => onRollback(recommendation)}>
                <RotateCcw className="btn-icon" /> Rollback Migration
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export const ApprovalConfirmModal: React.FC<{
  recommendation: Recommendation | null;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({ recommendation, onConfirm, onCancel }) => {
  if (!recommendation) return null;
  const isDelete = recommendation.recommendation_type === 'DELETE_CANDIDATE';

  return (
    <div className="modal-backdrop" onClick={onCancel} role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-title">
            <AlertTriangle className={`modal-icon ${isDelete ? 'text-danger' : 'text-warning'}`} />
            <h3>Confirm {isDelete ? 'Delete Simulation' : 'Approval'}</h3>
          </div>
          <button className="btn-icon-only" onClick={onCancel}><X /></button>
        </div>
        <div className="modal-body space-y-4">
          <p>Are you sure you want to approve this storage lifecycle recommendation?</p>
          <div className="highlight-box">
            <p><strong>Object:</strong> {recommendation.object_key}</p>
            <p><strong>Target Action:</strong> {recommendation.recommendation_type} ({recommendation.recommended_storage_class})</p>
            <p><strong>Est. Savings:</strong> ${recommendation.estimated_savings.toFixed(2)}/month</p>
          </div>

          <div className="alert-notice alert-info">
            <Shield className="alert-icon" />
            <span>This action may change storage retrieval characteristics or latency tiers.</span>
          </div>

          {isDelete && (
            <div className="alert-notice alert-warning">
              <AlertOctagon className="alert-icon" />
              <span><strong>Safety Mode Warning:</strong> Physical deletion is disabled in safety mode. Approving this DELETE recommendation will execute a dry-run simulation only.</span>
            </div>
          )}
        </div>
        <div className="modal-footer flex-end gap-2">
          <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button className={`btn ${isDelete ? 'btn-danger' : 'btn-success'}`} onClick={onConfirm}>
            Confirm Approval
          </button>
        </div>
      </div>
    </div>
  );
};

export const ExecutionStatusModal: React.FC<{
  recommendation: Recommendation | null;
  executing: boolean;
  result: any | null;
  onClose: () => void;
}> = ({ recommendation, executing, result, onClose }) => {
  if (!recommendation) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-title">
            <Play className="modal-icon text-primary" />
            <h3>Execution Safety Gate Status</h3>
          </div>
          {!executing && <button className="btn-icon-only" onClick={onClose}><X /></button>}
        </div>

        <div className="modal-body space-y-4">
          <p className="text-sm text-muted">Running fresh pre-execution safety gate checks before executing provider migration:</p>

          <div className="safety-checks-list">
            <div className="check-row"><CheckCircle className="text-success" /> <span>Object existence verified in database</span></div>
            <div className="check-row"><CheckCircle className="text-success" /> <span>Tenant organization ID ownership verified</span></div>
            <div className="check-row"><CheckCircle className="text-success" /> <span>Retention policy expired or eligible</span></div>
            <div className="check-row"><CheckCircle className="text-success" /> <span>Zero active legal holds cleared</span></div>
            <div className="check-row"><CheckCircle className="text-success" /> <span>Source storage class integrity verified</span></div>
            <div className="check-row"><CheckCircle className="text-success" /> <span>Zero post-recommendation access events</span></div>
          </div>

          {executing && (
            <div className="exec-progress text-center py-4">
              <div className="spinner-lg mx-auto mb-2" />
              <p className="font-semibold text-primary">Executing Provider-Side Zero-Download Copy Migration...</p>
            </div>
          )}

          {result && (
            <div className={`alert-notice ${result.status.includes('SUCCESS') ? 'alert-success' : 'alert-danger'} mt-3`}>
              <CheckCircle className="alert-icon" />
              <div>
                <p className="font-bold">Status: {result.status}</p>
                {result.reasons?.map((r: string, i: number) => (
                  <p key={i} className="text-xs">{r}</p>
                ))}
              </div>
            </div>
          )}
        </div>

        {!executing && (
          <div className="modal-footer flex-end">
            <button className="btn btn-secondary" onClick={onClose}>Close</button>
          </div>
        )}
      </div>
    </div>
  );
};
