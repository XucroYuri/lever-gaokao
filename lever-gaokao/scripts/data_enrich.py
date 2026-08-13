#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# dependencies = ["duckdb>=1.5,<2"]
# ///
# ─── How to run ───
# python lever-gaokao/scripts/data_enrich.py --db data/gaokao.duckdb

"""Load the 2025 Ministry of Education school list and enrich admissions."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NewType

import duckdb

CONTENTS_URL: Final = (
    "https://api.github.com/repos/zstar1003/zmex/contents/data/schools.json"
)
SOURCE_ID: Final = "moe-schools-2025-zmex"
SOURCE_URL: Final = "https://github.com/zstar1003/zmex/blob/main/data/schools.json"
EXPECTED_SCHOOL_COUNT: Final = 2919
SchoolCode = NewType("SchoolCode", str)
type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


class SourceDataError(RuntimeError):
    """Raised when the remote school source violates its expected contract."""


@dataclass(frozen=True, slots=True)
class School:
    """Normalized school dimension row."""

    school_code: SchoolCode
    school_name: str
    school_nature: str
    authority: str
    province: str
    city: str
    level: str
    source_id: str = SOURCE_ID


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Verified metadata retained from the source document."""

    source_date: str
    raw_fields: tuple[str, ...]


def fetch_json(url: str) -> dict[str, JsonValue]:
    """Fetch a GitHub API JSON object with the required curl executable."""
    completed = subprocess.run(
        ["curl.exe", "-sL", "--fail-with-body", url],
        check=True,
        capture_output=True,
    )
    parsed = json.loads(completed.stdout)
    if not isinstance(parsed, dict):
        raise SourceDataError("GitHub API response is not a JSON object")
    return parsed


def required_text(record: dict[str, JsonValue], key: str) -> str:
    """Parse one required non-empty string field."""
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SourceDataError(f"school field {key!r} is missing or invalid")
    return value.strip()


def parse_schools(
    payload: dict[str, JsonValue],
) -> tuple[list[School], SourceMetadata]:
    """Parse and validate the decoded zmex school document."""
    raw_meta = payload.get("meta")
    raw_schools = payload.get("schools")
    if not isinstance(raw_meta, dict) or not isinstance(raw_schools, list):
        raise SourceDataError("schools document must contain meta and schools")
    schools: list[School] = []
    for raw_school in raw_schools:
        if not isinstance(raw_school, dict):
            raise SourceDataError("schools must contain JSON objects")
        nature = required_text(raw_school, "nature")
        schools.append(
            School(
                school_code=SchoolCode(required_text(raw_school, "code")),
                school_name=required_text(raw_school, "name"),
                school_nature=nature if nature in {"公办", "民办"} else "其他",
                authority=required_text(raw_school, "department"),
                province=required_text(raw_school, "province"),
                city=required_text(raw_school, "city"),
                level=required_text(raw_school, "level"),
            )
        )
    declared_count = raw_meta.get("totalSchools")
    if declared_count != len(schools) or len(schools) != EXPECTED_SCHOOL_COUNT:
        raise SourceDataError(
            f"school count mismatch: metadata={declared_count}, parsed={len(schools)}"
        )
    if len({school.school_code for school in schools}) != len(schools):
        raise SourceDataError("school codes are not unique")
    if any(len(school.school_code) != 10 or not school.school_code.isdigit() for school in schools):
        raise SourceDataError("school code is not a 10-digit MOE identifier")
    source_date = required_text(raw_meta, "sourceDate")
    first_school = raw_schools[0]
    if not isinstance(first_school, dict):
        raise SourceDataError("first school is not a JSON object")
    return schools, SourceMetadata(source_date, tuple(first_school))


def download_schools() -> tuple[list[School], SourceMetadata]:
    """Download a large GitHub file via its base64 Git blob representation."""
    descriptor = fetch_json(CONTENTS_URL)
    encoded = descriptor.get("content")
    if descriptor.get("encoding") != "base64" or not isinstance(encoded, str):
        blob_url = descriptor.get("git_url")
        if not isinstance(blob_url, str):
            raise SourceDataError("GitHub descriptor has neither content nor git_url")
        blob = fetch_json(blob_url)
        encoded = blob.get("content")
        if blob.get("encoding") != "base64" or not isinstance(encoded, str):
            raise SourceDataError("GitHub blob response has no base64 content")
    payload = json.loads(base64.b64decode(encoded).decode("utf-8"))
    if not isinstance(payload, dict):
        raise SourceDataError("decoded schools document is not a JSON object")
    return parse_schools(payload)


def enrich_database(db_path: Path, schools: list[School]) -> None:
    """Replace school_dim and fill only NULL admission fields in one transaction."""
    rows = [
        (
            school.school_code,
            school.school_name,
            school.school_nature,
            school.authority,
            school.province,
            school.city,
            school.level,
            school.source_id,
        )
        for school in schools
    ]
    for attempt in range(2):
        try:
            with duckdb.connect(str(db_path)) as connection:
                connection.begin()
                connection.execute(
                    """CREATE OR REPLACE TABLE school_dim (
                        school_code VARCHAR, school_name VARCHAR,
                        school_nature VARCHAR, authority VARCHAR, province VARCHAR,
                        city VARCHAR, level VARCHAR, source_id VARCHAR
                    )"""
                )
                connection.executemany(
                    "INSERT INTO school_dim VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
                )
                connection.execute(
                    """INSERT INTO source_ledger
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM source_ledger WHERE source_id = ?
                    )""",
                    [SOURCE_ID, "教育部2025全国普通高等学校名单（zmex整理）", "开放数据",
                     SOURCE_URL, "MIT", "全国", 2025, "school_dim", True, SOURCE_ID],
                )
                for table in ("admission_major", "admission_school"):
                    connection.execute(
                        f"""UPDATE {table} AS admission
                        SET school_nature = school.school_nature
                        FROM school_dim AS school
                        WHERE admission.university_name = school.school_name
                          AND admission.school_nature IS NULL"""
                    )
                    connection.execute(
                        f"""UPDATE {table} AS admission
                        SET university_code = school.school_code
                        FROM school_dim AS school
                        WHERE admission.university_name = school.school_name
                          AND admission.university_code IS NULL"""
                    )
                connection.commit()
            return
        except duckdb.IOException:
            if attempt == 1:
                raise
            time.sleep(3)


def main() -> None:
    """Run the school dimension enrichment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/gaokao.duckdb"))
    args = parser.parse_args()
    schools, metadata = download_schools()
    enrich_database(args.db, schools)
    print(
        json.dumps(
            {
                "source_fields": metadata.raw_fields,
                "source_date": metadata.source_date,
                "school_dim_rows": len(schools),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
