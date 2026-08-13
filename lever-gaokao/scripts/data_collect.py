#!/usr/bin/env python3
"""Gaokao 数据层 v1：当年官方源采集 + 时限日历。

针对种子数据（Gaokao-Compass-11M）的缺口（一分一段全空、min_score 缺失），
从省级考试院官方源采集补全。当前实现山东（sdzk.cn，一分一段以 .xls 附件发布）。

两个子命令：
- calendar：输出年度数据采集时限日历（硬截止①出分前完成计划采集、硬截止②一分一段 48h 入库等）
- collect ：采集官方一分一段（抓 NewsInfo 页 → 提取 .xls → calamine 解析 → 入 DuckDB score_range）

用法：
    python scripts/data_collect.py calendar
    python scripts/data_collect.py collect --province shandong --year 2026
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

import duckdb

# 官方原文归档目录（提交到仓库，供人工校验原文对照；按 类别/省份/年份 分组）
OFFICIAL_SOURCES = Path("official-sources")


def _archive_file(src: Path, data_type: str, province: str, year: int) -> Path:
    """把官方源文件归档到 official-sources/{data_type}/{province}/{year}/。"""
    dest_dir = OFFICIAL_SOURCES / data_type / province / str(year)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    print(f"  归档原文 -> {dest}")
    return dest

# 山东 sdzk.cn 一分一段 NewsInfo 页面 NewsID（按年份；2026 为实测值）
SHANDONG_NEWSID: dict[int, str] = {
    2026: "7258",
}

# 山东普通类常规批第 1 次志愿投档情况表 NewsInfo 页面。
SHANDONG_TOUDANG_NEWSID: dict[int, str] = {
    2026: "7312",
}

# 浙江 zjzs.net 第一段平行投档分数线表 art 页面（按年份；2026 为实测值）
ZHEJIANG_TOUDANG_PAGES: dict[int, str] = {
    2026: "https://www.zjzs.net/art/2026/7/21/art_45_12550.html",
}

# 年度数据采集时限日历（硬截止以 ⚠ 标记）
TIMELINE: list[dict] = [
    {"window": "前一年 9 月 – 当年 3 月", "month_start": 9, "month_end": 3,
     "item": "招生工作规定 / 政策变化 / 选科要求调整", "action": "跟踪教育部 + 各省考试院政策发布", "hard": False},
    {"window": "当年 3 – 5 月", "month_start": 3, "month_end": 5,
     "item": "招生章程 / 计划预发布 / 院校更名合并 / 新增硕博点", "action": "批量采集 + 人工录入院校状态变化", "hard": False},
    {"window": "5 月底 – 6 月初", "month_start": 5, "month_end": 6,
     "item": "完整招生计划书 / 专业组目录", "action": "出分前完成全量采集", "hard": True,
     "deadline": "硬截止①：高考日（6 月上旬）"},
    {"window": "6 月下旬（出分后）", "month_start": 6, "month_end": 6,
     "item": "省控线 / 一分一段表", "action": "48 小时内采集 + 校验", "hard": True,
     "deadline": "硬截止②：填报窗口开启（6 月底）"},
    {"window": "6 月底 – 7 月初（填报期）", "month_start": 6, "month_end": 7,
     "item": "填报系统动态数据 / 计划变更", "action": "每日刷新", "hard": True,
     "deadline": "硬截止③：每日"},
    {"window": "7 月（投档期）", "month_start": 7, "month_end": 7,
     "item": "投档线 / 专业组投档分", "action": "出线后 24h 入库", "hard": True,
     "deadline": "硬截止④：投档线发布后 24h"},
    {"window": "7 – 8 月（征集期）", "month_start": 7, "month_end": 8,
     "item": "征集志愿计划 / 缺额", "action": "每轮征集实时更新", "hard": True,
     "deadline": "硬截止⑤：每轮征集"},
    {"window": "9 – 12 月", "month_start": 9, "month_end": 12,
     "item": "专业录取分 / 录取统计 / 复盘", "action": "下一年回测与模型校准", "hard": False},
]


def _download(url: str, dest: Path, timeout: int = 60) -> None:
    """用 curl 跟随 sdzk.cn 的缓存重定向并重试瞬时失败。"""
    subprocess.run(
        ["curl.exe", "-sL", "--retry", "3", "--max-time", str(timeout),
         url, "-o", str(dest)],
        check=True,
    )


def calendar_cmd(args: argparse.Namespace) -> None:
    """输出年度数据采集时限日历，并标注相对参考日期的状态。"""
    today = date.fromisoformat(args.today) if args.today else date.today()
    print(f"年度数据采集时限日历（参考日期 {today}）\n")
    for entry in TIMELINE:
        tag = "[硬截止]" if entry["hard"] else "[软截止]"
        deadline = entry.get("deadline", "")
        line = (f"[{tag}] {entry['window']}\n"
                f"    数据项: {entry['item']}\n"
                f"    动作:   {entry['action']}")
        if deadline:
            line += f"\n    {deadline}"
        print(line + "\n")
    print("说明：硬截止①是全局安全线（出分前完成招生计划采集）；"
          "硬截止②（一分一段 48h）是最高压环节，需自动采集 + 人工抽查双通道。")


def _extract_xls_url(html: str) -> str | None:
    """从 sdzk.cn NewsInfo 页面提取 .xls 附件相对路径。"""
    m = re.search(r'href=["\']([^"\']+\.xls(?:x)?)["\']', html, re.I)
    return m.group(1) if m else None


def _to_int(v) -> int | None:
    """把 calamine 单元格值（可能是 float/int/str/''/None）转 int，空值返回 None。"""
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _parse_shandong_yifenyiduan(path: Path, province: str, year: int) -> list[dict]:
    """解析山东一分一段 .xls（宽表：每科 本段人数/累计人数 两列）。"""
    from python_calamine import CalamineWorkbook

    wb = CalamineWorkbook.from_path(str(path))
    sheet = wb.get_sheet_by_name(wb.sheet_names[0]).to_python()

    # 找科目表头行（含"成绩"或"全省"/"选考"）
    subject_row_idx = None
    for i, row in enumerate(sheet[:5]):
        cells = [str(c) if c is not None else "" for c in row]
        if any("全省" in c or "选考" in c or c == "成绩" for c in cells):
            subject_row_idx = i
            break
    if subject_row_idx is None:
        raise RuntimeError("未识别到一分一段表头行")

    subject_row = sheet[subject_row_idx]
    # 科目名在奇数列（1,3,5...），每科占两列（本段人数/累计人数）
    subjects: list[tuple[int, str]] = []
    for col in range(1, len(subject_row), 2):
        name = str(subject_row[col]).strip() if subject_row[col] is not None else ""
        if name:
            # 归一化：全体/全省 -> 综合，选考X -> X
            name = name.replace("选考", "")
            if name in ("全省", "全体"):
                name = "综合"
            subjects.append((col, name))

    rows_out: list[dict] = []
    for row in sheet[subject_row_idx + 2:]:
        score = _to_int(row[0])
        if score is None:
            continue
        for col, subject in subjects:
            seg = _to_int(row[col])
            cum = _to_int(row[col + 1]) if col + 1 < len(row) else None
            if seg is None and cum is None:
                continue
            rows_out.append({
                "province": province, "year": year, "category": subject,
                "score": score,
                "segment_count": seg,
                "cumulative_count": cum,
            })
    return rows_out


def _parse_shandong_toudang(path: Path) -> list[dict]:
    """动态识别表头并解析山东专业+院校投档情况表。"""
    from python_calamine import CalamineWorkbook

    wb = CalamineWorkbook.from_path(str(path))
    sheet = wb.get_sheet_by_name(wb.sheet_names[0]).to_python()
    header_idx = None
    columns: dict[str, int] = {}
    aliases = {
        "school": ("院校代号及名称", "院校名称"),
        "major": ("专业代号及名称", "专业名称"),
        "score": ("投档最低分", "最低分"),
        "rank": ("最低位次", "投档最低位次"),
        "plan": ("计划数", "计划人数"),
        "subject": ("选考科目要求", "选科要求"),
    }
    for row_idx, row in enumerate(sheet[:20]):
        cells = [str(cell).strip() if cell is not None else "" for cell in row]
        found = {
            key: col_idx
            for key, names in aliases.items()
            for col_idx, cell in enumerate(cells)
            if any(name in cell for name in names)
        }
        if "school" in found and "major" in found and "rank" in found:
            header_idx, columns = row_idx, found
            break
    if header_idx is None:
        raise RuntimeError("未识别到山东投档情况表表头")

    rows_out: list[dict] = []
    for row in sheet[header_idx + 1:]:
        school_raw = str(row[columns["school"]]).strip()
        major_raw = str(row[columns["major"]]).strip()
        min_rank = _to_int(row[columns["rank"]])
        if not school_raw or not major_raw or min_rank is None:
            continue
        school_match = re.match(r"^([A-Z0-9]+)\s*(.+)$", school_raw)
        major_match = re.match(r"^([A-Z0-9]+)\s+(.+)$", major_raw)
        rows_out.append({
            "school_code": school_match.group(1) if school_match else None,
            "school_name": school_match.group(2).strip() if school_match else school_raw,
            "major_code": major_match.group(1) if major_match else None,
            "major_name": major_match.group(2).strip() if major_match else major_raw,
            "subject_req": str(row[columns["subject"]]).strip() if "subject" in columns else None,
            "min_score": _to_int(row[columns["score"]]) if "score" in columns else None,
            "min_rank": min_rank,
            "plan_count": _to_int(row[columns["plan"]]) if "plan" in columns else None,
        })
    return rows_out


def _parse_zhejiang_toudang(path: Path) -> list[dict]:
    """解析浙江第一段平行投档分数线表（含学校/专业/计划数/分数线/位次）。"""
    from python_calamine import CalamineWorkbook

    wb = CalamineWorkbook.from_path(str(path))
    sheet = wb.get_sheet_by_name(wb.sheet_names[0]).to_python()
    aliases = {
        "school": ("学校代号", "学校名称"),
        "major": ("专业代号", "专业名称"),
        "plan": ("计划数",),
        "score": ("分数线", "最低分"),
        "rank": ("位次",),
    }
    header_idx, columns = None, {}
    for row_idx, row in enumerate(sheet[:10]):
        cells = [str(c).strip() if c is not None else "" for c in row]
        found = {
            key: col_idx for key, names in aliases.items()
            for col_idx, cell in enumerate(cells)
            if any(name in cell for name in names)
        }
        if "school" in found and "major" in found and "score" in found and "rank" in found:
            header_idx, columns = row_idx, found
            break
    if header_idx is None:
        raise RuntimeError("未识别到浙江投档表表头")

    rows_out: list[dict] = []
    for row in sheet[header_idx + 1:]:
        school_raw = str(row[columns["school"]]).strip()
        major_raw = str(row[columns["major"]]).strip()
        if not school_raw or not major_raw:
            continue
        school_match = re.match(r"^([0-9A-Z]+)\s*(.+)$", school_raw)
        major_match = re.match(r"^([0-9A-Z]+)\s+(.+)$", major_raw)
        rows_out.append({
            "school_code": school_match.group(1) if school_match else school_raw,
            "school_name": school_match.group(2).strip() if school_match else school_raw,
            "major_code": major_match.group(1) if major_match else None,
            "major_name": major_match.group(2).strip() if major_match else major_raw,
            "subject_req": None,
            "min_score": _to_int(row[columns["score"]]),
            "min_rank": _to_int(row[columns["rank"]]),
            "plan_count": _to_int(row[columns["plan"]]) if "plan" in columns else None,
        })
    return rows_out


def _store_zhejiang_toudang(data_dir: Path, year: int, xls_url: str, rows: list[dict]) -> None:
    """新建浙江年度投档表并写入来源（分数线/计划数直接来自官方，无需反查）。"""
    db_path = data_dir / "gaokao.duckdb"
    table = f"zhejiang_toudang_{year}"
    sid = hashlib.sha256(xls_url.encode("utf-8")).hexdigest()[:16]
    with duckdb.connect(str(db_path)) as con:
        con.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
            school_code VARCHAR, school_name VARCHAR, major_code VARCHAR,
            major_name VARCHAR, subject_req VARCHAR, min_score BIGINT,
            min_rank BIGINT, plan_count BIGINT, source_id VARCHAR)""")
        con.execute(f"DELETE FROM {table} WHERE source_id = ?", [sid])
        con.executemany(
            f"INSERT INTO {table} VALUES (?,?,?,?,?,?,?,?,?)",
            [[r["school_code"], r["school_name"], r["major_code"], r["major_name"],
              r["subject_req"], r["min_score"], r["min_rank"], r["plan_count"], sid]
             for r in rows],
        )
        con.execute("DELETE FROM source_ledger WHERE source_id = ?", [sid])
        con.execute(
            "INSERT INTO source_ledger VALUES (?,?,?,?,?,?,?,?,?)",
            [sid, f"浙江省考试院 {year} 第一段平行投档分数线表", "当年官方",
             xls_url, "官方公开", "浙江", year, "专业投档线", True],
        )
        total, scored, planned = con.execute(
            f"SELECT COUNT(*), COUNT(min_score), COUNT(plan_count) FROM {table} WHERE source_id = ?",
            [sid],
        ).fetchone()
    print(f"  已入库 -> {db_path} / {table}")
    print(f"  总行数: {total}；min_score 非空: {scored}；plan_count 非空: {planned}")


def collect_cmd(args: argparse.Namespace) -> None:
    """采集山东/浙江官方一分一段或投档情况表。"""
    province = args.province
    year = args.year
    data_type = args.type
    data_dir = Path(args.data_dir)
    base = "https://www.zjzs.net" if province == "zhejiang" else "https://www.sdzk.cn"

    # 浙江：投档分数线表（art 页面，含计划数/分数线/位次，无需反查）
    if province == "zhejiang":
        page_url = ZHEJIANG_TOUDANG_PAGES.get(year)
        if page_url is None:
            raise SystemExit(f"无 {year} 年浙江投档线页面记录（已知：{list(ZHEJIANG_TOUDANG_PAGES)}）")
        raw_dir = data_dir / "official" / province / str(year)
        raw_dir.mkdir(parents=True, exist_ok=True)
        page_path = raw_dir / "page.html"
        print(f"抓取 {page_url}")
        _download(page_url, page_path)
        html = page_path.read_text(encoding="utf-8", errors="ignore")
        xls_rel = _extract_xls_url(html)
        if xls_rel is None:
            raise SystemExit("页面中未找到 .xls 附件（可能改为图片/动态加载）")
        xls_url = xls_rel if xls_rel.startswith("http") else base + xls_rel
        xls_path = raw_dir / "toudang.xls"
        print(f"下载附件 {xls_url}")
        _download(xls_url, xls_path)
        _archive_file(xls_path, "toudang", "zhejiang", year)
        rows = _parse_zhejiang_toudang(xls_path)
        print(f"解析出投档情况 {len(rows)} 行（{year} 浙江第一段平行投档）")
        _store_zhejiang_toudang(data_dir, year, xls_url, rows)
        return

    if province != "shandong":
        raise SystemExit("当前仅实现山东（shandong）与浙江（zhejiang）")

    newsids = SHANDONG_TOUDANG_NEWSID if data_type == "toudang" else SHANDONG_NEWSID
    newsid = newsids.get(year)
    if newsid is None:
        raise SystemExit(f"无 {year} 年山东 NewsID 记录（已知：{list(SHANDONG_NEWSID)}）")

    raw_dir = data_dir / "official" / province / str(year)
    raw_dir.mkdir(parents=True, exist_ok=True)

    page_url = f"{base}/NewsInfo.aspx?NewsID={newsid}"
    page_path = raw_dir / "page.html"
    print(f"抓取 {page_url}")
    _download(page_url, page_path)
    html = page_path.read_text(encoding="utf-8", errors="ignore")

    xls_rel = _extract_xls_url(html)
    if xls_rel is None:
        raise SystemExit("页面中未找到 .xls 附件（可能改为图片/动态加载）")
    xls_url = xls_rel if xls_rel.startswith("http") else base + xls_rel
    xls_path = raw_dir / f"{data_type}.xls"
    print(f"下载附件 {xls_url}")
    _download(xls_url, xls_path)
    _archive_file(xls_path, data_type, "shandong", year)

    if data_type == "toudang":
        rows = _parse_shandong_toudang(xls_path)
        print(f"解析出投档情况 {len(rows)} 行（{year} 山东普通类常规批第1次志愿）")
        _store_shandong_toudang(data_dir, year, xls_url, rows)
        return

    rows = _parse_shandong_yifenyiduan(xls_path, "山东", year)
    print(f"解析出一分一段 {len(rows)} 行（{year} 山东，按科目拆分）")

    # 入 DuckDB score_range（与 data_ingest.py 的表结构一致）
    db_path = data_dir / "gaokao.duckdb"
    con = duckdb.connect(str(db_path))
    sid = hashlib.sha256(xls_url.encode("utf-8")).hexdigest()[:16]
    con.execute(
        "DELETE FROM score_range WHERE province = ? AND year = ? AND source_id = ?",
        ["山东", year, sid],
    )
    # 动态按列插入（保持与现有 score_range 列兼容）
    for r in rows:
        con.execute(
            "INSERT INTO score_range (province, year, category, score, segment_count, cumulative_count, source_id) "
            "VALUES (?,?,?,?,?,?,?)",
            [r["province"], r["year"], r["category"], r["score"],
             r["segment_count"], r["cumulative_count"], sid],
        )
    # 记来源
    con.execute(
        "INSERT INTO source_ledger VALUES (?,?,?,?,?,?,?,?,?)",
        [sid, f"山东考试院 {year} 一分一段", "当年官方", xls_url, "官方公开",
         "山东", year, "score_range", False],
    )
    con.close()
    print(f"  已入库 -> {db_path}")
    print(f"  下一步: python scripts/data_ingest.py validate --db {db_path}")


def _store_shandong_toudang(data_dir: Path, year: int, xls_url: str, rows: list[dict]) -> None:
    """新建年度投档表，写入来源，并用官方一分一段位次反查最低分。"""
    db_path = data_dir / "gaokao.duckdb"
    table = f"shandong_toudang_{year}"
    sid = hashlib.sha256(xls_url.encode("utf-8")).hexdigest()[:16]
    with duckdb.connect(str(db_path)) as con:
        con.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
            school_code VARCHAR, school_name VARCHAR, major_code VARCHAR,
            major_name VARCHAR, subject_req VARCHAR, min_score BIGINT,
            min_rank BIGINT, plan_count BIGINT, source_id VARCHAR)""")
        con.execute(f"DELETE FROM {table} WHERE source_id = ?", [sid])
        con.executemany(
            f"INSERT INTO {table} VALUES (?,?,?,?,?,?,?,?,?)",
            [[r["school_code"], r["school_name"], r["major_code"], r["major_name"],
              r["subject_req"], r["min_score"], r["min_rank"], r["plan_count"], sid]
             for r in rows],
        )
        con.execute(f"""UPDATE {table} AS t SET min_score = (
            SELECT max(score) FROM score_range AS s
            WHERE s.province = '山东' AND s.year = ? AND s.category = '综合'
              AND s.cumulative_count >= t.min_rank)
            WHERE t.source_id = ? AND t.min_score IS NULL""", [year, sid])
        con.execute("DELETE FROM source_ledger WHERE source_id = ?", [sid])
        con.execute(
            "INSERT INTO source_ledger VALUES (?,?,?,?,?,?,?,?,?)",
            [sid, f"山东考试院 {year} 普通类常规批第1次志愿投档情况表", "当年官方",
             xls_url, "官方公开", "山东", year, "专业投档线", True],
        )
        total, scored = con.execute(
            f"SELECT count(*), count(min_score) FROM {table} WHERE source_id = ?", [sid]
        ).fetchone()
        samples = con.execute(
            f"SELECT school_name, major_name, min_score, min_rank FROM {table} "
            "WHERE source_id = ? AND min_score IS NOT NULL ORDER BY min_rank LIMIT 3", [sid]
        ).fetchall()
    print(f"  已入库 -> {db_path} / {table}")
    print(f"  总行数: {total}；min_score 非空: {scored}")
    print("  样例（院校 / 专业 / 最低分 / 最低位次）：")
    for school, major, score, rank in samples:
        print(f"    {school} / {major} / {score} / {rank}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gaokao 数据层 v1：官方源采集 + 时限日历")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cal = sub.add_parser("calendar", help="年度数据采集时限日历")
    p_cal.add_argument("--today", default=None, help="参考日期 YYYY-MM-DD，默认今天")
    p_cal.set_defaults(func=calendar_cmd)

    p_col = sub.add_parser("collect", help="采集官方一分一段或投档情况表")
    p_col.add_argument("--province", required=True)
    p_col.add_argument("--year", required=True, type=int)
    p_col.add_argument("--type", choices=("yifenyiduan", "toudang"), default="yifenyiduan")
    p_col.add_argument("--data-dir", default="data")
    p_col.set_defaults(func=collect_cmd)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
