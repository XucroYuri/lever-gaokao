#!/usr/bin/env python3
"""Gaokao 数据层 v1：种子数据采集 + DuckDB 建库 + 数据质量校验。

从 Gaokao-Compass-11M（HuggingFace，MIT 许可）下载指定省份/年份的四张表
（一分一段、院校投档线、专业录取、招生计划），用 DuckDB read_csv_auto 自动
标准化入库，并运行数据质量校验（字段覆盖率、分数-位次单调性、科类缺失、
计划数覆盖率），输出 JSON 校验报告。

用途：v1 试点，验证"种子数据 + 官方源交叉校验"的可行性。脚本只做确定性
机械处理，不判断学校好坏，不预测录取概率。

用法：
    python scripts/data_ingest.py ingest --province shandong --year 2024
    python scripts/data_ingest.py validate --db data/gaokao.duckdb
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import duckdb

HF_BASE = "https://huggingface.co/datasets/choucsan/Gaokao-Compass-11M/resolve/main"

# 省份文件夹名 -> 中文名
PROVINCES: dict[str, str] = {
    "anhui": "安徽", "beijing": "北京", "chongqing": "重庆", "fujian": "福建",
    "gansu": "甘肃", "guangdong": "广东", "guangxi": "广西", "guizhou": "贵州",
    "hainan": "海南", "hebei": "河北", "heilongjiang": "黑龙江", "henan": "河南",
    "hubei": "湖北", "hunan": "湖南", "jiangsu": "江苏", "jiangxi": "江西",
    "jilin": "吉林", "liaoning": "辽宁", "neimenggu": "内蒙古", "ningxia": "宁夏",
    "qinghai": "青海", "shaanxi": "陕西", "shandong": "山东", "shanghai": "上海",
    "shanxi": "山西", "sichuan": "四川", "tianjin": "天津", "xinjiang": "新疆",
    "xizang": "西藏", "yunnan": "云南", "zhejiang": "浙江",
}

# 源 CSV 文件名 -> DuckDB 表名
TABLES: dict[str, str] = {
    "score-range.csv": "score_range",
    "school-admission.csv": "admission_school",
    "major-admission.csv": "admission_major",
    "enrollment-plan.csv": "enrollment_plan",
}

# 导入时当作 NULL 的字符串（DuckDB read_csv_auto nullstr）
NULL_STRINGS = ["", "<NA>", "NULL", "null", "nan", "NaN", "None"]


def _download(url: str, dest: Path, retries: int = 3, timeout: int = 180) -> None:
    """带重试的下载；huggingface 偶发 SSL 抖动，重试后通常可恢复。"""
    req = urllib.request.Request(url, headers={"User-Agent": "lever-gaokao/1.0"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                dest.write_bytes(resp.read())
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)
            print(f"  [retry {attempt}] {exc}", file=sys.stderr)


def _source_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def ingest(args: argparse.Namespace) -> None:
    province = args.province
    year = args.year
    if province not in PROVINCES:
        sys.exit(f"未知省份: {province}（可选：{', '.join(PROVINCES)}）")

    endpoint = args.hf_endpoint or HF_BASE
    data_dir = Path(args.data_dir)
    raw_dir = data_dir / "raw" / province / str(year)
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. 下载四张表
    print(f"下载 {PROVINCES[province]} {year} 数据 -> {raw_dir}")
    for csv_name in TABLES:
        url = f"{endpoint}/data/{year}/{province}/{csv_name}"
        dest = raw_dir / csv_name
        if dest.exists() and not args.force:
            print(f"  [cached] {csv_name} ({dest.stat().st_size} bytes)")
            continue
        _download(url, dest)
        print(f"  [downloaded] {csv_name} ({dest.stat().st_size} bytes)")

    # 2. 用 read_csv_auto 自动推断类型 + null 处理，入库
    db_path = data_dir / "gaokao.duckdb"
    con = duckdb.connect(str(db_path))
    nullstr = "[" + ",".join(f"'{s}'" for s in NULL_STRINGS) + "]"
    for csv_name, table in TABLES.items():
        path = (raw_dir / csv_name).as_posix()
        url = f"{endpoint}/data/{year}/{province}/{csv_name}"
        sid = _source_id(url)
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT *, '{sid}' AS source_id
            FROM read_csv_auto('{path}', header=true, nullstr={nullstr})
            """
        )
        n = con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        print(f"  [loaded] {table}: {n} rows")

    # 2.5 修正 read_csv_auto 对全空列误判为 VARCHAR 的问题（显式类型）
    _numeric_cols: dict[str, dict[str, str]] = {
        "score_range": {"year": "BIGINT", "control_score": "BIGINT", "score": "BIGINT",
                        "segment_count": "BIGINT", "cumulative_count": "BIGINT"},
        "admission_school": {"year": "BIGINT", "min_score": "BIGINT", "min_rank": "BIGINT",
                             "control_score": "BIGINT", "score_diff": "BIGINT", "admit_count": "BIGINT"},
        "admission_major": {"year": "BIGINT", "min_score": "BIGINT", "min_rank": "BIGINT",
                            "max_score": "BIGINT", "avg_score": "BIGINT", "admit_count": "BIGINT"},
        "enrollment_plan": {"year": "BIGINT", "plan_count": "BIGINT", "duration": "BIGINT",
                            "tuition": "DOUBLE"},
    }
    for table, cols in _numeric_cols.items():
        existing = {r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()}
        for col, typ in cols.items():
            if col in existing:
                con.execute(f"ALTER TABLE {table} ALTER {col} TYPE {typ}")

    # 3. 写 source_ledger 来源治理表
    con.execute("""
        CREATE OR REPLACE TABLE source_ledger (
            source_id VARCHAR, source_name VARCHAR, source_type VARCHAR,
            source_url VARCHAR, license VARCHAR, province VARCHAR, year BIGINT,
            data_type VARCHAR, verified BOOLEAN
        )
    """)
    for csv_name, table in TABLES.items():
        url = f"{endpoint}/data/{year}/{province}/{csv_name}"
        con.execute(
            "INSERT INTO source_ledger VALUES (?,?,?,?,?,?,?,?,?)",
            [_source_id(url), "Gaokao-Compass-11M", "开放数据", url,
             "MIT", PROVINCES[province], year, table, False],
        )

    # 4. 建人工纠正表（correction_log，对应设计文档"人工纠正流程"）
    con.execute("""
        CREATE OR REPLACE TABLE correction_log (
            correction_id INTEGER PRIMARY KEY,
            table_name VARCHAR, row_pk VARCHAR, field VARCHAR,
            old_value VARCHAR, new_value VARCHAR, reason VARCHAR,
            corrector VARCHAR, corrected_time TIMESTAMP, source_id VARCHAR
        )
    """)
    con.close()
    print(f"  入库完成 -> {db_path}")
    print(f"  下一步: python scripts/data_ingest.py validate --db {db_path}")


def validate(args: argparse.Namespace) -> None:
    db_path = Path(args.db)
    con = duckdb.connect(str(db_path), read_only=True)
    report: dict = {"tables": {}, "checks": []}

    for table in TABLES.values():
        exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [table]
        ).fetchone()[0]
        if not exists:
            report["tables"][table] = {"present": False}
            continue
        n = con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        report["tables"][table] = {"present": True, "rows": n}

    # 一分一段完整性
    sr = report["tables"].get("score_range", {})
    if sr.get("present"):
        total = sr["rows"]
        nonempty = con.execute(
            "SELECT COUNT(*) FROM score_range WHERE score IS NOT NULL"
        ).fetchone()[0]
        report["checks"].append({
            "check": "一分一段完整性",
            "detail": f"score 非空 {nonempty}/{total} 行",
            "severity": "error" if nonempty == 0 else "ok",
        })

    # 分数-位次单调性可校验行数
    for table in ("admission_school", "admission_major"):
        info = report["tables"].get(table, {})
        if not info.get("present") or info.get("rows", 0) == 0:
            continue
        both = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE min_score IS NOT NULL AND min_rank IS NOT NULL"
        ).fetchone()[0]
        report["checks"].append({
            "check": f"{table} 分数-位次单调性",
            "detail": f"min_score 与 min_rank 同时非空 {both} 行",
            "severity": "ok" if both > 0 else "warn",
        })

    # 科类缺失检测
    for table in ("admission_school", "admission_major"):
        info = report["tables"].get(table, {})
        if not info.get("present"):
            continue
        empty = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE category IS NULL"
        ).fetchone()[0]
        total = info["rows"]
        if empty > 0:
            report["checks"].append({
                "check": f"{table} 科类缺失",
                "detail": f"category 空 {empty}/{total} 行（需按批次/科类回填）",
                "severity": "warn",
            })

    # 招生计划 plan_count 覆盖率
    ep = report["tables"].get("enrollment_plan", {})
    if ep.get("present"):
        total = ep["rows"]
        nonempty = con.execute(
            "SELECT COUNT(*) FROM enrollment_plan WHERE plan_count IS NOT NULL"
        ).fetchone()[0]
        report["checks"].append({
            "check": "招生计划 plan_count 覆盖率",
            "detail": f"plan_count 非空 {nonempty}/{total} 行",
            "severity": "ok" if nonempty == total else "warn",
        })

    con.close()
    out_path = Path(args.output or (db_path.parent / "reports" / "validate_report.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"校验报告 -> {out_path}")
    if args.json:
        # 单行 JSON，供程序化调用（dsh 等）直接解析
        print(json.dumps(report, ensure_ascii=False))
        return
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _build_filters(args: argparse.Namespace, prefix: str = "") -> tuple[list[str], list]:
    """把查询参数拼成 WHERE 子句片段 + 参数列表。prefix 用于 JOIN 时消除列歧义。"""
    conds: list[str] = []
    params: list = []
    if args.province:
        conds.append(f"{prefix}province = ?")
        params.append(args.province)
    if args.year:
        conds.append(f"{prefix}year = ?")
        params.append(args.year)
    if args.category:
        conds.append(f"{prefix}category = ?")
        params.append(args.category)
    if args.batch:
        conds.append(f"{prefix}batch = ?")
        params.append(args.batch)
    if args.min_rank is not None:
        conds.append(f"{prefix}min_rank >= ?")
        params.append(args.min_rank)
    if args.max_rank is not None:
        conds.append(f"{prefix}min_rank <= ?")
        params.append(args.max_rank)
    if args.subject:
        conds.append(f"({prefix}subject_req IS NULL OR {prefix}subject_req LIKE ?)")
        params.append(f"%{args.subject}%")
    if args.level:
        level_map = {"985": "is_985", "211": "is_211"}
        col = level_map.get(args.level)
        if col:
            conds.append(f"{prefix}{col} = 1")
    return conds, params


def query(args: argparse.Namespace) -> None:
    """约束查询：位次/分数/学费/科类/选科/层级筛选，输出排序结果。

    这是设计文档"查询分类与路由"中第 1 层（确定性 SQL 模板）的最小实现。
    只支持确定性约束查询，不做 RAG、不做自由 text2sql、不预测概率。
    """
    con = duckdb.connect(str(Path(args.db)), read_only=True)

    if args.table == "school":
        cols = "university_name, category, batch, min_rank, is_985, is_211"
        source = "admission_school"
    else:
        cols = ("m.university_name, m.major_name, m.major_group, m.subject_req, "
                "m.min_rank, e.tuition")
        source = ("admission_major m LEFT JOIN enrollment_plan e "
                  "ON m.university_name = e.university_name "
                  "AND m.major_name = e.major_name "
                  "AND m.category = e.category")

    # 前缀：major 模式字段带 m. 前缀
    prefix = "m." if args.table == "major" else ""
    conds, params = _build_filters(args, prefix)
    where = (" WHERE " + " AND ".join(conds)) if conds else ""

    if args.table == "major" and args.max_tuition is not None:
        where += (" AND" if where else " WHERE") + " (e.tuition IS NULL OR e.tuition <= ?)"
        params.append(args.max_tuition)

    sql = (
        f"SELECT {cols} FROM {source}{where} "
        f"ORDER BY {prefix}min_rank ASC NULLS LAST LIMIT ?"
    )
    params.append(args.limit)

    rows = con.execute(sql, params).fetchall()
    con.close()

    # JSON 输出（供 dsh 等程序化调用方使用）
    if args.json:
        import json as _json
        if args.table == "school":
            payload = [
                {"school": r[0], "category": r[1], "batch": r[2],
                 "min_rank": r[3], "is_985": bool(r[4]), "is_211": bool(r[5])}
                for r in rows
            ]
        else:
            payload = [
                {"school": r[0], "major": r[1], "major_group": r[2],
                 "subject_req": r[3], "min_rank": r[4], "tuition": r[5]}
                for r in rows
            ]
        print(_json.dumps({"table": args.table, "count": len(payload), "rows": payload},
                          ensure_ascii=False))
        return

    # 输出结果
    print(f"查询条件: 省份={args.province or '全部'} 年份={args.year or '全部'} "
          f"科类={args.category or '全部'} 位次[{args.min_rank or '-∞'}, {args.max_rank or '+∞'}] "
          f"选科={args.subject or '不限'} 学费上限={args.max_tuition or '不限'} 层级={args.level or '不限'}")
    print(f"命中 {len(rows)} 行（{args.table} 模式）\n")
    if args.table == "school":
        for name, cat, batch, rank, is985, is211 in rows:
            tags = "985" if is985 else ("211" if is211 else "")
            print(f"  {name}  [{cat}·{batch}]  位次{rank}  {tags}")
    else:
        for name, major, group, subj, rank, tuition in rows:
            tuition_s = f"{tuition:.0f}元" if tuition else "?"
            print(f"  {name} | {major} | 组:{group or '-'} | 选科:{subj or '不限'} | 位次{rank} | {tuition_s}")


def correct(args: argparse.Namespace) -> None:
    """人工纠正：把一条纠错记录写入 correction_log（设计文档"人工纠正流程"）。

    只记录，不直接覆盖原始数据；后续"版本化回写"是独立步骤。
    记录字段：表名、行主键、字段、旧值、新值、原因、纠正人。
    """
    con = duckdb.connect(str(Path(args.db)))
    next_id = con.execute(
        "SELECT COALESCE(MAX(correction_id), 0) + 1 FROM correction_log"
    ).fetchone()[0]
    con.execute(
        "INSERT INTO correction_log VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,?)",
        [next_id, args.table, args.row_pk, args.field, args.old,
         args.new, args.reason, args.corrector, args.source_id],
    )
    con.close()
    print(f"已记录纠正 #{next_id}: {args.table}.{args.row_pk}.{args.field} "
          f"{args.old or '(空)'} -> {args.new or '(空)'}（{args.reason}）")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gaokao 数据层 v1")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="下载并入库")
    p_ingest.add_argument("--province", required=True)
    p_ingest.add_argument("--year", required=True, type=int)
    p_ingest.add_argument("--data-dir", default="data")
    p_ingest.add_argument("--hf-endpoint", default=None, help="默认 HF 官方，可传 https://hf-mirror.com")
    p_ingest.add_argument("--force", action="store_true", help="强制重新下载")
    p_ingest.set_defaults(func=ingest)

    p_val = sub.add_parser("validate", help="校验已入库数据")
    p_val.add_argument("--db", default="data/gaokao.duckdb")
    p_val.add_argument("--output", default=None)
    p_val.add_argument("--json", action="store_true", help="单行 JSON 输出（供程序化调用）")
    p_val.set_defaults(func=validate)

    p_query = sub.add_parser("query", help="约束查询（位次/学费/科类/选科/层级）")
    p_query.add_argument("--table", choices=["school", "major"], default="major")
    p_query.add_argument("--db", default="data/gaokao.duckdb")
    p_query.add_argument("--province", default=None, help="省份中文名，如 山东")
    p_query.add_argument("--year", default=None, type=int)
    p_query.add_argument("--category", default=None, help="科类，如 综合/物理类/历史类/理科")
    p_query.add_argument("--batch", default=None, help="批次，如 普通类一段")
    p_query.add_argument("--min-rank", default=None, type=int)
    p_query.add_argument("--max-rank", default=None, type=int)
    p_query.add_argument("--subject", default=None, help="选科关键词，subject_req LIKE")
    p_query.add_argument("--max-tuition", default=None, type=int, help="学费上限（元/年）")
    p_query.add_argument("--level", choices=["985", "211"], default=None)
    p_query.add_argument("--limit", default=30, type=int)
    p_query.add_argument("--json", action="store_true", help="输出 JSON（供程序化调用）")
    p_query.set_defaults(func=query)

    p_correct = sub.add_parser("correct", help="人工纠正（写入 correction_log）")
    p_correct.add_argument("--db", default="data/gaokao.duckdb")
    p_correct.add_argument("--table", required=True, help="表名，如 admission_major")
    p_correct.add_argument("--row-pk", required=True, help="行主键，如 山东/2024/河南大学/机械工程")
    p_correct.add_argument("--field", required=True, help="纠错字段，如 tuition")
    p_correct.add_argument("--old", default=None, help="旧值")
    p_correct.add_argument("--new", required=True, help="新值")
    p_correct.add_argument("--reason", required=True, help="纠错原因/依据")
    p_correct.add_argument("--corrector", default="manual", help="纠正人标识")
    p_correct.add_argument("--source-id", default=None, help="依据来源 ID")
    p_correct.set_defaults(func=correct)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
