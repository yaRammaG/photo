"""ghp-import 封装：构建产物推送 gh-pages 分支。"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path


def ghp_push(root: Path, dist: Path | None = None) -> None:
    """把 dist/ 推送到 origin 的 gh-pages 分支（自动 build 由调用方负责）。"""
    dist = dist or root / "dist"
    msg = f"publish {date.today().isoformat()}"
    cmd = [sys.executable, "-m", "ghp_import", "-n", "-p", "-f", "-m", msg, str(dist)]
    try:
        subprocess.run(cmd, cwd=root, check=True)
    except FileNotFoundError as e:
        raise RuntimeError("ghp-import 未安装，请重新执行 pip install -e .") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            "ghp-import 推送失败：请确认当前目录是 git 仓库、"
            "已添加 origin 远程（git remote add origin ...）且账号有推送权限"
        ) from e


def pages_url(root: Path, custom_domain: str | None = None) -> str | None:
    """尽力推断 Pages 访问地址：自定义域名优先，否则解析 origin 远程。"""
    if custom_domain:
        return f"https://{str(custom_domain).strip()}"
    try:
        url = subprocess.run(
            ["git", "config", "remote.origin.url"],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout.strip()
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?/?$", url)
        if m:
            parts = m.group(1).split("/")
            if len(parts) == 2 and parts[1]:
                return f"https://{parts[0]}.github.io/{parts[1]}/"
    except Exception:
        pass
    return None
