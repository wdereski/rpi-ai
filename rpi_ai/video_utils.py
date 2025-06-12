from __future__ import annotations
import os
import subprocess
import shutil
import tempfile
import threading
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

from .utils import VIDEO_MAX, VIDEO_EXTENSIONS, open_with_default_app

try:
    import cv2
    has_cv2 = True
except Exception:
    has_cv2 = False

try:
    from tkvideoplayer import TkVideoPlayer
    has_tkvideoplayer = True
except Exception:
    has_tkvideoplayer = False

try:
    import vlc
    has_vlc = True
except Exception:
    has_vlc = False


def setup_video_player(app, video_path: Path) -> None:
    app.stop_video()
    app.preview_lbl.pack_forget()
    if getattr(app, 'video_player', None):
        app.video_player.destroy()
        app.video_player = None
    if getattr(app, 'video_frame', None):
        app.video_frame.destroy()
        app.video_frame = None

    app.video_controls.pack_forget()
    for widget in app.video_controls.winfo_children():
        widget.destroy()

    if not video_path.exists():
        print(f"Video file not found: {video_path}")
        app.preview_lbl.configure(image=app.default_img)
        app.preview_lbl.pack(anchor="center")
        return

    app.current_video_path = video_path

    if has_tkvideoplayer:
        try:
            app.video_frame = ttk.Frame(app.preview_frame, width=VIDEO_MAX[0], height=VIDEO_MAX[1])
            app.video_frame.pack(anchor="center")
            app.video_player = TkVideoPlayer(app.video_frame, scaled=True)
            app.video_player.load(str(video_path))
            app.video_player.pack(expand=True, fill="both")
            app.video_controls = ttk.Frame(app.preview_frame)
            app.video_controls.pack(fill="x", pady=5)
            ttk.Button(app.video_controls, text="Play", command=lambda: play_video(app)).pack(side="left", padx=5)
            ttk.Button(app.video_controls, text="Pause", command=lambda: pause_video(app)).pack(side="left", padx=5)
            ttk.Button(app.video_controls, text="Stop", command=lambda: stop_video(app)).pack(side="left", padx=5)
            ttk.Button(app.video_controls, text="Launch Video Player",
                       command=lambda: launch_external_player(app, video_path)).pack(side="right", padx=5)
            print(f"Loaded video with TkVideoPlayer: {video_path.name}")
            return
        except Exception as e:
            print(f"TkVideoPlayer failed: {e}")

    if has_cv2:
        try:
            app.video_frame = ttk.Frame(app.preview_frame, width=VIDEO_MAX[0], height=VIDEO_MAX[1])
            app.video_frame.pack(anchor="center")
            app.video_canvas = tk.Canvas(app.video_frame, width=VIDEO_MAX[0], height=VIDEO_MAX[1], bg="black")
            app.video_canvas.pack()
            display_video_thumbnail(app, video_path)
            setup_video_audio(app, video_path)
            app.video_controls = ttk.Frame(app.preview_frame)
            app.video_controls.pack(fill="x", pady=5)
            ttk.Button(app.video_controls, text="Play", command=lambda: play_video(app)).pack(side="left", padx=5)
            ttk.Button(app.video_controls, text="Stop", command=lambda: stop_video(app)).pack(side="left", padx=5)
            tk.Label(app.video_controls, text="Vol:").pack(side="left", padx=(10,2))
            app.volume_scale = tk.Scale(app.video_controls, from_=0, to=100, orient='horizontal',
                                        command=lambda v: set_volume(app, v), length=100)
            app.volume_scale.set(80)
            app.volume_scale.pack(side="left", padx=2)
            ttk.Button(app.video_controls, text="Launch Video Player",
                       command=lambda: launch_external_player(app, video_path)).pack(side="right", padx=5)
            print(f"Loaded video with OpenCV + VLC: {video_path.name}")
            return
        except Exception as e:
            print(f"OpenCV + VLC setup failed: {e}")

    setup_system_player(app, video_path)


def display_video_thumbnail(app, video_path: Path) -> None:
    if not has_cv2 or not getattr(app, 'video_canvas', None):
        return
    try:
        cap = cv2.VideoCapture(str(video_path))
        ret, frame = cap.read()
        cap.release()
        if ret:
            if app.video_rotation != 0:
                (h, w) = frame.shape[:2]
                center = (w / 2, h / 2)
                M = cv2.getRotationMatrix2D(center, -app.video_rotation, 1.0)
                new_dim = (w,h) if app.video_rotation == 180 else (h,w)
                frame = cv2.warpAffine(frame, M, new_dim)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            img.thumbnail(VIDEO_MAX, Image.LANCZOS)
            photo = ImageTk.PhotoImage(image=img)
            app.video_canvas.delete("all")
            app.video_canvas.create_image(VIDEO_MAX[0]//2, VIDEO_MAX[1]//2, image=photo, anchor='center')
            app.video_canvas.image = photo
    except Exception as e:
        print(f"Error creating video thumbnail: {e}")


def setup_video_audio(app, video_path: Path) -> None:
    if has_vlc and getattr(app, 'vlc_instance', None):
        try:
            app.vlc_media = app.vlc_instance.media_new(str(video_path))
            app.vlc_player = app.vlc_instance.media_player_new()
            app.vlc_player.set_media(app.vlc_media)
            if sys.platform.startswith("linux"):
                app.vlc_player.set_xwindow(0)
            elif sys.platform.startswith("win32"):
                app.vlc_player.set_hwnd(0)
        except Exception as e:
            print(f"VLC audio setup failed: {e}")


def launch_external_player(app, video_path: Path) -> None:
    try:
        if getattr(app, 'current_video_process', None):
            try:
                app.current_video_process.terminate()
                app.current_video_process.wait(timeout=2)
            except Exception:
                try:
                    app.current_video_process.kill()
                except Exception:
                    pass
        app.current_video_process = open_with_default_app(str(video_path), app)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch video player: {e}")


def setup_system_player(app, video_path: Path) -> None:
    app.video_frame = ttk.Frame(app.preview_frame)
    app.video_frame.pack(anchor="center", fill="both", expand=True)
    app.video_canvas = tk.Canvas(app.video_frame, width=VIDEO_MAX[0], height=VIDEO_MAX[1], bg="black")
    app.video_canvas.pack()
    display_video_thumbnail(app, video_path)
    app.video_controls = ttk.Frame(app.preview_frame)
    app.video_controls.pack(fill="x", pady=5)
    ttk.Label(app.video_controls, text="Embedded player not available.").pack(side="left", padx=5)
    ttk.Button(app.video_controls, text="Open in Default Player",
               command=lambda: launch_external_player(app, video_path)).pack(side="right", padx=5)


def play_video(app) -> None:
    if not getattr(app, 'current_video_path', None):
        return
    if has_tkvideoplayer and getattr(app, 'video_player', None):
        app.video_player.play()
        app.video_playing = True
        return
    if getattr(app, 'video_canvas', None):
        app.video_playing = True
        if getattr(app, 'vlc_player', None):
            app.vlc_player.play()
        play_video_cv2(app)


def pause_video(app) -> None:
    if getattr(app, 'vlc_player', None):
        app.vlc_player.pause()
        app.video_playing = False
        return
    if has_tkvideoplayer and getattr(app, 'video_player', None):
        app.video_player.pause()
        app.video_playing = False
        return
    if app.video_playing:
        app.video_playing = False


def stop_video(app) -> None:
    app.video_playing = False
    if getattr(app, 'vlc_player', None):
        try:
            app.vlc_player.stop()
        except Exception as e:
            print(f"VLC stop error: {e}")
    if has_tkvideoplayer and getattr(app, 'video_player', None):
        try:
            app.video_player.stop()
        except Exception as e:
            print(f"TkVideoPlayer stop error: {e}")
    if getattr(app, 'cap', None):
        try:
            app.cap.release()
            app.cap = None
        except Exception as e:
            print(f"OpenCV cap release error: {e}")


def set_volume(app, value):
    volume = int(float(value))
    if getattr(app, 'vlc_player', None):
        app.vlc_player.audio_set_volume(volume)
    if has_tkvideoplayer and getattr(app, 'video_player', None):
        try:
            app.video_player.set_volume(volume / 100.0)
        except Exception:
            pass


def play_video_cv2(app) -> None:
    if not has_cv2 or not getattr(app, 'current_video_path', None) or not app.video_playing:
        return
    if getattr(app, 'cap', None) and app.cap.isOpened():
        app.cap.release()
    app.cap = cv2.VideoCapture(str(app.current_video_path))

    def update_frame():
        if not app.video_playing or not getattr(app, 'cap', None) or not app.cap.isOpened():
            if getattr(app, 'cap', None):
                app.cap.release()
            return
        ret, frame = app.cap.read()
        if ret:
            if app.video_rotation != 0:
                (h, w) = frame.shape[:2]
                center = (w / 2, h / 2)
                M = cv2.getRotationMatrix2D(center, -app.video_rotation, 1.0)
                new_dim = (w,h) if app.video_rotation == 180 else (h,w)
                frame = cv2.warpAffine(frame, M, new_dim)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            img.thumbnail(VIDEO_MAX, Image.LANCZOS)
            photo = ImageTk.PhotoImage(image=img)
            if getattr(app, 'video_canvas', None) and app.video_canvas.winfo_exists():
                app.video_canvas.delete("all")
                app.video_canvas.create_image(VIDEO_MAX[0]//2, VIDEO_MAX[1]//2, image=photo)
                app.video_canvas.image = photo
                app.after(30, update_frame)
        else:
            stop_video(app)
            app.after(100, lambda: display_video_thumbnail(app, app.current_video_path))
    update_frame()


def rotate_video(app, angle: int) -> None:
    if not (app.current_file and app.current_file.lower().endswith(tuple(VIDEO_EXTENSIONS))):
        return
    app.video_rotation = (app.video_rotation + angle) % 360
    if app.video_playing:
        play_video_cv2(app)
    elif has_cv2 and app.current_video_path:
        display_video_thumbnail(app, app.current_video_path)


def save_rotated_video(app) -> None:
    if app.video_rotation == 0:
        messagebox.showinfo("Rotate", "No rotation to save.")
        return
    if shutil.which("ffmpeg") is None:
        messagebox.showerror("Rotate", "FFmpeg not found on your system's PATH. Please install it to rotate videos.")
        return
    src = app.current_video_path
    if not src or not src.exists():
        messagebox.showerror("Rotate", f"Source file not found: {src}")
        return
    transpose_map = {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}
    rotate_filter = transpose_map.get(app.video_rotation)
    if not rotate_filter:
        messagebox.showerror("Rotate", f"Unsupported rotation angle: {app.video_rotation}°")
        return
    with tempfile.NamedTemporaryFile(dir=src.parent, suffix=src.suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vf", rotate_filter,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "copy",
        str(tmp_path),
    ]
    progress_window = tk.Toplevel(app)
    progress_window.title("Rotating Video")
    progress_window.geometry("350x120")
    progress_window.transient(app)
    progress_window.grab_set()
    progress_window.resizable(False, False)
    label = tk.Label(progress_window, text="Processing video, please wait...")
    label.pack(pady=10)
    progress = ttk.Progressbar(progress_window, mode="indeterminate", length=300)
    progress.pack(pady=10)
    progress.start(10)

    def run_ffmpeg_thread():
        try:
            process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
            _, stderr = process.communicate()
            if process.returncode == 0:
                shutil.move(str(tmp_path), src)
                app.video_rotation = 0
                app.after(0, progress_window.destroy)
                app.after(0, lambda: messagebox.showinfo("Success", "Video rotated and saved successfully."))
                app.after(10, lambda: app.load_record(app.current_file))
            else:
                if tmp_path.exists():
                    tmp_path.unlink()
                app.after(0, progress_window.destroy)
                app.after(0, lambda: messagebox.showerror("FFmpeg Error", f"Failed to rotate video.\n\nError:\n{stderr[-500:]}"))
        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            app.after(0, progress_window.destroy)
            app.after(0, lambda: messagebox.showerror("Error", f"An unexpected error occurred: {e}"))
    threading.Thread(target=run_ffmpeg_thread, daemon=True).start()


def open_in_vlc(app, video_path: Path) -> None:
    stop_video(app)
    vlc_path = None
    if sys.platform == "win32":
        for path in [
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'VideoLAN', 'VLC', 'vlc.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'VideoLAN', 'VLC', 'vlc.exe')
        ]:
            if os.path.exists(path):
                vlc_path = path
                break
    elif sys.platform == "darwin":
        vlc_path = "/Applications/VLC.app/Contents/MacOS/VLC"
        if not os.path.exists(vlc_path):
            brew_vlc = "/usr/local/bin/vlc"
            if os.path.exists(brew_vlc):
                vlc_path = brew_vlc
    else:
        vlc_path = "/usr/bin/vlc"
        if not os.path.exists(vlc_path):
            vlc_path = "/usr/local/bin/vlc"
    if vlc_path and os.path.exists(vlc_path):
        try:
            subprocess.Popen([vlc_path, str(video_path)])
        except Exception as e:
            messagebox.showerror("VLC Error", f"Failed to open VLC: {e}")
    else:
        messagebox.showinfo("VLC Not Found", "VLC player not found. Please install VLC or use the system default player.")
        launch_external_player(app, video_path)


def open_in_default_player(video_path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(video_path)
    elif sys.platform == "darwin":
        subprocess.call(["open", video_path])
    else:
        subprocess.call(["xdg-open", video_path])
