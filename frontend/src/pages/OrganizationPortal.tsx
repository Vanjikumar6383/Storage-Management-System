import React, { useState, useId } from 'react';
import { useOrganization } from '../context/OrganizationContext';
import { OrganizationRegisterModal } from '../components/OrganizationRegisterModal';
import {
  HardDrive,
  Building2,
  Sparkles,
  PiggyBank,
  ArrowRight,
  ShieldCheck,
  Cloud,
  ArrowLeftRight,
  Layers,
  Activity,
  CheckCircle2,
  FileCheck2,
  Sliders,
  LogOut,
  Lock,
  Cpu,
  BarChart3,
} from 'lucide-react';

export const OrganizationPortal: React.FC = () => {
  const {
    selectedOrg,
    userEmail,
    currentPlan,
    logout,
    setScreenMode,
  } = useOrganization();

  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [selectedPlanForRegister, setSelectedPlanForRegister] = useState<
    'DEVELOPMENT_FREE' | 'ENTERPRISE_PRO' | 'HYPERSCALE'
  >('ENTERPRISE_PRO');

  // Interactive Live Cost Savings Calculator State
  const [storageTb, setStorageTb] = useState<number>(50);
  const storageSliderId = useId();

  // Standard AWS S3 is ~$23/TB/month ($0.023/GB).
  // Optimized blend (IA + Archive) averages ~$6.50/TB/month.
  const unoptimizedCost = Math.round(storageTb * 23);
  const optimizedCost = Math.round(storageTb * 6.5);
  const monthlySavings = unoptimizedCost - optimizedCost;
  const annualSavings = monthlySavings * 12;

  const handleOpenRegisterWithPlan = (
    plan: 'DEVELOPMENT_FREE' | 'ENTERPRISE_PRO' | 'HYPERSCALE'
  ) => {
    setSelectedPlanForRegister(plan);
    setRegisterModalOpen(true);
  };

  return (
    <div className="enterprise-portal">
      {/* ENTERPRISE TOP NAVIGATION */}
      <header className="portal-header">
        <div className="portal-header-left">
          <div className="portal-brand">
            <HardDrive className="brand-logo" size={24} />
            <div className="brand-titles">
              <span className="brand-name">Storage Optimizer</span>
              <span className="brand-pill">ENTERPRISE CLOUD PLATFORM</span>
            </div>
          </div>

          <nav className="portal-nav-links" aria-label="Enterprise Navigation">
            <a href="#hero" className="portal-link">Overview</a>
            <a href="#services" className="portal-link">Enterprise Services</a>
            <a href="#calculator" className="portal-link">Savings Calculator</a>
            <a href="#architecture" className="portal-link">Architecture</a>
            <a href="#plans" className="portal-link">Service Plans</a>
            <a href="#compliance" className="portal-link">Security & Trust</a>
          </nav>
        </div>

        <div className="portal-header-right">
          {selectedOrg && (
            <div className="current-org-badge" title={`Logged in as ${userEmail || 'Admin'}`}>
              <Building2 size={16} className="org-icon" />
              <div className="org-badge-text">
                <span className="org-name">{selectedOrg.name}</span>
                <span className="org-plan">{currentPlan || 'ENTERPRISE_PRO'}</span>
              </div>
            </div>
          )}

          <button
            className="btn btn-primary btn-sm btn-glow"
            onClick={() => setScreenMode('console')}
          >
            <Activity size={16} />
            <span>Open Storage Management System</span>
          </button>

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setRegisterModalOpen(true)}
          >
            <Building2 size={15} />
            <span>Register Service</span>
          </button>

          <button
            className="btn btn-ghost btn-sm icon-only-btn"
            onClick={logout}
            title="Log out or switch organization"
            aria-label="Log out"
          >
            <LogOut size={16} />
          </button>
        </div>
      </header>

      {/* HERO SECTION */}
      <section id="hero" className="portal-hero-section">
        <div className="hero-glow-sphere" />
        <div className="hero-grid-pattern" />

        <div className="hero-content">
          <div className="hero-pill-badge">
            <Sparkles size={14} />
            <span>AUTONOMOUS CLOUD LIFECYCLE MANAGEMENT</span>
          </div>

          <h1 className="hero-title">
            Intelligent Storage Lifecycle & <br />
            <span className="neon-gradient-text">Enterprise Cost Reduction</span>
          </h1>

          <p className="hero-description">
            Modern enterprises generate petabytes of object data, yet 60–80% turns cold within 60 days.
            Our multi-tenant control plane automates telemetry analysis, policy-driven tiered migration,
            and compliance legal holds with zero application downtime.
          </p>

          <div className="hero-actions">
            <button
              className="btn btn-primary btn-lg btn-glow"
              onClick={() => setScreenMode('console')}
            >
              <span>Launch Storage Management System</span>
              <ArrowRight size={18} />
            </button>

            <button
              className="btn btn-secondary btn-lg"
              onClick={() => setRegisterModalOpen(true)}
            >
              <Building2 size={18} />
              <span>Register New Organization</span>
            </button>

            <a href="#services" className="btn btn-ghost btn-lg">
              <span>Explore Services & Details &darr;</span>
            </a>
          </div>

          {/* KEY METRIC CARDS */}
          <div className="hero-metrics-grid">
            <div className="hero-metric-card">
              <div className="metric-val text-neon-blue">30% – 70%</div>
              <div className="metric-label">Cloud Cost Reduction</div>
              <div className="metric-sub">Across AWS S3, MinIO & Multi-Cloud</div>
            </div>

            <div className="hero-metric-card">
              <div className="metric-val text-neon-bright">Zero Downtime</div>
              <div className="metric-label">Migration Engine</div>
              <div className="metric-sub">Non-destructive background replication</div>
            </div>

            <div className="hero-metric-card">
              <div className="metric-val text-neon-blue">1-Click</div>
              <div className="metric-label">Instant Rollback</div>
              <div className="metric-sub">Guaranteed SLA against restore risk</div>
            </div>

            <div className="hero-metric-card">
              <div className="metric-val text-success">SEC 17a-4 / SOC2</div>
              <div className="metric-label">Compliance Locks</div>
              <div className="metric-sub">Immutable WORM & Legal Holds</div>
            </div>
          </div>
        </div>
      </section>

      {/* LIVE INTERACTIVE SAVINGS CALCULATOR */}
      <section id="calculator" className="portal-section calculator-section">
        <div className="section-header text-center">
          <div className="section-tag">
            <PiggyBank size={15} />
            <span>FINOPS SAVINGS FORECASTER</span>
          </div>
          <h2 className="section-title">Estimate Your Enterprise Storage Savings</h2>
          <p className="section-subtitle">
            Slide to estimate your monthly and annual cost savings achieved through autonomous tiering.
          </p>
        </div>

        <div className="calculator-container">
          <div className="calculator-controls">
            <div className="slider-header">
              <label htmlFor={storageSliderId} className="slider-label">Total Cloud Storage Volume:</label>
              <span className="slider-value-display">{storageTb} TB</span>
            </div>
            <input
              id={storageSliderId}
              type="range"
              min={5}
              max={500}
              step={5}
              value={storageTb}
              onChange={(e) => setStorageTb(Number(e.target.value))}
              className="storage-slider"
              aria-label="Storage Volume in TB"
            />
            <div className="slider-ticks">
              <span>5 TB</span>
              <span>100 TB</span>
              <span>250 TB</span>
              <span>500 TB</span>
            </div>

            <div className="calculator-notes">
              <div className="note-item">
                <CheckCircle2 size={16} className="text-neon-blue" />
                <span>Standard AWS S3 baseline at ~$23 / TB / month</span>
              </div>
              <div className="note-item">
                <CheckCircle2 size={16} className="text-neon-blue" />
                <span>Optimized tiered storage (Infrequent Access & Archive) at ~$6.50 / TB / month</span>
              </div>
              <div className="note-item">
                <CheckCircle2 size={16} className="text-neon-blue" />
                <span>Autonomous cold-object discovery identifies ~70% idle data</span>
              </div>
            </div>
          </div>

          <div className="calculator-results-card">
            <div className="results-badge">PROJECTED SAVINGS</div>
            <div className="results-primary">
              <div className="savings-number">${monthlySavings.toLocaleString()}</div>
              <div className="savings-period">/ month saved</div>
            </div>

            <div className="results-secondary">
              <span className="annual-highlight">${annualSavings.toLocaleString()} / year</span>
              <span className="annual-label">Estimated Annual Cloud Savings</span>
            </div>

            <div className="breakdown-bars">
              <div className="breakdown-row">
                <span>Unoptimized Monthly Baseline:</span>
                <strong>${unoptimizedCost.toLocaleString()}</strong>
              </div>
              <div className="breakdown-row text-success">
                <span>Optimized Autonomous Monthly Cost:</span>
                <strong>${optimizedCost.toLocaleString()}</strong>
              </div>
            </div>

            <button
              className="btn btn-primary btn-block btn-glow mt-4"
              onClick={() => handleOpenRegisterWithPlan('ENTERPRISE_PRO')}
            >
              <span>Unlock These Savings Now</span>
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </section>

      {/* ENTERPRISE SERVICES CATALOG */}
      <section id="services" className="portal-section services-section">
        <div className="section-header text-center">
          <div className="section-tag">
            <Layers size={15} />
            <span>ENTERPRISE CAPABILITIES</span>
          </div>
          <h2 className="section-title">Comprehensive Storage Management Services</h2>
          <p className="section-subtitle">
            Explore the core architectural services powering the Storage Optimizer platform.
          </p>
        </div>

        <div className="services-grid">
          {/* SERVICE 1 */}
          <div className="service-card">
            <div className="service-card-header">
              <div className="service-icon-box">
                <Sliders size={24} />
              </div>
              <span className="service-status-pill">CORE SERVICE</span>
            </div>
            <h3 className="service-name">Autonomous Lifecycle Tiering Engine</h3>
            <p className="service-description">
              Intelligent heuristic evaluation of storage objects based on recency, frequency, restore penalty modeling, and object age.
            </p>
            <ul className="service-feature-bullets">
              <li>Automatic promotion and demotion across Standard, Infrequent Access, and Archive classes.</li>
              <li>Heuristic safety guards prevent early-deletion and expedited-restore fee penalties.</li>
              <li>Continuous policy evaluation with customizable organization-wide rules.</li>
            </ul>
          </div>

          {/* SERVICE 2 */}
          <div className="service-card">
            <div className="service-card-header">
              <div className="service-icon-box">
                <Activity size={24} />
              </div>
              <span className="service-status-pill">REAL-TIME</span>
            </div>
            <h3 className="service-name">Deep Telemetry & Access Profiler</h3>
            <p className="service-description">
              Continuous ingestion of object-level access patterns, byte read volumes, and restore latency profiles.
            </p>
            <ul className="service-feature-bullets">
              <li>Sub-second telemetry processing with zero performance impact on data pipelines.</li>
              <li>Detection of orphaned build artifacts, stale test fixtures, and abandoned datasets.</li>
              <li>Detailed 30-day and 90-day access histograms for auditability.</li>
            </ul>
          </div>

          {/* SERVICE 3 */}
          <div className="service-card">
            <div className="service-card-header">
              <div className="service-icon-box">
                <ArrowLeftRight size={24} />
              </div>
              <span className="service-status-pill">NON-DESTRUCTIVE</span>
            </div>
            <h3 className="service-name">Zero-Downtime Migration & Rollback</h3>
            <p className="service-description">
              Safe object migrations with background state verification and guaranteed instant rollback.
            </p>
            <ul className="service-feature-bullets">
              <li>Non-destructive asynchronous replication ensures zero read interruption.</li>
              <li>1-Click instant rollback capability if operational access patterns change.</li>
              <li>Simulation Mode enables safe verification prior to touching physical cloud storage.</li>
            </ul>
          </div>

          {/* SERVICE 4 */}
          <div className="service-card">
            <div className="service-card-header">
              <div className="service-icon-box">
                <ShieldCheck size={24} />
              </div>
              <span className="service-status-pill">GOVERNANCE</span>
            </div>
            <h3 className="service-name">Legal Holds & Compliance Retention Lock</h3>
            <p className="service-description">
              Enterprise compliance framework enforcing immutable retention and blocking accidental purges.
            </p>
            <ul className="service-feature-bullets">
              <li>SEC Rule 17a-4, FINRA, and HIPAA-compliant WORM storage lock enforcement.</li>
              <li>Active legal hold overrides prevent policy engines from modifying protected records.</li>
              <li>Immutable audit logging tracking every policy decision, approval, and migration.</li>
            </ul>
          </div>

          {/* SERVICE 5 */}
          <div className="service-card">
            <div className="service-card-header">
              <div className="service-icon-box">
                <BarChart3 size={24} />
              </div>
              <span className="service-status-pill">FINOPS</span>
            </div>
            <h3 className="service-name">FinOps Cost Analytics & Forecasting</h3>
            <p className="service-description">
              Granular cloud expenditure reporting partitioned by environment, tenant, and storage location.
            </p>
            <ul className="service-feature-bullets">
              <li>Realized vs. potential monthly cost savings ledger with audit verification.</li>
              <li>Cost projections with tier unit pricing catalogs across multiple cloud providers.</li>
              <li>High-impact approval queues highlighting substantial savings opportunities.</li>
            </ul>
          </div>

          {/* SERVICE 6 */}
          <div className="service-card">
            <div className="service-card-header">
              <div className="service-icon-box">
                <Cloud size={24} />
              </div>
              <span className="service-status-pill">MULTI-CLOUD</span>
            </div>
            <h3 className="service-name">Multi-Cloud Storage Connectors</h3>
            <p className="service-description">
              Unified control plane supporting native AWS S3, local MinIO, Azure Blob, and Google Cloud Storage.
            </p>
            <ul className="service-feature-bullets">
              <li>Seamless abstraction across hybrid on-premise and multi-region cloud infrastructures.</li>
              <li>Zero credentials leakage with automatic reference credential resolution.</li>
              <li>Isolated multi-tenant boundaries with role-based access control (RBAC).</li>
            </ul>
          </div>
        </div>
      </section>

      {/* PLATFORM ARCHITECTURE & PIPELINE */}
      <section id="architecture" className="portal-section architecture-section">
        <div className="section-header text-center">
          <div className="section-tag">
            <Cpu size={15} />
            <span>HOW IT WORKS</span>
          </div>
          <h2 className="section-title">4-Stage Autonomous Lifecycle Pipeline</h2>
          <p className="section-subtitle">
            From raw access events to verified tier migration without risk or manual overhead.
          </p>
        </div>

        <div className="pipeline-steps-container">
          <div className="pipeline-step-card">
            <div className="step-circle">1</div>
            <h4>Ingest Telemetry</h4>
            <p>Access and restore events streamed into real-time telemetry tables without latency overhead.</p>
          </div>

          <div className="pipeline-connector" />

          <div className="pipeline-step-card">
            <div className="step-circle">2</div>
            <h4>Evaluate Policies</h4>
            <p>Heuristic engine examines retention rules, age thresholds, and legal hold constraints.</p>
          </div>

          <div className="pipeline-connector" />

          <div className="pipeline-step-card">
            <div className="step-circle">3</div>
            <h4>Review & Approve</h4>
            <p>Human-in-the-loop governance modal with full explainable evidence and safety verification.</p>
          </div>

          <div className="pipeline-connector" />

          <div className="pipeline-step-card">
            <div className="step-circle">4</div>
            <h4>Safe Migration</h4>
            <p>Non-destructive object replication with integrity checks and instant rollback guarantee.</p>
          </div>
        </div>
      </section>

      {/* SERVICE PLANS & PRICING */}
      <section id="plans" className="portal-section plans-section">
        <div className="section-header text-center">
          <div className="section-tag">
            <FileCheck2 size={15} />
            <span>TRANSPARENT TIERS</span>
          </div>
          <h2 className="section-title">Enterprise Storage Service Plans</h2>
          <p className="section-subtitle">
            Choose the tier tailored to your data footprint and compliance requirements.
          </p>
        </div>

        <div className="plans-grid">
          {/* PLAN 1 */}
          <div className="plan-card">
            <div className="plan-name">Free Development</div>
            <div className="plan-tagline">Ideal for testing and evaluation</div>
            <div className="plan-price">
              <span className="price-amount">$0</span>
              <span className="price-period">/ month</span>
            </div>
            <ul className="plan-features">
              <li><CheckCircle2 size={15} className="text-neon-blue" /> Up to 500 GB Storage Monitored</li>
              <li><CheckCircle2 size={15} className="text-neon-blue" /> Standard Lifecycle Heuristics</li>
              <li><CheckCircle2 size={15} className="text-neon-blue" /> Manual Approval Queue</li>
              <li><CheckCircle2 size={15} className="text-neon-blue" /> Local S3 & MinIO Simulation</li>
              <li><CheckCircle2 size={15} className="text-neon-blue" /> Community Support</li>
            </ul>
            <button
              className="btn btn-secondary btn-block"
              onClick={() => handleOpenRegisterWithPlan('DEVELOPMENT_FREE')}
            >
              Get Started Free
            </button>
          </div>

          {/* PLAN 2 (HIGHLIGHTED) */}
          <div className="plan-card featured">
            <div className="featured-badge">MOST POPULAR</div>
            <div className="plan-name">Enterprise Pro</div>
            <div className="plan-tagline">For production cloud storage fleets</div>
            <div className="plan-price">
              <span className="price-amount">$499</span>
              <span className="price-period">/ month</span>
            </div>
            <ul className="plan-features">
              <li><CheckCircle2 size={15} className="text-neon-bright" /> Up to 50 TB Storage Monitored</li>
              <li><CheckCircle2 size={15} className="text-neon-bright" /> Automated Async Migration Engine</li>
              <li><CheckCircle2 size={15} className="text-neon-bright" /> 1-Click Instant Migration Rollback</li>
              <li><CheckCircle2 size={15} className="text-neon-bright" /> WORM & SEC 17a-4 Legal Holds</li>
              <li><CheckCircle2 size={15} className="text-neon-bright" /> FinOps Cost Forecaster & Ledger</li>
              <li><CheckCircle2 size={15} className="text-neon-bright" /> 99.99% Availability SLA</li>
            </ul>
            <button
              className="btn btn-primary btn-block btn-glow"
              onClick={() => handleOpenRegisterWithPlan('ENTERPRISE_PRO')}
            >
              Register with Enterprise Pro
            </button>
          </div>

          {/* PLAN 3 */}
          <div className="plan-card">
            <div className="plan-name">Cloud HyperScale</div>
            <div className="plan-tagline">Petabyte-scale multi-cloud enterprises</div>
            <div className="plan-price">
              <span className="price-amount">Custom</span>
              <span className="price-period">Volume pricing</span>
            </div>
            <ul className="plan-features">
              <li><CheckCircle2 size={15} className="text-neon-blue" /> Unlimited Petabytes Monitored</li>
              <li><CheckCircle2 size={15} className="text-neon-blue" /> Sub-Second Real-Time Telemetry</li>
              <li><CheckCircle2 size={15} className="text-neon-blue" /> Dedicated Cloud VPC Peering</li>
              <li><CheckCircle2 size={15} className="text-neon-blue" /> Custom Heuristic & ML Cost Models</li>
              <li><CheckCircle2 size={15} className="text-neon-blue" /> Multi-Region Cross-Cloud Replication</li>
              <li><CheckCircle2 size={15} className="text-neon-blue" /> 24/7 Dedicated Support Engineering</li>
            </ul>
            <button
              className="btn btn-secondary btn-block"
              onClick={() => handleOpenRegisterWithPlan('HYPERSCALE')}
            >
              Contact HyperScale Team
            </button>
          </div>
        </div>
      </section>

      {/* SECURITY & TRUST SECTION */}
      <section id="compliance" className="portal-section compliance-section">
        <div className="compliance-card">
          <div className="compliance-header">
            <Lock size={28} className="text-neon-blue" />
            <div>
              <h3>Enterprise Security & Regulatory Compliance</h3>
              <p>Designed from the ground up for strict data security and compliance requirements.</p>
            </div>
          </div>

          <div className="compliance-grid">
            <div className="comp-item">
              <ShieldCheck size={20} className="text-success" />
              <div>
                <strong>Zero Data-Plane Lock-in</strong>
                <p>Your objects stay in your buckets. We orchestrate metadata, policy decisions, and tiering.</p>
              </div>
            </div>

            <div className="comp-item">
              <ShieldCheck size={20} className="text-success" />
              <div>
                <strong>AES-256 KMS Encryption</strong>
                <p>All stored configurations and telemetry data are encrypted at rest and in transit.</p>
              </div>
            </div>

            <div className="comp-item">
              <ShieldCheck size={20} className="text-success" />
              <div>
                <strong>Immutable Audit Logging</strong>
                <p>Every policy change, approval, and migration is permanently recorded with user attribution.</p>
              </div>
            </div>

            <div className="comp-item">
              <ShieldCheck size={20} className="text-success" />
              <div>
                <strong>Strict Tenant Isolation</strong>
                <p>PostgreSQL schema boundaries and role-based permissions prevent cross-tenant data access.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER CALLOUT / CURRENT ORG LAUNCH BANNER */}
      <section className="portal-cta-banner">
        <div className="cta-banner-content">
          <div className="cta-titles">
            <span className="cta-sub">READY TO CONTROL YOUR STORAGE EXPENSES?</span>
            <h2 className="cta-main">Access Your Storage Management System Console</h2>
            <p className="cta-desc">
              {selectedOrg
                ? `Currently authenticated as ${selectedOrg.name}. Enter the console to review live inventory and run recommendations.`
                : 'Sign in with your organization account or register a new workspace to start optimizing.'}
            </p>
          </div>

          <div className="cta-buttons">
            <button
              className="btn btn-primary btn-lg btn-glow"
              onClick={() => setScreenMode('console')}
            >
              <Activity size={18} />
              <span>Enter Storage Console</span>
            </button>

            <button
              className="btn btn-secondary btn-lg"
              onClick={() => setRegisterModalOpen(true)}
            >
              <Building2 size={18} />
              <span>Register Storage Service</span>
            </button>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="portal-footer">
        <div className="footer-left">
          <HardDrive size={18} className="text-neon-blue" />
          <span>Storage Lifecycle Optimizer &copy; 2026. Enterprise Cloud SaaS Control Plane.</span>
        </div>
        <div className="footer-right">
          <button className="footer-link" onClick={() => setScreenMode('login')}>
            Switch Organization
          </button>
          <button className="footer-link" onClick={() => setScreenMode('console')}>
            Control Plane
          </button>
          <button className="footer-link" onClick={logout}>
            Sign Out
          </button>
        </div>
      </footer>

      {/* REGISTRATION MODAL */}
      <OrganizationRegisterModal
        isOpen={registerModalOpen}
        onClose={() => setRegisterModalOpen(false)}
        defaultPlan={selectedPlanForRegister}
      />
    </div>
  );
};
