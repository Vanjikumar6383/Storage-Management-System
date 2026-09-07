export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface StorageByClass {
  storage_class: string;
  object_count: number;
  size_bytes: number;
  percentage: number;
  estimated_monthly_cost_usd: number;
}

export interface DashboardSummary {
  total_storage_bytes: number;
  total_objects: number;
  estimated_monthly_cost_usd: number;
  potential_monthly_savings_usd: number;
  approved_monthly_savings_usd: number;
  realized_monthly_savings_usd: number;
  pending_approvals_count: number;
  high_impact_approvals_count: number;
  active_legal_holds_count: number;
  storage_by_class: StorageByClass[];
  opportunities_by_type: Record<string, number>;
  recent_activity: AuditLog[];
  storage_provider?: string;
  storage_mode_label?: string;
  storage_mode_description?: string;
  safety_banner_text?: string;
  system_health?: Record<string, any>;
}

export interface StorageObject {
  id: string;
  object_key: string;
  object_size_bytes: number;
  storage_class: string;
  age_days: number;
  created_at: string;
  last_accessed_at?: string | null;
}

export interface Recommendation {
  id: string;
  object_id: string;
  object_key: string;
  object_size_bytes: number;
  age_days: number;
  recommendation_type: 'KEEP' | 'MOVE_TO_INFREQUENT_ACCESS' | 'ARCHIVE' | 'DELETE_CANDIDATE' | 'HOLD';
  current_storage_class: string;
  recommended_storage_class: string;
  reason: string;
  evidence: Record<string, any>;
  estimated_savings: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXECUTING' | 'EXECUTED' | 'EXECUTION_FAILED' | 'BLOCKED' | 'STALE';
  created_at: string;
  approval_status?: string;
  approval_decision?: string | null;
  override_reason?: string | null;
}

export interface ApprovalRequest {
  id: string;
  organization_id: string;
  recommendation_id: string;
  requested_action: string;
  status: string;
  decision?: string | null;
  override_reason?: string | null;
  requested_at: string;
  decided_at?: string | null;
}

export interface MigrationEvent {
  id: string;
  object_id: string;
  object_key: string;
  source_storage_class: string;
  destination_storage_class: string;
  status: 'PENDING' | 'IN_PROGRESS' | 'SUCCESS' | 'FAILED';
  rollback_status: 'NONE' | 'PENDING' | 'ROLLED_BACK' | 'FAILED';
  requested_at: string;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface AuditLog {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  outcome: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface RetentionPolicy {
  id: string;
  name: string;
  scope: 'ORGANIZATION' | 'ENVIRONMENT' | 'LOCATION' | 'OBJECT';
  retention_duration_days: number;
  priority: number;
  status: string;
  effective_date?: string | null;
}

export interface LegalHold {
  id: string;
  object_id: string;
  object_key: string;
  status: 'ACTIVE' | 'RELEASED';
  reason_reference: string;
  created_at: string;
  released_at?: string | null;
}

export interface Environment {
  id: string;
  name: string;
  environment_type: string;
  object_count: number;
  total_size_bytes: number;
  estimated_monthly_cost_usd: number;
}

export interface ExecutionResult {
  status: string;
  recommendation_id: string;
  object_id: string;
  migration_id?: string | null;
  reasons: string[];
}

export interface RollbackResult {
  status: string;
  migration_id: string;
  rollback_event_id: string;
  restored_storage_class: string;
  reasons: string[];
}

export interface OrganizationRegistrationPayload {
  name: string;
  slug?: string;
  admin_email: string;
  plan: 'DEVELOPMENT_FREE' | 'ENTERPRISE_PRO' | 'HYPERSCALE';
  provider: 'AWS_S3' | 'LOCAL_S3_COMPATIBLE' | 'AZURE_BLOB' | 'GOOGLE_CLOUD_STORAGE';
  bucket_name?: string;
  region?: string;
  environment_name?: string;
  seed_sample_data: boolean;
}

export interface OrganizationRegistrationResult {
  id: string;
  name: string;
  slug: string;
  admin_email: string;
  plan: string;
  provider: string;
  environment_id: string;
  location_id: string;
  created_at: string;
  message: string;
  session_token: string;
}

export interface OrganizationLoginPayload {
  slug_or_email: string;
}

export interface OrganizationLoginResult {
  id: string;
  name: string;
  slug: string;
  user_email: string;
  role: string;
  plan: string;
  provider: string;
  created_at: string;
  session_token: string;
  environments_count: number;
  objects_count: number;
  total_storage_bytes: number;
}

export interface OrganizationServiceDetails {
  id: string;
  name: string;
  slug: string;
  plan: string;
  status: string;
  limits: Record<string, any>;
  provider: string;
  features_enabled: string[];
  environments_count: number;
  locations_count: number;
  objects_count: number;
  total_storage_bytes: number;
  monthly_cost_usd: number;
  potential_monthly_savings_usd: number;
}

export interface ServicePlanTier {
  id: 'DEVELOPMENT_FREE' | 'ENTERPRISE_PRO' | 'HYPERSCALE';
  name: string;
  tagline: string;
  price: string;
  period: string;
  features: string[];
  highlight?: boolean;
  cta: string;
}

