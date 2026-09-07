"""
Local Folder Metadata Scanner Service.

PRIVACY GUARANTEE:
This service strictly reads ONLY filesystem metadata (filename, size, created, modified, and accessed timestamps).
File byte contents are NEVER opened, read, streamed, or accessed in any way.
"""

import os
import mimetypes
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from app.models import (
    StorageConnection,
    StorageProviderEnum,
    StorageLocation,
    Environment,
    StorageObject,
    Organization,
)
from app.services.recommendation_engine import RecommendationService

logger = logging.getLogger("storage.local_scanner")


def categorize_file(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".log", ".out", ".err", ".trace"]:
        return "logs"
    elif ext in [".tar", ".gz", ".zip", ".bak", ".dump", ".sql", ".7z", ".rar"]:
        return "backups"
    elif ext in [".csv", ".parquet", ".json", ".xlsx", ".tsv", ".avro", ".xml"]:
        return "analytical_data"
    elif ext in [".mp4", ".mov", ".jpg", ".jpeg", ".png", ".gif", ".mp3", ".wav", ".webm"]:
        return "media"
    elif ext in [".pdf", ".docx", ".doc", ".txt", ".md", ".rtf"]:
        return "documents"
    elif ext in [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs"]:
        return "code"
    return "general_data"


class LocalFolderScannerService:
    """
    Scans local storage directories capturing strictly filesystem metadata.
    Zero content reading is performed.
    """

    def __init__(self):
        self.rec_service = RecommendationService()

    def scan_and_link(
        self,
        db: Session,
        organization_id: UUID,
        local_path: str,
        max_files: int = 500,
        run_ml_recommendations: bool = True,
    ) -> Dict[str, Any]:
        """
        Scans a local directory and links its metadata to the organization.
        
        Args:
            db: SQLAlchemy session
            organization_id: Target organization UUID
            local_path: Absolute or relative local directory path
            max_files: Maximum files to index in a single run (to prevent runaway scans)
            run_ml_recommendations: Whether to generate ML recommendations immediately
        """
        # Validate organization
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        if not org:
            raise ValueError(f"Organization with ID {organization_id} not found.")

        # Normalize and validate path
        clean_path = os.path.abspath(os.path.expanduser(local_path.strip()))
        if not os.path.exists(clean_path):
            raise FileNotFoundError(f"Local path does not exist: '{clean_path}'")
        if not os.path.isdir(clean_path):
            raise ValueError(f"Specified path is not a directory: '{clean_path}'")

        # 1. Get or create StorageConnection
        conn_name = f"Local Storage ({os.path.basename(clean_path) or clean_path})"
        storage_conn = (
            db.query(StorageConnection)
            .filter(
                StorageConnection.organization_id == organization_id,
                StorageConnection.credential_reference == f"local://{clean_path}",
            )
            .first()
        )

        if not storage_conn:
            storage_conn = StorageConnection(
                organization_id=organization_id,
                name=conn_name,
                provider=StorageProviderEnum.LOCAL_S3_COMPATIBLE,
                credential_reference=f"local://{clean_path}",
                config={
                    "path": clean_path,
                    "privacy_mode": "METADATA_ONLY_ZERO_CONTENT_ACCESS",
                    "registered_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            db.add(storage_conn)
            db.flush()

        # 2. Get or create StorageLocation
        loc_name = f"local-dir-{os.path.basename(clean_path).lower() or 'root'}"
        storage_loc = (
            db.query(StorageLocation)
            .filter(
                StorageLocation.storage_connection_id == storage_conn.id,
                StorageLocation.name == loc_name,
            )
            .first()
        )

        if not storage_loc:
            storage_loc = StorageLocation(
                organization_id=organization_id,
                storage_connection_id=storage_conn.id,
                name=loc_name,
                region="local-filesystem",
            )
            db.add(storage_loc)
            db.flush()

        # 3. Get or create default Environment
        env = (
            db.query(Environment)
            .filter(
                Environment.organization_id == organization_id,
                Environment.storage_connection_id == storage_conn.id,
            )
            .first()
        )
        if not env:
            env = Environment(
                organization_id=organization_id,
                storage_connection_id=storage_conn.id,
                name="Local Storage Environment",
                environment_type="PRODUCTION",
                status="ACTIVE",
            )
            db.add(env)
            db.flush()

        # 4. Strictly Metadata-Only Scan (NEVER open() or read())
        total_files = 0
        total_bytes = 0
        created_objects: List[StorageObject] = []
        sample_metadata = []

        now_utc = datetime.now(timezone.utc)

        for root, dirs, files in os.walk(clean_path):
            # Skip hidden folders / git
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv", ".venv")]

            for fname in files:
                if fname.startswith("."):
                    continue

                full_file_path = os.path.join(root, fname)
                try:
                    # STRICT PRIVACY: os.stat only reads file inode metadata
                    stat_info = os.stat(full_file_path)
                except (PermissionError, OSError) as e:
                    logger.warning(f"Skipping inaccessible file {full_file_path}: {e}")
                    continue

                rel_key = os.path.relpath(full_file_path, clean_path).replace("\\", "/")
                file_size = stat_info.st_size
                mtime = datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc)
                ctime = datetime.fromtimestamp(stat_info.st_ctime, tz=timezone.utc)
                atime = datetime.fromtimestamp(stat_info.st_atime, tz=timezone.utc)

                mime_type, _ = mimetypes.guess_type(fname)
                category = categorize_file(fname)

                # Approximate access count in last 30 days based on atime
                days_since_access = (now_utc - atime).days if atime else 999
                access_count_30d = 5 if days_since_access < 30 else 0

                # Check if object already indexed
                existing_obj = (
                    db.query(StorageObject)
                    .filter(
                        StorageObject.storage_location_id == storage_loc.id,
                        StorageObject.object_key == rel_key,
                    )
                    .first()
                )

                if existing_obj:
                    existing_obj.object_size_bytes = file_size
                    existing_obj.last_modified_at = mtime
                    existing_obj.last_accessed_at = atime
                    existing_obj.updated_at = now_utc
                    obj_to_eval = existing_obj
                else:
                    new_obj = StorageObject(
                        organization_id=organization_id,
                        storage_location_id=storage_loc.id,
                        environment_id=env.id,
                        object_key=rel_key,
                        object_size_bytes=file_size,
                        object_type=mime_type or "application/octet-stream",
                        category=category,
                        storage_class="STANDARD",
                        current_state="ACTIVE",
                        dataset_partition="LOCAL_LINKED",
                        created_at=ctime,
                        last_modified_at=mtime,
                        last_accessed_at=atime,
                        access_count_30d=access_count_30d,
                        access_count_90d=access_count_30d,
                        version_count=1,
                        discovered_at=now_utc,
                    )
                    db.add(new_obj)
                    created_objects.append(new_obj)
                    obj_to_eval = new_obj

                total_files += 1
                total_bytes += file_size

                if len(sample_metadata) < 10:
                    sample_metadata.append({
                        "object_key": rel_key,
                        "size_bytes": file_size,
                        "category": category,
                        "modified_at": mtime.isoformat(),
                        "accessed_at": atime.isoformat(),
                    })

                if total_files >= max_files:
                    logger.info(f"Reached max_files limit of {max_files}. Stopping scan.")
                    break

            if total_files >= max_files:
                break

        db.commit()

        # 5. Evaluate ML Recommendations for newly indexed/updated objects
        recommendations_generated = 0
        if run_ml_recommendations:
            # Query all objects for this location to evaluate
            all_loc_objs = (
                db.query(StorageObject)
                .filter(StorageObject.storage_location_id == storage_loc.id)
                .all()
            )
            for target_obj in all_loc_objs:
                try:
                    self.rec_service.generate_and_save_recommendation(
                        db=db,
                        organization_id=organization_id,
                        object_id=target_obj.id,
                    )
                    recommendations_generated += 1
                except Exception as rec_err:
                    logger.warning(f"Failed to generate recommendation for {target_obj.object_key}: {rec_err}")
            db.commit()

        return {
            "status": "SUCCESS",
            "organization_id": str(organization_id),
            "linked_path": clean_path,
            "privacy_guarantee": "METADATA_ONLY: Zero byte content read. Only filenames, sizes, and timestamps indexed.",
            "total_files_scanned": total_files,
            "total_bytes_scanned": total_bytes,
            "total_mb_scanned": round(total_bytes / (1024 * 1024), 2),
            "recommendations_generated": recommendations_generated,
            "storage_connection_id": str(storage_conn.id),
            "storage_location_id": str(storage_loc.id),
            "sample_objects": sample_metadata,
        }
