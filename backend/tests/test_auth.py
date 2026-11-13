"""Auth tests: register, login, refresh, logout, profile."""

from tests.conftest import DEMO_EMAILS, auth_headers, demo_headers, login


def test_register_creates_customer_and_returns_tokens(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "password": "Password123!",
            "full_name": "New User",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == "new@example.com"
    assert [r["name"] for r in body["user"]["roles"]] == ["customer"]


def test_register_duplicate_email_conflicts(client):
    payload = {
        "email": "dup@example.com",
        "password": "Password123!",
        "full_name": "Dup",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_login_wrong_password_rejected(client, seeded):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAILS["customer"], "password": "WrongPassword1!"},
    )
    assert resp.status_code == 401


def test_login_demo_user_and_me(client, seeded):
    tokens = login(client, DEMO_EMAILS["customer"])
    me = client.get("/api/v1/users/me", headers=auth_headers(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == DEMO_EMAILS["customer"]


def test_me_requires_auth(client):
    assert client.get("/api/v1/users/me").status_code == 401


def test_refresh_rotates_tokens(client, seeded):
    tokens = login(client, DEMO_EMAILS["customer"])
    resp = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200, resp.text
    new_tokens = resp.json()
    assert new_tokens["access_token"] != tokens["access_token"]
    # The old refresh token is revoked after rotation.
    again = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert again.status_code == 401


def test_logout_revokes_refresh_token(client, seeded):
    tokens = login(client, DEMO_EMAILS["customer"])
    resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 200
    again = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert again.status_code == 401


def test_update_profile(client, seeded):
    headers = demo_headers(client, "customer")
    resp = client.patch(
        "/api/v1/users/me",
        json={"full_name": "Renamed Customer", "phone": "(940) 555-0199"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["full_name"] == "Renamed Customer"
    assert resp.json()["phone"] == "(940) 555-0199"


def test_register_as_driver_grants_driver_role_and_profile(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "driver@example.com",
            "password": "Password123!",
            "full_name": "New Driver",
            "role": "driver",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert [r["name"] for r in body["user"]["roles"]] == ["driver"]
    me = client.get(
        "/api/v1/drivers/me", headers=auth_headers(body["access_token"])
    )
    assert me.status_code == 200, me.text
    assert me.json()["onboarding_status"] == "applied"
    assert me.json()["online"] is False


def test_register_as_restaurant_owner_grants_role(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "password": "Password123!",
            "full_name": "New Owner",
            "role": "restaurant_owner",
        },
    )
    assert resp.status_code == 201, resp.text
    assert [r["name"] for r in resp.json()["user"]["roles"]] == [
        "restaurant_owner"
    ]


def test_register_rejects_staff_roles(client):
    for role in ("admin", "dispatcher", "restaurant_manager", "restaurant_staff"):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"staff-{role}@example.com",
                "password": "Password123!",
                "full_name": "Nope",
                "role": role,
            },
        )
        assert resp.status_code == 400, resp.text


def test_driver_online_requires_approval(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "pending@example.com",
            "password": "Password123!",
            "full_name": "Pending Driver",
            "role": "driver",
        },
    )
    assert resp.status_code == 201, resp.text
    headers = auth_headers(resp.json()["access_token"])
    blocked = client.patch(
        "/api/v1/drivers/me/availability",
        json={"online": True},
        headers=headers,
    )
    assert blocked.status_code == 403, blocked.text
