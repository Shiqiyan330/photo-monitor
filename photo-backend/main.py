import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from routers import admin, auth, photo, structure, upload, ws
from services.auth_service import employee_system
from services.photo_cleanup_service import start_photo_cleanup_scheduler
from services.sms_service import start_sms_scheduler
from services.watcher_service import start_watch

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent / "photos"
OFFICE_DATA_DIR = Path(__file__).resolve().parent / "office_data"
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(photo.router)
app.include_router(structure.router)
app.include_router(upload.router)
app.include_router(ws.router)


def run_watch():
    from routers.ws import manager

    start_watch(BASE_DIR, manager)


threading.Thread(target=run_watch, daemon=True).start()
start_photo_cleanup_scheduler(BASE_DIR)
start_sms_scheduler(employee_system)

OFFICE_DATA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/office-data", StaticFiles(directory=OFFICE_DATA_DIR), name="office-data")
