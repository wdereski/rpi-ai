from .gui import MetadataEditorApp
from .utils import PHOTOS_DIR


def main() -> None:
    PHOTOS_DIR.mkdir(exist_ok=True)
    app = MetadataEditorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
