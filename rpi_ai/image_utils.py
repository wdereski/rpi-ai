from __future__ import annotations
import os
from pathlib import Path
from PIL import Image, ImageTk
from tkinter import ttk, messagebox

from .utils import IMAGE_MAX


def setup_image_preview(app, img_path: Path) -> None:
    """Set up the image preview in the GUI."""
    app.stop_video()
    if getattr(app, 'video_player', None):
        app.video_player.destroy()
        app.video_player = None
    if getattr(app, 'video_frame', None):
        app.video_frame.destroy()
        app.video_frame = None

    app.video_controls.pack_forget()
    for widget in app.video_controls.winfo_children():
        widget.destroy()

    app.current_img_rotation = 0
    app.current_img = None
    app.current_img_path = img_path

    if not getattr(app, 'image_frame', None):
        app.image_frame = ttk.Frame(app.preview_frame)
        app.image_frame.pack(fill="both", expand=True)
        app.preview_lbl = ttk.Label(app.image_frame)
        app.preview_lbl.pack(anchor="center", pady=10)
        app.image_controls = ttk.Frame(app.image_frame)
        app.image_controls.pack(fill="x", pady=5)
        ttk.Button(app.image_controls, text="Rotate Left",
                   command=lambda: rotate_image(app, -90)).pack(side="left", padx=5)
        ttk.Button(app.image_controls, text="Rotate Right",
                   command=lambda: rotate_image(app, 90)).pack(side="left", padx=5)
        ttk.Button(app.image_controls, text="Save Rotation",
                   command=lambda: save_rotated_image(app)).pack(side="left", padx=5)
    else:
        app.image_frame.pack(fill="both", expand=True)
        app.preview_lbl.pack(anchor="center", pady=10)
        app.image_controls.pack(fill="x", pady=5)

    if img_path.is_file() and img_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif"}:
        try:
            app.current_img = Image.open(img_path)
            display_image(app)
        except Exception as e:
            print(f"PIL error: {e}")
            app.preview_lbl.configure(image=app.default_img)
    else:
        app.preview_lbl.configure(image=app.default_img)


def display_image(app) -> None:
    if not getattr(app, 'current_img', None):
        return
    try:
        rotated_img = app.current_img.rotate(app.current_img_rotation, expand=True)
        rotated_img.thumbnail(IMAGE_MAX, Image.LANCZOS)
        app.tk_img = ImageTk.PhotoImage(rotated_img)
        app.preview_lbl.configure(image=app.tk_img)
    except Exception as e:
        print(f"Error displaying image: {e}")
        if getattr(app, 'default_img', None):
            app.preview_lbl.configure(image=app.default_img)


def rotate_image(app, angle: int) -> None:
    if not getattr(app, 'current_img', None):
        return
    app.current_img_rotation = (app.current_img_rotation + angle) % 360
    display_image(app)


def save_rotated_image(app) -> None:
    if not getattr(app, 'current_img', None) or not getattr(app, 'current_img_path', None):
        messagebox.showerror("Error", "No image to save")
        return
    if app.current_img_rotation == 0:
        messagebox.showinfo("Info", "No rotation to save")
        return
    try:
        backup_path = str(app.current_img_path) + ".backup"
        if not os.path.exists(backup_path):
            import shutil
            shutil.copy2(app.current_img_path, backup_path)
        metadata = None
        try:
            if app.current_img_path.suffix.lower() in {".jpg", ".jpeg"}:
                exif = app.current_img.info.get('exif')
                metadata = {'exif': exif} if exif else None
            for key, value in app.current_img.info.items():
                if key not in {'exif'}:
                    if metadata is None:
                        metadata = {}
                    metadata[key] = value
        except Exception as e:
            print(f"Error extracting metadata: {e}")
        rotated_img = app.current_img.rotate(app.current_img_rotation, expand=True)
        if metadata:
            rotated_img.save(app.current_img_path, **metadata)
        else:
            rotated_img.save(app.current_img_path)
        rotated_img.close()
        app.current_img.close()
        app.current_img_rotation = 0
        try:
            app.after(100)
            app.current_img = Image.open(app.current_img_path)
            display_image(app)
            messagebox.showinfo("Success", f"Image saved with rotation applied.\nBackup created at {backup_path}")
        except Exception as e:
            print(f"Error reloading image after save: {e}")
            messagebox.showwarning("Warning", f"Image was saved, but there was an error reloading it: {e}")
            app.load_record(app.current_file)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save rotated image: {e}")
        print(f"Error saving rotated image: {e}")
        try:
            app.load_record(app.current_file)
        except Exception:
            pass
