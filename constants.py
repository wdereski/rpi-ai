# Ensure path operations work reliably
from pathlib import Path
import os
# Application constants
DB_FILE = os.path.join("/Users", "williamdereski", "Pictures", "metadata", "Dereski_media_metadata_master.db")


PHOTOS_DIR = Path(
    "/Users/williamdereski/Pictures/metadata/photos_export"
)



JSONL_CHUNK = 4 * 1024 * 1024  # 4 MB

IMAGE_MAX = (500, 350)  # preview size (w, h)
VIDEO_MAX = (500, 350)  # video player size (w, h)

# Video file extensions
VIDEO_EXTENSIONS = {
    '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'
}
