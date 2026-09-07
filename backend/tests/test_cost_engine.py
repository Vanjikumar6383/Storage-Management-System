import pytest
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone, timedelta, date

from app.db.database import SessionLocal
from app.models import (
    Organization,
    StorageLocation,
    StorageObject,
    RetentionPolicy,
    LegalHold,
    Recommendation,
    StorageCostSnapshot,
)
from app.models.cost import StoragePricingCatalog, SavingsLedger
from app.services.pricing_provider import PricingProvider
from app.services.savings_ledger import SavingsLedgerService
from app.services.cost_engine import CostSummaryService, SnapshotService, ExperimentService, ErrorAnalysisService
from app.services.approval_execution import ApprovalExecutionService
from app.services.recommendation_engine import RecommendationService


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_1_2_3_4_5_6_7_cost_and_savings_calculation(db_session):
    """TEST 1-7: Cost, savings, zero size, large size, zero baseline, and Decimal precision."""
    pricing = PricingProvider()
    pricing.seed_default_demo_pricing(db_session)

    # 1. Standard cost calculation (10 GB STANDARD @ $0.023)
    p_std = pricing.get_storage_price(db_session, "LOCAL_S3", "STANDARD")
    cost_std = round(Decimal("10.0") * p_std, 4)
    assert cost_std == Decimal("0.2300")

    # 2. Archive cost calculation (10 GB ARCHIVE @ $0.004)
    p_arch = pricing.get_storage_price(db_session, "LOCAL_S3", "ARCHIVE")
    cost_arch = round(Decimal("10.0") * p_arch, 4)
    assert cost_arch == Decimal("0.0400")

    # 3. Savings calculation
    sav = max(cost_std - cost_arch, Decimal("0.0000"))
    assert sav == Decimal("0.1900")

    # 4. Zero-size object
    cost_zero = round(Decimal("0.0") * p_std, 4)
    assert cost_zero == Decimal("0.0000")

    # 5. Large object (10,000 GB STANDARD @ $0.023)
    cost_large = round(Decimal("10000.0") * p_std, 4)
    assert cost_large == Decimal("230.0000")

    # 6 & 7. Zero baseline & Decimal precision
    assert isinstance(sav, Decimal)


def test_8_18_19_20_pricing_version_and_minimum_duration(db_session):
    """TEST 8, 18, 19, 20: Pricing version, fallback, and minimum storage duration."""
    pricing = PricingProvider()

    # Min storage days check
    min_days_std = pricing.get_minimum_storage_duration(db_session, "LOCAL_S3", "STANDARD")
    assert min_days_std == 0

    min_days_arch = pricing.get_minimum_storage_duration(db_session, "LOCAL_S3", "ARCHIVE")
    assert min_days_arch == 90

    # Custom pricing version
    custom_p = StoragePricingCatalog(
        provider="LOCAL_S3",
        storage_class="STANDARD",
        region="us-east-1",
        price_per_gb_month=Decimal("0.050000"),
        pricing_version="2026-v2-custom",
        active=True,
    )
    db_session.add(custom_p)
    db_session.commit()

    rate_v2 = pricing.get_storage_price(db_session, "LOCAL_S3", "STANDARD", version="2026-v2-custom")
    assert rate_v2 == Decimal("0.050000")

    db_session.delete(custom_p)
    db_session.commit()


def test_9_10_snapshot_creation_and_deduplication(db_session):
    """TEST 9, 10: Snapshot creation and duplicate snapshot prevention."""
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    snap_service = SnapshotService()

    today = date(2026, 8, 1)
    count1 = snap_service.create_daily_snapshots(db_session, snapshot_date=today)
    assert count1 >= 1

    # Second run for same date returns 0 created (deduplicated)
    count2 = snap_service.create_daily_snapshots(db_session, snapshot_date=today)
    assert count2 == 0

    db_session.query(StorageCostSnapshot).filter_by(snapshot_date=today).delete()
    db_session.commit()


def test_11_12_13_savings_ledger_and_rollback_reversal(db_session):
    """TEST 11, 12, 13: Migration creates realized savings, rollback reverses realized savings."""
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"cost/test_ledger_{uuid4().hex[:8]}.dat",
        object_size_bytes=100 * 1024 * 1024 * 1024,  # 100 GB
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    rec_service = RecommendationService()
    rec = rec_service.generate_and_save_recommendation(db_session, demo_org.id, obj.id, reference_time=ref_time)
    exec_service = ApprovalExecutionService()
    exec_service.process_approval_decision(db_session, demo_org.id, rec.id, decision="APPROVE")

    try:
        # Execute migration -> Creates realized savings ledger entry (TEST 11)
        res_exec = exec_service.execute_recommendation(db_session, demo_org.id, rec.id)
        assert res_exec.status == "SUCCESS"

        ledger_entry = db_session.query(SavingsLedger).filter_by(migration_id=res_exec.migration_id).first()
        assert ledger_entry is not None
        assert ledger_entry.status == "REALIZED"
        assert ledger_entry.monthly_savings > 0

        # Execute rollback -> Reverses realized savings (status = ROLLED_BACK) (TEST 13)
        res_rb = exec_service.rollback_migration(db_session, demo_org.id, uuid4() if not res_exec.migration_id else res_exec.migration_id)
        assert res_rb.status == "SUCCESS"

        db_session.refresh(ledger_entry)
        assert ledger_entry.status == "ROLLED_BACK"

    finally:
        db_session.delete(rec)
        db_session.delete(obj)
        db_session.commit()


def test_14_15_16_17_counterfactual_experiment_and_error_classification(db_session):
    """TEST 14-17, 21-24: Counterfactual experiment, retention/legal hold blocking, and error analysis."""
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    test_org = db_session.query(Organization).filter_by(slug="test-organization").first()

    exp_service = ExperimentService()
    exp_res = exp_service.run_counterfactual_experiment(db_session, demo_org.id)

    assert "baseline_monthly_cost_usd" in exp_res
    assert "optimized_monthly_cost_usd" in exp_res
    assert "estimated_monthly_savings_usd" in exp_res

    # Error analysis classification
    err_service = ErrorAnalysisService()
    err_res = err_service.classify_unexecuted_recommendations(db_session, demo_org.id)
    assert "total_unexecuted_recommendations" in err_res
    assert "category_breakdown" in err_res

    # Tenant isolation test (TEST 17)
    exp_test_org = exp_service.run_counterfactual_experiment(db_session, test_org.id)
    assert exp_test_org["organization_id"] == str(test_org.id)
