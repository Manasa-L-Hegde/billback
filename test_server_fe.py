import sys
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

print("1. Testing GET / (HTML frontend) ...")
r = client.get("/")
print("Root status:", r.status_code, "HTML title check:", "BillBack" in r.text)
assert r.status_code == 200
assert "BillBack" in r.text

print("\n2. Testing GET /static/app.js ...")
r = client.get("/static/app.js")
print("Static JS status:", r.status_code, "Length:", len(r.text))
assert r.status_code == 200

print("\n3. Testing POST /api/cases/demo ...")
r = client.post("/api/cases/demo", json={"vendor_mode": "partial_50", "min_accept_percent": 80.0, "autonomous": True})
print("Demo case status:", r.status_code, r.json())
assert r.status_code == 200
assert "demo_case_" in r.json()["case_id"]

print("\nAll frontend serving and demo endpoints validated successfully!")

