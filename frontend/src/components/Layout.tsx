import React, { useState } from 'react';
import { useOrganization } from '../context/OrganizationContext';
import { SafetyBanner } from './Common';
import { LinkLocalStorageModal } from './LinkLocalStorageModal';
import {
  LayoutDashboard,
  PiggyBank,
  Sparkles,
  CheckSquare,
  ArrowLeftRight,
  Database,
  Layers,
  ShieldCheck,
  FileSpreadsheet,
  Building2,
  HardDrive,
  FolderOpen,
} from 'lucide-react';

export type PageTab =
  | 'overview'
  | 'savings'
  | 'recommendations'
  | 'approvals'
  | 'migrations'
  | 'objects'
  | 'environments'
  | 'policies'
  | 'audit'
  | 'experiment';

interface LayoutProps {
  activeTab: PageTab;
  setActiveTab: (tab: PageTab) => void;
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ activeTab, setActiveTab, children }) => {
  const { organizations, selectedOrg, setSelectedOrg, setScreenMode, logout } = useOrganization();
  const [showLinkLocalModal, setShowLinkLocalModal] = useState(false);

  const navItems = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={18} /> },
    { id: 'savings', label: 'Savings View', icon: <PiggyBank size={18} /> },
    { id: 'recommendations', label: 'Recommendations', icon: <Sparkles size={18} /> },
    { id: 'approvals', label: 'Approvals Queue', icon: <CheckSquare size={18} /> },
    { id: 'migrations', label: 'Migrations & Rollback', icon: <ArrowLeftRight size={18} /> },
    { id: 'objects', label: 'Objects Explorer', icon: <Database size={18} /> },
    { id: 'environments', label: 'Environments', icon: <Layers size={18} /> },
    { id: 'policies', label: 'Policies & Legal Holds', icon: <ShieldCheck size={18} /> },
    { id: 'audit', label: 'Audit Log', icon: <FileSpreadsheet size={18} /> },
    { id: 'experiment', label: 'Synthetic Benchmark', icon: <Building2 size={18} /> },
  ];

  return (
    <div className="app-container">
      {/* LINK LOCAL STORAGE MODAL */}
      <LinkLocalStorageModal
        isOpen={showLinkLocalModal}
        onClose={() => setShowLinkLocalModal(false)}
        onSuccess={() => setActiveTab('objects')}
      />

      {/* HEADER */}
      <header className="app-header">
        <div className="header-brand">
          <HardDrive className="brand-logo" />
          <div className="brand-title">
            <h2>Storage Optimizer</h2>
            <span className="brand-subtitle">Production Control Plane</span>
          </div>
        </div>

        <div className="header-actions">
          <button
            className="btn btn-primary btn-sm header-link-btn"
            onClick={() => setShowLinkLocalModal(true)}
            title="Link local directory to index metadata and generate ML recommendations"
          >
            <FolderOpen size={15} />
            <span>Link Local Storage</span>
          </button>

          <button
            className="btn btn-secondary btn-sm header-portal-btn"
            onClick={() => setScreenMode('portal')}
            title="Return to Enterprise Hero Page & Services"
          >
            <Building2 size={15} />
            <span>Organization Portal</span>
          </button>

          <div className="org-selector-wrapper">
            <Building2 className="org-icon" />
            <select
              className="org-select-input"
              value={selectedOrg?.id || ''}
              onChange={(e) => {
                const found = organizations.find((o) => o.id === e.target.value);
                if (found) setSelectedOrg(found);
              }}
              aria-label="Select Organization Tenant"
            >
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name} ({org.slug})
                </option>
              ))}
            </select>
          </div>

          <button
            className="btn btn-ghost btn-sm header-logout-btn"
            onClick={logout}
            title="Sign out of Organization"
            aria-label="Sign out"
          >
            <span className="logout-text">Sign Out</span>
          </button>
        </div>
      </header>

      {/* SAFETY BANNER */}
      <SafetyBanner />

      {/* BODY */}
      <div className="app-body">
        {/* SIDEBAR */}
        <aside className="app-sidebar" role="navigation" aria-label="Main Navigation">
          <nav className="nav-menu">
            {navItems.map((item) => (
              <button
                key={item.id}
                className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
                onClick={() => setActiveTab(item.id as PageTab)}
                aria-current={activeTab === item.id ? 'page' : undefined}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </button>
            ))}
          </nav>
        </aside>

        {/* MAIN CONTENT */}
        <main className="app-main-content" role="main">
          {children}
        </main>
      </div>
    </div>
  );
};
