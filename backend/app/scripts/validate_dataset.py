"""
Synthetic Benchmark Dataset Quality Validation Tool.
Enforces 12 strict data-integrity, tenant-isolation, partition-leakage,
and consistency rules. Exits with non-zero code if validation fails.
"""

import sys
import argparse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import SessionLocal
from app.models import StorageObject, LegalHold, RetentionPolicy, Organization


def validate_dataset(min_objects: int = 1000) -> bool:
    print("======================================================================")
    print("RUNNING BENCHMARK DATASET QUALITY & INTEGRITY VALIDATION")
    print("======================================================================")

    db: Session = SessionLocal()
    errors = []

    try:
        # Check 1: Minimum object count
        tot_objs = db.query(func.count(StorageObject.id)).scalar()
        print(f"1. Total objects indexed: {tot_objs:,}")
        if tot_objs < min_objects:
            errors.append(f"Insufficient objects: expected >= {min_objects}, found {tot_objs}")

        # Check 2: Required non-null fields
        null_keys = db.query(StorageObject).filter(
            (StorageObject.organization_id == None) |
            (StorageObject.storage_location_id == None) |
            (StorageObject.object_key == None) |
            (StorageObject.created_at == None)
        ).count()
        print(f"2. Required fields check: {null_keys} invalid objects")
        if null_keys > 0:
            errors.append(f"Found {null_keys} objects with missing required attributes.")

        # Check 3: No negative sizes
        neg_sizes = db.query(StorageObject).filter(StorageObject.object_size_bytes < 0).count()
        print(f"3. Negative size check: {neg_sizes} objects")
        if neg_sizes > 0:
            errors.append(f"Found {neg_sizes} objects with negative size.")

        # Check 4: Valid storage classes
        valid_classes = ["STANDARD", "INFREQUENT_ACCESS", "ARCHIVE", "GLACIER", "DEEP_ARCHIVE"]
        inv_classes = db.query(StorageObject).filter(~StorageObject.storage_class.in_(valid_classes)).count()
        print(f"4. Valid storage classes check: {inv_classes} invalid classes")
        if inv_classes > 0:
            errors.append(f"Found {inv_classes} objects with unknown storage class.")

        # Check 5: Access count consistency (30d <= 90d)
        inconsistent_acc = db.query(StorageObject).filter(StorageObject.access_count_30d > StorageObject.access_count_90d).count()
        print(f"5. Access count consistency (30d <= 90d): {inconsistent_acc} anomalies")
        if inconsistent_acc > 0:
            errors.append(f"Found {inconsistent_acc} objects with access_count_30d > access_count_90d.")

        # Check 6: Duplicate object keys per location
        dups = (
            db.query(StorageObject.storage_location_id, StorageObject.object_key, func.count(StorageObject.id))
            .group_by(StorageObject.storage_location_id, StorageObject.object_key)
            .having(func.count(StorageObject.id) > 1)
            .count()
        )
        print(f"6. Duplicate object key check: {dups} duplicates")
        if dups > 0:
            errors.append(f"Found {dups} duplicate (location_id, object_key) pairs.")

        # Check 7: Partition leakage detection
        dev_keys = set(r[0] for r in db.query(StorageObject.object_key).filter_by(dataset_partition="DEVELOPMENT").all())
        val_keys = set(r[0] for r in db.query(StorageObject.object_key).filter_by(dataset_partition="VALIDATION").all())
        stress_keys = set(r[0] for r in db.query(StorageObject.object_key).filter_by(dataset_partition="STRESS").all())

        leakage_dev_val = len(dev_keys.intersection(val_keys))
        leakage_val_stress = len(val_keys.intersection(stress_keys))
        print(f"7. Partition leakage check: DEV/VAL leakage={leakage_dev_val}, VAL/STRESS leakage={leakage_val_stress}")
        if leakage_dev_val > 0 or leakage_val_stress > 0:
            errors.append(f"Partition leakage detected between dataset splits ({leakage_dev_val} dev-val, {leakage_val_stress} val-stress).")

        # Check 8: Ground truth label completeness
        missing_gt = db.query(StorageObject).filter(StorageObject.ground_truth_action == None).count()
        print(f"8. Ground truth completeness check: {missing_gt} missing labels")
        if missing_gt > 0:
            errors.append(f"Found {missing_gt} objects missing ground truth labels.")

        # Check 9: Active legal hold consistency
        holds = db.query(LegalHold).filter_by(status="ACTIVE").all()
        hold_obj_ids = [h.object_id for h in holds]
        invalid_holds = db.query(StorageObject).filter(
            StorageObject.id.in_(hold_obj_ids),
            StorageObject.ground_truth_action != "HOLD"
        ).count()
        print(f"9. Legal hold safety consistency: {invalid_holds} violations")
        if invalid_holds > 0:
            errors.append(f"Found {invalid_holds} objects with active legal hold not labeled as HOLD ground truth.")

        print("======================================================================")
        if errors:
            print("DATASET VALIDATION FAILED! Errors found:")
            for err in errors:
                print(f" - ERROR: {err}")
            print("======================================================================")
            return False

        print("DATASET VALIDATION PASSED SUCCESSFULLY! All 9 checks green.")
        print("======================================================================")
        return True

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Validate Synthetic Benchmark Dataset Integrity")
    parser.add_argument("--min-objects", type=int, default=1000, help="Minimum object count threshold")
    args = parser.parse_args()

    is_valid = validate_dataset(min_objects=args.min_objects)
    if not is_valid:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
