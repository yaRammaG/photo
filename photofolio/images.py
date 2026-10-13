"""Pillow 图片管线：多尺寸 WebP、full JPG、LQIP、EXIF 提取。"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

THUMB_WIDTH = 600
DISPLAY_WIDTH = 1600
LQIP_WIDTH = 16
QR_MAX_WIDTH = 800

# EXIF tag：IFD0
TAG_MAKE = 271
TAG_MODEL = 272
TAG_ORIENTATION = 274
# EXIF tag：Exif IFD
TAG_EXIF_IFD = 0x8769
TAG_EXPOSURE = 33434
TAG_FNUMBER = 33437
TAG_ISO = 34855
TAG_FOCAL = 37386
TAG_LENS = 42036


def _rat(value) -> float | None:
    """EXIF 数值统一转 float：支持 int/float/IFDRational/(num, den) 元组。"""
    if isinstance(value, (tuple, list)):
        if len(value) == 2:
            try:
                num, den = float(value[0]), float(value[1])
            except (TypeError, ValueError):
                return None
            return num / den if den else None
        if len(value) == 1:
            value = value[0]
        else:
            return None
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _fmt_exposure(value) -> str:
    v = _rat(value)
    if not v or v <= 0:
        return ""
    if v >= 1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return f"1/{round(1 / v)}"


def _fmt_fnumber(value) -> str:
    v = _rat(value)
    return f"f/{v:.1f}" if v else ""


def _fmt_focal(value) -> str:
    v = _rat(value)
    return f"{round(v)}mm" if v else ""


def extract_exif(exif) -> dict:
    try:
        exif_ifd = exif.get_ifd(TAG_EXIF_IFD)
    except Exception:
        exif_ifd = {}

    def pick(tag):
        v = exif.get(tag)
        if v in (None, ""):
            v = exif_ifd.get(tag)
        return v

    camera = " ".join(
        str(x).strip() for x in (pick(TAG_MAKE), pick(TAG_MODEL)) if x
    ).strip()

    iso = pick(TAG_ISO)
    if isinstance(iso, (tuple, list)):
        iso = iso[0] if iso else ""
    try:
        iso = int(iso)
    except (TypeError, ValueError):
        iso = ""

    lens = pick(TAG_LENS)
    focal = _fmt_focal(pick(TAG_FOCAL))
    aperture = _fmt_fnumber(pick(TAG_FNUMBER))
    shutter = _fmt_exposure(pick(TAG_EXPOSURE))

    parts = []
    if camera:
        parts.append(camera)
    seg = " ".join(x for x in (focal, aperture) if x)
    if seg:
        parts.append(seg)
    if shutter:
        parts.append(f"{shutter}s")
    if iso:
        parts.append(f"ISO {iso}")

    return {
        "camera": camera,
        "lens": str(lens).strip() if lens else "",
        "focal": focal,
        "aperture": aperture,
        "shutter": shutter,
        "iso": iso,
        "line": " · ".join(parts),
    }


def _make_lqip(img: Image.Image) -> str:
    small = img.copy()
    small.thumbnail((LQIP_WIDTH, LQIP_WIDTH * 4), Image.Resampling.LANCZOS)
    small = small.filter(ImageFilter.GaussianBlur(1.5))
    buf = io.BytesIO()
    small.save(buf, "WEBP", quality=40, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def process_photo(src: Path, out_dir: Path, photo_id: str) -> dict:
    """处理单张照片，输出 600/1600 WebP + full JPG，返回 gallery.json 记录。"""
    with Image.open(src) as im:
        exif = im.getexif()
        # 方向修正（按 EXIF orientation 旋转像素）
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        orig_w, orig_h = im.size

        # 缩略图 600（原片更窄则保持原尺寸，不放大）
        thumb_w = min(orig_w, THUMB_WIDTH)
        thumb_h = max(1, round(orig_h * thumb_w / orig_w))
        thumb = im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        thumb.save(out_dir / f"{photo_id}-600.webp", "WEBP", quality=82, method=6)

        # 展示图 1600（超宽不放大，窄于 1600 时复用 600 档）
        if orig_w > DISPLAY_WIDTH:
            disp_w = DISPLAY_WIDTH
            disp_h = max(1, round(orig_h * disp_w / orig_w))
            display = im.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
            display.save(
                out_dir / f"{photo_id}-1600.webp", "WEBP", quality=82, method=6
            )
            display_name = f"{photo_id}-1600.webp"
        else:
            disp_w, disp_h, display_name = thumb_w, thumb_h, f"{photo_id}-600.webp"

        # full：转 JPG（已做方向修正）
        im.save(out_dir / f"{photo_id}-full.jpg", "JPEG", quality=92, optimize=True)

        lqip = _make_lqip(im)
        exif_data = extract_exif(exif)

    return {
        "id": photo_id,
        "title": "",
        "thumb": f"img/{photo_id}-600.webp",
        "display": f"img/{display_name}",
        "full": f"img/{photo_id}-full.jpg",
        "lqip": lqip,
        "width": disp_w,
        "height": disp_h,
        "orientation": "landscape" if disp_w >= disp_h else "portrait",
        "exif": exif_data,
    }


def process_qr(src: Path, out_path: Path) -> dict:
    """处理二维码：白底合成 + 无损 PNG（保证扫码清晰），过大时等比缩小。"""
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA"):
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(bg, im.convert("RGBA"))
        if im.mode != "RGB":
            im = im.convert("RGB")
        if im.width > QR_MAX_WIDTH:
            im = im.resize(
                (QR_MAX_WIDTH, max(1, round(im.height * QR_MAX_WIDTH / im.width))),
                Image.Resampling.LANCZOS,
            )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        im.save(out_path, "PNG", optimize=True)
        w, h = im.size
    return {"width": w, "height": h}
