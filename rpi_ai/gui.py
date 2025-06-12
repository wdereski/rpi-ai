from __future__ import annotations
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import ImageTk, Image

from .database import MetadataDB
from .utils import PHOTOS_DIR, VIDEO_EXTENSIONS
from . import image_utils, video_utils


class MetadataEditorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Media Metadata Editor")
        self.geometry("800x600")
        self.db = MetadataDB()
        self.current_file: str | None = None
        self.current_img = None
        self.video_player = None
        self.video_frame = None
        self.video_controls = ttk.Frame(self)
        self._build_widgets()
        self._populate_tree()

    def _build_widgets(self) -> None:
        self.tree = ttk.Treeview(self, columns=("desc",), show="headings")
        self.tree.heading("desc", text="Description")
        self.tree.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        self.preview_frame = ttk.Frame(self)
        self.preview_frame.pack(fill="both", expand=True)
        self.preview_lbl = ttk.Label(self.preview_frame)
        self.preview_lbl.pack()

    def _populate_tree(self) -> None:
        for row in self.db.fetch_all():
            desc = row["description"] or ""
            self.tree.insert("", "end", iid=row["file_name"], values=(desc,))

    def on_tree_select(self, event) -> None:
        iid = self.tree.selection()[0]
        row = self.db.fetch_one(iid)
        if not row:
            return
        self.current_file = row["file_name"]
        path = PHOTOS_DIR / row["file_name"]
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            video_utils.setup_video_player(self, path)
        else:
            image_utils.setup_image_preview(self, path)

    def quit(self) -> None:
        video_utils.stop_video(self)
        self.db.conn.close()
        super().quit()
