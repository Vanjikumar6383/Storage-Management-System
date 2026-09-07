"""
Control Plane Dashboard Data & Overview Endpoints.
Provides aggregated SaaS control plane metrics, storage summaries, and queries.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import (
    Organization,
    User,
    OrganizationMembership,
    RoleEnum,
    Subscription,
    StorageConnection,
    StorageProviderEnum,
    Environment,
    StorageLocation,
    StorageObject,
    Recommendation,
    ApprovalRequest,
    MigrationEvent,
    AuditLog,
    RetentionPolicy,
    LegalHold,
)
from app.core.recommendation_config import RECOMMENDATION_THRESHOLDS
from app.services.cost_estimation import CostEstimationService

router = APIRouter(prefix="/organizations", tags=["Dashboard & Control Plane Overview"])


class OrganizationOutSchema(BaseModel):
    id: UUID
    name: str
    slug: str
    created_at: str

    class Config:
        from_attributes = True


class OrganizationRegistrationSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    admin_email: str = Field(..., min_length=5, max_length=255)
    plan: str = Field(default="DEVELOPMENT_FREE")
    provider: str = Field(default="LOCAL_S3_COMPATIBLE")
    bucket_name: Optional[str] = None
    region: Optional[str] = "us-east-1"
    environment_name: Optional[str] = "production"
    seed_sample_data: bool = False


class OrganizationRegistrationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    admin_email: str
    plan: str
    provider: str
    environment_id: str
    location_id: str
    created_at: str
    message: str
    session_token: str


class OrganizationLoginSchema(BaseModel):
    slug_or_email: str = Field(..., min_length=2)


class OrganizationLoginResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    user_email: str
    role: str
    plan: str
    provider: str
    created_at: str
    session_token: str
    environments_count: int
    objects_count: int
    total_storage_bytes: int


class OrganizationServiceDetailsResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    status: str
    limits: Dict[str, Any]
    provider: str
    features_enabled: List[str]
    environments_count: int
    locations_count: int
    objects_count: int
    total_storage_bytes: int
    monthly_cost_usd: float
    potential_monthly_savings_usd: float


@router.post("/register", response_model=OrganizationRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_organization(
    payload: OrganizationRegistrationSchema,
    db: Session = Depends(get_db),
):
    """
    Register a new organization tenant for the Storage Management System.
    Provisions tenant organization, admin user, membership, subscription plan,
    primary storage connection, production environment, storage location, and sample telemetry data.
    """
    # 1. Format and sanitize slug
    raw_slug = payload.slug.strip() if payload.slug else payload.name.strip()
    slug = re.sub(r"[^a-z0-9\-]+", "-", raw_slug.lower()).strip("-")
    if not slug:
        slug = f"org-{uuid.uuid4().hex[:8]}"

    # Check slug availability
    existing_org = db.query(Organization).filter_by(slug=slug).first()
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization identifier '{slug}' is already registered. Please choose another name or slug.",
        )

    # 2. Storage Provider mapping
    valid_providers = [p.value for p in StorageProviderEnum]
    provider_str = payload.provider.upper() if payload.provider else "LOCAL_S3_COMPATIBLE"
    if provider_str not in valid_providers:
        provider_str = "LOCAL_S3_COMPATIBLE"
    provider_enum = StorageProviderEnum(provider_str)

    # 3. Create Organization
    org = Organization(name=payload.name.strip(), slug=slug)
    db.add(org)
    db.flush()

    # 4. User and Membership
    user_email = payload.admin_email.strip().lower()
    user = db.query(User).filter_by(email=user_email).first()
    if not user:
        user = User(email=user_email, is_active="ACTIVE")
        db.add(user)
        db.flush()

    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role=RoleEnum.OWNER,
    )
    db.add(membership)

    # 5. Plan and Subscription Limits
    plan_name = payload.plan.upper()
    if plan_name not in ["DEVELOPMENT_FREE", "ENTERPRISE_PRO", "HYPERSCALE"]:
        plan_name = "DEVELOPMENT_FREE"

    plan_limits = {
        "DEVELOPMENT_FREE": {"max_storage_gb": 500, "tiering_speed": "STANDARD", "compliance_locks": False, "sla": "99.9%"},
        "ENTERPRISE_PRO": {"max_storage_gb": 50000, "tiering_speed": "EXPEDITED", "compliance_locks": True, "sla": "99.99%"},
        "HYPERSCALE": {"max_storage_gb": 1000000, "tiering_speed": "REAL_TIME", "compliance_locks": True, "sla": "99.999%"},
    }

    sub = Subscription(
        organization_id=org.id,
        plan=plan_name,
        status="ACTIVE",
        limits=plan_limits.get(plan_name, plan_limits["DEVELOPMENT_FREE"]),
    )
    db.add(sub)

    # 6. Storage Connection
    conn_name = f"{payload.name.strip()} Primary Storage"
    storage_conn = StorageConnection(
        organization_id=org.id,
        name=conn_name,
        provider=provider_enum,
        credential_reference="env:AUTOMATED_STORAGE_CREDENTIAL",
        config={"region": payload.region or "us-east-1"},
    )
    db.add(storage_conn)
    db.flush()

    # 7. Primary Environment
    env_name = payload.environment_name.strip() if payload.environment_name else "production"
    primary_env = Environment(
        organization_id=org.id,
        storage_connection_id=storage_conn.id,
        name=env_name,
        environment_type="PRODUCTION",
        status="ACTIVE",
    )
    db.add(primary_env)
    db.flush()

    # 8. Storage Location (Bucket)
    bucket_name = payload.bucket_name.strip() if payload.bucket_name else f"{slug}-primary-data"
    storage_loc = StorageLocation(
        organization_id=org.id,
        storage_connection_id=storage_conn.id,
        name=bucket_name,
        region=payload.region or "us-east-1",
    )
    db.add(storage_loc)
    db.flush()

    # 9. Deterministic Sample Telemetry Data
    if payload.seed_sample_data:
        ref_time = datetime.now(timezone.utc)
        starter_objects = [
            ("production/analytics_events.parquet", 25 * 1024 * 1024 * 1024, "STANDARD", 15, 120, 280),
            ("models/deep_learning_v3.weights", 85 * 1024 * 1024 * 1024, "STANDARD", 110, 0, 12),
            ("backups/database_q4_snapshot.tar.gz", 320 * 1024 * 1024 * 1024, "STANDARD", 220, 0, 0),
            ("syslog/ingress_gateway_2025.log", 40 * 1024 * 1024 * 1024, "INFREQUENT_ACCESS", 160, 2, 5),
            ("cache/stale_ci_pipeline_builds.tmp", 18 * 1024 * 1024 * 1024, "STANDARD", 340, 0, 0),
            ("compliance/annual_financial_audit.pdf", 6 * 1024 * 1024 * 1024, "STANDARD", 95, 1, 2),
        ]

        for key, size, s_class, age_days, acc_30, acc_90 in starter_objects:
            created_ts = ref_time - timedelta(days=age_days)
            st_obj = StorageObject(
                organization_id=org.id,
                storage_location_id=storage_loc.id,
                environment_id=primary_env.id,
                object_key=key,
                object_size_bytes=size,
                storage_class=s_class,
                created_at=created_ts,
                last_modified_at=created_ts,
                last_accessed_at=ref_time - timedelta(days=1) if acc_30 > 0 else (ref_time - timedelta(days=45) if acc_90 > 0 else None),
                access_count_30d=acc_30,
                access_count_90d=acc_90,
            )
            db.add(st_obj)
            db.flush()

            if "compliance" in key:
                db.add(LegalHold(
                    organization_id=org.id,
                    object_id=st_obj.id,
                    reason_reference="SEC Rule 17a-4 Regulatory Compliance Hold",
                    status="ACTIVE",
                ))

        # Initial retention policy
        db.add(RetentionPolicy(
            organization_id=org.id,
            name="Default 90-Day Enterprise Lifecycle Policy",
            retention_duration_days=90,
            priority=1,
            status="ACTIVE",
            effective_date=ref_time,
        ))

    # 10. Audit Log record
    db.add(AuditLog(
        organization_id=org.id,
        action="ORGANIZATION_REGISTERED",
        resource_type="ORGANIZATION",
        resource_id=str(org.id),
        actor_id=user.id,
        outcome="SUCCESS",
        metadata_json={
            "plan": plan_name,
            "provider": provider_str,
            "admin_email": user_email,
            "seeded_sample_data": payload.seed_sample_data,
        },
    ))

    db.commit()

    session_token = f"sess_{org.id.hex[:12]}_{uuid.uuid4().hex[:8]}"

    return OrganizationRegistrationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        admin_email=user_email,
        plan=plan_name,
        provider=provider_str,
        environment_id=str(primary_env.id),
        location_id=str(storage_loc.id),
        created_at=org.created_at.isoformat(),
        message="Organization successfully registered for Storage Management System.",
        session_token=session_token,
    )


@router.post("/login", response_model=OrganizationLoginResponse)
def login_organization(
    payload: OrganizationLoginSchema,
    db: Session = Depends(get_db),
):
    """
    Authenticate an organization via organization slug, workspace name, or administrator email.
    Returns tenant profile, permissions, active subscription plan, and system metrics preview.
    """
    query_term = payload.slug_or_email.strip().lower()

    # Match by slug or name
    org = db.query(Organization).filter(
        (Organization.slug == query_term) | (func.lower(Organization.name) == query_term)
    ).first()

    user_email = ""
    role = "OWNER"

    if not org:
        # Match by user email
        user = db.query(User).filter(func.lower(User.email) == query_term).first()
        if user:
            membership = db.query(OrganizationMembership).filter_by(user_id=user.id).first()
            if membership:
                org = db.query(Organization).filter_by(id=membership.organization_id).first()
                user_email = user.email
                role = membership.role.value if hasattr(membership.role, "value") else str(membership.role)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active organization found for '{payload.slug_or_email}'. Please check credentials or register.",
        )

    if not user_email:
        # Retrieve primary membership user
        mem = db.query(OrganizationMembership).filter_by(organization_id=org.id).first()
        if mem:
            u = db.query(User).filter_by(id=mem.user_id).first()
            if u:
                user_email = u.email
            role = mem.role.value if hasattr(mem.role, "value") else str(mem.role)
        else:
            user_email = f"admin@{org.slug}.internal"

    sub = db.query(Subscription).filter_by(organization_id=org.id).first()
    plan_name = sub.plan if sub else "DEVELOPMENT_FREE"

    conn = db.query(StorageConnection).filter_by(organization_id=org.id).first()
    provider_name = conn.provider.value if (conn and hasattr(conn.provider, "value")) else (str(conn.provider) if conn else "LOCAL_S3_COMPATIBLE")

    env_count = db.query(func.count(Environment.id)).filter(Environment.organization_id == org.id).scalar() or 0
    obj_count = db.query(func.count(StorageObject.id)).filter(StorageObject.organization_id == org.id).scalar() or 0
    tot_bytes = db.query(func.coalesce(func.sum(StorageObject.object_size_bytes), 0)).filter(StorageObject.organization_id == org.id).scalar() or 0

    session_token = f"sess_{org.id.hex[:12]}_{uuid.uuid4().hex[:8]}"

    return OrganizationLoginResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        user_email=user_email,
        role=role,
        plan=plan_name,
        provider=provider_name,
        created_at=org.created_at.isoformat(),
        session_token=session_token,
        environments_count=int(env_count),
        objects_count=int(obj_count),
        total_storage_bytes=int(tot_bytes),
    )


@router.get("/{organization_id}/service-details", response_model=OrganizationServiceDetailsResponse)
def get_organization_service_details(
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Fetch comprehensive service provisioning, subscription, feature flags, and storage telemetry status.
    """
    org = db.query(Organization).filter_by(id=organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")

    sub = db.query(Subscription).filter_by(organization_id=organization_id).first()
    plan_name = sub.plan if sub else "DEVELOPMENT_FREE"
    sub_status = sub.status if sub else "ACTIVE"
    sub_limits = sub.limits if sub and sub.limits else {"max_storage_gb": 1000}

    conn = db.query(StorageConnection).filter_by(organization_id=organization_id).first()
    provider_name = conn.provider.value if (conn and hasattr(conn.provider, "value")) else (str(conn.provider) if conn else "LOCAL_S3_COMPATIBLE")

    features = [
        "AUTONOMOUS_LIFECYCLE_TIERING",
        "REALTIME_TELEMETRY_ENGINE",
        "ZERO_DOWNTIME_MIGRATIONS",
        "FINOPS_COST_ANALYTICS",
        "RETENTION_AND_LEGAL_HOLDS",
        "MULTI_CLOUD_CONNECTIVITY",
    ]
    if plan_name in ["ENTERPRISE_PRO", "HYPERSCALE"]:
        features.extend([
            "COMPLIANCE_LOCK_ENFORCEMENT",
            "PRIORITY_RESTORE_SLA",
            "CROSS_REGION_REPLICATION",
        ])
    if plan_name == "HYPERSCALE":
        features.extend([
            "DEDICATED_VPC_PEERING",
            "CUSTOM_HEURISTIC_MODELS",
            "24_7_WHITEGLOVE_SLA",
        ])

    env_count = db.query(func.count(Environment.id)).filter(Environment.organization_id == organization_id).scalar() or 0
    loc_count = db.query(func.count(StorageLocation.id)).filter(StorageLocation.organization_id == organization_id).scalar() or 0
    obj_count = db.query(func.count(StorageObject.id)).filter(StorageObject.organization_id == organization_id).scalar() or 0
    tot_bytes = db.query(func.coalesce(func.sum(StorageObject.object_size_bytes), 0)).filter(StorageObject.organization_id == organization_id).scalar() or 0

    cost_service = CostEstimationService()
    tot_gb = float(tot_bytes) / (1024.0 * 1024.0 * 1024.0)
    monthly_cost = round(tot_gb * cost_service.get_unit_cost_per_gb_month("STANDARD"), 2)

    pot_savings = db.query(func.coalesce(func.sum(Recommendation.estimated_savings), 0.0)).filter(Recommendation.organization_id == organization_id).scalar() or 0.0

    return OrganizationServiceDetailsResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        plan=plan_name,
        status=sub_status,
        limits=sub_limits,
        provider=provider_name,
        features_enabled=features,
        environments_count=int(env_count),
        locations_count=int(loc_count),
        objects_count=int(obj_count),
        total_storage_bytes=int(tot_bytes),
        monthly_cost_usd=monthly_cost,
        potential_monthly_savings_usd=round(float(pot_savings), 2),
    )


@router.get("", response_model=List[OrganizationOutSchema])
def list_organizations(db: Session = Depends(get_db)):
    """List available tenant organizations."""
    orgs = db.query(Organization).order_by(Organization.name).all()
    return [
        OrganizationOutSchema(
            id=o.id,
            name=o.name,
            slug=o.slug,
            created_at=o.created_at.isoformat(),
        )
        for o in orgs
    ]
class DashboardSummarySchema(BaseModel):
    total_storage_bytes: int
    total_objects: int
    estimated_monthly_cost_usd: float
    potential_monthly_savings_usd: float
    approved_monthly_savings_usd: float
    realized_monthly_savings_usd: float
    pending_approvals_count: int
    high_impact_approvals_count: int
    active_legal_holds_count: int
    storage_by_class: List[Dict[str, Any]]
    opportunities_by_type: Dict[str, int]
    recent_activity: List[Dict[str, Any]]
    storage_provider: str = Field(default="LOCAL_S3_COMPATIBLE")
    storage_mode_label: str = Field(default="DEMO STORAGE")
    storage_mode_description: str = Field(default="Demo environment — no real cloud storage connected.")
    safety_banner_text: str = Field(default="Demo Storage Mode — lifecycle actions operate on demo storage only.")
    system_health: Dict[str, Any] = Field(default_factory=dict)


@router.get("/{organization_id}/dashboard-summary", response_model=DashboardSummarySchema)
def get_dashboard_summary(
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    """Fetch overview KPIs, storage class distribution, and governance opportunities."""
    org = db.query(Organization).filter_by(id=organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")

    cost_service = CostEstimationService()

    # Total storage & objects
    tot_bytes = db.query(func.coalesce(func.sum(StorageObject.object_size_bytes), 0)).filter(StorageObject.organization_id == organization_id).scalar()
    tot_objects = db.query(func.count(StorageObject.id)).filter(StorageObject.organization_id == organization_id).scalar()

    # Storage by class
    class_rows = (
        db.query(StorageObject.storage_class, func.count(StorageObject.id), func.coalesce(func.sum(StorageObject.object_size_bytes), 0))
        .filter(StorageObject.organization_id == organization_id)
        .group_by(StorageObject.storage_class)
        .all()
    )

    storage_by_class = []
    tot_cost = 0.0
    for s_class, count, bytes_sum in class_rows:
        unit_cost = cost_service.get_unit_cost_per_gb_month(s_class)
        size_gb = float(bytes_sum) / (1024.0 * 1024.0 * 1024.0)
        class_cost = round(size_gb * unit_cost, 4)
        tot_cost += class_cost
        pct = round((float(bytes_sum) / float(tot_bytes) * 100.0), 2) if tot_bytes > 0 else 0.0
        storage_by_class.append({
            "storage_class": s_class,
            "object_count": count,
            "size_bytes": bytes_sum,
            "percentage": pct,
            "estimated_monthly_cost_usd": class_cost,
        })

    # Recommendations & Savings breakdown
    recs = db.query(Recommendation).filter(Recommendation.organization_id == organization_id).all()
    potential_savings = 0.0
    approved_savings = 0.0
    realized_savings = 0.0
    opportunities: Dict[str, int] = {"KEEP": 0, "MOVE_TO_INFREQUENT_ACCESS": 0, "ARCHIVE": 0, "DELETE_CANDIDATE": 0, "HOLD": 0}

    for r in recs:
        rec_type = r.recommendation_type.value if hasattr(r.recommendation_type, "value") else str(r.recommendation_type)
        opportunities[rec_type] = opportunities.get(rec_type, 0) + 1
        savings = float(r.estimated_savings)
        potential_savings += savings
        if r.status in ("APPROVED", "EXECUTION_PENDING", "EXECUTING"):
            approved_savings += savings
        elif r.status == "EXECUTED":
            realized_savings += savings

    # Approvals & Legal holds
    pending_appr = db.query(func.count(ApprovalRequest.id)).filter(ApprovalRequest.organization_id == organization_id, ApprovalRequest.status == "PENDING").scalar()
    high_impact_appr = (
        db.query(func.count(ApprovalRequest.id))
        .join(Recommendation, ApprovalRequest.recommendation_id == Recommendation.id)
        .filter(
            ApprovalRequest.organization_id == organization_id,
            ApprovalRequest.status == "PENDING",
            Recommendation.recommendation_type.in_(["ARCHIVE", "DELETE_CANDIDATE"]),
        )
        .scalar()
    )
    active_holds = db.query(func.count(LegalHold.id)).filter(LegalHold.organization_id == organization_id, LegalHold.status == "ACTIVE").scalar()

    # Recent Audit Activity
    recent_audits = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(10)
        .all()
    )
    recent_activity = [
        {
            "id": str(a.id),
            "action": a.action,
            "resource_type": a.resource_type,
            "resource_id": a.resource_id,
            "outcome": a.outcome,
            "timestamp": a.timestamp.isoformat(),
            "metadata": a.metadata_json,
        }
        for a in recent_audits
    ]

    from app.core.config import get_storage_settings, get_app_config
    settings = get_storage_settings()
    app_cfg = get_app_config()
    is_aws = settings.provider == "AWS_S3"

    mode_label = "AWS S3" if is_aws else "DEMO STORAGE"
    mode_desc = "Connected to configured AWS provider." if is_aws else "Demo environment — no real cloud storage connected."
    banner_text = "Production Cloud Mode — lifecycle actions can modify real AWS S3 objects." if is_aws else "Demo Storage Mode — lifecycle actions operate on demo storage only."

    sys_health = {
        "application": "HEALTHY",
        "database": "HEALTHY",
        "storage_provider": mode_label,
        "storage_status": "HEALTHY",
        "environment": app_cfg.app_env,
        "last_sync": "Active",
        "api_health": "HEALTHY",
    }

    return DashboardSummarySchema(
        total_storage_bytes=int(tot_bytes),
        total_objects=int(tot_objects),
        estimated_monthly_cost_usd=round(tot_cost, 2),
        potential_monthly_savings_usd=round(potential_savings, 2),
        approved_monthly_savings_usd=round(approved_savings, 2),
        realized_monthly_savings_usd=round(realized_savings, 2),
        pending_approvals_count=int(pending_appr),
        high_impact_approvals_count=int(high_impact_appr),
        active_legal_holds_count=int(active_holds),
        storage_by_class=storage_by_class,
        opportunities_by_type=opportunities,
        recent_activity=recent_activity,
        storage_provider=settings.provider,
        storage_mode_label=mode_label,
        storage_mode_description=mode_desc,
        safety_banner_text=banner_text,
        system_health=sys_health,
    )


@router.get("/{organization_id}/objects")
def list_objects(
    organization_id: UUID,
    search: Optional[str] = None,
    storage_class: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List storage objects with metadata and filtering."""
    query = db.query(StorageObject).filter(StorageObject.organization_id == organization_id)
    if search:
        query = query.filter(StorageObject.object_key.ilike(f"%{search}%"))
    if storage_class and storage_class != "ALL":
        query = query.filter(StorageObject.storage_class == storage_class)

    total = query.count()
    objs = query.order_by(StorageObject.created_at.desc()).offset(offset).limit(limit).all()

    out = []
    ref_time = datetime.now(timezone.utc)
    for o in objs:
        created = o.created_at if o.created_at.tzinfo else o.created_at.replace(tzinfo=timezone.utc)
        age_days = (ref_time - created).days
        out.append({
            "id": str(o.id),
            "object_key": o.object_key,
            "object_size_bytes": o.object_size_bytes,
            "storage_class": o.storage_class,
            "age_days": age_days,
            "created_at": o.created_at.isoformat(),
            "last_accessed_at": o.last_accessed_at.isoformat() if o.last_accessed_at else None,
        })
    return {"total": total, "items": out}


@router.get("/{organization_id}/environments")
def list_environments(organization_id: UUID, db: Session = Depends(get_db)):
    """List development environments with storage usage stats."""
    envs = db.query(Environment).filter_by(organization_id=organization_id).all()
    out = []
    cost_service = CostEstimationService()

    for env in envs:
        obj_count = db.query(func.count(StorageObject.id)).filter(StorageObject.environment_id == env.id).scalar()
        size_bytes = db.query(func.coalesce(func.sum(StorageObject.object_size_bytes), 0)).filter(StorageObject.environment_id == env.id).scalar()

        size_gb = float(size_bytes) / (1024.0 * 1024.0 * 1024.0)
        est_cost = round(size_gb * cost_service.get_unit_cost_per_gb_month("STANDARD"), 2)

        out.append({
            "id": str(env.id),
            "name": env.name,
            "environment_type": env.environment_type,
            "object_count": obj_count,
            "total_size_bytes": size_bytes,
            "estimated_monthly_cost_usd": est_cost,
        })
    return out


@router.get("/{organization_id}/recommendations")
def list_recommendations(
    organization_id: UUID,
    recommendation_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List recommendations with evidence details and filter options."""
    query = (
        db.query(Recommendation, StorageObject)
        .join(StorageObject, Recommendation.object_id == StorageObject.id)
        .filter(Recommendation.organization_id == organization_id)
    )

    if recommendation_type and recommendation_type != "ALL":
        query = query.filter(Recommendation.recommendation_type == recommendation_type)
    if risk_level and risk_level != "ALL":
        query = query.filter(Recommendation.risk_level == risk_level)
    if status_filter and status_filter != "ALL":
        query = query.filter(Recommendation.status == status_filter)

    total = query.count()
    rows = query.order_by(Recommendation.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    ref_time = datetime.now(timezone.utc)
    for rec, obj in rows:
        created = obj.created_at if obj.created_at.tzinfo else obj.created_at.replace(tzinfo=timezone.utc)
        age_days = (ref_time - created).days

        appr = db.query(ApprovalRequest).filter_by(recommendation_id=rec.id).first()

        items.append({
            "id": str(rec.id),
            "object_id": str(obj.id),
            "object_key": obj.object_key,
            "object_size_bytes": obj.object_size_bytes,
            "age_days": age_days,
            "recommendation_type": rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type),
            "current_storage_class": rec.current_storage_class,
            "recommended_storage_class": rec.recommended_storage_class,
            "reason": rec.reason,
            "evidence": rec.evidence,
            "estimated_savings": float(rec.estimated_savings),
            "risk_level": rec.risk_level,
            "status": rec.status,
            "created_at": rec.created_at.isoformat(),
            "approval_status": appr.status if appr else "PENDING",
            "approval_decision": appr.decision if appr else None,
            "override_reason": appr.override_reason if appr else None,
        })
    return {"total": total, "items": items}


@router.get("/{organization_id}/migrations")
def list_migrations(organization_id: UUID, db: Session = Depends(get_db)):
    """List storage migrations and rollbacks."""
    rows = (
        db.query(MigrationEvent, StorageObject)
        .join(StorageObject, MigrationEvent.object_id == StorageObject.id)
        .filter(MigrationEvent.organization_id == organization_id)
        .order_by(MigrationEvent.requested_at.desc())
        .all()
    )

    out = []
    for mig, obj in rows:
        out.append({
            "id": str(mig.id),
            "object_id": str(obj.id),
            "object_key": obj.object_key,
            "source_storage_class": mig.source_storage_class,
            "destination_storage_class": mig.destination_storage_class,
            "status": mig.status,
            "rollback_status": mig.rollback_status,
            "requested_at": mig.requested_at.isoformat(),
            "completed_at": mig.completed_at.isoformat() if mig.completed_at else None,
            "error_message": mig.error_message,
        })
    return out


@router.get("/{organization_id}/audit-logs")
def list_audit_logs(
    organization_id: UUID,
    action: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List audit log records."""
    query = db.query(AuditLog).filter(AuditLog.organization_id == organization_id)
    if action and action != "ALL":
        query = query.filter(AuditLog.action == action)
    if outcome and outcome != "ALL":
        query = query.filter(AuditLog.outcome == outcome)

    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()

    items = []
    for a in logs:
        items.append({
            "id": str(a.id),
            "action": a.action,
            "resource_type": a.resource_type,
            "resource_id": a.resource_id,
            "outcome": a.outcome,
            "timestamp": a.timestamp.isoformat(),
            "metadata": a.metadata_json,
        })
    return {"total": total, "items": items}


@router.get("/{organization_id}/policies")
def list_policies(organization_id: UUID, db: Session = Depends(get_db)):
    """List retention policies and legal holds."""
    pols = db.query(RetentionPolicy).filter_by(organization_id=organization_id).order_by(RetentionPolicy.priority.desc()).all()
    holds = db.query(LegalHold, StorageObject).join(StorageObject, LegalHold.object_id == StorageObject.id).filter(LegalHold.organization_id == organization_id).order_by(LegalHold.created_at.desc()).all()

    policies_out = [
        {
            "id": str(p.id),
            "name": p.name,
            "scope": "OBJECT" if p.object_id else ("LOCATION" if p.storage_location_id else ("ENVIRONMENT" if p.environment_id else "ORGANIZATION")),
            "retention_duration_days": p.retention_duration_days,
            "priority": p.priority,
            "status": p.status,
            "effective_date": p.effective_date.isoformat() if p.effective_date else None,
        }
        for p in pols
    ]

    holds_out = [
        {
            "id": str(h.id),
            "object_id": str(obj.id),
            "object_key": obj.object_key,
            "status": h.status,
            "reason_reference": h.reason_reference,
            "created_at": h.created_at.isoformat(),
            "released_at": h.released_at.isoformat() if h.released_at else None,
        }
        for h, obj in holds
    ]

    return {"policies": policies_out, "legal_holds": holds_out}
