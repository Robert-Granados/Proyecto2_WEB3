import hashlib
import logging
import os
from typing import Iterable, List

from openai import OpenAI
try:
    from openai.error import APIError, RateLimitError, OpenAIError
except Exception:
    APIError = RateLimitError = OpenAIError = Exception
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("selector_helper")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

selector_cache: dict[str, List[str]] = {}


def _hash_html(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def _parse_selectors(response_text: str) -> List[str]:
    lines = [line.strip() for line in response_text.splitlines()]
    selectors = [line for line in lines if line and not line.startswith("#")]
    return selectors


def get_dynamic_selectors(html: str, fallback: Iterable[str]) -> List[str]:
    selectors = list(fallback)
    if not OPENAI_API_KEY:
        return selectors

    cache_key = _hash_html(html)
    if cache_key in selector_cache:
        return selector_cache[cache_key] + selectors

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        "Te paso un fragmento HTML y necesito que me devuelvas 3 selectores CSS válidos "
        "que capturen los contenedores principales de producto en la página de MercadoLibre. "
        "Responde sólo con los selectores en líneas separadas. Si no puedes generar ninguno, "
        "responde con la palabra NO_SELECTOR."
        f"\n\nHTML:\n{html[:4000]}"
    )

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            n=1,
        )
        content = response.choices[0].message.content
        generated = _parse_selectors(content)
        if not generated or generated == ["NO_SELECTOR"]:
            return selectors
        selector_cache[cache_key] = generated
        return generated + selectors
    except (APIError, RateLimitError, OpenAIError) as exc:
        logger.warning("OpenAI selector helper falló: %s", exc)
        return selectors
