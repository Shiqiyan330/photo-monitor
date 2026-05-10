from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from routers.deps import require_file_access, require_file_edit_access, require_ledger_access, require_ledger_upload_access, require_study_access, require_study_edit_access, require_upload_access
from services.auth_service import employee_system
from services.upload_service import (
    delete_data_upload,
    get_data_upload,
    list_data_uploads,
    save_data_upload_file,
    save_photo_upload_file,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])

PHOTO_BASE = Path(__file__).resolve().parents[1] / "photos"
DATA_BASE = Path(__file__).resolve().parents[1] / "office_data"


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _user_from_token(token: str | None) -> dict | None:
    user = employee_system.get_user_by_token(token)
    return user.to_public_dict() if user else None


def _require_permission(user: dict, permissions: set[str], detail: str) -> dict:
    if user["role"] == "admin":
        return user
    user_permissions = set(user.get("permissions") or [])
    if not user_permissions.intersection(permissions):
        raise HTTPException(status_code=403, detail=detail)
    return user


def get_file_view_user(
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    user = _user_from_token(token) or _user_from_token(_extract_bearer_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return _require_permission(user, {"company_files_view"}, "No permission to access files")


def get_study_view_user(
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    user = _user_from_token(token) or _user_from_token(_extract_bearer_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return _require_permission(user, {"study_view", "study_edit"}, "No permission to access study articles")


def get_ledger_view_user(
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    user = _user_from_token(token) or _user_from_token(_extract_bearer_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return _require_permission(user, {"ledger_view"}, "No permission to access ledgers")


def inline_file_response(target: Path, item: dict) -> FileResponse:
    response = FileResponse(target, media_type=item.get("content_type"))
    ascii_name = item["id"] or "preview"
    encoded_name = quote(item["name"])
    response.headers["Content-Disposition"] = f"inline; filename={ascii_name}; filename*=UTF-8''{encoded_name}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


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
    user: dict = Depends(require_file_edit_access),
):
    item = save_data_upload_file(DATA_BASE, "company_files", file, department, user)
    return {"success": True, "item": item}


@router.get("/files")
def get_uploaded_files(user: dict = Depends(require_file_access)):
    return {"items": list_data_uploads(DATA_BASE, "company_files", user)}


@router.get("/files/{upload_id}/download")
def download_uploaded_file(upload_id: str, user: dict = Depends(require_file_access)):
    target, item = get_data_upload(DATA_BASE, "company_files", upload_id, user)
    return FileResponse(target, filename=item["name"], media_type=item.get("content_type"))


@router.get("/files/{upload_id}/view")
def view_uploaded_file(upload_id: str, user: dict = Depends(get_file_view_user)):
    target, item = get_data_upload(DATA_BASE, "company_files", upload_id, user)
    return inline_file_response(target, item)


@router.delete("/files/{upload_id}")
def delete_uploaded_file(upload_id: str, user: dict = Depends(require_file_edit_access)):
    item = delete_data_upload(DATA_BASE, "company_files", upload_id, user)
    return {"success": True, "item": item}


@router.post("/study-articles")
def upload_study_article(
    department: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(require_study_edit_access),
):
    item = save_data_upload_file(DATA_BASE, "study_articles", file, department, user)
    return {"success": True, "item": item}


@router.get("/study-articles")
def get_study_articles(user: dict = Depends(require_study_access)):
    return {"items": list_data_uploads(DATA_BASE, "study_articles", user)}


@router.get("/study-articles/{upload_id}/download")
def download_study_article(upload_id: str, user: dict = Depends(require_study_access)):
    target, item = get_data_upload(DATA_BASE, "study_articles", upload_id, user)
    return FileResponse(target, filename=item["name"], media_type=item.get("content_type"))


@router.get("/study-articles/{upload_id}/view")
def view_study_article(upload_id: str, user: dict = Depends(get_study_view_user)):
    target, item = get_data_upload(DATA_BASE, "study_articles", upload_id, user)
    return inline_file_response(target, item)


@router.delete("/study-articles/{upload_id}")
def delete_study_article(upload_id: str, user: dict = Depends(require_study_edit_access)):
    item = delete_data_upload(DATA_BASE, "study_articles", upload_id, user)
    return {"success": True, "item": item}


@router.post("/ledgers")
def upload_ledger_data(
    department: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(require_ledger_upload_access),
):
    item = save_data_upload_file(DATA_BASE, "ledgers", file, department, user)
    return {"success": True, "item": item}


@router.get("/ledgers")
def get_uploaded_ledgers(user: dict = Depends(require_ledger_access)):
    return {"items": list_data_uploads(DATA_BASE, "ledgers", user)}


@router.get("/ledgers/{upload_id}/download")
def download_uploaded_ledger(upload_id: str, user: dict = Depends(require_ledger_access)):
    target, item = get_data_upload(DATA_BASE, "ledgers", upload_id, user)
    return FileResponse(target, filename=item["name"], media_type=item.get("content_type"))


@router.get("/ledgers/{upload_id}/view")
def view_uploaded_ledger(upload_id: str, user: dict = Depends(get_ledger_view_user)):
    target, item = get_data_upload(DATA_BASE, "ledgers", upload_id, user)
    return inline_file_response(target, item)


@router.delete("/ledgers/{upload_id}")
def delete_uploaded_ledger(upload_id: str, user: dict = Depends(require_ledger_upload_access)):
    item = delete_data_upload(DATA_BASE, "ledgers", upload_id, user)
    return {"success": True, "item": item}
