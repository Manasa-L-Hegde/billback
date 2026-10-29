import sys
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

print("1. Testing GET / ...")
r = client.get("/")
print("Root status:", r.status_code, r.json())
assert r.status_code == 200

print("\n2. Testing GET /api/cases ...")
r = client.get("/api/cases")
print("Cases status:", r.status_code, f"Found {len(r.json())} cases")
assert r.status_code == 200

print("\n3. Testing GET /api/vendors/City%20Wholesale%20Mart/drift ...")
r = client.get("/api/vendors/City%20Wholesale%20Mart/drift")
print("Drift status:", r.status_code, r.json())
assert r.status_code == 200

print("\n4. Testing POST /api/cases ...")
with open("samples/test_bill5.jpg", "rb") as inv_f, open("samples/test_slip5.jpg", "rb") as slip_f:
    r = client.post(
        "/api/cases",
        files={
            "invoice": ("test_bill5.jpg", inv_f, "image/jpeg"),
            "slip": ("test_slip5.jpg", slip_f, "image/jpeg")
        },
        data={
            "vendor_email": "vendor@example.com",
            "vendor_mode": "partial_50",
            "min_accept_percent": 80.0,
            "autonomous": "true"
        }
    )
print("Create case response:", r.status_code, r.json())
assert r.status_code == 200
case_id = r.json()["case_id"]

print("\n5. Testing GET /api/cases/{case_id}/stream (SSE) ...")
with client.stream("GET", f"/api/cases/{case_id}/stream") as stream_res:
    for line in stream_res.iter_lines():
        if line and line.startswith("event:"):
            print("  [SSE Event]:", line)

print("\nAll server API endpoints validated successfully!")

