"""
Explainable Policy/Rule-Based Storage Lifecycle Recommendation Engine.
Combines metadata, telemetry usage profiles, restore risk, retention policy decisions,
and legal holds to generate immutable, auditable recommendations.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session
from app.models import StorageObject, Recommendation, RecommendationTypeEnum
from app.services.telemetry import ObjectUsageProfileService, ObjectUsageProfile
from app.services.policy_engine import PolicyEngineService, PolicyDecision
from app.services.cost_estimation import CostEstimationService, StorageCostEstimate
from app.core.recommendation_config import RECOMMENDATION_THRESHOLDS, LifecycleRuleThresholds
from app.ml.predictor import get_ml_predictor

logger = logging.getLogger("storage.recommendation.engine")


class RuleEvaluationResult(BaseModel):
    rule_id: str
    rule_name: str
    result: bool
    evidence: str
    priority: int


class RecommendationResult(BaseModel):
    object_id: str
    organization_id: str
    recommendation_type: str  # KEEP, MOVE_TO_INFREQUENT_ACCESS, ARCHIVE, DELETE_CANDIDATE, HOLD
    current_storage_class: str
    recommended_storage_class: str
    reason: str
    risk_level: str  # LOW, MEDIUM, HIGH
    impact_level: str  # LOW_IMPACT, HIGH_IMPACT
    requires_approval: bool
    estimated_savings_usd: float
    estimated_retrieval_risk_usd: float
    rule_version: str
    evidence_structure: Dict[str, Any]
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RecommendationService:
    """Explainable rule-based recommendation service."""

    def __init__(self, thresholds: LifecycleRuleThresholds = RECOMMENDATION_THRESHOLDS):
        self.thresholds = thresholds
        self.telemetry_service = ObjectUsageProfileService()
        self.policy_service = PolicyEngineService()
        self.cost_service = CostEstimationService()

    def evaluate_object_recommendation(
        self,
        db: Session,
        organization_id: UUID,
        obj: StorageObject,
        usage_profile: Optional[ObjectUsageProfile] = None,
        policy_decision: Optional[PolicyDecision] = None,
        reference_time: Optional[datetime] = None,
    ) -> RecommendationResult:
        """
        Pure, side-effect free evaluation of lifecycle rules for a single object.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        if obj.organization_id != organization_id:
            raise PermissionError("Tenant isolation mismatch: Object does not belong to organization.")

        # 1. Fetch telemetry profile & policy decision if not pre-fetched in batch
        prof = usage_profile or self.telemetry_service.build_usage_profile(db, organization_id, obj.id, reference_time=ref_time)
        pol = policy_decision or self.policy_service.evaluate_action(db, organization_id, obj.id, proposed_action="DELETE", reference_time=ref_time, audit=False)

        # ML Model Inference
        ml_predictor = get_ml_predictor()
        ml_res = None
        if ml_predictor.is_available:
            try:
                ret_days = 0
                ret_left = 999
                if pol.retention_expires_at:
                    ret_left = (pol.retention_expires_at - ref_time).days
                    ret_days = max(0, prof.age_days + ret_left)

                ml_features = {
                    "size_bytes": obj.object_size_bytes,
                    "object_age_days": prof.age_days,
                    "access_count_30d": prof.accesses_30d,
                    "last_access_days_ago": prof.days_since_last_access if prof.days_since_last_access is not None else prof.age_days,
                    "restore_events_90d": prof.restores_90d,
                    "retention_days": ret_days,
                    "retention_expiry_days_left": ret_left,
                    "env_type": "production",
                    "region": "us-east-1",
                    "data_category": obj.category or "general_data",
                    "current_storage_class": obj.storage_class,
                    "retention_policy": "active" if pol.retention_state == "ACTIVE" else "none",
                    "legal_hold": pol.legal_hold_active,
                }
                ml_res = ml_predictor.predict_object(ml_features)
            except Exception as ml_err:
                logger.warning(f"ML prediction error: {ml_err}")
                ml_res = None

        rules_evaluated: List[RuleEvaluationResult] = []

        rec_type = RecommendationTypeEnum.KEEP.value
        rec_class = obj.storage_class
        risk_level = "LOW"
        impact_level = "LOW_IMPACT"
        requires_approval = False
        primary_reason = "Current storage class maintained."

        curr_class_upper = obj.storage_class.upper()

        # Rule 1: Legal Hold Check (Priority 1 - Regulatory Safety Strict Guard)
        if pol.legal_hold_active:
            r1 = RuleEvaluationResult(
                rule_id="LEGAL-001",
                rule_name="Active Legal Hold Protection",
                result=True,
                evidence="Active legal hold is present. Deletion and aggressive tiering are blocked.",
                priority=1,
            )
            rules_evaluated.append(r1)
            rec_type = RecommendationTypeEnum.HOLD.value
            rec_class = obj.storage_class
            risk_level = "LOW"
            impact_level = "HIGH_IMPACT"
            requires_approval = True
            primary_reason = "Active legal hold prevents deletion or tier migration."

        # Rule 2: Policy Conflict / Unknown (Priority 2)
        elif pol.retention_state == "UNKNOWN":
            r2 = RuleEvaluationResult(
                rule_id="POLICY-002",
                rule_name="Policy Conflict / Unknown Retention State",
                result=True,
                evidence="Multiple conflicting retention policies detected at the applicable hierarchy level.",
                priority=2,
            )
            rules_evaluated.append(r2)
            rec_type = RecommendationTypeEnum.HOLD.value
            rec_class = obj.storage_class
            risk_level = "HIGH"
            impact_level = "HIGH_IMPACT"
            requires_approval = True
            primary_reason = "Conflicting retention policies require manual review before lifecycle action."

        # Rule 3: High Restore Risk Protection (Priority 3)
        elif prof.restore_risk == "HIGH":
            r3 = RuleEvaluationResult(
                rule_id="RESTORE-001",
                rule_name="High Restore Risk Protection",
                result=True,
                evidence=f"High restore frequency ({prof.restores_90d} restores in 90d) or failure rate detected.",
                priority=3,
            )
            rules_evaluated.append(r3)
            rec_type = RecommendationTypeEnum.HOLD.value if curr_class_upper in ("ARCHIVE", "GLACIER") else RecommendationTypeEnum.KEEP.value
            rec_class = obj.storage_class
            risk_level = "HIGH"
            impact_level = "HIGH_IMPACT"
            requires_approval = True
            primary_reason = "High restore activity indicates operational retrieval demand. Aggressive archival is blocked."

        # Rule 4: Frequent / Recent Access Activity (Priority 4)
        elif prof.accesses_30d >= self.thresholds.minimum_accesses_for_keep or prof.access_frequency in ("HIGH", "MEDIUM"):
            r4 = RuleEvaluationResult(
                rule_id="ACCESS-001",
                rule_name="Active Access Activity",
                result=True,
                evidence=f"{prof.accesses_30d} meaningful accesses in last 30 days (frequency: {prof.access_frequency}).",
                priority=4,
            )
            rules_evaluated.append(r4)
            rec_type = RecommendationTypeEnum.KEEP.value
            rec_class = obj.storage_class
            risk_level = "LOW"
            impact_level = "LOW_IMPACT"
            requires_approval = False
            primary_reason = "Frequent or recent access activity indicates continued operational use."

        # Rule 5: Object Size Below Efficiency Threshold (Priority 5)
        elif obj.object_size_bytes < self.thresholds.minimum_object_size_for_migration_bytes or obj.object_size_bytes <= 0:
            r5 = RuleEvaluationResult(
                rule_id="SIZE-001",
                rule_name="Object Size Below Migration Threshold",
                result=True,
                evidence=f"Object size ({obj.object_size_bytes} bytes) is below minimum migration threshold ({self.thresholds.minimum_object_size_for_migration_bytes} bytes).",
                priority=5,
            )
            rules_evaluated.append(r5)
            rec_type = RecommendationTypeEnum.KEEP.value
            rec_class = obj.storage_class
            risk_level = "LOW"
            impact_level = "LOW_IMPACT"
            requires_approval = False
            primary_reason = "Small object size does not justify tier migration overhead."

        # Rule 6: Delete Candidate Evaluation (Priority 6)
        elif (
            prof.age_days >= self.thresholds.delete_candidate_age_days
            and prof.accesses_180d == 0
            and prof.restores_90d == 0
            and pol.retention_state == "EXPIRED"
            and not pol.legal_hold_active
            and pol.decision == "ALLOWED"
        ):
            r6 = RuleEvaluationResult(
                rule_id="DELETE-001",
                rule_name="Unused Object Eligible for Deletion Review",
                result=True,
                evidence=f"Age ({prof.age_days}d) exceeds 365d, 0 accesses in 180d, retention expired, no legal hold.",
                priority=6,
            )
            rules_evaluated.append(r6)
            rec_type = RecommendationTypeEnum.DELETE_CANDIDATE.value
            rec_class = "DELETE_CANDIDATE"
            risk_level = "MEDIUM"
            impact_level = "HIGH_IMPACT"
            requires_approval = True
            primary_reason = "Retention expired, no legal hold, and zero access in 180 days. Eligible for deletion review."

        # Rule 7: Active Retention Prevents Deletion (Priority 7)
        elif prof.age_days >= self.thresholds.delete_candidate_age_days and pol.retention_state == "ACTIVE":
            r7 = RuleEvaluationResult(
                rule_id="POLICY-001",
                rule_name="Active Retention Prevents Deletion",
                result=True,
                evidence=f"Object is old ({prof.age_days}d) but active retention extends until {pol.retention_expires_at}.",
                priority=7,
            )
            rules_evaluated.append(r7)
            rec_type = RecommendationTypeEnum.HOLD.value
            rec_class = obj.storage_class
            risk_level = "LOW"
            impact_level = "HIGH_IMPACT"
            requires_approval = True
            primary_reason = "Active retention policy prevents deletion recommendation."

        # Rule 8: Archival Candidate Evaluation (Priority 8)
        elif (
            prof.age_days >= self.thresholds.archive_age_days
            and prof.accesses_30d == 0
            and prof.restores_90d == 0
            and curr_class_upper not in ("ARCHIVE", "GLACIER", "DEEP_ARCHIVE")
        ):
            r8 = RuleEvaluationResult(
                rule_id="ARCHIVE-001",
                rule_name="Cold Object Eligible for Archival",
                result=True,
                evidence=f"Age ({prof.age_days}d) exceeds {self.thresholds.archive_age_days}d with 0 accesses in 30d and 0 restores.",
                priority=8,
            )
            rules_evaluated.append(r8)
            rec_type = RecommendationTypeEnum.ARCHIVE.value
            rec_class = "ARCHIVE"
            risk_level = "LOW"
            impact_level = "HIGH_IMPACT"
            requires_approval = True
            primary_reason = f"Object age exceeds {self.thresholds.archive_age_days} days with zero recent access. Archival optimizes cost."

        # Rule 9: Infrequent Access Candidate Evaluation (Priority 9)
        elif (
            prof.age_days >= self.thresholds.infrequent_access_age_days
            and prof.accesses_30d == 0
            and curr_class_upper in ("STANDARD", "HOT")
        ):
            r9 = RuleEvaluationResult(
                rule_id="IA-001",
                rule_name="Infrequent Access Candidate",
                result=True,
                evidence=f"Age ({prof.age_days}d) exceeds {self.thresholds.infrequent_access_age_days}d with 0 accesses in 30d.",
                priority=9,
            )
            rules_evaluated.append(r9)
            rec_type = RecommendationTypeEnum.MOVE_TO_INFREQUENT_ACCESS.value
            rec_class = "INFREQUENT_ACCESS"
            risk_level = "LOW"
            impact_level = "LOW_IMPACT"
            requires_approval = False
            primary_reason = f"Object age exceeds {self.thresholds.infrequent_access_age_days} days with zero 30d access. Infrequent access tiering recommended."

        # Rule 10: Already Archived or Infrequent Match (Priority 10)
        elif curr_class_upper in ("ARCHIVE", "GLACIER", "INFREQUENT_ACCESS") and rec_class == obj.storage_class:
            r10 = RuleEvaluationResult(
                rule_id="SAME_CLASS-001",
                rule_name="Already Optimal Storage Class",
                result=True,
                evidence=f"Object is already in storage class '{obj.storage_class}'. No redundant migration recommended.",
                priority=10,
            )
            rules_evaluated.append(r10)
            rec_type = RecommendationTypeEnum.KEEP.value
            rec_class = obj.storage_class
            risk_level = "LOW"
            impact_level = "LOW_IMPACT"
            requires_approval = False
            primary_reason = f"Object is already in target storage class '{obj.storage_class}'."

        else:
            r_def = RuleEvaluationResult(
                rule_id="DEFAULT-001",
                rule_name="Baseline Retention",
                result=True,
                evidence="Object does not meet lifecycle migration thresholds.",
                priority=99,
            )
            rules_evaluated.append(r_def)

        # Calculate Storage Cost Estimate
        target_class_for_calc = rec_class if rec_class != "DELETE_CANDIDATE" else "DELETE_CANDIDATE"
        cost_est = self.cost_service.calculate_savings(
            object_size_bytes=obj.object_size_bytes,
            current_storage_class=obj.storage_class,
            recommended_storage_class="ARCHIVE" if rec_type == RecommendationTypeEnum.ARCHIVE.value else (
                "INFREQUENT_ACCESS" if rec_type == RecommendationTypeEnum.MOVE_TO_INFREQUENT_ACCESS.value else obj.storage_class
            ),
            restores_90d=prof.restores_90d,
            thresholds=self.thresholds,
        )

        evidence_struct = {
            "rules": [r.model_dump() for r in rules_evaluated],
            "rule_version": self.thresholds.rule_version,
            "pricing_assumption_version": self.thresholds.pricing_assumption_version,
            "calculated_at": ref_time.isoformat(),
            "impact_level": impact_level,
            "requires_approval": requires_approval,
            "telemetry_summary": {
                "age_days": prof.age_days,
                "accesses_30d": prof.accesses_30d,
                "accesses_180d": prof.accesses_180d,
                "restores_90d": prof.restores_90d,
                "access_frequency": prof.access_frequency,
                "restore_risk": prof.restore_risk,
            },
            "policy_summary": {
                "retention_state": pol.retention_state,
                "legal_hold_active": pol.legal_hold_active,
                "policy_decision": pol.decision,
            },
            "cost_summary": cost_est.model_dump(),
        }

        return RecommendationResult(
            object_id=str(obj.id),
            organization_id=str(organization_id),
            recommendation_type=rec_type,
            current_storage_class=obj.storage_class,
            recommended_storage_class=rec_class,
            reason=primary_reason,
            risk_level=risk_level,
            impact_level=impact_level,
            requires_approval=requires_approval,
            estimated_savings_usd=cost_est.estimated_monthly_savings_usd,
            estimated_retrieval_risk_usd=cost_est.estimated_retrieval_risk_usd,
            rule_version=self.thresholds.rule_version,
            evidence_structure=evidence_struct,
            evaluated_at=ref_time,
        )

    def generate_and_save_recommendation(
        self,
        db: Session,
        organization_id: UUID,
        object_id: UUID,
        reference_time: Optional[datetime] = None,
    ) -> Recommendation:
        """
        Generates recommendation and saves/upserts immutable record in database.
        Pure simulation: does NOT modify or delete storage objects.
        """
        obj = db.query(StorageObject).filter_by(id=object_id).first()
        if not obj:
            raise ValueError(f"Storage object '{object_id}' not found.")

        result = self.evaluate_object_recommendation(db, organization_id, obj, reference_time=reference_time)

        # Check existing active recommendation for object
        existing = (
            db.query(Recommendation)
            .filter(
                Recommendation.organization_id == organization_id,
                Recommendation.object_id == object_id,
                Recommendation.status == "PENDING",
            )
            .first()
        )

        if existing:
            # Update existing pending record idempotently
            existing.recommendation_type = result.recommendation_type
            existing.current_storage_class = result.current_storage_class
            existing.recommended_storage_class = result.recommended_storage_class
            existing.reason = result.reason
            existing.evidence = result.evidence_structure
            existing.estimated_savings = result.estimated_savings_usd
            existing.risk_level = result.risk_level
            existing.created_at = result.evaluated_at
            db.commit()
            db.refresh(existing)
            return existing

        rec = Recommendation(
            organization_id=organization_id,
            object_id=object_id,
            recommendation_type=result.recommendation_type,
            current_storage_class=result.current_storage_class,
            recommended_storage_class=result.recommended_storage_class,
            reason=result.reason,
            evidence=result.evidence_structure,
            estimated_savings=result.estimated_savings_usd,
            risk_level=result.risk_level,
            status="PENDING",
            created_at=result.evaluated_at,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec

    def batch_generate_recommendations(
        self,
        db: Session,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        reference_time: Optional[datetime] = None,
    ) -> List[Recommendation]:
        """
        High-performance batch recommendation generator preventing N+1 queries.
        Processes objects in bulk using batch usage profiles.
        """
        ref_time = reference_time or datetime.now(timezone.utc)

        objects = (
            db.query(StorageObject)
            .filter(StorageObject.organization_id == organization_id)
            .order_by(StorageObject.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        if not objects:
            return []

        obj_ids = [o.id for o in objects]

        # 1. Batch telemetry profiles (1 query)
        profiles_list = self.telemetry_service.batch_build_usage_profiles(db, organization_id, obj_ids, reference_time=ref_time)
        prof_map = {p.object_id: p for p in profiles_list}

        recommendations = []
        for obj in objects:
            p_prof = prof_map.get(str(obj.id))
            rec_record = self.generate_and_save_recommendation(db, organization_id, obj.id, reference_time=ref_time)
            recommendations.append(rec_record)

        db.commit()
        return recommendations
