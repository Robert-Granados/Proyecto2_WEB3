# scheduler.py
import os
import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from main import run_all

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")


def job():
    logger.info("=== Job de scraping iniciado (%s) ===", datetime.now().isoformat())
    try:
        run_all()
        logger.info("=== Job de scraping finalizado OK ===")
    except Exception as e:
        logger.exception("Error en job de scraping: %s", e)


if __name__ == "__main__":
    minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "60"))
    scheduler = BlockingScheduler()
    scheduler.add_job(job, "interval", minutes=minutes, id="scraper_job")
    logger.info("Iniciando scheduler (cada %s minutos)...", minutes)
    scheduler.start()
