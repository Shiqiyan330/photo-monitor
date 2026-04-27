from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import asyncio

class PhotoHandler(FileSystemEventHandler):
    def __init__(self, manager):
        self.manager = manager

    def on_created(self, event):
        if not event.is_directory:
            asyncio.run(self.manager.broadcast({
                "type": "new_photo",
                "path": event.src_path
            }))


def start_watch(folder: Path, manager):
    observer = Observer()
    handler = PhotoHandler(manager)

    observer.schedule(handler, str(folder), recursive=True)
    observer.start()