from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from routers.deps import require_upload_access
from services.upload_service import save_upload_file

router = APIRouter(prefix="/uploads", tags=["uploads"])

BASE = Path(__file__).resolve().parents[1] / "photos"


@router.post("")
def upload_data(
    department: str = Form(...),
    station: str = Form("uploads"),
    file: UploadFile = File(...),
    user: dict = Depends(require_upload_access),
):
    item = save_upload_file(BASE, file, department, station, user)
    return {"success": True, "item": item}
