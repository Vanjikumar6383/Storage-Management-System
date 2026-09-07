"""
Dataset Export Utility for Synthetic Benchmark Metadata.
Exports metadata-only records to CSV or JSONL. Never exports object payload contents.
"""

import argparse
import json
import csv
import sys
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models import StorageObject


def export_dataset(output_path: str = "dataset_export.csv", file_format: str = "csv", limit: int = 50000):
    print("======================================================================")
    print(f"Exporting Synthetic Dataset Metadata ({file_format.upper()}) -> {output_path}")
    print("======================================================================")

    db: Session = SessionLocal()
    try:
        objs = db.query(StorageObject).limit(limit).all()
        print(f"Exporting {len(objs):,} object metadata rows...")

        fieldnames = [
            "id",
            "organization_id",
            "environment_id",
            "object_key",
            "category",
            "object_size_bytes",
            "storage_class",
            "dataset_partition",
            "scenario_tag",
            "ground_truth_action",
            "ground_truth_reason",
            "created_at",
            "access_count_30d",
            "access_count_90d",
        ]

        if file_format.lower() == "jsonl":
            with open(output_path, "w", encoding="utf-8") as f:
                for o in objs:
                    row = {
                        "id": str(o.id),
                        "organization_id": str(o.organization_id),
                        "environment_id": str(o.environment_id) if o.environment_id else None,
                        "object_key": o.object_key,
                        "category": o.category,
                        "object_size_bytes": o.object_size_bytes,
                        "storage_class": o.storage_class,
                        "dataset_partition": o.dataset_partition,
                        "scenario_tag": o.scenario_tag,
                        "ground_truth_action": o.ground_truth_action,
                        "ground_truth_reason": o.ground_truth_reason,
                        "created_at": o.created_at.isoformat() if o.created_at else None,
                        "access_count_30d": o.access_count_30d,
                        "access_count_90d": o.access_count_90d,
                    }
                    f.write(json.dumps(row) + "\n")
        else:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for o in objs:
                    writer.writerow({
                        "id": str(o.id),
                        "organization_id": str(o.organization_id),
                        "environment_id": str(o.environment_id) if o.environment_id else None,
                        "object_key": o.object_key,
                        "category": o.category,
                        "object_size_bytes": o.object_size_bytes,
                        "storage_class": o.storage_class,
                        "dataset_partition": o.dataset_partition,
                        "scenario_tag": o.scenario_tag,
                        "ground_truth_action": o.ground_truth_action,
                        "ground_truth_reason": o.ground_truth_reason,
                        "created_at": o.created_at.isoformat() if o.created_at else None,
                        "access_count_30d": o.access_count_30d,
                        "access_count_90d": o.access_count_90d,
                    })

        print(f"Export successful: {output_path}")
        print("======================================================================")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Export Synthetic Benchmark Metadata")
    parser.add_argument("--output", type=str, default="dataset_export.csv", help="Output file path")
    parser.add_argument("--format", type=str, choices=["csv", "jsonl"], default="csv", help="Export format")
    parser.add_argument("--limit", type=int, default=50000, help="Max objects to export")

    args = parser.parse_args()
    export_dataset(output_path=args.output, file_format=args.format, limit=args.limit)


if __name__ == "__main__":
    main()
