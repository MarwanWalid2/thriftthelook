"""Endpoint coverage for the judge-safe offline path."""

from fastapi.testclient import TestClient

from api.main import app, format_style_profile


def test_health_reports_offline_mode() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "offline"}


def test_outfit_stream_includes_complete_demo_payload() -> None:
    client = TestClient(app)

    response = client.get("/api/outfit?budget=75")

    assert response.status_code == 200
    assert "event: progress" in response.text
    assert "event: complete" in response.text
    assert "Synthetic demo inventory" in response.text


def test_uploaded_photo_replays_offline_demo_without_provider_keys() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/outfit",
        data={"budget": "75"},
        files={"photo": ("outfit.jpg", b"synthetic-image", "image/jpeg")},
    )

    assert response.status_code == 200
    assert "event: complete" in response.text
    assert '"mode": "offline"' in response.text


def test_research_exclusion_changes_the_offline_result() -> None:
    client = TestClient(app)

    response = client.get("/api/outfit?budget=150&exclude_ids=demo-jacket-1")

    assert response.status_code == 200
    assert "demo-jacket-1\"" not in response.text


def test_offline_result_uses_submitted_delivery_zip() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/outfit",
        data={"budget": "75", "delivery_zip": "10001"},
        files={"photo": ("outfit.jpg", b"synthetic-image", "image/jpeg")},
    )

    assert response.status_code == 200
    assert '"zip": "10001"' in response.text


def test_style_profile_normalizes_user_preferences() -> None:
    profile = format_style_profile(" M ", " neon  red ", " very good ")

    assert profile == (
        "Size: M; colors to avoid: neon red; minimum condition: very good."
    )
