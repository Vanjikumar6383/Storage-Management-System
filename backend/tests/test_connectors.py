import pytest
from datetime import datetime, timezone
from app.connectors.base import NormalizedStorageLocation, NormalizedObjectMetadata
from app.connectors.s3_connector import LocalS3Connector


class FakeS3Client:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    def list_buckets(self):
        if self.should_fail:
            raise RuntimeError("Connection refused")
        return {
            "Buckets": [
                {"Name": "test-bucket-alpha", "CreationDate": datetime.now(timezone.utc)},
                {"Name": "test-bucket-beta", "CreationDate": datetime.now(timezone.utc)},
            ]
        }

    def list_objects_v2(self, Bucket, MaxKeys=1000, ContinuationToken=None):
        if Bucket == "empty-bucket":
            return {}
        if ContinuationToken == "page2":
            return {
                "Contents": [
                    {
                        "Key": "logs/page2.log",
                        "Size": 512,
                        "StorageClass": "STANDARD",
                        "LastModified": datetime.now(timezone.utc),
                        "ETag": '"etag-512"',
                    }
                ]
            }
        return {
            "Contents": [
                {
                    "Key": "data/file1.csv",
                    "Size": 1024,
                    "StorageClass": "STANDARD",
                    "LastModified": datetime.now(timezone.utc),
                    "ETag": '"etag-1024"',
                }
            ],
            "NextContinuationToken": "page2",
        }

    def head_object(self, Bucket, Key):
        return {
            "ContentLength": 2048,
            "StorageClass": "STANDARD_IA",
            "LastModified": datetime.now(timezone.utc),
            "ETag": '"etag-2048"',
            "ContentType": "application/octet-stream",
        }


def test_connector_test_connection_success():
    connector = LocalS3Connector()
    connector.client = FakeS3Client(should_fail=False)
    assert connector.test_connection() is True


def test_connector_test_connection_failure():
    connector = LocalS3Connector()
    connector.client = FakeS3Client(should_fail=True)
    assert connector.test_connection() is False


def test_connector_list_storage_locations():
    connector = LocalS3Connector()
    connector.client = FakeS3Client(should_fail=False)
    locs = connector.list_storage_locations()
    assert len(locs) == 2
    assert locs[0].name == "test-bucket-alpha"


def test_connector_list_objects_and_pagination():
    connector = LocalS3Connector()
    connector.client = FakeS3Client(should_fail=False)

    objs, next_cursor = connector.list_objects("test-bucket-alpha")
    assert len(objs) == 1
    assert objs[0].object_key == "data/file1.csv"
    assert objs[0].object_size_bytes == 1024
    assert next_cursor == "page2"

    objs2, next_cursor2 = connector.list_objects("test-bucket-alpha", cursor=next_cursor)
    assert len(objs2) == 1
    assert objs2[0].object_key == "logs/page2.log"
    assert next_cursor2 is None


def test_connector_empty_bucket():
    connector = LocalS3Connector()
    connector.client = FakeS3Client(should_fail=False)
    objs, next_cursor = connector.list_objects("empty-bucket")
    assert len(objs) == 0
    assert next_cursor is None


def test_connector_get_object_metadata_normalization():
    connector = LocalS3Connector()
    connector.client = FakeS3Client(should_fail=False)
    meta = connector.get_object_metadata("test-bucket-alpha", "data/file1.csv")
    assert meta.object_size_bytes == 2048
    assert meta.storage_class in ("MOVE_TO_INFREQUENT_ACCESS", "INFREQUENT_ACCESS")
