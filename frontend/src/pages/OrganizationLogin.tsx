import React, { useState } from 'react';
import { useOrganization } from '../context/OrganizationContext';
import { OrganizationRegisterModal } from '../components/OrganizationRegisterModal';
import {
  HardDrive,
  Building2,
  ShieldCheck,
  Sparkles,
  ArrowRight,
  Lock,
  Cloud,
  CheckCircle2,
  AlertCircle,
  PiggyBank,
  ArrowLeftRight,
} from 'lucide-react';

export const OrganizationLogin: React.FC = () => {
  const {
    organizations,
    loading,
    error,
    loginWithAccount,
    quickLoginWithOrg,
  } = useOrganization();

  const [slugOrEmail, setSlugOrEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [showRegisterModal, setShowRegisterModal] = useState(false);

  const handleManualLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    if (!slugOrEmail.trim()) {
      setLoginError('Please enter your organization slug or administrator email.');
      return;
    }

    setIsSubmitting(true);
    try {
      await loginWithAccount(slugOrEmail.trim());
    } catch (err: any) {
      setLoginError(err.message || 'Authentication failed. Please verify credentials or register.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="org-login-page">
      <div className="login-backdrop-glow" />

      {/* TOP HEADER */}
      <header className="org-login-nav">
        <div className="login-brand">
          <HardDrive className="brand-logo" size={24} />
          <div className="brand-text">
            <span className="brand-main">Storage Optimizer</span>
            <span className="brand-badge">ENTERPRISE</span>
          </div>
        </div>

        <div className="login-nav-right">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setShowRegisterModal(true)}
          >
            <Building2 size={15} />
            <span>Register Organization</span>
          </button>
        </div>
      </header>

      {/* MAIN AUTH WRAPPER */}
      <div className="login-content-wrapper">
        <div className="login-split-card">
          {/* LEFT: LOGIN FORM */}
          <div className="login-form-pane">
            <div className="login-header-group">
              <div className="login-chip">
                <Lock size={14} />
                <span>ORGANIZATION ACCESS PORTAL</span>
              </div>
              <h1 className="login-headline">Sign in to your Organization</h1>
              <p className="login-subtext">
                Access your enterprise control plane, autonomous lifecycle tiering, and cloud cost management console.
              </p>
            </div>

            {(loginError || error) && (
              <div className="login-error-box">
                <AlertCircle size={18} />
                <span>{loginError || error}</span>
              </div>
            )}

            {/* PRESET ONE-CLICK LOGIN FOR ALL 10 CANONICAL DEMO ORGANIZATIONS */}
            <div className="preset-orgs-section">
              <label className="input-category-label">Quick Sign-In (10 Canonical Demo Organizations):</label>
              <div className="preset-org-chips">
                {organizations.map((org) => (
                  <button
                    key={org.id}
                    type="button"
                    className="preset-org-btn"
                    onClick={() => quickLoginWithOrg(org)}
                    title={`Log in as ${org.name}`}
                  >
                    <Building2 size={14} className="preset-icon" />
                    <span className="preset-name">{org.name}</span>
                    <span className="preset-slug">/{org.slug}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="login-divider">
              <span>or authenticate via workspace identifier</span>
            </div>

            {/* MANUAL LOGIN FORM */}
            <form onSubmit={handleManualLogin} className="manual-login-form">
              <div className="form-group">
                <label className="form-label" htmlFor="login-slug">
                  Organization Slug or Business Email
                </label>
                <div className="input-icon-wrapper">
                  <Building2 size={18} className="field-icon" />
                  <input
                    id="login-slug"
                    type="text"
                    className="form-input with-left-icon"
                    placeholder="e.g. demo-organization or admin@demo-org.local"
                    value={slugOrEmail}
                    onChange={(e) => setSlugOrEmail(e.target.value)}
                    required
                  />
                </div>
                <span className="input-hint">
                  Supports workspace slugs (e.g. <code>demo-organization</code>) or administrator emails.
                </span>
              </div>

              <button
                type="submit"
                className="btn btn-primary btn-block btn-glow"
                disabled={isSubmitting || loading}
              >
                {isSubmitting ? (
                  <span>Authenticating...</span>
                ) : (
                  <>
                    <span>Enter Organization Portal</span>
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </form>

            {/* FOOTER CALLOUT TO REGISTER */}
            <div className="login-register-prompt">
              <span>Need storage management for a new organization?</span>
              <button
                type="button"
                className="text-link-button"
                onClick={() => setShowRegisterModal(true)}
              >
                Register for Storage Service &rarr;
              </button>
            </div>
          </div>

          {/* RIGHT: ENTERPRISE CAPABILITIES SHOWCASE */}
          <div className="login-showcase-pane">
            <div className="showcase-inner">
              <div className="showcase-badge">
                <Sparkles size={14} />
                <span>PLATFORM CAPABILITIES</span>
              </div>

              <h3 className="showcase-title">Autonomous Cloud Storage Governance</h3>
              <p className="showcase-desc">
                Stop overpaying for idle AWS S3 and hybrid cloud objects. Our multi-tenant control plane identifies cold data, enforces compliance policies, and automates tiered migrations with zero downtime.
              </p>

              <div className="showcase-feature-list">
                <div className="showcase-feature-item">
                  <div className="feature-icon-box">
                    <PiggyBank size={18} />
                  </div>
                  <div className="feature-details">
                    <h4>30% to 70% Cloud Savings</h4>
                    <p>Continuous heuristic analysis routes objects between Standard, Infrequent Access, and Archive.</p>
                  </div>
                </div>

                <div className="showcase-feature-item">
                  <div className="feature-icon-box">
                    <ArrowLeftRight size={18} />
                  </div>
                  <div className="feature-details">
                    <h4>Zero-Downtime Safe Migrations</h4>
                    <p>Non-destructive background replication with verified integrity and one-click rollback.</p>
                  </div>
                </div>

                <div className="showcase-feature-item">
                  <div className="feature-icon-box">
                    <ShieldCheck size={18} />
                  </div>
                  <div className="feature-details">
                    <h4>Legal Holds & Retention Locks</h4>
                    <p>SEC Rule 17a-4, FINRA, and HIPAA compliance prevents accidental lifecycle purging.</p>
                  </div>
                </div>

                <div className="showcase-feature-item">
                  <div className="feature-icon-box">
                    <Cloud size={18} />
                  </div>
                  <div className="feature-details">
                    <h4>Multi-Cloud S3 / MinIO Ready</h4>
                    <p>Plug-and-play connectors for AWS S3, MinIO, Azure Blob, and Google Cloud Storage.</p>
                  </div>
                </div>
              </div>

              <div className="showcase-trust-bar">
                <div className="trust-item">
                  <CheckCircle2 size={15} className="text-success" />
                  <span>SOC2 Type II Ready</span>
                </div>
                <div className="trust-item">
                  <CheckCircle2 size={15} className="text-success" />
                  <span>AES-256 KMS Encryption</span>
                </div>
                <div className="trust-item">
                  <CheckCircle2 size={15} className="text-success" />
                  <span>99.99% Enterprise SLA</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ONBOARDING REGISTRATION MODAL */}
      <OrganizationRegisterModal
        isOpen={showRegisterModal}
        onClose={() => setShowRegisterModal(false)}
      />
    </div>
  );
};
