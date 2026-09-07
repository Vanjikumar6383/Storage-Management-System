import React, { useState } from 'react';
import { OrganizationProvider, useOrganization } from './context/OrganizationContext';
import { Layout, PageTab } from './components/Layout';
import { OverviewPage, SavingsPage } from './pages/OverviewAndSavings';
import { RecommendationsPage, ApprovalsPage } from './pages/RecommendationsAndApprovals';
import { MigrationsPage, ObjectsPage, EnvironmentsPage, PoliciesPage, AuditLogPage } from './pages/RemainingPages';
import { ExperimentPage } from './pages/ExperimentPage';
import { OrganizationLogin } from './pages/OrganizationLogin';
import { OrganizationPortal } from './pages/OrganizationPortal';

const MainApp: React.FC = () => {
  const { screenMode } = useOrganization();
  const [activeTab, setActiveTab] = useState<PageTab>('overview');

  if (screenMode === 'login') {
    return <OrganizationLogin />;
  }

  if (screenMode === 'portal') {
    return <OrganizationPortal />;
  }

  return (
    <Layout activeTab={activeTab} setActiveTab={setActiveTab}>
      {activeTab === 'overview' && <OverviewPage onSelectRecommendation={() => setActiveTab('recommendations')} />}
      {activeTab === 'savings' && <SavingsPage />}
      {activeTab === 'recommendations' && <RecommendationsPage />}
      {activeTab === 'approvals' && <ApprovalsPage />}
      {activeTab === 'migrations' && <MigrationsPage />}
      {activeTab === 'objects' && <ObjectsPage />}
      {activeTab === 'environments' && <EnvironmentsPage />}
      {activeTab === 'policies' && <PoliciesPage />}
      {activeTab === 'audit' && <AuditLogPage />}
      {activeTab === 'experiment' && <ExperimentPage />}
    </Layout>
  );
};

export const App: React.FC = () => {
  return (
    <OrganizationProvider>
      <MainApp />
    </OrganizationProvider>
  );
};


export default App;
