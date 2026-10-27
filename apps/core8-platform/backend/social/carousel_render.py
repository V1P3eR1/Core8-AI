"""Carousel renderer — 1080×1350 JPEG slides, Hebrew RTL, editable templates.

- Font: Assistant (SIL Open Font License 1.1, bundled in social/fonts/ with
  the licence text). No other fonts, logos or stock assets are used.
- Shaping: Pillow + libraqm (`direction="rtl"`). If raqm is missing the text
  still renders, but complex shaping may be imperfect — the API reports it.
- Templates: `sm_settings.carousel_templates` (user-editable in the dashboard).

Output assets are saved through `media.save_upload` with ownership='rendered'
so they pass the same Instagram spec validation as any upload.
"""

import io
import os

from PIL import Image, ImageDraw, ImageFont, features

from .db import jdump
from .settings import get_setting, set_setting

W, H = 1080, 1350
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Assistant-Variable.ttf")

DEFAULT_TEMPLATES: dict = {
    "default": "core8_dark",
    "templates": {
        "core8_dark": {
            "label": "Core8 כהה",
            "bg": "#0B1220", "bg_accent": "#111C33", "accent": "#4F7CFF",
            "title_color": "#FFFFFF", "body_color": "#C7D2E6", "muted": "#6B7A99",
            "title_size": 84, "body_size": 46, "footer_size": 30,
            "margin": 96, "footer": "core8-ai.com", "show_counter": True,
            "demo_watermark": True,
        },
        "core8_light": {
            "label": "Core8 בהיר",
            "bg": "#F7F8FC", "bg_accent": "#E9EDF7", "accent": "#2F5BFF",
            "title_color": "#0B1220", "body_color": "#334155", "muted": "#8A94A8",
            "title_size": 84, "body_size": 46, "footer_size": 30,
            "margin": 96, "footer": "core8-ai.com", "show_counter": True,
            "demo_watermark": True,
        },
    },
}


def raqm_available() -> bool:
    return bool(features.check("raqm"))


def _font(size: int, weight: int = 600) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(FONT_PATH, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


_GLYPH_FALLBACK = {"→": "<", "←": ">", "⟶": "<", "•": "·", "✓": "V"}


def _safe_text(text: str) -> str:
    """Assistant lacks arrow glyphs; swap them for ASCII that mirrors correctly in RTL."""
    for k, v in _GLYPH_FALLBACK.items():
        text = (text or "").replace(k, v)
    return text


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for para in _safe_text(text or "").split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = words[0]
        for w in words[1:]:
            cand = f"{cur} {w}"
            if font.getlength(cand) <= max_width:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _draw_rtl_block(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, x_right: int,
                    y: int, max_width: int, fill: str, line_gap: float = 1.25) -> int:
    """Draw right-aligned wrapped text; returns the y after the block."""
    kw = {"direction": "rtl"} if raqm_available() else {}
    line_h = int(font.size * line_gap)
    for line in _wrap(text, font, max_width):
        if line:
            draw.text((x_right, y), line, font=font, fill=fill, anchor="ra", **kw)
        y += line_h
    return y


def render_slide(slide: dict, template: dict, index: int, total: int, is_demo: bool = False) -> Image.Image:
    t = {**DEFAULT_TEMPLATES["templates"]["core8_dark"], **(template or {})}
    img = Image.new("RGB", (W, H), t["bg"])
    draw = ImageDraw.Draw(img)
    margin = int(t["margin"])
    # Accent band top-right + soft lower block (pure shapes, no external assets)
    draw.rectangle([W - margin - 160, margin - 24, W - margin, margin - 10], fill=t["accent"])
    draw.rounded_rectangle([margin // 2, H - 360, W - margin // 2, H - margin // 2], radius=36, fill=t["bg_accent"])

    if is_demo and t.get("demo_watermark"):
        draw.text((W // 2, H // 2), "DEMO", font=_font(220, 800), fill=t["bg_accent"], anchor="mm")

    title_font = _font(int(t["title_size"]), 700)
    body_font = _font(int(t["body_size"]), 500)
    footer_font = _font(int(t["footer_size"]), 500)
    max_w = W - 2 * margin

    y = margin + 40
    title = slide.get("title") or ""
    if slide.get("kicker"):
        y = _draw_rtl_block(draw, slide["kicker"], _font(34, 600), W - margin, y, max_w, t["accent"]) + 12
    y = _draw_rtl_block(draw, title, title_font, W - margin, y, max_w, t["title_color"], 1.15) + 36
    if slide.get("body"):
        _draw_rtl_block(draw, slide["body"], body_font, W - margin, y, max_w, t["body_color"], 1.35)

    # Footer
    kw = {"direction": "rtl"} if raqm_available() else {}
    draw.text((W - margin, H - margin - 20), _safe_text(t["footer"]), font=footer_font, fill=t["muted"], anchor="rs", **kw)
    if t.get("show_counter"):
        draw.text((margin, H - margin - 20), f"{index + 1}/{total}", font=footer_font, fill=t["muted"], anchor="ls")
    if index + 1 < total:
        # "swipe" arrow hint (LTR arrow on the left for RTL reading direction)
        ax, ay = margin + 8, H - margin - 84
        draw.polygon([(ax, ay), (ax + 26, ay - 18), (ax + 26, ay + 18)], fill=t["accent"])
        draw.rectangle([ax + 24, ay - 5, ax + 70, ay + 5], fill=t["accent"])
    return img


def to_jpeg_bytes(img: Image.Image, quality: int = 92) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
    return buf.getvalue()


async def get_templates() -> dict:
    return await get_setting("carousel_templates") or DEFAULT_TEMPLATES


async def save_templates(value: dict) -> dict:
    if "templates" not in value or not isinstance(value["templates"], dict) or not value["templates"]:
        raise ValueError("templates חסר")
    if value.get("default") not in value["templates"]:
        value["default"] = next(iter(value["templates"]))
    return await set_setting("carousel_templates", value)


async def resolve_template(name: str | None) -> dict:
    cfg = await get_templates()
    key = name or cfg.get("default")
    return cfg["templates"].get(key) or next(iter(cfg["templates"].values()))


async def preview_slide_bytes(slide: dict, template_name: str | None, index: int = 0, total: int = 1,
                              is_demo: bool = False) -> bytes:
    tpl = await resolve_template(template_name)
    return to_jpeg_bytes(render_slide(slide, tpl, index, total, is_demo), quality=80)


async def render_carousel(item: dict, template_name: str | None = None, actor: str = "user") -> list[dict]:
    """Render every slide of a carousel item into JPEG assets. Returns the assets in order."""
    from .media import save_upload
    pkg = item.get("package") or {}
    slides = pkg.get("slides") or []
    if not (2 <= len(slides) <= 20):
        raise ValueError("קרוסלה דורשת 2–20 שקופיות")
    tpl = await resolve_template(template_name or pkg.get("template"))
    assets = []
    for i, s in enumerate(slides):
        data = to_jpeg_bytes(render_slide(s, tpl, i, len(slides), bool(item.get("is_demo"))))
        a = await save_upload(data, f"carousel-{item['id'][:8]}-{i + 1}.jpg", "image/jpeg",
                             ownership="rendered", permission_note="נוצר על-ידי המערכת מטקסט של הבעלים; גופן Assistant (OFL)",
                             is_demo=1 if item.get("is_demo") else 0, alt_text=(s.get("title") or "")[:1000],
                             brief=jdump({"slide": i + 1, "template": template_name or pkg.get("template")}))
        assets.append(a)
    return assets


DEFAULT_TEMPLATES_SETTING_KEY = "carousel_templates"
