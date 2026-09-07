import pytest
from sqlalchemy.exc import IntegrityError
from app.db.database import SessionLocal
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
    LegalHold,
    Recommendation,
    RecommendationTypeEnum,
)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_seed_data_exists(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    assert demo_org is not None
    assert demo_org.name == "Demo Organization"

    test_org = db_session.query(Organization).filter_by(slug="test-organization").first()
    assert test_org is not None
    assert test_org.name == "Test Organization"


def test_tenant_isolation_and_fk_relationship(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conns = db_session.query(StorageConnection).filter_by(organization_id=demo_org.id).all()
    assert len(conns) >= 1
    assert conns[0].organization_id == demo_org.id


def test_unique_constraint_enforcement(db_session):
    # Attempt duplicate organization slug
    duplicate_org = Organization(name="Duplicate Demo", slug="demo-organization")
    db_session.add(duplicate_org)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_storage_object_creation_and_policy_references(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key="logs/2026/08/test_audit.log",
        object_size_bytes=2048,
        storage_class="STANDARD",
        created_at=demo_org.created_at,
        last_modified_at=demo_org.created_at,
    )
    db_session.add(obj)
    db_session.commit()

    # Place legal hold
    hold = LegalHold(
        organization_id=demo_org.id,
        object_id=obj.id,
        status="ACTIVE",
        reason_reference="REF-COMPLIANCE-9912",
    )
    db_session.add(hold)
    db_session.commit()

    fetch_obj = db_session.query(StorageObject).filter_by(id=obj.id).first()
    assert fetch_obj is not None
    assert len(fetch_obj.legal_holds) == 1
    assert fetch_obj.legal_holds[0].reason_reference == "REF-COMPLIANCE-9912"

    # Cleanup test object
    db_session.delete(obj)
    db_session.commit()
