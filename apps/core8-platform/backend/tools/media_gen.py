"""Post-media pipeline — the media library and Gemini image generation.

Media files live in backend/media/<tenant_id>/ (served by FastAPI in dev, nginx in
prod) and are tracked in the media_assets table; `filename` holds the path relative to
media/. Files are public by URL because Instagram must fetch them; names are random UUIDs. Both uploaded and generated assets
produce a media_url that queue_post can publish.

Generated images use Imagen via the Gemini API and are written as JPEG —
Instagram's publish API accepts JPEG for image posts.
"""

import os
import re
import uuid

import aiosqlite

from config import cfg
from database import get_db
from tenancy import current_tenant
from tools.registry import ToolDef, registry

MEDIA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

_SAFE_TENANT = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

IMAGEN_MODEL = "imagen-4.0-generate-001"
_VALID_ASPECT = {"1:1", "3:4", "4:3", "9:16", "16:9"}


def _public_url(filename: str) -> str:
    return f"{cfg.media_base_url.rstrip('/')}/{filename}"


async def save_media_asset(data: bytes, ext: str, source: str, media_type: str,
                           prompt: str = "", plan_id: str = "") -> dict:
    """Write a media file to MEDIA_DIR/<tenant_id>/ and record it in media_assets."""
    tenant_id = current_tenant()
    if not _SAFE_TENANT.match(tenant_id):
        raise ValueError("unsafe tenant id for a media path")
    asset_id = str(uuid.uuid4())
    filename = f"{tenant_id}/{asset_id}.{ext.lstrip('.')}"
    os.makedirs(os.path.join(MEDIA_DIR, tenant_id), exist_ok=True)
    with open(os.path.join(MEDIA_DIR, filename), "wb") as f:
        f.write(data)
    async with get_db() as db:
        await db.execute(
            """INSERT INTO media_assets
                   (tenant_id, id, filename, source, media_type, prompt, plan_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tenant_id, asset_id, filename, source, media_type, prompt, plan_id or None),
        )
        await db.commit()
    return {"id": asset_id, "filename": filename, "media_type": media_type,
            "url": _public_url(filename)}


async def generate_post_image(prompt: str, aspect_ratio: str = "1:1",
                              plan_id: str = "") -> dict:
    """Generate a post image with Imagen and store it in the media library."""
    if not cfg.gemini_api_key:
        return {"error": "GEMINI_API_KEY is not set — image generation is unavailable."}
    if not prompt.strip():
        return {"error": "prompt is required."}
    if aspect_ratio not in _VALID_ASPECT:
        return {"error": f"Invalid aspect_ratio '{aspect_ratio}'. "
                         f"Valid: {sorted(_VALID_ASPECT)}"}
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=cfg.gemini_api_key)
        resp = await client.aio.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
                output_mime_type="image/jpeg",
            ),
        )
    except Exception as e:
        return {"error": f"Gemini image generation failed: {e}"}
    if not resp.generated_images:
        return {"error": "Gemini returned no image — the prompt may have been filtered."}
    image_bytes = resp.generated_images[0].image.image_bytes
    asset = await save_media_asset(image_bytes, "jpg", "generated", "image",
                                   prompt=prompt, plan_id=plan_id)
    asset["bytes"] = len(image_bytes)
    return asset


async def list_media_assets(source: str = "", limit: int = 50) -> list[dict]:
    cols = "id, filename, source, media_type, prompt, created_at"
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        if source:
            query = (f"SELECT {cols} FROM media_assets WHERE tenant_id=? AND source=? "
                     "ORDER BY created_at DESC LIMIT ?")
            args = (current_tenant(), source, min(limit, 200))
        else:
            query = (f"SELECT {cols} FROM media_assets WHERE tenant_id=? "
                     "ORDER BY created_at DESC LIMIT ?")
            args = (current_tenant(), min(limit, 200))
        async with db.execute(query, args) as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["url"] = _public_url(d["filename"])
        result.append(d)
    return result


def register_media_tools():
    registry.register(ToolDef(
        name="generate_post_image",
        description=(
            "Generate a post image with Gemini (Imagen) from a text prompt. "
            "aspect_ratio: 1:1 (feed), 9:16 (reel/story), 4:3, 3:4, or 16:9. "
            "Returns a media_url usable directly by queue_post."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "prompt":       {"type": "string", "description": "What the image should show"},
                "aspect_ratio": {"type": "string", "description": "1:1 | 9:16 | 4:3 | 3:4 | 16:9 (default 1:1)"},
                "plan_id":      {"type": "string", "description": "Originating content plan id (optional)"},
            },
            "required": ["prompt"],
        },
        handler=generate_post_image,
    ))
    registry.register(ToolDef(
        name="list_media_assets",
        description="List media in the library (uploaded and generated), newest "
                    "first. Optionally filter by source: upload | generated.",
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "upload | generated (optional)"},
                "limit":  {"type": "integer", "description": "Max results (default 50)"},
            },
        },
        handler=list_media_assets,
    ))
