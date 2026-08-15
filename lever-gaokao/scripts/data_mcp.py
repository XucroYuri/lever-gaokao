#!/usr/bin/env python3
"""Gaokao 数据层 MCP server：把约束查询与数据校验能力暴露给 MCP 兼容的 Agent 工具。

对接 data_ingest.py / data_collect.py 建出的 DuckDB（data/gaokao.duckdb），
提供三个只读工具：query_majors（专业级约束查询）、query_schools（院校级约束查询）、
validate_data（数据质量校验报告）。

运行（stdio 传输，供 MCP 客户端接入）：
    python scripts/data_mcp.py

注意：只做确定性约束查询，不预测录取概率，不输出伪精确概率。
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
from mcp.server.mcpserver import MCPServer

DB_PATH = Path("data/gaokao.duckdb")

server = MCPServer(
    name="gaokao-data",
    title="高考志愿数据层",
    description="高考志愿数据层：位次/学费/科类/选科约束查询 + 数据质量校验",
    instructions=(
        "只读查询工具。约束查询走参数化 SQL（位次优先于分数），不预测录取概率。"
        "结果仅供参考，正式填报需回到省级考试院官方数据复核。"
    ),
    version="0.1.0",
)


def _con() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        raise RuntimeError(f"数据库不存在: {DB_PATH}，请先运行 data_ingest.py ingest")
    return duckdb.connect(str(DB_PATH), read_only=True)


@server.tool(description="专业级约束查询：按位次区间/选科/学费上限/科类返回匹配专业，按位次升序。省份如 山东，选科如 物理。")
def query_majors(
    province: str = "",
    year: int = 0,
    min_rank: int = 0,
    max_rank: int = 0,
    subject: str = "",
    max_tuition: int = 0,
    limit: int = 30,
) -> str:
    conds: list[str] = []
    params: list = []
    if province:
        conds.append("m.province = ?")
        params.append(province)
    if year:
        conds.append("m.year = ?")
        params.append(year)
    if min_rank:
        conds.append("m.min_rank >= ?")
        params.append(min_rank)
    if max_rank:
        conds.append("m.min_rank <= ?")
        params.append(max_rank)
    if subject:
        conds.append("(m.subject_req IS NULL OR m.subject_req LIKE ?)")
        params.append(f"%{subject}%")
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    if max_tuition:
        where += (" AND" if where else " WHERE") + " (e.tuition IS NULL OR e.tuition <= ?)"
        params.append(max_tuition)
    sql = (
        "SELECT m.university_name, m.major_name, m.subject_req, m.min_rank, e.tuition "
        "FROM admission_major m LEFT JOIN enrollment_plan e "
        "ON m.university_name = e.university_name AND m.major_name = e.major_name "
        f"AND m.category = e.category{where} ORDER BY m.min_rank ASC NULLS LAST LIMIT ?"
    )
    params.append(limit)
    con = _con()
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()
    out = [
        {"school": r[0], "major": r[1], "subject_req": r[2], "min_rank": r[3], "tuition": r[4]}
        for r in rows
    ]
    return json.dumps(out, ensure_ascii=False)


@server.tool(description="院校级约束查询：按位次区间/科类/批次/985/211 返回匹配院校。")
def query_schools(
    province: str = "",
    year: int = 0,
    min_rank: int = 0,
    max_rank: int = 0,
    category: str = "",
    level: str = "",
    limit: int = 30,
) -> str:
    conds: list[str] = []
    params: list = []
    if province:
        conds.append("province = ?")
        params.append(province)
    if year:
        conds.append("year = ?")
        params.append(year)
    if min_rank:
        conds.append("min_rank >= ?")
        params.append(min_rank)
    if max_rank:
        conds.append("min_rank <= ?")
        params.append(max_rank)
    if category:
        conds.append("category = ?")
        params.append(category)
    if level == "985":
        conds.append("is_985 = 1")
    elif level == "211":
        conds.append("is_211 = 1")
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    sql = (
        "SELECT university_name, category, batch, min_rank, is_985, is_211 "
        f"FROM admission_school{where} ORDER BY min_rank ASC NULLS LAST LIMIT ?"
    )
    params.append(limit)
    con = _con()
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()
    out = [
        {"school": r[0], "category": r[1], "batch": r[2], "min_rank": r[3],
         "is_985": bool(r[4]), "is_211": bool(r[5])}
        for r in rows
    ]
    return json.dumps(out, ensure_ascii=False)


@server.tool(description="返回数据质量校验报告：各表行数、一分一段完整性、字段覆盖率等。")
def validate_data() -> str:
    con = _con()
    try:
        report: dict = {"tables": {}, "checks": []}
        for t in ("score_range", "admission_school", "admission_major", "enrollment_plan"):
            exists = con.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [t]
            ).fetchone()[0]
            if not exists:
                report["tables"][t] = {"present": False}
                continue
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            report["tables"][t] = {"present": True, "rows": n}
        nonempty = con.execute(
            "SELECT COUNT(*) FROM score_range WHERE score IS NOT NULL"
        ).fetchone()[0]
        report["checks"].append({
            "check": "一分一段完整性",
            "detail": f"score 非空 {nonempty}/{report['tables'].get('score_range',{}).get('rows',0)} 行",
        })
    finally:
        con.close()
    return json.dumps(report, ensure_ascii=False, indent=2)


@server.tool(description="检查本地数据版本与覆盖情况，可选用联网对比仓库最新数据版本（判断是否可更新）。")
def check_update(check_remote: bool = False) -> str:
    """数据版本检查：本地 data/version.json vs 仓库最新（可选联网）。"""
    import urllib.request

    ver_path = Path("data/version.json")
    result: dict = {"local": None, "coverage": {}, "remote": None, "update_available": False}
    if ver_path.exists():
        try:
            local = json.loads(ver_path.read_text(encoding="utf-8"))
            result["local"] = local.get("data_version")
            result["coverage"] = local.get("coverage", {})
            result["sources_total"] = len(local.get("sources", []))
            result["verified_total"] = sum(
                1 for s in local.get("sources", []) if s.get("verified")
            )
        except Exception as e:
            result["local_error"] = str(e)
    else:
        result["local_error"] = "缺少 data/version.json（尚未生成数据版本）"

    if check_remote:
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/XucroYuri/lever-gaokao/contents/data/version.json",
                headers={"User-Agent": "lever-gaokao-mcp", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read())
            import base64

            remote = json.loads(base64.b64decode(payload["content"]))
            result["remote"] = remote.get("data_version")
            result["remote_updated_at"] = remote.get("generated_at")
            if result["local"] and result["remote"]:
                result["update_available"] = result["remote"] != result["local"]
        except Exception as e:
            result["remote_error"] = str(e)

    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    server.run(transport="stdio")
