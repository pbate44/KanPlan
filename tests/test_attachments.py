"""Tests for app/views/attachments.py"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import Resolver404, resolve, reverse

from app.models import Board, Card, CardAttachment, Column, Swimlane


@pytest.fixture
def swimlane_card(user):
    """A card on its own board, assigned to a swimlane."""
    board = Board.objects.create(name="Attachment Board", owner=user)
    column = Column.objects.create(name="Todo", board=board, position=0)
    swimlane = Swimlane.objects.create(name="Lane", board=board, position=0)
    return Card.objects.create(
        title="Attachment Card", column=column, swimlane=swimlane, position=0
    )


@pytest.fixture
def attachment(swimlane_card):
    """A CardAttachment already saved to the test card."""
    f = SimpleUploadedFile("existing.png", b"fakepng", content_type="image/png")
    return CardAttachment.objects.create(
        card=swimlane_card,
        file=f,
        filename="existing.png",
        file_type="image/png",
        file_size=7,
    )


@pytest.mark.django_db
class TestAttachmentUpload:

    def test_upload_valid_image_creates_record(self, auth_client, swimlane_card):
        url = reverse("upload_attachment", args=[swimlane_card.pk])
        f = SimpleUploadedFile("photo.png", b"x" * 100, content_type="image/png")
        response = auth_client.post(url, {"file": f})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["filename"] == "photo.png"
        assert data["file_type"] == "image/png"
        assert CardAttachment.objects.filter(card=swimlane_card).count() == 1

    def test_upload_valid_pdf(self, auth_client, swimlane_card):
        url = reverse("upload_attachment", args=[swimlane_card.pk])
        f = SimpleUploadedFile("report.pdf", b"pdfdata", content_type="application/pdf")
        response = auth_client.post(url, {"file": f})
        assert response.status_code == 200
        assert response.json()["file_type"] == "application/pdf"

    def test_upload_response_includes_all_fields(self, auth_client, swimlane_card):
        url = reverse("upload_attachment", args=[swimlane_card.pk])
        f = SimpleUploadedFile("img.jpg", b"jpgdata", content_type="image/jpeg")
        data = auth_client.post(url, {"file": f}).json()
        for field in ("attachment_id", "filename", "file_type", "file_size", "icon_class", "upload_date"):
            assert field in data, f"Missing field: {field}"

    def test_upload_disallowed_extension_rejected(self, auth_client, swimlane_card):
        url = reverse("upload_attachment", args=[swimlane_card.pk])
        f = SimpleUploadedFile("script.exe", b"mzdata", content_type="application/octet-stream")
        response = auth_client.post(url, {"file": f})
        assert response.status_code == 400
        assert response.json()["status"] == "error"

    def test_upload_extension_mime_mismatch_rejected(self, auth_client, swimlane_card):
        url = reverse("upload_attachment", args=[swimlane_card.pk])
        # .png extension but declares text/plain — not in the .png allow-set
        f = SimpleUploadedFile("disguised.png", b"notimage", content_type="text/plain")
        response = auth_client.post(url, {"file": f})
        assert response.status_code == 400

    def test_upload_oversized_file_rejected(self, auth_client, swimlane_card, settings):
        settings.MAX_UPLOAD_SIZE = 10  # 10 bytes for this test only
        url = reverse("upload_attachment", args=[swimlane_card.pk])
        f = SimpleUploadedFile("big.png", b"x" * 100, content_type="image/png")
        response = auth_client.post(url, {"file": f})
        assert response.status_code == 400
        assert response.json()["status"] == "error"

    def test_upload_no_file_provided(self, auth_client, swimlane_card):
        url = reverse("upload_attachment", args=[swimlane_card.pk])
        response = auth_client.post(url)
        assert response.status_code == 400
        assert response.json()["message"] == "No file was provided"

    def test_upload_nonexistent_card_returns_404(self, auth_client):
        url = reverse("upload_attachment", args=[99999])
        f = SimpleUploadedFile("photo.png", b"data", content_type="image/png")
        response = auth_client.post(url, {"file": f})
        assert response.status_code == 404

    def test_upload_requires_post(self, auth_client, swimlane_card):
        url = reverse("upload_attachment", args=[swimlane_card.pk])
        assert auth_client.get(url).status_code == 405


@pytest.mark.django_db
class TestGetAttachments:

    def test_list_returns_existing_attachments(self, auth_client, swimlane_card, attachment):
        url = reverse("get_attachments", args=[swimlane_card.pk])
        response = auth_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["attachments"]) == 1
        assert data["attachments"][0]["filename"] == "existing.png"

    def test_list_empty_when_no_attachments(self, auth_client, swimlane_card):
        url = reverse("get_attachments", args=[swimlane_card.pk])
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response.json()["attachments"] == []

    def test_list_includes_icon_class_and_upload_date(self, auth_client, swimlane_card, attachment):
        url = reverse("get_attachments", args=[swimlane_card.pk])
        item = auth_client.get(url).json()["attachments"][0]
        assert "icon_class" in item
        assert "upload_date" in item

    def test_list_requires_get(self, auth_client, swimlane_card):
        url = reverse("get_attachments", args=[swimlane_card.pk])
        assert auth_client.post(url).status_code == 405


@pytest.mark.django_db
class TestAttachmentView:

    def test_view_serves_file_inline(self, auth_client, attachment):
        url = reverse("view_attachment", args=[attachment.pk])
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        assert response["Content-Disposition"].startswith("inline")
        assert b"".join(response.streaming_content) == b"fakepng"

    def test_view_downloads_disallowed_type(self, auth_client, swimlane_card):
        # e.g. an HTML file uploaded before the type checks existed
        attachment = CardAttachment.objects.create(
            card=swimlane_card,
            file=SimpleUploadedFile("page.html", b"<script></script>", content_type="text/html"),
            filename="page.html",
            file_type="text/html",
            file_size=17,
        )
        response = auth_client.get(reverse("view_attachment", args=[attachment.pk]))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/octet-stream"
        assert response["Content-Disposition"].startswith("attachment")

    def test_view_missing_file_returns_404(self, auth_client, attachment):
        attachment.file.delete(save=False)
        url = reverse("view_attachment", args=[attachment.pk])
        assert auth_client.get(url).status_code == 404

    def test_attachments_not_served_from_public_media_route(self):
        with pytest.raises(Resolver404):
            resolve("/media/card_attachments/existing.png")

    def test_view_nonexistent_attachment_returns_404(self, auth_client):
        url = reverse("view_attachment", args=[99999])
        assert auth_client.get(url).status_code == 404


@pytest.mark.django_db
class TestAttachmentDelete:

    def test_delete_removes_db_record(self, auth_client, swimlane_card, attachment):
        pk = attachment.pk
        url = reverse("delete_attachment", args=[pk])
        response = auth_client.post(url)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert not CardAttachment.objects.filter(pk=pk).exists()

    def test_delete_nonexistent_attachment_returns_404(self, auth_client):
        url = reverse("delete_attachment", args=[99999])
        assert auth_client.post(url).status_code == 404

    def test_delete_requires_post(self, auth_client, attachment):
        url = reverse("delete_attachment", args=[attachment.pk])
        assert auth_client.get(url).status_code == 405


@pytest.mark.django_db
class TestAttachmentPermissions:

    def test_unauthenticated_upload_redirects(self, client, swimlane_card):
        url = reverse("upload_attachment", args=[swimlane_card.pk])
        f = SimpleUploadedFile("photo.png", b"data", content_type="image/png")
        assert client.post(url, {"file": f}).status_code == 302

    def test_unauthenticated_list_redirects(self, client, swimlane_card):
        url = reverse("get_attachments", args=[swimlane_card.pk])
        assert client.get(url).status_code == 302

    def test_unauthenticated_view_redirects(self, client, attachment):
        url = reverse("view_attachment", args=[attachment.pk])
        assert client.get(url).status_code == 302

    def test_unauthenticated_delete_redirects(self, client, attachment):
        url = reverse("delete_attachment", args=[attachment.pk])
        assert client.post(url).status_code == 302

    def test_other_user_cannot_upload_to_card(self, client, other_user, swimlane_card):
        client.force_login(other_user)
        url = reverse("upload_attachment", args=[swimlane_card.pk])
        f = SimpleUploadedFile("photo.png", b"data", content_type="image/png")
        assert client.post(url, {"file": f}).status_code == 404

    def test_other_user_cannot_list_card_attachments(self, client, other_user, swimlane_card):
        client.force_login(other_user)
        url = reverse("get_attachments", args=[swimlane_card.pk])
        assert client.get(url).status_code == 404

    def test_other_user_cannot_view_attachment(self, client, other_user, attachment):
        client.force_login(other_user)
        url = reverse("view_attachment", args=[attachment.pk])
        assert client.get(url).status_code == 404

    def test_other_user_cannot_delete_attachment(self, client, other_user, attachment):
        client.force_login(other_user)
        url = reverse("delete_attachment", args=[attachment.pk])
        assert client.post(url).status_code == 404


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _attachment_of_type(card, filename, mime, content=b"data"):
    return CardAttachment.objects.create(
        card=card,
        file=SimpleUploadedFile(filename, content, content_type=mime),
        filename=filename,
        file_type=mime,
        file_size=len(content),
    )


@pytest.mark.django_db
class TestAttachmentFileTypes:

    @pytest.mark.parametrize("filename,mime,icon", [
        ("sheet.xlsx", XLSX_MIME, "bi-file-excel"),
        ("data.csv", "text/csv", "bi-file-excel"),
        ("notes.txt", "text/plain", "bi-file-text"),
        ("doc.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "bi-file-word"),
        ("report.pdf", "application/pdf", "bi-file-pdf"),
        ("photo.png", "image/png", "bi-file-image"),
    ])
    def test_icon_class(self, swimlane_card, filename, mime, icon):
        assert _attachment_of_type(swimlane_card, filename, mime).get_icon_class() == icon

    def test_xlsx_is_not_parsed_as_word(self, swimlane_card):
        from app.services.ai_service import get_file_content_from_storage
        att = _attachment_of_type(swimlane_card, "sheet.xlsx", XLSX_MIME, b"PK-not-a-docx")
        assert get_file_content_from_storage(att) == "[Unsupported file type for content extraction]"

    def test_csv_is_parsed_as_csv(self, swimlane_card):
        from app.services.ai_service import get_file_content_from_storage
        att = _attachment_of_type(swimlane_card, "data.csv", "text/csv", b"a,b\n1,2\n")
        assert get_file_content_from_storage(att) == "a,b\n1,2"


@pytest.mark.django_db
class TestAttachmentsWithoutSwimlane:

    def test_card_without_swimlane_can_list_and_upload(self, auth_client, card):
        assert card.swimlane is None
        assert auth_client.get(reverse("get_attachments", args=[card.pk])).status_code == 200
        f = SimpleUploadedFile("photo.png", b"x" * 10, content_type="image/png")
        resp = auth_client.post(reverse("upload_attachment", args=[card.pk]), {"file": f})
        assert resp.status_code == 200
