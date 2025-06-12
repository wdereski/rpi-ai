from __future__ import annotations
import os
import sys
import subprocess
import json
from pathlib import Path
from typing import List

DB_FILE = "Dereski_media_metadata_master.db"
PHOTOS_DIR = Path("photos_export")
JSONL_CHUNK = 4 * 1024 * 1024

IMAGE_MAX = (500, 350)
VIDEO_MAX = (500, 350)
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}

def open_with_default_app(path: str, app_instance=None) -> subprocess.Popen | None:
    """Launch *path* with the system default application and track the process."""
    if app_instance and getattr(app_instance, 'current_video_process', None):
        try:
            app_instance.current_video_process.terminate()
            app_instance.current_video_process.wait(timeout=2)
        except Exception:
            try:
                app_instance.current_video_process.kill()
            except Exception:
                pass
        app_instance.current_video_process = None

    if sys.platform.startswith("darwin"):
        process = subprocess.Popen(["open", path])
    elif sys.platform.startswith(("win32", "cygwin")):
        os.startfile(path)  # type: ignore[attr-defined]
        process = None
    else:
        process = subprocess.Popen(["xdg-open", path])
    return process


def safe_json_list(text: str) -> List[str]:
    """Parse JSON text as a list, return empty list if invalid."""
    if not text:
        return []
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, list) else [str(obj)]
    except (json.JSONDecodeError, TypeError):
        return [s.strip() for s in text.split(',') if s.strip()]


def safe_json_str(text: str) -> str:
    """Parse JSON text, return string representation if invalid."""
    if not text:
        return ""
    try:
        obj = json.loads(text)
        return str(obj) if not isinstance(obj, str) else obj
    except (json.JSONDecodeError, TypeError):
        return text
