#!/usr/bin/env python3
"""Gaokao 数据层：数据版本化（data/version.json）。

从 DuckDB source_ledger 汇总生成数据包版本信息，供客户端判断数据新旧、
决定是否拉取更新。配合 CI 定时数据更新（.github/workflows/data-update.yml）使用。

产出 data/version.json：
  schema_version  规范版本
  data_version    数据包版本（如 2026.1，取已采集的最大年份）
  generated_at    生成时间
  coverage        各数据类型 × 省份 × 年份 覆盖
  sources         全部来源记录（类型/省份/年份/verified）
  stats           各表行数

用法：
    python scripts/data_version.py [--db data/gaokao.duckdb] [--output data/version.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb


# 目标覆盖省份（31 省级行政区；按数据类型区分所需覆盖）
ALL_PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
]

# 各数据类型的目标覆盖（一分一段/投档线全国 31 省；院校名单全国）
TARGET_COVERAGE: dict[str, list[str]] = {
    "score_range": ALL_PROVINCES,
    "toudang": ALL_PROVINCES,
    "school_dim": ["全国"],
}


def build_version(con: duckdb.DuckDBPyConnection) -> dict:
    sources = con.execute(
        "SELECT source_name, source_type, province, year, data_type, verified "
        "FROM source_ledger ORDER BY province, year"
    ).fetchall()

    coverage: dict[str, dict[str, list[int]]] = {}
    source_rows: list[dict] = []
    for name, stype, province, year, dtype, verified in sources:
        key = "toudang" if "投档" in dtype else "score_range" if "一分" in dtype else dtype
        coverage.setdefault(key, {}).setdefault(province, [])
        if year not in coverage[key][province]:
            coverage[key][province].append(year)
        source_rows.append({
            "name": name, "type": stype, "province": province,
            "year": year, "data_type": dtype, "verified": bool(verified),
        })

    # 省份覆盖对比：各数据类型缺哪些省份
    coverage_gaps: dict[str, list[str]] = {}
    for key, targets in TARGET_COVERAGE.items():
        covered = set(coverage.get(key, {}).keys())
        gaps = [p for p in targets if p not in covered]
        if gaps:
            coverage_gaps[key] = gaps

    # 数据包版本：取已采集的最大年份（如 2026.1）
    years = [int(y) for y in {s["year"] for s in source_rows if s["year"]}]
    max_year = max(years) if years else 0
    data_version = f"{max_year}.1" if max_year else "0.0"

    stats: dict[str, int] = {}
    for t in con.execute(
        "SELECT table_name FROM information_schema.tables ORDER BY table_name"
    ).fetchall():
        n = con.execute(f'SELECT COUNT(*) FROM "{t[0]}"').fetchone()[0]
        stats[t[0]] = n

    return {
        "schema_version": 1,
        "data_version": data_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": coverage,
        "coverage_gaps": coverage_gaps,
        "sources": source_rows,
        "stats": stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gaokao 数据版本化")
    parser.add_argument("--db", default="data/gaokao.duckdb")
    parser.add_argument("--output", default="data/version.json")
    args = parser.parse_args()

    con = duckdb.connect(str(Path(args.db)), read_only=True)
    version = build_version(con)
    con.close()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(version, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"数据版本 {version['data_version']} -> {out}")
    print(f"覆盖: " + "; ".join(
        f"{k}({'/'.join(f'{p}:{",".join(map(str, ys))}' for p, ys in v.items())})"
        for k, v in version["coverage"].items()
    ))
    if version.get("coverage_gaps"):
        print("缺口提示（建议补充官方源）: " + "; ".join(
            f"{k} 缺 {len(g)} 省（{'/'.join(g[:8])}{'…' if len(g) > 8 else ''}）"
            for k, g in version["coverage_gaps"].items()
        ))
    else:
        print("缺口提示: 无（目标省份已全覆盖）")
    print(f"来源 {len(version['sources'])} 条，其中已核验 {sum(1 for s in version['sources'] if s['verified'])} 条")


if __name__ == "__main__":
    main()
