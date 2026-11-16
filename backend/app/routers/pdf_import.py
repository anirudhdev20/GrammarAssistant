from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import get_settings
from ..pdf import extract_pdf_text

router = APIRouter(prefix="/api/import", tags=["import"])


class PdfImportResponse(BaseModel):
    text: str
    filename: str
    pages: int
    pages_read: int
    characters: int
    truncated: bool


@router.post("/pdf", response_model=PdfImportResponse)
async def import_pdf(file: UploadFile = File(...)) -> PdfImportResponse:
    settings = get_settings()
    data = await file.read(settings.max_pdf_bytes + 1)
    await file.close()

    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > settings.max_pdf_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"PDF is larger than the {settings.max_pdf_bytes // (1024 * 1024)} MB limit.",
        )
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="Upload a valid PDF file.")

    try:
        text, pages, pages_read, truncated = extract_pdf_text(
            data, settings.max_pdf_pages, settings.max_text_chars
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return PdfImportResponse(
        text=text,
        filename=(file.filename or "document.pdf")[:200],
        pages=pages,
        pages_read=pages_read,
        characters=len(text),
        truncated=truncated,
    )
