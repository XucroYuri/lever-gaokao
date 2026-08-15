#!/usr/bin/env python3
"""立维志愿数据更新：从 GitHub Releases 拉取最新数据包并校验。

数据发布 workflow（data-update.yml）会把数据包发布为 data-{version} Release，
本脚本从 Releases 拉取最新数据包（version.json + SHA256SUMS，可选 gaokao.duckdb），
校验 SHA256 后放置到本地 data 目录。

用法：
    # 检查最新数据包版本（不下载）
    python scripts/data_update.py check

    # 下载并应用最新数据包（校验后放入 data/）
    python scripts/data_update.py update [--data-dir data] [--repo XucroYuri/lever-gaokao]

说明：数据本体（duckdb）可能未随 Release 分发（体积大）；若 Release 无 duckdb，
脚本会提示用本地采集（data_collect.py）补齐。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

GITHUB_API = "https://api.github.com"
DEFAULT_REPO = "XucroYuri/lever-gaokao"


def _get(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={
        "User-Agent": "liwei-zhiyuan-data-update",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "liwei-zhiyuan-data-update"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())


def latest_data_release(repo: str) -> dict | None:
    """找最新的 data-* Release。"""
    releases = _get(f"{GITHUB_API}/repos/{repo}/releases?per_page=10")
    if not isinstance(releases, list):
        return None
    data_releases = [r for r in releases if r.get("tag_name", "").startswith("data-")]
    return data_releases[0] if data_releases else None


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_check(args: argparse.Namespace) -> None:
    release = latest_data_release(args.repo)
    if not release:
        print("未找到 data-* Release（数据包尚未发布）")
        return
    print(f"最新数据包: {release['tag_name']}（{release['published_at'][:10]}）")
    for asset in release.get("assets", []):
        print(f"  {asset['name']}  ({asset['size'] // 1024}KB)")


def cmd_update(args: argparse.Namespace) -> None:
    release = latest_data_release(args.repo)
    if not release:
        print("未找到 data-* Release（数据包尚未发布）")
        sys.exit(1)

    tag = release["tag_name"]
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # 下载全部资产
        files: dict[str, Path] = {}
        for asset in release.get("assets", []):
            name = asset["name"]
            dest = tmp_dir / name
            print(f"下载 {name} ...")
            _download(asset["browser_download_url"], dest)
            files[name] = dest

        # 校验 SHA256（若有 SHA256SUMS）
        sums_path = files.get("SHA256SUMS.txt")
        if sums_path:
            sums: dict[str, str] = {}
            for line in sums_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    sums[parts[1]] = parts[0]
            ok = True
            for name, path in files.items():
                if name in sums and sha256_of(path) != sums[name]:
                    print(f"  ❌ {name} SHA256 校验失败")
                    ok = False
            if not ok:
                print("校验失败，未应用")
                sys.exit(1)
            print("  ✅ SHA256 校验通过")

        # 应用到 data 目录
        for name, path in files.items():
            if name == "SHA256SUMS.txt":
                continue
            dest = data_dir / name
            if path.exists():
                import shutil
                shutil.copy2(path, dest)
                print(f"  已应用 {name} -> {data_dir}")

    print(f"数据包 {tag} 应用完成（数据目录 {data_dir}）")
    print("提示：若数据包不含 gaokao.duckdb，请用 data_collect.py 本地采集官方数据补齐。")

    # 校验版本文件
    ver = data_dir / "version.json"
    if ver.exists():
        try:
            v = json.loads(ver.read_text(encoding="utf-8"))
            print(f"当前数据版本: {v.get('data_version')}")
            if v.get("coverage_gaps"):
                for k, gaps in v["coverage_gaps"].items():
                    print(f"  缺口: {k} 缺 {len(gaps)} 省")
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="立维志愿数据更新")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="检查最新数据包版本")
    p_check.add_argument("--repo", default=DEFAULT_REPO)
    p_check.set_defaults(func=cmd_check)

    p_update = sub.add_parser("update", help="下载并应用最新数据包")
    p_update.add_argument("--repo", default=DEFAULT_REPO)
    p_update.add_argument("--data-dir", default="data")
    p_update.set_defaults(func=cmd_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
