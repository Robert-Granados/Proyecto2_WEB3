# db_utils.py
import os
import json
import hashlib
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "db"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}

DATA_DIR = os.getenv("DATA_DIR", "data")

logging.basicConfig(
    filename=os.path.join(os.getenv("LOGS_DIR", "logs"), "scraper.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("db_utils")


@contextmanager
def get_conn():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


def compute_product_hash(product: dict) -> str:
    base = (
        f"{product.get('name','')}|{product.get('brand','')}|{product.get('category','')}|"
        f"{product.get('price')}|{product.get('url','')}|{product.get('image_url','')}"
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def compute_file_hash_value(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def add_event(conn, entity_type: str, entity_id: int | None, event_type: str, description: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO events (entity_type, entity_id, event_type, description)
            VALUES (%s, %s, %s, %s)
            """,
            (entity_type, entity_id, event_type, description),
        )


def upsert_product(product: dict, run_ts: datetime):
    data_hash = compute_product_hash(product)

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, data_hash, is_active FROM products WHERE url = %s", (product["url"],))
            row = cur.fetchone()

            if row is None:
                cur.execute(
                    """
                    INSERT INTO products (url, name, brand, category, image_url, price, currency, page,
                                          first_seen_at, last_seen_at, data_hash, is_active)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
                    RETURNING id
                    """,
                    (
                        product["url"],
                        product.get("name"),
                        product.get("brand"),
                        product.get("category"),
                        product.get("image_url"),
                        product.get("price"),
                        product.get("currency"),
                        product.get("page"),
                        run_ts,
                        run_ts,
                        data_hash,
                    ),
                )
                new_id = cur.fetchone()["id"]
                add_event(conn, "product", new_id, "created", f"Producto nuevo: {product.get('name')}")
                logger.info("Producto creado: %s", product.get("name"))
            else:
                cur.execute(
                    "UPDATE products SET last_seen_at = %s WHERE id = %s",
                    (run_ts, row["id"]),
                )

                if row["data_hash"] != data_hash:
                    cur.execute(
                        """
                    UPDATE products
                    SET name = %s,
                        brand = %s,
                        category = %s,
                        image_url = %s,
                        price = %s,
                        currency = %s,
                        page = %s,
                        data_hash = %s,
                        last_change_at = %s,
                        is_active = TRUE
                    WHERE id = %s
                    """,
                    (
                        product.get("name"),
                        product.get("brand"),
                        product.get("category"),
                        product.get("image_url"),
                        product.get("price"),
                        product.get("currency"),
                        product.get("page"),
                        data_hash,
                        run_ts,
                        row["id"],
                    ),
                    )
                    add_event(conn, "product", row["id"], "updated", f"Producto actualizado: {product.get('name')}")
                    logger.info("Producto actualizado: %s", product.get("name"))
                else:
                    if not row["is_active"]:
                        cur.execute(
                            "UPDATE products SET is_active = TRUE, last_change_at = %s WHERE id = %s",
                            (run_ts, row["id"]),
                        )
                        add_event(conn, "product", row["id"], "reactivated", f"Producto reapareció: {product.get('name')}")
                        logger.info("Producto reactivado: %s", product.get("name"))

        conn.commit()


def mark_missing_products(run_ts: datetime):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name FROM products
                WHERE is_active = TRUE AND last_seen_at < %s
                """,
                (run_ts,),
            )
            rows = cur.fetchall()

            for row in rows:
                cur.execute(
                    "UPDATE products SET is_active = FALSE, last_change_at = %s WHERE id = %s",
                    (run_ts, row["id"]),
                )
                add_event(conn, "product", row["id"], "deleted", f"Producto ya no aparece: {row['name']}")
                logger.info("Producto marcado como eliminado: %s", row["name"])

        conn.commit()


def upsert_file_record(file_info: dict, run_ts: datetime):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, hash, is_active FROM files WHERE url = %s", (file_info["url"],))
            row = cur.fetchone()

            if row is None:
                cur.execute(
                    """
                    INSERT INTO files (url, filename, local_path, mime_type, hash,
                                       first_seen_at, last_seen_at, is_active)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE)
                    RETURNING id
                    """,
                    (
                        file_info["url"],
                        file_info["filename"],
                        file_info["local_path"],
                        file_info.get("mime_type"),
                        file_info["hash"],
                        run_ts,
                        run_ts,
                    ),
                )
                new_id = cur.fetchone()["id"]
                add_event(conn, "file", new_id, "created", f"Archivo nuevo: {file_info['filename']}")
                logger.info("Archivo creado: %s", file_info["filename"])
            else:
                cur.execute(
                    "UPDATE files SET last_seen_at = %s WHERE id = %s",
                    (run_ts, row["id"]),
                )

                if row["hash"] != file_info["hash"]:
                    cur.execute(
                        """
                        UPDATE files
                        SET filename = %s,
                            local_path = %s,
                            mime_type = %s,
                            hash = %s,
                            last_change_at = %s,
                            is_active = TRUE
                        WHERE id = %s
                        """,
                        (
                            file_info["filename"],
                            file_info["local_path"],
                            file_info.get("mime_type"),
                            file_info["hash"],
                            run_ts,
                            row["id"],
                        ),
                    )
                    add_event(conn, "file", row["id"], "file_changed", f"Archivo cambió: {file_info['filename']}")
                    logger.info("Archivo cambiado: %s", file_info["filename"])
                else:
                    if not row["is_active"]:
                        cur.execute(
                            "UPDATE files SET is_active = TRUE, last_change_at = %s WHERE id = %s",
                            (run_ts, row["id"]),
                        )
                        add_event(conn, "file", row["id"], "reactivated", f"Archivo reapareció: {file_info['filename']}")
                        logger.info("Archivo reactivado: %s", file_info["filename"])

        conn.commit()


def mark_missing_files(run_ts: datetime):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, filename, local_path FROM files
                WHERE is_active = TRUE AND last_seen_at < %s
                """,
                (run_ts,),
            )
            rows = cur.fetchall()

            for row in rows:
                cur.execute(
                    "UPDATE files SET is_active = FALSE, last_change_at = %s WHERE id = %s",
                    (run_ts, row["id"]),
                )
                add_event(conn, "file", row["id"], "deleted", f"Archivo ya no disponible: {row['filename']}")
                logger.info("Archivo marcado eliminado: %s", row["filename"])
                local_path = row.get("local_path")
                if local_path:
                    try:
                        if os.path.exists(local_path):
                            os.remove(local_path)
                            logger.info("Archivo local eliminado tras desaparición: %s", local_path)
                    except OSError as exc:
                        logger.warning("No se pudo eliminar archivo local %s: %s", local_path, exc)

        conn.commit()


def fetch_file_records(active_only: bool = True) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT id, url, filename, local_path, mime_type, hash, is_active
                FROM files
            """
            params: list = []
            if active_only:
                query += " WHERE is_active = TRUE"
            cur.execute(query, params)
            return cur.fetchall()


def _datetime_to_iso(rows, keys):
    for r in rows:
        for key in keys:
            if r.get(key) is not None and isinstance(r[key], datetime):
                r[key] = r[key].isoformat()
    return rows


def _decimal_to_float(rows, keys):
    for r in rows:
        for key in keys:
            if isinstance(r.get(key), Decimal):
                r[key] = float(r[key])
    return rows


def export_products_to_json(path: str | None = None):
    if path is None:
        path = os.path.join(DATA_DIR, "results.json")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, url, name, brand, category, image_url, price, currency,
                       page, first_seen_at, last_seen_at, last_change_at, is_active
                FROM products
                ORDER BY last_seen_at DESC
                """
            )
            rows = cur.fetchall()

    rows = _datetime_to_iso(rows, ["first_seen_at", "last_seen_at", "last_change_at"])
    rows = _decimal_to_float(rows, ["price"])

    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def export_files_to_json(path: str | None = None):
    if path is None:
        path = os.path.join(DATA_DIR, "files.json")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, url, filename, local_path, mime_type, hash,
                       first_seen_at, last_seen_at, last_change_at, is_active
                FROM files
                ORDER BY last_seen_at DESC
                """
            )
            rows = cur.fetchall()

    rows = _datetime_to_iso(rows, ["first_seen_at", "last_seen_at", "last_change_at"])

    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def export_events_to_json(path: str | None = None):
    if path is None:
        path = os.path.join(DATA_DIR, "events.json")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, entity_type, entity_id, event_type, description, created_at
                FROM events
                ORDER BY created_at DESC
                """
            )
            rows = cur.fetchall()

    rows = _datetime_to_iso(rows, ["created_at"])

    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def _merge_updates(base: dict, updates: dict, allowed: set):
    merged = dict(base)
    for key in allowed:
        if key in updates:
            merged[key] = updates[key]
    return merged


def update_product_record(product_id: int, updates: dict) -> dict | None:
    now = datetime.now(timezone.utc)
    allowed = {"name", "brand", "category", "image_url", "price", "currency", "is_active"}
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            row = cur.fetchone()
            if row is None:
                return None

            merged = _merge_updates(row, updates, allowed)
            data_hash = compute_product_hash(merged)
            cur.execute(
                """
                UPDATE products
                SET name = %s,
                    brand = %s,
                    category = %s,
                    image_url = %s,
                    price = %s,
                    currency = %s,
                    last_change_at = %s,
                    data_hash = %s,
                    is_active = %s
                WHERE id = %s
                """,
                (
                    merged.get("name"),
                    merged.get("brand"),
                    merged.get("category"),
                    merged.get("image_url"),
                    merged.get("price"),
                    merged.get("currency"),
                    now,
                    data_hash,
                    bool(merged.get("is_active")),
                    product_id,
                ),
            )
            add_event(
                conn,
                "product",
                product_id,
                "updated",
                f"Producto editado manualmente: {merged.get('name') or product_id}",
            )
            logger.info("Producto editado manualmente: %s", merged.get("name"))

        conn.commit()

    merged["last_change_at"] = now
    export_products_to_json()
    merged["is_active"] = bool(merged.get("is_active", True))
    normalized = _datetime_to_iso([merged], ["first_seen_at", "last_seen_at", "last_change_at"])
    normalized = _decimal_to_float(normalized, ["price"])
    return normalized[0]


def deactivate_product_record(product_id: int) -> bool:
    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT name FROM products WHERE id = %s", (product_id,))
            row = cur.fetchone()
            if row is None:
                return False
            cur.execute(
                "UPDATE products SET is_active = FALSE, last_change_at = %s WHERE id = %s",
                (now, product_id),
            )
            add_event(conn, "product", product_id, "deleted", f"Producto eliminado manualmente: {row['name']}")
            logger.info("Producto eliminado manualmente: %s", row["name"])

        conn.commit()

    export_products_to_json()
    return True


def update_file_record(file_id: int, updates: dict) -> dict | None:
    now = datetime.now(timezone.utc)
    allowed = {"filename", "local_path", "mime_type", "is_active"}
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM files WHERE id = %s", (file_id,))
            row = cur.fetchone()
            if row is None:
                return None

            merged = _merge_updates(row, updates, allowed)
            cur.execute(
                """
                UPDATE files
                SET filename = %s,
                    local_path = %s,
                    mime_type = %s,
                    last_change_at = %s,
                    is_active = %s
                WHERE id = %s
                """,
                (
                    merged.get("filename"),
                    merged.get("local_path"),
                    merged.get("mime_type"),
                    now,
                    bool(merged.get("is_active")),
                    file_id,
                ),
            )
            add_event(
                conn,
                "file",
                file_id,
                "updated",
                f"Archivo editado manualmente: {merged.get('filename') or file_id}",
            )
            logger.info("Archivo editado manualmente: %s", merged.get("filename"))

        conn.commit()

    merged["last_change_at"] = now
    export_files_to_json()
    merged["is_active"] = bool(merged.get("is_active", True))
    normalized = _datetime_to_iso([merged], ["first_seen_at", "last_seen_at", "last_change_at"])
    return normalized[0]


def deactivate_file_record(file_id: int) -> bool:
    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT filename FROM files WHERE id = %s", (file_id,))
            row = cur.fetchone()
            if row is None:
                return False
            cur.execute(
                "UPDATE files SET is_active = FALSE, last_change_at = %s WHERE id = %s",
                (now, file_id),
            )
            add_event(conn, "file", file_id, "deleted", f"Archivo eliminado manualmente: {row['filename']}")
            logger.info("Archivo eliminado manualmente: %s", row["filename"])

        conn.commit()

    export_files_to_json()
    return True
