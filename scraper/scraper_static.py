# scraper/scraper_static.py
import os
import time
import logging
import json
import re
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from db_utils import upsert_product, upsert_file_record, compute_file_hash_value
from scraper.selector_helper import get_dynamic_selectors
from scraper.file_monitor import monitor_local_file_changes

load_dotenv()

# MercadoLibre Costa Rica
BASE_CATEGORY_URL = os.getenv(
    "SCRAPER_CATEGORY_URL",
    "https://listado.mercadolibre.co.cr/computacion",
)
MAX_PAGES = int(os.getenv("SCRAPER_MAX_PAGES", "3"))
USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (compatible; ScraperBot/1.0)",
)
ITEMS_PER_PAGE = 48  # ML typically shows 48 results per page
DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", "downloads")
STATIC_FILE_URLS = [u.strip() for u in os.getenv("STATIC_FILE_URLS", "").split(",") if u.strip()]

logger = logging.getLogger("scraper_static")
BRAND_JSON_PATTERN = re.compile(r'"id"\s*:\s*"Marca"\s*,\s*"text"\s*:\s*"([^"]+)"')
KNOWN_BRANDS = [
    "ASUS",
    "ACER",
    "HP",
    "DELL",
    "LENOVO",
    "APPLE",
    "SAMSUNG",
    "LG",
    "SONY",
    "MSI",
    "INTEL",
    "NVIDIA",
    "GIGABYTE",
    "RAZER",
    "LOGITECH",
    "CORSAIR",
    "HYPERX",
    "THERMALTAKE",
    "ACER",
    "KINGSTON",
    "ADATA",
    "CYBERPOWER",
    "EVGA",
    "SKYTECH",
    "PANASONIC",
    "MICROSOFT",
    "GOOGLE",
    "HUAWEI",
    "XIAOMI",
    "AMD",
]


def get_session():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "es-CR,es;q=0.9,en;q=0.8",
        }
    )
    return session


def parse_price(text: str, default_currency: str | None = "CRC"):
    """Normalize ML price format (e.g. '₡315,000.50')."""
    if not text:
        return None, default_currency

    numeric_part = "".join(ch for ch in text if ch.isdigit() or ch in ",.")
    if not numeric_part:
        return None, default_currency

    normalized = numeric_part.replace(".", "").replace(",", "")
    try:
        value = float(normalized)
    except ValueError:
        return None, default_currency

    return value, default_currency


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

    for selector in selectors:
        img = card.select_one(selector)
        if not img:
            continue

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

        for attr in attrs:
            value = img.get(attr)
            if attr.endswith("srcset"):
                url = _extract_from_srcset(value)
            else:
                url = _normalize_image_url(value)
            if url:
                return url

    return None

def extract_brand_from_product_page(session: requests.Session, url: str) -> Optional[str]:
    if not url:
        return None
    try:
        resp = session.get(url, timeout=20)
    except requests.RequestException as exc:
        logger.debug("No se pudo cargar %s para leer la marca: %s", url, exc)
        return None
    if resp.status_code != 200:
        logger.debug("Respuesta %s al pedir %s para extraer marca", resp.status_code, url)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    for th in soup.select("th"):
        label = th.get_text(strip=True).lower()
        if label == "marca":
            td = th.find_next_sibling("td")
            if td:
                text = td.get_text(" ", strip=True)
                return text or None

    json_match = BRAND_JSON_PATTERN.search(resp.text)
    if json_match:
        raw_brand = json_match.group(1)
        try:
            return json.loads(f"\"{raw_brand}\"")
        except json.JSONDecodeError:
            return raw_brand or None

    return None


def guess_brand_from_name(name: str | None) -> Optional[str]:
    if not name:
        return None
    upper_name = name.upper()
    # prefer longer brand names first
    for brand in sorted(KNOWN_BRANDS, key=len, reverse=True):
        if brand in upper_name:
            return brand if brand.isupper() else brand.title()
    # fallback to first word if uppercase context
    first = name.split()[0]
    if first.isupper() and len(first) <= 4:
        return first
    return None


def parse_products_from_page(html: str, page_number: int, session: requests.Session, brand_cache: dict[str, Optional[str]]):
    soup = BeautifulSoup(html, "html.parser")
    products = []

    card_selectors = get_dynamic_selectors(html, ["li.ui-search-layout__item div.poly-card"])
    product_cards = []
    for selector in card_selectors:
        product_cards = soup.select(selector)
        if product_cards:
            break
    for card in product_cards:
        title_el = card.select_one("a.poly-component__title")
        name = title_el.get_text(strip=True) if title_el else "Producto sin nombre"
        url = title_el["href"] if title_el and title_el.has_attr("href") else None

        price_fraction = card.select_one(".andes-money-amount__fraction")
        price_cents = card.select_one(".andes-money-amount__cents")
        currency_symbol = card.select_one(".andes-money-amount__currency-symbol")

        price_text = price_fraction.get_text(strip=True) if price_fraction else ""
        if price_cents:
            price_text = f"{price_text}.{price_cents.get_text(strip=True)}"

        currency = "CRC" if currency_symbol and "₡" in currency_symbol.get_text() else "CRC"
        price, currency = parse_price(price_text, currency)

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
            "category": "MercadoLibre - Computacion",
            "image_url": extract_image_url_from_card(card),
            "price": price,
            "currency": currency,
            "page": page_number,
        }

        if product["url"] and product["price"] is not None:
            products.append(product)

    return products


def fetch_page(session: requests.Session, url: str):
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            logger.warning("Status %s al pedir %s", resp.status_code, url)
            return None
        return resp.text
    except requests.RequestException as e:
        logger.error("Error al pedir %s: %s", url, e)
        return None


def iterate_category_pages(run_ts: datetime):
    session = get_session()
    all_products = []
    brand_cache: dict[str, Optional[str]] = {}

    for page in range(1, MAX_PAGES + 1):
        if page == 1:
            url = BASE_CATEGORY_URL
        else:
            offset = 1 + (page - 1) * ITEMS_PER_PAGE
            url = BASE_CATEGORY_URL.rstrip("/") + f"/_Desde_{offset}"

        logger.info("Scraping page %s: %s", page, url)
        html = fetch_page(session, url)
        if not html:
            break

        products = parse_products_from_page(html, page, session, brand_cache)
        if not products:
            logger.info("No products on page %s, stopping pagination", page)
            break

        for p in products:
            upsert_product(p, run_ts)
            all_products.append(p)

        time.sleep(2)

    return all_products


def download_static_files(run_ts: datetime):
    if not STATIC_FILE_URLS:
        logger.info("No hay STATIC_FILE_URLS definidas.")
        return

    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    session = get_session()

    for file_url in STATIC_FILE_URLS:
        try:
            resp = session.get(file_url, timeout=30)
            if resp.status_code != 200:
                logger.warning("No se pudo descargar archivo %s (status %s)", file_url, resp.status_code)
                continue

            filename = file_url.rstrip("/").split("/")[-1] or "index.html"
            local_path = os.path.join(DOWNLOADS_DIR, filename)

            content = resp.content
            with open(local_path, "wb") as f:
                f.write(content)

            hash_val = compute_file_hash_value(content)
            mime_type = resp.headers.get("Content-Type", "")

            file_info = {
                "url": file_url,
                "filename": filename,
                "local_path": local_path,
                "mime_type": mime_type,
                "hash": hash_val,
            }

            upsert_file_record(file_info, run_ts)
            logger.info("Archivo descargado y registrado: %s", file_url)

            time.sleep(1)
        except requests.RequestException as e:
            logger.error("Error descargando archivo %s: %s", file_url, e)


def run_static_scraper(run_ts: datetime | None = None):
    if run_ts is None:
        run_ts = datetime.now(timezone.utc)

    logger.info("=== Inicio scraper estatico ===")
    monitor_local_file_changes(run_ts)
    products = iterate_category_pages(run_ts)
    download_static_files(run_ts)
    logger.info("=== Fin scraper estatico. Productos encontrados: %s ===", len(products))
    return products
