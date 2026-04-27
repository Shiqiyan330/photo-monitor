import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers import admin, auth, photo, ws
from services.watcher_service import start_watch

BASE_DIR = Path(__file__).resolve().parent / "photos"
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
app.include_router(ws.router)


def run_watch():
    from routers.ws import manager

    start_watch(BASE_DIR, manager)


threading.Thread(target=run_watch, daemon=True).start()

app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")
