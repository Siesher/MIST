"""Export API endpoint for PDF progress reports."""

import logging
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.database import get_db
from backend.app.services.export_service import get_export_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/report.pdf")
async def export_report_pdf(
    user_id: str = Query(...),
    user_name: str = Query(default="Студент"),
    db: AsyncSession = Depends(get_db),
):
    """Generate and download a PDF progress report."""
    service = await get_export_service()
    pdf_bytes = await service.generate_report_pdf(db, user_id, user_name)

    content_type = "application/pdf"
    filename = "mits_report.pdf"

    # If WeasyPrint was not available, export service returns HTML
    if pdf_bytes[:5] == b"<!DOC":
        content_type = "text/html; charset=utf-8"
        filename = "mits_report.html"

    return Response(
        content=pdf_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
