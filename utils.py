import os
import subprocess
import sys


def open_with_default_app(path: str, app_instance=None) -> subprocess.Popen:
    """Launch *path* with the OS default application."""
    if app_instance and hasattr(app_instance, "current_video_process") and app_instance.current_video_process:
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
