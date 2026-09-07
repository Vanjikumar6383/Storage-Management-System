"""
Telemetry, Usage Aggregation, and Restore Risk Service Layer.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

from sqlalchemy import func, case, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import StorageObject, AccessEvent, RestoreEvent
from app.core.telemetry_config import (
    AccessEventTypeEnum,
    AccessFrequencyEnum,
    RestoreRiskEnum,
    RestoreStatusEnum,
    MEANINGFUL_ACCESS_EVENTS,
    TELEMETRY_THRESHOLDS,
)

logger = logging.getLogger("storage.service.telemetry")


# Pydantic Schemas for Telemetry Output
class ObjectUsageProfile(BaseModel):
    object_id: str
    organization_id: str
    object_key: str
    storage_location_id: str
    storage_class: str
    object_size_bytes: int
    created_at: datetime
    age_days: int
    last_access_at: Optional[datetime] = None
    days_since_last_access: Optional[int] = None
    accesses_7d: int = 0
    accesses_30d: int = 0
    accesses_90d: int = 0
    accesses_180d: int = 0
    total_meaningful_accesses: int = 0
    access_frequency: str = AccessFrequencyEnum.NONE.value
    last_restore_at: Optional[datetime] = None
    restores_30d: int = 0
    restores_90d: int = 0
    restores_180d: int = 0
    restore_success_rate: float = 1.0
    avg_restore_duration_seconds: Optional[float] = None
    restore_risk: str = RestoreRiskEnum.LOW.value
    risk_explainability: List[str] = Field(default_factory=list)


class AccessEventIngestionService:
    """Service for recording access events idempotently with tenant scoping."""

    def record_access_event(
        self,
        db: Session,
        organization_id: UUID,
        object_id: UUID,
        event_type: str,
        event_timestamp: Optional[datetime] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> AccessEvent:
        obj = db.query(StorageObject).filter_by(id=object_id).first()
        if not obj:
            raise ValueError(f"Storage object '{object_id}' not found.")

        # Enforce tenant isolation
        if obj.organization_id != organization_id:
            raise PermissionError("Tenant isolation mismatch: Object does not belong to organization.")

        ts = event_timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Check idempotency
        if idempotency_key:
            existing = db.query(AccessEvent).filter_by(idempotency_key=idempotency_key).first()
            if existing:
                logger.info(f"Duplicate access event skipped (idempotency key: {idempotency_key}).")
                return existing

        event = AccessEvent(
            organization_id=organization_id,
            object_id=object_id,
            event_type=event_type,
            event_timestamp=ts,
            source=source,
            metadata_json=metadata or {},
            idempotency_key=idempotency_key,
        )
        db.add(event)

        # Update last_accessed_at if meaningful access
        if event_type in MEANINGFUL_ACCESS_EVENTS:
            if not obj.last_accessed_at or ts > obj.last_accessed_at:
                obj.last_accessed_at = ts

        try:
            db.commit()
            db.refresh(event)
            return event
        except IntegrityError:
            db.rollback()
            if idempotency_key:
                return db.query(AccessEvent).filter_by(idempotency_key=idempotency_key).first()
            raise


class RestoreEventService:
    """Service for recording and updating restore events."""

    def record_restore_event(
        self,
        db: Session,
        organization_id: UUID,
        object_id: UUID,
        source_storage_class: str,
        target_storage_class: str,
        requested_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        status: str = RestoreStatusEnum.REQUESTED.value,
        restore_duration_seconds: Optional[int] = None,
        failure_reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> RestoreEvent:
        obj = db.query(StorageObject).filter_by(id=object_id).first()
        if not obj:
            raise ValueError(f"Storage object '{object_id}' not found.")

        if obj.organization_id != organization_id:
            raise PermissionError("Tenant isolation mismatch: Object does not belong to organization.")

        req_ts = requested_at or datetime.now(timezone.utc)
        if req_ts.tzinfo is None:
            req_ts = req_ts.replace(tzinfo=timezone.utc)

        comp_ts = completed_at
        if comp_ts and comp_ts.tzinfo is None:
            comp_ts = comp_ts.replace(tzinfo=timezone.utc)

        if idempotency_key:
            existing = db.query(RestoreEvent).filter_by(idempotency_key=idempotency_key).first()
            if existing:
                logger.info(f"Duplicate restore event skipped (idempotency key: {idempotency_key}).")
                return existing

        event = RestoreEvent(
            organization_id=organization_id,
            object_id=object_id,
            requested_at=req_ts,
            completed_at=comp_ts,
            status=status,
            source_storage_class=source_storage_class,
            target_storage_class=target_storage_class,
            restore_duration_seconds=restore_duration_seconds,
            failure_reason=failure_reason,
            idempotency_key=idempotency_key,
        )
        db.add(event)
        try:
            db.commit()
            db.refresh(event)
            return event
        except IntegrityError:
            db.rollback()
            if idempotency_key:
                return db.query(RestoreEvent).filter_by(idempotency_key=idempotency_key).first()
            raise


class UsageAggregationService:
    """Service to calculate access statistics and frequency metrics."""

    @staticmethod
    def classify_access_frequency(accesses_30d: int, accesses_180d: int) -> str:
        cfg = TELEMETRY_THRESHOLDS
        if accesses_30d >= cfg.high_access_30d:
            return AccessFrequencyEnum.HIGH.value
        if accesses_30d >= cfg.medium_access_30d:
            return AccessFrequencyEnum.MEDIUM.value
        if accesses_30d >= cfg.low_access_30d:
            return AccessFrequencyEnum.LOW.value
        if accesses_180d >= cfg.very_low_access_180d:
            return AccessFrequencyEnum.VERY_LOW.value
        return AccessFrequencyEnum.NONE.value


class RestoreRiskService:
    """Service to calculate restore activity and risk classification."""

    @staticmethod
    def classify_restore_risk(
        restores_90d: int,
        restores_30d: int,
        failed_count: int,
        total_attempts: int,
    ) -> tuple[str, List[str]]:
        reasons = []
        cfg = TELEMETRY_THRESHOLDS

        failure_rate = (failed_count / total_attempts) if total_attempts > 0 else 0.0

        if restores_90d >= cfg.high_restore_count_90d:
            reasons.append(f"High restore frequency: {restores_90d} restores in last 90 days.")
        if total_attempts >= 2 and failure_rate >= cfg.high_restore_failure_rate:
            reasons.append(f"High restore failure rate: {failure_rate*100:.1f}% of attempts failed.")

        if reasons:
            return RestoreRiskEnum.HIGH.value, reasons

        if restores_90d >= cfg.medium_restore_count_90d or restores_30d > 0:
            reasons.append(f"Moderate restore activity: {restores_90d} restores in last 90 days.")
            return RestoreRiskEnum.MEDIUM.value, reasons

        reasons.append("Low restore activity: No recent restores detected.")
        return RestoreRiskEnum.LOW.value, reasons


class ObjectUsageProfileService:
    """Combines metadata, access stats, and restore metrics into a single ObjectUsageProfile."""

    def build_usage_profile(
        self,
        db: Session,
        organization_id: UUID,
        object_id: UUID,
        reference_time: Optional[datetime] = None,
    ) -> ObjectUsageProfile:
        profiles = self.batch_build_usage_profiles(
            db, organization_id, [object_id], reference_time=reference_time
        )
        if not profiles:
            raise ValueError(f"Object '{object_id}' not found for tenant '{organization_id}'.")
        return profiles[0]

    def batch_build_usage_profiles(
        self,
        db: Session,
        organization_id: UUID,
        object_ids: Optional[List[UUID]] = None,
        reference_time: Optional[datetime] = None,
    ) -> List[ObjectUsageProfile]:
        """
        High-performance batch aggregation using a single SQL query to prevent N+1 overhead.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        t_7d = ref_time - timedelta(days=7)
        t_30d = ref_time - timedelta(days=30)
        t_90d = ref_time - timedelta(days=90)
        t_180d = ref_time - timedelta(days=180)

        # Base query for objects
        query = db.query(StorageObject).filter(StorageObject.organization_id == organization_id)
        if object_ids:
            query = query.filter(StorageObject.id.in_(object_ids))

        objects = query.all()
        if not objects:
            return []

        target_obj_ids = [obj.id for obj in objects]

        # 1. Single SQL Aggregation for Access Events
        meaningful_types = list(MEANINGFUL_ACCESS_EVENTS)
        access_agg = (
            db.query(
                AccessEvent.object_id,
                func.count(case((AccessEvent.event_timestamp >= t_7d, 1))).label("cnt_7d"),
                func.count(case((AccessEvent.event_timestamp >= t_30d, 1))).label("cnt_30d"),
                func.count(case((AccessEvent.event_timestamp >= t_90d, 1))).label("cnt_90d"),
                func.count(case((AccessEvent.event_timestamp >= t_180d, 1))).label("cnt_180d"),
                func.count().label("cnt_total"),
                func.max(AccessEvent.event_timestamp).label("max_access_ts"),
            )
            .filter(
                AccessEvent.organization_id == organization_id,
                AccessEvent.object_id.in_(target_obj_ids),
                AccessEvent.event_type.in_(meaningful_types),
            )
            .group_by(AccessEvent.object_id)
            .all()
        )

        access_map = {row.object_id: row for row in access_agg}

        # 2. Single SQL Aggregation for Restore Events
        restore_agg = (
            db.query(
                RestoreEvent.object_id,
                func.count(case((RestoreEvent.requested_at >= t_30d, 1))).label("rst_30d"),
                func.count(case((RestoreEvent.requested_at >= t_90d, 1))).label("rst_90d"),
                func.count(case((RestoreEvent.requested_at >= t_180d, 1))).label("rst_180d"),
                func.count().label("rst_total"),
                func.count(case((RestoreEvent.status == RestoreStatusEnum.FAILED.value, 1))).label("rst_failed"),
                func.count(case((RestoreEvent.status == RestoreStatusEnum.SUCCEEDED.value, 1))).label("rst_succeeded"),
                func.max(RestoreEvent.requested_at).label("max_restore_ts"),
                func.avg(RestoreEvent.restore_duration_seconds).label("avg_duration"),
            )
            .filter(
                RestoreEvent.organization_id == organization_id,
                RestoreEvent.object_id.in_(target_obj_ids),
            )
            .group_by(RestoreEvent.object_id)
            .all()
        )

        restore_map = {row.object_id: row for row in restore_agg}

        # 3. Assemble Profiles
        profiles = []
        for obj in objects:
            acc_data = access_map.get(obj.id)
            rst_data = restore_map.get(obj.id)

            # Access stats
            cnt_7d = acc_data.cnt_7d if acc_data else 0
            cnt_30d = acc_data.cnt_30d if acc_data else 0
            cnt_90d = acc_data.cnt_90d if acc_data else 0
            cnt_180d = acc_data.cnt_180d if acc_data else 0
            cnt_total = acc_data.cnt_total if acc_data else 0

            # Determine last access timestamp
            last_access_ts = obj.last_accessed_at
            if acc_data and acc_data.max_access_ts:
                if not last_access_ts or acc_data.max_access_ts > last_access_ts:
                    last_access_ts = acc_data.max_access_ts

            if last_access_ts and last_access_ts.tzinfo is None:
                last_access_ts = last_access_ts.replace(tzinfo=timezone.utc)

            age_days = max(0, (ref_time - obj.created_at).days) if obj.created_at else 0
            days_since_last_access = (
                max(0, (ref_time - last_access_ts).days) if last_access_ts else None
            )

            freq_category = UsageAggregationService.classify_access_frequency(
                cnt_30d, cnt_180d
            )

            # Restore stats
            rst_30d = rst_data.rst_30d if rst_data else 0
            rst_90d = rst_data.rst_90d if rst_data else 0
            rst_180d = rst_data.rst_180d if rst_data else 0
            rst_total = rst_data.rst_total if rst_data else 0
            rst_failed = rst_data.rst_failed if rst_data else 0
            rst_succeeded = rst_data.rst_succeeded if rst_data else 0

            last_restore_ts = rst_data.max_restore_ts if rst_data else None
            if last_restore_ts and last_restore_ts.tzinfo is None:
                last_restore_ts = last_restore_ts.replace(tzinfo=timezone.utc)

            success_rate = (rst_succeeded / rst_total) if rst_total > 0 else 1.0
            avg_duration = float(rst_data.avg_duration) if (rst_data and rst_data.avg_duration) else None

            risk_category, explainability = RestoreRiskService.classify_restore_risk(
                rst_90d, rst_30d, rst_failed, rst_total
            )

            profiles.append(
                ObjectUsageProfile(
                    object_id=str(obj.id),
                    organization_id=str(obj.organization_id),
                    object_key=obj.object_key,
                    storage_location_id=str(obj.storage_location_id),
                    storage_class=obj.storage_class,
                    object_size_bytes=obj.object_size_bytes,
                    created_at=obj.created_at,
                    age_days=age_days,
                    last_access_at=last_access_ts,
                    days_since_last_access=days_since_last_access,
                    accesses_7d=cnt_7d,
                    accesses_30d=cnt_30d,
                    accesses_90d=cnt_90d,
                    accesses_180d=cnt_180d,
                    total_meaningful_accesses=cnt_total,
                    access_frequency=freq_category,
                    last_restore_at=last_restore_ts,
                    restores_30d=rst_30d,
                    restores_90d=rst_90d,
                    restores_180d=rst_180d,
                    restore_success_rate=round(success_rate, 2),
                    avg_restore_duration_seconds=avg_duration,
                    restore_risk=risk_category,
                    risk_explainability=explainability,
                )
            )

        return profiles
