"""Jinja2 渲染：包内模板 → dist/（首页 / 相册页 / About 页）。"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
    )


def render_site(
    dist: Path,
    site: dict,
    albums: list[dict],
    hero: dict | None = None,
    about_photo: dict | None = None,
    qr_photo: dict | None = None,
) -> None:
    env = _env()
    year = datetime.now().year
    dist.mkdir(parents=True, exist_ok=True)

    # 每个相册的 gallery.json（图片路径相对相册目录）
    for album in albums:
        album_dir = dist / "albums" / album["slug"]
        album_dir.mkdir(parents=True, exist_ok=True)
        payload = {"title": album["title"], "photos": album["photos"]}
        (album_dir / "gallery.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # 首页（精选）
    (dist / "index.html").write_text(
        env.get_template("index.html").render(
            site=site, albums=albums, hero=hero, qr=qr_photo, rel=".", year=year
        ),
        encoding="utf-8",
    )

    # 相册页
    for i, album in enumerate(albums):
        nxt = albums[(i + 1) % len(albums)] if len(albums) > 1 else None
        page = dist / "albums" / album["slug"] / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            env.get_template("album.html").render(
                site=site, album=album, next_album=nxt, qr=qr_photo,
                rel="../..", year=year,
            ),
            encoding="utf-8",
        )

    # About 页
    about_page = dist / "about" / "index.html"
    about_page.parent.mkdir(parents=True, exist_ok=True)
    about_page.write_text(
        env.get_template("about.html").render(
            site=site, about_photo=about_photo, qr=qr_photo, rel="..", year=year
        ),
        encoding="utf-8",
    )

    shutil.copytree(TEMPLATES_DIR / "static", dist / "static", dirs_exist_ok=True)
