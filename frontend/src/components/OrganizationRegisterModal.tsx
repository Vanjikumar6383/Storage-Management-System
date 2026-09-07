import React, { useState } from 'react';
import { useOrganization } from '../context/OrganizationContext';
import { OrganizationRegistrationPayload } from '../types';
import {
  X,
  Building2,
  Cloud,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

interface OrganizationRegisterModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultPlan?: 'DEVELOPMENT_FREE' | 'ENTERPRISE_PRO' | 'HYPERSCALE';
}

export const OrganizationRegisterModal: React.FC<OrganizationRegisterModalProps> = ({
  isOpen,
  onClose,
  defaultPlan = 'ENTERPRISE_PRO',
}) => {
  const { registerAndLaunch } = useOrganization();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [plan, setPlan] = useState<'DEVELOPMENT_FREE' | 'ENTERPRISE_PRO' | 'HYPERSCALE'>(defaultPlan);
  const [provider, setProvider] = useState<'AWS_S3' | 'LOCAL_S3_COMPATIBLE' | 'AZURE_BLOB' | 'GOOGLE_CLOUD_STORAGE'>('LOCAL_S3_COMPATIBLE');
  const [bucketName, setBucketName] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [environmentName, setEnvironmentName] = useState('production');
  const [seedSampleData, setSeedSampleData] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleNameChange = (val: string) => {
    setName(val);
    if (!slug || slug === name.toLowerCase().replace(/[^a-z0-9]/g, '-')) {
      setSlug(val.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''));
    }
  };

  const handleNextStep = () => {
    setFormError(null);
    if (step === 1) {
      if (!name.trim()) {
        setFormError('Organization name is required.');
        return;
      }
      if (!adminEmail.trim() || !adminEmail.includes('@')) {
        setFormError('A valid administrator business email is required.');
        return;
      }
      setStep(2);
    } else if (step === 2) {
      setStep(3);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      const payload: OrganizationRegistrationPayload = {
        name: name.trim(),
        slug: slug.trim() || undefined,
        admin_email: adminEmail.trim(),
        plan,
        provider,
        bucket_name: bucketName.trim() || undefined,
        region: region.trim() || 'us-east-1',
        environment_name: environmentName.trim() || 'production',
        seed_sample_data: seedSampleData,
      };

      await registerAndLaunch(payload);
      onClose();
    } catch (err: any) {
      setFormError(err.message || 'Failed to register organization. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-reg-title">
      <div className="modal-container register-org-modal">
        {/* MODAL HEADER */}
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-badge">
              <Building2 size={16} />
              <span>ORGANIZATION ONBOARDING</span>
            </div>
            <h3 id="modal-reg-title" className="neon-heading-sm">
              Register for Storage Management System
            </h3>
            <p className="modal-subtitle">
              Configure your organization workspace and provision intelligent storage lifecycle management.
            </p>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        {/* STEP PROGRESS BAR */}
        <div className="modal-step-indicator">
          <div className={`step-item ${step >= 1 ? 'active' : ''} ${step > 1 ? 'completed' : ''}`}>
            <span className="step-num">{step > 1 ? <CheckCircle2 size={14} /> : '1'}</span>
            <span className="step-label">Organization Info</span>
          </div>
          <div className="step-line" />
          <div className={`step-item ${step >= 2 ? 'active' : ''} ${step > 2 ? 'completed' : ''}`}>
            <span className="step-num">{step > 2 ? <CheckCircle2 size={14} /> : '2'}</span>
            <span className="step-label">Storage Infrastructure</span>
          </div>
          <div className="step-line" />
          <div className={`step-item ${step === 3 ? 'active' : ''}`}>
            <span className="step-num">3</span>
            <span className="step-label">Plan & Activation</span>
          </div>
        </div>

        {formError && (
          <div className="register-error-banner">
            <AlertCircle size={18} />
            <span>{formError}</span>
          </div>
        )}

        {/* MODAL BODY */}
        <form onSubmit={handleSubmit} className="register-form">
          {step === 1 && (
            <div className="register-step-body animate-fade-in">
              <div className="form-group">
                <label className="form-label" htmlFor="reg-org-name">
                  Organization / Enterprise Name *
                </label>
                <input
                  id="reg-org-name"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Apex Aerospace Systems"
                  value={name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  required
                />
                <span className="input-hint">The legal or team name for your organization tenant.</span>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="reg-org-slug">
                  Workspace Slug / Identifier
                </label>
                <div className="input-affix-group">
                  <span className="input-prefix">app.storage-optimizer.io/</span>
                  <input
                    id="reg-org-slug"
                    type="text"
                    className="form-input input-with-prefix"
                    placeholder="apex-aerospace"
                    value={slug}
                    onChange={(e) => setSlug(e.target.value)}
                  />
                </div>
                <span className="input-hint">Unique URL slug for multi-tenant isolation.</span>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="reg-admin-email">
                  Administrator Business Email *
                </label>
                <input
                  id="reg-admin-email"
                  type="email"
                  className="form-input"
                  placeholder="infra-lead@apexaerospace.com"
                  value={adminEmail}
                  onChange={(e) => setAdminEmail(e.target.value)}
                  required
                />
                <span className="input-hint">Owner account credentials for alerts and governance approvals.</span>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="register-step-body animate-fade-in">
              <div className="form-group">
                <label className="form-label">Primary Cloud Storage Provider</label>
                <div className="provider-card-grid">
                  {[
                    { id: 'LOCAL_S3_COMPATIBLE', label: 'Local S3 / MinIO (Demo)', desc: 'Zero cloud credentials required' },
                    { id: 'AWS_S3', label: 'Amazon S3', desc: 'Standard, IA, Glacier, Deep Archive' },
                    { id: 'AZURE_BLOB', label: 'Azure Blob Storage', desc: 'Hot, Cool, Cold, Archive tiers' },
                    { id: 'GOOGLE_CLOUD_STORAGE', label: 'Google Cloud Storage', desc: 'Standard, Nearline, Coldline, Archive' },
                  ].map((p) => (
                    <div
                      key={p.id}
                      className={`provider-card ${provider === p.id ? 'selected' : ''}`}
                      onClick={() => setProvider(p.id as any)}
                    >
                      <div className="provider-header">
                        <Cloud size={20} className="provider-icon" />
                        <span className="provider-title">{p.label}</span>
                      </div>
                      <span className="provider-desc">{p.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="form-row">
                <div className="form-group flex-1">
                  <label className="form-label" htmlFor="reg-bucket-name">
                    Initial Bucket / Container Name
                  </label>
                  <input
                    id="reg-bucket-name"
                    type="text"
                    className="form-input"
                    placeholder="e.g. apex-prod-telemetry-bucket"
                    value={bucketName}
                    onChange={(e) => setBucketName(e.target.value)}
                  />
                </div>
                <div className="form-group flex-1">
                  <label className="form-label" htmlFor="reg-region">
                    Storage Region
                  </label>
                  <input
                    id="reg-region"
                    type="text"
                    className="form-input"
                    placeholder="e.g. us-east-1"
                    value={region}
                    onChange={(e) => setRegion(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="reg-env-name">
                  Primary Environment Name
                </label>
                <input
                  id="reg-env-name"
                  type="text"
                  className="form-input"
                  placeholder="production"
                  value={environmentName}
                  onChange={(e) => setEnvironmentName(e.target.value)}
                />
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="register-step-body animate-fade-in">
              <div className="form-group">
                <label className="form-label">Select Storage Service Tier</label>
                <div className="plan-selection-grid">
                  {[
                    {
                      id: 'DEVELOPMENT_FREE',
                      name: 'Free Development',
                      price: '$0/mo',
                      sub: 'Up to 500 GB telemetry tracking, standard lifecycle heuristics, manual approvals.',
                    },
                    {
                      id: 'ENTERPRISE_PRO',
                      name: 'Enterprise Pro',
                      price: '$499/mo',
                      badge: 'RECOMMENDED',
                      sub: 'Up to 50 TB, automated migrations, compliance legal holds, FinOps savings analytics.',
                    },
                    {
                      id: 'HYPERSCALE',
                      name: 'Cloud HyperScale',
                      price: 'Custom',
                      sub: 'Unlimited petabytes, sub-second telemetry, dedicated VPC peering & 24/7 SLA.',
                    },
                  ].map((p) => (
                    <div
                      key={p.id}
                      className={`plan-card-option ${plan === p.id ? 'selected' : ''}`}
                      onClick={() => setPlan(p.id as any)}
                    >
                      <div className="plan-header-line">
                        <span className="plan-option-name">{p.name}</span>
                        {p.badge && <span className="plan-pill">{p.badge}</span>}
                      </div>
                      <div className="plan-price-tag">{p.price}</div>
                      <p className="plan-option-desc">{p.sub}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="sample-data-toggle-card">
                <label className="toggle-container">
                  <input
                    type="checkbox"
                    checked={seedSampleData}
                    onChange={(e) => setSeedSampleData(e.target.checked)}
                  />
                  <span className="toggle-slider" />
                </label>
                <div className="toggle-text">
                  <strong>Start with 0 Data (Clean Slate)</strong>
                  <p>
                    {seedSampleData
                      ? 'Pre-seed sample objects for testing purposes.'
                      : 'Default: Strictly 0 objects and 0 data provisioned. You can link your local storage folder immediately after registration.'}
                  </p>
                </div>
              </div>
            </div>

          )}

          {/* MODAL FOOTER */}
          <div className="modal-footer">
            {step > 1 ? (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setStep((s) => (s - 1) as any)}
                disabled={submitting}
              >
                Back
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onClose}
                disabled={submitting}
              >
                Cancel
              </button>
            )}

            {step < 3 ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleNextStep}
              >
                <span>Continue</span>
                <ArrowRight size={16} />
              </button>
            ) : (
              <button
                type="submit"
                className="btn btn-primary btn-glow"
                disabled={submitting}
              >
                {submitting ? (
                  <span>Provisioning Service...</span>
                ) : (
                  <>
                    <Sparkles size={16} />
                    <span>Activate & Enter Storage System</span>
                  </>
                )}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};
