"""Admin-site login: env credentials, token exchange, fail-closed behaviour."""

from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

URL = "/internal/admin/login"


@override_settings(ADMIN_USERNAME="admin", ADMIN_PASSWORD="secret-pass")
def test_valid_credentials_return_internal_token() -> None:
    response = APIClient().post(
        URL, {"username": "admin", "password": "secret-pass"}, format="json"
    )
    assert response.status_code == 200
    assert response.json() == {"service": "candidate", "token": "test-internal-token"}


@override_settings(ADMIN_USERNAME="admin", ADMIN_PASSWORD="secret-pass")
def test_wrong_password_is_rejected() -> None:
    response = APIClient().post(URL, {"username": "admin", "password": "nope"}, format="json")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@override_settings(ADMIN_USERNAME="", ADMIN_PASSWORD="")
def test_missing_configuration_fails_closed() -> None:
    response = APIClient().post(URL, {"username": "admin", "password": "x"}, format="json")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ADMIN_LOGIN_DISABLED"
