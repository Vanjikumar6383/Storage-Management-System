"""
Production-Oriented Retention & Legal-Hold Policy Evaluation Engine.
Independent governance safety layer enforcing fail-safe compliance decisions.
"""

import logging
import enum
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from uuid import UUID
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session
from app.models import (
    StorageObject,
    RetentionPolicy,
    LegalHold,
    AuditLog,
)

logger = logging.getLogger("storage.policy.engine")


class ProposedActionEnum(str, enum.Enum):
    KEEP = "KEEP"
    MOVE_TO_INFREQUENT_ACCESS = "MOVE_TO_INFREQUENT_ACCESS"
    ARCHIVE = "ARCHIVE"
    DELETE = "DELETE"


class PolicyDecisionEnum(str, enum.Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class RetentionStateEnum(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"
    NO_POLICY = "NO_POLICY"


class PolicyDecision(BaseModel):
    """Normalized Policy Engine Decision Output."""
    object_id: str
    organization_id: str
    action: str
    decision: str = Field(..., description="ALLOWED, BLOCKED, or REQUIRES_REVIEW")
    retention_state: str = Field(..., description="ACTIVE, EXPIRED, UNKNOWN, or NO_POLICY")
    legal_hold_active: bool = False
    retention_expires_at: Optional[datetime] = None
    applicable_policy_id: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyEngineService:
    """Independent policy evaluation service for storage objects."""

    def resolve_applicable_policy(
        self,
        db: Session,
        organization_id: UUID,
        obj: StorageObject,
    ) -> Tuple[Optional[RetentionPolicy], str, bool]:
        """
        Determines applicable retention policy using deterministic precedence hierarchy:
        1. Object-level policy
        2. Storage-location policy
        3. Environment policy
        4. Organization-level policy

        Returns tuple of (selected_policy, hierarchy_level, has_conflict).
        """
        all_active_policies = (
            db.query(RetentionPolicy)
            .filter(
                RetentionPolicy.organization_id == organization_id,
                RetentionPolicy.status == "ACTIVE",
            )
            .all()
        )

        if not all_active_policies:
            return None, "NONE", False

        # Filter candidates by hierarchy level
        obj_policies = [p for p in all_active_policies if p.object_id == obj.id]
        loc_policies = [p for p in all_active_policies if p.storage_location_id == obj.storage_location_id and p.object_id is None]
        env_policies = [
            p for p in all_active_policies
            if obj.environment_id and p.environment_id == obj.environment_id and p.storage_location_id is None and p.object_id is None
        ]
        org_policies = [
            p for p in all_active_policies
            if p.object_id is None and p.storage_location_id is None and p.environment_id is None
        ]

        hierarchy_groups = [
            ("OBJECT", obj_policies),
            ("STORAGE_LOCATION", loc_policies),
            ("ENVIRONMENT", env_policies),
            ("ORGANIZATION", org_policies),
        ]

        for level, candidates in hierarchy_groups:
            if candidates:
                if len(candidates) == 1:
                    return candidates[0], level, False

                # Sort candidates by priority descending
                sorted_candidates = sorted(candidates, key=lambda p: p.priority, reverse=True)
                max_priority = sorted_candidates[0].priority
                top_priority_candidates = [p for p in sorted_candidates if p.priority == max_priority]

                if len(top_priority_candidates) == 1:
                    return top_priority_candidates[0], level, False

                # Check if top priority candidates have identical parameters
                durations = {p.retention_duration_days for p in top_priority_candidates}
                if len(durations) == 1:
                    # Same duration -> Unambiguous
                    return top_priority_candidates[0], level, False

                # Multiple conflicting policies at same priority -> Conflict
                logger.warning(f"Conflicting retention policies detected at {level} level for object '{obj.id}'.")
                return None, level, True

        return None, "NONE", False

    def evaluate_action(
        self,
        db: Session,
        organization_id: UUID,
        object_id: UUID,
        proposed_action: str,
        reference_time: Optional[datetime] = None,
        audit: bool = True,
    ) -> PolicyDecision:
        """
        Pure, side-effect free evaluation of a proposed lifecycle action.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        action_clean = proposed_action.upper()
        if action_clean not in ProposedActionEnum.__members__:
            raise ValueError(f"Invalid proposed action '{proposed_action}'. Must be KEEP, MOVE_TO_INFREQUENT_ACCESS, ARCHIVE, or DELETE.")

        obj = db.query(StorageObject).filter_by(id=object_id).first()
        if not obj:
            raise ValueError(f"Storage object '{object_id}' not found.")

        if obj.organization_id != organization_id:
            raise PermissionError("Tenant isolation mismatch: Object does not belong to organization.")

        # 1. Check Legal Holds
        active_holds = (
            db.query(LegalHold)
            .filter(
                LegalHold.organization_id == organization_id,
                LegalHold.object_id == object_id,
                LegalHold.status == "ACTIVE",
            )
            .all()
        )
        legal_hold_active = len(active_holds) > 0

        # 2. Resolve Applicable Retention Policy
        policy, level, has_conflict = self.resolve_applicable_policy(db, organization_id, obj)

        retention_state = RetentionStateEnum.NO_POLICY.value
        retention_expires_at: Optional[datetime] = None
        policy_id: Optional[str] = str(policy.id) if policy else None
        reasons: List[str] = []

        if has_conflict:
            retention_state = RetentionStateEnum.UNKNOWN.value
            reasons.append("Multiple conflicting retention policies detected at the same precedence level.")
        elif policy:
            base_date = max(policy.effective_date, obj.created_at) if policy.effective_date else obj.created_at
            if base_date.tzinfo is None:
                base_date = base_date.replace(tzinfo=timezone.utc)

            retention_expires_at = base_date + timedelta(days=policy.retention_duration_days)

            if ref_time < retention_expires_at:
                retention_state = RetentionStateEnum.ACTIVE.value
                reasons.append(f"Retention policy '{policy.name}' ({level} level) is ACTIVE until {retention_expires_at.isoformat()}.")
            else:
                retention_state = RetentionStateEnum.EXPIRED.value
                reasons.append(f"Retention policy '{policy.name}' ({level} level) EXPIRED on {retention_expires_at.isoformat()}.")
        else:
            retention_state = RetentionStateEnum.NO_POLICY.value
            reasons.append("No applicable retention policy found for object.")

        if legal_hold_active:
            hold_refs = [h.reason_reference for h in active_holds]
            reasons.append(f"Active legal hold(s) present: {', '.join(hold_refs)}.")

        # 3. Action-Specific Decision Matrix
        decision = PolicyDecisionEnum.ALLOWED.value

        if action_clean == ProposedActionEnum.KEEP.value:
            decision = PolicyDecisionEnum.ALLOWED.value
            reasons.append("KEEP action is safe and does not modify storage tier or delete data.")

        elif action_clean in (ProposedActionEnum.MOVE_TO_INFREQUENT_ACCESS.value, ProposedActionEnum.ARCHIVE.value):
            if retention_state == RetentionStateEnum.UNKNOWN.value:
                decision = PolicyDecisionEnum.REQUIRES_REVIEW.value
                reasons.append(f"Conflicting retention policies require manual review before {action_clean}.")
            elif legal_hold_active:
                decision = PolicyDecisionEnum.ALLOWED.value
                reasons.append(f"{action_clean} is allowed while preserving active legal hold and storage accessibility.")
            else:
                decision = PolicyDecisionEnum.ALLOWED.value
                reasons.append(f"{action_clean} preserves retention and governance rules.")

        elif action_clean == ProposedActionEnum.DELETE.value:
            # Rule 1: Legal Hold OVERRIDES EVERYTHING
            if legal_hold_active:
                decision = PolicyDecisionEnum.BLOCKED.value
                reasons.append("Active legal hold prevents object deletion.")

            # Rule 2: Active Retention BLOCKS
            elif retention_state == RetentionStateEnum.ACTIVE.value:
                decision = PolicyDecisionEnum.BLOCKED.value
                reasons.append("Retention period has not expired.")

            # Rule 3: Fail-safe on NO_POLICY -> REQUIRES_REVIEW
            elif retention_state == RetentionStateEnum.NO_POLICY.value:
                decision = PolicyDecisionEnum.REQUIRES_REVIEW.value
                reasons.append("No applicable retention policy found. Manual review required before deletion.")

            # Rule 4: Fail-safe on UNKNOWN -> REQUIRES_REVIEW
            elif retention_state == RetentionStateEnum.UNKNOWN.value:
                decision = PolicyDecisionEnum.REQUIRES_REVIEW.value
                reasons.append("Multiple conflicting retention policies detected. Manual review required before deletion.")

            # Rule 5: Allowed Deletion
            elif retention_state == RetentionStateEnum.EXPIRED.value:
                decision = PolicyDecisionEnum.ALLOWED.value
                reasons.append("Retention period has expired and no active legal hold exists.")

        policy_decision = PolicyDecision(
            object_id=str(obj.id),
            organization_id=str(obj.organization_id),
            action=action_clean,
            decision=decision,
            retention_state=retention_state,
            legal_hold_active=legal_hold_active,
            retention_expires_at=retention_expires_at,
            applicable_policy_id=policy_id,
            reasons=reasons,
            evaluated_at=ref_time,
        )

        # 4. Record Audit Log if requested
        if audit:
            audit_log = AuditLog(
                organization_id=organization_id,
                action="POLICY_EVALUATION",
                resource_type="storage_objects",
                resource_id=str(obj.id),
                timestamp=ref_time,
                outcome=decision,
                metadata_json={
                    "proposed_action": action_clean,
                    "decision": decision,
                    "retention_state": retention_state,
                    "legal_hold_active": legal_hold_active,
                    "reasons": reasons,
                },
            )
            db.add(audit_log)
            db.commit()

        return policy_decision
