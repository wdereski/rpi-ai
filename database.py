import json
import os
import sqlite3
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .constants import DB_FILE, PHOTOS_DIR, VIDEO_EXTENSIONS, JSONL_CHUNK


class MetadataDB:
    """Context-manager wrapper around sqlite3 with JSON helper methods."""

    def __init__(self, db_path: str = DB_FILE):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    # -- context management -------------------------------------------------
    def __enter__(self) -> "MetadataDB":
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.conn.close()

    # -- schema -------------------------------------------------------------
    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS media (
                id            TEXT PRIMARY KEY,
                file_name     TEXT NOT NULL UNIQUE,
                media_type    TEXT,
                date_original TEXT,
                keywords      TEXT,
                genre         TEXT,
                duration      TEXT,
                file_path     TEXT,
                file_size     INTEGER,
                file_ext      TEXT,
                width         INTEGER,
                height        INTEGER,
                tags          TEXT,
                people        TEXT,
                location_name TEXT,
                location      TEXT,
                latitude      REAL,
                longitude     REAL,
                labels        TEXT,
                description   TEXT,
                date_added    TEXT,
                last_updated  TEXT
            )
            """
        )
        self.conn.commit()

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _json_dump(obj: Any) -> str:
        return json.dumps(obj, separators=(",", ":"))

    @staticmethod
    def _json_load(text: Any) -> Any:
        if isinstance(text, (list, dict)) or text in (None, "", "None"):
            return text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    # -- import / merge -----------------------------------------------------
    def import_master(self, path: Path) -> int:
        """Load master data file (line-delimited JSON). Returns # inserted."""
        cur = self.conn.cursor()
        inserted = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                # normalise field names (master sample uses "File Name", etc.)
                record = {
                    "id": data.get("id") or os.urandom(8).hex(),
                    "file_name": data.get("File Name") or data.get("file_name"),
                    "media_type": data.get("Media Type"),
                    "date_original": data.get("Date Original"),
                    "keywords": self._json_dump(
                        MetadataDB._json_load(data.get("Keywords"))
                    ),
                    "genre": data.get("Genre"),
                    "duration": data.get("Duration"),
                    "file_path": data.get("File Path"),
                    "file_size": data.get("File Size"),
                    "file_ext": data.get("File Ext"),
                    "width": data.get("Width"),
                    "height": data.get("Height"),
                    "tags": self._json_dump(MetadataDB._json_load(data.get("Tags"))),
                    "people": self._json_dump(MetadataDB._json_load(data.get("People"))),
                    "location_name": self._json_dump(
                        MetadataDB._json_load(data.get("Location Name"))
                    ),
                    "location": self._json_dump(
                        MetadataDB._json_load(data.get("Location"))
                    ),
                    "latitude": data.get("Latitude"),
                    "longitude": data.get("Longitude"),
                    "labels": self._json_dump(MetadataDB._json_load(data.get("Labels"))),
                    "description": data.get("Description"),
                    "date_added": data.get("Date Added"),
                    "last_updated": data.get("Last Updated"),
                }
                try:
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO media(
                            id,file_name,media_type,date_original,keywords,genre,duration,
                            file_path,file_size,file_ext,width,height,tags,people,
                            location_name,location,latitude,longitude,labels,description,
                            date_added,last_updated
                        ) VALUES(
                            :id,:file_name,:media_type,:date_original,:keywords,:genre,:duration,
                            :file_path,:file_size,:file_ext,:width,:height,:tags,:people,
                            :location_name,:location,:latitude,:longitude,:labels,:description,
                            :date_added,:last_updated
                        )
                        """,
                        record,
                    )
                    inserted += cur.rowcount
                except sqlite3.IntegrityError as err:
                    print("DB error:", err, file=sys.stderr)
        self.conn.commit()
        return inserted

    def merge_updates(self, path: Path) -> int:
        """Apply AI-enriched updates. Returns # rows updated."""
        cur = self.conn.cursor()
        updated = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                cur.execute(
                    """
                    UPDATE media
                       SET keywords      = :keywords,
                           location_name = :location_name,
                           description   = :description,
                           last_updated  = datetime('now')
                     WHERE id = :id OR file_name = :file_name
                    """,
                    {
                        "keywords": self._json_dump(data.get("keywords")),
                        "location_name": self._json_dump(data.get("location_name")),
                        "description": data.get("description"),
                        "id": data.get("id"),
                        "file_name": data.get("file_name"),
                    },
                )
                updated += cur.rowcount
        self.conn.commit()
        return updated

    # -- query --------------------------------------------------------------
    def search(self, query: str) -> List[sqlite3.Row]:
        """Search for media records across text fields."""
        cur = self.conn.cursor()
        q = f"%{query.lower()}%"
        cur.execute(
            """
            SELECT *
              FROM media
             WHERE lower(file_name)     LIKE ?
                OR lower(id)            LIKE ?
                OR lower(description)   LIKE ?
                OR lower(location_name) LIKE ?
                OR lower(keywords)      LIKE ?
                OR lower(people)        LIKE ?
                OR lower(labels)        LIKE ?
                OR lower(tags)          LIKE ?
             ORDER BY file_name
            """,
            (q, q, q, q, q, q, q, q),
        )
        return cur.fetchall()

    def add_new_media(self, file_path: Path) -> str | None:
        """Add a new media file to the database."""
        if not file_path.exists():
            return None

        PHOTOS_DIR.mkdir(exist_ok=True)
        dest_path = PHOTOS_DIR / file_path.name
        shutil.copy2(file_path, dest_path)

        cur = self.conn.cursor()
        new_id = os.urandom(8).hex()
        file_name = dest_path.name

        record = {
            "id": new_id,
            "file_name": file_name,
            "file_path": str(dest_path),
            "media_type": "image" if file_path.suffix.lower() not in VIDEO_EXTENSIONS else "video",
            "date_added": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
        }

        try:
            cur.execute(
                """
                INSERT INTO media (id, file_name, file_path, media_type, date_added, last_updated)
                VALUES (:id, :file_name, :file_path, :media_type, :date_added, :last_updated)
                """,
                record,
            )
            self.conn.commit()
            return file_name
        except sqlite3.IntegrityError as err:
            print(f"Error adding new media: {err}", file=sys.stderr)
            return None

    def fetch_all(self) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM media ORDER BY file_name")
        return cur.fetchall()

    def fetch_one(self, file_name: str) -> sqlite3.Row | None:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM media WHERE file_name = ?", (file_name,))
        return cur.fetchone()

    def save_record(
        self,
        file_name: str,
        keywords: List[str],
        location_name: str | Dict[str, Any],
        description: str,
        people: List[str],
        labels: List[str],
    ) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE media
               SET keywords      = ?,
                   location_name = ?,
                   description   = ?,
                   people        = ?,
                   labels        = ?,
                   last_updated  = datetime('now')
             WHERE file_name = ?
            """,
            (
                self._json_dump(keywords),
                self._json_dump(location_name),
                description,
                self._json_dump(people),
                self._json_dump(labels),
                file_name,
            ),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # EXPORT for OpenAI vector-store
    # ------------------------------------------------------------------

    def export_jsonl(
        self,
        out_dir: Path,
        chunk_size: int = JSONL_CHUNK,
        *,
        include_all_fields: bool = True,
        fields: Tuple[str, ...] | None = None,
    ) -> int:
        """Export database records to JSONL chunks."""
        if isinstance(out_dir, str):
            out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        cur = self.conn.cursor()

        if include_all_fields or fields is None:
            cur.execute("PRAGMA table_info(media)")
            fields = tuple(row[1] for row in cur.fetchall())

        fields_str = ", ".join(f'"{field}"' for field in fields)
        cur.execute(f"SELECT {fields_str} FROM media")

        chunk_idx, current_size = 0, 0
        outfile_path = out_dir / f"media_chunk_{chunk_idx:04d}.jsonl"
        print(f"Creating export file: {outfile_path}")

        outfile = outfile_path.open("w", encoding="utf-8")

        def process_row(row: sqlite3.Row) -> dict:
            result = {}
            for col in fields:
                val = row[col]
                if col in {
                    "id",
                    "file_name",
                    "media_type",
                    "date_original",
                    "keywords",
                    "genre",
                    "duration",
                    "file_path",
                    "file_size",
                    "file_ext",
                    "width",
                    "height",
                    "tags",
                    "people",
                    "location_name",
                    "location",
                    "latitude",
                    "longitude",
                    "labels",
                    "description",
                    "date_added",
                    "last_updated",
                }:
                    try:
                        val = self._json_load(val)
                    except Exception as e:
                        print(f"Warning: Could not parse JSON for {col}: {e}")
                    result[col] = val
            return result

        records_processed = 0
        for row in cur:
            try:
                record = process_row(row)
                line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
                if current_size + len(line.encode("utf-8")) > chunk_size:
                    outfile.close()
                    chunk_idx += 1
                    outfile_path = out_dir / f"media_chunk_{chunk_idx:04d}.jsonl"
                    print(f"Creating export file: {outfile_path}")
                    outfile = outfile_path.open("w", encoding="utf-8")
                    current_size = 0
                outfile.write(line)
                current_size += len(line.encode("utf-8"))
                records_processed += 1
                if records_processed % 100 == 0:
                    print(f"Processed {records_processed} records...")
            except Exception as e:
                print(f"Error processing record: {e}")
                continue

        outfile.close()
        print(f"Export complete: {records_processed} records in {chunk_idx + 1} files")
        return chunk_idx + 1
