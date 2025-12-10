# main.py
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from scraper.scraper_static import run_static_scraper
from scraper.scraper_dynamic import run_dynamic_scraper
from db_utils import (
    mark_missing_products,
    mark_missing_files,
    export_products_to_json,
    export_files_to_json,
    export_events_to_json,
)

load_dotenv()


def run_all():
    run_ts = datetime.now(timezone.utc)

    static_products = run_static_scraper(run_ts)

    dynamic_products = []
    if os.getenv("ENABLE_DYNAMIC_SCRAPER", "0") == "1":
        dynamic_products = run_dynamic_scraper(run_ts, max_pages=1)

    if static_products or dynamic_products:
        mark_missing_products(run_ts)
        mark_missing_files(run_ts)
    else:
        logger = logging.getLogger("main")
        logger.warning("No se encontraron productos ni dinámicos; se omite marcar como eliminados.")

    export_products_to_json()
    export_files_to_json()
    export_events_to_json()


if __name__ == "__main__":
    run_all()
