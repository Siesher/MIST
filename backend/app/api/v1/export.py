"""Export API endpoint for PDF progress reports."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.auth import get_optional_user
from backend.app.models.database import get_db
from backend.app.models.tables import UserTable
from backend.app.services.export_service import get_export_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/report.pdf")
async def export_report_pdf(
    user_id: str = Query(...),
    user_name: str = Query(default="Студент"),
    db: AsyncSession = Depends(get_db),
    user: UserTable | None = Depends(get_optional_user),
):
    """Generate and download a PDF progress report.

    Anti-IDOR: user_id берётся только из токена; анонимный запрос с
    произвольным user_id не должен отдавать чужой отчёт.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user_id = user.id
    user_name = user.display_name or user_name
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
