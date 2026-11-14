"""Restaurant verification: signup requires evidence, approval requires
verification, and unverified restaurants can never go live."""

from tests.conftest import demo_headers

EVIDENCE = {
    "phone": "(940) 555-0100",
    "owner_name": "Test Owner",
    "business_address": "1 Test St, Denton, TX 76201",
}


def _apply(client, headers, **overrides):
    body = {"name": "New Signup Diner", **EVIDENCE, **overrides}
    return client.post("/api/v1/restaurants", json=body, headers=headers)


def test_signup_requires_verification_evidence(client, seeded):
    admin = demo_headers(client, "admin")
    # Name alone is not enough: owner, phone, and address are required.
    res = client.post(
        "/api/v1/restaurants", json={"name": "No Evidence Diner"}, headers=admin
    )
    assert res.status_code == 422, res.text

    res = _apply(client, admin)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "pending"
    assert data["verification_status"] == "unverified"
    assert data["owner_name"] == "Test Owner"
    assert data["business_address"] == "1 Test St, Denton, TX 76201"
    assert data["verified_at"] is None


def test_approve_requires_verification(client, seeded):
    admin = demo_headers(client, "admin")
    restaurant = _apply(client, admin).json()

    res = client.post(
        f"/api/v1/admin/restaurants/{restaurant['id']}/approve", headers=admin
    )
    assert res.status_code == 400, res.text
    assert "Verify" in res.json()["error"]["message"]

    # Still pending and still not orderable after the refused approval.
    assert (
        client.get(
            f"/api/v1/restaurants/{restaurant['id']}", headers=admin
        ).json()["status"]
        == "pending"
    )


def test_verify_then_approve(client, seeded):
    admin = demo_headers(client, "admin")
    restaurant = _apply(client, admin).json()

    res = client.post(
        f"/api/v1/admin/restaurants/{restaurant['id']}/verify",
        json={"notes": "Checked Google listing and phone."},
        headers=admin,
    )
    assert res.status_code == 200, res.text
    assert res.json()["verification_status"] == "verified"
    assert res.json()["verification_notes"] == "Checked Google listing and phone."
    assert res.json()["verified_at"] is not None

    res = client.post(
        f"/api/v1/admin/restaurants/{restaurant['id']}/approve", headers=admin
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "active"


def test_verify_requires_admin(client, seeded):
    admin = demo_headers(client, "admin")
    customer = demo_headers(client, "customer")
    restaurant = _apply(client, admin).json()
    res = client.post(
        f"/api/v1/admin/restaurants/{restaurant['id']}/verify",
        json={},
        headers=customer,
    )
    assert res.status_code == 403, res.text
