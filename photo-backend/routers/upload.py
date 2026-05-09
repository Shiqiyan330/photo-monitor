from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from routers.deps import require_file_access, require_upload_access
from services.upload_service import (
    delete_data_upload,
    get_data_upload,
    list_data_uploads,
    save_data_upload_file,
    save_photo_upload_file,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])

PHOTO_BASE = Path(__file__).resolve().parents[1] / "photos"
DATA_BASE = Path(__file__).resolve().parents[1] / "uploaded_data"


@router.post("")
def upload_data(
    department: str = Form(...),
    station: str = Form("uploads"),
    file: UploadFile = File(...),
    user: dict = Depends(require_upload_access),
):
    item = save_photo_upload_file(PHOTO_BASE, file, department, station, user)
    return {"success": True, "item": item}


@router.post("/files")
def upload_file_data(
    department: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(require_upload_access),
):
    item = save_data_upload_file(DATA_BASE, "files", file, department, user)
    return {"success": True, "item": item}


@router.get("/files")
def get_uploaded_files(user: dict = Depends(require_file_access)):
    return {"items": list_data_uploads(DATA_BASE, "files", user)}


@router.get("/files/{upload_id}/download")
def download_uploaded_file(upload_id: str, user: dict = Depends(require_file_access)):
    target, item = get_data_upload(DATA_BASE, "files", upload_id, user)
    return FileResponse(target, filename=item["name"], media_type=item.get("content_type"))


@router.delete("/files/{upload_id}")
def delete_uploaded_file(upload_id: str, user: dict = Depends(require_file_access)):
    item = delete_data_upload(DATA_BASE, "files", upload_id, user)
    return {"success": True, "item": item}


@router.post("/ledgers")
def upload_ledger_data(
    department: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(require_upload_access),
):
    item = save_data_upload_file(DATA_BASE, "ledgers", file, department, user)
    return {"success": True, "item": item}


@router.get("/ledgers")
def get_uploaded_ledgers(user: dict = Depends(require_upload_access)):
    return {"items": list_data_uploads(DATA_BASE, "ledgers", user)}


@router.get("/ledgers/{upload_id}/download")
def download_uploaded_ledger(upload_id: str, user: dict = Depends(require_upload_access)):
    target, item = get_data_upload(DATA_BASE, "ledgers", upload_id, user)
    return FileResponse(target, filename=item["name"], media_type=item.get("content_type"))


@router.delete("/ledgers/{upload_id}")
def delete_uploaded_ledger(upload_id: str, user: dict = Depends(require_upload_access)):
    item = delete_data_upload(DATA_BASE, "ledgers", upload_id, user)
    return {"success": True, "item": item}
