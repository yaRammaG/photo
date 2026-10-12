"""photofolio 命令行入口：init / build / serve / publish。"""

from __future__ import annotations

import shutil
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import click
import yaml

from .images import process_photo
from .render import render_site
from .scanner import make_photo_id, scan_albums

DEFAULT_CONFIG = """\
# photofolio 站点配置
title: "My Photofolio"        # 站点标题
author: "Your Name"           # 作者名
about: |                      # About 页文字
  在这里写下你的简介……
social:
  github: ""                  # 如 https://github.com/xxx
  instagram: ""               # 如 https://instagram.com/xxx
  email: ""                   # 如 me@example.com
hero_photo: ""                # 首页主图，如 photos/street/001.jpg
custom_domain: ""             # 自定义域名，如 photo.example.com（留空则用 github.io）
"""

DEPLOY_WORKFLOW = """\
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install photofolio
        run: pip install .

      - name: Build site
        run: photofolio build

      - name: Publish to gh-pages
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          ghp-import -n -p -f -m "publish $(date -u +%F)" dist
"""


def load_config(root: Path) -> dict:
    cfg_file = root / "config.yaml"
    config = {}
    if cfg_file.exists():
        config = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
    config.setdefault("title", "Photofolio")
    config.setdefault("author", "")
    config.setdefault("social", {})
    return config


@click.group()
def cli():
    """photofolio — 静态摄影作品图库生成器。"""


@cli.command()
def init():
    """初始化项目：生成 config.yaml、photos/ 与 CI workflow。"""
    root = Path.cwd()
    cfg = root / "config.yaml"
    if cfg.exists():
        click.echo("config.yaml 已存在，跳过")
    else:
        cfg.write_text(DEFAULT_CONFIG, encoding="utf-8")
        click.echo("已生成 config.yaml")
    (root / "photos").mkdir(exist_ok=True)

    workflow = root / ".github" / "workflows" / "deploy.yml"
    if workflow.exists():
        click.echo(".github/workflows/deploy.yml 已存在，跳过")
    else:
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text(DEPLOY_WORKFLOW, encoding="utf-8")
        click.echo("已生成 .github/workflows/deploy.yml")

    gi = root / ".gitignore"
    lines = ["dist/", ".venv/", "__pycache__/", "*.egg-info/"]
    if gi.exists():
        existing = gi.read_text(encoding="utf-8").splitlines()
        missing = [x for x in lines if x not in existing]
        if missing:
            gi.write_text(
                gi.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(missing) + "\n",
                encoding="utf-8",
            )
    else:
        gi.write_text("\n".join(lines) + "\n", encoding="utf-8")

    click.echo("下一步：把照片放进 photos/<相册名>/，然后运行 photofolio build")


def build_site(root: Path) -> tuple[int, int, float]:
    """构建 dist/，返回 (相册数, 照片数, 用时秒)。"""
    config = load_config(root)
    photos_dir = root / "photos"
    albums = scan_albums(photos_dir)
    if not albums:
        raise click.ClickException(
            f"{photos_dir} 下没有找到相册（每个子目录 = 一个相册）"
        )

    dist = root / "dist"
    if dist.exists():
        shutil.rmtree(dist)

    started = time.time()
    total = 0
    for album in albums:
        img_dir = dist / "albums" / album["slug"] / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        seen: set[str] = set()
        photos = []
        for i, src in enumerate(album["files"]):
            pid = make_photo_id(src.stem, i, seen)
            photos.append(process_photo(src, img_dir, pid))
        album["photos"] = photos
        album["count"] = len(photos)
        total += len(photos)
        click.echo(f"  [{album['name']}] {len(photos)} 张")

    if config.get("custom_domain"):
        dist.joinpath("CNAME").write_text(
            str(config["custom_domain"]).strip() + "\n", encoding="utf-8"
        )

    render_site(
        dist,
        config,
        albums,
        hero=resolve_hero(root, config, albums),
        about_photo=process_about_photo(photos_dir, dist),
    )
    return len(albums), total, time.time() - started


@cli.command()
def build():
    """处理 photos/ 并生成静态站点到 dist/。"""
    n_albums, total, elapsed = build_site(Path.cwd())
    click.echo(
        f"完成：{n_albums} 个相册 / {total} 张照片，用时 {elapsed:.1f}s -> dist/"
    )


def resolve_hero(root: Path, config: dict, albums: list[dict]) -> dict | None:
    """解析首页主图：config.hero_photo 优先，否则第一个相册第一张。"""
    want = config.get("hero_photo")
    want_path = (root / want).resolve() if want else None
    for album in albums:
        for i, f in enumerate(album["files"]):
            if want_path and f.resolve() == want_path:
                return {"slug": album["slug"], **album["photos"][i]}
    if albums and albums[0]["photos"]:
        return {"slug": albums[0]["slug"], **albums[0]["photos"][0]}
    return None


def process_about_photo(photos_dir: Path, dist: Path) -> dict | None:
    """处理 photos/about.jpg（走同一图片管线），无则返回 None。"""
    src = None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = photos_dir / f"about{ext}"
        if p.is_file():
            src = p
            break
    if src is None:
        return None
    out_dir = dist / "about" / "img"
    out_dir.mkdir(parents=True, exist_ok=True)
    return process_photo(src, out_dir, "about")


@cli.command()
@click.option("--port", default=8000, show_default=True, type=int)
def serve(port):
    """本地静态服务器预览 dist/。"""
    dist = Path.cwd() / "dist"
    if not (dist / "index.html").exists():
        raise click.ClickException("dist/index.html 不存在，请先运行 photofolio build")
    handler = partial(SimpleHTTPRequestHandler, directory=str(dist))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        click.echo(f"预览地址：http://127.0.0.1:{port}/ （Ctrl+C 退出）")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


@cli.command()
def publish():
    """构建并发布到 GitHub Pages（gh-pages 分支）。"""
    from .publish import ghp_push, pages_url

    root = Path.cwd()
    if not (root / "photos").is_dir():
        raise click.ClickException("当前目录不是 photofolio 项目（缺少 photos/）")

    click.echo("1/2 构建站点...")
    n_albums, total, elapsed = build_site(root)
    click.echo(f"  {n_albums} 个相册 / {total} 张照片，用时 {elapsed:.1f}s")

    config = load_config(root)
    click.echo("2/2 推送 gh-pages 分支...")
    try:
        ghp_push(root)
    except RuntimeError as e:
        raise click.ClickException(str(e)) from None

    url = pages_url(root, config.get("custom_domain"))
    if url:
        click.echo(f"发布完成，稍后可访问：{url}")
    else:
        click.echo("发布完成")
    click.echo("首次部署需在仓库 Settings -> Pages 中选择 gh-pages 分支")


if __name__ == "__main__":
    cli()
