"""Recruiter auth endpoints: register, login, profile (M2 acceptance)."""

from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.recruiters.models import Recruiter

pytestmark = pytest.mark.django_db

REGISTER_URL = "/auth/recruiters/register"
LOGIN_URL = "/auth/recruiters/login"
ME_URL = "/recruiters/me"

PASSWORD = "correct horse battery staple"


def register_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": "ada@example.com",
        "password": PASSWORD,
        "full_name": "Ada Lovelace",
        "company_name": "Analytical Engines",
        "phone": "+44 20 7946 0000",
    }
    payload.update(overrides)
    return payload


def test_register_creates_recruiter_and_returns_token() -> None:
    response = APIClient().post(REGISTER_URL, register_payload(), format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] == 3600
    assert body["recruiter"]["email"] == "ada@example.com"
    assert "password" not in body["recruiter"]
    assert Recruiter.objects.filter(email="ada@example.com").exists()

    token = AccessToken(body["access"])
    assert token["role"] == "recruiter"
    assert token["iss"] == "job-service"
    assert str(token["sub"]) == str(Recruiter.objects.get(email="ada@example.com").id)


def test_refresh_returns_access_with_role_and_issuer() -> None:
    client = APIClient()
    assert client.post(REGISTER_URL, register_payload(), format="json").status_code == 201
    login = client.post(
        LOGIN_URL, {"email": "ada@example.com", "password": PASSWORD}, format="json"
    )
    assert login.status_code == 200
    assert login.json()["refresh"]

    response = APIClient().post(
        "/auth/recruiters/refresh",
        {"refresh": login.json()["refresh"]},
        format="json",
    )

    assert response.status_code == 200
    token = AccessToken(response.json()["access"])
    assert token["role"] == "recruiter"
    assert token["iss"] == "job-service"


def test_refresh_rejects_an_invalid_token() -> None:
    response = APIClient().post(
        "/auth/recruiters/refresh",
        {"refresh": "not-a-token"},
        format="json",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


def test_register_normalizes_email_to_lowercase() -> None:
    response = APIClient().post(
        REGISTER_URL, register_payload(email="Ada@Example.COM"), format="json"
    )
    assert response.status_code == 201
    assert response.json()["recruiter"]["email"] == "ada@example.com"


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.Argon2PasswordHasher"],
)
def test_register_hashes_password_with_argon2() -> None:
    APIClient().post(REGISTER_URL, register_payload(), format="json")
    recruiter = Recruiter.objects.get(email="ada@example.com")
    assert recruiter.password.startswith("argon2$")
    assert recruiter.check_password(PASSWORD)


def test_register_duplicate_email_returns_409() -> None:
    client = APIClient()
    assert client.post(REGISTER_URL, register_payload(), format="json").status_code == 201

    response = client.post(REGISTER_URL, register_payload(email="ADA@example.com"), format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"
    assert Recruiter.objects.count() == 1


def test_register_short_password_is_rejected() -> None:
    response = APIClient().post(REGISTER_URL, register_payload(password="short"), format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_returns_access_token() -> None:
    client = APIClient()
    client.post(REGISTER_URL, register_payload(), format="json")

    response = client.post(
        LOGIN_URL, {"email": "ada@example.com", "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200
    assert AccessToken(response.json()["access"])["role"] == "recruiter"


def test_login_wrong_password_is_generic_401() -> None:
    client = APIClient()
    client.post(REGISTER_URL, register_payload(), format="json")

    response = client.post(
        LOGIN_URL, {"email": "ada@example.com", "password": "wrong-password"}, format="json"
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_unknown_email_matches_wrong_password_response() -> None:
    # No user enumeration: identical code and message for both cases.
    client = APIClient()
    client.post(REGISTER_URL, register_payload(), format="json")

    wrong_password = client.post(
        LOGIN_URL, {"email": "ada@example.com", "password": "wrong-password"}, format="json"
    )
    unknown_email = client.post(
        LOGIN_URL, {"email": "nobody@example.com", "password": PASSWORD}, format="json"
    )
    assert unknown_email.status_code == wrong_password.status_code == 401
    assert unknown_email.json() == wrong_password.json()


def _authenticated_client() -> APIClient:
    client = APIClient()
    response = client.post(REGISTER_URL, register_payload(), format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
    return client


def test_me_requires_authentication() -> None:
    response = APIClient().get(ME_URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_me_returns_own_profile() -> None:
    response = _authenticated_client().get(ME_URL)
    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"
    assert response.json()["company_name"] == "Analytical Engines"


def test_put_me_updates_editable_fields_only() -> None:
    client = _authenticated_client()
    response = client.put(
        ME_URL,
        {"full_name": "Ada B. Lovelace", "company_name": "New Co", "phone": "123"},
        format="json",
    )
    assert response.status_code == 200

    recruiter = Recruiter.objects.get(email="ada@example.com")
    assert recruiter.full_name == "Ada B. Lovelace"
    assert recruiter.company_name == "New Co"
    assert recruiter.phone == "123"
    assert recruiter.email == "ada@example.com"
