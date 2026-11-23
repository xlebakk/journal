"""Center settings and the logo."""

import io
import time
from typing import Any

import pytest
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts import sessions
from apps.audit.models import AuditLog
from apps.core.files import safe_cell
from apps.core.models import CenterSettings

URL = "/api/v1/admin/settings"


@pytest.fixture(autouse=True)
def media(settings: Any, tmp_path: Any) -> Any:
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def image_file(fmt: str = "PNG", size: tuple[int, int] = (800, 400), **save: Any) -> io.BytesIO:
    data = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(data, format=fmt, **save)
    data.seek(0)
    data.name = f"logo.{fmt.lower()}"
    return data


@pytest.mark.django_db
class TestSettings:
    def test_read_and_patch_with_audit(self, admin_client: APIClient) -> None:
        body = admin_client.get(URL).json()
        assert body["edit_window_days"] == 7
        assert body["last_backup_at"] is None
        response = admin_client.patch(
            URL, {"edit_window_days": 10, "center_name": "Центр «Знание»"}, format="json"
        )
        assert response.status_code == 200, response.json()
        assert CenterSettings.load().edit_window_days == 10
        log = AuditLog.objects.get(action="settings.update")
        assert log.before == {"edit_window_days": 7, "center_name": "Учебный центр"}

    def test_ranges_and_url(self, admin_client: APIClient) -> None:
        response = admin_client.patch(URL, {"max_grades_per_lesson": 10}, format="json")
        assert response.status_code == 400
        response = admin_client.patch(URL, {"site_url": "javascript:alert(1)"}, format="json")
        assert response.json() == {"site_url": ["invalid_url"]}

    def test_patch_needs_fresh_password(self, admin_client: APIClient) -> None:
        session = admin_client.session
        session[sessions.REAUTH_AT] = time.time() - 600
        session.save()
        response = admin_client.patch(URL, {"edit_window_days": 3}, format="json")
        assert response.json() == {"detail": "reauth_required"}


@pytest.mark.django_db
class TestLogo:
    def test_upload_reencodes_and_shows_in_branding(
        self, admin_client: APIClient, media: Any
    ) -> None:
        upload = image_file("JPEG", exif=b"Exif\x00\x00secret-gps")
        response = admin_client.post(f"{URL}/logo", {"file": upload}, format="multipart")
        assert response.status_code == 200, response.json()
        assert response.json()["logo"].startswith("data:image/png;base64,")
        stored = list((media / "logo").iterdir())
        assert len(stored) == 1
        assert len(stored[0].stem) == 32
        with Image.open(stored[0]) as saved:
            assert saved.format == "PNG"
            assert max(saved.size) == 512
            assert not saved.info.get("exif")
        assert b"secret-gps" not in stored[0].read_bytes()
        branding = APIClient().get("/api/v1/auth/login").json()
        assert branding["logo"].startswith("data:image/png;base64,")

    def test_replace_and_delete_remove_old_file(
        self, admin_client: APIClient, media: Any, django_capture_on_commit_callbacks: Any
    ) -> None:
        # The old file goes away only after the commit.
        with django_capture_on_commit_callbacks(execute=True):
            admin_client.post(f"{URL}/logo", {"file": image_file()}, format="multipart")
            admin_client.post(f"{URL}/logo", {"file": image_file()}, format="multipart")
        assert len(list((media / "logo").iterdir())) == 1
        with django_capture_on_commit_callbacks(execute=True):
            response = admin_client.delete(f"{URL}/logo")
        assert response.json()["logo"] is None
        assert list((media / "logo").iterdir()) == []
        assert AuditLog.objects.filter(action__startswith="settings.logo").count() == 3

    def test_rejects_non_images_and_big_files(self, admin_client: APIClient, settings: Any) -> None:
        fake = io.BytesIO(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")
        fake.name = "logo.png"
        response = admin_client.post(f"{URL}/logo", {"file": fake}, format="multipart")
        assert response.json() == {"file": ["unsupported_file"]}
        gif = image_file("GIF")
        response = admin_client.post(f"{URL}/logo", {"file": gif}, format="multipart")
        assert response.json() == {"file": ["unsupported_file"]}
        settings.LOGO_MAX_BYTES = 100
        response = admin_client.post(f"{URL}/logo", {"file": image_file()}, format="multipart")
        assert response.json() == {"file": ["file_too_large"]}


def video_file(head: bytes = b"\x00\x00\x00\x18ftypmp42", size: int = 4096) -> io.BytesIO:
    data = io.BytesIO(head + b"\x00" * (size - len(head)))
    data.name = "clip.mp4"
    return data


@pytest.mark.django_db
class TestBrand:
    """Stage 19: one colour for the whole interface and the video of the login page."""

    def test_brand_color_is_validated_and_public(self, admin_client: APIClient) -> None:
        response = admin_client.patch(URL, {"brand_color": "red"}, format="json")
        assert response.json() == {"brand_color": ["invalid_color"]}
        response = admin_client.patch(URL, {"brand_color": "#1F7A5C"}, format="json")
        assert response.json()["brand_color"] == "#1f7a5c"
        assert APIClient().get("/api/v1/auth/login").json()["brand_color"] == "#1f7a5c"
        assert AuditLog.objects.get(action="settings.update").after == {"brand_color": "#1f7a5c"}

    def test_video_upload_serve_and_delete(
        self, admin_client: APIClient, media: Any, django_capture_on_commit_callbacks: Any
    ) -> None:
        with django_capture_on_commit_callbacks(execute=True):
            response = admin_client.post(f"{URL}/video", {"file": video_file()}, format="multipart")
        url = response.json()["login_video"]
        assert url.startswith("/api/v1/branding/video/")
        assert url.endswith(".mp4")
        assert APIClient().get("/api/v1/auth/login").json()["login_video"] == url
        anonymous = APIClient()
        whole = anonymous.get(url)
        assert whole.status_code == 200
        assert whole["Content-Type"] == "video/mp4"
        assert len(b"".join(whole.streaming_content)) == 4096  # type: ignore[attr-defined]
        part = anonymous.get(url, HTTP_RANGE="bytes=10-19")
        assert part.status_code == 206
        assert part["Content-Range"] == "bytes 10-19/4096"
        assert len(part.content) == 10
        assert anonymous.get(url, HTTP_RANGE="bytes=9000-").status_code == 416
        # Only the current file is served; other names are 404.
        assert anonymous.get("/api/v1/branding/video/" + "0" * 32 + ".mp4").status_code == 404
        assert anonymous.get("/api/v1/branding/video/..%2Fsecret").status_code == 404
        with django_capture_on_commit_callbacks(execute=True):
            response = admin_client.delete(f"{URL}/video")
        assert response.json()["login_video"] is None
        assert list((media / "video").iterdir()) == []
        assert anonymous.get(url).status_code == 404
        assert AuditLog.objects.filter(action__startswith="settings.video").count() == 2

    def test_video_rejects_other_files(self, admin_client: APIClient, settings: Any) -> None:
        response = admin_client.post(
            f"{URL}/video", {"file": video_file(head=b"<html><script>")}, format="multipart"
        )
        assert response.json() == {"file": ["unsupported_video"]}
        webm = admin_client.post(
            f"{URL}/video", {"file": video_file(head=b"\x1a\x45\xdf\xa3")}, format="multipart"
        )
        assert webm.json()["login_video"].endswith(".webm")
        settings.LOGIN_VIDEO_MAX_BYTES = 100
        response = admin_client.post(f"{URL}/video", {"file": video_file()}, format="multipart")
        assert response.json() == {"file": ["file_too_large"]}


@pytest.mark.parametrize(
    ("value", "expected"),
    [("=1+1", "'=1+1"), ("+7", "'+7"), ("-x", "'-x"), ("@a", "'@a"), ("ok", "ok"), (5, 5)],
)
def test_safe_cell(value: Any, expected: Any) -> None:
    assert safe_cell(value) == expected
