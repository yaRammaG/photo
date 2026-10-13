"""遍历 photos/ 目录：每个子目录 = 一个相册，产出文件清单。"""

from __future__ import annotations

import re
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def slugify(name: str) -> str:
    slug = re.sub(r"[^\w-]+", "-", name.strip()).strip("-")
    return slug or "album"


def make_photo_id(stem: str, index: int, seen: set[str]) -> str:
    pid = re.sub(r"[^\w-]+", "_", stem).strip("_") or f"{index:03d}"
    base, n = pid, 2
    while pid in seen:
        pid = f"{base}-{n}"
        n += 1
    seen.add(pid)
    return pid


def scan_albums(photos_dir: Path) -> list[dict]:
    """返回 [{name, slug, title, files: [Path, ...]}]，按目录名排序。"""
    albums = []
    if not photos_dir.is_dir():
        return albums
    for sub in sorted(
        p for p in photos_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ):
        files = sorted(
            f for f in sub.iterdir()
            if f.is_file()
            and f.suffix.lower() in IMAGE_EXTS
            and not f.name.startswith(".")
        )
        if not files:
            continue
        albums.append(
            {"name": sub.name, "slug": slugify(sub.name), "title": sub.name, "files": files}
        )
    return albums
