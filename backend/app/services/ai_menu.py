"""AI menu features: text menu generation (OpenAI chat) and food photo
generation (OpenAI image) with Supabase Storage hosting.

All provider calls are plain httpx REST — no vendor SDK. Every function
raises AIServiceError with a user-facing message when the provider is
not configured or the call fails, so the API layer can map it to a
503/502 without leaking provider details.
"""

import base64
import binascii
import json
import re
import uuid

import httpx

from app.core.config import settings

OPENAI_BASE = "https://api.openai.com/v1"

MAX_GENERATED_ITEMS = 40
MAX_PRICE_CENTS = 30000

MENU_SYSTEM_PROMPT = (
    "You write menus for a restaurant on a food delivery app. "
    "Return only JSON. Group dishes into sensible categories "
    "(Starters, Mains, Breads, Desserts, Beverages, or whatever fits the "
    "cuisine). Every dish gets one appetizing sentence of description. "
    "Prices are realistic US delivery-menu prices. Never invent the "
    "restaurant's history, awards, or health claims."
)


class AIServiceError(Exception):
    """User-facing AI failure: the message is safe to show the owner."""

    def __init__(self, message: str, *, not_configured: bool = False):
        super().__init__(message)
        self.not_configured = not_configured


def _require_openai_key() -> str:
    if not settings.openai_api_key:
        raise AIServiceError(
            "AI menu generation is not set up yet. Add an OpenAI API key "
            "to the backend environment to enable it.",
            not_configured=True,
        )
    return settings.openai_api_key


def generate_menu_items(
    *, restaurant_name: str, prompt: str, item_count: int
) -> list[dict]:
    """Ask the LLM for a menu: categories with items (name, description,
    price in cents). Returns the validated item list, unsaved."""
    api_key = _require_openai_key()
    count = max(1, min(item_count, MAX_GENERATED_ITEMS))
    user_prompt = (
        f"Restaurant: {restaurant_name}\n"
        f"Menu brief: {prompt}\n"
        f"Number of items: about {count}\n\n"
        'Return a JSON object with one key, "categories": a list of '
        'objects with "name" and "items". Each item has "name", '
        '"description" (one appetizing sentence), and "price_cents" '
        "(integer, realistic US delivery-menu price in cents). The "
        "item's category is its parent category name. Use realistic dish "
        "names for the brief. Prices must be whole-dollar or "
        "half-dollar amounts."
    )
    try:
        with httpx.Client(timeout=60.0) as client:
            res = client.post(
                f"{OPENAI_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": settings.openai_text_model,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.7,
                    "messages": [
                        {"role": "system", "content": MENU_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
    except httpx.HTTPError:
        raise AIServiceError(
            "The AI service could not be reached. Please try again."
        ) from None
    if res.status_code != 200:
        raise AIServiceError("Menu generation failed. Please try again.")
    try:
        data = res.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, ValueError):
        raise AIServiceError(
            "Menu generation returned something unexpected. Please try again."
        ) from None
    items: list[dict] = []
    for category in parsed.get("categories", []) or []:
        category_name = str(category.get("name", "")).strip() or "Menu"
        for raw in category.get("items", []) or []:
            name = str(raw.get("name", "")).strip()
            if not name:
                continue
            try:
                price = int(raw.get("price_cents", 0))
            except (TypeError, ValueError):
                price = 0
            price = max(0, min(price, MAX_PRICE_CENTS))
            items.append(
                {
                    "name": name[:255],
                    "description": str(raw.get("description", "") or "").strip()[
                        :1000
                    ]
                    or None,
                    "price_cents": price,
                    "category": category_name[:255],
                }
            )
            if len(items) >= count:
                break
        if len(items) >= count:
            break
    if not items:
        raise AIServiceError(
            "Menu generation came back empty. Try a more detailed brief."
        )
    return items


def generate_food_image(*, name: str, description: str | None) -> bytes:
    """Generate one food photo for a menu item. Returns raw image bytes."""
    api_key = _require_openai_key()
    prompt = (
        f"Appetizing overhead food photography of {name}"
        + (f" ({description})" if description else "")
        + ", served on a plate, warm natural light, restaurant menu photo, "
        "no text, no watermark, no people."
    )
    try:
        with httpx.Client(timeout=120.0) as client:
            res = client.post(
                f"{OPENAI_BASE}/images/generations",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": settings.openai_image_model,
                    "prompt": prompt,
                    "size": "1024x1024",
                    "quality": "medium",
                    "n": 1,
                },
            )
    except httpx.HTTPError:
        raise AIServiceError(
            "The image service could not be reached. Please try again."
        ) from None
    if res.status_code != 200:
        raise AIServiceError("Photo generation failed. Please try again.")
    try:
        datum = res.json()["data"][0]
    except (KeyError, IndexError, ValueError):
        raise AIServiceError(
            "Photo generation returned something unexpected. Please try again."
        ) from None
    if datum.get("b64_json"):
        try:
            return base64.b64decode(datum["b64_json"])
        except (ValueError, binascii.Error):
            raise AIServiceError(
                "Photo generation returned something unexpected. Please try again."
            ) from None
    if datum.get("url"):
        try:
            with httpx.Client(timeout=60.0) as client:
                img = client.get(datum["url"])
            img.raise_for_status()
            return img.content
        except httpx.HTTPError:
            raise AIServiceError(
                "Photo generation failed. Please try again."
            ) from None
    raise AIServiceError(
        "Photo generation returned something unexpected. Please try again."
    )


def slugify(value: str) -> str:
    """URL-safe slug for a storage filename."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "dish"


def upload_menu_image(*, image_bytes: bytes, filename: str) -> str:
    """Store a generated photo in Supabase Storage and return its public
    URL. Creates the bucket on first use."""
    if not settings.supabase_url or not settings.supabase_service_key:
        raise AIServiceError(
            "Photo storage is not set up yet. Add the Supabase URL and "
            "service key to the backend environment to enable it.",
            not_configured=True,
        )
    base = settings.supabase_url.rstrip("/")
    bucket = settings.menu_image_bucket
    headers = {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            # Create the public bucket if it does not exist yet; a
            # duplicate-bucket error just means it is already there.
            client.post(
                f"{base}/storage/v1/bucket",
                headers=headers,
                json={"id": bucket, "name": bucket, "public": True},
            )
            path = f"{uuid.uuid4().hex}-{filename}"
            res = client.post(
                f"{base}/storage/v1/object/{bucket}/{path}",
                headers={
                    **headers,
                    "Content-Type": "image/png",
                    "x-upsert": "true",
                },
                content=image_bytes,
            )
    except httpx.HTTPError:
        raise AIServiceError("Photo upload failed. Please try again.") from None
    if res.status_code not in (200, 201):
        raise AIServiceError("Photo upload failed. Please try again.")
    return f"{base}/storage/v1/object/public/{bucket}/{path}"
