#!/usr/bin/env python3
"""Deterministic CSV ledger helper for the college-admission skill."""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import re
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


FIELD_ORDER = [
    "candidate_id",
    "province",
    "year",
    "batch",
    "category",
    "subject_type",
    "institution",
    "city",
    "school_nature",
    "authority",
    "volunteer_unit",
    "major_group",
    "major",
    "plan_count",
    "selection_requirements",
    "tuition",
    "campus",
    "restrictions",
    "source_type",
    "source_ref",
    "source_status",
    "discovery_method",
    "tags",
    "current_status",
    "downgrade_reason",
    "reentry_condition",
    "next_action",
    "review_role",
]

REQUIRED_FIELDS = [
    "candidate_id",
    "institution",
    "volunteer_unit",
    "source_type",
    "source_status",
    "discovery_method",
    "current_status",
]

VALID_STATUSES = {"候选", "观察", "降级", "剔除", "待核验", "最终组合"}
REENTRY_STATUSES = {"观察", "降级", "剔除", "待核验"}

SUBJECT_ALIASES = {
    "物理": ("物理", "物"),
    "化学": ("化学", "化"),
    "生物": ("生物", "生"),
    "政治": ("思想政治", "政治", "政"),
    "历史": ("历史", "史"),
    "地理": ("地理", "地"),
    "技术": ("技术", "技"),
}


class ToolError(Exception):
    pass


def read_csv(path: str) -> tuple[list[dict[str, str]], list[str]]:
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ToolError(f"CSV 缺少表头: {path}")
            rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
            return rows, [field.strip() for field in reader.fieldnames]
    except FileNotFoundError as exc:
        raise ToolError(f"无法读取 CSV 文件: {path}") from exc
    except UnicodeDecodeError as exc:
        raise ToolError(f"CSV 不是 UTF-8 编码: {path}") from exc


def fieldnames_for(rows: list[dict[str, str]], source_fields: list[str] | None = None) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for field in FIELD_ORDER + (source_fields or []):
        if field not in seen:
            ordered.append(field)
            seen.add(field)
    for row in rows:
        for field in row:
            if field not in seen:
                ordered.append(field)
                seen.add(field)
    return ordered


def write_csv(path: str, rows: list[dict[str, str]], source_fields: list[str] | None = None) -> None:
    fields = fieldnames_for(rows, source_fields)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def status_for(errors: list[str], warnings: list[str]) -> str:
    if errors:
        return "error"
    if warnings:
        return "warn"
    return "pass"


def emit_human(command: str, report: dict[str, Any]) -> None:
    label = {"pass": "PASS", "warn": "WARN", "error": "ERROR"}[report["status"]]
    print(f"[{label}] {command}")
    print(f"摘要: {report.get('summary', '')}")
    print(f"错误: {len(report['errors'])}; 警告: {len(report['warnings'])}")
    for item in report["errors"]:
        print(f"- ERROR: {item}")
    for item in report["warnings"]:
        print(f"- WARN: {item}")


def write_report(path: str | None, report: dict[str, Any]) -> None:
    if not path:
        return
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def ratio_0_to_1(value: str) -> float:
    try:
        ratio = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("比例必须是 0 到 1 之间的数字") from exc
    if ratio < 0 or ratio > 1:
        raise argparse.ArgumentTypeError("比例必须在 0 到 1 之间")
    return ratio


def validate_rows(rows: list[dict[str, str]], fields: list[str]) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {"row_count": len(rows)}

    missing_fields = [field for field in REQUIRED_FIELDS if field not in fields]
    if missing_fields:
        errors.append("缺少必填字段: " + ", ".join(missing_fields))

    duplicate_ids = [cid for cid, count in Counter(row.get("candidate_id", "") for row in rows if row.get("candidate_id")).items() if count > 1]
    if duplicate_ids:
        errors.append("candidate_id 重复: " + ", ".join(sorted(duplicate_ids)))
    details["duplicate_ids"] = sorted(duplicate_ids)

    invalid_status_rows: list[str] = []
    missing_value_rows: list[str] = []
    missing_reentry_rows: list[str] = []
    for idx, row in enumerate(rows, start=2):
        label = row.get("candidate_id") or f"第 {idx} 行"
        for field in REQUIRED_FIELDS:
            if field in fields and not row.get(field):
                missing_value_rows.append(f"{label}:{field}")
        status = row.get("current_status", "")
        if status and status not in VALID_STATUSES:
            invalid_status_rows.append(f"{label}:{status}")
        if status in REENTRY_STATUSES and "reentry_condition" in fields and not row.get("reentry_condition"):
            missing_reentry_rows.append(label)

    if missing_value_rows:
        errors.append("必填字段存在空值: " + ", ".join(missing_value_rows))
    if invalid_status_rows:
        errors.append("current_status 非法: " + ", ".join(invalid_status_rows))
    if "reentry_condition" not in fields:
        errors.append("缺少字段: reentry_condition")
    elif missing_reentry_rows:
        warnings.append("观察/降级/剔除/待核验候选缺少复入条件: " + ", ".join(missing_reentry_rows))

    return errors, warnings, details


def command_template(args: argparse.Namespace) -> int:
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELD_ORDER)
            writer.writeheader()
        print(f"[PASS] template\n摘要: 已写出候选 CSV 模板: {args.output}")
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=FIELD_ORDER)
        writer.writeheader()
    return 0


def command_validate(args: argparse.Namespace) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    try:
        rows, fields = read_csv(args.csv_path)
        errors, warnings, details = validate_rows(rows, fields)
    except ToolError as exc:
        errors.append(str(exc))

    report = {
        "command": "validate-candidate-table",
        "status": status_for(errors, warnings),
        "summary": "候选表结构校验完成",
        "errors": errors,
        "warnings": warnings,
        "details": details,
    }
    emit_human("validate-candidate-table", report)
    write_report(args.report, report)
    return 1 if errors else 0


def parse_money(value: str) -> float | None:
    text = (value or "").replace(",", "").strip()
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    amount = float(match.group(0))
    if "万" in text:
        amount *= 10000
    return amount


def requirement_subjects(requirement: str) -> set[str]:
    if not requirement or "不限" in requirement:
        return set()
    required: set[str] = set()
    for subject, aliases in SUBJECT_ALIASES.items():
        if any(alias in requirement for alias in aliases):
            required.add(subject)
    return required


def user_has_subject(subject_text: str, subject: str) -> bool:
    return any(alias in subject_text for alias in SUBJECT_ALIASES[subject])


def subject_compatible(user_subject: str, requirement: str) -> bool:
    required = requirement_subjects(requirement)
    if not required:
        return True
    return all(user_has_subject(user_subject, subject) for subject in required)


def contains_any(value: str, needles: list[str]) -> bool:
    return any(needle and needle in value for needle in needles)


def append_reason(row: dict[str, str], reasons: list[str]) -> None:
    existing = row.get("downgrade_reason", "").strip()
    reason_text = "；".join(reasons)
    row["downgrade_reason"] = f"{existing}；{reason_text}" if existing else reason_text


def command_filter(args: argparse.Namespace) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    output_rows: list[dict[str, str]] = []
    fields: list[str] = []

    try:
        rows, fields = read_csv(args.csv_path)
        validation_errors, validation_warnings, _ = validate_rows(rows, fields)
        if validation_errors:
            errors.extend(validation_errors)
        warnings.extend(validation_warnings)
        for row in rows:
            result = dict(row)
            reasons: list[str] = []
            if args.batch and row.get("batch") and row.get("batch") != args.batch:
                reasons.append(f"批次不匹配: {row.get('batch')} != {args.batch}")
            if args.subject_type and not subject_compatible(args.subject_type, row.get("selection_requirements", "")):
                reasons.append(f"选科不匹配: {row.get('selection_requirements')}")
            if args.max_tuition is not None:
                tuition = parse_money(row.get("tuition", ""))
                if tuition is not None and tuition > args.max_tuition:
                    reasons.append(f"学费超预算: {int(tuition)} > {int(args.max_tuition)}")
            if args.allow_nature:
                nature = row.get("school_nature", "")
                if nature and not any(allowed in nature or nature in allowed for allowed in args.allow_nature):
                    reasons.append(f"办学性质不在允许范围: {nature}")
            if args.exclude_region and contains_any(row.get("city", ""), args.exclude_region):
                reasons.append(f"地区命中排除项: {row.get('city')}")
            if args.unacceptable_major_keyword:
                major_text = " ".join([row.get("major", ""), row.get("major_group", "")])
                if contains_any(major_text, args.unacceptable_major_keyword):
                    reasons.append("专业命中不可接受关键词")

            if reasons:
                result["current_status"] = "剔除"
                append_reason(result, reasons)
                result["review_role"] = "filter-candidates"
                result["reentry_condition"] = result.get("reentry_condition") or "硬约束变化或主 Agent 复核认定可接受后复入"
                result["next_action"] = result.get("next_action") or "主 Agent 复核硬约束后决定是否复入"
            output_rows.append(result)
        details["filtered_count"] = sum(1 for row in output_rows if row.get("current_status") == "剔除" and row.get("review_role") == "filter-candidates")
        details["row_count"] = len(output_rows)
        if args.output:
            write_csv(args.output, output_rows, fields)
    except ToolError as exc:
        errors.append(str(exc))

    report = {
        "command": "filter-candidates",
        "status": status_for(errors, warnings),
        "summary": "硬规则过滤完成；脚本不判断候选价值",
        "errors": errors,
        "warnings": warnings,
        "details": details,
    }
    emit_human("filter-candidates", report)
    write_report(args.report, report)
    return 1 if errors else 0


def command_merge(args: argparse.Namespace) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    merged: dict[str, dict[str, str]] = {}
    history: dict[str, list[dict[str, str]]] = defaultdict(list)
    fields: list[str] = []
    conflicts: list[dict[str, str]] = []

    try:
        for path in args.csv_paths:
            rows, source_fields = read_csv(path)
            fields.extend(source_fields)
            if "candidate_id" not in source_fields:
                errors.append(f"{path} 缺少 candidate_id，无法合并")
                continue
            for row in rows:
                cid = row.get("candidate_id", "")
                if not cid:
                    errors.append(f"{path} 存在空 candidate_id")
                    continue
                previous = merged.get(cid)
                history[cid].append({"source_file": path, **row})
                if previous:
                    if previous.get("institution") != row.get("institution") or previous.get("volunteer_unit") != row.get("volunteer_unit"):
                        errors.append(f"candidate_id {cid} 指向不同院校或志愿单位，无法安全合并")
                        continue
                    if previous.get("current_status") != row.get("current_status"):
                        conflicts.append({
                            "candidate_id": cid,
                            "old_status": previous.get("current_status", ""),
                            "new_status": row.get("current_status", ""),
                        })
                merged[cid] = {**(previous or {}), **{key: value for key, value in row.items() if value}}
        if conflicts:
            warnings.append(f"发现 {len(conflicts)} 个候选状态变化或冲突，已保留最新非空字段并写入报告")
        output_rows = list(merged.values())
        if args.output and not errors:
            write_csv(args.output, output_rows, fields)
    except ToolError as exc:
        errors.append(str(exc))

    report = {
        "command": "merge-ledgers",
        "status": status_for(errors, warnings),
        "summary": "ledger 合并完成；候选不会因后续文件缺失而被删除",
        "errors": errors,
        "warnings": warnings,
        "details": {
            "candidate_count": len(merged),
            "conflicts": conflicts,
            "history": history,
        },
    }
    emit_human("merge-ledgers", report)
    write_report(args.report, report)
    return 1 if errors else 0


def has_adjustment_audit(row: dict[str, str]) -> bool:
    text = " ".join([row.get("tags", ""), row.get("next_action", ""), row.get("downgrade_reason", ""), row.get("restrictions", "")])
    return any(keyword in text for keyword in ["调剂", "最差", "专业组", "组内", "服从"])


def command_audit_final(args: argparse.Namespace) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    try:
        rows, fields = read_csv(args.csv_path)
        validation_errors, validation_warnings, _ = validate_rows(rows, fields)
        errors.extend(validation_errors)
        warnings.extend(validation_warnings)
        bad_status = []
        not_final = []
        missing_adjustment = []
        gradients = Counter()
        for row in rows:
            cid = row.get("candidate_id") or row.get("institution") or "未知候选"
            status = row.get("current_status", "")
            if status in {"待核验", "剔除"}:
                bad_status.append(f"{cid}:{status}")
            elif status and status != "最终组合":
                not_final.append(f"{cid}:{status}")
            gradient_text = " ".join([row.get("tags", ""), row.get("downgrade_reason", ""), row.get("next_action", "")])
            for keyword in ["保底", "兜底", "强稳", "稳妥", "冲刺"]:
                if keyword in gradient_text:
                    gradients[keyword] += 1
            if row.get("major_group") and not has_adjustment_audit(row):
                missing_adjustment.append(cid)

        if bad_status:
            errors.append("最终组合包含不可直接进入最终表的状态: " + ", ".join(bad_status))
        if not_final:
            warnings.append("最终组合候选 current_status 不是最终组合: " + ", ".join(not_final))
        if not (gradients["保底"] or gradients["兜底"]):
            warnings.append("最终组合缺少明确保底/兜底标签")
        if missing_adjustment:
            warnings.append("存在专业组但未看到专业组调剂审计线索: " + ", ".join(missing_adjustment))
        details = {"row_count": len(rows), "gradient_counts": dict(gradients)}
    except ToolError as exc:
        errors.append(str(exc))

    report = {
        "command": "audit-final-table",
        "status": status_for(errors, warnings),
        "summary": "最终组合机械审计完成",
        "errors": errors,
        "warnings": warnings,
        "details": details,
    }
    emit_human("audit-final-table", report)
    write_report(args.report, report)
    return 1 if errors else 0


def joined_row_text(row: dict[str, str]) -> str:
    return " ".join(row.get(field, "") for field in ["institution", "authority", "school_nature", "tags", "major", "major_group", "city"])


def row_matches_region(row: dict[str, str], keywords: list[str]) -> bool:
    if not keywords:
        return False
    text = " ".join(row.get(field, "") for field in ["province", "city", "campus"])
    return any(keyword and keyword in text for keyword in keywords)


def command_coverage(args: argparse.Namespace) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    try:
        rows, fields = read_csv(args.csv_path)
        validation_errors, validation_warnings, _ = validate_rows(rows, fields)
        errors.extend(validation_errors)
        warnings.extend(validation_warnings)
        provinces = Counter(row.get("province", "") for row in rows if row.get("province"))
        cities = Counter(row.get("city", "") for row in rows if row.get("city"))
        texts = [joined_row_text(row) for row in rows]
        all_text = "\n".join(texts)

        if args.home_province and rows:
            home_count = sum(1 for row in rows if row.get("province") == args.home_province)
            if home_count == len(rows):
                warnings.append("候选池全部来自本省，可能遗漏本省外或非同源低估机会")
        elif len(provinces) <= 1 and rows:
            warnings.append("候选池省份过于集中，建议检查本省外或非同源候选覆盖")

        home_region_keywords = getattr(args, "home_region_keyword", []) or []
        min_outside_ratio = getattr(args, "min_outside_home_region_ratio", 0.25)
        home_region_match_count = 0
        outside_home_region_ratio: float | None = None
        if home_region_keywords and rows:
            home_region_match_count = sum(1 for row in rows if row_matches_region(row, home_region_keywords))
            outside_home_region_ratio = (len(rows) - home_region_match_count) / len(rows)
            if outside_home_region_ratio < min_outside_ratio:
                warnings.append(
                    "候选池过度集中于本省/本区域，可能遗漏区域外低估机会、升学跳板或真保底对照组"
                )

        for city in args.popular_city or []:
            if rows and sum(1 for row in rows if city in row.get("city", "")) / len(rows) >= 0.7:
                warnings.append(f"候选池过度集中于热门城市: {city}")

        if not re.search(r"985|211|双一流|部委|中央|直属|硕博|保研|高平台", all_text):
            warnings.append("未看到高平台、保研/硕博或部委直属相关候选线索")
        if not re.search(r"海关|外交|民航|铁路|电力|应急|司法|公安|金融监管|行业|系统", all_text):
            warnings.append("未看到行业特色或特殊身份候选线索")
        if not re.search(r"AI|人工智能|区域国别|一带一路|供应链|绿色低碳|公共治理|人口|老龄|应急", all_text, re.IGNORECASE):
            warnings.append("未看到宏观变量候选标签")
        if not re.search(r"高职|专科|职业本科", all_text):
            warnings.append("未看到优质高职/职业本科扩展画像候选")

        majors = [row.get("major", "") or row.get("major_group", "") for row in rows]
        major_roots = [major[:4] for major in majors if major]
        if major_roots:
            top_major, top_count = Counter(major_roots).most_common(1)[0]
            if top_count / len(major_roots) >= 0.7:
                warnings.append(f"候选专业方向过于集中，可能过拟合单一方向: {top_major}")
        details = {
            "row_count": len(rows),
            "province_counts": dict(provinces),
            "city_counts": dict(cities),
            "home_region_keywords": home_region_keywords,
            "home_region_match_count": home_region_match_count,
            "outside_home_region_ratio": outside_home_region_ratio,
        }
    except ToolError as exc:
        errors.append(str(exc))

    report = {
        "command": "coverage-audit",
        "status": status_for(errors, warnings),
        "summary": "覆盖缺口审计完成；提示只作为补充搜索方向",
        "errors": errors,
        "warnings": warnings,
        "details": details,
    }
    emit_human("coverage-audit", report)
    write_report(args.report, report)
    return 1 if errors else 0


def sample_selftest_rows() -> list[dict[str, str]]:
    base = {
        "province": "样例本省",
        "year": "2026",
        "batch": "本科批",
        "category": "普通类",
        "subject_type": "物化政",
        "plan_count": "10",
        "selection_requirements": "物理",
        "campus": "主校区",
        "source_ref": "selftest",
        "source_status": "待核验假设",
        "current_status": "候选",
        "downgrade_reason": "",
        "reentry_condition": "",
        "next_action": "核验当年官方计划",
        "review_role": "selftest",
    }
    return [
        {
            **base,
            "candidate_id": "C001",
            "institution": "样例稳妥大学",
            "city": "样例城市A",
            "school_nature": "公办",
            "authority": "省属",
            "volunteer_unit": "样例稳妥大学-01",
            "major_group": "01专业组",
            "major": "金融学",
            "tuition": "5000",
            "restrictions": "已审计专业组调剂，最差可接受",
            "source_type": "用户提供",
            "discovery_method": "用户提供",
            "tags": "稳妥 保底 调剂",
        },
        {
            **base,
            "candidate_id": "C002",
            "institution": "样例高费学院",
            "city": "样例城市B",
            "school_nature": "民办",
            "authority": "民办",
            "volunteer_unit": "样例高费学院-01",
            "major_group": "01专业组",
            "major": "会计学",
            "selection_requirements": "不限",
            "tuition": "25000",
            "restrictions": "",
            "source_type": "用户提供",
            "discovery_method": "用户提供",
            "tags": "热门城市",
            "next_action": "核验费用和家庭预算",
        },
        {
            **base,
            "candidate_id": "C003",
            "institution": "样例待核验大学",
            "city": "样例城市C",
            "school_nature": "公办",
            "authority": "行业特色",
            "volunteer_unit": "样例待核验大学-02",
            "major_group": "02专业组",
            "major": "应急管理",
            "tuition": "6000",
            "restrictions": "",
            "source_type": "口碑线索",
            "discovery_method": "机会雷达",
            "tags": "应急 行业 宏观变量",
            "current_status": "待核验",
            "downgrade_reason": "缺少当年官方计划",
            "reentry_condition": "当年官方招生计划确认后复入",
            "next_action": "核验省考试院计划",
        },
    ]


def write_raw_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_selftest_step(label: str, func: Any, args: argparse.Namespace, expected_code: int) -> tuple[str | None, dict[str, Any]]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = func(args)
    detail = {"label": label, "expected_code": expected_code, "actual_code": code}
    if code != expected_code:
        detail["output"] = buffer.getvalue()
        return f"{label} 返回码 {code}，预期 {expected_code}", detail
    return None, detail


def command_selftest(args: argparse.Namespace) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    steps: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="ledger_tool_selftest_") as tmpdir:
        root = Path(tmpdir)
        template_path = root / "template.csv"
        candidates_path = root / "candidates.csv"
        bad_path = root / "bad.csv"
        filtered_path = root / "filtered.csv"
        merged_path = root / "merged.csv"
        final_path = root / "final.csv"
        coverage_region_report = root / "coverage-region.json"
        coverage_diverse_path = root / "coverage-diverse.csv"
        coverage_diverse_report = root / "coverage-diverse.json"
        coverage_tag_false_positive_path = root / "coverage-tag-false-positive.csv"
        coverage_tag_false_positive_report = root / "coverage-tag-false-positive.json"

        rows = sample_selftest_rows()
        write_csv(str(candidates_path), rows, FIELD_ORDER)
        bad_fields = [field for field in FIELD_ORDER if field != "source_type"]
        write_raw_csv(bad_path, bad_fields, rows[:1])
        final_rows = [
            {**rows[0], "current_status": "最终组合", "tags": "保底 调剂 最差可接受"},
            rows[2],
        ]
        write_csv(str(final_path), final_rows, FIELD_ORDER)
        diverse_rows = rows + [
            {
                **rows[0],
                "candidate_id": "C004",
                "province": "样例外省",
                "institution": "样例异地大学",
                "city": "样例外省城市",
                "volunteer_unit": "样例异地大学-01",
                "major": "汉语言文学",
                "tags": "非同源对照 学风升学",
            }
        ]
        write_csv(str(coverage_diverse_path), diverse_rows, FIELD_ORDER)
        tag_false_positive_rows = rows + [
            {
                **rows[0],
                "candidate_id": "C005",
                "province": "样例外省",
                "institution": "样例异地大学",
                "city": "样例外省城市B",
                "volunteer_unit": "样例异地大学-01",
                "major": "数据科学与大数据技术",
                "tags": "样例本省生源友好 非同源对照",
            }
        ]
        write_csv(str(coverage_tag_false_positive_path), tag_false_positive_rows, FIELD_ORDER)

        checks = [
            (
                "template",
                command_template,
                argparse.Namespace(output=str(template_path)),
                0,
            ),
            (
                "validate good candidates",
                command_validate,
                argparse.Namespace(csv_path=str(candidates_path), report=None),
                0,
            ),
            (
                "validate missing field",
                command_validate,
                argparse.Namespace(csv_path=str(bad_path), report=None),
                1,
            ),
            (
                "filter hard constraints",
                command_filter,
                argparse.Namespace(
                    csv_path=str(candidates_path),
                    output=str(filtered_path),
                    report=None,
                    subject_type="物化政",
                    batch="本科批",
                    max_tuition=8000,
                    allow_nature=[],
                    exclude_region=[],
                    unacceptable_major_keyword=[],
                ),
                0,
            ),
            (
                "merge ledgers",
                command_merge,
                argparse.Namespace(csv_paths=[str(candidates_path), str(filtered_path)], output=str(merged_path), report=None),
                0,
            ),
            (
                "audit final catches pending",
                command_audit_final,
                argparse.Namespace(csv_path=str(final_path), report=None),
                1,
            ),
            (
                "coverage audit warnings only",
                command_coverage,
                argparse.Namespace(csv_path=str(candidates_path), home_province="样例本省", popular_city=["样例城市C"], report=None),
                0,
            ),
        ]

        for label, func, step_args, expected in checks:
            error, detail = run_selftest_step(label, func, step_args, expected)
            steps.append(detail)
            if error:
                errors.append(error)

        if template_path.exists():
            header = template_path.read_text(encoding="utf-8").splitlines()[0]
            if "candidate_id" not in header:
                errors.append("template 未包含 candidate_id 字段")
        else:
            errors.append("template 未写出文件")

        if filtered_path.exists():
            filtered_rows, _ = read_csv(str(filtered_path))
            filtered = {row.get("candidate_id"): row for row in filtered_rows}
            if filtered.get("C002", {}).get("current_status") != "剔除":
                errors.append("filter-candidates 未将高费候选 C002 标记为剔除")
        else:
            errors.append("filter-candidates 未写出过滤结果")

        if merged_path.exists():
            merged_rows, _ = read_csv(str(merged_path))
            if len(merged_rows) != 3:
                errors.append(f"merge-ledgers 合并后候选数量异常: {len(merged_rows)}")
        else:
            errors.append("merge-ledgers 未写出合并结果")

        region_args = [
            "coverage-audit",
            str(candidates_path),
            "--home-region-keyword",
            "样例本省",
            "--home-region-keyword",
            "样例邻区",
            "--min-outside-home-region-ratio",
            "0.25",
            "--report",
            str(coverage_region_report),
        ]
        region_buffer = io.StringIO()
        region_error_buffer = io.StringIO()
        with contextlib.redirect_stdout(region_buffer), contextlib.redirect_stderr(region_error_buffer):
            try:
                region_code = main(region_args)
            except SystemExit as exc:
                region_code = int(exc.code or 0)
        steps.append({"label": "coverage CLI home region warning", "expected_code": 0, "actual_code": region_code})
        if region_code != 0:
            errors.append("coverage-audit 新增地域参数返回码异常: " + region_error_buffer.getvalue().strip())
        elif coverage_region_report.exists():
            region_report = json.loads(coverage_region_report.read_text(encoding="utf-8"))
            region_warnings = "\n".join(region_report.get("warnings", []))
            if "本省/本区域" not in region_warnings:
                errors.append("coverage-audit 未提示本省/本区域候选过度集中")
            if "outside_home_region_ratio" not in region_report.get("details", {}):
                errors.append("coverage-audit 报告缺少 outside_home_region_ratio")
        else:
            errors.append("coverage-audit 未写出本区域覆盖报告")

        diverse_args = [
            "coverage-audit",
            str(coverage_diverse_path),
            "--home-region-keyword",
            "样例本省",
            "--home-region-keyword",
            "样例邻区",
            "--min-outside-home-region-ratio",
            "0.25",
            "--report",
            str(coverage_diverse_report),
        ]
        diverse_buffer = io.StringIO()
        diverse_error_buffer = io.StringIO()
        with contextlib.redirect_stdout(diverse_buffer), contextlib.redirect_stderr(diverse_error_buffer):
            try:
                diverse_code = main(diverse_args)
            except SystemExit as exc:
                diverse_code = int(exc.code or 0)
        steps.append({"label": "coverage CLI home region passes with outside candidate", "expected_code": 0, "actual_code": diverse_code})
        if diverse_code != 0:
            errors.append("coverage-audit 非同源对照样例返回码异常: " + diverse_error_buffer.getvalue().strip())
        elif coverage_diverse_report.exists():
            diverse_report = json.loads(coverage_diverse_report.read_text(encoding="utf-8"))
            diverse_warnings = "\n".join(diverse_report.get("warnings", []))
            if "本省/本区域" in diverse_warnings:
                errors.append("coverage-audit 在非同源候选达到阈值时仍提示本省/本区域集中")
        else:
            errors.append("coverage-audit 未写出非同源对照覆盖报告")

        invalid_ratio_args = [
            "coverage-audit",
            str(candidates_path),
            "--min-outside-home-region-ratio",
            "1.5",
        ]
        invalid_ratio_buffer = io.StringIO()
        invalid_ratio_error_buffer = io.StringIO()
        with contextlib.redirect_stdout(invalid_ratio_buffer), contextlib.redirect_stderr(invalid_ratio_error_buffer):
            try:
                invalid_ratio_code = main(invalid_ratio_args)
            except SystemExit as exc:
                invalid_ratio_code = int(exc.code or 0)
        steps.append({"label": "coverage CLI rejects invalid outside ratio", "expected_code": 2, "actual_code": invalid_ratio_code})
        if invalid_ratio_code != 2:
            errors.append("coverage-audit 未拒绝超出 0 到 1 范围的本区域外比例参数")

        tag_false_positive_args = [
            "coverage-audit",
            str(coverage_tag_false_positive_path),
            "--home-region-keyword",
            "样例本省",
            "--min-outside-home-region-ratio",
            "0.25",
            "--report",
            str(coverage_tag_false_positive_report),
        ]
        tag_false_positive_buffer = io.StringIO()
        tag_false_positive_error_buffer = io.StringIO()
        with contextlib.redirect_stdout(tag_false_positive_buffer), contextlib.redirect_stderr(tag_false_positive_error_buffer):
            try:
                tag_false_positive_code = main(tag_false_positive_args)
            except SystemExit as exc:
                tag_false_positive_code = int(exc.code or 0)
        steps.append(
            {"label": "coverage CLI ignores narrative fields for home-region ratio", "expected_code": 0, "actual_code": tag_false_positive_code}
        )
        if tag_false_positive_code != 0:
            errors.append("coverage-audit 叙事字段误匹配样例返回码异常: " + tag_false_positive_error_buffer.getvalue().strip())
        elif coverage_tag_false_positive_report.exists():
            tag_false_positive_report = json.loads(coverage_tag_false_positive_report.read_text(encoding="utf-8"))
            tag_false_positive_warnings = "\n".join(tag_false_positive_report.get("warnings", []))
            tag_false_positive_details = tag_false_positive_report.get("details", {})
            if "本省/本区域" in tag_false_positive_warnings:
                errors.append("coverage-audit 将 tags 中的地域叙事误算为本省/本区域候选")
            if tag_false_positive_details.get("outside_home_region_ratio") != 0.25:
                errors.append("coverage-audit tags 误匹配样例的区域外比例异常")
        else:
            errors.append("coverage-audit 未写出叙事字段误匹配覆盖报告")

    report = {
        "command": "selftest",
        "status": status_for(errors, warnings),
        "summary": "脚本标准库自检完成；不读取真实招生数据，不生成仓库内文件",
        "errors": errors,
        "warnings": warnings,
        "details": {"steps": steps},
    }
    emit_human("selftest", report)
    write_report(args.report, report)
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lever-GaoKao 候选池 ledger 确定性辅助工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    selftest = subparsers.add_parser("selftest", help="运行脚本标准库自检")
    selftest.add_argument("--report", help="写出 JSON 自检报告")
    selftest.set_defaults(func=command_selftest)

    template = subparsers.add_parser("template", help="输出候选 CSV 最小字段模板")
    template.add_argument("--output", help="写出模板 CSV")
    template.set_defaults(func=command_template)

    validate = subparsers.add_parser("validate-candidate-table", help="校验候选 CSV 字段、状态和 candidate_id")
    validate.add_argument("csv_path")
    validate.add_argument("--report", help="写出 JSON 审计报告")
    validate.set_defaults(func=command_validate)

    filter_cmd = subparsers.add_parser("filter-candidates", help="按显式硬约束过滤候选")
    filter_cmd.add_argument("csv_path")
    filter_cmd.add_argument("--output", help="写出过滤后的 CSV")
    filter_cmd.add_argument("--report", help="写出 JSON 审计报告")
    filter_cmd.add_argument("--subject-type", help="考生选科文本，例如 物化政")
    filter_cmd.add_argument("--batch", help="允许批次")
    filter_cmd.add_argument("--max-tuition", type=float, help="最高可接受学费，单位元/年")
    filter_cmd.add_argument("--allow-nature", action="append", default=[], help="允许办学性质，可重复")
    filter_cmd.add_argument("--exclude-region", action="append", default=[], help="排除城市或地区关键词，可重复")
    filter_cmd.add_argument("--unacceptable-major-keyword", action="append", default=[], help="不可接受专业关键词，可重复")
    filter_cmd.set_defaults(func=command_filter)

    merge = subparsers.add_parser("merge-ledgers", help="合并多轮候选池和 ledger")
    merge.add_argument("csv_paths", nargs="+")
    merge.add_argument("--output", help="写出合并后的 CSV")
    merge.add_argument("--report", help="写出 JSON 审计报告")
    merge.set_defaults(func=command_merge)

    audit = subparsers.add_parser("audit-final-table", help="审计最终组合表的机械风险")
    audit.add_argument("csv_path")
    audit.add_argument("--report", help="写出 JSON 审计报告")
    audit.set_defaults(func=command_audit_final)

    coverage = subparsers.add_parser("coverage-audit", help="提示候选池覆盖缺口和过拟合风险")
    coverage.add_argument("csv_path")
    coverage.add_argument("--home-province", help="考生所在省份，用于检查本省外或非同源覆盖")
    coverage.add_argument("--popular-city", action="append", default=[], help="热门城市关键词，可重复")
    coverage.add_argument("--home-region-keyword", action="append", default=[], help="本省、本区域或城市群关键词，可重复")
    coverage.add_argument(
        "--min-outside-home-region-ratio",
        type=ratio_0_to_1,
        default=0.25,
        help="候选池中本省/本区域外候选的最低比例，默认 0.25",
    )
    coverage.add_argument("--report", help="写出 JSON 审计报告")
    coverage.set_defaults(func=command_coverage)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
