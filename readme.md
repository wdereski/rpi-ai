
# MediaVaultPro

This project provides a Tkinter-based application for managing media metadata.

Run `python mediavaultpro.py` to launch the GUI.

The application code is organized into modules under the `mediavaultpro/`
package:

- `constants.py` – shared configuration values.
- `utils.py` – helper functions such as launching files with the system default
  application.
- `database.py` – the `MetadataDB` class that wraps SQLite operations.
- `app.py` – the `MetadataEditorApp` GUI and `main()` entry point.

This project provides a simple GUI tool for browsing and editing metadata
for a local collection of photos and videos.

The application stores the path to your media directory in a lightweight
`config.json` file located inside the `rpi_ai` package. The default path is
`photos_export`. You can change it from the **Settings → Set Media Folder...**
menu within the GUI or by editing the JSON file directly.

This repository contains a simple media metadata editor packaged as `rpi_ai`.

## Usage

Run the application with Python's module syntax:

```bash
python -m rpi_ai.main
```
