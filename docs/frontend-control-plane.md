# Production Control-Plane Frontend Specification

## Overview
The **Storage Lifecycle Optimizer Control-Plane UI** provides Storage Administrators, DevOps Engineers, and FinOps operators with an intuitive, desktop-first, multi-tenant control surface for evaluating storage inventory, inspecting explainable lifecycle recommendations, managing human approvals, executing zero-download storage migrations, and initiating rollback routines.

---

## 1. Page Architecture & Navigation Layout

The application utilizes a dark glassmorphic SaaS control-plane layout featuring a top header with multi-tenant organization switching, safety mode boundary alerts, and sidebar navigation:

- **Overview Dashboard (`OverviewPage.tsx`)**: Displays top KPI metrics (Total Storage Bytes/GB, Total Object Count, Estimated Monthly Cost USD, Potential Monthly Savings USD), storage distribution by class (`STANDARD`, `INFREQUENT_ACCESS`, `ARCHIVE`), lifecycle opportunity counts, pending approval queue status, and recent audit trail events.
- **Savings View (`SavingsPage.tsx`)**: Displays a dedicated savings realization funnel maintaining strict distinction between **Potential (Estimated)**, **Approved (Awaiting Execution)**, and **Realized (Executed)** monthly cost savings.
- **Recommendations Page (`RecommendationsPage.tsx`)**: Interactive searchable and filterable table (Recommendation Type, Risk Level, Approval Status) with direct links to explainable evidence drilldowns.
- **Approvals Queue (`ApprovalsPage.tsx`)**: Categorizes pending recommendations into **High-Impact Queue** (`ARCHIVE`, `DELETE_CANDIDATE`) requiring explicit confirmation and **Standard Queue** (`MOVE_TO_INFREQUENT_ACCESS`, `KEEP`).
- **Migrations & Rollback (`MigrationsPage.tsx`)**: Displays execution lineage for provider migrations, current status (`SUCCESS`, `FAILED`), rollback status (`ROLLED_BACK`), and interactive `Rollback` trigger buttons.
- **Objects Explorer (`ObjectsPage.tsx`)**: Filterable object metadata inventory with search, size, age, current storage class, and last access timestamp.
- **Environments View (`EnvironmentsPage.tsx`)**: Development environment storage allocation and cost metrics.
- **Policies & Legal Holds (`PoliciesPage.tsx`)**: Retention policy priorities, duration rules, and active legal hold warnings displaying absolute override blocking.
- **Audit Log (`AuditLogPage.tsx`)**: Searchable immutable governance audit log.

---

## 2. API Integration & Multi-Tenant Context

All API calls are routed through a typed API client infrastructure in `frontend/src/api/`:

- **Client Infrastructure**: `client.ts` automatically injects the active tenant `organization_id` header/query parameter onto all HTTP requests.
- **Tenant Context (`OrganizationContext.tsx`)**: React Context provider managing tenant switching. Changing tenant automatically refetches metrics across all active views without page reloads.

---

## 3. Explainable Evidence & Safety UX

When reviewing recommendations in the **Recommendation Detail Modal** (`RecommendationDetailModal.tsx`):
- **Object Information**: Key, Size, Age, Current Storage Class.
- **System Recommendation & Target Class**: Visual transition indicator (`STANDARD` $\rightarrow$ `ARCHIVE`).
- **Why? Checklist**: Displays empirical evidence (Object Age in days, 30-day payload read count, 90-day restore frequency, Retention status, Legal hold status).
- **Evaluated Safety Rules**: Rule pass/fail statuses (`AGE-001`, `ACCESS-002`, `RESTORE-001`, `LEGAL-001`).
- **Cost Analysis**: Current cost vs Recommended cost vs Net monthly savings.
- **Safety Boundary Notice**: `SAFETY MODE ACTIVE — Physical deletion disabled in dry-run safety mode. Human approval required for all actions.`

---

## 4. Execution & Rollback Workflows

- **Pre-Execution Safety Gate UX**: Executing an approved recommendation opens `ExecutionStatusModal.tsx`, displaying live pre-execution safety gate checks (`✓ Object exists`, `✓ Tenant verified`, `✓ Retention verified`, `✓ Legal hold cleared`, `✓ Storage class verified`, `✓ Recommendation current`).
- **Rollback UX**: Clicking `Rollback` on a completed migration prompts for an operator reason, invokes `POST /api/v1/migrations/{id}/rollback`, updates the DB storage class back to `source_storage_class`, and disables further rollbacks.

---

## 5. Verification & Testing

- **Unit Testing**: Vitest test suite (`npm run test`) passes 100%.
- **Production Build**: Vite + TypeScript compilation (`npm run build`) builds `dist/` cleanly without warnings.
