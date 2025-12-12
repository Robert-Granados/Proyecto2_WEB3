import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from db_utils import (
    compute_file_hash_value,
    deactivate_file_record,
    fetch_file_records,
    upsert_file_record,
)

logger = logging.getLogger("file_monitor")
DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", "downloads")


def monitor_local_file_changes(
    run_ts: datetime | None = None,
    downloads_dir: str | None = None,
):
    if run_ts is None:
        run_ts = datetime.now(timezone.utc)

    dir_path = downloads_dir or DOWNLOADS_DIR
    Path(dir_path).mkdir(parents=True, exist_ok=True)
    records = fetch_file_records(active_only=True)
    if not records:
        return

    for record in records:
        local_path = record.get("local_path")
        if not local_path:
            continue

        file_path = Path(local_path)
        if not file_path.exists():
            logger.warning("Archivo local perdido detectado: %s", local_path)
            deactivate_file_record(record["id"])
            continue

        try:
            content = file_path.read_bytes()
        except OSError as exc:
            logger.warning("No se pudo leer %s para verificar hash: %s", local_path, exc)
            continue

        current_hash = compute_file_hash_value(content)
        if current_hash != record.get("hash"):
            file_info = {
                "url": record.get("url"),
                "filename": record.get("filename") or file_path.name,
                "local_path": local_path,
                "mime_type": record.get("mime_type"),
                "hash": current_hash,
            }
            upsert_file_record(file_info, run_ts)
            logger.info("Hash actualizado manualmente: %s", file_path.name)
