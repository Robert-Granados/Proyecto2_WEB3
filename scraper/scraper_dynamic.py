# scraper/scraper_dynamic.py
import os
import time
import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from db_utils import upsert_product
from scraper.scraper_static import (
    extract_brand_from_product_page,
    get_session,
    guess_brand_from_name,
    parse_price,
)

load_dotenv()

BASE_CATEGORY_URL = os.getenv(
    "SCRAPER_CATEGORY_URL",
    "https://listado.mercadolibre.co.cr/computacion",
)
logger = logging.getLogger("scraper_dynamic")


def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1366,768")
    options.binary_location = os.getenv("CHROME_BIN", "/usr/bin/chromium")
    driver = webdriver.Chrome(options=options)
    return driver


def _normalize_image_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    if url.startswith("//"):
        url = f"https:{url}"
    if url.startswith("data:"):
        return None
    return url


def _extract_from_srcset(srcset: Optional[str]) -> Optional[str]:
    if not srcset:
        return None
    for candidate in srcset.split(","):
        url = candidate.strip().split(" ")[0]
        normalized = _normalize_image_url(url)
        if normalized:
            return normalized
    return None


def extract_image_url_from_card(card):
    selectors = [
        "img.ui-search-result-image__element",
        "img.ui-search-result-image__wrapper img",
        "img",
    ]
    attrs = (
        "data-src",
        "data-srcset",
        "data-original",
        "src",
        "srcset",
        "data-lazy",
        "data-lazy-src",
        "data-lazy-srcset",
        "data-image",
    )
    for selector in selectors:
        try:
            img_el = card.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        for attr in attrs:
            value = img_el.get_attribute(attr)
            if attr.endswith("srcset"):
                url = _extract_from_srcset(value)
            else:
                url = _normalize_image_url(value)
            if url:
                return url
    return None


def parse_products_from_dom(
    driver,
    page_number: int,
    session: requests.Session,
    brand_cache: dict[str, Optional[str]],
):
    products = []
    cards = driver.find_elements(By.CSS_SELECTOR, "li.ui-search-layout__item div.poly-card")

    for card in cards:
        try:
            title_el = card.find_element(By.CSS_SELECTOR, "a.poly-component__title")
            name = title_el.text.strip()
            url = title_el.get_attribute("href")
        except Exception:
            name, url = "Producto", None

        try:
            price_main = card.find_element(By.CSS_SELECTOR, ".andes-money-amount__fraction").text.strip()
        except Exception:
            price_main = ""
        try:
            price_cents = card.find_element(By.CSS_SELECTOR, ".andes-money-amount__cents").text.strip()
        except Exception:
            price_cents = ""

        price_text = price_main if price_main else ""
        if price_text and price_cents:
            price_text = f"{price_text}.{price_cents}"

        price, currency = parse_price(price_text, "CRC")

        brand = None
        if url:
            brand = brand_cache.get(url)
            if brand is None:
                brand = extract_brand_from_product_page(session, url)
                brand_cache[url] = brand
        if not brand:
            brand = guess_brand_from_name(name)

        product = {
            "url": url,
            "name": name,
            "brand": brand,
            "category": "MercadoLibre - Dinamico",
            "image_url": extract_image_url_from_card(card),
            "price": price,
            "currency": currency,
            "page": page_number,
        }

        if url and price is not None:
            products.append(product)

    return products


def run_dynamic_scraper(run_ts: datetime | None = None, max_pages: int = 1):
    if run_ts is None:
        run_ts = datetime.now(timezone.utc)

    logger.info("=== Inicio scraper dinamico ===")
    driver = get_driver()
    brand_cache: dict[str, Optional[str]] = {}
    session = get_session()
    all_products = []
    try:
        for page in range(1, max_pages + 1):
            if page == 1:
                url = BASE_CATEGORY_URL
            else:
                offset = 1 + (page - 1) * 48
                url = BASE_CATEGORY_URL.rstrip("/") + f"/_Desde_{offset}"

            logger.info("[dyn] Navegando a %s", url)
            driver.get(url)
            time.sleep(5)

            products = parse_products_from_dom(driver, page, session, brand_cache)
            for p in products:
                upsert_product(p, run_ts)
                all_products.append(p)

        logger.info("=== Fin scraper dinamico. Productos: %s ===", len(all_products))
    finally:
        driver.quit()

    return all_products
