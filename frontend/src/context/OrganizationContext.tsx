import React, { createContext, useContext, useState, useEffect } from 'react';
import { Organization, OrganizationRegistrationPayload } from '../types';
import { getOrganizations, registerOrganization, loginOrganization } from '../api/organizations';

export type ScreenMode = 'login' | 'portal' | 'console';

interface OrganizationContextType {
  organizations: Organization[];
  selectedOrg: Organization | null;
  setSelectedOrg: (org: Organization) => void;
  loading: boolean;
  error: string | null;
  refreshOrganizations: () => Promise<void>;
  // Auth & Session
  isLoggedIn: boolean;
  userEmail: string | null;
  userRole: string | null;
  currentPlan: string | null;
  screenMode: ScreenMode;
  setScreenMode: (mode: ScreenMode) => void;
  loginWithAccount: (slugOrEmail: string) => Promise<void>;
  quickLoginWithOrg: (org: Organization) => void;
  logout: () => void;
  registerAndLaunch: (payload: OrganizationRegistrationPayload) => Promise<Organization>;
}

const OrganizationContext = createContext<OrganizationContextType | undefined>(undefined);

const STORAGE_SESSION_KEY = 'storage_optimizer_org_session';

export const OrganizationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Auth & Session State
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(() => {
    return !!localStorage.getItem(STORAGE_SESSION_KEY);
  });
  const [userEmail, setUserEmail] = useState<string | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_SESSION_KEY);
      return saved ? JSON.parse(saved).userEmail : null;
    } catch {
      return null;
    }
  });
  const [userRole, setUserRole] = useState<string | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_SESSION_KEY);
      return saved ? JSON.parse(saved).userRole : null;
    } catch {
      return null;
    }
  });
  const [currentPlan, setCurrentPlan] = useState<string | null>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_SESSION_KEY);
      return saved ? JSON.parse(saved).currentPlan : null;
    } catch {
      return null;
    }
  });
  const [screenMode, setScreenMode] = useState<ScreenMode>(() => {
    const hasSession = !!localStorage.getItem(STORAGE_SESSION_KEY);
    return hasSession ? 'portal' : 'login';
  });

  const fetchOrgs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getOrganizations();
      setOrganizations(data);

      // Restore saved organization or default
      const saved = localStorage.getItem(STORAGE_SESSION_KEY);
      let targetOrg: Organization | null = null;
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          targetOrg = data.find((o) => o.id === parsed.orgId) || null;
        } catch {
          targetOrg = null;
        }
      }

      if (!targetOrg && data.length > 0) {
        targetOrg = data.find((o) => o.slug === 'demo-organization') || data[0];
      }

      if (targetOrg && !selectedOrg) {
        setSelectedOrg(targetOrg);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load organization tenants');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrgs();
  }, []);

  const persistSession = (org: Organization, email: string, role: string, plan: string) => {
    localStorage.setItem(
      STORAGE_SESSION_KEY,
      JSON.stringify({
        orgId: org.id,
        orgSlug: org.slug,
        orgName: org.name,
        userEmail: email,
        userRole: role,
        currentPlan: plan,
      })
    );
    setSelectedOrg(org);
    setIsLoggedIn(true);
    setUserEmail(email);
    setUserRole(role);
    setCurrentPlan(plan);
  };

  const loginWithAccount = async (slugOrEmail: string) => {
    setError(null);
    const res = await loginOrganization({ slug_or_email: slugOrEmail });
    const matchedOrg: Organization = {
      id: res.id,
      name: res.name,
      slug: res.slug,
      created_at: res.created_at,
    };
    persistSession(matchedOrg, res.user_email, res.role, res.plan);
    // After login, see the professional enterprise hero page
    setScreenMode('portal');
  };

  const quickLoginWithOrg = (org: Organization) => {
    const defaultEmail = `admin@${org.slug}.internal`;
    persistSession(org, defaultEmail, 'OWNER', 'ENTERPRISE_PRO');
    // After login, see the professional enterprise hero page
    setScreenMode('portal');
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_SESSION_KEY);
    setIsLoggedIn(false);
    setUserEmail(null);
    setUserRole(null);
    setCurrentPlan(null);
    setScreenMode('login');
  };

  const registerAndLaunch = async (payload: OrganizationRegistrationPayload): Promise<Organization> => {
    setError(null);
    const res = await registerOrganization(payload);
    const newOrg: Organization = {
      id: res.id,
      name: res.name,
      slug: res.slug,
      created_at: res.created_at,
    };
    // Update local list
    setOrganizations((prev) => [newOrg, ...prev]);
    persistSession(newOrg, res.admin_email, 'OWNER', res.plan);
    // After registering for storage service, get the storage management system service
    setScreenMode('console');
    return newOrg;
  };

  return (
    <OrganizationContext.Provider
      value={{
        organizations,
        selectedOrg,
        setSelectedOrg,
        loading,
        error,
        refreshOrganizations: fetchOrgs,
        isLoggedIn,
        userEmail,
        userRole,
        currentPlan,
        screenMode,
        setScreenMode,
        loginWithAccount,
        quickLoginWithOrg,
        logout,
        registerAndLaunch,
      }}
    >
      {children}
    </OrganizationContext.Provider>
  );
};

export const useOrganization = () => {
  const ctx = useContext(OrganizationContext);
  if (!ctx) {
    throw new Error('useOrganization must be used within an OrganizationProvider');
  }
  return ctx;
};

