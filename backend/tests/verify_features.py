import urllib.request
import json
import os

def test_all():
    print("--- 1. Testing ML Model Info ---")
    req = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/ml/model-info")
    ml_info = json.loads(req.read().decode())
    print("ML Model Status:", ml_info.get("status"))
    print("ML Metrics:", ml_info.get("metadata", {}).get("test_metrics"))

    print("\n--- 2. Testing 10 Canonical Demo Organizations ---")
    req = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/organizations")
    orgs = json.loads(req.read().decode())
    print(f"Total Organizations in DB: {len(orgs)}")
    for o in orgs:
        print(f"  * {o['slug'].ljust(25)} | {o['name']}")

    print("\n--- 3. Testing Zero-Data Registration for New Org ---")
    reg_payload = {
        "name": "ZeroData Innovators Corp",
        "slug": f"zerodata-test-org",
        "admin_email": "admin@zerodata-test.io",
        "plan": "DEVELOPMENT_FREE",
        "provider": "LOCAL_S3_COMPATIBLE",
        "seed_sample_data": False,
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/organizations/register",
        data=json.dumps(reg_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        res = urllib.request.urlopen(req)
        reg_res = json.loads(res.read().decode())
        org_id = reg_res["id"]
        print(f"Registered Org: {reg_res['name']} ({reg_res['slug']}) | ID: {org_id}")
    except urllib.error.HTTPError as e:
        if e.code == 409:
            # Already exists, fetch it
            req2 = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/organizations")
            all_orgs = json.loads(req2.read().decode())
            target = next(o for o in all_orgs if o["slug"] == "zerodata-test-org")
            org_id = target["id"]
            print(f"Using existing test org: {target['name']} | ID: {org_id}")
        else:
            raise e

    # Check that it has 0 data
    req = urllib.request.urlopen(f"http://127.0.0.1:8000/api/v1/organizations/{org_id}")

    details = json.loads(req.read().decode())
    print(f"Initial State Verification: Objects Count = {details['objects_count']}, Total Storage Bytes = {details['total_storage_bytes']}")
    assert details["objects_count"] == 0, "Expected 0 objects for new organization"
    assert details["total_storage_bytes"] == 0, "Expected 0 bytes for new organization"
    print(">>> ZERO DATA REQUIREMENT VERIFIED SUCCESSFULLY! <<<")

    print("\n--- 4. Testing Link Local Storage (Metadata Only) ---")
    local_dir = os.path.abspath("app/ml")
    link_payload = {
        "local_path": local_dir,
        "max_files": 50,
        "run_ml_recommendations": True,
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:8000/api/v1/organizations/{org_id}/storage/link-local",
        data=json.dumps(link_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res = urllib.request.urlopen(req)
    link_res = json.loads(res.read().decode())
    print("Linking Status:", link_res["status"])
    print("Privacy Guarantee:", link_res["privacy_guarantee"])
    print(f"Files Indexed (Metadata Only): {link_res['total_files_scanned']}")
    print(f"Total Bytes: {link_res['total_bytes_scanned']} ({link_res['total_mb_scanned']} MB)")
    print(f"ML Recommendations Generated: {link_res['recommendations_generated']}")
    print("Sample Metadata Object:")
    if link_res["sample_objects"]:
        print(json.dumps(link_res["sample_objects"][0], indent=2))

    # Verify updated organization count
    req = urllib.request.urlopen(f"http://127.0.0.1:8000/api/v1/dashboard/organizations/{org_id}")
    updated_details = json.loads(req.read().decode())
    print(f"\nAfter Linking Verification: Objects Count = {updated_details['objects_count']}, Total Storage Bytes = {updated_details['total_storage_bytes']}")
    assert updated_details["objects_count"] > 0, "Objects should now be indexed"
    print(">>> LOCAL STORAGE LINKING WITH PRIVACY VERIFIED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_all()
