from io import BytesIO

from pypdf import PdfWriter

from app.pdf import build_pdf


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model"].endswith("web_sm")


def test_analyze_spelling(client):
    response = client.post("/api/analyze", json={"text": "I recieve teh mail.", "include_stats": True})
    assert response.status_code == 200
    body = response.json()
    assert body["stats"]["words"] == 4
    assert any(issue["type"] == "spelling" for issue in body["issues"])
    assert "language_tool_disabled" in body["degraded"]


def test_analyze_category_filter(client):
    response = client.post(
        "/api/analyze",
        json={"text": "I recieve teh mail , now.", "categories": ["style"], "include_stats": False},
    )
    assert response.status_code == 200
    assert all(issue["type"] == "style" for issue in response.json()["issues"])


def test_analyze_min_severity(client):
    response = client.post(
        "/api/analyze",
        json={"text": "I recieve teh mail , now.", "min_severity": "error", "include_stats": False},
    )
    assert response.status_code == 200
    assert all(issue["severity"] == "error" for issue in response.json()["issues"])


def test_rewrite(client):
    payload = {"text": "I recieve teh mail.", "start": 2, "end": 9, "replacement": "receive"}
    response = client.post("/api/rewrite", json=payload)
    assert response.status_code == 200
    assert response.json()["text"] == "I receive teh mail."


def test_rewrite_invalid_span(client):
    payload = {"text": "short", "start": 2, "end": 99, "replacement": "x"}
    assert client.post("/api/rewrite", json=payload).status_code == 422


def test_dictionary_roundtrip(client):
    assert client.post("/api/dictionary", json={"word": "zqwv"}).status_code == 200
    assert "zqwv" in client.get("/api/dictionary").json()["words"]
    assert client.delete("/api/dictionary/zqwv").status_code == 200
    assert "zqwv" not in client.get("/api/dictionary").json()["words"]


def test_analyze_rejects_too_long_text(client):
    response = client.post("/api/analyze", json={"text": "a" * 60001})
    assert response.status_code == 422


def test_pdf_export(client):
    text = "First paragraph with a correction.\n\nSecond paragraph follows here."
    response = client.post("/api/export/pdf", json={"text": text, "title": "My Draft"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=\"grammar-assistant-" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 800


def test_pdf_export_handles_unicode(client):
    response = client.post(
        "/api/export/pdf",
        json={"text": "Caf\u00e9 \u2014 \u201cquoted\u201d \U0001F600 text."},
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_pdf_export_rejects_blank_text(client):
    assert client.post("/api/export/pdf", json={"text": ""}).status_code == 422
    assert client.post("/api/export/pdf", json={"text": "   "}).status_code == 422


def test_pdf_import_extracts_text(client):
    pdf = build_pdf("I recieve teh mail.\n\nSecond paragraph for import.")
    response = client.post(
        "/api/import/pdf",
        files={"file": ("draft.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "recieve teh mail" in body["text"]
    assert body["filename"] == "draft.pdf"
    assert body["pages"] == 1
    assert body["pages_read"] == 1
    assert body["characters"] == len(body["text"])
    assert body["truncated"] is False


def test_pdf_import_rejects_non_pdf(client):
    response = client.post(
        "/api/import/pdf",
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 415


def test_pdf_import_rejects_blank_pdf(client):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    response = client.post(
        "/api/import/pdf",
        files={"file": ("blank.pdf", buffer.getvalue(), "application/pdf")},
    )
    assert response.status_code == 422
    assert "No selectable text" in response.json()["detail"]


def test_pdf_import_rejects_password_protected_pdf(client):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    buffer = BytesIO()
    writer.write(buffer)
    response = client.post(
        "/api/import/pdf",
        files={"file": ("locked.pdf", buffer.getvalue(), "application/pdf")},
    )
    assert response.status_code == 422
    assert "password-protected" in response.json()["detail"]
