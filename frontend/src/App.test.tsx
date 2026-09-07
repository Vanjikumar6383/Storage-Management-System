import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LoadingSpinner, EmptyState, ErrorState, KPICard, SafetyBanner } from './components/Common';
import { RecommendationDetailModal, ApprovalConfirmModal } from './components/Modals';

describe('Production Control-Plane UI Component Tests', () => {
  it('1. renders KPI card with correct values and titles', () => {
    render(<KPICard title="TOTAL STORAGE" value="142.5 GB" subtext="Active objects" variant="primary" />);
    expect(screen.getByText('TOTAL STORAGE')).toBeDefined();
    expect(screen.getByText('142.5 GB')).toBeDefined();
    expect(screen.getByText('Active objects')).toBeDefined();
  });

  it('2. renders loading state spinner and message', () => {
    render(<LoadingSpinner message="Loading storage inventory..." />);
    expect(screen.getByText('Loading storage inventory...')).toBeDefined();
  });

  it('3. renders error state with retry button', () => {
    const handleRetry = vi.fn();
    render(<ErrorState message="Unable to load recommendations." onRetry={handleRetry} />);
    expect(screen.getByText('Unable to load recommendations.')).toBeDefined();
    expect(screen.getByText('Retry')).toBeDefined();
  });

  it('4. renders empty state message', () => {
    render(<EmptyState title="No Records Found" message="No storage objects matched criteria." />);
    expect(screen.getByText('No Records Found')).toBeDefined();
    expect(screen.getByText('No storage objects matched criteria.')).toBeDefined();
  });

  it('5. renders prototype safety banner notice', () => {
    render(<SafetyBanner />);
    expect(screen.getByText('SAFETY MODE ACTIVE')).toBeDefined();
    expect(screen.getByText(/Recommendations never modify storage automatically/i)).toBeDefined();
  });

  it('6 & 7. renders recommendation detail modal with explainable evidence', () => {
    const mockRec: any = {
      id: 'rec-1',
      object_id: 'obj-1',
      object_key: 'logs/archive.zip',
      object_size_bytes: 10485760,
      age_days: 241,
      recommendation_type: 'ARCHIVE',
      current_storage_class: 'STANDARD',
      recommended_storage_class: 'ARCHIVE',
      reason: 'Cold object eligible for archival',
      evidence: { access_count_30d: 0, restore_count_90d: 0 },
      estimated_savings: 0.35,
      risk_level: 'LOW',
      status: 'PENDING',
      created_at: new Date().toISOString(),
    };

    render(
      <RecommendationDetailModal
        recommendation={mockRec}
        onClose={vi.fn()}
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onExecute={vi.fn()}
      />
    );

    expect(screen.getByText('Recommendation Explanation & Analysis')).toBeDefined();
    expect(screen.getByText('logs/archive.zip')).toBeDefined();
    expect(screen.getByText('Why was this recommendation generated?')).toBeDefined();
  });

  it('8 & 9. renders approval confirmation modal with warnings', () => {
    const mockRec: any = {
      id: 'rec-2',
      object_key: 'builds/output.tar',
      recommendation_type: 'DELETE_CANDIDATE',
      recommended_storage_class: 'DELETE_CANDIDATE',
      estimated_savings: 1.42,
    };

    render(<ApprovalConfirmModal recommendation={mockRec} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText('Confirm Delete Simulation')).toBeDefined();
    expect(screen.getByText(/Physical deletion is disabled in safety mode/i)).toBeDefined();
  });
});
