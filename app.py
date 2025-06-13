"""Tkinter-based Media Metadata Editor GUI."""
from __future__ import annotations

import json
import os
import sys
import textwrap
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import tempfile
import threading
import time
import shlex
from datetime import datetime

# Optional video player libraries
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from tkvideoplayer import TkVideoPlayer
    HAS_TKVIDEOPLAYER = True
except ImportError:
    HAS_TKVIDEOPLAYER = False

try:
    import pyglet
    HAS_PYGLET = True
except ImportError:
    HAS_PYGLET = False

try:
    import pygame
    pygame.mixer.init()
    HAS_PYGAME = True
except (ImportError, pygame.error):
    HAS_PYGAME = False

try:
    import vlc
    HAS_VLC = True
except ImportError:
    HAS_VLC = False

from .constants import PHOTOS_DIR, IMAGE_MAX, VIDEO_MAX, VIDEO_EXTENSIONS
from .database import MetadataDB
from .utils import open_with_default_app
class MetadataEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Media Metadata Editor")
        self.geometry("1200x750")
        self.minsize(1000, 650)
        
        # Add full-screen support attributes
        self.fullscreen_window = None
        self.is_fullscreen = False
        self.fullscreen_video_player = None
        self.fullscreen_canvas = None

        self.current_video_process = None  # manage video windows
        
        # Set theme colors
        self.bg_color = "#f0f4f8"
        self.accent_color = "#4a90e2"
        self.text_color = "#333333"
        
        self.configure(bg=self.bg_color)
        self.style = ttk.Style()
        self.style.theme_use('alt')  # Use alternate theme as base
        
        # Configure styles
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.text_color)
        self.style.configure("TButton", background=self.accent_color, foreground="white")
        self.style.configure("Treeview", background="white", foreground=self.text_color, rowheight=25)
        self.style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))
        
        # Set up copy-paste bindings
        self.setup_copy_paste()
        
        # Create menu
        self.create_menu()
        
        # Initialize database
        self.db = MetadataDB()
        self.current_file = None
        
        # Create default image for preview
        self.default_img = None
        
        # Current media properties
        self.current_img = None
        self.current_img_rotation = 0
        
        # Video player references
        self.video_player = None
        self.video_frame = None
        self.current_video_path = None
        self.video_playing = False
        self.video_rotation = 0
        
        # Audio player references
        self.vlc_instance = None
        self.vlc_player = None
        self.vlc_media = None
        self.pygame_player = None
        
        # Initialize VLC if available
        if has_vlc:
            try:
                self.vlc_instance = vlc.Instance('--no-xlib')
            except Exception as e:
                print(f"VLC initialization error: {e}")
                self.vlc_instance = None
        
        # Build UI
        self._build_widgets()
        self._populate_tree()
        
    def setup_copy_paste(self):
        """Set up copy-paste bindings for entry and text widgets."""
        # Define key bindings for copy, cut, paste
        self.copy_paste_bindings = {
            # Windows/Linux bindings
            '<Control-c>': self.copy_text,
            '<Control-x>': self.cut_text,
            '<Control-v>': self.paste_text,
            # Mac bindings
            '<Command-c>': self.copy_text,
            '<Command-x>': self.cut_text,
            '<Command-v>': self.paste_text,
        }
    




    # ────────────────────────────────────────────────────────────────────
    #  CLIPBOARD + MOUSE COPY/PASTE  (replace the old helper)
    # ────────────────────────────────────────────────────────────────────
    def apply_copy_paste_bindings(self, widget: tk.Widget) -> None:
        """
        Attach keyboard shortcuts **and** a right-click / middle-click context
        menu that offers Cut / Copy / Paste.  Also routes all paste actions
        through self.paste_text so text is inserted only once.
        """

        # Avoid binding the same widget more than once
        if getattr(widget, "_context_menu_installed", False):
            return
        widget._context_menu_installed = True

        # -------- context (right-click) menu ----------
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Cut",   command=lambda w=widget: w.event_generate("<<Cut>>"))
        menu.add_command(label="Copy",  command=lambda w=widget: w.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda w=widget: w.event_generate("<<Paste>>"))

        # Button-3 = right click on most systems (mac trackpads map it too)
        widget.bind("<Button-3>", lambda e, m=menu: m.tk_popup(e.x_root, e.y_root), add="+")
        # Button-2 = middle click (classic X-11 quick-paste)
        widget.bind("<Button-2>", lambda e: widget.event_generate("<<Paste>>"),      add="+")

        # -------- keyboard shortcuts ----------
        widget.bind("<Control-c>", lambda e: widget.event_generate("<<Copy>>"),  add="+")
        widget.bind("<Control-x>", lambda e: widget.event_generate("<<Cut>>"),   add="+")
        widget.bind("<Control-v>", lambda e: widget.event_generate("<<Paste>>"), add="+")

        # Route ALL paste events through your existing handler ─ it already
        # returns "break", preventing the default Tk paste (so no duplicates).
        widget.bind("<<Paste>>", self.paste_text, add="+")
     
        

        
    
    def copy_text(self, event):
        """Copy selected text to clipboard."""
        try:
            widget = event.widget
            if isinstance(widget, tk.Entry) or isinstance(widget, ttk.Entry):
                if widget.selection_present():
                    selected_text = widget.selection_get()
                    self.clipboard_clear()
                    self.clipboard_append(selected_text)
            elif isinstance(widget, tk.Text):
                if widget.tag_ranges("sel"):
                    selected_text = widget.get("sel.first", "sel.last")
                    self.clipboard_clear()
                    self.clipboard_append(selected_text)
        except Exception as e:
            print(f"Copy error: {e}")
    
    def cut_text(self, event):
        """Cut selected text to clipboard."""
        try:
            widget = event.widget
            if isinstance(widget, tk.Entry) or isinstance(widget, ttk.Entry):
                if widget.selection_present():
                    selected_text = widget.selection_get()
                    self.clipboard_clear()
                    self.clipboard_append(selected_text)
                    widget.delete("sel.first", "sel.last")
            elif isinstance(widget, tk.Text):
                if widget.tag_ranges("sel"):
                    selected_text = widget.get("sel.first", "sel.last")
                    self.clipboard_clear()
                    self.clipboard_append(selected_text)
                    widget.delete("sel.first", "sel.last")
        except Exception as e:
            print(f"Cut error: {e}")
    
    def paste_text(self, event):
        """Paste clipboard text into widget."""
        try:
            widget = event.widget
            text_to_paste = self.clipboard_get()
            
            if isinstance(widget, tk.Entry) or isinstance(widget, ttk.Entry):
                if widget.selection_present():
                    widget.delete("sel.first", "sel.last")
                widget.insert("insert", text_to_paste)
            elif isinstance(widget, tk.Text):
                if widget.tag_ranges("sel"):
                    widget.delete("sel.first", "sel.last")
                widget.insert("insert", text_to_paste)
            return "break"
        except Exception as e:
            print(f"Paste error: {e}")
            return "break"

            # ───────────────────────────────────────────────────────────
    #  CONTEXT-MENU / MOUSE PASTE  (new)
    # ───────────────────────────────────────────────────────────
    def _attach_context_menu(self, widget: tk.Widget):
        """Add right-click menu + middle-click paste to a widget."""
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Cut",
                         command=lambda w=widget: w.event_generate("<<Cut>>"))
        menu.add_command(label="Copy",
                         command=lambda w=widget: w.event_generate("<<Copy>>"))
        menu.add_command(label="Paste",
                         command=lambda w=widget: w.event_generate("<<Paste>>"))

        # right-click (Windows / macOS) = <Button-2> on mac trackpads, <Button-3> elsewhere
        widget.bind("<Button-3>", lambda e, m=menu: m.tk_popup(e.x_root, e.y_root))
        # middle-click paste (common on Linux / X11)
        widget.bind("<Button-2>", lambda e: widget.event_generate("<<Paste>>"))
        # make sure our custom paste suppresses double-insert
        widget.bind("<<Paste>>", self.paste_text, add="+")
        
        
    def create_menu(self):
        menubar = tk.Menu(self)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Add New Media", command=self.on_add_media)
        file_menu.add_separator()
        file_menu.add_command(label="Import Master Data", command=self.on_import_master)
        file_menu.add_command(label="Merge Updates", command=self.on_merge_updates)
        file_menu.add_separator()
        file_menu.add_command(label="Export to JSONL", command=self.on_export_jsonl)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Search", command=lambda: self.search_entry.focus())
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # Image menu
        image_menu = tk.Menu(menubar, tearoff=0)
        image_menu.add_command(label="Rotate Left", command=lambda: self.rotate_image(-90))
        image_menu.add_command(label="Rotate Right", command=lambda: self.rotate_image(90))
        image_menu.add_command(label="Save Rotation", command=self.save_rotated_image)
        menubar.add_cascade(label="Image", menu=image_menu)

        # --- Video menu -----------------------------------------------------------
        video_menu = tk.Menu(menubar, tearoff=0)
        video_menu.add_command(label="Rotate Left", command=lambda: self.rotate_video(-90))
        video_menu.add_command(label="Rotate Right", command=lambda: self.rotate_video(90))
        video_menu.add_separator()
        video_menu.add_command(label="Save Rotation", command=self.save_rotated_video)
        menubar.add_cascade(label="Video", menu=video_menu)

        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo(
            "About", "Media Metadata Editor\nVersion 1.0\n\nFor editing and managing media metadata"
        ))
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.config(menu=menubar)

    def on_add_media(self):
        """Callback to add a new media file."""
        file_paths = filedialog.askopenfilenames(
            title="Select Media Files to Add",
            filetypes=[("Media Files", "*.jpg *.jpeg *.png *.gif *.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if not file_paths:
            return

        added_count = 0
        for file_path_str in file_paths:
            file_path = Path(file_path_str)
            new_file_name = self.db.add_new_media(file_path)
            if new_file_name:
                added_count += 1
        
        if added_count > 0:
            self._populate_tree()
            messagebox.showinfo("Success", f"Added {added_count} new media file(s).")
    
    def save_rotated_image(self):
        """Save the rotated image to disk, preserving metadata if possible."""
        if not self.current_img or not hasattr(self, 'current_img_path') or not self.current_img_path:
            messagebox.showerror("Error", "No image to save")
            return
            
        if self.current_img_rotation == 0:
            messagebox.showinfo("Info", "No rotation to save")
            return
            
        try:
            # Create a backup of the original file
            backup_path = str(self.current_img_path) + ".backup"
            if not os.path.exists(backup_path):
                import shutil
                shutil.copy2(self.current_img_path, backup_path)
                
            # Extract metadata if possible (EXIF, etc.)
            metadata = None
            try:
                # For JPEG images, try to extract EXIF data
                if self.current_img_path.suffix.lower() in {".jpg", ".jpeg"}:
                    exif = self.current_img.info.get('exif')
                    metadata = {'exif': exif} if exif else None
                    
                # For other metadata types (e.g., PNG metadata, etc.)
                for key, value in self.current_img.info.items():
                    if key not in {'exif'}:  # Already handled exif
                        if metadata is None:
                            metadata = {}
                        metadata[key] = value
            except Exception as e:
                print(f"Error extracting metadata: {e}")
                
            # Apply rotation and save
            rotated_img = self.current_img.rotate(self.current_img_rotation, expand=True)
            
            # Save the rotated image, preserving metadata if available
            if metadata:
                rotated_img.save(self.current_img_path, **metadata)
            else:
                rotated_img.save(self.current_img_path)
            
            # Close the image to ensure file handles are released
            rotated_img.close()
            if hasattr(self, 'current_img') and self.current_img:
                self.current_img.close()
                
            # Reload the image from disk to ensure we're displaying the saved version
            self.current_img_rotation = 0  # Reset rotation angle after saving
            
            try:
                # Wait a moment for the file to be fully written
                self.after(100)
                # Reload the image from disk
                self.current_img = Image.open(self.current_img_path)
                self.display_image()
                
                messagebox.showinfo("Success", 
                                   f"Image saved with rotation applied.\nBackup created at {backup_path}")
            except Exception as e:
                print(f"Error reloading image after save: {e}")
                messagebox.showwarning("Warning", 
                                      f"Image was saved, but there was an error reloading it: {e}")
                # Force reload of current record
                self.load_record(self.current_file)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save rotated image: {e}")
            print(f"Error saving rotated image: {e}")
            # Attempt to reload the original file
            try:
                self.load_record(self.current_file)
            except Exception:
                pass


    # ───────────────────────────────────────────────────────────
    #  VIDEO ROTATION - Corrected
    # ───────────────────────────────────────────────────────────

    def rotate_video(self, angle: int) -> None:
        """Queue a 90/180/270° rotation for the current video preview."""
        if not (self.current_file and self.current_file.lower().endswith(tuple(VIDEO_EXTENSIONS))):
            return  # not a video → ignore

        # keep rotation in 0-359 range
        self.video_rotation = (self.video_rotation + angle) % 360
        # Refresh the video preview to show the intended rotation
        if self.video_playing:
            self.play_video_cv2() # Re-render with new rotation
        else:
             # Just show a rotated thumbnail if possible
            if has_cv2 and self.current_video_path:
                self.display_video_thumbnail(self.current_video_path)


    def save_rotated_video(self) -> None:
        """Rotate video file using ffmpeg and replace the original."""
        if self.video_rotation == 0:
            messagebox.showinfo("Rotate", "No rotation to save.")
            return
        if shutil.which("ffmpeg") is None:
            messagebox.showerror("Rotate", "FFmpeg not found on your system's PATH. Please install it to rotate videos.")
            return

        src = self.current_video_path
        if not src or not src.exists():
            messagebox.showerror("Rotate", f"Source file not found: {src}")
            return

        transpose_map = {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}
        rotate_filter = transpose_map.get(self.video_rotation)
        if not rotate_filter:
            messagebox.showerror("Rotate", f"Unsupported rotation angle: {self.video_rotation}°")
            return

        # Create a temporary file for the output
        with tempfile.NamedTemporaryFile(dir=src.parent, suffix=src.suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-vf", rotate_filter,
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", # Good balance of quality and size
            "-c:a", "copy",  # Copy audio stream without re-encoding
            str(tmp_path),
        ]

        # --- Progress Dialog ---
        progress_window = tk.Toplevel(self)
        progress_window.title("Rotating Video")
        progress_window.geometry("350x120")
        progress_window.transient(self)
        progress_window.grab_set()
        progress_window.resizable(False, False)
        
        label = tk.Label(progress_window, text="Processing video, please wait...")
        label.pack(pady=10)
        progress = ttk.Progressbar(progress_window, mode="indeterminate", length=300)
        progress.pack(pady=10)
        progress.start(10)

        def run_ffmpeg_thread():
            try:
                # Using PIPE for stderr to capture potential errors
                process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
                _, stderr = process.communicate() # Wait for completion

                if process.returncode == 0:
                    # Success: replace original file
                    shutil.move(str(tmp_path), src)
                    self.video_rotation = 0  # Reset rotation
                    
                    self.after(0, progress_window.destroy)
                    self.after(0, lambda: messagebox.showinfo("Success", "Video rotated and saved successfully."))
                    # Reload the video in the player
                    self.after(10, lambda: self.load_record(self.current_file))
                else:
                    # Failure
                    if tmp_path.exists():
                        tmp_path.unlink()
                    self.after(0, progress_window.destroy)
                    self.after(0, lambda: messagebox.showerror("FFmpeg Error", f"Failed to rotate video.\n\nError:\n{stderr[-500:]}"))
            
            except Exception as e:
                if tmp_path.exists():
                    tmp_path.unlink()
                self.after(0, progress_window.destroy)
                self.after(0, lambda: messagebox.showerror("Error", f"An unexpected error occurred: {e}"))

        # Run ffmpeg in a separate thread to avoid freezing the GUI
        threading.Thread(target=run_ffmpeg_thread, daemon=True).start()
    
    def reload_current_video(self):
        """Reload the current video after processing."""
        # Save the current position if playing
        was_playing = False
        position = 0
        if hasattr(self, 'video_player') and self.video_player:
            try:
                was_playing = self.video_player.is_playing()
                position = self.video_player.get_position()
            except:
                pass
        
        # Close existing video
        if hasattr(self, 'close_video'):
            self.close_video()
        
        # Reload the same file
        if hasattr(self, 'load_video'):
            self.load_video(self.current_file)
            
            # Restore playback state
            if was_playing and position > 0:
                # Wait a bit to ensure video is loaded
                self.after(500, lambda: self.seek_and_play(position))

    def seek_and_play(self, position):
        """Helper to seek to position and play if needed."""
        if hasattr(self, 'video_player') and self.video_player:
            try:
                self.video_player.set_position(position)
                self.video_player.play()
            except:
                pass
    # ---------------------------------------------------------------------
    #  GUI construction
    # ---------------------------------------------------------------------
    def _build_widgets(self) -> None:
        """Create the main split‑pane UI: file list on the left, editor on the right."""
        # ----- outer paned window ----------------------------------------
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10, pady=10)

        
        # ========== LEFT  — file list =====================================
        left_frame = ttk.Frame(pane)
        pane.add(left_frame, weight=1)           # let the list stretch
        
        # Search bar at top
        search_frame = ttk.Frame(left_frame, padding=(0, 0, 0, 8))
        search_frame.pack(fill="x")
        
        ttk.Label(search_frame, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.search_entry.bind("<Return>", self.on_search)
        self.apply_copy_paste_bindings(self.search_entry)
        
        ttk.Button(search_frame, text="Search", command=lambda: self.on_search(None)).pack(side="right", padx=(5, 0))

        # File list
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill="both", expand=True)
        
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("description", "desc"),
            show="headings",
            selectmode="browse",
            height=25,
        )
        self.tree.heading("description", text="File Name")
        self.tree.heading("desc", text="Description")
        self.tree.column("description", width=250)
        self.tree.column("desc", width=80)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # ========== RIGHT — metadata editor ===============================
        right_frame = ttk.Frame(pane, padding=16)
        pane.add(right_frame, weight=2)          # give enough space for the editor
        
        # ── Preview frame (for both image and video) ───────────────────────
        self.preview_frame = ttk.Frame(right_frame, padding=(0, 0, 0, 10))
        self.preview_frame.pack(fill="x")
        
        # Default preview label for images
        self.preview_lbl = ttk.Label(self.preview_frame)
        self.preview_lbl.pack(anchor="center")
        
        # Generate a placeholder image
        placeholder = tk.PhotoImage(width=1, height=1)
        self.default_img = placeholder
        self.preview_lbl.configure(image=self.default_img)
        
        # Video controls frame (will be populated when needed)
        self.video_controls = ttk.Frame(self.preview_frame)
        
        # Create a horizontal separator
        ttk.Separator(right_frame, orient="horizontal").pack(fill="x", pady=10)

        # ── READ‑ONLY info bar ───────────────────────────────────────────
        info_frame = ttk.LabelFrame(right_frame, text="File Information", padding=10)
        info_frame.pack(fill="x", pady=(0, 10))
        
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill="x")

        # File name
        ttk.Label(info_grid, text="File:", width=12, anchor="e").grid(row=0, column=0, sticky="w", pady=2)
        self.fn_lbl = ttk.Label(info_grid, width=60, anchor="w")
        self.fn_lbl.grid(row=0, column=1, sticky="w", pady=2)

        # ID
        ttk.Label(info_grid, text="ID:", width=12, anchor="e").grid(row=1, column=0, sticky="w", pady=2)
        self.id_lbl = ttk.Label(info_grid, width=60, anchor="w")
        self.id_lbl.grid(row=1, column=1, sticky="w", pady=2)

        # Date taken
        ttk.Label(info_grid, text="Date Taken:", width=12, anchor="e").grid(row=2, column=0, sticky="w", pady=2)
        self.date_lbl = ttk.Label(info_grid, width=60, anchor="w")
        self.date_lbl.grid(row=2, column=1, sticky="w", pady=2)

        # Location coordinates
        ttk.Label(info_grid, text="Coordinates:", width=12, anchor="e").grid(row=3, column=0, sticky="w", pady=2)
        self.loc_lbl = ttk.Label(info_grid, width=60, anchor="w")
        self.loc_lbl.grid(row=3, column=1, sticky="w", pady=2)

        # ── EDITABLE form ────────────────────────────────────────────────
        form_frame = ttk.LabelFrame(right_frame, text="Edit Metadata", padding=10)
        form_frame.pack(fill="both", expand=True)
        
        form = ttk.Frame(form_frame)
        form.pack(fill="both", expand=True)

        # Keywords
        ttk.Label(form, text="Keywords:", width=12, anchor="e").grid(row=0, column=0, sticky="w", pady=5)
        self.kw_var = tk.StringVar()
        self.kw_entry = ttk.Entry(form, textvariable=self.kw_var, width=60)
        self.kw_entry.grid(row=0, column=1, sticky="we", pady=5)
        self.apply_copy_paste_bindings(self.kw_entry)
        ttk.Label(form, text="(comma separated)").grid(row=0, column=2, sticky="w", padx=5, pady=5)

        # Location name
        ttk.Label(form, text="Location name:", width=12, anchor="e").grid(row=1, column=0, sticky="w", pady=5)
        self.loc_var = tk.StringVar()
        self.loc_entry = ttk.Entry(form, textvariable=self.loc_var, width=60)
        self.loc_entry.grid(row=1, column=1, sticky="we", pady=5)
        self.apply_copy_paste_bindings(self.loc_entry)

        # People
        ttk.Label(form, text="People:", width=12, anchor="e").grid(row=2, column=0, sticky="w", pady=5)
        self.people_var = tk.StringVar()
        self.people_entry = ttk.Entry(form, textvariable=self.people_var, width=60)
        self.people_entry.grid(row=2, column=1, sticky="we", pady=5)
        self.apply_copy_paste_bindings(self.people_entry)
        ttk.Label(form, text="(comma separated)").grid(row=2, column=2, sticky="w", padx=5, pady=5)

        # Labels
        ttk.Label(form, text="Labels:", width=12, anchor="e").grid(row=3, column=0, sticky="w", pady=5)
        self.labels_var = tk.StringVar()
        self.labels_entry = ttk.Entry(form, textvariable=self.labels_var, width=60)
        self.labels_entry.grid(row=3, column=1, sticky="we", pady=5)
        self.apply_copy_paste_bindings(self.labels_entry)
        ttk.Label(form, text="(comma separated)").grid(row=3, column=2, sticky="w", padx=5, pady=5)

        # Description
        ttk.Label(form, text="Description:", width=12, anchor="ne").grid(row=4, column=0, sticky="ne", pady=5)
        self.desc_txt = tk.Text(form, width=60, height=4, wrap="word")
        self.desc_txt.grid(row=4, column=1, sticky="we", pady=5)
        self.apply_copy_paste_bindings(self.desc_txt)
        
        # Add a scrollbar for description
        desc_sb = ttk.Scrollbar(form, orient="vertical", command=self.desc_txt.yview)
        self.desc_txt.configure(yscrollcommand=desc_sb.set)
        desc_sb.grid(row=4, column=2, sticky="ns", pady=5)

        form.columnconfigure(1, weight=1)        # let entry column stretch

        # ── action buttons ───────────────────────────────────────────────
        btns = ttk.Frame(right_frame, padding=(0, 10, 0, 0))
        btns.pack(fill="x")
        
        # Navigation buttons
        nav_frame = ttk.Frame(btns)
        nav_frame.pack(side="left")
        ttk.Button(nav_frame, text="Previous", command=self.on_previous).pack(side="left", padx=(0, 5))
        ttk.Button(nav_frame, text="Next", command=self.on_next).pack(side="left")
        
        # Save button with accent style
        self.style.configure("Accent.TButton", background=self.accent_color)
        ttk.Button(btns, text="Save Changes", command=self.on_save, style="Accent.TButton").pack(side="right")

                # NEW ─ Delete button
        ttk.Button(btns, text="Delete",
                   command=self.delete_selected_image).pack(side="right", padx=(0, 8))

        
    # --------------------------------------------------------------------
    # Populate / refresh
    # --------------------------------------------------------------------
    def _populate_tree(self, rows=None):
        """Clear and refill the tree. If rows is None, show all; if it’s an empty list, show nothing."""
        # 1) delete existing items
        for child in self.tree.get_children():
            self.tree.delete(child)

        # 2) load all if no rows passed
        if rows is None:
            rows = self.db.fetch_all()

        # 3) insert each row—use direct indexing, not .get()
        for r in rows:
            desc = r["description"] or ""
            self.tree.insert(
                "",
                "end",
                iid=r["file_name"],
                values=(r["file_name"], desc)
            )
            
    # --------------------------------------------------------------------
    # Menu callbacks
    # --------------------------------------------------------------------
    def on_import_master(self):
        path = filedialog.askopenfilename(
            title="Choose master data file (.txt | .jsonl)",
            filetypes=[("JSON Lines", "*.txt *.jsonl"), ("All files", "*")],
        )
        if not path:
            return
        n = self.db.import_master(Path(path))
        self._populate_tree()
        messagebox.showinfo("Import complete", f"{n} records imported.")

    def on_merge_updates(self):
        path = filedialog.askopenfilename(
            title="Choose update file (.jsonl)",
            filetypes=[("JSON Lines", "*.jsonl"), ("All files", "*")],
        )
        if not path:
            return
        n = self.db.merge_updates(Path(path))
        self._populate_tree()
        messagebox.showinfo("Merge complete", f"{n} records updated.")

    def on_export_jsonl(self):
        out_dir = filedialog.askdirectory(title="Export to directory")
        if not out_dir:
            return
        num_files = self.db.export_jsonl(Path(out_dir))
        messagebox.showinfo("Export complete", f"Wrote {num_files} chunk(s).")

    # --------------------------------------------------------------------
    # Tree / search callbacks
    # --------------------------------------------------------------------
    def on_search(self, event):
        q = self.search_var.get().strip()
        rows = self.db.search(q) if q else self.db.fetch_all()
        self._populate_tree(rows)

    def on_tree_select(self, event):
        item = self.tree.selection()
        if not item:
            return
        file_name = item[0]
        self.load_record(file_name)

    # --------------------------------------------------------------------
    # Record handling
    # --------------------------------------------------------------------
    def load_record(self, file_name: str):
        # First completely cleanup any media players
        self.stop_video()
        if self.video_player:
            self.video_player.destroy()
            self.video_player = None
        if self.video_frame:
            self.video_frame.destroy()
            self.video_frame = None
        
        # Clean up any image resources
        if hasattr(self, 'current_img') and self.current_img:
            try:
                self.current_img.close()
            except Exception:
                pass
            self.current_img = None
        
        # Clear video controls
        self.video_controls.pack_forget()
        for widget in self.video_controls.winfo_children():
            widget.destroy()
        
        # Hide image preview if it exists
        if hasattr(self, 'image_frame') and self.image_frame:
            self.image_frame.pack_forget()
        
        row = self.db.fetch_one(file_name)
        if not row:
            return
        self.current_file = row["file_name"]

        # Display read-only information
        self.fn_lbl.config(text=row["file_name"])
        self.id_lbl.config(text=row["id"])
        self.date_lbl.config(text=row["date_original"] or "Unknown")
        
        # Location coordinates
        if row["latitude"] is not None and row["longitude"] is not None:
            self.loc_lbl.config(text=f"{row['latitude']}, {row['longitude']}")
        else:
            self.loc_lbl.config(text="Unknown")

        # Check file type for preview
        file_path = PHOTOS_DIR / row["file_name"]
        file_ext = file_path.suffix.lower()
        
        # Handle different media types
        if file_ext in VIDEO_EXTENSIONS:
            self.video_rotation = 0 # Reset rotation for new video
            self.setup_video_player(file_path)
        else:
            self.current_img_rotation = 0 # Reset rotation for new image
            self.setup_image_preview(file_path)

        # editable fields
        self.kw_var.set(", ".join(self._safe_json_list(row["keywords"])))
        self.loc_var.set(self._safe_json_str(row["location_name"]))
        self.people_var.set(", ".join(self._safe_json_list(row["people"])))
        self.labels_var.set(", ".join(self._safe_json_list(row["labels"])))
        
        self.desc_txt.delete("1.0", "end")
        self.desc_txt.insert("end", row["description"] or "")
        
    def setup_image_preview(self, img_path: Path):
        """Set up the image preview."""
        # Clean up video player components
        self.stop_video()
        if self.video_player:
            self.video_player.destroy()
            self.video_player = None
        if self.video_frame:
            self.video_frame.destroy()
            self.video_frame = None
        
        # Clear video controls
        self.video_controls.pack_forget()
        for widget in self.video_controls.winfo_children():
            widget.destroy()
        
        # Reset rotation
        self.current_img_rotation = 0
        self.current_img = None
        self.current_img_path = img_path
        
        # Create image preview frame if it doesn't exist
        if not hasattr(self, 'image_frame') or not self.image_frame:
            self.image_frame = ttk.Frame(self.preview_frame)
            self.image_frame.pack(fill="both", expand=True)
            
            # Image preview label
            self.preview_lbl = ttk.Label(self.image_frame)
            self.preview_lbl.pack(anchor="center", pady=10)
            
            # Image controls
            self.image_controls = ttk.Frame(self.image_frame)
            self.image_controls.pack(fill="x", pady=5)
            
            # Rotation buttons  (replace only the command= parts)
            ttk.Button(self.image_controls, text="Rotate Left",
                      command=lambda: (self.rotate_image(-90))
            ).pack(side="left", padx=5)

            ttk.Button(self.image_controls, text="Rotate Right",
                      command=lambda: (self.rotate_image(90))
            ).pack(side="left", padx=5)

            ttk.Button(self.image_controls, text="Save Rotation",
                      command=lambda: (self.save_rotated_image())
            ).pack(side="left", padx=5)
        else:
            self.image_frame.pack(fill="both", expand=True)
            self.preview_lbl.pack(anchor="center", pady=10)
            self.image_controls.pack(fill="x", pady=5)
        
        # Load and display the image
        if img_path.is_file() and img_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif"}:
            try:
                self.current_img = Image.open(img_path)
                self.display_image()
            except Exception as e:
                print(f"PIL error: {e}")
                self.preview_lbl.configure(image=self.default_img)
        else:
            self.preview_lbl.configure(image=self.default_img)
    
    def display_image(self):
        """Display the current image with rotation applied."""
        if not self.current_img:
            return
            
        try:
            # Apply rotation
            rotated_img = self.current_img.rotate(self.current_img_rotation, expand=True)
            
            # Resize for display
            rotated_img.thumbnail(IMAGE_MAX, Image.LANCZOS)
            
            # Convert to PhotoImage
            self.tk_img = ImageTk.PhotoImage(rotated_img)
            self.preview_lbl.configure(image=self.tk_img)
        except Exception as e:
            print(f"Error displaying image: {e}")
            if hasattr(self, 'default_img') and self.default_img:
                self.preview_lbl.configure(image=self.default_img)
        
    def rotate_image(self, angle):
        """Rotate the image by the specified angle."""
        if not self.current_img:
            return
            
        # Update rotation angle
        self.current_img_rotation = (self.current_img_rotation + angle) % 360
        
        # Redisplay the image
        self.display_image()
    
    def setup_video_player(self, video_path: Path):
        """Set up the embedded video player with sound and launch button."""
        # First clean up any existing video or image components
        self.stop_video()
        self.preview_lbl.pack_forget()
        
        if self.video_player:
            self.video_player.destroy()
            self.video_player = None
        
        if self.video_frame:
            self.video_frame.destroy()
            self.video_frame = None
        
        # Clear video controls
        self.video_controls.pack_forget()
        for widget in self.video_controls.winfo_children():
            widget.destroy()
            
        if not video_path.exists():
            print(f"Video file not found: {video_path}")
            self.preview_lbl.configure(image=self.default_img)
            self.preview_lbl.pack(anchor="center")
            return
            
        self.current_video_path = video_path
        
        # Try TkVideoPlayer first (has built-in audio support)
        if has_tkvideoplayer:
            try:
                self.video_frame = ttk.Frame(self.preview_frame, width=VIDEO_MAX[0], height=VIDEO_MAX[1])
                self.video_frame.pack(anchor="center")
                
                self.video_player = TkVideoPlayer(self.video_frame, scaled=True)
                self.video_player.load(str(video_path))
                self.video_player.pack(expand=True, fill="both")
                
                # Video controls
                self.video_controls = ttk.Frame(self.preview_frame)
                self.video_controls.pack(fill="x", pady=5)
                
                ttk.Button(self.video_controls, text="Play", command=self.play_video).pack(side="left", padx=5)
                ttk.Button(self.video_controls, text="Pause", command=self.pause_video).pack(side="left", padx=5)
                ttk.Button(self.video_controls, text="Stop", command=self.stop_video).pack(side="left", padx=5)
                
                # Launch external player button
                ttk.Button(self.video_controls, text="Launch Video Player", 
                          command=lambda: self.launch_external_player(video_path)).pack(side="right", padx=5)
                
                print(f"Loaded video with TkVideoPlayer (with sound): {video_path.name}")
                return
                
            except Exception as e:
                print(f"TkVideoPlayer failed: {e}")
        
        # Fall back to OpenCV + VLC audio combination
        if has_cv2:
            try:
                self.video_frame = ttk.Frame(self.preview_frame, width=VIDEO_MAX[0], height=VIDEO_MAX[1])
                self.video_frame.pack(anchor="center")
                
                # Create a canvas for displaying frames
                self.video_canvas = tk.Canvas(self.video_frame, width=VIDEO_MAX[0], height=VIDEO_MAX[1], bg="black")
                self.video_canvas.pack()
                
                self.display_video_thumbnail(video_path)
                
                # Setup VLC for audio playback
                self.setup_video_audio(video_path)
                
                # Video controls
                self.video_controls = ttk.Frame(self.preview_frame)
                self.video_controls.pack(fill="x", pady=5)
                
                ttk.Button(self.video_controls, text="Play", command=self.play_video).pack(side="left", padx=5)
                ttk.Button(self.video_controls, text="Stop", command=self.stop_video).pack(side="left", padx=5)
                
                # Volume control
                tk.Label(self.video_controls, text="Vol:").pack(side="left", padx=(10,2))
                self.volume_scale = tk.Scale(self.video_controls, from_=0, to=100, orient='horizontal',
                                            command=self.set_volume, length=100)
                self.volume_scale.set(80)
                self.volume_scale.pack(side="left", padx=2)
                
                # Launch external player button
                ttk.Button(self.video_controls, text="Launch Video Player", 
                          command=lambda: self.launch_external_player(video_path)).pack(side="right", padx=5)
                
                print(f"Loaded video with OpenCV + VLC audio: {video_path.name}")
                return
                
            except Exception as e:
                print(f"OpenCV + VLC setup failed: {e}")
        
        # Final fallback - just show launch button
        self.setup_system_player(video_path)


    def display_video_thumbnail(self, video_path):
        """Displays the first frame of a video as a thumbnail, with rotation."""
        if not has_cv2 or not hasattr(self, 'video_canvas'):
            return

        try:
            cap = cv2.VideoCapture(str(video_path))
            ret, frame = cap.read()
            cap.release()

            if ret:
                # Apply rotation
                if self.video_rotation != 0:
                    (h, w) = frame.shape[:2]
                    center = (w / 2, h / 2)
                    M = cv2.getRotationMatrix2D(center, -self.video_rotation, 1.0)
                    new_dim = (w,h) if self.video_rotation == 180 else (h,w)
                    frame = cv2.warpAffine(frame, M, new_dim)

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                img.thumbnail(VIDEO_MAX, Image.LANCZOS)
                
                photo = ImageTk.PhotoImage(image=img)
                self.video_canvas.delete("all")
                self.video_canvas.create_image(VIDEO_MAX[0]//2, VIDEO_MAX[1]//2, image=photo, anchor='center')
                self.video_canvas.image = photo # Keep a reference
        except Exception as e:
            print(f"Error creating video thumbnail: {e}")


    def setup_video_audio(self, video_path: Path):
        """Setup VLC for audio playback with OpenCV video."""
        if has_vlc and self.vlc_instance:
            try:
                self.vlc_media = self.vlc_instance.media_new(str(video_path))
                self.vlc_player = self.vlc_instance.media_player_new()
                self.vlc_player.set_media(self.vlc_media)
                # Set VLC to audio-only mode
                if sys.platform.startswith("linux"):
                    self.vlc_player.set_xwindow(0)
                elif sys.platform.startswith("win32"):
                    self.vlc_player.set_hwnd(0)
                elif sys.platform.startswith("darwin"):
                     # On macOS, there is no simple way to hide the window.
                     # This will remain a known limitation.
                    pass

                print("VLC audio setup successful")
            except Exception as e:
                print(f"VLC audio setup failed: {e}")

    def launch_external_player(self, video_path: Path):
        """Launch the video in the system's default player."""
        try:
            # Kill any existing external video process first
            if hasattr(self, 'current_video_process') and self.current_video_process:
                try:
                    self.current_video_process.terminate()
                    self.current_video_process.wait(timeout=2)
                except:
                    try:
                        self.current_video_process.kill()
                    except:
                        pass
            
            # Launch external player
            self.current_video_process = open_with_default_app(str(video_path), self)
            print(f"Launched external player for: {video_path.name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch video player: {e}")


          
    def setup_system_player(self, video_path: Path):
        """Set up a button to open the video in the system's default player."""
        self.video_frame = ttk.Frame(self.preview_frame)
        self.video_frame.pack(anchor="center", fill="both", expand=True)

        # A canvas to show thumbnail or placeholder
        self.video_canvas = tk.Canvas(self.video_frame, width=VIDEO_MAX[0], height=VIDEO_MAX[1], bg="black")
        self.video_canvas.pack()
        self.display_video_thumbnail(video_path)

        # Controls
        self.video_controls = ttk.Frame(self.preview_frame)
        self.video_controls.pack(fill="x", pady=5)
        
        ttk.Label(self.video_controls, text="Embedded player not available.").pack(side="left", padx=5)
        ttk.Button(self.video_controls, text="Open in Default Player",
                  command=lambda: self.launch_external_player(video_path)).pack(side="right", padx=5)

        
    def play_video(self):
        """Play the current video with audio."""
        if not self.current_video_path:
            return
        
        # TkVideoPlayer (has built-in audio)
        if has_tkvideoplayer and self.video_player:
            self.video_player.play()
            self.video_playing = True
            return
            
        # OpenCV + VLC audio combination
        if hasattr(self, 'video_canvas') and self.video_canvas:
            self.video_playing = True
            
            # Start VLC audio
            if hasattr(self, 'vlc_player') and self.vlc_player:
                self.vlc_player.play()
            
            # Start OpenCV video
            self.play_video_cv2()
            
    def pause_video(self):
        """Pause the current video."""
        # VLC player
        if hasattr(self, 'vlc_player') and self.vlc_player:
            self.vlc_player.pause()
            self.video_playing = False # for CV2 loop
            return
            
        # TkVideoPlayer
        if has_tkvideoplayer and self.video_player:
            self.video_player.pause()
            self.video_playing = False
            
            # Pause pygame audio if available
            if hasattr(self, 'pygame_player') and self.pygame_player:
                pygame.mixer.pause()
            return
            
        # OpenCV with audio
        if self.video_playing:
            self.video_playing = False
            
            # Pause audio
            if hasattr(self, 'pygame_player') and self.pygame_player:
                pygame.mixer.pause()
            elif hasattr(self, 'pyglet_player') and self.pyglet_player:
                self.pyglet_player.pause()
            
    def stop_video(self):
        """Stop the current video and clean up resources."""
        self.video_playing = False
        
        # Stop VLC audio
        if hasattr(self, 'vlc_player') and self.vlc_player:
            try:
                self.vlc_player.stop()
            except Exception as e:
                print(f"VLC stop error: {e}")
                
        # TkVideoPlayer cleanup
        if has_tkvideoplayer and self.video_player:
            try:
                self.video_player.stop()
            except Exception as e:
                print(f"TkVideoPlayer stop error: {e}")
                
        # OpenCV cleanup
        if hasattr(self, 'cap') and self.cap:
            try:
                self.cap.release()
                self.cap = None
            except Exception as e:
                print(f"OpenCV cap release error: {e}")
        
    def set_volume(self, value):
        """Set volume for video playback."""
        volume = int(float(value))
        
        # Set VLC volume
        if hasattr(self, 'vlc_player') and self.vlc_player:
            self.vlc_player.audio_set_volume(volume)
        
        # Set TkVideoPlayer volume if available
        if hasattr(self, 'video_player') and hasattr(self.video_player, 'set_volume'):
            try:
                # TkVideoPlayer volume is 0.0 to 1.0
                self.video_player.set_volume(volume / 100.0)
            except:
                pass
            
    def play_video_cv2(self):
        """Play video using OpenCV with proper aspect ratio and rotation."""
        if not has_cv2 or not self.current_video_path or not self.video_playing:
            return
        
        if hasattr(self, 'cap') and self.cap and self.cap.isOpened():
             self.cap.release()

        self.cap = cv2.VideoCapture(str(self.current_video_path))
        
        def update_frame():
            if not self.video_playing or not hasattr(self, 'cap') or not self.cap.isOpened():
                if hasattr(self, 'cap') and self.cap: self.cap.release()
                return

            ret, frame = self.cap.read()
            if ret:
                # Apply rotation if needed
                if self.video_rotation != 0:
                    (h, w) = frame.shape[:2]
                    center = (w / 2, h / 2)
                    M = cv2.getRotationMatrix2D(center, -self.video_rotation, 1.0)
                    new_dim = (w,h) if self.video_rotation == 180 else (h,w)
                    frame = cv2.warpAffine(frame, M, new_dim)

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                img.thumbnail(VIDEO_MAX, Image.LANCZOS)
                
                photo = ImageTk.PhotoImage(image=img)
                
                if hasattr(self, 'video_canvas') and self.video_canvas.winfo_exists():
                    self.video_canvas.delete("all")
                    self.video_canvas.create_image(VIDEO_MAX[0]//2, VIDEO_MAX[1]//2, image=photo)
                    self.video_canvas.image = photo
                    
                    self.after(30, update_frame)  # ~33fps
            else:
                self.stop_video()
                # Optionally, reset to first frame thumbnail
                self.after(100, lambda: self.display_video_thumbnail(self.current_video_path))

        update_frame()
        
    def open_in_vlc(self, video_path: Path):
        """Open the video in VLC player."""
        # Stop any current playback
        self.stop_video()
        
        # Check if VLC is available
        vlc_path = None
        
        # Try to find VLC on different platforms
        if sys.platform == "win32":
            # Windows
            for path in [
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'VideoLAN', 'VLC', 'vlc.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'VideoLAN', 'VLC', 'vlc.exe')
            ]:
                if os.path.exists(path):
                    vlc_path = path
                    break
        elif sys.platform == "darwin":
            # macOS
            vlc_path = "/Applications/VLC.app/Contents/MacOS/VLC"
            if not os.path.exists(vlc_path):
                # Try Homebrew installation
                brew_vlc = "/usr/local/bin/vlc"
                if os.path.exists(brew_vlc):
                    vlc_path = brew_vlc
        else:
            # Linux
            vlc_path = "/usr/bin/vlc"
            if not os.path.exists(vlc_path):
                vlc_path = "/usr/local/bin/vlc"
                
        if vlc_path and os.path.exists(vlc_path):
            try:
                subprocess.Popen([vlc_path, str(video_path)])
            except Exception as e:
                messagebox.showerror("VLC Error", f"Failed to open VLC: {e}")
        else:
            messagebox.showinfo("VLC Not Found", 
                               "VLC player not found. Please install VLC or use the system default player.")
            self.launch_external_player(video_path)
        
    def open_in_default_player(self, video_path: Path):
        """Open the video in the system's default player."""
        if sys.platform == "win32":
            os.startfile(video_path)
        elif sys.platform == "darwin":  # macOS
            subprocess.call(["open", video_path])
        else:  # linux
            subprocess.call(["xdg-open", video_path])

    @staticmethod
    def _safe_json_list(text: str) -> List[str]:
        """Parse JSON text as a list, return empty list if invalid."""
        if not text: return []
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, list) else [str(obj)]
        except (json.JSONDecodeError, TypeError):
            return [s.strip() for s in text.split(',') if s.strip()]
            
    @staticmethod
    def _safe_json_str(text: str) -> str:
        """Parse JSON text, handle both string and object types."""
        if not text: return ""
        try:
            obj = json.loads(text)
            return str(obj) if not isinstance(obj, str) else obj
        except (json.JSONDecodeError, TypeError):
            return text

    def on_save(self):
        if not self.current_file:
            return
        keywords = [k.strip() for k in self.kw_var.get().split(",") if k.strip()]
        location_name = self.loc_var.get().strip() or "unknown"
        description = self.desc_txt.get("1.0", "end").strip()
        people = [p.strip() for p in self.people_var.get().split(",") if p.strip()]
        labels = [l.strip() for l in self.labels_var.get().split(",") if l.strip()]
        
        self.db.save_record(
            self.current_file, 
            keywords, 
            location_name, 
            description,
            people,
            labels
        )
            
        # Refresh one line in tree
        self.tree.set(self.current_file, column="desc", value=description)
        messagebox.showinfo("Saved", f"Metadata for {self.current_file} saved.")

    # --------------------------------------------------------------------
    # Navigation
    # --------------------------------------------------------------------
    def on_next(self) -> None:
        """Select the next row in the Treeview (wraps to first at end)."""
        # First completely cleanup any media players
        self.stop_video()
        
        # current selection
        selected = self.tree.selection()
        if not selected:
            return
        cur_iid = selected[0]

        # find the next sibling; if none, wrap
        nxt = self.tree.next(cur_iid)
        if not nxt:
            all_items = self.tree.get_children()
            if not all_items:
                return
            nxt = all_items[0]

        # make it the current selection and load its metadata
        self.tree.selection_set(nxt)
        self.tree.see(nxt)
        self.load_record(nxt)
        
    def on_previous(self) -> None:
        """Select the previous row in the Treeview (wraps to last at beginning)."""
        # First completely cleanup any media players
        self.stop_video()
        
        # current selection
        selected = self.tree.selection()
        if not selected:
            return
        cur_iid = selected[0]

        # find the previous sibling; if none, wrap
        prev = self.tree.prev(cur_iid)
        if not prev:
            all_items = self.tree.get_children()
            if not all_items:
                return
            prev = all_items[-1]  # Get the last item

        # make it the current selection and load its metadata
        self.tree.selection_set(prev)
        self.tree.see(prev)
        self.load_record(prev)

    # --------------------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------------------
    def quit(self):
        """Clean up resources and exit."""
        # Stop any playing video or audio
        self.stop_video()

        # Kill any external video process
        if hasattr(self, 'current_video_process') and self.current_video_process:
            try:
                self.current_video_process.terminate()
                self.current_video_process.wait(timeout=2)
            except:
                try:
                    self.current_video_process.kill()
                except:
                    pass
                
        if has_pygame:
            try:
                pygame.mixer.quit()
            except:
                pass
        
        # Close database connection
        self.db.conn.close()
        super().quit()

    # ───────────────────────────────────────────────────────────
    #  DELETE  (new feature)
    # ───────────────────────────────────────────────────────────
    def delete_selected_image(self) -> None:
        """Delete the selected image file *and* its DB row."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Delete", "No image selected.")
            return

        file_name = sel[0]                          # iid == file_name
        row = self.db.fetch_one(file_name)
        if row is None:
            # If not in DB, maybe it's just in the tree. Remove from tree.
            self.tree.delete(file_name)
            messagebox.showerror("Delete", "Record not found in database, removed from list.")
            return

        file_path_str = row["file_path"]
        if not file_path_str:
            messagebox.showerror("Delete", "File path is missing from the database record.")
            return
        
        file_path = Path(file_path_str)

        if not messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete '{file_name}' and all its metadata?\n\nThis cannot be undone."
        ):
            return

        try:
            # 1) delete file from disk (ignore if missing)
            if file_path.exists():
                os.remove(file_path)
                print(f"Deleted file: {file_path}")
            else:
                 print(f"File not found on disk, but will delete DB record: {file_path}")

            # 2) delete database row
            cur = self.db.conn.cursor()
            cur.execute("DELETE FROM media WHERE file_name = ?", (file_name,))
            self.db.conn.commit()

            # 3) update UI
            self.tree.delete(file_name)
            self.clear_form()
            messagebox.showinfo("Delete", "Image and metadata deleted successfully.")
        except Exception as exc:
            messagebox.showerror("Delete", f"An error occurred while deleting:\n{exc}")

    def clear_form(self) -> None:
        """Reset preview/image fields after a delete."""
        self.stop_video()
        if self.video_player: self.video_player.destroy()
        if self.video_frame: self.video_frame.destroy()
        
        if self.current_img: self.current_img.close()
        self.current_img = None
        self.current_file = None

        self.preview_lbl.configure(image=self.default_img)
        
        # Clear all entry fields
        self.fn_lbl.config(text="")
        self.id_lbl.config(text="")
        self.date_lbl.config(text="")
        self.loc_lbl.config(text="")
        self.kw_var.set("")
        self.loc_var.set("")
        self.people_var.set("")
        self.labels_var.set("")
        self.desc_txt.delete("1.0", "end")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Ensure the export directory exists
    PHOTOS_DIR.mkdir(exist_ok=True)
    app = MetadataEditorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
