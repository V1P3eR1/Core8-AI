"""Media upload — POST /api/instagram/media (multipart).

Accepts an image or video file, stores it in the media library, and returns a
media_url that queue_post can publish. JWT-protected: only an operator uploads.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from security.jwt_auth import require_jwt
from tools.media_gen import save_media_asset

logger = logging.getLogger("core8.media")

router = APIRouter()

# extension -> (media_type, ...)
_EXT_TYPE = {
    "jpg": "image", "jpeg": "image", "png": "image",
    "mp4": "video", "mov": "video",
}
_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/api/instagram/media", dependencies=[Depends(require_jwt)])
async def upload_media(file: UploadFile = File(...)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in _EXT_TYPE:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: {sorted(_EXT_TYPE)}",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 50 MB).")
    asset = await save_media_asset(data, ext, "upload", _EXT_TYPE[ext])
    logger.info("Media uploaded: %s (%d bytes)", asset["filename"], len(data))
    return asset
