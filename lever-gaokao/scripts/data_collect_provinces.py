#!/usr/bin/env python3
"""Gaokao 数据层 v1：PDF 类省份官方源采集（北京/辽宁/贵州等）。

部分省份的一分一段以 PDF 发布（含文本层），pypdf 可直接提取。实测北京 2026
考生分数分布 PDF：表头与数据行完全干净（仅标题个别字乱码，不影响解析），
313 行，单调性 0 违反。

用法：
    python scripts/data_collect_provinces.py collect --province beijing --year 2026
"""

from __future__ import annotations

import argparse
import hashlib
import re
import urllib.parse
import urllib.request
from pathlib import Path

import duckdb

# 各省一分一段发布页（按年份）
PROVINCE_PAGES: dict[str, dict[int, str]] = {
    "beijing": {
        2026: "https://www.bjeea.cn/html/gkgz/tzgg/2026/0624/88238.html",
    },
}

# 辽宁一分一段 PDF（物理/历史分卷，官方直链）
LIAONING_YIFENYIDUAN_PDFS: dict[int, dict[str, str]] = {
    2026: {
        "物理": "https://www.lnzsks.com/lnzkbfiles/2026/lns2026gkcjtjb0624clhptll01.pdf",
        "历史": "https://www.lnzsks.com/lnzkbfiles/2026/lns2026gkcjtjb0624clhptlw02.pdf",
    },
}

# 贵州一分一段 PDF（物理/历史分卷，相对发布页目录的路径）
GUIZHOU_YIFENYIDUAN_PDFS: dict[int, dict[str, str]] = {
    2026: {
        "物理": "http://zsksy.guizhou.gov.cn/tzgg/202606/P020260625601945906859.pdf",
        "历史": "http://zsksy.guizhou.gov.cn/tzgg/202606/P020260625601945966806.pdf",
    },
}

# 官方原文目录（提交到仓库，供人工校验原文对照）
OFFICIAL_SOURCES = Path("official-sources")


def _download(url: str, dest: Path, timeout: int = 90) -> None:
    # 对 URL 做百分号编码（中文文件名等非 ASCII 字符），保留已有转义与路径/查询分隔符
    url = urllib.parse.quote(url, safe="/:?&=%.~-+")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (lever-gaokao)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dest.write_bytes(resp.read())


def _extract_pdf_url(html: str, include: str, exclude: str = "") -> str | None:
    """从发布页提取包含 include（且不含 exclude）的 PDF 相对路径。"""
    for href in re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.I):
        if include in href and exclude not in href:
            return href
    return None


def _to_int(v) -> int | None:
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _parse_score_distribution_pdf(path: Path) -> list[dict]:
    """解析一分一段 PDF（分数/人数/累计）。

    兼容：累计列千分位逗号（"137,508"）、首行"692分以上"后缀、每页重复表头、
    行尾可能存在的乱码字符。单调性护栏：累计数随分数递减必须递增，违反则跳过。
    """
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    all_text = "\n".join((p.extract_text() or "") for p in reader.pages)
    rows: list[dict] = []
    prev_cum: int | None = None
    for line in all_text.splitlines():
        line = line.strip()
        # 分数(2-3位) + 人数 + 累计（可含逗号千分位）
        m = re.match(r"^(\d{2,3})\D*(\d+)\s+([\d,]+)\s*", line)
        if not m:
            continue
        score = int(m.group(1))
        segment = int(m.group(2))
        cum = int(m.group(3).replace(",", ""))
        if prev_cum is not None and cum < prev_cum:
            continue  # 累计不增，疑似误匹配（页脚/汇总行）
        prev_cum = cum
        rows.append({"score": score, "segment_count": segment, "cumulative_count": cum})
    return rows


def collect_beijing(data_dir: Path, year: int, page_url: str) -> None:
    """采集北京一分一段（考生分数分布 PDF），入 score_range。

    PDF 原文保存到仓库 official-sources/（供人工校验原文对照）；
    入库数据 verified=False，人工对照原文核验通过后才标记 True。
    """
    work_dir = data_dir / "official" / "beijing" / str(year)
    work_dir.mkdir(parents=True, exist_ok=True)
    src_dir = OFFICIAL_SOURCES / "yifenyiduan" / "beijing" / str(year)
    src_dir.mkdir(parents=True, exist_ok=True)

    page_path = work_dir / "page.html"
    print(f"抓取 {page_url}")
    _download(page_url, page_path)
    html = page_path.read_text(encoding="utf-8", errors="ignore")

    pdf_rel = _extract_pdf_url(html, include="考生分数分布", exclude="单考")
    if pdf_rel is None:
        raise SystemExit("未找到高考考生分数分布 PDF")
    pdf_url = pdf_rel if pdf_rel.startswith("http") else "https://www.bjeea.cn" + pdf_rel
    pdf_path = src_dir / "yifenyiduan.pdf"  # 原文存仓库
    print(f"下载附件 {pdf_url} -> {pdf_path}")
    _download(pdf_url, pdf_path)

    rows = _parse_score_distribution_pdf(pdf_path)
    if not rows:
        raise SystemExit("PDF 未解析出数据行（可能是扫描件/无文本层）")
    print(f"解析出一分一段 {len(rows)} 行（{year} 北京）")

    db_path = data_dir / "gaokao.duckdb"
    sid = hashlib.sha256(pdf_url.encode("utf-8")).hexdigest()[:16]
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            "DELETE FROM score_range WHERE province = ? AND year = ? AND source_id = ?",
            ["北京", year, sid],
        )
        for r in rows:
            con.execute(
                "INSERT INTO score_range (province, year, category, score, segment_count, cumulative_count, source_id) "
                "VALUES (?,?,?,?,?,?,?)",
                ["北京", year, "综合", r["score"], r["segment_count"], r["cumulative_count"], sid],
            )
        con.execute("DELETE FROM source_ledger WHERE source_id = ?", [sid])
        con.execute(
            "INSERT INTO source_ledger VALUES (?,?,?,?,?,?,?,?,?)",
            [sid, f"北京教育考试院 {year} 考生分数分布", "当年官方",
             pdf_url, "官方公开", "北京", year, "score_range", False],
        )
        total = con.execute(
            "SELECT COUNT(*) FROM score_range WHERE province = ? AND year = ? AND source_id = ?",
            ["北京", year, sid],
        ).fetchone()[0]
    print(f"  已入库 -> {db_path} / score_range（{total} 行，北京 {year}）")
    print(f"  verified=False（待人工对照 official-sources/yifenyiduan/beijing/{year}/yifenyiduan.pdf 原文核验）")


def _store_yifenyiduan_multi(data_dir: Path, province: str, year: int,
                             rows_by_cat: dict[str, list[dict]],
                             sources: dict[str, tuple[str, str]]) -> None:
    """把多科类一分一段入 score_range（每科类独立 source_id，verified=False 待人工核验）。

    rows_by_cat: {科类: [row,...]}；sources: {科类: (来源URL, 归档文件名)}
    """
    db_path = data_dir / "gaokao.duckdb"
    with duckdb.connect(str(db_path)) as con:
        for cat, rows in rows_by_cat.items():
            url, _ = sources[cat]
            sid = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            con.execute(
                "DELETE FROM score_range WHERE province = ? AND year = ? AND category = ? AND source_id = ?",
                [province, year, cat, sid],
            )
            for r in rows:
                con.execute(
                    "INSERT INTO score_range (province, year, category, score, segment_count, cumulative_count, source_id) "
                    "VALUES (?,?,?,?,?,?,?)",
                    [province, year, cat, r["score"], r["segment_count"], r["cumulative_count"], sid],
                )
            con.execute("DELETE FROM source_ledger WHERE source_id = ?", [sid])
            con.execute(
                "INSERT INTO source_ledger VALUES (?,?,?,?,?,?,?,?,?)",
                [sid, f"{province}教育考试院 {year} {cat}类一分一段", "当年官方",
                 url, "官方公开", province, year, "score_range", False],
            )
    print(f"  已入库 -> {db_path} / score_range（{province} {year}，verified=False 待人工核验）")


def collect_liaoning(data_dir: Path, year: int) -> None:
    """采集辽宁一分一段（物理/历史双 PDF，官方直链），原文归档 + verified=False。"""
    pdfs = LIAONING_YIFENYIDUAN_PDFS[year]
    rows_by_cat: dict[str, list[dict]] = {}
    sources: dict[str, tuple[str, str]] = {}
    for cat, url in pdfs.items():
        fname = "wuli.pdf" if cat == "物理" else "lishi.pdf"
        pdf_path = OFFICIAL_SOURCES / "yifenyiduan" / "liaoning" / str(year) / fname
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"下载 {cat}类 PDF: {url}")
        _download(url, pdf_path)
        rows = _parse_score_distribution_pdf(pdf_path)
        print(f"  {cat}类: {len(rows)} 行（累计至 {rows[-1]['cumulative_count'] if rows else 0}）")
        rows_by_cat[cat] = rows
        sources[cat] = (url, fname)
    _store_yifenyiduan_multi(data_dir, "辽宁", year, rows_by_cat, sources)


def _parse_guizhou_pdf(path: Path) -> list[dict]:
    """解析贵州宽表格式一分一段 PDF。

    贵州格式为转置宽表：'分数 691及以上 690 ... 0'（每块 20 分，有分数才列出），
    随后 本段人数/累计人数/累计比例% 标签与 3N 个数字（每分 本段/累计/比例 三元组）。
    """
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    all_text = "\n".join((p.extract_text() or "") for p in reader.pages)
    lines = all_text.splitlines()
    rows: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("分数"):
            scores: list[int] = []
            for part in line[2:].split():
                part = part.replace("及以上", "").replace("及以下", "")
                if part.isdigit():
                    scores.append(int(part))
            if not scores:
                i += 1
                continue
            nums: list[float] = []
            j = i + 1
            while j < len(lines) and len(nums) < 3 * len(scores):
                for tok in lines[j].split():
                    if re.fullmatch(r"\d+(\.\d+)?", tok):
                        nums.append(float(tok))
                j += 1
            for k, score in enumerate(scores):
                if 3 * k + 1 < len(nums):
                    rows.append({
                        "score": score,
                        "segment_count": int(nums[3 * k]),
                        "cumulative_count": int(nums[3 * k + 1]),
                    })
            i = j
        else:
            i += 1
    return rows


def collect_guizhou(data_dir: Path, year: int) -> None:
    """采集贵州一分一段（物理/历史双 PDF，宽表格式），原文归档 + verified=False。"""
    pdfs = GUIZHOU_YIFENYIDUAN_PDFS[year]
    rows_by_cat: dict[str, list[dict]] = {}
    sources: dict[str, tuple[str, str]] = {}
    for cat, url in pdfs.items():
        fname = "wuli.pdf" if cat == "物理" else "lishi.pdf"
        pdf_path = OFFICIAL_SOURCES / "yifenyiduan" / "guizhou" / str(year) / fname
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"下载 {cat}类 PDF: {url}")
        _download(url, pdf_path)
        rows = _parse_guizhou_pdf(pdf_path)
        print(f"  {cat}类: {len(rows)} 行（累计至 {rows[-1]['cumulative_count'] if rows else 0}）")
        rows_by_cat[cat] = rows
        sources[cat] = (url, fname)
    _store_yifenyiduan_multi(data_dir, "贵州", year, rows_by_cat, sources)


def collect_cmd(args: argparse.Namespace) -> None:
    province = args.province
    year = args.year
    data_dir = Path(args.data_dir)

    if province == "liaoning":
        if year not in LIAONING_YIFENYIDUAN_PDFS:
            raise SystemExit(f"无 {year} 年辽宁 PDF 记录（已知：{list(LIAONING_YIFENYIDUAN_PDFS)}）")
        collect_liaoning(data_dir, year)
        return

    if province == "guizhou":
        if year not in GUIZHOU_YIFENYIDUAN_PDFS:
            raise SystemExit(f"无 {year} 年贵州 PDF 记录（已知：{list(GUIZHOU_YIFENYIDUAN_PDFS)}）")
        collect_guizhou(data_dir, year)
        return

    pages = PROVINCE_PAGES.get(province, {})
    page_url = pages.get(year)
    if page_url is None:
        raise SystemExit(f"无 {year} 年{province}发布页记录（已知：{list(pages)}）")
    if province == "beijing":
        collect_beijing(data_dir, year, page_url)
    else:
        raise SystemExit(f"未实现 {province} 采集器")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gaokao 数据层：PDF 类省份官方源采集")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("collect", help="采集省份官方一分一段（PDF）")
    p.add_argument("--province", required=True)
    p.add_argument("--year", required=True, type=int)
    p.add_argument("--data-dir", default="data")
    p.set_defaults(func=collect_cmd)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
