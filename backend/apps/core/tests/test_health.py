import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_is_public_and_ok() -> None:
    response = APIClient().get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_unknown_api_url_returns_json_404() -> None:
    response = APIClient().get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}
