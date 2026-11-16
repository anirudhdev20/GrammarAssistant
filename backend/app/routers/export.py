from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..pdf import build_pdf

router = APIRouter(prefix="/api/export", tags=["export"])


class PdfExportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=60000)
    title: str = Field(default="Grammar Assistant", min_length=1, max_length=120)


@router.post("/pdf")
def export_pdf(payload: PdfExportRequest) -> Response:
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="text must not be blank")
    pdf = build_pdf(payload.text, payload.title)
    filename = f"grammar-assistant-{datetime.now(timezone.utc):%Y-%m-%d}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
